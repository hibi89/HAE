"""Portable guard contracts. NTFS reparse flag is simulated, not native Windows QA."""
from __future__ import annotations

import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from test_customer_delivery import owner, package, reports

ROOT = Path(__file__).resolve().parents[1] / "retail"
sys.path.insert(0, str(ROOT))
import candidate_cli as candidate


class ReparseSafetyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bundle = self.root / "reports"
        self.bundle.mkdir()
        for name, report in reports().items():
            (self.bundle / name).write_bytes(owner._encode(report))
        self.delivery = self.root / "delivery"
        self.archive = self.root / "review.zip"

    def simulate_reparse(self, target: Path):
        original = owner._is_link_or_reparse
        return mock.patch.object(owner, "_is_link_or_reparse", side_effect=lambda path: path == target or original(path))

    def test_native_windows_reparse_attribute_bit_is_detected(self):
        fake = SimpleNamespace(st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        with mock.patch.object(Path, "lstat", return_value=fake):
            self.assertTrue(owner._is_link_or_reparse(self.root / "ntfs-junction"))

    def test_nonexistent_output_target_is_not_reparse(self):
        self.assertFalse(owner._is_link_or_reparse(self.root / "new-output-name"))

    def test_denied_metadata_access_fails_closed(self):
        with mock.patch.object(Path, "lstat", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                owner._is_link_or_reparse(self.root / "blocked")

    def test_reparse_parent_of_source_directory_rejected(self):
        with self.simulate_reparse(self.root):
            with self.assertRaisesRegex(owner.DeliveryError, "reparse-point"):
                owner.build(self.bundle, self.delivery)
        self.assertFalse(self.delivery.exists())

    def test_reparse_source_report_file_rejected(self):
        with self.simulate_reparse(self.bundle / "source-map.json"):
            with self.assertRaises(owner.DeliveryError):
                owner.build(self.bundle, self.delivery)
        self.assertFalse(self.delivery.exists())

    def test_reparse_output_directory_parent_rejected(self):
        safe_out = self.root / "output-parent"
        safe_out.mkdir()
        with self.simulate_reparse(safe_out):
            with self.assertRaisesRegex(owner.DeliveryError, "reparse-point"):
                owner.build(self.bundle, safe_out / "review")
        self.assertEqual(list(safe_out.iterdir()), [])

    def test_reparse_archive_parent_rejected(self):
        zip_parent = self.root / "zip-parent"
        zip_parent.mkdir()
        with self.simulate_reparse(zip_parent):
            with self.assertRaisesRegex(owner.DeliveryError, "reparse-point"):
                package._safe_new_zip(zip_parent / "buyer.zip", self.bundle, self.delivery)
        self.assertFalse((zip_parent / "buyer.zip").exists())

    def test_reparse_archive_parent_blocks_verify(self):
        owner.build(self.bundle, self.delivery)
        package.pack(self.bundle, self.delivery, self.archive)
        with self.simulate_reparse(self.root):
            with self.assertRaisesRegex(owner.DeliveryError, "reparse-point"):
                package.verify_zip(self.archive, self.bundle)
        self.assertTrue(self.archive.exists())

    def test_verify_failure_does_not_delete_delivery_or_archive(self):
        def fail_verify(*args, **kwargs):
            raise owner.DeliveryError("simulated verification failure")
        with mock.patch.object(package, "verify_zip", side_effect=fail_verify):
            with self.assertRaisesRegex(owner.DeliveryError, "manual review"):
                candidate.prepare(self.bundle, self.delivery, self.archive)
        self.assertTrue(self.delivery.is_dir())
        self.assertTrue(self.archive.is_file())


if __name__ == "__main__":
    unittest.main()
