"""Reproduces and prevents deletion of another directory after output-path replacement."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_customer_delivery import owner, reports


class OutputWriteRollbackSafety(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="rea-owner-rollback-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.bundle = self.root / "bundle"
        self.bundle.mkdir()
        for name, report in reports().items():
            (self.bundle / name).write_bytes(owner._encode(report))
        self.out = self.root / "review"

    def test_replaced_folder_is_not_traversed_or_deleted_after_write_failure(self):
        victim = self.root / "unrelated"
        victim.mkdir()
        original = {
            "review.json": b"KEEP unrelated review JSON",
            "review.html": b"KEEP unrelated HTML",
            "manifest.json": b"KEEP unrelated manifest",
        }
        for name, data in original.items():
            (victim / name).write_bytes(data)
        real_open = Path.open

        def replace_on_manifest(path, *args, **kwargs):
            if path == self.out / "manifest.json":
                self.out.rename(self.root / "original-generated-directory")
                if os.name == "nt":
                    # A native junction is available without symlink privileges.
                    made = subprocess.run(
                        ["cmd", "/d", "/c", "mklink", "/J", str(self.out), str(victim)],
                        capture_output=True, text=True, timeout=15,
                    )
                    if made.returncode:
                        raise OSError(f"cannot create Windows test junction: {made.stderr}")
                else:
                    self.out.symlink_to(victim, target_is_directory=True)
                raise OSError("injected crash immediately after output path swap")
            return real_open(path, *args, **kwargs)

        with mock.patch.object(Path, "open", replace_on_manifest):
            with self.assertRaisesRegex(owner.DeliveryError, "partial directory left untouched"):
                owner.build(self.bundle, self.out)
        self.assertTrue(owner._is_link_or_reparse(self.out))
        self.assertEqual(original, {name: (victim / name).read_bytes() for name in original})
        # Remove only the test link/junction before TemporaryDirectory cleanup.
        if os.name == "nt":
            self.out.rmdir()
        else:
            self.out.unlink()
        generated = self.root / "original-generated-directory"
        self.assertTrue((generated / "review.json").is_file())
        self.assertTrue((generated / "review.html").is_file())

    def test_partial_original_folder_is_preserved_for_manual_review(self):
        real_open = Path.open

        def fail_manifest(path, *args, **kwargs):
            if path == self.out / "manifest.json":
                raise OSError("simulated drive failure")
            return real_open(path, *args, **kwargs)

        with mock.patch.object(Path, "open", fail_manifest):
            with self.assertRaisesRegex(owner.DeliveryError, "manual review"):
                owner.build(self.bundle, self.out)
        self.assertFalse(self.out.is_symlink())
        self.assertTrue((self.out / "review.json").is_file())
        self.assertTrue((self.out / "review.html").is_file())
        self.assertFalse((self.out / "manifest.json").exists())
        with self.assertRaisesRegex(owner.DeliveryError, "already exists"):
            owner.build(self.bundle, self.out)


if __name__ == "__main__":
    unittest.main()
