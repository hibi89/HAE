"""AZENTFLOW AX P85 gate: 3 synthetic workflows, DBVORA protocol, LA audit, bounded scheduler.

The test uses the REAL HAE localhost server and the separately staged Lightning
Azent runtime. A deliberately tiny DBVORA-compatible mock is the only provider:
no production DB, customer data, credentials, outbound network, or paid APIs.
Missing LA source is a failure, never a silent integration skip.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]
LA_ROOT = REPO_ROOT / "packages" / "lightning-azent"
sys.path.insert(0, str(APP_ROOT))
if LA_ROOT.is_dir():
    sys.path.insert(0, str(LA_ROOT))

from axflow.engine import canonical_json
from axflow.planner import plan_request
from axflow.web import create_server

IMPORT_TASK = "Import this CSV into local SQLite"
CONDITIONAL_TASK = "이 CSV에서 amount가 100 이상일 때만 로컬 SQLite에 저장해줘"
LOOKUP_TASK = "Find rows in this CSV where id equals 11"
CONTACTS = b"id,name\n11,SyntheticA\n12,SyntheticB\n"
SALES = b"id,amount\n21,120\n22,80\n23,100\n"
INVENTORY = {
    "contract_version": "p0-01.v1",
    "db_id": "0123456789abcdef01234567",
    "engine": "sqlite",
    "size_bytes": 4096,
    "size_scope": "main_database_file_only_excludes_wal_and_shm",
    "observed_at": "2026-11-13T00:00:00Z",
    "provenance": {
        "size_bytes": "measured_local_filesystem",
        "tables": "measured_sqlite_catalog",
        "relationships": "declared_sqlite_foreign_keys",
        "cpu_usage": "unavailable",
    },
    "tables": [
        {"name": "synthetic_orders", "columns": [
            {"name": "id", "type": "INTEGER", "nullable_declared": True,
             "pk_position": 1, "hidden": 0},
        ], "foreign_keys": []},
    ],
    "relationships": [],
}


class _DbvoraMockHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def do_GET(self):
        self.server.requests.append((self.command, self.path))
        if self.path == "/health":
            content = {"ok": self.server.healthy, "mode": "local-read-only"}
        elif self.path == "/api/inventory":
            content = self.server.inventory
        else:
            self.send_error(404)
            return
        body = json.dumps(content, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _MockServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self):
        self.requests = []
        self.healthy = True
        self.inventory = INVENTORY
        super().__init__(("127.0.0.1", 0), _DbvoraMockHandler)


class AzentflowP85Acceptance(unittest.TestCase):
    def setUp(self):
        self.assertTrue(
            (LA_ROOT / "lightning_azent" / "__init__.py").is_file(),
            "P85 requires separate real LA source, not a mock or skip",
        )
        self.tmp = tempfile.TemporaryDirectory(prefix="azentflow-p85-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        (self.inputs / "contacts.csv").write_bytes(CONTACTS)
        (self.inputs / "sales.csv").write_bytes(SALES)
        self.state = self.root / "runtime.sqlite"
        self.data = self.root / "business.sqlite"
        self.mock = _MockServer()
        self.mock_thread = threading.Thread(
            target=self.mock.serve_forever,
            kwargs={"poll_interval": 0.01}, daemon=True,
        )
        self.mock_thread.start()
        self.mock_url = f"http://127.0.0.1:{self.mock.server_port}"
        self.addCleanup(self.stop_mock)
        self.server = create_server(
            self.inputs, self.state, self.data,
            port=0, engine_backend="lightning-azent",
            dbvora_url=self.mock_url,
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": 0.01}, daemon=True,
        )
        self.thread.start()
        self.addCleanup(self.stop_hae)
        self.origin = f"http://127.0.0.1:{self.server.server_port}"

    def stop_mock(self):
        if self.mock is not None:
            self.mock.shutdown()
            self.mock_thread.join(timeout=5)
            self.mock.server_close()
            self.mock = None

    def stop_hae(self):
        if self.server is not None:
            self.server.shutdown()
            self.thread.join(timeout=5)
            self.server.server_close()
            self.server = None

    def get(self, endpoint):
        try:
            with urlopen(self.origin + endpoint, timeout=20) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def post(self, endpoint, payload):
        req = Request(
            self.origin + endpoint, method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Origin": self.origin},
        )
        try:
            with urlopen(req, timeout=20) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def preview(self, task, path):
        code, plan = self.post("/api/preview", {"task": task, "csv_path": path})
        self.assertEqual(code, 200, plan)
        return plan

    def execute(self, plan, task, path, *, approve):
        return self.post("/api/run", {
            "task": task, "csv_path": path,
            "preview_id": plan["preview_id"],
            "pending_run_id": plan["pending_run_id"],
            "approve_writes": approve,
        })

    def rows_by_run(self, run_id):
        if not self.data.is_file():
            return []
        with closing(sqlite3.connect(self.data)) as c:
            return c.execute(
                "SELECT row_number,payload_json FROM csv_records WHERE run_id=? ORDER BY row_number",
                (run_id,),
            ).fetchall()

    def test_p85_three_different_synthetic_workflows_end_to_end(self):
        # Explicitly distinct business use cases: contacts import, thresholded
        # sales import, and read-only contact search. The last is not a write.
        plan_a = self.preview(IMPORT_TASK, "contacts.csv")
        plan_b = self.preview(CONDITIONAL_TASK, "sales.csv")
        plan_c = self.preview(LOOKUP_TASK, "contacts.csv")
        self.assertEqual(
            {plan_a["workflow"], plan_b["workflow"], plan_c["workflow"]},
            {"csv_to_sqlite", "csv_conditional_import", "csv_lookup"},
        )
        self.assertNotEqual(canonical_json(plan_a["plan"]), canonical_json(plan_b["plan"]))
        self.assertFalse(plan_c["requires_approval"])
        self.assertFalse(self.state.exists(), "read-only previews must not create runtime DB")
        self.assertFalse(self.data.exists(), "read-only previews must not create business DB")

        code, denied = self.execute(plan_b, CONDITIONAL_TASK, "sales.csv", approve=False)
        self.assertEqual(code, 403, denied)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.data.exists())

        code, a = self.execute(plan_a, IMPORT_TASK, "contacts.csv", approve=True)
        self.assertEqual(code, 200, a)
        self.assertEqual(a["result"]["imported_rows"], 2)
        code, b = self.execute(plan_b, CONDITIONAL_TASK, "sales.csv", approve=True)
        self.assertEqual(code, 200, b)
        self.assertEqual(b["result"]["imported_rows"], 2)
        code, c = self.execute(plan_c, LOOKUP_TASK, "contacts.csv", approve=False)
        self.assertEqual(code, 200, c)
        self.assertEqual(c["result"]["matched_count"], 1)
        self.assertEqual(len(self.rows_by_run(a["run_id"])), 2)
        self.assertEqual(len(self.rows_by_run(b["run_id"])), 2)
        self.assertEqual(len(self.rows_by_run(c["run_id"])), 0)
        with closing(sqlite3.connect(self.data)) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 4)
            self.assertEqual(con.execute("PRAGMA quick_check(1)").fetchone()[0], "ok")
        self.assertNotEqual(a["run_id"], b["run_id"])
        self.assertNotEqual(b["run_id"], c["run_id"])
        self.assertTrue(all(
            result["status"]["status"] == "completed" for result in (a, b, c)
        ))

    def test_p85_real_http_dbvora_mock_contract_read_only_and_redacted(self):
        code, report = self.get("/api/dbvora")
        self.assertEqual(code, 200, report)
        self.assertTrue(report["available"], report)
        self.assertEqual(report["contract_version"], "p0-01.v1")
        self.assertEqual(report["engine"], "sqlite")
        self.assertEqual(report["tables"][0]["name"], "synthetic_orders")
        self.assertEqual(self.mock.requests, [
            ("GET", "/health"), ("GET", "/api/inventory"),
        ])
        self.assertNotIn("contacts.csv", json.dumps(report))
        self.assertNotIn("SyntheticA", json.dumps(report))
        self.assertFalse(self.state.exists())
        self.assertFalse(self.data.exists())
        self.assertTrue(all(method == "GET" for method, _ in self.mock.requests))

    def test_p85_dbvora_contract_mismatch_and_disconnection_do_not_mask_la_receipt(self):
        p = self.preview(IMPORT_TASK, "contacts.csv")
        self.mock.inventory = {**INVENTORY, "contract_version": "p0-99.v999"}
        code, unavailable = self.get("/api/dbvora")
        self.assertEqual(code, 200, unavailable)
        self.assertFalse(unavailable["available"])
        self.assertEqual(unavailable["error_code"], "UNSUPPORTED_CONTRACT")
        code, finished = self.execute(p, IMPORT_TASK, "contacts.csv", approve=True)
        self.assertEqual(code, 200, finished)
        self.assertEqual(finished["status"]["status"], "completed")
        self.assertFalse(finished["dbvora"]["available"])
        self.assertEqual(finished["workflow_status"], "partial")
        self.assertEqual(len(self.rows_by_run(finished["run_id"])), 2)
        self.stop_mock()
        code, lost = self.get("/api/dbvora")
        self.assertEqual(code, 200, lost)
        self.assertFalse(lost["available"])
        self.assertEqual(lost["error_code"], "UNAVAILABLE")
        code, durable = self.get("/api/status?run_id=" + finished["run_id"])
        self.assertEqual(code, 200, durable)
        self.assertEqual(durable["status"], "completed")
        self.assertEqual(len(self.rows_by_run(finished["run_id"])), 2)

    def test_p85_durable_la_audit_approval_receipts_and_read_only_verifier(self):
        p = self.preview(IMPORT_TASK, "contacts.csv")
        code, response = self.execute(p, IMPORT_TASK, "contacts.csv", approve=True)
        self.assertEqual(code, 200, response)
        run_id = response["run_id"]
        code, audit = self.get("/api/la-audit?run_id=" + run_id)
        self.assertEqual(code, 200, audit)
        self.assertEqual(audit["plan_sha256"], response["status"]["plan_sha256"])
        self.assertEqual(audit["run_id"], run_id)
        self.assertGreaterEqual(audit["approval_count"], 1)
        self.assertGreaterEqual(audit["total_events"], 1)
        self.assertFalse(audit["truncated"])
        self.assertNotIn("SyntheticA", json.dumps(audit))
        self.assertNotIn("contacts.csv", json.dumps(audit))
        self.assertEqual(response["integration"]["workflow_status"], "completed")
        self.assertTrue(response["integration"]["audit_persisted"])
        self.assertTrue(response["integration"]["dbvora"]["available"])
        self.assertEqual(len(self.rows_by_run(run_id)), 2)

        from lightning_azent import LAExecutor
        executor = LAExecutor(self.state, self.data, self.inputs)
        receipt = executor.verify_receipts(plan_request(IMPORT_TASK, "contacts.csv"), run_id)
        self.assertTrue(receipt["verified"])
        self.assertEqual(receipt["run_id"], run_id)
        self.assertEqual(len(self.rows_by_run(run_id)), 2)
        code, same = self.execute(p, IMPORT_TASK, "contacts.csv", approve=True)
        self.assertEqual(code, 200, same)
        self.assertEqual(same["run_id"], run_id)
        self.assertEqual(len(self.rows_by_run(run_id)), 2)

    def test_p85_interval_schedule_denies_unapproved_or_out_of_bounds_without_databases(self):
        from lightning_azent import LAExecutor
        plan = plan_request(IMPORT_TASK, "contacts.csv")
        plan["trigger"] = {"type": "interval", "every_seconds": 1}
        executor = LAExecutor(self.state, self.data, self.inputs)
        with self.assertRaises(Exception):
            # LA's schedule() may return an iterator; force its consumption.
            list(executor.schedule(plan, "AzentP85", max_runs=1, approve_writes=False))
        self.assertFalse(self.state.exists())
        self.assertFalse(self.data.exists())
        with self.assertRaises(Exception):
            list(executor.schedule(plan, "AzentP85", max_runs=1001, approve_writes=True))
        self.assertFalse(self.state.exists())
        self.assertFalse(self.data.exists())
        # A different trigger/plan must not be auto-executed by HAE's preview.
        code, error = self.post("/api/preview", {
            "task": "Schedule this CSV to SQLite", "csv_path": "contacts.csv",
        })
        self.assertEqual(code, 422, error)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.data.exists())

    def test_p85_real_la_cli_two_bounded_ticks_and_durable_tick_restart(self):
        plan = plan_request(IMPORT_TASK, "contacts.csv")
        plan["trigger"] = {"type": "interval", "every_seconds": 1}
        plan_path = self.root / "schedule.json"
        plan_path.write_text(canonical_json(plan), encoding="utf-8")
        schedule_state = self.root / "scheduled-run.sqlite"
        schedule_data = self.root / "scheduled-business.sqlite"
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join((str(LA_ROOT), str(APP_ROOT)))
        args = [
            sys.executable, "-m", "lightning_azent", "schedule", str(plan_path),
            "--state", str(schedule_state), "--data", str(schedule_data),
            "--input-root", str(self.inputs),
            "--schedule-id", "AzentScheduleP85", "--synthetic",
        ]
        denied = subprocess.run(
            args + ["--max-runs", "2"],
            cwd=self.root, env=env, capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(denied.returncode, 2, denied.stderr)
        self.assertFalse(schedule_state.exists())
        self.assertFalse(schedule_data.exists())
        start = time.monotonic()
        first = subprocess.run(
            args + ["--max-runs", "2", "--approve-writes"],
            cwd=self.root, env=env, capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        ticks = json.loads(first.stdout)
        self.assertEqual([item["tick"] for item in ticks], [0, 1])
        self.assertEqual(len(set(item["run_id"] for item in ticks)), 2)
        self.assertTrue(all(item["advanced"] for item in ticks))
        self.assertLess(time.monotonic() - start, 20)
        with closing(sqlite3.connect(schedule_data)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 4)
        with closing(sqlite3.connect(schedule_state)) as db:
            progress = db.execute(
                "SELECT next_tick FROM interval_schedules WHERE schedule_id=?",
                ("AzentScheduleP85",),
            ).fetchone()[0]
            self.assertEqual(progress, 2)

        # New scheduler process uses existing ledger instead of reusing ticks.
        resumed = subprocess.run(
            args + ["--max-runs", "1", "--approve-writes"],
            cwd=self.root, env=env, capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(json.loads(resumed.stdout)[0]["tick"], 2)
        with closing(sqlite3.connect(schedule_data)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 6)
        with closing(sqlite3.connect(schedule_state)) as db:
            ticks = db.execute(
                "SELECT next_tick FROM interval_schedules WHERE schedule_id=?",
                ("AzentScheduleP85",),
            ).fetchone()[0]
            self.assertEqual(ticks, 3)

    def test_p85_risky_external_task_refused_and_dbvora_mock_no_write_endpoints(self):
        for text in ("Send this CSV to Gmail", "Delete remote database and upload CSV"):
            with self.subTest(task=text):
                code, _ = self.post("/api/preview", {"task": text, "csv_path": "contacts.csv"})
                self.assertEqual(code, 422)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.data.exists())
        self.assertEqual(self.mock.requests, [])


if __name__ == "__main__":
    unittest.main()
