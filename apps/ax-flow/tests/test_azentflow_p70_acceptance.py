"""AZENTFLOW AX P70 acceptance: independent LA, two local workflows, recovery.

All tests use disposable synthetic CSV and SQLite. The genuine LA package must
be staged by CI; missing it is a failure rather than a skipped integration.
No cloud credentials, customer data, or outbound provider calls are involved.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
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

ORDERS_TASK = "Import this CSV into local SQLite"
SALES_TASK = "이 CSV에서 amount가 100 이상일 때만 로컬 SQLite에 저장해줘"
ORDERS = b"id,name\n11,SyntheticCustomerA\n12,SyntheticCustomerB\n"
SALES = b"amount,id\n120,OrderA\n80,OrderB\n100,OrderC\n"


class AzentflowP70Acceptance(unittest.TestCase):
    """Acceptance separate from legacy MVP score and product release gate."""

    def setUp(self):
        self.assertTrue(
            (LA_ROOT / "lightning_azent" / "__init__.py").is_file(),
            "real LA checkout required; do not skip standalone integration",
        )
        self.temp = tempfile.TemporaryDirectory(prefix="azentflow-p70-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "input"
        self.inputs.mkdir()
        (self.inputs / "orders.csv").write_bytes(ORDERS)
        (self.inputs / "sales.csv").write_bytes(SALES)
        self.state = self.root / "run-ledger.sqlite"
        self.business = self.root / "business.sqlite"
        self.server = None
        self.thread = None
        self.addCleanup(self.stop_server)
        self.start_server()

    def start_server(self):
        self.assertIsNone(self.server)
        self.server = create_server(
            self.inputs, self.state, self.business, port=0,
            engine_backend="lightning-azent",
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": 0.01},
            daemon=True,
        )
        self.thread.start()
        self.origin = "http://127.0.0.1:" + str(self.server.server_port)

    def stop_server(self):
        if self.server is not None:
            self.server.shutdown()
            self.thread.join(timeout=5)
            self.server.server_close()
            self.server = None
            self.thread = None

    def post(self, route, data):
        request = Request(
            self.origin + route, data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json", "Origin": self.origin},
            method="POST",
        )
        try:
            with urlopen(request, timeout=20) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def get_json(self, route):
        with urlopen(self.origin + route, timeout=20) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def preview(self, task=ORDERS_TASK, filename="orders.csv", resume_run_id=None):
        body = {"task": task, "csv_path": filename}
        if resume_run_id is not None:
            body["resume_run_id"] = resume_run_id
        status, data = self.post("/api/preview", body)
        self.assertEqual(status, 200, data)
        return data

    def execute(self, preview, task=ORDERS_TASK, filename="orders.csv", approve=True):
        return self.post("/api/run", {
            "task": task, "csv_path": filename,
            "preview_id": preview["preview_id"],
            "pending_run_id": preview["pending_run_id"],
            "approve_writes": approve,
        })

    def count_rows(self, run_id=None):
        if not self.business.is_file():
            return 0
        with closing(sqlite3.connect(self.business)) as db:
            if run_id is None:
                return db.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0]
            return db.execute(
                "SELECT COUNT(*) FROM csv_records WHERE run_id=?", (run_id,)
            ).fetchone()[0]

    def test_p70_two_distinct_customer_workflows_with_local_ui_preview(self):
        # Verify shipped local UI route and preview controls, not a browser E2E.
        with urlopen(self.origin + "/", timeout=20) as response:
            html = response.read()
            self.assertEqual(response.status, 200)
            self.assertIn(b'id="preview"', html)
            self.assertIn(b'id="run"', html)
            self.assertIn(b'Content-Security-Policy', str(response.headers).encode())
        with urlopen(self.origin + "/app.js", timeout=20) as response:
            self.assertIn(b"/api/preview", response.read())

        # Workflow A: all customer contact rows imported after explicit review.
        p1 = self.preview()
        self.assertEqual(p1["workflow"], "csv_to_sqlite")
        self.assertTrue(p1["requires_approval"])
        self.assertEqual(p1["input"]["row_count"], 2)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())
        code, a = self.execute(p1)
        self.assertEqual(code, 200, a)
        self.assertEqual(a["status"]["status"], "completed")
        self.assertEqual(a["result"]["imported_rows"], 2)

        # Workflow B: Korean conditional sales threshold; excludes unapproved
        # lower amount rows, runs a different multi-step LA branch IR.
        p2 = self.preview(SALES_TASK, "sales.csv")
        self.assertEqual(p2["workflow"], "csv_conditional_import")
        self.assertTrue(p2["requires_approval"])
        self.assertNotEqual(canonical_json(p1["plan"]), canonical_json(p2["plan"]))
        self.assertEqual(p2["plan"]["version"], p1["plan"]["version"])
        code, b = self.execute(p2, SALES_TASK, "sales.csv")
        self.assertEqual(code, 200, b)
        self.assertEqual(b["status"]["status"], "completed")
        self.assertEqual(b["result"]["imported_rows"], 2)
        self.assertNotEqual(a["run_id"], b["run_id"])
        self.assertEqual(self.count_rows(a["run_id"]), 2)
        self.assertEqual(self.count_rows(b["run_id"]), 2)
        self.assertEqual(self.count_rows(), 4)
        self.assertEqual([s["op"] for s in p2["plan"]["steps"]][-1], "branch")

    def test_p70_unapproved_write_and_changed_plan_hold_before_sqlite(self):
        p = self.preview(SALES_TASK, "sales.csv")
        code, _ = self.execute(p, SALES_TASK, "sales.csv", approve=False)
        self.assertEqual(code, 403)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())
        code, _ = self.execute(p, ORDERS_TASK, "sales.csv", approve=True)
        self.assertEqual(code, 409)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())
        (self.inputs / "sales.csv").write_bytes(
            b"amount,id\n999,SyntheticChanged\n"
        )
        code, _ = self.execute(p, SALES_TASK, "sales.csv", approve=True)
        self.assertEqual(code, 409)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())

    def test_p70_two_concurrent_identical_approvals_do_not_duplicate_business_rows(self):
        preview = self.preview()
        def request(_):
            return self.execute(preview)
        start = time.monotonic()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(request, range(2)))
        elapsed = time.monotonic() - start
        self.assertEqual([status for status, _ in outcomes], [200, 200], outcomes)
        a, b = (body for _, body in outcomes)
        self.assertEqual(a["run_id"], b["run_id"])
        self.assertEqual(a["result"], b["result"])
        self.assertEqual(self.count_rows(a["run_id"]), 2)
        self.assertEqual(self.count_rows(), 2)
        self.assertEqual(a["status"]["status"], "completed")
        self.assertEqual(b["status"]["status"], "completed")
        # Bounded small local synthetic fixture, not a performance/SLA claim.
        self.assertLess(elapsed, 20.0, "local double-write exceeded 20s test budget")

    def test_p70_restarted_service_reads_durable_la_receipts(self):
        preview = self.preview()
        code, result = self.execute(preview)
        self.assertEqual(code, 200, result)
        run_id = result["run_id"]
        old_origin = self.origin
        self.stop_server()
        self.start_server()
        self.assertNotEqual(self.origin, "", old_origin)
        code, status = self.get_json("/api/status?run_id=" + run_id)
        self.assertEqual(code, 200)
        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["integration"]["execution_status"], "completed")
        code, audit = self.get_json("/api/la-audit?run_id=" + run_id)
        self.assertEqual(code, 200)
        self.assertEqual(audit["plan_sha256"], result["status"]["plan_sha256"])
        self.assertGreaterEqual(audit["approval_count"], 1)
        self.assertEqual(self.count_rows(run_id), 2)
        self.assertNotIn("SyntheticCustomerA", json.dumps(audit))

    def test_p70_reapproval_required_on_simulated_failed_run_recovery(self):
        first_preview = self.preview()
        code, first = self.execute(first_preview)
        self.assertEqual(code, 200, first)
        run_id = first["run_id"]
        # Fault-injection of incomplete state; not a real process crash.
        with closing(sqlite3.connect(self.state)) as state:
            with state:
                state.execute("UPDATE runs SET status='failed' WHERE run_id=?", (run_id,))
        self.stop_server()
        self.start_server()
        code, _ = self.post("/api/preview", {
            "task": "Find rows in this CSV where id equals 11", "csv_path": "orders.csv", "resume_run_id": run_id,
        })
        self.assertEqual(code, 409, "changed recovery plan must be rejected")
        second_preview = self.preview(resume_run_id=run_id)
        self.assertEqual(second_preview["resumes_run_id"], run_id)
        code, _ = self.execute(second_preview, approve=False)
        self.assertEqual(code, 403)
        self.assertEqual(self.count_rows(run_id), 2)
        code, resumed = self.execute(second_preview, approve=True)
        self.assertEqual(code, 200, resumed)
        self.assertEqual(resumed["run_id"], run_id)
        self.assertEqual(resumed["status"]["status"], "completed")
        self.assertEqual(self.count_rows(run_id), 2)

    def test_p70_real_independent_la_cli_on_hae_generated_ir(self):
        plan = plan_request(ORDERS_TASK, "orders.csv")
        plan_path = self.root / "plan.json"
        plan_path.write_text(canonical_json(plan), encoding="utf-8")
        native_state = self.root / "native-state.sqlite"
        native_data = self.root / "native-business.sqlite"
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([str(LA_ROOT), str(APP_ROOT)])
        common = [
            sys.executable, "-m", "lightning_azent",
            "run", str(plan_path), "--state", str(native_state),
            "--data", str(native_data), "--input-root", str(self.inputs),
            "--run-id", "AzentP70", "--synthetic",
        ]
        denied = subprocess.run(
            common, env=env, cwd=str(self.root),
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(denied.returncode, 2, denied.stderr)
        self.assertFalse(native_state.exists())
        self.assertFalse(native_data.exists())
        first = subprocess.run(
            common + ["--approve-writes"], env=env, cwd=str(self.root),
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)["imported_rows"], 2)
        self.assertNotEqual(native_state.resolve(), native_data.resolve())
        with closing(sqlite3.connect(native_data)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 2)
        inspect = subprocess.run(
            [sys.executable, "-m", "lightning_azent", "status",
             "--state", str(native_state), "--run-id", "AzentP70"],
            env=env, cwd=str(self.root), capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(inspect.returncode, 0, inspect.stderr)
        self.assertEqual(json.loads(inspect.stdout)["status"], "completed")
        again = subprocess.run(
            [sys.executable, "-m", "lightning_azent",
             "resume", str(plan_path), "--state", str(native_state),
             "--data", str(native_data), "--input-root", str(self.inputs),
             "--run-id", "AzentP70", "--synthetic", "--approve-writes"],
            env=env, cwd=str(self.root), capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(again.returncode, 0, again.stderr)
        with closing(sqlite3.connect(native_data)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 2)

    def test_p70_input_size_limit_fails_closed_before_any_sqlite(self):
        oversize = self.inputs / "too-big.csv"
        oversize.write_bytes(b"id,name\n" + b"1,X\n" * 70000)
        start = time.monotonic()
        code, _ = self.post("/api/preview", {
            "task": ORDERS_TASK, "csv_path": "too-big.csv",
        })
        elapsed = time.monotonic() - start
        self.assertIn(code, {400, 413, 415, 422})
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())
        self.assertLess(elapsed, 20.0, "oversized local CSV refused too slowly")


if __name__ == "__main__":
    unittest.main()
