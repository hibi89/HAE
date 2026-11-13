"""AZENTFLOW AX P50 gate: real HAE -> independent LA -> local SQLite.

Synthetic-only acceptance. This suite intentionally REQUIRES the staged LA source:
an absent runtime is a failure, never an integration skip. No customer files,
network provider, or live credentials are used.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import threading
import unittest
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

from axflow.engine import VERSION as IR_VERSION
from axflow.la_adapter import inspect_backend
from axflow.planner import plan_request
from axflow.web import create_server

TASK = "Import this CSV into local SQLite"
CSV = b"id,name\n11,SyntheticAlpha\n12,SyntheticBeta\n"


class AzentflowP50Acceptance(unittest.TestCase):
    """One real offline CSV workflow, independent state/data, and fail-closed gates."""

    def setUp(self):
        self.assertTrue(
            (LA_ROOT / "lightning_azent" / "__init__.py").is_file(),
            "P50 real-integration gate requires exact staged Lightning Azent package",
        )
        self.temp = tempfile.TemporaryDirectory(prefix="azentflow-p50-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input_root = self.root / "input"
        self.input_root.mkdir()
        self.source = self.input_root / "synthetic.csv"
        self.source.write_bytes(CSV)
        self.state = self.root / "runtime.db"
        self.business = self.root / "business.db"
        self.assertNotEqual(self.state.resolve(), self.business.resolve())
        self.server = create_server(
            self.input_root, self.state, self.business,
            port=0, engine_backend="lightning-azent",
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True,
        )
        self.thread.start()
        self.addCleanup(self._close)
        self.origin = "http://127.0.0.1:" + str(self.server.server_port)

    def _close(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()

    def post(self, endpoint, payload):
        req = Request(
            self.origin + endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Origin": self.origin},
            method="POST",
        )
        try:
            with urlopen(req, timeout=20) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def get(self, endpoint):
        with urlopen(self.origin + endpoint, timeout=20) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def preview(self):
        status, preview = self.post(
            "/api/preview", {"task": TASK, "csv_path": "synthetic.csv"},
        )
        self.assertEqual(status, 200, preview)
        return preview

    def run(self, preview, approve):
        return self.post("/api/run", {
            "task": TASK, "csv_path": "synthetic.csv",
            "preview_id": preview["preview_id"], "approve_writes": approve,
        })

    def test_p50_contract_and_explicit_approval_with_split_databases(self):
        plan = plan_request(TASK, "synthetic.csv")
        self.assertEqual(plan["version"], IR_VERSION)
        backend = inspect_backend(plan)
        self.assertEqual(backend["api_version"], "azent.api.v0")
        self.assertEqual(len(backend["capability_fingerprint"]), 64)
        self.assertIsInstance(backend["package_version"], str)
        self.assertTrue(backend["package_version"])

        preview = self.preview()
        self.assertEqual(preview["engine_backend"]["api_version"], "azent.api.v0")
        self.assertEqual(preview["plan"], plan)
        self.assertTrue(preview["requires_approval"])
        self.assertFalse(self.state.exists(), "plan preview created runtime ledger")
        self.assertFalse(self.business.exists(), "plan preview created customer data DB")
        status, _ = self.run(preview, approve=False)
        self.assertEqual(status, 403, "unapproved business write was not rejected")
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())

        status, completed = self.run(preview, approve=True)
        self.assertEqual(status, 200, completed)
        self.assertEqual(completed["status"]["status"], "completed")
        self.assertEqual(completed["backend"]["name"], "Lightning Azent")
        self.assertEqual(completed["result"]["imported_rows"], 2)
        self.assertTrue(self.state.is_file())
        self.assertTrue(self.business.is_file())
        with closing(sqlite3.connect(self.state)) as state:
            state_tables = {r[0] for r in state.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            self.assertTrue({"runs", "steps"}.issubset(state_tables))
            self.assertNotIn("csv_records", state_tables)
            self.assertEqual(state.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        with closing(sqlite3.connect(self.business)) as business:
            business_tables = {r[0] for r in business.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            self.assertIn("csv_records", business_tables)
            self.assertNotIn("runs", business_tables)
            self.assertEqual(business.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 2)
            self.assertEqual(business.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        code, audit = self.get("/api/la-audit?run_id=" + completed["run_id"])
        self.assertEqual(code, 200)
        self.assertGreaterEqual(audit["approval_count"], 1)
        self.assertEqual(audit["plan_sha256"], completed["status"]["plan_sha256"])
        self.assertNotIn("SyntheticAlpha", json.dumps(audit))
        self.assertNotIn("SyntheticBeta", json.dumps(audit))

    def test_p50_replay_does_not_repeat_business_write(self):
        preview = self.preview()
        status, first = self.run(preview, approve=True)
        self.assertEqual(status, 200, first)
        status, second = self.run(preview, approve=True)
        self.assertEqual(status, 200, second)
        self.assertEqual(second["run_id"], first["run_id"])
        self.assertEqual(second["result"], first["result"])
        with closing(sqlite3.connect(self.business)) as business:
            self.assertEqual(
                business.execute(
                    "SELECT COUNT(*) FROM csv_records WHERE run_id=?",
                    (first["run_id"],),
                ).fetchone()[0],
                2,
                "same approved run produced duplicate business rows",
            )

    def test_p50_source_mutation_invalidates_approval_without_write(self):
        preview = self.preview()
        self.source.write_bytes(b"id,name\n99,SyntheticChanged\n")
        status, _ = self.run(preview, approve=True)
        self.assertEqual(status, 409, "stale source digest did not fail closed")
        self.assertFalse(self.state.exists(), "stale input produced a runtime run")
        self.assertFalse(self.business.exists(), "stale input modified business DB")


if __name__ == "__main__":
    unittest.main()
