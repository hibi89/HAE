"""Fail-closed source attribution for the REA_APP offline Gate R verifier."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_gate_r", ROOT / "verify_gate_r.py")
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class TestGateRSourceAttribution(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="rea-verifier-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "rea_app").mkdir()
        (self.root / "tests").mkdir()
        self.sources = {
            "rea_app/__init__.py": b"\"\"\"synthetic\"\"\"\n",
            "rea_app/scanner.py": b"from pathlib import Path\n",
            "tests/test_smoke.py": b"import unittest\n",
        }
        for relative, content in self.sources.items():
            (self.root / relative).write_bytes(content)
        manifest = {name: verifier.git_blob_id(data) for name, data in self.sources.items()}
        self.patches = (patch.object(verifier, "ROOT", self.root),
                        patch.object(verifier, "SOURCE_BLOBS", manifest))
        for active_patch in self.patches:
            active_patch.start()
            self.addCleanup(active_patch.stop)

    def checked(self) -> bool:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return verifier.check_source()

    def test_matches_known_github_blob_fingerprint(self) -> None:
        data = b'"""Read-only, bounded source analysis for REA_APP."""\n\n__version__ = "0.3.0"\n'
        self.assertEqual(verifier.git_blob_id(data), "e6d7269a82c761c70eda0d52ee1d858711d92b21")

    def test_matching_source_is_accepted(self) -> None:
        self.assertTrue(self.checked())

    def test_modified_source_is_rejected(self) -> None:
        (self.root / "rea_app/scanner.py").write_text("tampered", encoding="utf-8")
        self.assertFalse(self.checked())

    def test_unreviewed_test_script_is_rejected(self) -> None:
        (self.root / "tests/test_extra.py").write_text("pass\n", encoding="utf-8")
        self.assertFalse(self.checked())

    def test_installed_parser_version_mismatch_blocks_node_suite(self) -> None:
        from subprocess import CompletedProcess
        observed = CompletedProcess(args=["node"], returncode=0, stdout="7.30.0\n", stderr="")
        with patch.object(verifier.shutil, "which", return_value="/usr/bin/node"), \
                patch.object(verifier.subprocess, "run", return_value=observed) as runner:
            self.assertFalse(verifier.parser_dependency_pinned())
        self.assertEqual(runner.call_count, 1)

    def test_exact_installed_parser_version_is_accepted(self) -> None:
        from subprocess import CompletedProcess
        observed = CompletedProcess(args=["node"], returncode=0, stdout="7.29.9\n", stderr="")
        with patch.object(verifier.shutil, "which", return_value="/usr/bin/node"), \
                patch.object(verifier.subprocess, "run", return_value=observed) as runner:
            self.assertTrue(verifier.parser_dependency_pinned())
        self.assertEqual(runner.call_count, 1)
        self.assertIn("@babel/parser/package.json", runner.call_args.args[0][2])

    def test_symlink_in_manifest_is_rejected(self) -> None:
        source = self.root / "tests/test_smoke.py"
        source.unlink()
        try:
            source.symlink_to(self.root / "rea_app/scanner.py")
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unsupported on host: {exc}")
        self.assertFalse(self.checked())


if __name__ == "__main__":
    unittest.main()
