"""G85 regression tests for immutable G83 verifier source pins.

Uses only disposable local Git fixture repos. No private HAE/LA execution, NAS,
provider calls, user data, source files or shipped binary changes.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from g84_verify_ugreen_native import (
    NativeGateError, PUBLIC_G83_FILES, verify_public_source_integrity,
)


@unittest.skipUnless(shutil.which("git"), "Git executable required")
class PublicVerifierPinTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory(prefix="g85-native-git-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repo"
        self.root.mkdir()
        self.git("init", "--quiet")
        for path in PUBLIC_G83_FILES:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"# frozen {path}\n", encoding="utf-8")
        self.commit("fixture G83 baseline")
        self.baseline = self.git("rev-parse", "HEAD")

    def git(self, *args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True, text=True, check=True, timeout=10,
        )
        return proc.stdout.strip()

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("-c", "user.name=LocalFixture", "-c",
                 "user.email=local-fixture@example.invalid",
                 "commit", "--quiet", "-m", message)

    def test_exact_baseline_is_accepted(self) -> None:
        verify_public_source_integrity(self.root, self.baseline)

    def test_docs_only_descendant_is_accepted(self) -> None:
        readme = self.root / "docs" / "checkpoint.md"
        readme.parent.mkdir()
        readme.write_text("Documentation-only successor\n", encoding="utf-8")
        self.commit("new checkpoint")
        self.assertNotEqual(self.baseline, self.git("rev-parse", "HEAD"))
        verify_public_source_integrity(self.root, self.baseline)

    def test_changed_committed_verifier_rejected(self) -> None:
        (self.root / PUBLIC_G83_FILES[0]).write_text(
            "# altered verifier\n", encoding="utf-8"
        )
        self.commit("change verifier code")
        with self.assertRaisesRegex(NativeGateError, "integrity mismatch"):
            verify_public_source_integrity(self.root, self.baseline)

    def test_changed_uncommitted_bridge_rejected(self) -> None:
        (self.root / PUBLIC_G83_FILES[1]).write_text(
            "# changed bridge\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(NativeGateError, "integrity mismatch"):
            verify_public_source_integrity(self.root, self.baseline)

    def test_absent_baseline_rejected(self) -> None:
        with self.assertRaisesRegex(NativeGateError, "does not descend"):
            verify_public_source_integrity(self.root, "0" * 40)


if __name__ == "__main__":
    unittest.main()
