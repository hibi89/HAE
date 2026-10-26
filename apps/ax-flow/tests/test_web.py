import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from axflow.web import create_server


class WebUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "input"
        self.inputs.mkdir()
        (self.inputs / "contacts.csv").write_text("id,name\n11,Synthetic\n", encoding="utf-8")
        self.state = self.root / "ui-state.db"
        self.business = self.root / "ui-business.db"
        self.server = create_server(self.inputs, self.state, self.business, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop_server)
        self.origin = "http://127.0.0.1:" + str(self.server.server_port)
        self.url = self.origin

    def _stop_server(self):
        self.server.shutdown()
        self.thread.join(timeout=3)
        self.server.server_close()

    def request(self, path, *, payload=None, raw=None, headers=None, method=None):
        data = raw
        request_headers = dict(headers or {})
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        if data is not None:
            request_headers.setdefault("Origin", self.origin)
        request = Request(self.url + path, data=data, headers=request_headers, method=method)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.headers, response.read()
        except HTTPError as exc:
            return exc.code, exc.headers, exc.read()

    def post_json(self, path, payload, *, headers=None):
        status, response_headers, raw = self.request(path, payload=payload, headers=headers, method="POST")
        return status, response_headers, json.loads(raw.decode("utf-8"))

    def test_local_page_and_assets_have_no_external_dependencies(self):
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("Content-Security-Policy", headers)
        self.assertIn(b"/app.js", body)
        self.assertIn(b"localhost only", body)
        script_status, _, script = self.request("/app.js")
        css_status, _, css = self.request("/app.css")
        self.assertEqual((script_status, css_status), (200, 200))
        self.assertNotIn(b"https://", script)
        self.assertNotIn(b"https://", css)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())

    def test_preview_parses_supported_request_and_rejects_unsupported_scope(self):
        status, _, body = self.post_json("/api/preview", {
            "task": "이 CSV를 로컬 SQLite에 저장해줘", "csv_path": "contacts.csv",
        })
        self.assertEqual(status, 200)
        self.assertTrue(body["validated"])
        self.assertEqual(body["workflow"], "csv_to_sqlite")
        self.assertEqual(body["plan"]["steps"][0]["path"], "contacts.csv")
        self.assertFalse(self.state.exists(), "preview must not create a database")

        for task in ("email this CSV to someone", "delete CSV rows in SQLite", "do not import CSV to SQLite"):
            code, _, error = self.post_json("/api/preview", {
                "task": task, "csv_path": "contacts.csv",
            })
            self.assertEqual(code, 422)
            self.assertIn("supported", error["error"])

    def test_write_needs_explicit_approval_and_rejects_path_escape(self):
        _, _, preview = self.post_json("/api/preview", {
            "task": "Import this CSV into local SQLite", "csv_path": "contacts.csv",
        })
        code, _, body = self.post_json("/api/run", {
            "task": "Import this CSV into local SQLite",
            "csv_path": "contacts.csv", "preview_id": preview["preview_id"], "approve_writes": False,
        })
        self.assertEqual(code, 403)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())

        code, _, body = self.post_json("/api/preview", {
            "task": "Import this CSV into local SQLite", "csv_path": "../escape.csv",
        })
        self.assertEqual(code, 422)
        self.assertIn("relative .csv", body["error"])

    def test_browser_run_writes_synthetic_rows_and_returns_redacted_status(self):
        _, _, preview = self.post_json("/api/preview", {
            "task": "Import this CSV file into local SQLite", "csv_path": "contacts.csv",
        })
        payload = {
            "task": "Import this CSV file into local SQLite",
            "csv_path": "contacts.csv", "preview_id": preview["preview_id"], "approve_writes": True,
        }
        code, _, body = self.post_json("/api/run", {
            **payload,
        })
        self.assertEqual(code, 200, body)
        run_id = body["run_id"]
        self.assertRegex(run_id, r"^Gui[A-Fa-f0-9]{12}$")
        self.assertEqual(body["result"]["imported_rows"], 1)
        self.assertEqual(body["status"]["status"], "completed")
        self.assertNotIn("Synthetic", json.dumps(body["status"]))
        replay_code, _, replay = self.post_json("/api/run", payload)
        self.assertEqual(replay_code, 200)
        self.assertEqual(replay["run_id"], run_id)
        self.assertEqual(replay["result"], body["result"])
        with closing(sqlite3.connect(self.business)) as con:
            self.assertEqual(con.execute(
                "SELECT payload_json FROM csv_records WHERE run_id=? AND row_number=1", (run_id,)
            ).fetchone()[0], '{"id":"11","name":"Synthetic"}')
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM csv_records WHERE run_id=?", (run_id,)
            ).fetchone()[0], 1)

        code, _, raw = self.request("/api/status?run_id=" + quote(run_id))
        self.assertEqual(code, 200)
        status = json.loads(raw.decode("utf-8"))
        self.assertEqual(status["status"], "completed")
        self.assertNotIn("Synthetic", json.dumps(status))

    def test_run_rejects_missing_or_mismatched_preview_token(self):
        _, _, preview = self.post_json("/api/preview", {
            "task": "Import this CSV into local SQLite", "csv_path": "contacts.csv",
        })
        code, _, body = self.post_json("/api/run", {
            "task": "Import this CSV into local SQLite", "csv_path": "contacts.csv",
            "preview_id": "0" * 32, "approve_writes": True,
        })
        self.assertEqual(code, 409)
        self.assertIn("preview", body["error"])
        code, _, body = self.post_json("/api/run", {
            "task": "Import this CSV into local SQLite", "csv_path": "../escape.csv",
            "preview_id": preview["preview_id"], "approve_writes": True,
        })
        self.assertEqual(code, 422)
        self.assertFalse(self.state.exists())

    def test_failed_run_returns_redacted_receipt_and_recoverable_error(self):
        _, _, preview = self.post_json("/api/preview", {
            "task": "Import this CSV into local SQLite", "csv_path": "missing.csv",
        })
        code, _, body = self.post_json("/api/run", {
            "task": "Import this CSV into local SQLite", "csv_path": "missing.csv",
            "preview_id": preview["preview_id"], "approve_writes": True,
        })
        self.assertEqual(code, 422)
        self.assertEqual(body["error_type"], "PlanError")
        self.assertEqual(body["status"]["status"], "failed")
        self.assertEqual(body["status"]["error_type"], "PlanError")
        self.assertNotIn("contacts.csv", json.dumps(body["status"]))
        code, _, raw = self.request("/api/status?run_id=" + quote(body["run_id"]))
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["status"], "failed")

    def test_request_origin_host_body_shape_and_content_type_are_checked(self):
        status, _, body = self.post_json(
            "/api/preview", {"task": "Import CSV into SQLite", "csv_path": "contacts.csv"},
            headers={"Origin": "https://attacker.example"},
        )
        self.assertEqual(status, 403)
        self.assertIn("cross-origin", body["error"])

        status, _, body = self.post_json(
            "/api/preview", {"task": "Import CSV into SQLite", "csv_path": "contacts.csv"},
            headers={"Host": "attacker.example"},
        )
        self.assertEqual(status, 403)
        self.assertIn("loopback", body["error"])

        status, _, body = self.post_json("/api/preview", {
            "task": "Import CSV into SQLite", "csv_path": "contacts.csv", "extra": True,
        })
        self.assertEqual(status, 400)

        status, _, raw = self.request(
            "/api/preview", raw=b'{"task":"Import CSV into SQLite","task":"send email","csv_path":"contacts.csv"}',
            headers={"Content-Type": "application/json", "Origin": self.origin}, method="POST",
        )
        self.assertEqual(status, 400)
        self.assertIn("invalid JSON", raw.decode("utf-8"))

        status, _, _ = self.request(
            "/api/preview", raw=b"{}", headers={"Content-Type": "text/plain", "Origin": self.origin}, method="POST",
        )
        self.assertEqual(status, 415)


if __name__ == "__main__":
    unittest.main()
