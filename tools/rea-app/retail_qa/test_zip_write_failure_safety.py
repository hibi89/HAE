"""A ZIP writer failure must never remove an unrelated replacement path."""
from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from test_customer_delivery import owner, package, reports


class PackageFailureSafetyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="rea-zip-fail-safe-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.reports = self.root / "reports"
        self.reports.mkdir()
        for name, record in reports().items():
            (self.reports / name).write_bytes(owner._encode(record))
        self.original = {p.name: p.read_bytes() for p in self.reports.iterdir()}
        self.delivery = self.root / "delivery"
        owner.build(self.reports, self.delivery)
        self.archive = self.root / "package.zip"

    def test_other_writer_archive_preserved_if_path_swapped_before_failure(self):
        moved = self.root / "generated-archive-moved.zip"
        other_writer = b"KEEP THIS UNRELATED WRITER'S FILE"

        def replace_then_fail(*_args, **_kwargs):
            self.archive.rename(moved)
            self.archive.write_bytes(other_writer)
            raise OSError("injected ZIP writer failure after replacement")

        with mock.patch.object(zipfile.ZipFile, "__init__", replace_then_fail):
            with self.assertRaisesRegex(owner.DeliveryError, "partial archive left untouched"):
                package.pack(self.reports, self.delivery, self.archive)
        self.assertEqual(self.archive.read_bytes(), other_writer)
        self.assertTrue(moved.exists())
        self.assertEqual(self.original, {p.name: p.read_bytes() for p in self.reports.iterdir()})

    def test_partial_self_created_archive_remains_unmodified_on_write_failure(self):
        with mock.patch.object(zipfile.ZipFile, "__init__", side_effect=OSError("simulated drive failure")):
            with self.assertRaisesRegex(owner.DeliveryError, "manual review"):
                package.pack(self.reports, self.delivery, self.archive)
        self.assertTrue(self.archive.is_file())
        self.assertEqual(self.archive.stat().st_size, 0)
        with self.assertRaisesRegex(owner.DeliveryError, "archive exists"):
            package.pack(self.reports, self.delivery, self.archive)


if __name__ == "__main__":
    unittest.main()
