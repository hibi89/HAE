"""Regression for Windows cp1252 console diagnostics with Korean paths."""
from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import unittest


APP = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("hae_console_under_test", APP / "launch_integrated.py")
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class WindowsConsolePathTests(unittest.TestCase):
    def test_korean_path_escaped_only_for_printing(self):
        original = Path("HAE 한글 고객 폴더") / "contacts.csv"
        printable = launcher._console_safe_path(original)
        self.assertIn("contacts.csv", printable)
        self.assertIn(r"\u", printable)
        self.assertTrue(printable.isascii())
        self.assertEqual(str(original), str(Path("HAE 한글 고객 폴더") / "contacts.csv"))
        buffer = io.BytesIO()
        with io.TextIOWrapper(buffer, encoding="cp1252", errors="strict") as stream:
            stream.write(printable)
            stream.flush()

    def test_ascii_paths_remain_unchanged(self):
        original = Path("HAE") / "input" / "contacts.csv"
        self.assertEqual(launcher._console_safe_path(original), str(original))

    def test_display_escaping_does_not_change_provided_filesystem_path(self):
        original = Path("사용자 경로") / "input" / "contacts.csv"
        printable = launcher._console_safe_path(original)
        self.assertNotEqual(printable, str(original))
        self.assertTrue(printable.isascii())


if __name__ == "__main__":
    unittest.main()
