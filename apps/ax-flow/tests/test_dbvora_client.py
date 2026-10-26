import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from axflow.dbvora_client import DbvoraClient


INVENTORY = {
    "contract_version": "p0-01.v1",
    "db_id": "0123456789abcdef01234567",
    "engine": "sqlite",
    "size_bytes": 4096,
    "size_scope": "main_database_file_only_excludes_wal_and_shm",
    "observed_at": "2026-10-27T00:00:00Z",
    "provenance": {
        "size_bytes": "measured_local_filesystem",
        "tables": "measured_sqlite_catalog",
        "relationships": "declared_sqlite_foreign_keys",
        "cpu_usage": "unavailable",
    },
    "tables": [
        {
            "name": "orders",
            "columns": [
                {"name": "id", "type": "INTEGER", "nullable_declared": True, "pk_position": 1, "hidden": 0},
                {"name": "customer_id", "type": "INTEGER", "nullable_declared": True, "pk_position": 0, "hidden": 0},
            ],
            "foreign_keys": [
                {
                    "id": 0,
                    "to_table": "customers",
                    "from_columns": ["customer_id"],
                    "to_columns": ["id"],
                    "on_update": "NO ACTION",
                    "on_delete": "CASCADE",
                },
            ],
        },
        {
            "name": "customers",
            "columns": [
                {"name": "id", "type": "INTEGER", "nullable_declared": True, "pk_position": 1, "hidden": 0},
                {"name": "name", "type": "TEXT", "nullable_declared": False, "pk_position": 0, "hidden": 0},
            ],
            "foreign_keys": [],
        },
    ],
    "relationships": [
        {
            "from_table": "orders",
            "from_columns": ["customer_id"],
            "to_table": "customers",
            "to_columns": ["id"],
            "evidence": "declared_foreign_key",
        },
    ],
}


class _FixtureHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, responses):
        self.responses = responses
        self.requests = []
        super().__init__(("127.0.0.1", 0), _FixtureHandler)


class _FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        self.server.requests.append((self.command, self.path))
        status, headers, body = self.server.responses.get(
            self.path, (404, {"Content-Type": "application/json"}, {"error": "missing"})
        )
        if not isinstance(body, bytes):
            body = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        if not any(name.casefold() == "content-length" for name in headers):
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)


