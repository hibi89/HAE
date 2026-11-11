"""Synthetic offline owner-asset binding vs a real loopback protocol responder."""
from __future__ import annotations

from contextlib import closing
import json
from urllib.request import urlopen
import copy
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from axflow.asset_attestation import (
    AssetAttestationError, attest_synthetic_dbvora_asset,
)
from axflow.dbvora_client import DbvoraClient
from axflow.engine import PlanError
from axflow.web import create_server
from test_hae_la_dbvora_asset_e2e import _ProtocolFixture, _contract_from_real_synthetic_sqlite


class SyntheticAssetAttestationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hae-synthetic-asset-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "selected.sqlite"
        with closing(sqlite3.connect(self.db)) as con, con:
            con.executescript("""
                PRAGMA foreign_keys=ON;
                CREATE TABLE parent (id INTEGER PRIMARY KEY, label TEXT NOT NULL);
                CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id));
                INSERT INTO parent VALUES (1,'PRIVATE_SYNTHETIC_ROW');
                INSERT INTO child VALUES (10,1);
            """)
        self.provider = _ProtocolFixture()
        self.provider.inventory = _contract_from_real_synthetic_sqlite(self.db)
        self.thread = threading.Thread(target=self.provider.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_provider)
        self.client = DbvoraClient("http://127.0.0.1:" + str(self.provider.server_port))
        self.sha_before = hashlib.sha256(self.db.read_bytes()).hexdigest()

    def stop_provider(self):
        self.provider.shutdown()
        self.thread.join(timeout=3)
        self.provider.server_close()

    def check_unchanged(self):
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), self.sha_before)

    def _serve_hae(self, *, linked=True, approved=True):
        inputs = self.root / "csv-input"
        inputs.mkdir(exist_ok=True)
        server = create_server(
            inputs, self.root / "runtime.sqlite", self.root / "business.sqlite",
            port=0, dbvora_url=self.client.base_url,
            dbvora_asset_source=self.db if linked else None,
            synthetic_asset_allowed=approved,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 3)
        self.addCleanup(server.shutdown)
        return "http://127.0.0.1:" + str(server.server_port)

    def test_hae_opt_in_asset_api_checks_real_source_against_loopback(self):
        origin = self._serve_hae()
        with urlopen(origin + "/api/dbvora-asset", timeout=5) as response:
            receipt = json.load(response)
        self.assertTrue(receipt["available"])
        self.assertTrue(receipt["provider_protocol_verified"])
        self.assertEqual(receipt["source_sha256"], self.sha_before)
        self.assertNotIn(str(self.db), json.dumps(receipt))
        self.assertNotIn("PRIVATE_SYNTHETIC_ROW", json.dumps(receipt))
        self.assertFalse((self.root / "runtime.sqlite").exists())
        self.assertFalse((self.root / "business.sqlite").exists())
        self.check_unchanged()

    def test_hae_asset_api_refuses_wrong_remote_asset(self):
        origin = self._serve_hae()
        self.provider.inventory["db_id"] = "0" * 24
        with urlopen(origin + "/api/dbvora-asset", timeout=5) as response:
            payload = json.load(response)
        self.assertEqual(payload, {
            "available": False, "error_code": "ASSET_ATTESTATION_HOLD",
            "release_gate": "HOLD",
        })
        self.check_unchanged()

    def test_hae_asset_endpoint_not_linked_by_default(self):
        origin = self._serve_hae(linked=False)
        with urlopen(origin + "/api/dbvora-asset", timeout=5) as response:
            payload = json.load(response)
        self.assertEqual(payload["error_code"], "NOT_LINKED")
        self.assertEqual(self.provider.requests, [])
        self.check_unchanged()

    def test_hae_source_link_rejects_missing_explicit_synthetic_gate(self):
        with self.assertRaises(PlanError):
            self._serve_hae(approved=False)
        self.assertEqual(self.provider.requests, [])

    def test_owner_approved_exact_schema_and_fk_attested_without_rows(self):
        receipt = attest_synthetic_dbvora_asset(self.db, self.client, synthetic=True)
        self.assertTrue(receipt["provider_protocol_verified"])
        self.assertEqual(receipt["table_count"], 2)
        self.assertEqual(receipt["foreign_key_count"], 1)
        self.assertEqual(receipt["source_sha256"], self.sha_before)
        self.assertEqual(receipt["release_gate"], "HOLD")
        self.assertFalse(receipt["dbvora_process_identity_verified"])
        self.assertFalse(receipt["customer_ready"])
        self.assertNotIn("PRIVATE_SYNTHETIC_ROW", str(receipt))
        self.assertNotIn(str(self.root), str(receipt))
        self.assertNotIn("parent", str(receipt))
        self.assertEqual(self.provider.requests, [("GET", "/health"), ("GET", "/api/inventory")])
        self.check_unchanged()

    def test_missing_consent_rejected_without_network(self):
        with self.assertRaises(AssetAttestationError):
            attest_synthetic_dbvora_asset(self.db, self.client)
        with self.assertRaises(AssetAttestationError):
            attest_synthetic_dbvora_asset(self.db, self.client, synthetic=1)
        self.assertEqual(self.provider.requests, [])
        self.check_unchanged()

    def test_wrong_asset_id_is_refused_not_silently_relinked(self):
        self.provider.inventory["db_id"] = "0" * 24
        with self.assertRaises(AssetAttestationError):
            attest_synthetic_dbvora_asset(self.db, self.client, synthetic=True)
        self.check_unchanged()

    def test_wrong_size_scope_refused(self):
        self.provider.inventory["size_scope"] = "unknown"
        with self.assertRaises(AssetAttestationError):
            attest_synthetic_dbvora_asset(self.db, self.client, synthetic=True)
        self.check_unchanged()

    def test_changed_relationship_map_refused(self):
        self.provider.inventory["relationships"][0]["to_table"] = "unrelated"
        with self.assertRaises(AssetAttestationError):
            attest_synthetic_dbvora_asset(self.db, self.client, synthetic=True)
        self.check_unchanged()

    def test_missing_provenance_refused(self):
        self.provider.inventory["provenance"]["tables"] = "unknown"
        with self.assertRaises(AssetAttestationError):
            attest_synthetic_dbvora_asset(self.db, self.client, synthetic=True)
        self.check_unchanged()

    def test_changed_size_refused(self):
        self.provider.inventory["size_bytes"] += 4096
        with self.assertRaises(AssetAttestationError):
            attest_synthetic_dbvora_asset(self.db, self.client, synthetic=True)
        self.check_unchanged()

    def test_table_column_and_fk_swaps_refused(self):
        initial = copy.deepcopy(self.provider.inventory)
        for change in ("table", "column", "fk"):
            with self.subTest(change=change):
                self.provider.inventory = copy.deepcopy(initial)
                tables = self.provider.inventory["tables"]
                if change == "table":
                    tables[0]["name"] = "unexpected"
                elif change == "column":
                    tables[0]["columns"][0]["name"] = "tampered"
                else:
                    with_key = next(t for t in tables if t["foreign_keys"])
                    with_key["foreign_keys"][0]["to_table"] = "wrong"
                with self.assertRaises(AssetAttestationError):
                    attest_synthetic_dbvora_asset(self.db, self.client, synthetic=True)
        self.check_unchanged()

    def test_unhealthy_provider_refused_no_inventory_fetch(self):
        self.provider.healthy = False
        with self.assertRaises(AssetAttestationError):
            attest_synthetic_dbvora_asset(self.db, self.client, synthetic=True)
        self.assertEqual(self.provider.requests, [("GET", "/health")])
        self.check_unchanged()

    def test_changed_source_during_provider_get_refused(self):
        valid = copy.deepcopy(self.provider.inventory)
        def change_then_reply():
            with closing(sqlite3.connect(self.db)) as con, con:
                con.execute("UPDATE parent SET label='MUTATED_SYNTHETIC' WHERE id=1")
            return {"available": True, **valid}
        with patch.object(self.client, "fetch_inventory", side_effect=change_then_reply):
            with self.assertRaises(AssetAttestationError):
                attest_synthetic_dbvora_asset(self.db, self.client, synthetic=True)
        self.assertEqual(self.provider.requests, [])

    def test_source_symlink_refused_before_network(self):
        alias = self.root / "alias.sqlite"
        try:
            alias.symlink_to(self.db)
        except (OSError, NotImplementedError):
            self.skipTest("symlink unavailable on this OS")
        with self.assertRaises(AssetAttestationError):
            attest_synthetic_dbvora_asset(alias, self.client, synthetic=True)
        self.assertEqual(self.provider.requests, [])
        self.check_unchanged()


if __name__ == "__main__":
    unittest.main()
