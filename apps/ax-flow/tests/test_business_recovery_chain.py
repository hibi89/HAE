"""Synthetic-only SQLite recovery-chain and owner-consent regression."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from axflow.business_recovery_chain import (
    RecoveryChainError, verify_synthetic_restore_chain,
)
from axflow.business_state_backup import (
    backup_business_state, restore_business_state_pinned,
)


class SyntheticRecoveryChainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hae-recovery-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "owner.sqlite"
        self.backup = self.root / "owner-backup.sqlite"
        self.restored = self.root / "new-restored.sqlite"
        with closing(sqlite3.connect(self.source)) as con, con:
            con.executescript("""
                PRAGMA foreign_keys=ON;
                CREATE TABLE clients (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
                CREATE TABLE orders (id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL
                    REFERENCES clients(id), amount REAL);
                INSERT INTO clients VALUES (1, 'PRIVATE_CUSTOMER_SYNTHETIC');
                INSERT INTO orders VALUES (9, 1, 12.5);
            """)
        self.source_before = self.source.read_bytes()
        self.source_sha = hashlib.sha256(self.source_before).hexdigest()
        backup_receipt = backup_business_state(self.source, self.backup)
        self.backup_sha = backup_receipt["artifact_sha256"]
        restore_business_state_pinned(self.backup, self.restored, self.backup_sha)
        self.backup_before = self.backup.read_bytes()
        self.restored_before = self.restored.read_bytes()

    def verify(self, **kwargs):
        return verify_synthetic_restore_chain(
            kwargs.get("source", self.source),
            kwargs.get("backup", self.backup),
            kwargs.get("restored", self.restored),
            expected_source_sha256=kwargs.get("source_sha", self.source_sha),
            expected_backup_sha256=kwargs.get("backup_sha", self.backup_sha),
            synthetic=kwargs.get("synthetic", True),
        )

    def unchanged(self):
        self.assertEqual(self.source.read_bytes(), self.source_before)
        self.assertEqual(self.backup.read_bytes(), self.backup_before)
        self.assertEqual(self.restored.read_bytes(), self.restored_before)

    def test_backup_restore_verifies_sql_and_rows_without_exposing_them(self):
        receipt = self.verify()
        self.assertTrue(receipt["independent_restore_verified"])
        self.assertTrue(receipt["logical_schema_and_rows_equal"])
        self.assertTrue(receipt["all_three_sources_unchanged"])
        self.assertEqual(receipt["table_count"], 2)
        self.assertEqual(receipt["foreign_key_count"], 1)
        self.assertEqual(receipt["source_sha256"], self.source_sha)
        self.assertEqual(receipt["backup_sha256"], self.backup_sha)
        self.assertEqual(receipt["release_gate"], "HOLD")
        self.assertFalse(receipt["dbvora_real_process_verified"])
        self.assertFalse(receipt["customer_ready"])
        self.assertNotIn("PRIVATE_CUSTOMER_SYNTHETIC", json.dumps(receipt))
        self.assertNotIn(str(self.root), json.dumps(receipt))
        self.unchanged()

    def test_repeated_read_only_check_is_idempotent(self):
        self.assertEqual(self.verify(), self.verify())
        self.unchanged()

    def test_requires_explicit_synthetic_flag_and_pinned_shas(self):
        for changes in ({"synthetic": False}, {"synthetic": 1},
                        {"source_sha": "0" * 64}, {"backup_sha": "0" * 64},
                        {"source_sha": "NOT_SHA"}, {"backup_sha": ""}):
            with self.subTest(changes=changes), self.assertRaises(RecoveryChainError):
                self.verify(**changes)
        self.unchanged()

    def test_wrong_or_duplicate_source_paths_rejected(self):
        with self.assertRaises(RecoveryChainError):
            self.verify(backup=self.source)
        with self.assertRaises(RecoveryChainError):
            self.verify(restored=self.backup)
        with self.assertRaises(RecoveryChainError):
            self.verify(source=Path("relative.sqlite"))
        self.unchanged()

    def test_mutated_restored_row_rejected_even_when_schema_is_same(self):
        with closing(sqlite3.connect(self.restored)) as con, con:
            con.execute("UPDATE orders SET amount=99.5 WHERE id=9")
        with self.assertRaises(RecoveryChainError):
            self.verify()
        self.assertEqual(self.source.read_bytes(), self.source_before)
        self.assertEqual(self.backup.read_bytes(), self.backup_before)

    def test_mutated_backup_rejected_before_logical_validation(self):
        with closing(sqlite3.connect(self.backup)) as con, con:
            con.execute("INSERT INTO clients VALUES(2,'PRIVATE_AFTER')")
        with self.assertRaises(RecoveryChainError):
            self.verify()
        self.assertEqual(self.source.read_bytes(), self.source_before)

    def test_swapped_tables_schema_rejected(self):
        with closing(sqlite3.connect(self.restored)) as con, con:
            con.execute("CREATE TABLE extra(note TEXT)")
        with self.assertRaises(RecoveryChainError):
            self.verify()

    def test_symlinked_restore_is_not_trusted(self):
        alias = self.root / "alias.sqlite"
        try:
            alias.symlink_to(self.restored)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        with self.assertRaises(RecoveryChainError):
            self.verify(restored=alias)
        self.unchanged()

    def test_wal_sidecar_rejected(self):
        (self.root / "new-restored.sqlite-wal").write_bytes(b"untrusted")
        with self.assertRaises(RecoveryChainError):
            self.verify()

    def test_corrupt_restore_rejected(self):
        self.restored.write_bytes(b"not a sqlite file")
        with self.assertRaises(RecoveryChainError):
            self.verify()

    def test_source_change_during_digest_refused(self):
        from axflow import business_recovery_chain as module
        original_digest = module._logical_digest
        modified = {"done": False}
        def injected(path):
            result = original_digest(path)
            if path == self.backup and not modified["done"]:
                modified["done"] = True
                with closing(sqlite3.connect(self.source)) as con, con:
                    con.execute("INSERT INTO clients VALUES(55,'RACED')")
            return result
        with patch.object(module, "_logical_digest", side_effect=injected):
            with self.assertRaises(RecoveryChainError):
                self.verify()
        self.assertTrue(modified["done"])

    def test_cli_success_does_not_write_and_has_no_private_values(self):
        invocation = [
            sys.executable, "-m", "axflow.business_recovery_cli",
            "--source", str(self.source), "--backup", str(self.backup),
            "--restored", str(self.restored), "--source-sha256", self.source_sha,
            "--backup-sha256", self.backup_sha, "--synthetic",
        ]
        result = subprocess.run(invocation, capture_output=True, text=True, timeout=12)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["status"], "VERIFIED_SYNTHETIC_RESTORE_CHAIN")
        self.assertNotIn("PRIVATE_CUSTOMER", result.stdout + result.stderr)
        self.assertNotIn(str(self.root), result.stdout + result.stderr)
        self.unchanged()

    def test_cli_refuses_missing_opt_in_or_wrong_backup_sha_without_leak(self):
        invocation = [
            sys.executable, "-m", "axflow.business_recovery_cli",
            "--source", str(self.source), "--backup", str(self.backup),
            "--restored", str(self.restored), "--source-sha256", self.source_sha,
            "--backup-sha256", "0" * 64,
        ]
        for flags in ([], ["--synthetic"]):
            result = subprocess.run(invocation + flags, capture_output=True,
                                    text=True, timeout=12)
            self.assertEqual(result.returncode, 2)
            self.assertIn("HAE_SYNTHETIC_RESTORE_CHAIN_HOLD", result.stderr)
            self.assertNotIn(str(self.root), result.stderr)
            self.assertNotIn("PRIVATE_CUSTOMER", result.stdout + result.stderr)
        self.unchanged()


if __name__ == "__main__":
    unittest.main()
