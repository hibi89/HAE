"""Synthetic-only business SQLite portability test gates for HAE."""
from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from axflow.business_state_backup import (
    BusinessBackupError,
    backup_business_state,
    inspect_business_state,
    restore_business_state,
    restore_business_state_pinned,
)


class BusinessDataPortabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hae-business-synthetic-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "business.sqlite"
        with closing(sqlite3.connect(self.source)) as con, con:
            con.execute("CREATE TABLE records(run_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL)")
            con.execute("CREATE TABLE csv_records(run_id TEXT, row_idx INTEGER, amount INTEGER)")
            con.execute("INSERT INTO records VALUES('r1', '{\"PRIVATE_CLIENT\":21}')")
            con.execute("INSERT INTO csv_records VALUES('r1', 1, 321)")
        self.original = self.source.read_bytes()

    def test_inspection_no_private_rows_or_path(self):
        receipt = inspect_business_state(self.source)
        self.assertEqual(receipt["status"], "VERIFIED_OFFLINE_SOURCE")
        self.assertEqual(receipt["table_count"], 2)
        self.assertEqual(receipt["sqlite_integrity"], "ok")
        self.assertNotIn("PRIVATE_CLIENT", str(receipt))
        self.assertNotIn(str(self.root), str(receipt))
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_backup_and_sha_pinned_restore_new_file(self):
        copy, target = self.root / "backup.sqlite", self.root / "restored.sqlite"
        evidence = backup_business_state(self.source, copy)
        self.assertTrue(evidence["source_unchanged"])
        self.assertEqual(evidence["artifact_sha256"], hashlib.sha256(copy.read_bytes()).hexdigest())
        result = restore_business_state_pinned(copy, target, evidence["artifact_sha256"])
        self.assertEqual(result["sqlite_integrity"], "ok")
        with closing(sqlite3.connect(target)) as con:
            self.assertEqual(con.execute("SELECT amount FROM csv_records").fetchone()[0], 321)
            self.assertEqual(con.execute("SELECT payload_json FROM records").fetchone()[0],
                             '{"PRIVATE_CLIENT":21}')
        self.assertEqual(self.original, self.source.read_bytes())

    def test_existing_target_cannot_be_overwritten(self):
        target = self.root / "protected.sqlite"
        target.write_bytes(b"DO_NOT_CHANGE")
        with self.assertRaises(BusinessBackupError):
            backup_business_state(self.source, target)
        self.assertEqual(target.read_bytes(), b"DO_NOT_CHANGE")

    def test_restore_rejects_existing_original_file(self):
        backup = self.root / "copy.sqlite"
        evidence = backup_business_state(self.source, backup)
        with self.assertRaises(BusinessBackupError):
            restore_business_state_pinned(backup, self.source, evidence["artifact_sha256"])
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_wrong_sha_stops_before_restoration(self):
        backup = self.root / "backup.sqlite"
        backup_business_state(self.source, backup)
        target = self.root / "should-not-exist.sqlite"
        with self.assertRaises(BusinessBackupError):
            restore_business_state_pinned(backup, target, "0" * 64)
        self.assertFalse(target.exists())

    def test_bad_sha_format_stops(self):
        with self.assertRaises(BusinessBackupError):
            restore_business_state_pinned(self.source, self.root / "bad.sqlite", "INVALID")
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_corrupt_db_is_rejected(self):
        corrupted = self.root / "corrupt.sqlite"
        corrupted.write_bytes(b"not a sqlite file")
        with self.assertRaises(BusinessBackupError):
            inspect_business_state(corrupted)

    def test_empty_db_without_business_tables_is_rejected(self):
        empty = self.root / "empty.sqlite"
        sqlite3.connect(empty).close()
        with self.assertRaises(BusinessBackupError):
            inspect_business_state(empty)

    def test_view_and_trigger_are_unsupported(self):
        with closing(sqlite3.connect(self.source)) as con, con:
            con.execute("CREATE VIEW human_view AS SELECT * FROM records")
        with self.assertRaises(BusinessBackupError):
            inspect_business_state(self.source)

    def test_invalid_foreign_keys_are_rejected(self):
        bad = self.root / "bad-keys.sqlite"
        with closing(sqlite3.connect(bad)) as con, con:
            con.execute("PRAGMA foreign_keys=OFF")
            con.execute("CREATE TABLE parents(id INTEGER PRIMARY KEY)")
            con.execute("CREATE TABLE children(id INTEGER, parent_id INTEGER REFERENCES parents(id))")
            con.execute("INSERT INTO children VALUES(1,999)")
        with self.assertRaises(BusinessBackupError):
            inspect_business_state(bad)

    def test_live_wal_mode_is_not_supported(self):
        with closing(sqlite3.connect(self.source)) as con, con:
            con.execute("PRAGMA journal_mode=WAL")
        with self.assertRaises(BusinessBackupError):
            inspect_business_state(self.source)

    def test_symlink_cannot_be_used_as_source_or_target(self):
        linked = self.root / "linked.sqlite"
        try:
            linked.symlink_to(self.source)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on this host")
        with self.assertRaises(BusinessBackupError):
            inspect_business_state(linked)
        with self.assertRaises(BusinessBackupError):
            backup_business_state(self.source, linked)

    def test_concurrent_target_file_is_preserved(self):
        if os.name == "nt":
            self.skipTest("POSIX hardlink atomic-publish fixture")
        from axflow import business_state_backup as module
        target = self.root / "raced.sqlite"
        original = module.os.link
        def external_peer(src, dst):
            Path(dst).write_bytes(b"PEER_DATA")
            return original(src, dst)
        with patch.object(module.os, "link", side_effect=external_peer):
            with self.assertRaises(BusinessBackupError):
                backup_business_state(self.source, target)
        self.assertEqual(target.read_bytes(), b"PEER_DATA")

    def test_unpinned_restore_not_invoked_by_pinned_api(self):
        backup = self.root / "backup.sqlite"
        proof = backup_business_state(self.source, backup)
        fresh = self.root / "restore.sqlite"
        with patch("axflow.business_state_backup.restore_business_state", wraps=restore_business_state) as called:
            restore_business_state_pinned(backup, fresh, proof["artifact_sha256"])
            self.assertEqual(called.call_count, 1)

    def test_same_source_target_is_rejected(self):
        with self.assertRaises(BusinessBackupError):
            backup_business_state(self.source, self.source)

    def test_no_public_release_flag_in_receipt(self):
        evidence = inspect_business_state(self.source)
        self.assertFalse(evidence["customer_ready"])
        self.assertEqual(evidence["release_gate"], "HOLD")


if __name__ == "__main__":
    unittest.main()
