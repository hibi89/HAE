"""Synthetic candidate CLI end-to-end and conservative rollback acceptance."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_customer_delivery import reports, owner, package

ROOT = Path(__file__).resolve().parents[1] / "retail"
sys.path.insert(0, str(ROOT))
import candidate_cli as candidate


class CandidateTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        self.bundle = self.root / "private-reports"
        self.bundle.mkdir()
        for name, value in reports().items():
            (self.bundle / name).write_bytes(owner._encode(value))
        self.delivery = self.root / "buyer-preview"
        self.archive = self.root / "buyer-preview.zip"

    def test_single_command_cli_and_source_immutability(self):
        source = {p.name: p.read_bytes() for p in self.bundle.iterdir()}
        cmd = [sys.executable, str(ROOT / "candidate_cli.py"), "--bundle", str(self.bundle),
               "--delivery", str(self.delivery), "--archive", str(self.archive)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("RELEASE HOLD", r.stdout)
        self.assertTrue(self.archive.is_file())
        owner.verify(self.bundle, self.delivery)
        package.verify_zip(self.archive, self.bundle)
        self.assertEqual(source, {p.name: p.read_bytes() for p in self.bundle.iterdir()})
        self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 2)

    def test_preexisting_delivery_never_replaced(self):
        self.delivery.mkdir()
        (self.delivery / "buyer.txt").write_text("retain")
        with self.assertRaises(owner.DeliveryError):
            candidate.prepare(self.bundle, self.delivery, self.archive)
        self.assertEqual((self.delivery / "buyer.txt").read_text(), "retain")
        self.assertFalse(self.archive.exists())

    def test_preexisting_archive_never_replaced(self):
        self.archive.write_bytes(b"existing original")
        with self.assertRaises(owner.DeliveryError):
            candidate.prepare(self.bundle, self.delivery, self.archive)
        self.assertFalse(self.delivery.exists())
        self.assertEqual(self.archive.read_bytes(), b"existing original")

    def test_invalid_bundle_creates_no_destination(self):
        (self.bundle / "source-map.json").write_bytes(b"{invalid")
        with self.assertRaises(owner.DeliveryError):
            candidate.prepare(self.bundle, self.delivery, self.archive)
        self.assertFalse(self.delivery.exists())
        self.assertFalse(self.archive.exists())

    def test_postpack_verify_failure_rolls_back_own_outputs(self):
        with mock.patch.object(package, "verify_zip", side_effect=owner.DeliveryError("synthetic fail")):
            with self.assertRaises(owner.DeliveryError):
                candidate.prepare(self.bundle, self.delivery, self.archive)
        self.assertFalse(self.delivery.exists())
        self.assertFalse(self.archive.exists())

    def test_replacement_during_failure_is_preserved(self):
        def replacement(*args, **kwargs):
            (self.delivery / "review.html").write_text("changed by another writer")
            raise owner.DeliveryError("synthetic race")
        with mock.patch.object(package, "verify_zip", side_effect=replacement):
            with self.assertRaisesRegex(owner.DeliveryError, "manual review"):
                candidate.prepare(self.bundle, self.delivery, self.archive)
        self.assertEqual((self.delivery / "review.html").read_text(), "changed by another writer")
        self.assertTrue(self.delivery.exists())

    def test_output_inside_input_rejected(self):
        with self.assertRaises(owner.DeliveryError):
            candidate.prepare(self.bundle, self.bundle / "subdir", self.archive)
        self.assertFalse(self.archive.exists())


if __name__ == "__main__":
    unittest.main()
