"""Offline Windows bundle instructions must be legible without LA checkout.

Uses a stub zipapp writer, not a simulated LA execution. No runtime databases,
external downloads or user data are accessed by this packaging test.
"""
from __future__ import annotations

from pathlib import Path
import runpy
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tools" / "build_hae_windows_bundle.py"
EXAMPLE_LINES = (
    "HAE + Lightning Azent synthetic local MVP",
    "Requires Python 3.11+; no Git/pip/network at runtime.",
    "Start: double-click run-bundled.cmd",
    "Check Windows/NTFS: double-click VERIFY-WINDOWS.cmd",
    "HTTP/SQLite test only: run-bundled.cmd --verify",
    "Only synthetic CSV data is supported.",
)


class WindowsBundleReadmeTests(unittest.TestCase):
    def test_fresh_bundle_instructions_are_separate_lines(self):
        fake_package = types.ModuleType("package_hae_integrated")

        def fake_build(output, _la_package):
            Path(output).write_bytes(b"synthetic-test-only")

        fake_package.build_integrated_zipapp = fake_build
        with patch.dict(sys.modules, {"package_hae_integrated": fake_package}):
            builder = runpy.run_path(str(SCRIPT), run_name="bundle_readme_test")

        with tempfile.TemporaryDirectory(prefix="hae-bundle-readme-") as temp:
            target = Path(temp) / "HAE-Windows"
            builder["build_windows_bundle"](target, Path(temp) / "not-required-LA")
            readme = (target / "README.txt").read_text(encoding="utf-8")
            self.assertEqual(readme.splitlines(), list(EXAMPLE_LINES))
            self.assertEqual(readme, "\n".join(EXAMPLE_LINES) + "\n")
            self.assertNotIn("\\n", readme, "literal slash-n escapes are not physical lines")
            self.assertEqual((target / "hae-integrated.pyz").read_bytes(), b"synthetic-test-only")
            with self.assertRaises(FileExistsError):
                builder["build_windows_bundle"](target, Path(temp) / "not-required-LA")


if __name__ == "__main__":
    unittest.main()
