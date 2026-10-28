"""Real local HAE → LA → SOVIA → DBVORA integration using synthetic rows only.

Set HAE_INTEGRATION_ROOT to a checkout containing packages/lightning-azent,
SOVIA, and DBVORA to enable this optional cross-repository acceptance test.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from contextlib import closing
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_ROOT = Path(os.environ.get("HAE_INTEGRATION_ROOT", Path(__file__).resolve().parents[3]))
_LA = _ROOT / "packages" / "lightning-azent"
_SOVIA = _ROOT / "SOVIA"
_DBVORA = _ROOT / "DBVORA"
_READY = (_LA.is_dir() and _SOVIA.is_dir() and _DBVORA.is_dir())
if _READY:
    for _path in (_LA, _DBVORA):
        sys.path.insert(0, str(_path))


@unittest.skipUnless(_READY, "cross-repository LA/SOVIA/DBVORA source checkouts are not configured")
class IntegratedMvpE2ETests(unittest.TestCase):
    def setUp(self):
        import uvicorn
        from dbvora.api import create_app
        from axflow.web import create_server

        self.temp = tempfile.TemporaryDirectory(prefix="hae-p2-e2e-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.csv = self.inputs / "sales.csv"
        self.csv.write_text("amount,id\n99999,low\n100000,edge\n150000,high\n", encoding="utf-8")
        self.bad_csv = self.inputs / "bad.csv"
        self.bad_csv.write_text("amount,id\n100000\n", encoding="utf-8")
        self.numeric_csv = self.inputs / "numeric.csv"
        self.numeric_csv.write_text("amount,id\nnot-a-number,bad\n", encoding="utf-8")
        self.locked_csv = self.inputs / "locked.csv"
        self.locked_csv.write_text("amount,id\n110000,locked\n", encoding="utf-8")
        self.state = self.root / "state.sqlite"
        self.business = self.root / "business.sqlite"
        with closing(sqlite3.connect(self.business)) as connection:
            connection.execute("CREATE TABLE seed_to_materialize_database (value INTEGER)")
            connection.execute("DROP TABLE seed_to_materialize_database")
            connection.commit()

        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            db_port = listener.getsockname()[1]
        self.db_port = db_port
        self.db_server = uvicorn.Server(uvicorn.Config(
            create_app(self.business, port=db_port), host="127.0.0.1", port=db_port,
            log_level="critical", access_log=False,
        ))
        self.db_thread = threading.Thread(target=self.db_server.run, daemon=True)
        self.db_thread.start()
        self.addCleanup(self._stop_dbvora)
        for _ in range(100):
            if self.db_server.started:
                break
            time.sleep(0.02)
        self.assertTrue(self.db_server.started, "DBVORA local API did not start")

        self.server = create_server(
            self.inputs, self.state, self.business, port=0,
            dbvora_url=f"http://127.0.0.1:{self.db_port}",
            engine_backend="lightning-azent", sovia_root=_SOVIA,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop_hae)
        self.origin = f"http://127.0.0.1:{self.server.server_port}"

    def _stop_hae(self):
        self.server.shutdown()
        self.thread.join(timeout=3)
        self.server.server_close()

    def _stop_dbvora(self):
        self.db_server.should_exit = True
        self.db_thread.join(timeout=3)
        if self.db_thread.is_alive():
            self.db_server.force_exit = True
            self.db_thread.join(timeout=2)
        if self.db_thread.is_alive():
            raise RuntimeError("DBVORA local API failed to stop; retaining its open database")

    def request(self, path, payload=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Origin": self.origin} if payload is not None else {}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.origin + path, data=data, headers=headers)
        try:
            with urlopen(request, timeout=12) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_real_preview_approval_import_audit_inventory_and_replay(self):
        task = "매출 CSV에서 amount 100000 이상인 행만 추출해서 SQLite에 저장해줘"
        before = hashlib.sha256(self.business.read_bytes()).hexdigest()
        code, invalid = self.request("/api/preview", {"task": task, "csv_path": "bad.csv"})
        self.assertEqual(code, 422, invalid)
        code, invalid_number = self.request("/api/preview", {"task": task, "csv_path": "numeric.csv"})
        self.assertEqual(code, 422, invalid_number)
        self.assertEqual(hashlib.sha256(self.business.read_bytes()).hexdigest(), before)

        code, preview = self.request("/api/preview", {"task": task, "csv_path": "sales.csv"})
        self.assertEqual(code, 200, preview)
        self.assertEqual(preview["input"]["row_count"], 3)
        self.assertEqual(preview["engine_backend"]["name"], "Lightning Azent")
        code, denied = self.request("/api/run", {
            "task": task, "csv_path": "sales.csv", "preview_id": preview["preview_id"],
            "approve_writes": False,
        })
        self.assertEqual(code, 403, denied)
        self.assertEqual(hashlib.sha256(self.business.read_bytes()).hexdigest(), before)

        approved_bytes = self.csv.read_bytes()
        self.csv.write_text("amount,id\n99999,low\n100000,changed\n150000,high\n", encoding="utf-8")
        code, changed = self.request("/api/run", {
            "task": task, "csv_path": "sales.csv", "preview_id": preview["preview_id"],
            "approve_writes": True,
        })
        self.assertEqual(code, 409, changed)
        self.assertEqual(hashlib.sha256(self.business.read_bytes()).hexdigest(), before)
        self.csv.write_bytes(approved_bytes)
        code, preview = self.request("/api/preview", {"task": task, "csv_path": "sales.csv"})
        self.assertEqual(code, 200, preview)
        code, run = self.request("/api/run", {
            "task": task, "csv_path": "sales.csv", "preview_id": preview["preview_id"],
            "approve_writes": True,
        })
        self.assertEqual(code, 200, run)
        run_id = run["run_id"]
        self.assertEqual(run["status"]["status"], "completed")
        self.assertEqual(run["result"]["imported_rows"], 2)
        audit = run["sovia_audit"]
        self.assertEqual(run["workflow_status"], "completed")
        self.assertTrue(run["dbvora"]["available"])
        self.assertTrue(audit["available"], audit)
        self.assertTrue(run["audit_persisted"])
        self.assertEqual(audit["mode"], "post_execution_advisory")
        self.assertTrue(audit["approval"]["la_receipt_matched"])
        self.assertFalse(audit["execution"]["evidence_authenticated"])
        self.assertFalse(audit["review"]["execution_authorized"])

        with closing(sqlite3.connect(self.business)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 2)
        with closing(sqlite3.connect(self.state)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM approval_receipts").fetchone()[0], 1)
        self.server._sovia_reports.clear()
        code, fetched_after_cache_clear = self.request("/api/audit?" + urlencode({"run_id": run_id}))
        self.assertEqual(code, 200, fetched_after_cache_clear)
        self.assertEqual(fetched_after_cache_clear["run_id"], run_id)

        code, inventory = self.request("/api/dbvora")
        self.assertEqual(code, 200, inventory)
        self.assertTrue(inventory["available"], inventory)
        self.assertGreater(inventory["size_bytes"], 0)
        self.assertIn("csv_records", {table["name"] for table in inventory["tables"]})
        code, fetched_audit = self.request("/api/audit?" + urlencode({"run_id": run_id}))
        self.assertEqual(code, 200, fetched_audit)
        self.assertEqual(fetched_audit["plan_sha256"], run["status"]["plan_sha256"])
        code, fetched_status = self.request("/api/status?" + urlencode({"run_id": run_id}))
        self.assertEqual(code, 200, fetched_status)
        self.assertEqual(fetched_status["integration"]["workflow_status"], "completed")

        code, replay = self.request("/api/run", {
            "task": task, "csv_path": "sales.csv", "preview_id": preview["preview_id"],
            "approve_writes": True,
        })
        self.assertEqual(code, 200, replay)
        self.assertEqual(replay["run_id"], run_id)
        with closing(sqlite3.connect(self.business)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 2)
        with closing(sqlite3.connect(self.state)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM approval_receipts").fetchone()[0], 1)

        # Missing, incompatible and unreachable optional components must be
        # visible as partial integration, never reported as success.
        from axflow.dbvora_client import DbvoraClient
        plan_sha = run["status"]["plan_sha256"]
        self.server.sovia_root = None
        missing_sovia = self.server.run_integrations(preview["plan"], run_id, plan_sha, run, True)
        self.assertFalse(missing_sovia["sovia_audit"]["available"])
        self.assertEqual(missing_sovia["workflow_status"], "partial")
        unsupported = self.root / "unsupported-sovia"
        unsupported.mkdir()
        self.server.sovia_root = unsupported
        mismatch = self.server.run_integrations(preview["plan"], run_id, plan_sha, run, True)
        self.assertFalse(mismatch["sovia_audit"]["available"])
        self.assertEqual(mismatch["workflow_status"], "partial")
        self.server.sovia_root = _SOVIA
        configured_dbvora = self.server.dbvora_client
        self.server.dbvora_client = DbvoraClient("http://127.0.0.1:1", timeout_seconds=0.2)
        unavailable_dbvora = self.server.run_integrations(preview["plan"], run_id, plan_sha, run, True)
        self.assertFalse(unavailable_dbvora["dbvora"]["available"])
        self.assertEqual(unavailable_dbvora["workflow_status"], "partial")
        self.server.dbvora_client = configured_dbvora

        # A real LA SQLite write refusal must still deliver its failed-step
        # audit to SOVIA, then a same-run resume must disclose recovery.
        lock_task = "Import this CSV where amount >= 100000 into SQLite"
        code, lock_preview = self.request("/api/preview", {
            "task": lock_task, "csv_path": "locked.csv",
        })
        self.assertEqual(code, 200, lock_preview)
        with closing(sqlite3.connect(self.business)) as connection:
            connection.execute(
                "CREATE TRIGGER refuse_synthetic_import BEFORE INSERT ON csv_records "
                "BEGIN SELECT RAISE(ABORT, 'synthetic write refusal'); END"
            )
            connection.commit()
        try:
            code, failure = self.request("/api/run", {
                "task": lock_task, "csv_path": "locked.csv",
                "preview_id": lock_preview["preview_id"], "approve_writes": True,
            })
        finally:
            with closing(sqlite3.connect(self.business)) as connection:
                connection.execute("DROP TRIGGER refuse_synthetic_import")
                connection.commit()
        self.assertEqual(code, 422, failure)
        self.assertNotIn("synthetic write refusal", failure["error"])
        self.assertNotIn(str(self.root), json.dumps(failure))
        failed_integration = failure["integration"]
        self.assertEqual(failure["status"]["status"], "failed")
        self.assertTrue(failed_integration["sovia_audit"]["available"])
        self.assertIn("imported", failed_integration["sovia_audit"]["execution"]["failed_attempt_steps"])

        code, recovered = self.request("/api/run", {
            "task": lock_task, "csv_path": "locked.csv",
            "preview_id": lock_preview["preview_id"], "approve_writes": True,
        })
        self.assertEqual(code, 200, recovered)
        self.assertEqual(recovered["status"]["status"], "completed")
        self.assertIn("imported", recovered["sovia_audit"]["execution"]["failed_attempt_steps"])
        self.assertEqual(recovered["sovia_audit"]["execution"]["retry_count"], 1)

        # A server restart keeps durable status and audit queryable, but the
        # old in-memory preview/approval token cannot authorize a new request.
        approved_business_hash = hashlib.sha256(self.business.read_bytes()).hexdigest()
        old_server, old_thread = self.server, self.thread
        old_server.shutdown()
        old_thread.join(timeout=3)
        old_server.server_close()
        from axflow.web import create_server
        self.server = create_server(
            self.inputs, self.state, self.business, port=0,
            dbvora_url=f"http://127.0.0.1:{self.db_port}",
            engine_backend="lightning-azent", sovia_root=_SOVIA,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f"http://127.0.0.1:{self.server.server_port}"
        code, restarted_status = self.request("/api/status?" + urlencode({"run_id": recovered["run_id"]}))
        self.assertEqual(code, 200, restarted_status)
        self.assertEqual(restarted_status["status"], "completed")
        code, restarted_audit = self.request("/api/audit?" + urlencode({"run_id": recovered["run_id"]}))
        self.assertEqual(code, 200, restarted_audit)
        self.assertEqual(restarted_audit["run_id"], recovered["run_id"])
        code, stale_approval = self.request("/api/run", {
            "task": lock_task, "csv_path": "locked.csv",
            "preview_id": lock_preview["preview_id"], "approve_writes": True,
        })
        self.assertEqual(code, 409, stale_approval)
        self.assertEqual(hashlib.sha256(self.business.read_bytes()).hexdigest(), approved_business_hash)


if __name__ == "__main__":
    unittest.main()
