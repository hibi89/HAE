"""Durable local approval and metadata-only audit feed contract."""
from __future__ import annotations

from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
import subprocess
import tempfile
import unittest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from lightning_azent import LAExecutor
from lightning_azent.engine import Engine, InjectedStop


class RunAuditAcceptanceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.state = self.root / "state.sqlite"
        self.business = self.root / "business.sqlite"
        self.executor = LAExecutor(self.state, self.business)

    def test_write_approval_is_plan_bound_and_audit_omits_payloads(self):
        plan = {"version": "axflow.ir.v0", "steps": [
            {"id": "source", "op": "literal", "value": {"secret": "synthetic-private-sentinel"}},
            {"id": "save", "op": "sqlite_put", "from": "source"},
        ]}
        result = self.executor.execute(plan, "AuditWrite1", approve_writes=True)
        audit = self.executor.audit("AuditWrite1")

        self.assertEqual(result["stored_by"], "save")
        types = [event["event_type"] for event in audit["events"]]
        self.assertEqual(types, ["run_started", "write_approval_granted", "step_completed",
                                 "step_completed", "run_completed"])
        serialized = json.dumps(audit, sort_keys=True)
        self.assertNotIn("synthetic-private-sentinel", serialized)
        approval = next(event for event in audit["events"]
                        if event["event_type"] == "write_approval_granted")
        self.assertEqual(approval["details"]["method"], "explicit-local-flag")
        self.assertEqual(approval["details"]["scope"]["write_steps"],
                         [{"step_id": "save", "operation": "sqlite_put"}])
        self.assertEqual(approval["details"]["scope"]["plan_sha256"], audit["plan_sha256"])
        with closing(sqlite3.connect(self.state)) as con:
            receipt = con.execute(
                "SELECT plan_hash,scope_json,method FROM approval_receipts WHERE run_id=?",
                ("AuditWrite1",),
            ).fetchone()
        self.assertEqual(receipt[0], audit["plan_sha256"])
        self.assertEqual(json.loads(receipt[1])["write_steps"],
                         [{"step_id": "save", "operation": "sqlite_put"}])
        self.assertEqual(receipt[2], "explicit-local-flag")
        self.assertEqual(len(audit["approval_receipts"]), 1)
        self.assertEqual(audit["approval_receipts"][0]["scope"]["write_steps"],
                         [{"step_id": "save", "operation": "sqlite_put"}])

    def test_completed_replay_is_audited_without_repeating_approval_or_steps(self):
        plan = {"version": "axflow.ir.v0", "steps": [
            {"id": "source", "op": "literal", "value": {"value": 1}},
            {"id": "save", "op": "sqlite_put", "from": "source"},
        ]}
        first = self.executor.execute(plan, "AuditReplay1", approve_writes=True)
        second = self.executor.execute(plan, "AuditReplay1", approve_writes=True)
        audit = self.executor.audit("AuditReplay1")

        self.assertEqual(first, second)
        types = [event["event_type"] for event in audit["events"]]
        self.assertEqual(types.count("write_approval_granted"), 1)
        self.assertEqual(types.count("step_completed"), 2)
        self.assertEqual(types[-1], "run_replayed")
        with closing(sqlite3.connect(self.state)) as con:
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM approval_receipts WHERE run_id=?", ("AuditReplay1",)
            ).fetchone()[0], 1)

    def test_failed_write_retains_approval_and_failure_events_for_recovery(self):
        plan = {"version": "axflow.ir.v0", "steps": [
            {"id": "source", "op": "literal", "value": {"value": 1}},
            {"id": "save", "op": "sqlite_put", "from": "source"},
        ]}
        engine = Engine(self.state, self.business)
        with self.assertRaises(InjectedStop):
            engine.execute(plan, "AuditFailure1", approve_writes=True,
                           inject_stop_after_business=True)

        audit = self.executor.audit("AuditFailure1")
        types = [event["event_type"] for event in audit["events"]]
        self.assertIn("write_approval_granted", types)
        self.assertIn("step_failed", types)
        self.assertEqual(types[-1], "run_failed")
        with closing(sqlite3.connect(self.state)) as con:
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM approval_receipts WHERE run_id=?", ("AuditFailure1",)
            ).fetchone()[0], 1)

    def test_read_only_audit_lookup_does_not_initialize_missing_ledgers(self):
        with self.assertRaisesRegex(ValueError, "runtime ledger does not exist"):
            self.executor.audit("MissingAudit1")
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())

    def test_cli_audit_subcommand_returns_saved_events(self):
        plan = {"version": "axflow.ir.v0", "steps": [
            {"id": "source", "op": "literal", "value": {"value": 1}},
        ]}
        self.executor.execute(plan, "AuditCli1")
        env = dict(os.environ, PYTHONPATH=str(PACKAGE_ROOT))
        result = subprocess.run([
            sys.executable, "-m", "lightning_azent", "audit",
            "--state", str(self.state), "--run-id", "AuditCli1",
        ], cwd=self.root, env=env, capture_output=True, text=True, timeout=12)

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["run_id"], "AuditCli1")
        self.assertEqual(payload["approval_receipts"], [])
        self.assertEqual([event["event_type"] for event in payload["events"]],
                         ["run_started", "step_completed", "run_completed"])


if __name__ == "__main__":
    unittest.main()
