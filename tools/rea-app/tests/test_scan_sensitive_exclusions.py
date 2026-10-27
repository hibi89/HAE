"""REA_APP regression: credentials must not be opened during a bounded source walk."""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL_ROOT))

from rea_app.scanner import PRIVATE_DIRS, PRIVATE_FILES, ScanLimits, walk_source


class SensitiveScanExclusionTests(unittest.TestCase):
    def test_known_auth_files_are_excluded_before_open_and_source_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rea-app-secrets-") as directory:
            root = Path(directory) / "source"
            root.mkdir()
            source = root / "app.ts"
            source.write_text("export const safe = true;\n", encoding="utf-8")
            source_hash = hashlib.sha256(source.read_bytes()).digest()
            secret_paths = []
            for name in sorted(PRIVATE_FILES | {".env", ".env.production", "my_private_key.txt"}):
                secret = root / name
                secret.write_text("secret-material-never-open\n", encoding="utf-8")
                secret_paths.append(secret)

            actual_open = os.open
            opened = []

            def guarded_open(path, flags, *args, **kwargs):
                candidate = Path(path)
                if candidate.name.casefold() in PRIVATE_FILES or candidate in secret_paths:
                    raise AssertionError("attempted to open credential file")
                opened.append(candidate)
                return actual_open(path, flags, *args, **kwargs)

            with patch("rea_app.scanner.os.open", side_effect=guarded_open):
                report = walk_source(root, ScanLimits())
            self.assertEqual([item.path for item in report.files], ["app.ts"])
            self.assertIn(source, opened)
            self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), source_hash)
            self.assertEqual({item["path"] for item in report.skipped_files},
                             {file.name for file in secret_paths})
            self.assertTrue(all(item["reason"] == "secret_name" for item in report.skipped_files))

    def test_private_auth_directories_are_pruned_before_walking(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rea-app-secrets-") as directory:
            root = Path(directory) / "source"
            root.mkdir()
            (root / "safe.js").write_text("export const safe = 1;\n", encoding="utf-8")
            for name in sorted(PRIVATE_DIRS):
                private_dir = root / name
                private_dir.mkdir()
                (private_dir / "auth.js").write_text("export const secret = 'token';\n", encoding="utf-8")

            actual_open = os.open
            def guarded_open(path, flags, *args, **kwargs):
                if any(part.casefold() in PRIVATE_DIRS for part in Path(path).parts):
                    raise AssertionError("entered a private credential directory")
                return actual_open(path, flags, *args, **kwargs)

            with patch("rea_app.scanner.os.open", side_effect=guarded_open):
                report = walk_source(root, ScanLimits())
            self.assertEqual([item.path for item in report.files], ["safe.js"])
            self.assertEqual({item["path"] for item in report.skipped_files}, PRIVATE_DIRS)
            self.assertTrue(all(item["reason"] == "secret_directory" for item in report.skipped_files))


if __name__ == "__main__":
    unittest.main()
