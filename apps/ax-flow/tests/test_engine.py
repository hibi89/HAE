import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from axflow.engine import ApprovalRequired, Engine, InjectedStop, PlanError, validate


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
        with sqlite3.connect(self.root / "business.db") as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM records").fetchone()[0], 3)

    def test_write_requires_explicit_approval(self):
        with self.assertRaises(ApprovalRequired):
            self.engine.execute(self.plan, "Block")
        with sqlite3.connect(self.root / "business.db") as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM records").fetchone()[0], 0)

    def test_restart_after_committed_write_does_not_duplicate(self):
        with self.assertRaises(InjectedStop):
            self.engine.execute(self.plan, "Crash", approve_writes=True, inject_stop_after_business=True)
        restarted = Engine(self.root / "state.db", self.root / "business.db")
        self.assertEqual(restarted.execute(self.plan, "Crash", approve_writes=True)["name"], "fixture")
        with sqlite3.connect(self.root / "business.db") as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM records WHERE run_id='Crash'").fetchone()[0], 1)

    def test_rejects_invalid_specs_and_plan_reuse(self):
        for bad in ({"version": "n8n", "steps": []}, {"version": "axflow.ir.v0", "steps": [{"id": "ok", "op": "shell", "cmd": "rm -rf /"}]},
                    {"version": "axflow.ir.v0", "steps": [{"id": "one", "op": "field", "from": "two", "field": "x"}]}):
            with self.assertRaises(PlanError):
                validate(bad)
        self.engine.execute(self.plan, "Stable", approve_writes=True)
        changed = json.loads(json.dumps(self.plan));changed["steps"][0]["value"]["count"] = 3
        with self.assertRaises(PlanError):
            self.engine.execute(changed, "Stable", approve_writes=True)

    def test_cli_validate_requires_synthetic_flag(self):
        path = self.root / "plan.json"
        path.write_text(json.dumps(self.plan), encoding="utf-8")
        fail = subprocess.run([sys.executable, "-m", "axflow", "validate", str(path)], capture_output=True, text=True)
        self.assertEqual(fail.returncode, 2)
        ok = subprocess.run([sys.executable, "-m", "axflow", "validate", str(path), "--synthetic"], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)


if __name__ == "__main__":
    unittest.main()
