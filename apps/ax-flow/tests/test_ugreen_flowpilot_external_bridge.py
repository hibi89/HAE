"""Real G81 FlowPilot -> HAE -> LA synthetic SQLite E2E in private HAE CI.

Requires a separately pinned checkout of the PUBLIC UGREEN branch supplied in
UGREEN_BRIDGE_ROOT. No private code is copied to the public repo. Tests use the
real private HAE HTTP server and real LA package, temporary SQLite and CSV only.
No NAS, API keys, customer data, license changes or public submission.
"""
from __future__ import annotations

from contextlib import closing
import importlib
import os
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
import threading
import unittest

REPO = Path(__file__).resolve().parents[3]
LA = REPO / "packages" / "lightning-azent"
EXTERNAL = Path(os.environ.get("UGREEN_BRIDGE_ROOT", "/nonexistent-ugreen-bridge"))
ENABLED = (
    (EXTERNAL / "flowpilot_hae_bridge.py").is_file()
    and (LA / "lightning_azent" / "__init__.py").is_file()
)
if ENABLED:
    sys.path.insert(0, str(EXTERNAL))
    sys.path.insert(0, str(LA))
    sys.path.insert(0, str(REPO / "apps" / "ax-flow"))
    from flowpilot_hae_bridge import APPROVAL, run_bridge, _request
    from axflow.web import create_server

TASK = "Import this CSV into local SQLite"
CSV = "contacts.csv"
FIXTURE = b"id,name\n11,SyntheticAlice\n12,SyntheticBob\n"


@unittest.skipUnless(ENABLED, "Pinned public FlowPilot bridge and native private LA not installed")
class ExternalUGREENHAEBridgeAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="hae-ugreen-real-e2e-")
        self.addCleanup(self.temp.cleanup)
        home = Path(self.temp.name)
        self.root = home / "input"
        self.root.mkdir()
        (self.root / CSV).write_bytes(FIXTURE)
        self.state = home / "runtime.sqlite"
        self.business = home / "business.sqlite"
        self.server = create_server(
            self.root, self.state, self.business, port=0,
            engine_backend="lightning-azent",
        )
        self.worker = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        self.worker.start()
        self.addCleanup(self.stop)
        self.port = self.server.server_port
        self.assertGreaterEqual(self.port, 1024)

    def stop(self):
        self.server.shutdown()
        self.worker.join(timeout=5)
        self.server.server_close()

    def invoke(self, **opts):
        args = dict(csv_path=CSV, port=self.port, confirm_synthetic=True)
        args.update(opts)
        return run_bridge(TASK, **args)

    def db_count(self):
        if not self.business.exists():
            return 0
        with closing(sqlite3.connect(self.business)) as db:
            return db.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0]

    def test_live_hae_la_preview_approval_write_readback_and_audit(self):
        first = self.invoke()
        self.assertEqual(first["status"], "WAITING_HAE_WRITE_APPROVAL")
        self.assertFalse(first["executed"])
        self.assertFalse(self.state.exists(), "Preview created runtime DB")
        self.assertFalse(self.business.exists(), "Preview created business DB")

        declined = self.invoke(approval="DECLINED", preview_id=first["preview_id"])
        self.assertEqual(declined["status"], "DECLINED")
        self.assertFalse(self.business.exists(), "Decline wrote database")

        outcome = self.invoke(approval=APPROVAL, preview_id=first["preview_id"])
        self.assertEqual(outcome["status"], "HAE_LA_SQLITE_AUDIT_CONFIRMED")
        self.assertEqual(outcome["imported_rows"], 2)
        self.assertTrue(outcome["hae_http_audit_verified"])
        self.assertFalse(outcome["actual_la_execution_verified"])
        # Independent SQLite read immediately below, not a protocol-stub claim.
        self.assertFalse(outcome["real_nas_verified"])
        self.assertGreaterEqual(outcome["audit_events"], 2)
        self.assertEqual(self.db_count(), 2)
        run_id = outcome["run_id"]
        code, ledger = _request(self.port, "GET", "/api/status?run_id="+run_id)
        self.assertEqual(code, 200)
        self.assertEqual(ledger["status"], "completed")
        code, audit = _request(self.port, "GET", "/api/la-audit?run_id="+run_id)
        self.assertEqual(code, 200)
        self.assertEqual(audit["run_id"], run_id)
        self.assertGreaterEqual(audit["approval_count"], 1)
        print("G81 REAL HAE->LA->SQLite->AUDIT CONTRACT PASS", flush=True)

    def test_source_changed_after_preview_prevents_sqlite_write(self):
        preview = self.invoke()
        self.assertEqual(preview["status"], "WAITING_HAE_WRITE_APPROVAL")
        (self.root / CSV).write_bytes(b"id,name\n11,MutatedAlice\n12,MutatedBob\n")
        run = self.invoke(approval=APPROVAL, preview_id=preview["preview_id"])
        self.assertEqual(run["status"], "BLOCKED_HAE_EXECUTION_REJECTED")
        self.assertFalse(self.business.exists())
        renewed = self.invoke()
        self.assertEqual(renewed["status"], "WAITING_HAE_WRITE_APPROVAL")
        committed = self.invoke(approval=APPROVAL, preview_id=renewed["preview_id"])
        self.assertEqual(committed["status"], "HAE_LA_SQLITE_AUDIT_CONFIRMED")
        self.assertEqual(self.db_count(), 2)
        print("G81 REAL APPROVAL SOURCE BINDING PASS", flush=True)

    def test_unsupported_task_fails_without_writes(self):
        result = run_bridge("Delete all CSV files", csv_path=CSV, port=self.port,
                            confirm_synthetic=True)
        self.assertEqual(result["status"], "BLOCKED_HAE_PREVIEW_REJECTED")
        self.assertFalse(self.business.exists())
        print("G81 REAL HAE UNSUPPORTED INTENT DENIAL PASS", flush=True)


if __name__ == "__main__":
    unittest.main()
