"""Deterministic source snapshot provenance tests; no customer data."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from rea_app.scanner import _snapshot_stable


class SnapshotIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="rea-snapshot-consistency-")
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / "entry.ts"
        self.file.write_bytes(b"abcd")
        self.handle = self.file.open("rb")
        self.addCleanup(self.handle.close)
        self.before = os.fstat(self.handle.fileno())

    def test_unchanged_complete_read_is_stable(self) -> None:
        data = self.handle.read(32)
        self.assertTrue(_snapshot_stable(self.before, os.fstat(self.handle.fileno()), len(data)))

    def test_same_length_mutation_is_unstable(self) -> None:
        data = self.handle.read(32)
        self.file.write_bytes(b"wxyz")
        os.utime(self.file, ns=(self.before.st_atime_ns, self.before.st_mtime_ns + 3_000_000_000))
        self.assertFalse(_snapshot_stable(self.before, os.fstat(self.handle.fileno()), len(data)))

    def test_truncated_during_read_is_unstable(self) -> None:
        data = self.handle.read(32)
        self.file.write_bytes(b"")
        self.assertFalse(_snapshot_stable(self.before, os.fstat(self.handle.fileno()), len(data)))

    def test_file_grew_during_read_is_unstable(self) -> None:
        data = self.handle.read(32)
        with self.file.open("ab") as handle:
            handle.write(b"e")
        self.assertFalse(_snapshot_stable(self.before, os.fstat(self.handle.fileno()), len(data)))

    def test_partial_read_is_unstable(self) -> None:
        data = self.handle.read(2)
        self.assertFalse(_snapshot_stable(self.before, os.fstat(self.handle.fileno()), len(data)))


if __name__ == "__main__":
    unittest.main()
