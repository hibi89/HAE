"""Synthetic HAE -> genuine LA -> SQLite -> DBVORA *protocol fixture* acceptance.

The DBVORA HTTP responder here is a contract fixture, NOT the real DBVORA
process. It derives metadata from the actual SQLite written by HAE/LA and never
claims real provider authorization, customer-data handling or release readiness.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen

from axflow.schema_inventory import inspect_offline_schema
from axflow.asset_attestation import attest_synthetic_dbvora_asset
from axflow.business_recovery_chain import verify_synthetic_restore_chain
from axflow.business_state_backup import backup_business_state, restore_business_state_pinned
from axflow.dbvora_client import DbvoraClient
from axflow.web import create_server


REPO = Path(__file__).resolve().parents[3]
LA_PACKAGE = REPO / "packages" / "lightning-azent"


class _ProtocolFixture(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self):
        self.requests = []
        self.inventory = None
        self.healthy = True
        super().__init__(("127.0.0.1", 0), _ProtocolHandler)


class _ProtocolHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        self.server.requests.append((self.command, self.path))
        if self.path == "/health":
            body = {"ok": self.server.healthy, "mode": "local-read-only"}
            status = 200
        elif self.path == "/api/inventory" and self.server.inventory is not None:
            body = self.server.inventory
            status = 200
        else:
            body, status = {"error": "unavailable"}, 503
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def _contract_from_real_synthetic_sqlite(path: Path) -> dict:
    """Translate verified *synthetic* catalog metadata into the existing p0 contract."""
    local = inspect_offline_schema(path, synthetic=True, reveal_names=True)
    tables = []
    relations = []
    for table in local["tables"]:
        keys = []
        for key_id, fk in enumerate(table["foreign_keys"]):
            keys.append({
                "id": key_id,
                "to_table": fk["target_table"],
                "from_columns": [fk["from"]],
                "to_columns": [fk["to"]],
                "on_update": "NO ACTION",
                "on_delete": "NO ACTION",
            })
            relations.append({
                "from_table": table["table"], "from_columns": [fk["from"]],
                "to_table": fk["target_table"], "to_columns": [fk["to"]],
                "evidence": "declared_foreign_key",
            })
        tables.append({
            "name": table["table"],
            "columns": [{
                "name": col["name"], "type": col["type"],
                "nullable_declared": not col["not_null_declared"],
                "pk_position": col["pk_position"], "hidden": 0,
            } for col in table["columns"]],
            "foreign_keys": keys,
        })
    return {
        "contract_version": "p0-01.v1", "engine": "sqlite",
        "db_id": hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:24],
        "size_bytes": local["source_size_bytes"],
        "size_scope": "main_database_file_only_excludes_wal_and_shm",
        "observed_at": "2026-11-11T00:00:00Z",
        "provenance": {
            "size_bytes": "measured_local_filesystem",
            "tables": "measured_sqlite_catalog",
            "relationships": "declared_sqlite_foreign_keys",
            "cpu_usage": "unavailable",
        },
        "tables": tables, "relationships": relations,
    }


@unittest.skipUnless(LA_PACKAGE.is_dir(), "real Lightning Azent source must be staged")
class HaeLaDbvoraAssetE2ETests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hae-asset-e2e-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "input"
        self.inputs.mkdir()
        (self.inputs / "synthetic.csv").write_bytes(
            b"id,name\n7,SyntheticPrivateEvidenceRow\n8,SyntheticSecondRow\n"
        )
        self.state = self.root / "state.db"
        self.business = self.root / "business.db"
        self.provider = _ProtocolFixture()
        self.provider_thread = threading.Thread(
            target=self.provider.serve_forever, daemon=True,
        )
        self.provider_thread.start()
        self.addCleanup(self._shutdown, self.provider, self.provider_thread)
        provider_url = "http://127.0.0.1:" + str(self.provider.server_port)
        self.hae = create_server(
            self.inputs, self.state, self.business, port=0,
            engine_backend="lightning-azent", dbvora_url=provider_url,
            dbvora_asset_source=self.business, synthetic_asset_allowed=True,
        )
        self.hae_thread = threading.Thread(target=self.hae.serve_forever, daemon=True)
        self.hae_thread.start()
        self.addCleanup(self._shutdown, self.hae, self.hae_thread)
        self.origin = "http://127.0.0.1:" + str(self.hae.server_port)

    @staticmethod
    def _shutdown(server, thread):
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    def get(self, route):
        with urlopen(self.origin + route, timeout=7) as response:
            self.assertEqual(response.status, 200)
            return json.loads(response.read().decode("utf-8"))

    def post(self, route, payload):
        req = Request(self.origin + route,
                      data=json.dumps(payload).encode("utf-8"),
                      headers={"Origin": self.origin, "Content-Type": "application/json"},
                      method="POST")
        with urlopen(req, timeout=7) as response:
            self.assertEqual(response.status, 200)
            return json.loads(response.read().decode("utf-8"))

    def _execute_approved_synthetic_workflow(self):
        task = "Import this CSV into local SQLite"
        preview = self.post("/api/preview", {
            "task": task, "csv_path": "synthetic.csv",
        })
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())
        self.assertEqual(preview["engine_backend"]["name"], "Lightning Azent")
        outcome = self.post("/api/run", {
            "task": task, "csv_path": "synthetic.csv",
            "preview_id": preview["preview_id"],
            "pending_run_id": preview["pending_run_id"],
            "approve_writes": True,
        })
        self.assertEqual(outcome["status"]["status"], "completed")
        self.assertEqual(outcome["result"]["imported_rows"], 2)
        self.assertEqual(outcome["run_id"], preview["pending_run_id"])
        with closing(sqlite3.connect(self.business)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 2)
        return outcome["run_id"]

    def test_genuine_la_sqlite_is_visible_through_hae_dbvora_contract(self):
        run_id = self._execute_approved_synthetic_workflow()
        # Execution itself may probe DBVORA while its fixture is unavailable;
        # assert only the independent inventory/disconnect requests below.
        self.provider.requests.clear()
        before = hashlib.sha256(self.business.read_bytes()).hexdigest()
        self.provider.inventory = _contract_from_real_synthetic_sqlite(self.business)
        inventory = self.get("/api/dbvora")
        self.assertTrue(inventory["available"], inventory)
        self.assertEqual(inventory["contract_version"], "p0-01.v1")
        self.assertEqual(inventory["engine"], "sqlite")
        self.assertIn("csv_records", [table["name"] for table in inventory["tables"]])
        self.assertEqual(inventory["size_bytes"], self.business.stat().st_size)
        self.assertEqual(self.provider.requests, [
            ("GET", "/health"), ("GET", "/api/inventory"),
        ])
        provider_url = "http://127.0.0.1:" + str(self.provider.server_port)
        proof = attest_synthetic_dbvora_asset(
            self.business, DbvoraClient(provider_url), synthetic=True,
        )
        self.assertTrue(proof["provider_protocol_verified"])
        self.assertFalse(proof["customer_ready"])
        self.assertEqual(proof["source_sha256"], before)
        linked_asset = self.get("/api/dbvora-asset")
        self.assertTrue(linked_asset["available"], linked_asset)
        self.assertEqual(linked_asset["source_sha256"], before)
        serialized = json.dumps(inventory)
        self.assertNotIn("SyntheticPrivateEvidenceRow", serialized)
        self.assertNotIn(str(self.root), serialized)
        self.assertNotIn("payload_json", json.dumps(inventory.get("provenance")))
        self.assertEqual(hashlib.sha256(self.business.read_bytes()).hexdigest(), before)
        persisted = self.get("/api/status?run_id=" + run_id)
        self.assertEqual(persisted["status"], "completed")
        audit = self.get("/api/la-audit?run_id=" + run_id)
        self.assertEqual(audit["run_id"], run_id)
        self.assertGreaterEqual(audit["total_events"], 1)

    def test_la_sqlite_snapshot_restore_and_logical_proof_is_independent(self):
        """Real LA execution then synthetic fresh-path SQLite backup/restore."""
        run_id = self._execute_approved_synthetic_workflow()
        self.provider.inventory = _contract_from_real_synthetic_sqlite(self.business)
        source_sha = hashlib.sha256(self.business.read_bytes()).hexdigest()
        owner_asset = self.get("/api/dbvora-asset")
        self.assertTrue(owner_asset["available"], owner_asset)
        self.assertEqual(owner_asset["source_sha256"], source_sha)

        backup = self.root / "safe-fresh-backup.sqlite"
        restored = self.root / "safe-fresh-restored.sqlite"
        snapshot = backup_business_state(self.business, backup)
        self.assertEqual(snapshot["source_sha256"], source_sha)
        recovered = restore_business_state_pinned(
            backup, restored, snapshot["artifact_sha256"],
        )
        self.assertEqual(recovered["source_sha256"], snapshot["artifact_sha256"])
        proof = verify_synthetic_restore_chain(
            self.business, backup, restored,
            expected_source_sha256=source_sha,
            expected_backup_sha256=snapshot["artifact_sha256"],
            synthetic=True,
        )
        self.assertTrue(proof["independent_restore_verified"])
        self.assertEqual(proof["source_sha256"], source_sha)
        self.assertEqual(proof["table_count"], 1)
        with closing(sqlite3.connect(restored)) as db:
            rows = db.execute(
                "SELECT name FROM csv_records ORDER BY row_idx"
            ).fetchall()
        self.assertEqual(rows, [
            ("SyntheticPrivateEvidenceRow",),
            ("SyntheticSecondRow",),
        ])
        serialized = json.dumps(proof)
        self.assertNotIn("SyntheticPrivateEvidenceRow", serialized)
        self.assertNotIn(str(self.root), serialized)
        self.assertEqual(hashlib.sha256(self.business.read_bytes()).hexdigest(), source_sha)
        self.assertEqual(self.get("/api/status?run_id=" + run_id)["status"], "completed")

    def test_provider_disconnect_does_not_erase_la_sqlite_or_retry_writes(self):
        run_id = self._execute_approved_synthetic_workflow()
        # Execution itself may probe DBVORA while its fixture is unavailable;
        # assert only the independent inventory/disconnect requests below.
        self.provider.requests.clear()
        before = hashlib.sha256(self.business.read_bytes()).hexdigest()
        self.provider.healthy = False
        unavailable = self.get("/api/dbvora")
        self.assertFalse(unavailable["available"])
        self.assertEqual(unavailable["error_code"], "INVALID_HEALTH")
        failed_attestation = self.get("/api/dbvora-asset")
        self.assertEqual(failed_attestation["error_code"], "ASSET_ATTESTATION_HOLD")
        self.assertEqual(self.provider.requests, [("GET", "/health"), ("GET", "/health")])
        self.assertEqual(self.get("/api/status?run_id=" + run_id)["status"], "completed")
        self.assertEqual(hashlib.sha256(self.business.read_bytes()).hexdigest(), before)
        with closing(sqlite3.connect(self.business)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()
