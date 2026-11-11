"""Synthetic HAE HTTP registry lifecycle (no customer data or external network)."""
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

from axflow.asset_registry import initialize_synthetic_registry, read_synthetic_registry
from axflow.engine import PlanError
from axflow.web import create_server
from test_hae_la_dbvora_asset_e2e import _ProtocolFixture, _contract_from_real_synthetic_sqlite


class RegistryHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hae-owner-registry-http-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "source.db"
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("CREATE TABLE rows (id INTEGER PRIMARY KEY, label TEXT NOT NULL)")
            con.execute("INSERT INTO rows VALUES (1,'PRIVATE_SYNTHETIC_ROW')")
        self.sha = hashlib.sha256(self.db.read_bytes()).hexdigest()
        self.registry = self.root / "registry.db"
        initialize_synthetic_registry(self.registry, synthetic=True, acknowledge_new_file=True)
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.provider = _ProtocolFixture()
        self.provider.inventory = _contract_from_real_synthetic_sqlite(self.db)
        self.provider_thread = threading.Thread(target=self.provider.serve_forever, daemon=True)
        self.provider_thread.start()
        self.addCleanup(self._close, self.provider, self.provider_thread)
        self.dbvora_url = "http://127.0.0.1:" + str(self.provider.server_port)
        self.server = self._serve()

    @staticmethod
    def _close(server, thread):
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    def _serve(self, *, registry=True):
        server = create_server(
            self.inputs, self.root / "run.db", self.root / "business.db",
            port=0, dbvora_url=self.dbvora_url, dbvora_asset_source=self.db,
            asset_registry_path=self.registry if registry else None,
            synthetic_asset_allowed=True,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self._close, server, thread)
        return "http://127.0.0.1:" + str(server.server_port)

    def request(self, endpoint, *, payload=None, origin=True, external=False):
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        if body is not None and origin:
            headers["Origin"] = "https://attacker.example" if external else self.server
        req = Request(self.server + endpoint, data=body, headers=headers,
                      method="POST" if payload is not None else "GET")
        try:
            with urlopen(req, timeout=7) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            with error:
                return error.code, json.load(error)

    def approve(self, *, sha=None, consent=True):
        return self.request("/api/asset-registry/register", payload={
            "approve_registry_write": consent,
            "expected_sha256": sha if sha is not None else self.sha,
        })

    def test_register_restart_and_idempotent_replay(self):
        code, data = self.request("/api/asset-registry")
        self.assertEqual(code, 200)
        self.assertEqual(data["asset_count"], 0)
        self.assertEqual(self.provider.requests, [])
        code, data = self.approve()
        self.assertEqual(code, 200, data)
        self.assertEqual(data["status"], "REGISTERED")
        self.assertEqual(data["source_sha256"], self.sha)
        self.assertNotIn("PRIVATE_SYNTHETIC_ROW", json.dumps(data))
        self.assertNotIn(str(self.root), json.dumps(data))
        saved = self.registry.read_bytes()
        self.assertEqual(self.approve()[1]["status"], "ALREADY_REGISTERED")
        self.assertEqual(saved, self.registry.read_bytes())
        restored = self._serve()
        with urlopen(restored + "/api/asset-registry", timeout=7) as response:
            status = json.load(response)
        self.assertEqual(status["asset_count"], 1)
        self.assertEqual(status["assets"][0]["source_sha256"], self.sha)
        self.assertFalse((self.root / "run.db").exists())
        self.assertFalse((self.root / "business.db").exists())

    def test_rejects_missing_consent_no_network_or_write(self):
        before = self.registry.read_bytes()
        code, _ = self.approve(consent=False)
        self.assertEqual(code, 403)
        self.assertEqual(self.provider.requests, [])
        self.assertEqual(self.registry.read_bytes(), before)

    def test_rejects_cross_origin_and_missing_origin(self):
        before = self.registry.read_bytes()
        body = {"approve_registry_write": True, "expected_sha256": self.sha}
        self.assertEqual(self.request("/api/asset-registry/register",
                                      payload=body, origin=False)[0], 403)
        self.assertEqual(self.request("/api/asset-registry/register",
                                      payload=body, external=True)[0], 403)
        self.assertEqual(self.provider.requests, [])
        self.assertEqual(self.registry.read_bytes(), before)

    def test_rejects_forged_or_stale_sha(self):
        self.assertEqual(self.approve(sha="0"*64)[0], 409)
        self.assertEqual(self.approve(sha="BAD")[0], 400)
        self.assertEqual(read_synthetic_registry(self.registry, synthetic=True)["asset_count"], 0)

    def test_source_drift_denies_overwrite(self):
        self.assertEqual(self.approve()[0], 200)
        before = self.registry.read_bytes()
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("UPDATE rows SET label='CHANGED' WHERE id=1")
        self.assertEqual(self.approve()[0], 409)
        self.assertEqual(self.registry.read_bytes(), before)

    def test_remote_health_failure_blocks_registration(self):
        before = self.registry.read_bytes()
        self.provider.healthy = False
        self.assertEqual(self.approve()[0], 409)
        self.assertEqual(self.registry.read_bytes(), before)

    def test_unconfigured_registry_read_does_not_create(self):
        without = self._serve(registry=False)
        with urlopen(without + "/api/asset-registry", timeout=7) as response:
            status = json.load(response)
        self.assertEqual(status["error_code"], "NOT_CONFIGURED")

    def test_registry_missing_or_aliasing_runtime_refused(self):
        self.registry.unlink()
        with self.assertRaises(PlanError):
            self._serve()
        initialize_synthetic_registry(self.registry, synthetic=True, acknowledge_new_file=True)
        with self.assertRaises(PlanError):
            create_server(
                self.inputs, self.registry, self.root / "business.db",
                port=0, dbvora_url=self.dbvora_url, dbvora_asset_source=self.db,
                asset_registry_path=self.registry, synthetic_asset_allowed=True,
            )


if __name__ == "__main__":
    unittest.main()
