"""Owner-initiated, durable HAE synthetic asset registry acceptance."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest

from axflow.asset_registry import (
    AssetRegistryError, initialize_synthetic_registry, read_synthetic_registry,
    register_synthetic_asset, verify_registered_synthetic_asset,
)
from axflow.dbvora_client import DbvoraClient
from test_hae_la_dbvora_asset_e2e import _ProtocolFixture, _contract_from_real_synthetic_sqlite


class SyntheticRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hae-asset-registry-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "synthetic.sqlite"
        with closing(sqlite3.connect(self.source)) as con, con:
            con.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, note TEXT NOT NULL)")
            con.execute("INSERT INTO accounts VALUES(1, 'PRIVATE_SYNTHETIC_ROW')")
        self.source_bytes = self.source.read_bytes()
        self.registry = self.root / "registry.sqlite"
        self.provider = _ProtocolFixture()
        self.provider.inventory = _contract_from_real_synthetic_sqlite(self.source)
        self.thread = threading.Thread(target=self.provider.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._close_provider)
        self.client = DbvoraClient("http://127.0.0.1:" + str(self.provider.server_port))

    def _close_provider(self):
        self.provider.shutdown()
        self.thread.join(timeout=3)
        self.provider.server_close()

    def init(self):
        return initialize_synthetic_registry(
            self.registry, synthetic=True, acknowledge_new_file=True)

    def register(self):
        return register_synthetic_asset(
            self.registry, self.source, self.client,
            synthetic=True, acknowledge_owner=True)

    def verify(self):
        return verify_registered_synthetic_asset(
            self.registry, self.source, self.client, synthetic=True)

    def check_private(self, result):
        text = json.dumps(result, sort_keys=True)
        self.assertNotIn("PRIVATE_SYNTHETIC_ROW", text)
        self.assertNotIn(str(self.root), text)
        self.assertNotIn("accounts", text)

    def test_owner_init_registration_and_reverification_after_restart(self):
        created = self.init()
        self.assertEqual(created["asset_count"], 0)
        registered = self.register()
        self.assertEqual(registered["status"], "REGISTERED")
        self.assertEqual(registered["table_count"], 1)
        self.assertEqual(registered["provider"], "dbvora")
        self.check_private(registered)
        before = self.registry.read_bytes()
        self.assertEqual(self.register()["status"], "ALREADY_REGISTERED")
        self.assertEqual(before, self.registry.read_bytes())
        self.assertEqual(read_synthetic_registry(self.registry, synthetic=True)["asset_count"], 1)
        checked = self.verify()
        self.assertEqual(checked["status"], "PINNED_SOURCE_REVERIFIED")
        self.assertFalse(checked["dbvora_process_identity_verified"])
        self.assertFalse(checked["customer_ready"])
        self.assertEqual(self.registry.read_bytes(), before)
        self.assertEqual(self.source.read_bytes(), self.source_bytes)
        self.check_private(checked)
        with closing(sqlite3.connect(self.registry)) as conn:
            saved = str(conn.execute("SELECT * FROM asset_records").fetchone())
            self.assertNotIn(str(self.root), saved)
            self.assertNotIn("PRIVATE_SYNTHETIC_ROW", saved)

    def test_init_refuses_missing_ack_without_creating_file(self):
        with self.assertRaises(AssetRegistryError):
            initialize_synthetic_registry(self.registry, synthetic=True)
        self.assertFalse(self.registry.exists())

    def test_init_refuses_existing_file_without_overwrite(self):
        self.registry.write_bytes(b"KEEP_ORIGINAL")
        with self.assertRaises(AssetRegistryError):
            self.init()
        self.assertEqual(self.registry.read_bytes(), b"KEEP_ORIGINAL")

    def test_missing_owner_ack_has_no_network_or_registry_write(self):
        self.init()
        before = self.registry.read_bytes()
        with self.assertRaises(AssetRegistryError):
            register_synthetic_asset(
                self.registry, self.source, self.client, synthetic=True)
        self.assertEqual(self.provider.requests, [])
        self.assertEqual(self.registry.read_bytes(), before)

    def test_verify_unknown_asset_has_no_provider_call(self):
        self.init()
        with self.assertRaises(AssetRegistryError):
            self.verify()
        self.assertEqual(self.provider.requests, [])
        self.assertEqual(read_synthetic_registry(self.registry, synthetic=True)["asset_count"], 0)

    def test_provider_offline_does_not_persist_false_success(self):
        self.init()
        self.register()
        before = self.registry.read_bytes()
        self.provider.healthy = False
        with self.assertRaises(AssetRegistryError):
            self.verify()
        self.assertEqual(self.registry.read_bytes(), before)

    def test_source_changed_after_registration_fails_before_network(self):
        self.init()
        self.register()
        self.provider.requests.clear()
        with closing(sqlite3.connect(self.source)) as con, con:
            con.execute("UPDATE accounts SET note='ALTERED' WHERE id=1")
        with self.assertRaises(AssetRegistryError):
            self.verify()
        self.assertEqual(self.provider.requests, [])

    def test_source_change_cannot_silently_rebind_approval(self):
        self.init()
        self.register()
        saved = self.registry.read_bytes()
        with closing(sqlite3.connect(self.source)) as con, con:
            con.execute("UPDATE accounts SET note='ALTERED' WHERE id=1")
        self.provider.inventory = _contract_from_real_synthetic_sqlite(self.source)
        with self.assertRaises(AssetRegistryError):
            self.register()
        self.assertEqual(self.registry.read_bytes(), saved)

    def test_registry_source_same_path_cannot_be_used(self):
        self.init()
        with self.assertRaises(AssetRegistryError):
            register_synthetic_asset(
                self.registry, self.registry, self.client,
                synthetic=True, acknowledge_owner=True)
        self.assertEqual(self.provider.requests, [])

    def test_wrong_registry_schema_rejected_before_provider(self):
        self.registry.write_bytes(b"not a valid registry")
        with self.assertRaises(AssetRegistryError):
            self.register()
        self.assertEqual(self.provider.requests, [])

    def test_registry_symlink_not_followed(self):
        self.init()
        alias = self.root / "registry-alias.sqlite"
        try:
            alias.symlink_to(self.registry)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        with self.assertRaises(AssetRegistryError):
            read_synthetic_registry(alias, synthetic=True)

    def test_cli_roundtrip_init_list_register_verify(self):
        def run(*args):
            return subprocess.run(
                [sys.executable, "-m", "axflow.asset_registry_cli", *args,
                 "--synthetic"], capture_output=True, text=True, timeout=12)
        init = run("init", "--registry", str(self.registry), "--ack-new-file")
        self.assertEqual(init.returncode, 0, init.stderr)
        ls = run("list", "--registry", str(self.registry))
        self.assertEqual(json.loads(ls.stdout)["asset_count"], 0)
        registered = run("register", "--registry", str(self.registry),
                         "--source", str(self.source), "--dbvora-url", self.client.base_url,
                         "--ack-owner")
        self.assertEqual(registered.returncode, 0, registered.stderr)
        verified = run("verify", "--registry", str(self.registry),
                       "--source", str(self.source), "--dbvora-url", self.client.base_url)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertEqual(json.loads(verified.stdout)["status"], "PINNED_SOURCE_REVERIFIED")
        self.check_private(json.loads(verified.stdout))
        self.assertEqual(self.source.read_bytes(), self.source_bytes)

    def test_cli_missing_opt_in_never_leaks_file_paths(self):
        proc = subprocess.run(
            [sys.executable, "-m", "axflow.asset_registry_cli", "init",
             "--registry", str(self.registry)],
            capture_output=True, text=True, timeout=12)
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn(str(self.registry), proc.stderr)
        self.assertFalse(self.registry.exists())


if __name__ == "__main__":
    unittest.main()
