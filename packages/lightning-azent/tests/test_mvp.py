"""Synthetic-only parity acceptance for the extracted Lightning Azent runner."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from lightning_azent.engine import ApprovalRequired, Engine, PlanError, validate
from lightning_azent.runlog import inspect_run
from lightning_azent.scheduler import interval_ticks

FIXTURE_ROOT = REPO_ROOT / "docs" / "lightning-azent" / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


class IndependentEngineMvpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.engine = Engine(self.root / "runtime.sqlite",
                             self.root / "business.sqlite", input_root=self.root)

    def test_csv_import_requires_approval_and_replay_is_idempotent(self):
        source = self.root / "orders.csv"
        source.write_bytes(b"id,amount,label\n1,99,low\n2,100,edge\n3,150,high\n")
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        plan = fixture("csv-filter-import.json")
        self.assertIs(validate(plan), plan)
        with self.assertRaises(ApprovalRequired):
            self.engine.execute(plan, "Blocked")
        with sqlite3.connect(self.root / "business.sqlite") as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 0)
        first = self.engine.execute(plan, "Approved", approve_writes=True)
        again = self.engine.execute(plan, "Approved", approve_writes=True)
        self.assertEqual(first, again)
        with sqlite3.connect(self.root / "business.sqlite") as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 2)
        self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())
        status = inspect_run(self.root / "runtime.sqlite", "Approved")
        self.assertEqual(status["status"], "completed")
        self.assertNotIn("high", str(status))

    def test_guarded_branch_readonly(self):
        result = self.engine.execute(fixture("conditional-route.json"), "BranchTrue")
        self.assertEqual(result, {"route": "accepted"})
        with sqlite3.connect(self.root / "business.sqlite") as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM records").fetchone()[0], 0)

    def test_interval_two_ticks_are_durable(self):
        plan = fixture("interval-replay.json")
        t = [0]
        def clock():
            t[0] += 1
            return float(t[0])
        ticks = list(interval_ticks(plan, self.engine, "SyntheticSchedule",
                                    max_runs=2, approve_writes=True, clock=clock,
                                    sleeper=lambda _: None))
        self.assertEqual([item["tick"] for item in ticks], [0, 1])
        self.assertNotEqual(ticks[0]["run_id"], ticks[1]["run_id"])
        with sqlite3.connect(self.root / "business.sqlite") as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM records").fetchone()[0], 2)

    def test_bad_schema_and_unsupported_network_fail_closed(self):
        for op in ("shell", "http_request", "gmail_send"):
            plan = {"version": "axflow.ir.v0",
                    "steps": [{"id": "remote", "op": op, "value": "invalid"}]}
            with self.assertRaises(PlanError):
                validate(plan)

    def test_cli_validate_and_no_approval_fail_closed(self):
        plan_path = self.root / "plan.json"
        plan_path.write_text(json.dumps(fixture("interval-replay.json")), encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = str(PACKAGE_ROOT)
        command = [sys.executable, "-m", "lightning_azent", "validate", str(plan_path)]
        validated = subprocess.run(command, capture_output=True, text=True,
                                   timeout=12, env=env, cwd=self.root)
        self.assertEqual(validated.returncode, 0, validated.stderr)
        self.assertEqual(json.loads(validated.stdout)["valid"], True)
        no_permission = subprocess.run([
            sys.executable, "-m", "lightning_azent", "run", str(plan_path),
            "--state", str(self.root / "cli-state.sqlite"),
            "--data", str(self.root / "cli-business.sqlite"),
            "--run-id", "NoApproval",
        ], capture_output=True, text=True, timeout=12, env=env, cwd=self.root)
        self.assertEqual(no_permission.returncode, 2)
        self.assertFalse((self.root / "cli-business.sqlite").exists())


    def test_cli_invalid_run_id_rejected_before_database_creation(self):
        plan_path = self.root / "conditional.json"
        plan_path.write_text(json.dumps(fixture("conditional-route.json")), encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = str(PACKAGE_ROOT)
        state = self.root / "invalid-run-state.sqlite"
        data = self.root / "invalid-run-business.sqlite"
        outcome = subprocess.run([
            sys.executable, "-m", "lightning_azent", "run", str(plan_path),
            "--state", str(state), "--data", str(data),
            "--run-id", "invalid-hyphen", "--synthetic", "--approve-writes",
        ], capture_output=True, text=True, timeout=12, env=env, cwd=self.root)
        self.assertEqual(outcome.returncode, 2, outcome.stderr)
        self.assertFalse(state.exists(), "invalid run must not initialize runtime SQLite")
        self.assertFalse(data.exists(), "invalid run must not initialize business SQLite")

    def test_cli_invalid_schedule_preflight_keeps_database_absent(self):
        plan_path = self.root / "interval.json"
        plan_path.write_text(json.dumps(fixture("interval-replay.json")), encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = str(PACKAGE_ROOT)
        for label, extra in (
            ("schedule-id", ["--schedule-id", "invalid-hyphen", "--max-runs", "1"]),
            ("max-runs", ["--schedule-id", "SafeSchedule", "--max-runs", "1001"]),
        ):
            with self.subTest(label=label):
                state = self.root / f"{label}-state.sqlite"
                data = self.root / f"{label}-business.sqlite"
                outcome = subprocess.run([
                    sys.executable, "-m", "lightning_azent", "schedule", str(plan_path),
                    "--state", str(state), "--data", str(data), "--synthetic",
                    "--approve-writes", *extra,
                ], capture_output=True, text=True, timeout=12, env=env, cwd=self.root)
                self.assertEqual(outcome.returncode, 2, outcome.stderr)
                self.assertFalse(state.exists(), f"{label}: runtime DB unexpectedly created")
                self.assertFalse(data.exists(), f"{label}: business DB unexpectedly created")


if __name__ == "__main__":
    unittest.main()
