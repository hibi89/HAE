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