class DbvoraClientTests(unittest.TestCase):
    def start_server(self, *, health=None, inventory=None):
        responses = {
            "/health": (200, {"Content-Type": "application/json"}, health or {
                "ok": True, "mode": "local-read-only",
            }),
            "/api/inventory": (200, {"Content-Type": "application/json"}, inventory if inventory is not None else INVENTORY),
        }
        server = _FixtureHTTPServer(responses)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        server.fixture_thread = thread
        self.addCleanup(self.stop_server, server, thread)
        return server, "http://127.0.0.1:" + str(server.server_port)

    @staticmethod
    def stop_server(server, thread):
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()

    def test_reads_actual_dbvora_contract_and_returns_metadata_only(self):
        server, origin = self.start_server()
        result = DbvoraClient(origin).fetch_inventory()
        self.assertTrue(result["available"])
        self.assertEqual(result["contract_version"], "p0-01.v1")
        self.assertEqual(result["size_bytes"], 4096)
        self.assertEqual([table["name"] for table in result["tables"]], ["customers", "orders"])
        order = result["tables"][1]
        self.assertEqual(order["columns"][0]["pk_position"], 1)
        self.assertEqual(order["foreign_keys"][0]["to_table"], "customers")
        self.assertEqual(result["relationships"][0]["evidence"], "declared_foreign_key")
        self.assertEqual(server.requests, [("GET", "/health"), ("GET", "/api/inventory")])
        self.assertNotIn("rows", json.dumps(result))
        self.assertNotIn("path", json.dumps(result))

    def test_unconfigured_and_unavailable_states_are_bounded(self):
        self.assertEqual(
            DbvoraClient().fetch_inventory(),
            {
                "available": False,
                "error_code": "NOT_CONFIGURED",
                "message": "Configure a loopback DBVORA URL to view database metadata.",
            },
        )
        server, origin = self.start_server()
        self.stop_server(server, server.fixture_thread)
        result = DbvoraClient(origin, timeout_seconds=0.25).fetch_inventory()
        self.assertFalse(result["available"])
        self.assertEqual(result["error_code"], "UNAVAILABLE")
        self.assertNotIn("127.0.0.1", result["message"])
        self.assertNotIn(str(server.server_port), result["message"])

    def test_only_explicit_loopback_http_origin_is_accepted(self):
        for value in (
            "https://127.0.0.1:8766",
            "http://example.com:8766",
            "http://127.0.0.2:8766",
            "http://127.0.0.1",
            "http://127.0.0.1:0",
            "http://user@127.0.0.1:8766",
            "http://127.0.0.1:8766/private",
            "http://127.0.0.1:8766/?target=elsewhere",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    DbvoraClient(value)

    def test_health_mode_must_be_local_and_read_only(self):
        server, origin = self.start_server(health={"ok": True, "mode": "read-write"})
        result = DbvoraClient(origin).fetch_inventory()
        self.assertFalse(result["available"])
        self.assertEqual(result["error_code"], "INVALID_HEALTH")
        self.assertEqual(server.requests, [("GET", "/health")])

    def test_redirect_is_not_followed_and_inventory_is_not_requested(self):
        server, origin = self.start_server()
        server.responses["/health"] = (
            302, {"Content-Type": "application/json", "Location": "https://example.com/"}, b""
        )
        result = DbvoraClient(origin).fetch_inventory()
        self.assertFalse(result["available"])
        self.assertEqual(result["error_code"], "HTTP_302")
        self.assertEqual(server.requests, [("GET", "/health")])

    def test_invalid_contract_and_duplicate_json_fail_closed(self):
        server, origin = self.start_server(inventory={"contract_version": "unknown"})
        result = DbvoraClient(origin).fetch_inventory()
        self.assertFalse(result["available"])
        self.assertEqual(result["error_code"], "UNSUPPORTED_CONTRACT")

        server, origin = self.start_server()
        server.responses["/api/inventory"] = (
            200, {"Content-Type": "application/json"}, b'{"contract_version":"p0-01.v1","contract_version":"bad"}'
        )
        result = DbvoraClient(origin).fetch_inventory()
        self.assertFalse(result["available"])
        self.assertEqual(result["error_code"], "INVALID_RESPONSE")

    def test_large_response_is_rejected_before_parsing(self):
        server, origin = self.start_server()
        server.responses["/api/inventory"] = (
            200,
            {"Content-Type": "application/json", "Content-Length": str(2 * 1024 * 1024 + 1)},
            b"{}",
        )
        result = DbvoraClient(origin).fetch_inventory()
        self.assertFalse(result["available"])
        self.assertEqual(result["error_code"], "RESPONSE_TOO_LARGE")

    def test_extremely_long_content_length_fails_closed(self):
        server, origin = self.start_server()
        server.responses["/api/inventory"] = (
            200, {"Content-Type": "application/json", "Content-Length": "9" * 5000}, b"{}"
        )
        result = DbvoraClient(origin).fetch_inventory()
        self.assertFalse(result["available"])
        self.assertEqual(result["error_code"], "RESPONSE_TOO_LARGE")

    def test_deeply_nested_json_fails_closed(self):
        server, origin = self.start_server()
        nested = b"[" * 2000 + b"0" + b"]" * 2000
        server.responses["/api/inventory"] = (
            200, {"Content-Type": "application/json"}, nested
        )
        result = DbvoraClient(origin).fetch_inventory()
        self.assertFalse(result["available"])
        self.assertEqual(result["error_code"], "INVALID_RESPONSE")


if __name__ == "__main__":
    unittest.main()
