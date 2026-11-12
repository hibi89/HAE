"""P43: actual LA SQLite audit events bound to privacy-minimized SOVIA steps."""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))
sys.path.insert(0, str(REPO_ROOT / "apps" / "ax-flow"))

from axflow.la_adapter import HAEConsumer
from axflow.planner import plan_request
from lightning_azent import LAExecutor
from lightning_azent.engine import PlanError
from lightning_azent.hae_bridge import HAEBridge
from sovia_semantic_projection_private import project_completed_synthetic_steps

TASK = "Import this CSV file into local SQLite"


class SemanticLAProjectionP43Tests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(prefix="la-semantic-p43-")
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.source = self.root / "secret-file-reference.csv"
        self.source.write_bytes(b"id,hidden\n1,private_one\n2,private_two\n")
        self.run = "SecretSyntheticRunID"
        self.state, self.business = self.root / "state.sqlite", self.root / "business.sqlite"
        self.bridge = HAEBridge(LAExecutor(self.state, self.business, self.root))
        self.plan = plan_request(TASK, self.source.name)
        self.owner = HAEConsumer(self.bridge)

    def execute(self):
        pre = self.owner.preview(TASK, self.source.name, self.run)
        self.owner.execute(
            TASK, self.source.name, self.run,
            synthetic=True, owner_confirmed=True,
            confirmed_request_sha256=pre["request_sha256"])

    def project(self):
        return project_completed_synthetic_steps(
            self.bridge, self.plan, self.run, synthetic_acknowledged=True)

    def test_actual_sqlite_audit_steps_are_sanitized_and_ordered(self):
        self.execute()
        doc = self.project()
        self.assertEqual(2, len(doc["plan"]["steps"]))
        self.assertEqual(2, len(doc["observations"]["events"]))
        self.assertEqual(["step001", "step002"],
                         [x["event_id"] for x in doc["observations"]["events"]])
        self.assertEqual(["csv_read", "sqlite_import_csv"],
                         [x["tool_code"] for x in doc["plan"]["steps"]])
        self.assertEqual(["csv_read"], doc["policy"]["policy"]["allowed_tools"])
        self.assertTrue(doc["plan"]["steps"][1]["permission_asserted"])
        out = json.dumps(doc)
        for prohibited in ("SecretSyntheticRunID", self.source.name,
                           "private_one", "private_two", "id,hidden",
                           "request_sha256", "scope_json", "raw_input"):
            self.assertNotIn(prohibited, out)

    def test_ack_prevents_any_runtime_files(self):
        with self.assertRaisesRegex(PlanError, "approval required"):
            project_completed_synthetic_steps(self.bridge, self.plan, self.run)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())

    def test_missing_completed_audit_step_denies_projection(self):
        self.execute()
        with closing(sqlite3.connect(self.state)) as db:
            db.execute("DELETE FROM audit_events WHERE run_id=? AND event_type=? "
                       "AND details_json LIKE ?", (self.run, "step_completed", '%"step_id":"input"%'))
            db.commit()
        with self.assertRaisesRegex(PlanError, "audit does not cover"):
            self.project()

    def test_extra_duplicate_step_event_denied(self):
        self.execute()
        with closing(sqlite3.connect(self.state)) as db:
            row = db.execute(
                "SELECT run_id,plan_hash,event_type,occurred_at,details_json "
                "FROM audit_events WHERE event_type='step_completed' LIMIT 1").fetchone()
            db.execute(
                "INSERT INTO audit_events(run_id,plan_hash,event_type,occurred_at,details_json) "
                "VALUES (?,?,?,?,?)", row)
            db.commit()
        with self.assertRaisesRegex(PlanError, "duplicate completed"):
            self.project()

    def test_missing_business_receipt_blocks_projection(self):
        self.execute()
        with closing(sqlite3.connect(self.business)) as db:
            db.execute("DELETE FROM csv_records WHERE row_number=2")
            db.commit()
        with self.assertRaises(PlanError):
            self.project()


if __name__ == "__main__":
    unittest.main()
