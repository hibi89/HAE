"""Guard the checked-in standalone HAE+LA zipapp against stale source.

This test also runs the shipped binary through the Windows-oriented launcher
outside the checkout. It is explicitly NOT a substitute for real Windows/NTFS.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "apps" / "ax-flow" / "hae-integrated.pyz"
LA = ROOT / "packages" / "lightning-azent" / "lightning_azent"
HAE = ROOT / "apps" / "ax-flow" / "axflow"


def source_files(folder: Path, prefix: str) -> dict[str, bytes]:
    return {
        prefix + "/" + path.relative_to(folder).as_posix(): path.read_bytes()
        for path in folder.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    }


class WindowsCertificationBoundaryTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "Windows host must execute full release acceptance")
    def test_nonwindows_cannot_claim_native_release_success(self):
        gate = ROOT / "apps" / "ax-flow" / "windows_acceptance.py"
        result = subprocess.run(
            [sys.executable, str(gate)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 3)
        self.assertIn("UNVERIFIED", result.stdout)
        self.assertNotIn("PASS", result.stdout)


@unittest.skipUnless(PACKAGE.is_file(), "prebuilt HAE+LA package is missing")
class ShippedOfflinePackageTests(unittest.TestCase):
    def test_checked_in_zipapp_matches_current_hae_and_staged_la_sources(self):
        if not (LA / "__init__.py").is_file():
            self.skipTest("LA source branch has not been staged for source identity verification")
        expected = {
            **source_files(HAE, "axflow"),
            **source_files(LA, "lightning_azent"),
        }
        with ZipFile(PACKAGE) as archive:
            names = {name for name in archive.namelist() if not name.endswith("/")}
            self.assertEqual(names - {"__main__.py"}, set(expected))
            for name, source in expected.items():
                self.assertEqual(archive.read(name), source, "outdated zipapp source: " + name)

    def test_shipped_zipapp_starts_real_la_without_checkout_or_network(self):
        with tempfile.TemporaryDirectory(prefix="hae-shipped-check-") as temporary:
            root = Path(temporary)
            bundle = root / "HAE 한글 offline"
            bundle.mkdir()
            shutil.copyfile(PACKAGE, bundle / "hae-integrated.pyz")
            shutil.copyfile(ROOT / "apps" / "ax-flow" / "launch_integrated.py",
                            bundle / "launch_integrated.py")
            with closing(socket.socket()) as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            started = subprocess.run([
                sys.executable, str(bundle / "launch_integrated.py"),
                "--data-dir", str(root / "로컬 데이터"), "--port", str(port), "--smoke",
            ], cwd=root, env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
            self.assertIn("readiness: PASS", started.stdout)
            self.assertFalse((root / "로컬 데이터" / "runtime.db").exists())
            self.assertFalse((root / "로컬 데이터" / "business.db").exists())

            untouched = root / "사용자 실제 데이터"
            verify = subprocess.run([
                sys.executable, str(bundle / "launch_integrated.py"),
                "--data-dir", str(untouched), "--verify",
            ], cwd=root, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)
            self.assertIn("7/7 PASS", verify.stdout)
            self.assertFalse(untouched.exists(), "isolated acceptance must never initialize real user data")


if __name__ == "__main__":
    unittest.main()
