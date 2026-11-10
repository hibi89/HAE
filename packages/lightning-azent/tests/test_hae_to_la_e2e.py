"""Real HAE planner -> opt-in LA bridge -> disposable SQLite acceptance.

Requires a full authorized HAE repository checkout. No customer data, OAuth,
network or production service. The original HAE routes are not modified.
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))
sys.path.insert(0, str(REPO_ROOT / "apps" / "ax-flow"))

from axflow.la_adapter import HAEConsumer
from axflow.engine import PlanError as HAEPlanError
from lightning_azent import LAExecutor
from lightning_azent.engine import ApprovalRequired, PlanError
from lightning_azent.hae_bridge import HAEBridge
from sqlite_test_utils import sqlite_connection

TASK = "Import this CSV file into local SQLite"


class HAEToLARealSQLiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "orders.csv"
        self.source.write_bytes(b"id,amount,label\n1,99,low\n2,100,edge\n3,150,high\n")
        self.state = self.root / "runtime.sqlite"
        self.business = self.root / "business.sqlite"
        self.executor = LAExecutor(self.state, self.business, self.root)
        self.consumer = HAEConsumer(HAEBridge(self.executor))

    def assert_no_state(self):
        self.assertFalse(self.state.exists(), "runtime created before consent")
        self.assertFalse(self.business.exists(), "business DB created before consent")

    def review(self, run_id="RunOne", csv_path="orders.csv"):
        return self.consumer.preview(TASK, csv_path, run_id)

    def test_hae_plan_preview_is_redacted_and_creates_no_databases(self):
        preview = self.review()
        self.assertEqual(preview["api_version"], "azent.api.v0")
        self.assertEqual(preview["preview"]["step_count"], 2)
        self.assertTrue(preview["requires_write_approval"])
        self.assertFalse(preview["approved"])
        self.assertFalse(preview["executed"])
        self.assertNotIn("orders.csv", str(preview))
        self.assertNotIn("high", str(preview))
        self.assert_no_state()

    def test_missing_confirmation_does_not_create_databases(self):
        preview = self.review()
        with self.assertRaises(ApprovalRequired):
            self.consumer.execute(TASK, "orders.csv", "RunOne", synthetic=True)
        with self.assertRaises(ApprovalRequired):
            self.consumer.execute(TASK, "orders.csv", "RunOne", synthetic=True,
                                  owner_confirmed=True)
        with self.assertRaises(PlanError):
            self.consumer.execute(TASK, "orders.csv", "RunOne", synthetic=False,
                                  owner_confirmed=True,
                                  confirmed_request_sha256=preview["request_sha256"])
        self.assert_no_state()

    def test_approval_digest_is_bound_to_run_and_input_path(self):
        preview = self.review()
        digest = preview["request_sha256"]
        (self.root / "different.csv").write_bytes(self.source.read_bytes())
        for changed_run, changed_path in (("RunTwo", "orders.csv"),
                                          ("RunOne", "different.csv")):
            with self.subTest(run=changed_run, path=changed_path):
                with self.assertRaises(ApprovalRequired):
                    self.consumer.execute(TASK, changed_path, changed_run,
                                          synthetic=True, owner_confirmed=True,
                                          confirmed_request_sha256=digest)
                self.assert_no_state()

    def test_real_sqlite_import_resume_and_receipt_readback(self):
        original_hash = hashlib.sha256(self.source.read_bytes()).hexdigest()
        digest = self.review()["request_sha256"]
        first = self.consumer.execute(TASK, "orders.csv", "RunOne", synthetic=True,
                                      owner_confirmed=True,
                                      confirmed_request_sha256=digest)
        self.assertTrue(self.state.is_file())
        self.assertTrue(self.business.is_file())
        with sqlite_connection(self.business) as db:
            row_count = db.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0]
        self.assertEqual(row_count, 3)
        self.assertEqual(original_hash, hashlib.sha256(self.source.read_bytes()).hexdigest())
        evidence = self.consumer.evidence(TASK, "orders.csv", "RunOne")
        self.assertTrue(evidence["verified"])
        self.assertFalse(evidence["independent_sovia_audit"])
        self.assertEqual(evidence["status"]["status"], "completed")
        replay = self.consumer.execute(TASK, "orders.csv", "RunOne", synthetic=True,
                                       owner_confirmed=True,
                                       confirmed_request_sha256=digest, resume=True)
        self.assertEqual(first, replay)
        with sqlite_connection(self.business) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 3)

    def test_unsupported_external_task_rejects_before_sqlite(self):
        with self.assertRaises(HAEPlanError):
            self.consumer.preview("Send this CSV over Gmail", "orders.csv", "RunOne")
        self.assert_no_state()


if __name__ == "__main__":
    unittest.main()
