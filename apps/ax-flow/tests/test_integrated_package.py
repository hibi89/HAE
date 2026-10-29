"""Execute HAE + real LA from a single offline zipapp, outside both source trees."""
from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


REPO = Path(__file__).resolve().parents[3]
LA_SOURCE = REPO / "packages" / "lightning-azent"
LA_MARKER = LA_SOURCE / "lightning_azent" / "__init__.py"
TASK = "Import this CSV into local SQLite"


@unittest.skipUnless(LA_MARKER.is_file(), "real LA source has not been staged for offline packaging")
class IntegratedOfflineZipappTests(unittest.TestCase):
    def test_offline_single_file_hae_la_http_write_audit_restart(self):
        with tempfile.TemporaryDirectory(prefix="hae-offline-zipapp-") as folder:
            root = Path(folder)
            data_dir = root / "input"
            data_dir.mkdir()
            (data_dir / "contacts.csv").write_bytes(
                b"id,name\n11,SyntheticAlice\n12,SyntheticBob\n"
            )
            artifact = root / "hae-integrated.pyz"
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            build = subprocess.run([
                sys.executable, str(REPO / "tools" / "package_hae_integrated.py"),
                "--la-package", str(LA_SOURCE), "--output", str(artifact),
            ], cwd=root, env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(build.returncode, 0, build.stderr)
            self.assertTrue(artifact.is_file())

            state = root / "state.db"
            business = root / "business.db"
            worker = None
            log = root / "server.log"
            server_log = None

            def start():
                nonlocal worker, server_log
                with closing(socket.socket()) as sock:
                    sock.bind(("127.0.0.1", 0))
                    port = sock.getsockname()[1]
                origin = "http://127.0.0.1:" + str(port)
                server_log = log.open("ab")
                worker = subprocess.Popen([
                    sys.executable, str(artifact), "serve", "--synthetic",
                    "--engine-backend", "lightning-azent",
                    "--input-root", str(data_dir), "--state", str(state),
                    "--data", str(business), "--port", str(port),
                ], cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=server_log,
                    stderr=subprocess.STDOUT)
                for _ in range(100):
                    if worker.poll() is not None:
                        self.fail("offline packaged HAE terminated: " +
                                  log.read_text(encoding="utf-8", errors="replace"))
                    try:
                        with urlopen(origin + "/api/health", timeout=1) as response:
                            health = json.load(response)
                        if health.get("ready") and health.get("engine_backend", {}).get("name") == "Lightning Azent":
                            return origin
                    except (OSError, ValueError):
                        time.sleep(0.05)
                self.fail("offline packaged HAE did not become ready")

            def stop():
                nonlocal worker, server_log
                if worker is not None and worker.poll() is None:
                    worker.terminate()
                    try:
                        worker.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        worker.kill()
                        worker.wait(timeout=5)
                if server_log is not None:
                    server_log.close()
                server_log = None
                worker = None

            def request(origin, method, path, payload=None):
                data = json.dumps(payload).encode("utf-8") if payload is not None else None
                headers = {"Origin": origin, "Content-Type": "application/json"} if data else {}
                req = Request(origin + path, data=data, headers=headers, method=method)
                try:
                    with urlopen(req, timeout=6) as response:
                        return response.status, json.load(response)
                except HTTPError as error:
                    with error:
                        return error.code, json.load(error)

            try:
                origin = start()
                with urlopen(origin + "/", timeout=3) as response:
                    self.assertIn("HAE", response.read().decode("utf-8"))
                self.assertFalse(state.exists())
                self.assertFalse(business.exists())
                args = {"task": TASK, "csv_path": "contacts.csv"}
                code, preview = request(origin, "POST", "/api/preview", args)
                self.assertEqual(code, 200, preview)
                self.assertFalse(state.exists())
                code, denied = request(origin, "POST", "/api/run", {
                    **args, "preview_id": preview["preview_id"], "approve_writes": False,
                })
                self.assertEqual(code, 403, denied)
                self.assertFalse(business.exists())

                code, executed = request(origin, "POST", "/api/run", {
                    **args, "preview_id": preview["preview_id"], "approve_writes": True,
                })
                self.assertEqual(code, 200, executed)
                self.assertEqual(executed["status"]["status"], "completed")
                self.assertEqual(executed["workflow_status"], "completed")
                self.assertEqual(executed["result"]["imported_rows"], 2)
                run_id = executed["run_id"]

                code, audit = request(origin, "GET", "/api/la-audit?run_id=" + run_id)
                self.assertEqual(code, 200, audit)
                self.assertGreaterEqual(audit["total_events"], 1)
                self.assertGreaterEqual(audit["approval_count"], 1)
                self.assertNotIn("SyntheticAlice", json.dumps(audit))

                # Packaged LA must support a second independent run against the
                # already-initialized runtime/business ledgers.
                code, next_preview = request(origin, "POST", "/api/preview", args)
                self.assertEqual(code, 200, next_preview)
                code, second = request(origin, "POST", "/api/run", {
                    **args, "preview_id": next_preview["preview_id"],
                    "approve_writes": True,
                })
                self.assertEqual(code, 200, second)
                self.assertNotEqual(second["run_id"], run_id)
                self.assertEqual(second["status"]["status"], "completed")
                self.assertEqual(second["result"]["imported_rows"], 2)

                stop()
                with closing(sqlite3.connect(business)) as connection:
                    self.assertEqual(connection.execute(
                        "SELECT COUNT(*) FROM csv_records"
                    ).fetchone()[0], 4)

                origin = start()
                code, after_restart = request(origin, "GET", "/api/status?run_id=" + run_id)
                self.assertEqual(code, 200, after_restart)
                self.assertEqual(after_restart["status"], "completed")
                code, restored_audit = request(origin, "GET", "/api/la-audit?run_id=" + run_id)
                self.assertEqual(code, 200, restored_audit)
                self.assertEqual(restored_audit["total_events"], audit["total_events"])
            finally:
                stop()


if __name__ == "__main__":
    unittest.main()
