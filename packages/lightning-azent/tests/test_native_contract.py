"""Native azent.ir.v0, legacy parity, and side-effect-free request validation."""
from __future__ import annotations

from copy import deepcopy
import json
import os
import sqlite3
from sqlite_test_utils import sqlite_connection
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parents[1]
sys.path.insert(0, str(PKG_ROOT))
from lightning_azent import LAExecutor, NATIVE_VERSION, LEGACY_VERSION
from lightning_azent.contract import capabilities, prepare_plan
from lightning_azent.engine import ApprovalRequired, PlanError

FIXTURES = REPO_ROOT / "docs" / "lightning-azent" / "fixtures"


def read_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class NativeInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.state = self.root / "runtime.sqlite"
        self.business = self.root / "business.sqlite"
        self.executor = LAExecutor(self.state, self.business, self.root)

    def test_native_and_legacy_branch_parity_without_input_mutation(self):
        original = read_fixture("conditional-route.json")
        native = deepcopy(original)
        native["version"] = NATIVE_VERSION
        before = deepcopy(native)
        prepared = prepare_plan(native)
        self.assertEqual(prepared.source_version, NATIVE_VERSION)
        self.assertEqual(prepared.runtime_plan["version"], LEGACY_VERSION)
        self.assertEqual(native, before)
        self.assertEqual(self.executor.execute(native, "Native"), {"route": "accepted"})
        self.assertEqual(self.executor.execute(original, "Legacy"), {"route": "accepted"})
        with sqlite_connection(self.business) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM records").fetchone()[0], 0)
        self.assertEqual(native, before)

    def test_unknown_schema_and_legacy_disabled_before_db(self):
        plan = read_fixture("conditional-route.json")
        invalid = {**plan, "version": "azent.ir.v99"}
        for proposal in (invalid, {**plan, "version": "n8n.ir.v1"}):
            with self.assertRaises(PlanError):
                self.executor.execute(proposal, "Rejected")
        with self.assertRaises(PlanError):
            prepare_plan(plan, allow_legacy=False)
        with self.assertRaises(PlanError):
            prepare_plan({**plan, "unexpected": True})
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())

    def test_missing_approval_is_side_effect_free_for_native_writes(self):
        plan = read_fixture("csv-filter-import.json")
        plan["version"] = NATIVE_VERSION
        with self.assertRaises(ApprovalRequired):
            self.executor.execute(plan, "Denied")
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())

    def test_native_csv_import_and_idempotent_replay(self):
        (self.root / "orders.csv").write_bytes(
            b"id,amount,label\n1,99,low\n2,100,edge\n3,150,high\n")
        plan = read_fixture("csv-filter-import.json")
        plan["version"] = NATIVE_VERSION
        one = self.executor.execute(plan, "CsvNative", approve_writes=True)
        two = self.executor.execute(plan, "CsvNative", approve_writes=True)
        self.assertEqual(one, two)
        with sqlite_connection(self.business) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 2)
        status = self.executor.status("CsvNative")
        self.assertEqual(status["status"], "completed")
        self.assertNotIn("high", str(status))

    def test_native_interval_schedule_two_runs_and_recovery(self):
        plan = read_fixture("interval-replay.json")
        plan["version"] = NATIVE_VERSION
        now = [0]
        def clock():
            now[0] += 1
            return float(now[0])
        seen = list(self.executor.schedule(
            plan, "NativeSchedule", max_runs=2, approve_writes=True,
            clock=clock, sleeper=lambda _: None))
        self.assertEqual([tick["tick"] for tick in seen], [0, 1])
        self.assertNotEqual(seen[0]["run_id"], seen[1]["run_id"])
        with sqlite_connection(self.business) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM records").fetchone()[0], 2)
        # A fresh LAExecutor resumes the persisted schedule at the next tick.
        reopened = LAExecutor(self.state, self.business, self.root)
        third = list(reopened.schedule(
            plan, "NativeSchedule", max_runs=1, approve_writes=True,
            clock=clock, sleeper=lambda _: None))
        self.assertEqual(third[0]["tick"], 2)
        self.assertEqual(self.executor.status(third[0]["run_id"])["status"], "completed")
        with sqlite_connection(self.business) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM records").fetchone()[0], 3)

    def test_cli_native_workflow_executes_with_local_synthetic_opt_in(self):
        native = FIXTURES / "native-conditional-route.json"
        env = dict(os.environ, PYTHONPATH=str(PKG_ROOT))
        run = subprocess.run([
            sys.executable, "-m", "lightning_azent", "run", str(native),
            "--state", str(self.state), "--data", str(self.business),
            "--run-id", "NativeCli", "--synthetic",
        ], cwd=self.root, env=env, capture_output=True, text=True, timeout=12)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout), {"route": "accepted"})
        self.assertEqual(self.executor.status("NativeCli")["status"], "completed")

    def test_status_uses_read_only_state_and_does_not_create_db(self):
        with self.assertRaises(Exception):
            self.executor.status("MissingRun")
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())

    def test_capabilities_truthfully_omit_external_actions(self):
        info = capabilities()
        self.assertEqual(info["native_ir_version"], NATIVE_VERSION)
        self.assertEqual(info["legacy_ir_version"], LEGACY_VERSION)
        self.assertEqual(info["api_version"], "azent.api.v0")
        self.assertEqual(info["runtime_schema_version"], 2)
        self.assertEqual(info["audit_feed"], "metadata-only.v0")
        self.assertTrue(info["write_approval_receipts"])
        self.assertEqual(info["external_connectors"], [])
        self.assertNotIn("shell", info["implemented_operations"])
        self.assertNotIn("http_request", info["implemented_operations"])

    def test_cli_native_version_and_capabilities_subcommands(self):
        native = FIXTURES / "native-conditional-route.json"
        env = dict(os.environ, PYTHONPATH=str(PKG_ROOT))
        validation = subprocess.run(
            [sys.executable, "-m", "lightning_azent", "validate", str(native)],
            cwd=self.root, env=env, capture_output=True, text=True, timeout=12)
        self.assertEqual(validation.returncode, 0, validation.stderr)
        response = json.loads(validation.stdout)
        self.assertEqual(response["version"], NATIVE_VERSION)
        self.assertEqual(response["runtime_compat_version"], LEGACY_VERSION)
        cap = subprocess.run(
            [sys.executable, "-m", "lightning_azent", "capabilities"],
            cwd=self.root, env=env, capture_output=True, text=True, timeout=12)
        self.assertEqual(cap.returncode, 0, cap.stderr)
        self.assertEqual(json.loads(cap.stdout)["native_ir_version"], NATIVE_VERSION)
        self.assertEqual(json.loads(cap.stdout)["runtime_schema_version"], 2)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())


if __name__ == "__main__":
    unittest.main()
