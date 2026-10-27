"""Local synthetic evidence for the owner's SQLite runtime backup contract."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import sqlite3
from sqlite_test_utils import sqlite_connection
import tempfile
import unittest

from lightning_azent.state_backup import StateBackupError, backup_runtime_state, restore_runtime_state


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StateBackupAcceptanceTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.state = self.root / 'state.sqlite'
        with sqlite_connection(self.state) as conn:
            conn.execute('CREATE TABLE runs(run_id TEXT PRIMARY KEY, plan_hash TEXT, status TEXT)')
            conn.execute('CREATE TABLE steps(run_id TEXT, step_id TEXT, output_json TEXT)')
            conn.execute("INSERT INTO runs VALUES('Synthetic1', 'digest', 'completed')")
            conn.execute("INSERT INTO steps VALUES('Synthetic1', 'Step1', '{}')")

    def test_backup_restore_receipts_and_original_sha(self):
        old = _sha(self.state)
        backup, restored = self.root/'backup.sqlite', self.root/'restored.sqlite'
        result = backup_runtime_state(self.state, backup)
        self.assertTrue(result['source_unchanged'])
        self.assertEqual(result['sqlite_integrity'], 'ok')
        self.assertEqual(result['source_sha256'], old)
        self.assertEqual(_sha(self.state), old)
        result2 = restore_runtime_state(backup, restored)
        self.assertEqual(result2['sqlite_integrity'], 'ok')
        with sqlite_connection(restored) as c:
            self.assertEqual(c.execute('SELECT run_id, status FROM runs').fetchall(), [('Synthetic1','completed')])
            self.assertEqual(c.execute('SELECT COUNT(*) FROM steps').fetchone()[0], 1)

    def test_existing_destination_never_overwritten(self):
        existing=self.root/'backup.sqlite'
        existing.write_bytes(b'unrelated-file')
        with self.assertRaises(StateBackupError):
            backup_runtime_state(self.state, existing)
        self.assertEqual(existing.read_bytes(),b'unrelated-file')

    def test_identical_path_rejected_without_change(self):
        before=_sha(self.state)
        with self.assertRaises(StateBackupError):
            backup_runtime_state(self.state,self.state)
        self.assertEqual(_sha(self.state),before)

    def test_nonledger_sqlite_rejected_and_no_orphan_temp_file(self):
        other=self.root/'nonledger.sqlite'
        with sqlite_connection(other) as c:
            c.execute('CREATE TABLE arbitrary(x INTEGER)')
        with self.assertRaises(StateBackupError):
            backup_runtime_state(other,self.root/'should-not-exist.sqlite')
        self.assertEqual(list(self.root.glob('.axflow-state-*.part')),[])
        self.assertFalse((self.root/'should-not-exist.sqlite').exists())

    def test_corrupted_database_rejected(self):
        damaged=self.root/'damaged.sqlite'
        damaged.write_bytes(b'not a sqlite database')
        with self.assertRaises(StateBackupError):
            restore_runtime_state(damaged,self.root/'refuse.sqlite')
        self.assertFalse((self.root/'refuse.sqlite').exists())
        self.assertEqual(list(self.root.glob('.axflow-state-*.part')),[])

    def test_wal_mode_backups_committed_receipts(self):
        connection=sqlite3.connect(self.state)
        try:
            connection.execute('PRAGMA journal_mode=WAL')
            connection.execute("INSERT INTO runs VALUES('WAL2', 'new', 'completed')")
            connection.commit()
            backed=self.root/'wal-backup.sqlite'
            result=backup_runtime_state(self.state,backed)
            self.assertEqual(result['sqlite_integrity'],'ok')
            with sqlite_connection(backed) as copy:
                self.assertEqual(copy.execute('SELECT COUNT(*) FROM runs').fetchone()[0],2)
        finally:
            connection.close()

    def test_concurrent_publish_to_same_destination_has_one_winner(self):
        target=self.root/'race.sqlite'
        def go():
            try:
                backup_runtime_state(self.state,target)
                return 'success'
            except StateBackupError:
                return 'rejected'
        with ThreadPoolExecutor(max_workers=2) as pool:
            f1=pool.submit(go);f2=pool.submit(go)
            self.assertEqual(sorted([f1.result(timeout=10),f2.result(timeout=10)]),['rejected','success'])
        with sqlite_connection(target) as c:
            self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertEqual(list(self.root.glob('.axflow-state-*.part')),[])


if __name__ == '__main__':
    unittest.main()
