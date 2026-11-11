"""Three operator-friendly *local synthetic* CSV scenarios against real LA.

These are three supported local workflow variants, not Gmail/Sheets OAuth or
three commercial customer pilots. The DB and input root are disposable.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from axflow.web import create_server

REPO = Path(__file__).resolve().parents[3]
LA_PACKAGE = REPO / "packages" / "lightning-azent"


@unittest.skipUnless(LA_PACKAGE.is_dir(), "Real Lightning Azent package must be staged")
class ThreeLocalCustomerStyleFlows(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hae-three-flows-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.csv_path = self.inputs / "offers.csv"
        self.csv_path.write_text(
            "id,name,amount\n1,  Alpha  ,50\n2,  Beta  ,250\n3,  Gamma  ,300\n",
            encoding="utf-8",
        )
        self.csv_bytes = self.csv_path.read_bytes()
        self.state = self.root / "runtime.sqlite"
        self.business = self.root / "business.sqlite"
        self.hae = None
        self.hae_thread = None
        self._start()

    def _start(self):
        self.hae = create_server(
            self.inputs, self.state, self.business,
            port=0, engine_backend="lightning-azent",
        )
        self.hae_thread = threading.Thread(target=self.hae.serve_forever, daemon=True)
        self.hae_thread.start()
        self.addCleanup(self._stop, self.hae, self.hae_thread)
        self.origin = "http://127.0.0.1:" + str(self.hae.server_port)

    @staticmethod
    def _stop(server, thread):
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    def _call(self, path, body=None):
        headers = {}
        raw = None
        if body is not None:
            raw = json.dumps(body).encode("utf-8")
            headers = {"Origin": self.origin, "Content-Type": "application/json"}
        request = Request(self.origin + path, method="POST" if raw is not None else "GET",
                          headers=headers, data=raw)
        try:
            with urlopen(request, timeout=8) as response:
                return response.status, json.loads(response.read())
        except HTTPError as exc:
            with exc:
                return exc.code, json.loads(exc.read())

    def _preview(self, task):
        code, preview = self._call("/api/preview", {
            "task": task, "csv_path": "offers.csv",
        })
        self.assertEqual(code, 200, preview)
        self.assertEqual(preview["engine_backend"]["name"], "Lightning Azent")
        self.assertTrue(preview["validated"])
        self.assertTrue(preview["requires_approval"])
        return preview

    def _run(self, task, preview, approved):
        return self._call("/api/run", {
            "task": task, "csv_path": "offers.csv",
            "preview_id": preview["preview_id"],
            "pending_run_id": preview["pending_run_id"],
            "approve_writes": approved,
        })

    def _scenario(self, task, expected_count, *, expected_names=None):
        preview = self._preview(task)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())
        code, refusal = self._run(task, preview, False)
        self.assertEqual(code, 403, refusal)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())
        code, outcome = self._run(task, preview, True)
        self.assertEqual(code, 200, outcome)
        self.assertEqual(outcome["status"]["status"], "completed")
        self.assertEqual(outcome["result"]["imported_rows"], expected_count)
        run_id = outcome["run_id"]
        self.assertEqual(run_id, preview["pending_run_id"])
        with closing(sqlite3.connect(self.business)) as con:
            rows = con.execute(
                "SELECT payload_json FROM csv_records WHERE run_id=? ORDER BY row_number",
                (run_id,),
            ).fetchall()
        self.assertEqual(len(rows), expected_count)
        values = [json.loads(record[0]) for record in rows]
        if expected_names is not None:
            self.assertEqual([row["name"] for row in values], expected_names)
        original_business_sha = hashlib.sha256(self.business.read_bytes()).hexdigest()
        code, history = self._call("/api/status?run_id=" + run_id)
        self.assertEqual(code, 200)
        self.assertEqual(history["status"], "completed")
        self.assertNotIn("Alpha", json.dumps(history))
        # A second POST with an already consumed preview must never duplicate
        # side effects. Durable read-only replay remains available.
        code, _ = self._run(task, preview, True)
        self.assertEqual(code, 409)
        self.assertEqual(
            hashlib.sha256(self.business.read_bytes()).hexdigest(), original_business_sha
        )
        self.assertEqual(self.csv_path.read_bytes(), self.csv_bytes)
        self.assertEqual(self._call("/api/la-audit?run_id=" + run_id)[0], 200)
        return run_id

    def test_01_plain_language_csv_to_sqlite(self):
        run_id = self._scenario(
            "이 CSV 파일을 로컬 SQLite에 저장해줘", 3,
            expected_names=["  Alpha  ", "  Beta  ", "  Gamma  "],
        )
        self.assertEqual(self._call("/api/status?run_id=" + run_id)[1]["status"], "completed")

    def test_02_plain_language_filtered_csv_import(self):
        self._scenario(
            "Import this CSV where amount > 100 into SQLite", 2,
            expected_names=["  Beta  ", "  Gamma  "],
        )

    def test_03_plain_language_normalized_csv_import(self):
        self._scenario(
            "Trim whitespace in the name column, then import this CSV into local SQLite",
            3, expected_names=["Alpha", "Beta", "Gamma"],
        )


if __name__ == "__main__":
    unittest.main()
