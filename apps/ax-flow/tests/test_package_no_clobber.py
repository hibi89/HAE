"""Verify zipapp packaging never overwrites a pre-existing artifact.

Uses an original, minimal synthetic LA source fixture: no LA checkout, network,
credentials, or database writes required. Validates the real package builder.
"""
from __future__ import annotations

import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[3]
BUILD = runpy.run_path(str(ROOT / "tools" / "package_hae_integrated.py"), run_name="test_package_no_clobber")
build_integrated_zipapp = BUILD["build_integrated_zipapp"]


class PackageNoClobberTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hae-no-clobber-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.la = self.root / "la"
        module = self.la / "lightning_azent" / "__init__.py"
        module.parent.mkdir(parents=True)
        module.write_text("# synthetic LA packaging fixture\n", encoding="utf-8")

    def test_valid_fresh_zipapp_builds_and_original_hae_is_untouched(self):
        path = self.root / "new.pyz"
        built = build_integrated_zipapp(path, self.la)
        self.assertEqual(built, path)
        with ZipFile(path) as archive:
            self.assertIn("axflow/__init__.py", archive.namelist())
            self.assertEqual(archive.read("lightning_azent/__init__.py"),
                             b"# synthetic LA packaging fixture\n")
        with self.assertRaises(FileExistsError):
            build_integrated_zipapp(path, self.la)

    def test_dangling_output_symlink_is_preserved(self):
        path = self.root / "dangling.pyz"
        destination = self.root / "absent-original"
        try:
            path.symlink_to(destination)
        except (NotImplementedError, OSError):
            self.skipTest("output symlink creation unavailable on this host")
        with self.assertRaises(FileExistsError):
            build_integrated_zipapp(path, self.la)
        self.assertTrue(path.is_symlink())
        self.assertFalse(destination.exists())

    @unittest.skipIf(os.name == "nt", "POSIX atomic publication path")
    def test_competing_writer_during_publication_is_not_overwritten(self):
        target = self.root / "concurrent.pyz"
        real_link = os.link

        def competing_writer(source, destination):
            target.write_bytes(b"DO-NOT-OVERWRITE")
            return real_link(source, destination)

        with patch("os.link", side_effect=competing_writer):
            with self.assertRaises(FileExistsError):
                build_integrated_zipapp(target, self.la)
        self.assertEqual(target.read_bytes(), b"DO-NOT-OVERWRITE")


if __name__ == "__main__":
    unittest.main()
