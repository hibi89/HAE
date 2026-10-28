"""Local synthetic evidence for the owner's SQLite runtime backup contract."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import sqlite3
from sqlite_test_utils import sqlite_connection
import subprocess
import sys
import tempfile
import time
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

    def test_process_exit_during_staging_keeps_source_and_retry_safe(self):
        source_hash = _sha(self.state)
        destination = self.root / 'after-crash.sqlite'
        marker = self.root / 'backup-paused'
        child = r'''import sys, time
from pathlib import Path
import sqlite3
import lightning_azent.state_backup as state_backup
source, destination, marker = map(Path, sys.argv[1:])
real_connect = sqlite3.connect
class PausedConnection:
    def __init__(self, connection): self.connection = connection
    def backup(self, target, **kwargs):
        marker.write_text("ready", encoding="ascii")
        time.sleep(60)
        return self.connection.backup(target, **kwargs)
    def __getattr__(self, name): return getattr(self.connection, name)
state_backup.sqlite3.connect = lambda *args, **kwargs: PausedConnection(real_connect(*args, **kwargs))
state_backup.backup_runtime_state(source, destination)
'''
        process = subprocess.Popen(
            [sys.executable, '-B', '-c', child,
             str(self.state), str(destination), str(marker)],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1])},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and not marker.exists():
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    self.fail(f'backup child exited before staging: {stdout!r} {stderr!r}')
                time.sleep(0.02)
            self.assertTrue(marker.exists(), 'backup child did not reach staged SQLite copy')
            self.assertEqual(len(list(self.root.glob('.axflow-state-*.part'))), 1)
            self.assertFalse(destination.exists(), 'incomplete backup was published')
            process.terminate()
            process.wait(timeout=5)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()

        self.assertEqual(_sha(self.state), source_hash)
        self.assertFalse(destination.exists())
        # A hard process exit leaves only its private, unpublished staging
        # file. A fresh backup must publish a new verified artifact safely.
        result = backup_runtime_state(self.state, destination)
        self.assertEqual(result['sqlite_integrity'], 'ok')
        self.assertEqual(_sha(self.state), source_hash)
        with sqlite_connection(destination) as connection:
            self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(connection.execute('SELECT run_id FROM runs').fetchall(), [('Synthetic1',)])


if __name__ == '__main__':
    unittest.main()
