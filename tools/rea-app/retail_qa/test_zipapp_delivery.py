"""Test actual standalone Python zipapp run with strict no-overwrite and source binding."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from test_customer_delivery import owner, package, reports

ROOT = Path(__file__).resolve().parents[1] / "retail"
sys.path.insert(0, str(ROOT))
import build_zipapp as builder


class RetailZipappTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.report = self.root / "bundle"
        self.report.mkdir()
        for name, payload in reports().items():
            (self.report / name).write_bytes(owner._encode(payload))
        self.before = {p.name: p.read_bytes() for p in self.report.iterdir()}
        self.pyz = self.root / "candidate.pyz"

    def test_reproducible_self_contained_zipapp_and_execution(self):
        one = builder.build(ROOT, self.pyz)
        again = self.root / "again.pyz"
        two = builder.build(ROOT, again)
        self.assertEqual(one, two)
        self.assertEqual(self.pyz.read_bytes(), again.read_bytes())
        with zipfile.ZipFile(self.pyz) as z:
            self.assertEqual(tuple(z.namelist()), ("__main__.py", *builder.PACKAGE_FILES, "MANIFEST.json"))
            receipt = json.loads(z.read("MANIFEST.json"))
            self.assertEqual(receipt["customer_release"], "HOLD_PENDING_OWNER_ACCEPTANCE")
            for name in builder.PACKAGE_FILES:
                self.assertEqual(receipt["source_sha256"][name], owner._hash(z.read(name)))
            self.assertNotIn(b"SYNTHETIC_NEVER_IN_BUYER_ZIP", b"".join(z.read(n) for n in z.namelist()))
        review, archive = self.root / "review", self.root / "review.zip"
        cmd = [sys.executable, str(self.pyz), "--bundle", str(self.report),
               "--delivery", str(review), "--archive", str(archive)]
        r = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("RELEASE HOLD", r.stdout)
        owner.verify(self.report, review)
        package.verify_zip(archive, self.report)
        self.assertEqual(self.before, {p.name: p.read_bytes() for p in self.report.iterdir()})
        repeat = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(repeat.returncode, 2)
        self.assertNotIn("Traceback", repeat.stderr)

    def test_existing_zipapp_and_source_tree_preserved(self):
        self.pyz.write_bytes(b"KEEP_EXISTING")
        source_before = {n: (ROOT / n).read_bytes() for n in builder.PACKAGE_FILES}
        with self.assertRaises(owner.DeliveryError):
            builder.build(ROOT, self.pyz)
        self.assertEqual(self.pyz.read_bytes(), b"KEEP_EXISTING")
        self.assertEqual(source_before, {n: (ROOT / n).read_bytes() for n in builder.PACKAGE_FILES})

    def test_invalid_package_location_rejected(self):
        with self.assertRaises(owner.DeliveryError):
            builder.build(ROOT, ROOT / "injected.pyz")
        self.assertFalse((ROOT / "injected.pyz").exists())

    def test_builder_cli_offline_no_external_assets(self):
        cmd = [sys.executable, str(ROOT / "build_zipapp.py"), "--archive", str(self.pyz)]
        r = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("RELEASE HOLD", r.stdout)
        self.assertLess(self.pyz.stat().st_size, builder.MAX_PACKAGE_BYTES)


if __name__ == "__main__":
    unittest.main()
