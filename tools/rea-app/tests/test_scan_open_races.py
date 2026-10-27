"""Synthetic path-replacement safety tests; no third-party source is inspected."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL_ROOT))

from rea_app.scanner import ScanLimits, walk_source


class ScannerOpenRaceTests(unittest.TestCase):
    def test_replaced_file_identity_is_rejected_without_reading_replacement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rea-app-race-") as directory:
            root = Path(directory) / "source"
            root.mkdir()
            victim = root / "entry.ts"
            victim.write_text("export const safe = true;\n", encoding="utf-8")
            replacement = Path(directory) / "replacement.ts"
            replacement.write_text("export const replaced = true;\n", encoding="utf-8")
            actual_open = os.open
            swapped = False

            def open_after_swap(path, flags, *args, **kwargs):
                nonlocal swapped
                if Path(path) == victim and not swapped:
                    os.replace(replacement, victim)
                    swapped = True
                return actual_open(path, flags, *args, **kwargs)

            with patch("rea_app.scanner.os.open", side_effect=open_after_swap):
                result = walk_source(root, ScanLimits())

            self.assertTrue(swapped)
            self.assertFalse(any(item.path == "entry.ts" for item in result.files))
            self.assertIn(
                {"path": "entry.ts", "reason": "file_identity_changed"},
                result.skipped_files,
            )
            self.assertFalse(any(item.content and "replaced" in item.content for item in result.files))

    @unittest.skipUnless(os.name != "nt" and hasattr(os, "O_NOFOLLOW"), "POSIX no-follow descriptor required")
    def test_symlink_swapped_at_open_is_rejected_without_reading_outside_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rea-app-race-") as directory:
            root = Path(directory) / "source"
            root.mkdir()
            victim = root / "entry.ts"
            victim.write_text("export const safe = true;\n", encoding="utf-8")
            external = Path(directory) / "outside.ts"
            external.write_text("export const forbidden_source = true;\n", encoding="utf-8")
            actual_open = os.open
            swapped = False

            def open_after_swap(path, flags, *args, **kwargs):
                nonlocal swapped
                if Path(path) == victim and not swapped:
                    victim.unlink()
                    os.symlink(external, victim)
                    swapped = True
                return actual_open(path, flags, *args, **kwargs)

            with patch("rea_app.scanner.os.open", side_effect=open_after_swap):
                result = walk_source(root, ScanLimits())

            self.assertTrue(swapped)
            self.assertFalse(any(item.path == "entry.ts" for item in result.files))
            self.assertTrue(any(
                item["path"] == "entry.ts" and str(item["reason"]).startswith("unreadable:")
                for item in result.skipped_files
            ))


if __name__ == "__main__":
    unittest.main()
