"""Owner-reviewed HAE local workflow save/load HTTP acceptance (synthetic only)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from axflow.engine import PlanError
from axflow.workflow_catalog import initialize_workflow_catalog
from axflow.web import create_server


class WorkflowCatalogWebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hae-workflow-catalog-http-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.data = self.inputs / "data.csv"
        self.data.write_bytes(b"id,amount\n1,50\n2,500\n")
        self.catalog = self.root / "workflow-catalog.sqlite"
        initialize_workflow_catalog(
            self.catalog, synthetic=True, acknowledge_new_file=True,
        )
        self.task = "Import this CSV where amount > 100 into SQLite"
        self.serve()

    @staticmethod
    def _close(server, thread):
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    def serve(self, *, configured=True):
        server = create_server(
            self.inputs, self.root / "runtime.db", self.root / "business.db",
            port=0, workflow_catalog_path=self.catalog if configured else None,
            synthetic_asset_allowed=True,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self._close, server, thread)
        self.origin = "http://127.0.0.1:" + str(server.server_port)
        return self.origin

    def query(self, route, payload=None, *, origin=True, external=False):
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"} if data is not None else {}
        if data is not None and origin:
            headers["Origin"] = "https://attacker.example" if external else self.origin
        request = Request(self.origin + route, method="POST" if data is not None else "GET",
                          data=data, headers=headers)
        try:
            with urlopen(request, timeout=6) as response:
                return response.status, json.load(response)
        except HTTPError as exc:
            with exc:
                return exc.code, json.load(exc)

    def preview(self):
        code, data = self.query("/api/preview", {
            "task": self.task, "csv_path": "data.csv",
        })
        self.assertEqual(code, 200, data)
        self.assertFalse((self.root / "runtime.db").exists())
        self.assertFalse((self.root / "business.db").exists())
        return data

    def save(self, preview, *, approved=True):
        return self.query("/api/workflows/save", {
            "task": self.task, "csv_path": "data.csv",
            "preview_id": preview["preview_id"],
            "approve_workflow_save": approved,
        })

    def test_explicit_save_then_restart_load_never_runs_automatically(self):
        preview = self.preview()
        self.assertEqual(self.query("/api/workflows")[1]["recipe_count"], 0)
        self.assertEqual(self.save(preview, approved=False)[0], 403)
        code, result = self.save(preview)
        self.assertEqual(code, 200, result)
        self.assertEqual(result["status"], "SAVED")
        self.assertTrue(result["needs_new_preview"])
        self.assertEqual(self.save(preview)[1]["status"], "ALREADY_SAVED")
        code, listed = self.query("/api/workflows")
        self.assertEqual(code, 200)
        self.assertEqual(listed["recipe_count"], 1)
        self.assertNotIn("data.csv", json.dumps(listed))
        url = self.serve()
        with urlopen(url + "/api/workflows/load?recipe_id=" + result["recipe_id"],
                     timeout=6) as response:
            loaded = json.load(response)
        self.assertEqual(loaded["task"], self.task)
        self.assertEqual(loaded["csv_path"], "data.csv")
        self.assertFalse(loaded["write_approved"])
        self.assertTrue(loaded["needs_new_preview"])
        self.assertFalse((self.root / "runtime.db").exists())
        self.assertFalse((self.root / "business.db").exists())

    def test_source_mutation_refuses_reload_and_stale_preview_save(self):
        preview = self.preview()
        saved = self.save(preview)[1]
        self.data.write_bytes(b"id,amount\n1,999\n")
        code, result = self.query("/api/workflows/load?recipe_id=" + saved["recipe_id"])
        self.assertEqual(code, 409, result)
        self.assertEqual(self.save(preview)[0], 409)

    def test_cross_origin_save_refused_without_any_metadata_write(self):
        preview = self.preview()
        payload = {"task": self.task, "csv_path": "data.csv",
                   "preview_id": preview["preview_id"], "approve_workflow_save": True}
        self.assertEqual(self.query("/api/workflows/save", payload, origin=False)[0], 403)
        self.assertEqual(self.query("/api/workflows/save", payload, external=True)[0], 403)
        self.assertEqual(self.query("/api/workflows")[1]["recipe_count"], 0)

    def test_no_catalog_means_read_only_unconfigured_and_save_hold(self):
        self.serve(configured=False)
        status = self.query("/api/workflows")[1]
        self.assertEqual(status["error_code"], "NOT_CONFIGURED")
        # Preview remains local and safe without optional catalog.
        preview = self.preview()
        self.assertEqual(self.save(preview)[0], 409)

    def test_invalid_id_or_missing_catalog_refuses_without_creating_file(self):
        self.assertEqual(self.query("/api/workflows/load?recipe_id=invalid")[0], 400)
        self.catalog.unlink()
        with self.assertRaises(PlanError):
            self.serve()
        self.assertFalse(self.catalog.exists())


if __name__ == "__main__":
    unittest.main()
