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

    def test_hardlinked_destination_lock_fails_closed(self):
        target = self.root / 'locked-backup.sqlite'
        protected = self.root / 'protected-target.txt'
        protected.write_bytes(b'preserve this file')
        key = hashlib.sha256(os.fsencode(os.path.normcase(str(target.resolve())))).hexdigest()[:24]
        lock_path = self.root / f'.axflow-state-{key}.lock'
        try:
            os.link(protected, lock_path)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f'hard links are unavailable in this Windows environment: {error}')
        with self.assertRaises(StateBackupError):
            backup_runtime_state(self.state, target)
        self.assertEqual(protected.read_bytes(), b'preserve this file')
        self.assertFalse(target.exists())

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

    def test_concurrent_process_publish_to_same_destination_has_one_winner(self):
        target = self.root / 'process-race.sqlite'
        start = self.root / 'process-race-start'
        child = r'''import sys, time
from pathlib import Path
import sqlite3
import lightning_azent.state_backup as state_backup
from lightning_azent.state_backup import StateBackupError, backup_runtime_state
source, target, start, ready = map(Path, sys.argv[1:])
real_connect = sqlite3.connect
class DelayedConnection:
    def __init__(self, connection): self.connection = connection
    def backup(self, destination, **kwargs):
        time.sleep(0.25)
        return self.connection.backup(getattr(destination, "connection", destination), **kwargs)
    def __getattr__(self, name): return getattr(self.connection, name)
state_backup.sqlite3.connect = lambda *args, **kwargs: DelayedConnection(real_connect(*args, **kwargs))
ready.write_text("ready", encoding="ascii")
while not start.exists(): time.sleep(0.01)
try:
    state_backup.backup_runtime_state(source, target)
except StateBackupError as error:
    print("rejected: " + str(error))
else:
    print("success")
'''
        environment = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
        processes = []
        ready_paths = [self.root / f'process-race-ready-{index}' for index in range(2)]
        for ready in ready_paths:
            processes.append(subprocess.Popen(
                [sys.executable, '-B', '-c', child,
                 str(self.state), str(target), str(start), str(ready)],
                cwd=Path(__file__).resolve().parents[1], env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            ))
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and not all(path.exists() for path in ready_paths):
                if any(process.poll() is not None for process in processes):
                    break
                time.sleep(0.01)
            self.assertTrue(all(path.exists() for path in ready_paths),
                            'both child processes did not reach the publication barrier')
            start.write_text('go', encoding='ascii')
            results = []
            for process in processes:
                stdout, stderr = process.communicate(timeout=15)
                self.assertEqual(process.returncode, 0, stderr)
                results.append(stdout.strip())
            self.assertEqual(sum(value == 'success' for value in results), 1, results)
            self.assertEqual(sum(value.startswith('rejected: destination already exists')
                                 for value in results), 1, results)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()
        with sqlite_connection(target) as connection:
            self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        self.assertEqual(list(self.root.glob('.axflow-state-*.part')), [])

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
        # file. A fresh backup removes it under the destination lock before
        # publishing a new verified artifact safely.
        orphan = list(self.root.glob('.axflow-state-*.part'))
        self.assertEqual(len(orphan), 1)
        other_result = backup_runtime_state(self.state, self.root / 'independent-target.sqlite')
        self.assertEqual(other_result['sqlite_integrity'], 'ok')
        self.assertTrue(orphan[0].exists(), 'another destination cleaned this target\'s crash artifact')
        result = backup_runtime_state(self.state, destination)
        self.assertEqual(result['sqlite_integrity'], 'ok')
        self.assertEqual(_sha(self.state), source_hash)
        self.assertEqual(list(self.root.glob('.axflow-state-*.part')), [])
        with sqlite_connection(destination) as connection:
            self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(connection.execute('SELECT run_id FROM runs').fetchall(), [('Synthetic1',)])


if __name__ == '__main__':
    unittest.main()
