import json
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

from axflow.engine import ApprovalRequired, Engine, InjectedStop, PlanError, validate
from axflow.runlog import inspect_run


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.engine = Engine(self.root / "state.db", self.root / "business.db")
        self.plan = {"version": "axflow.ir.v0", "steps": [
            {"id": "source", "op": "literal", "value": {"name": "fixture", "count": 2}},
            {"id": "field", "op": "field", "from": "source", "field": "count"},
            {"id": "save", "op": "sqlite_put", "from": "source"},
            {"id": "read", "op": "sqlite_get", "from": "save"},
        ]}

    def test_three_end_to_end_workflows_and_duplicate_replay(self):
        for suffix in ("a", "b", "c"):
            self.assertEqual(self.engine.execute(self.plan, "Run"+suffix, approve_writes=True), {"count": 2, "name": "fixture"})
        self.assertEqual(self.engine.execute(self.plan, "Runa", approve_writes=True), {"count": 2, "name": "fixture"})
        with closing(sqlite3.connect(self.root / "business.db")) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM records").fetchone()[0], 3)

    def test_write_requires_explicit_approval(self):
        with self.assertRaises(ApprovalRequired):
            self.engine.execute(self.plan, "Block")
        with closing(sqlite3.connect(self.root / "business.db")) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM records").fetchone()[0], 0)

    def test_restart_after_committed_write_does_not_duplicate(self):
        with self.assertRaises(InjectedStop):
            self.engine.execute(self.plan, "Crash", approve_writes=True, inject_stop_after_business=True)
        failed = inspect_run(self.root / "state.db", "Crash")
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error_type"], "InjectedStop")
        self.assertEqual(failed["steps_recorded"], 2)
        restarted = Engine(self.root / "state.db", self.root / "business.db")
        self.assertEqual(restarted.execute(self.plan, "Crash", approve_writes=True)["name"], "fixture")
        completed = inspect_run(self.root / "state.db", "Crash")
        self.assertEqual(completed["status"], "completed")
        self.assertIsNone(completed["error_type"])
        with closing(sqlite3.connect(self.root / "business.db")) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM records WHERE run_id='Crash'").fetchone()[0], 1)

    def test_concurrent_independent_runs_and_same_run_replay_are_idempotent(self):
        barrier = threading.Barrier(2)

        def execute(run_id):
            barrier.wait(timeout=5)
            return self.engine.execute(self.plan, run_id, approve_writes=True)

        with ThreadPoolExecutor(max_workers=2) as pool:
            outputs = list(pool.map(execute, ("ParallelA", "ParallelB")))
        self.assertEqual(outputs, [{"count": 2, "name": "fixture"}] * 2)

        duplicate_barrier = threading.Barrier(2)

        def duplicate():
            duplicate_barrier.wait(timeout=5)
            return self.engine.execute(self.plan, "SharedRun", approve_writes=True)

        with ThreadPoolExecutor(max_workers=2) as pool:
            duplicate_outputs = list(pool.map(lambda _: duplicate(), range(2)))
        self.assertEqual(duplicate_outputs, [{"count": 2, "name": "fixture"}] * 2)
        with closing(sqlite3.connect(self.root / "business.db")) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM records").fetchone()[0], 3)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM records WHERE run_id='SharedRun'").fetchone()[0], 1)
        with closing(sqlite3.connect(self.root / "state.db")) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM runs WHERE run_id='SharedRun'").fetchone()[0], 1)

    def test_concurrent_same_run_id_with_different_plan_is_rejected(self):
        changed = json.loads(json.dumps(self.plan))
        changed["steps"][0]["value"]["count"] = 9
        barrier = threading.Barrier(2)

        def attempt(plan):
            barrier.wait(timeout=5)
            try:
                return ("completed", self.engine.execute(plan, "Collision", approve_writes=True))
            except PlanError as exc:
                return ("rejected", str(exc))

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, (self.plan, changed)))
        self.assertCountEqual([item[0] for item in outcomes], ["completed", "rejected"])
        self.assertIn("same run id", next(item[1] for item in outcomes if item[0] == "rejected"))
        with closing(sqlite3.connect(self.root / "business.db")) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM records WHERE run_id='Collision'").fetchone()[0], 1)

    def test_rejects_invalid_specs_and_plan_reuse(self):
        for bad in ({"version": "n8n", "steps": []}, {"version": "axflow.ir.v0", "steps": [{"id": "ok", "op": "shell", "cmd": "rm -rf /"}]},
                    {"version": "axflow.ir.v0", "steps": [{"id": "one", "op": "field", "from": "two", "field": "x"}]}):
            with self.assertRaises(PlanError):
                validate(bad)
        self.engine.execute(self.plan, "Stable", approve_writes=True)
        changed = json.loads(json.dumps(self.plan));changed["steps"][0]["value"]["count"] = 3
        with self.assertRaises(PlanError):
            self.engine.execute(changed, "Stable", approve_writes=True)

    def test_cli_status_and_resume(self):
        path = self.root / "plan.json"
        path.write_text(json.dumps(self.plan), encoding="utf-8")
        base = [sys.executable, "-m", "axflow"]
        run_args = [str(path), "--state", str(self.root / "state.db"),
                    "--data", str(self.root / "business.db"), "--run-id", "ResumeCase",
                    "--synthetic", "--approve-writes"]
        first = subprocess.run(base + ["run"] + run_args, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        status = subprocess.run(base + ["status", "--state", str(self.root / "state.db"),
                                         "--run-id", "ResumeCase", "--synthetic"],
                                capture_output=True, text=True)
        self.assertEqual(status.returncode, 0, status.stderr)
        report = json.loads(status.stdout)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["steps_recorded"], 4)
        self.assertNotIn("fixture", str(report))
        restarted = subprocess.run(base + ["resume"] + run_args, capture_output=True, text=True)
        self.assertEqual(restarted.returncode, 0, restarted.stderr)
        with closing(sqlite3.connect(self.root / "business.db")) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM records WHERE run_id='ResumeCase'").fetchone()[0], 1)

    def test_cli_validate_requires_synthetic_flag(self):
        path = self.root / "plan.json"
        path.write_text(json.dumps(self.plan), encoding="utf-8")
        fail = subprocess.run([sys.executable, "-m", "axflow", "validate", str(path)], capture_output=True, text=True)
        self.assertEqual(fail.returncode, 2)
        ok = subprocess.run([sys.executable, "-m", "axflow", "validate", str(path), "--synthetic"], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)

    def test_cli_rejects_malformed_or_ambiguous_json_and_missing_paths(self):
        base = [sys.executable, "-m", "axflow", "validate"]
        malformed = self.root / "malformed.json"
        malformed.write_text('{"version":"axflow.ir.v0","version":"axflow.ir.v0","steps":[]}', encoding="utf-8")
        rejected = subprocess.run(base + [str(malformed), "--synthetic"], capture_output=True, text=True)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("duplicate JSON key", rejected.stderr)
        missing = subprocess.run(base + [str(self.root / "missing.json"), "--synthetic"], capture_output=True, text=True)
        self.assertEqual(missing.returncode, 2)
        self.assertIn("AX FLOW stopped safely", missing.stderr)

    def test_engine_rejects_path_like_run_ids_and_unsafe_database_paths(self):
        with self.assertRaises(PlanError):
            self.engine.execute(self.plan, "../escape", approve_writes=True)
        same = self.root / "same.db"
        with self.assertRaises(PlanError):
            Engine(same, same)
        missing_parent = self.root / "missing" / "state.db"
        with self.assertRaises(PlanError):
            Engine(missing_parent, self.root / "business.db")
        self.assertFalse(same.exists())
        self.assertFalse(missing_parent.parent.exists())


if __name__ == "__main__":
    unittest.main()
