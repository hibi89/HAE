import json
import hashlib
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path


class ZipappSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.outside = cls.root / "outside"
        cls.outside.mkdir()
        cls.package = cls.outside / "axflow.pyz"
        repo = Path(__file__).resolve().parents[3]
        build = subprocess.run(
            [sys.executable, str(repo / "tools" / "package_axflow.py"), "--output", str(cls.package)],
            cwd=cls.outside, capture_output=True, text=True, timeout=15,
        )
        if build.returncode != 0:
            raise RuntimeError(build.stderr or build.stdout)
        if not cls.package.is_file():
            raise RuntimeError("zipapp builder did not create the requested output")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def _run_packaged(self, *args, timeout=15):
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        return subprocess.run(
            [sys.executable, str(self.package), *map(str, args)],
            cwd=self.outside, env=env, capture_output=True, text=True, timeout=timeout,
        )

    def test_zipapp_cli_runs_synthetic_workflow_outside_source_tree(self):
        plan_path = self.outside / "plan.json"
        plan_path.write_text(json.dumps({"version": "axflow.ir.v0", "steps": [
            {"id": "seed", "op": "literal", "value": {"name": "package-fixture", "count": 3}},
            {"id": "save", "op": "sqlite_put", "from": "seed"},
            {"id": "read", "op": "sqlite_get", "from": "save"},
        ]}), encoding="utf-8")
        checked = self._run_packaged("validate", plan_path, "--synthetic")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertIn("VALIDATED", checked.stdout)

        state, business = self.outside / "runtime.db", self.outside / "business.db"
        executed = self._run_packaged(
            "run", plan_path, "--synthetic", "--state", state, "--data", business,
            "--run-id", "PackagedDemo", "--approve-writes",
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)
        self.assertEqual(json.loads(executed.stdout)["result"], {"count": 3, "name": "package-fixture"})
        with closing(sqlite3.connect(business)) as con:
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM records WHERE run_id='PackagedDemo' AND step_id='save'"
            ).fetchone()[0], 1)

    def test_package_builder_refuses_to_overwrite_an_existing_artifact(self):
        before = hashlib.sha256(self.package.read_bytes()).hexdigest()
        repo = Path(__file__).resolve().parents[3]
        attempt = subprocess.run(
            [sys.executable, str(repo / "tools" / "package_axflow.py"), "--output", str(self.package)],
            cwd=self.outside, capture_output=True, text=True, timeout=15,
        )
        self.assertNotEqual(attempt.returncode, 0)
        self.assertIn("overwrite", attempt.stderr.lower())
        self.assertEqual(hashlib.sha256(self.package.read_bytes()).hexdigest(), before)

    def test_zipapp_serves_bundled_ui_assets_from_localhost(self):
        inputs = self.outside / "input"
        inputs.mkdir()
        (inputs / "contacts.csv").write_text("id,name\n1,Fixture\n", encoding="utf-8")
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        state, business = self.outside / "ui-runtime.db", self.outside / "ui-business.db"
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        process = subprocess.Popen(
            [sys.executable, str(self.package), "serve", "--input-root", str(inputs),
             "--state", str(state), "--data", str(business), "--synthetic", "--port", str(port)],
            cwd=self.outside, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        base = f"http://127.0.0.1:{port}"
        try:
            deadline = time.monotonic() + 8
            while True:
                if process.poll() is not None:
                    stdout, stderr = process.communicate(timeout=1)
                    self.fail(f"packaged server exited early: {stdout} {stderr}")
                try:
                    with opener.open(base + "/", timeout=1) as response:
                        page = response.read().decode("utf-8")
                    break
                except (OSError, urllib.error.URLError):
                    if time.monotonic() >= deadline:
                        self.fail("packaged localhost UI did not become ready")
                    time.sleep(0.05)
            self.assertIn("/app.js", page)
            self.assertIn("/app.css", page)
            for asset in ("/app.js", "/app.css"):
                with opener.open(base + asset, timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    self.assertGreater(len(response.read()), 100)
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
