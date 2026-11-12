"""P41 actual first-party LA SQLite -> minimal *synthetic* public contract."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
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
from lightning_azent.sovia_projection import export_local_synthetic_projection

TASK = "Import this CSV file into local SQLite"
FINGERPRINT = "a" * 64


class RealLASyntheticProjectionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="la-sovia-p41-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.input = self.root / "public-synthetic.csv"
        self.input.write_bytes(b"id,amount\n1,12\n2,18\n")
        self.runtime = self.root / "state.sqlite"
        self.business = self.root / "business.sqlite"
        self.bridge = HAEBridge(LAExecutor(self.runtime, self.business, self.root))
        self.consumer = HAEConsumer(self.bridge)
        self.run_id = "SyntheticSoviaP41"
        self.plan = plan_request(TASK, self.input.name)
        self.input_hash = hashlib.sha256(self.input.read_bytes()).hexdigest()

    def _get_projection(self, *, acknowledged=True):
        return export_local_synthetic_projection(
            self.bridge, self.plan, self.run_id,
            sovia_plan_fingerprint_sha256=FINGERPRINT,
            synthetic_acknowledged=acknowledged)

    def _execute(self):
        preview = self.consumer.preview(TASK, self.input.name, self.run_id)
        self.assertFalse(preview["approved"])
        self.assertTrue(preview["requires_write_approval"])
        self.consumer.execute(
            TASK, self.input.name, self.run_id, synthetic=True,
            owner_confirmed=True,
            confirmed_request_sha256=preview["request_sha256"])

    def test_ack_required_before_any_sqlite_open(self):
        with self.assertRaisesRegex(PlanError, "acknowledgement"):
            self._get_projection(acknowledged=False)
        self.assertFalse(self.runtime.exists())
        self.assertFalse(self.business.exists())

    def test_source_must_exist_as_actual_completed_sqlite_run(self):
        with self.assertRaises(PlanError):
            self._get_projection()
        self.assertFalse(self.runtime.exists())
        self.assertFalse(self.business.exists())

    def test_actual_sqlite_receipts_emit_only_abstract_sovia_contract(self):
        self._execute()
        doc = self._get_projection()
        self.assertEqual(
            {"schema_version", "source_kind", "synthetic_only",
             "source_authenticated", "approval_authenticated",
             "stream_completeness_verified", "plan_fingerprint_sha256",
             "run_status", "steps", "audit"}, set(doc))
        self.assertEqual(FINGERPRINT, doc["plan_fingerprint_sha256"])
        self.assertEqual(2, doc["steps"]["declared"])
        self.assertEqual(2, doc["steps"]["recorded"])
        self.assertEqual(2, doc["steps"]["completed"])
        self.assertEqual(0, doc["steps"]["failed"])
        self.assertGreater(doc["audit"]["event_count"], 0)
        self.assertGreaterEqual(doc["audit"]["write_approval_claims"], 1)
        self.assertIs(doc["source_authenticated"], False)
        self.assertIs(doc["approval_authenticated"], False)
        self.assertIs(doc["stream_completeness_verified"], False)
        raw = json.dumps(doc)
        for secret in ("SyntheticSoviaP41", self.input.name, "amount",
                       "sqlite_import_csv", "request_sha256", "run_id",
                       "client_records", self.input_hash):
            self.assertNotIn(secret, raw)
        self.assertEqual(self.input_hash,
                         hashlib.sha256(self.input.read_bytes()).hexdigest())

    def test_missing_real_business_row_blocks_projection(self):
        self._execute()
        from sqlite_test_utils import sqlite_connection
        with sqlite_connection(self.business) as db:
            db.execute("DELETE FROM csv_records WHERE row_number=2")
        with self.assertRaises(PlanError):
            self._get_projection()

    def test_missing_completed_audit_blocks_projection(self):
        self._execute()
        from sqlite_test_utils import sqlite_connection
        with sqlite_connection(self.runtime) as db:
            db.execute("DELETE FROM audit_events WHERE run_id=? AND event_type=?",
                       (self.run_id, "run_completed"))
        with self.assertRaises(PlanError):
            self._get_projection()

    def test_changed_plan_same_run_denied(self):
        self._execute()
        modified = plan_request(TASK, "different.csv")
        with self.assertRaises(PlanError):
            export_local_synthetic_projection(
                self.bridge, modified, self.run_id,
                sovia_plan_fingerprint_sha256=FINGERPRINT,
                synthetic_acknowledged=True)

    def test_wrong_sovia_digest_or_fake_authority_denied(self):
        self._execute()
        for bad in ("", "A" * 64, "not-a-hash", False, 42):
            with self.subTest(bad=bad):
                with self.assertRaises(PlanError):
                    export_local_synthetic_projection(
                        self.bridge, self.plan, self.run_id,
                        sovia_plan_fingerprint_sha256=bad,
                        synthetic_acknowledged=True)
        with self.assertRaises(PlanError):
            export_local_synthetic_projection(
                object(), self.plan, self.run_id,
                sovia_plan_fingerprint_sha256=FINGERPRINT,
                synthetic_acknowledged=True)

    def test_completed_replay_remains_not_authenticated_by_sovia(self):
        self._execute()
        preview = self.consumer.preview(TASK, self.input.name, self.run_id)
        self.consumer.execute(TASK, self.input.name, self.run_id, synthetic=True,
                              owner_confirmed=True,
                              confirmed_request_sha256=preview["request_sha256"],
                              resume=True)
        doc = self._get_projection()
        self.assertEqual("completed", doc["run_status"])
        self.assertFalse(doc["source_authenticated"])

    def test_readonly_projection_leaves_existing_receipts_untouched(self):
        self._execute()
        before = (self.runtime.stat().st_size, self.business.stat().st_size,
                  hashlib.sha256(self.runtime.read_bytes()).hexdigest(),
                  hashlib.sha256(self.business.read_bytes()).hexdigest())
        self._get_projection()
        after = (self.runtime.stat().st_size, self.business.stat().st_size,
                 hashlib.sha256(self.runtime.read_bytes()).hexdigest(),
                 hashlib.sha256(self.business.read_bytes()).hexdigest())
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
