"""Distribution acceptance: build and run the portable Windows bundle without the source tree.

The .cmd entrypoint requires a real Windows CI runner; Python supervision and
all bundled LA/SQLite contracts run on both Windows and Linux.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import closing
from urllib.error import URLError
from urllib.request import Request, urlopen


REPO = Path(__file__).resolve().parents[3]
LA_PACKAGE = REPO / "packages" / "lightning-azent"
LA_MARKER = LA_PACKAGE / "lightning_azent" / "__init__.py"


def free_port() -> int:
    with closing(socket.socket()) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@unittest.skipUnless(LA_MARKER.is_file(), "real LA source has not been staged")
class PortableWindowsBundleTests(unittest.TestCase):
    def test_portable_launcher_smoke_lock_and_termination(self):
        with tempfile.TemporaryDirectory(prefix="hae-bundle-acceptance-") as directory:
            root = Path(directory)
            bundle = root / "HAE 한글 Windows Offline"
            built = subprocess.run([
                sys.executable, str(REPO / "tools" / "build_hae_windows_bundle.py"),
                "--la-package", str(LA_PACKAGE), "--output-dir", str(bundle),
            ], cwd=root, capture_output=True, text=True, timeout=20)
            self.assertEqual(built.returncode, 0, built.stderr)
            self.assertEqual({name.name for name in bundle.iterdir()}, {
                "run-bundled.cmd", "launch_integrated.py", "hae-integrated.pyz",
            })
            duplicate = subprocess.run([
                sys.executable, str(REPO / "tools" / "build_hae_windows_bundle.py"),
                "--la-package", str(LA_PACKAGE), "--output-dir", str(bundle),
            ], cwd=root, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(duplicate.returncode, 0, "bundle builder must not overwrite output")

            data = root / "로컬 사용자 데이터"
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            script = bundle / "launch_integrated.py"
            smoke = subprocess.run([
                sys.executable, str(script), "--data-dir", str(data),
                "--port", str(free_port()), "--smoke",
            ], cwd=root, env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(smoke.returncode, 0, smoke.stdout + smoke.stderr)
            self.assertIn("readiness: PASS", smoke.stdout)
            self.assertTrue((data / "input" / "contacts.csv").is_file())
            self.assertFalse((data / "runtime.db").exists())
            self.assertFalse((data / "business.db").exists())

            # Full acceptance must run against a private temporary SQLite DB,
            # NOT against the user's configured HAE data directory.
            verification = subprocess.run([
                sys.executable, str(script), "--verify",
                "--data-dir", str(data),
            ], cwd=root, env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(verification.returncode, 0, verification.stdout + verification.stderr)
            self.assertIn("7/7 PASS", verification.stdout)
            self.assertFalse((data / "runtime.db").exists())
            self.assertFalse((data / "business.db").exists())

            invalid_modes = subprocess.run([
                sys.executable, str(script), "--smoke", "--verify",
            ], cwd=root, env=env, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(invalid_modes.returncode, 0)

            # An occupied loopback port must not be mistaken for our own
            # successfully started backend (even when it hosts another HAE).
            with closing(socket.socket()) as occupied:
                occupied.bind(("127.0.0.1", 0))
                occupied.listen(1)
                held_port = occupied.getsockname()[1]
                unavailable = subprocess.run([
                    sys.executable, str(script), "--data-dir", str(data),
                    "--port", str(held_port), "--smoke",
                ], cwd=root, env=env, capture_output=True, text=True, timeout=10)
                self.assertNotEqual(unavailable.returncode, 0)
                self.assertIn("is in use", unavailable.stderr)
                self.assertFalse((data / "business.db").exists())

            port = free_port()
            origin = f"http://127.0.0.1:{port}"
            with (root / "server.log").open("w", encoding="utf-8") as log:
                server = subprocess.Popen([
                    sys.executable, str(script), "--data-dir", str(data),
                    "--port", str(port), "--no-browser",
                ], cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
                try:
                    for attempt in range(120):
                        self.assertIsNone(server.poll(), "portable launcher exited unexpectedly")
                        try:
                            with urlopen(origin + "/api/health", timeout=0.5) as response:
                                status = json.load(response)
                            if status["ready"] and status["engine_backend"]["name"] == "Lightning Azent":
                                break
                        except (OSError, ValueError, URLError):
                            time.sleep(0.04)
                    else:
                        self.fail("bundled integrated backend did not become ready")

                    conflict = subprocess.run([
                        sys.executable, str(script), "--data-dir", str(data),
                        "--port", str(free_port()), "--smoke",
                    ], cwd=root, env=env, capture_output=True, text=True, timeout=10)
                    self.assertNotEqual(conflict.returncode, 0)
                    self.assertIn("already running", conflict.stderr)

                    payload = {"task": "Import this CSV into local SQLite", "csv_path": "contacts.csv"}
                    def post(path: str, body: dict):
                        req = Request(origin + path, data=json.dumps(body).encode("utf-8"),
                                      headers={"Origin": origin, "Content-Type": "application/json"},
                                      method="POST")
                        with urlopen(req, timeout=10) as response:
                            return json.load(response)

                    preview = post("/api/preview", payload)
                    result = post("/api/run", {
                        **payload, "preview_id": preview["preview_id"],
                        "approve_writes": True,
                    })
                    self.assertEqual(result["status"]["status"], "completed")
                    self.assertEqual(result["result"]["imported_rows"], 2)
                    with urlopen(origin + "/api/la-audit?run_id=" + result["run_id"], timeout=5) as response:
                        audit = json.load(response)
                    self.assertGreaterEqual(audit["approval_count"], 1)
                finally:
                    if server.poll() is None:
                        server.terminate()
                    try:
                        server.wait(timeout=6)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=6)

            # A Windows console can be closed without delivering Python
            # SIGTERM. The server must live in the same process, not survive
            # as an orphaned child still occupying the listening port.
            abrupt_port = free_port()
            abruptly_killed = subprocess.Popen([
                sys.executable, str(script), "--data-dir", str(data),
                "--port", str(abrupt_port), "--no-browser",
            ], cwd=root, env=env, stdin=subprocess.DEVNULL,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                for _ in range(120):
                    self.assertIsNone(abruptly_killed.poll())
                    try:
                        with urlopen(f"http://127.0.0.1:{abrupt_port}/api/health", timeout=0.5) as response:
                            if json.load(response).get("ready"):
                                break
                    except (OSError, ValueError, URLError):
                        time.sleep(0.04)
                else:
                    self.fail("bundle supervisor did not open its localhost port")
                abruptly_killed.kill()  # TerminateProcess on Windows; SIGKILL on Linux
                abruptly_killed.wait(timeout=5)
                for _ in range(40):
                    try:
                        with closing(socket.create_connection(("127.0.0.1", abrupt_port), timeout=0.2)):
                            time.sleep(0.05)
                    except OSError:
                        break
                else:
                    self.fail("killing the bundle launcher orphaned an HTTP server")
            finally:
                if abruptly_killed.poll() is None:
                    abruptly_killed.kill()
                    abruptly_killed.wait(timeout=5)

            # The previous shutdown must release both port and lock.
            recovered = subprocess.run([
                sys.executable, str(script), "--data-dir", str(data),
                "--port", str(port), "--smoke",
            ], cwd=root, env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(recovered.returncode, 0, recovered.stdout + recovered.stderr)


if __name__ == "__main__":
    unittest.main()
