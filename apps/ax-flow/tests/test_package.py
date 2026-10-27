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

    def test_zipapp_cli_runs_normalize_filter_import_with_duplicate_receipt(self):
        inputs = self.outside / "normalized-input"
        inputs.mkdir()
        csv_path = inputs / "contacts.csv"
        source_bytes = (
            "id,name,active\n"
            "7, PACKAGED-SYNTHETIC-MARKER ,yes\n"
            "7,PACKAGED-SYNTHETIC-MARKER,yes\n"
            "8,Other,no\n"
        ).encode("utf-8")
        csv_path.write_bytes(source_bytes)
        source_hash = hashlib.sha256(source_bytes).hexdigest()
        source_size = csv_path.stat().st_size
        source_mtime = csv_path.stat().st_mtime_ns
        plan_path = self.outside / "normalized-plan.json"
        plan_path.write_text(json.dumps({"version": "axflow.ir.v0", "steps": [
            {"id": "input", "op": "csv_read", "path": "contacts.csv"},
            {"id": "normalized", "op": "csv_normalize", "from": "input",
             "transforms": {"name": "trim"}},
            {"id": "filtered", "op": "csv_filter", "from": "normalized", "field": "active",
             "operator": "eq", "value": "yes"},
            {"id": "imported", "op": "sqlite_import_csv", "from": "filtered"},
        ]}), encoding="utf-8")
        state, business = self.outside / "normalized-runtime.db", self.outside / "normalized-business.db"
        executed = self._run_packaged(
            "run", plan_path, "--input-root", inputs, "--synthetic", "--state", state,
            "--data", business, "--run-id", "PackagedNormalize", "--approve-writes",
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)
        result = json.loads(executed.stdout)["result"]
        self.assertEqual(result["imported_rows"], 2)
        self.assertEqual(result["duplicate_count"], 1)
        self.assertEqual(result["duplicate_row_numbers"], [2])
        self.assertEqual(result["source_sha256"], source_hash)
        self.assertNotIn("PACKAGED-SYNTHETIC-MARKER", executed.stdout)
        self.assertEqual((csv_path.stat().st_size, csv_path.stat().st_mtime_ns), (source_size, source_mtime))
        self.assertEqual(hashlib.sha256(csv_path.read_bytes()).hexdigest(), source_hash)
        self.assertNotEqual(state.resolve(), business.resolve())
        self.assertNotIn("PACKAGED-SYNTHETIC-MARKER", state.read_bytes().decode("latin1"))
        with closing(sqlite3.connect(business)) as con:
            rows = con.execute(
                "SELECT row_number,payload_json FROM csv_records WHERE run_id=? ORDER BY row_number",
                ("PackagedNormalize",),
            ).fetchall()
        self.assertEqual([row[0] for row in rows], [1, 2])
        self.assertEqual(json.loads(rows[0][1])["name"], "PACKAGED-SYNTHETIC-MARKER")
        self.assertEqual(rows[0][1], rows[1][1])

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

            def post_json(route, payload):
                request = urllib.request.Request(
                    base + route,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "Origin": base},
                    method="POST",
                )
                with opener.open(request, timeout=2) as response:
                    return json.loads(response.read().decode("utf-8"))

            task = "이 CSV를 로컬 SQLite에 저장해줘"
            preview = post_json("/api/preview", {"task": task, "csv_path": "contacts.csv"})
            self.assertEqual(preview["workflow"], "csv_to_sqlite")
            self.assertTrue(preview["requires_approval"])
            result = post_json("/api/run", {
                "task": task, "csv_path": "contacts.csv", "preview_id": preview["preview_id"],
                "approve_writes": True,
            })
            self.assertEqual(result["status"]["status"], "completed")
            self.assertEqual(result["result"]["imported_rows"], 1)
            self.assertNotIn("Fixture", json.dumps(result))
            with closing(sqlite3.connect(business)) as con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 1)
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
