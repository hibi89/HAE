"""Actual Windows-only buyer gates: physical NTFS junction and offline Chromium file://.

Linux/macOS intentionally skip; only a native Windows full checkout can certify.
No real customer data, installs, browser extensions or network-dependent tests.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_customer_delivery import owner, package, reports


@unittest.skipUnless(os.name == "nt", "BLOCKED: native Windows required")
class NativeWindowsAcceptanceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="rea-app-native-windows-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)

    def test_real_ntfs_junction_is_rejected_without_touching_target(self):
        target = self.base / "source-target"
        target.mkdir()
        marker = target / "KEEP_ORIGINAL.txt"
        marker.write_text("preserve\n", encoding="utf-8")
        junction = self.base / "input-junction"
        command = ["cmd", "/d", "/c", "mklink", "/J", str(junction), str(target)]
        made = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertEqual(made.returncode, 0, made.stderr or made.stdout)
        # Remove the junction itself, never recursively delete its target contents.
        self.addCleanup(lambda: junction.rmdir() if junction.exists() else None)
        attrs = junction.lstat().st_file_attributes
        self.assertTrue(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        self.assertTrue(owner._is_link_or_reparse(junction))
        with self.assertRaisesRegex(owner.DeliveryError, "reparse-point"):
            owner._directory(junction)
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve\n")

    def test_real_edge_or_chrome_renders_local_review_file(self):
        programs = [
            shutil.which("msedge"), shutil.which("chrome"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        ]
        browser = next((p for p in programs if p and Path(p).is_file()), None)
        self.assertIsNotNone(browser, "Edge/Chrome missing: physical buyer file:// not verified")
        source = self.base / "synthetic-bundle"
        source.mkdir()
        for name, report in reports().items():
            (source / name).write_bytes(owner._encode(report))
        original_sha = {p.name: owner._hash(p.read_bytes()) for p in source.iterdir()}
        preview = self.base / "preview"
        owner.build(source, preview)
        owner.verify(source, preview)
        user_data = self.base / "browser-profile"
        command = [str(browser), "--headless=new", "--disable-gpu", "--no-first-run",
                   "--disable-extensions", "--disable-background-networking", "--no-default-browser-check",
                   f"--user-data-dir={user_data}", "--dump-dom", (preview / "review.html").as_uri()]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=40)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertIn("상업 출시: 보류", result.stdout)
        self.assertNotIn("secret-API-123", result.stdout)
        self.assertIn("Content-Security-Policy", result.stdout)
        self.assertEqual(original_sha, {p.name: owner._hash(p.read_bytes()) for p in source.iterdir()})


if __name__ == "__main__":
    unittest.main()
