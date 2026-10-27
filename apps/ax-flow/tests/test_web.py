import hashlib
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
from unittest.mock import patch

from axflow.web import create_server


class WebUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "input"
        self.inputs.mkdir()
        (self.inputs / "contacts.csv").write_text("id,name\n11,Synthetic\n", encoding="utf-8")
        (self.inputs / "sales.csv").write_text(
            "amount,id\n125,A\n20,B\n125,C\n", encoding="utf-8"
        )
        (self.inputs / "people.csv").write_text(
            "id,name\n11,PrivateMarker\n12,OtherFixture\n", encoding="utf-8"
        )
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
        self.assertIn(b"duplicate_count", script)
        self.assertIn(b"csv_normalize_import", script)
        self.assertIn(b"DBVORA", body)
        self.assertIn(b"/api/dbvora", script)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())

    def test_dbvora_endpoint_reports_unconfigured_without_network(self):
        status, _, raw = self.request("/api/dbvora")
        self.assertEqual(status, 200)
        body = json.loads(raw.decode("utf-8"))
        self.assertFalse(body["available"])
        self.assertEqual(body["error_code"], "NOT_CONFIGURED")
        self.assertIn("loopback", body["message"])

    def test_dbvora_endpoint_exposes_only_read_only_metadata(self):
        inventory = {
            "available": True,
            "contract_version": "p0-01.v1",
            "engine": "sqlite",
            "size_bytes": 2048,
            "size_scope": "main_database_file_only_excludes_wal_and_shm",
            "observed_at": "2026-10-27T00:00:00Z",
            "tables": [{
                "name": "customers",
                "columns": [{
                    "name": "id", "type": "INTEGER", "nullable_declared": True,
                    "pk_position": 1, "hidden": 0,
                }],
                "foreign_keys": [],
            }],
            "relationships": [],
        }
        with patch.object(self.server.dbvora_client, "fetch_inventory", return_value=inventory):
            status, _, raw = self.request("/api/dbvora")
        self.assertEqual(status, 200)
        body = json.loads(raw.decode("utf-8"))
        self.assertEqual(body["tables"][0]["columns"][0]["pk_position"], 1)
        self.assertEqual(body["size_bytes"], 2048)
        self.assertNotIn("payload", body)

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

    def test_preview_and_execute_filtered_import_lookup_and_conditional_flows(self):
        filtered_task = "이 CSV에서 amount가 100 이상인 행만 로컬 SQLite에 저장해줘"
        code, _, preview = self.post_json("/api/preview", {
            "task": filtered_task, "csv_path": "sales.csv",
        })
        self.assertEqual(code, 200, preview)
        self.assertEqual(preview["workflow"], "csv_filtered_import")
        self.assertTrue(preview["requires_approval"])
        self.assertEqual([step["op"] for step in preview["plan"]["steps"]],
                         ["csv_read", "csv_filter", "sqlite_import_csv"])
        code, _, filtered = self.post_json("/api/run", {
            "task": filtered_task, "csv_path": "sales.csv",
            "preview_id": preview["preview_id"], "approve_writes": True,
        })
        self.assertEqual(code, 200, filtered)
        self.assertEqual(filtered["result"]["imported_rows"], 2)

        lookup_task = "이 CSV에서 id가 11인 행을 찾아줘"
        code, _, preview = self.post_json("/api/preview", {
            "task": lookup_task, "csv_path": "people.csv",
        })
        self.assertEqual(code, 200, preview)
        self.assertEqual(preview["workflow"], "csv_lookup")
        self.assertFalse(preview["requires_approval"])
        code, _, lookup = self.post_json("/api/run", {
            "task": lookup_task, "csv_path": "people.csv",
            "preview_id": preview["preview_id"], "approve_writes": False,
        })
        self.assertEqual(code, 200, lookup)
        self.assertEqual(lookup["result"]["matched_count"], 1)
        self.assertEqual(lookup["result"]["matched_row_numbers"], [1])
        self.assertNotIn("PrivateMarker", json.dumps(lookup))

        conditional_task = "이 CSV에서 amount가 100 이상일 때만 로컬 SQLite에 저장해줘"
        code, _, preview = self.post_json("/api/preview", {
            "task": conditional_task, "csv_path": "sales.csv",
        })
        self.assertEqual(code, 200, preview)
        self.assertEqual(preview["workflow"], "csv_conditional_import")
        self.assertTrue(preview["requires_approval"])
        self.assertIn("condition", [step["op"] for step in preview["plan"]["steps"]])
        code, _, conditional = self.post_json("/api/run", {
            "task": conditional_task, "csv_path": "sales.csv",
            "preview_id": preview["preview_id"], "approve_writes": True,
        })
        self.assertEqual(code, 200, conditional)
        self.assertEqual(conditional["result"]["imported_rows"], 2)

        no_match_task = "이 CSV에서 amount가 500 이상일 때만 로컬 SQLite에 저장해줘"
        code, _, preview = self.post_json("/api/preview", {
            "task": no_match_task, "csv_path": "sales.csv",
        })
        self.assertEqual(code, 200, preview)
        code, _, no_match = self.post_json("/api/run", {
            "task": no_match_task, "csv_path": "sales.csv",
            "preview_id": preview["preview_id"], "approve_writes": True,
        })
        self.assertEqual(code, 200, no_match)
        self.assertEqual(no_match["result"], {"imported_rows": 0, "matched_rows": 0})
        with closing(sqlite3.connect(self.business)) as con:
            count = con.execute(
                "SELECT COUNT(*) FROM csv_records WHERE run_id=?", (no_match["run_id"],)
            ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_browser_normalization_import_reports_duplicate_rows_without_raw_data(self):
        (self.inputs / "normalize.csv").write_text(
            "id,name\n21, PrivateMarker \n21,PrivateMarker\n", encoding="utf-8"
        )
        task = "Trim whitespace in the name column, then import this CSV into local SQLite"
        code, _, preview = self.post_json("/api/preview", {"task": task, "csv_path": "normalize.csv"})
        self.assertEqual(code, 200, preview)
        self.assertEqual(preview["workflow"], "csv_normalize_import")
        self.assertTrue(preview["requires_approval"])
        self.assertEqual([step["op"] for step in preview["plan"]["steps"]], [
            "csv_read", "csv_normalize", "sqlite_import_csv",
        ])

        code, _, response = self.post_json("/api/run", {
            "task": task, "csv_path": "normalize.csv", "preview_id": preview["preview_id"],
            "approve_writes": True,
        })
        self.assertEqual(code, 200, response)
        self.assertEqual(response["result"]["imported_rows"], 2)
        self.assertEqual(response["result"]["duplicate_count"], 1)
        self.assertEqual(response["result"]["duplicate_row_numbers"], [2])
        self.assertNotIn("PrivateMarker", json.dumps(response["status"]))
        with closing(sqlite3.connect(self.business)) as business:
            self.assertEqual(business.execute(
                "SELECT COUNT(*) FROM csv_records WHERE run_id=?", (response["run_id"],)
            ).fetchone()[0], 2)
            self.assertEqual(business.execute(
                "SELECT payload_json FROM csv_records WHERE run_id=? AND row_number=1",
                (response["run_id"],),
            ).fetchone()[0], '{"id":"21","name":"PrivateMarker"}')

    def test_natural_language_numeric_conversion_fails_before_invalid_rows_are_saved(self):
        valid_path = self.inputs / "amounts.csv"
        valid_bytes = b"amount\n42\n3.75\n1.25e2\n 8.5 \n1e-7\n"
        valid_path.write_bytes(valid_bytes)
        task = "Convert the amount column to a number, then import this CSV into local SQLite"

        code, _, preview = self.post_json("/api/preview", {"task": task, "csv_path": "amounts.csv"})
        self.assertEqual(code, 200, preview)
        self.assertEqual(preview["plan"]["steps"][1]["transforms"], {"amount": "number"})
        valid_hash = hashlib.sha256(valid_bytes).hexdigest()
        valid_metadata = (valid_path.stat().st_size, valid_path.stat().st_mtime_ns)
        code, _, result = self.post_json("/api/run", {
            "task": task, "csv_path": "amounts.csv", "preview_id": preview["preview_id"],
            "approve_writes": True,
        })
        self.assertEqual(code, 200, result)
        self.assertEqual(result["result"]["imported_rows"], 5)
        with closing(sqlite3.connect(self.business)) as business:
            stored = business.execute(
                "SELECT payload_json FROM csv_records WHERE run_id=? ORDER BY row_number",
                (result["run_id"],),
            ).fetchall()
        self.assertEqual([json.loads(item[0])["amount"] for item in stored], [42, 3.75, 125, 8.5, 1e-7])
        self.assertEqual(hashlib.sha256(valid_path.read_bytes()).hexdigest(), valid_hash)
        self.assertEqual((valid_path.stat().st_size, valid_path.stat().st_mtime_ns), valid_metadata)

        invalid_values = (
            "", "   ", "NaN", "Infinity", "-inf", "1e9999", "1e-9999", "$12.50",
            "1_000", "9007199254740993", "0.10000000000000001",
        )
        for index, value in enumerate(invalid_values):
            with self.subTest(value=value):
                invalid_name = f"invalid-amount-{index}.csv"
                invalid_path = self.inputs / invalid_name
                invalid_bytes = f'amount\n"{value}"\n'.encode("utf-8")
                invalid_path.write_bytes(invalid_bytes)
                original_hash = hashlib.sha256(invalid_bytes).hexdigest()
                original_metadata = (invalid_path.stat().st_size, invalid_path.stat().st_mtime_ns)
                code, _, invalid_preview = self.post_json("/api/preview", {
                    "task": task, "csv_path": invalid_name,
                })
                self.assertEqual(code, 200, invalid_preview)
                code, _, failure = self.post_json("/api/run", {
                    "task": task, "csv_path": invalid_name,
                    "preview_id": invalid_preview["preview_id"], "approve_writes": True,
                })
                self.assertEqual(code, 422, failure)
                self.assertEqual(failure["error_type"], "PlanError")
                self.assertEqual(failure["status"]["status"], "failed")
                self.assertEqual(hashlib.sha256(invalid_path.read_bytes()).hexdigest(), original_hash)
                self.assertEqual((invalid_path.stat().st_size, invalid_path.stat().st_mtime_ns), original_metadata)
                with closing(sqlite3.connect(self.business)) as business:
                    self.assertEqual(business.execute(
                        "SELECT COUNT(*) FROM csv_records WHERE run_id=?", (failure["run_id"],)
                    ).fetchone()[0], 0)
                    self.assertEqual(business.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 5)
                if value.strip():
                    self.assertNotIn(value.strip(), json.dumps(failure["status"]))

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
