"""Regression for assembling the portable HAE release from its prebuilt zipapp."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "apps" / "ax-flow"
REPACK = ROOT / "tools" / "repack_hae_windows_release.py"
REQUIRED = {
    "hae-integrated.pyz", "run-bundled.cmd", "launch_integrated.py",
    "VERIFY-WINDOWS.cmd", "windows_offline_acceptance.py", "README.txt",
}


@unittest.skipUnless((APP / "hae-integrated.pyz").is_file(), "prebuilt LA zipapp unavailable")
class RepackWindowsReleaseTests(unittest.TestCase):
    def test_repack_without_la_checkout_and_verify_against_isolated_sqlite(self):
        with tempfile.TemporaryDirectory(prefix="hae-repacked-release-") as folder:
            root = Path(folder)
            bundle = root / "HAE 한글 Windows Bundle"
            create = subprocess.run([
                sys.executable, str(REPACK), "--output-dir", str(bundle),
            ], cwd=root, capture_output=True, text=True, timeout=15)
            self.assertEqual(create.returncode, 0, create.stderr)
            self.assertEqual({p.name for p in bundle.iterdir()}, REQUIRED)
            prebuilt_hash = hashlib.sha256((APP / "hae-integrated.pyz").read_bytes()).hexdigest()
            self.assertEqual(hashlib.sha256((bundle / "hae-integrated.pyz").read_bytes()).hexdigest(),
                             prebuilt_hash)
            for filename in REQUIRED - {"hae-integrated.pyz", "README.txt"}:
                self.assertEqual((APP / filename).read_bytes(), (bundle / filename).read_bytes(),
                                 "outdated repacked release component: " + filename)

            # An existing destination must never be silently overwritten.
            again = subprocess.run([
                sys.executable, str(REPACK), "--output-dir", str(bundle),
            ], cwd=root, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(again.returncode, 0)

            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            untouched = root / "existing-user-data"
            verify = subprocess.run([
                sys.executable, str(bundle / "launch_integrated.py"),
                "--verify", "--data-dir", str(untouched),
            ], cwd=root, env=env, capture_output=True, text=True, timeout=35)
            self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)
            self.assertIn("7/7 PASS", verify.stdout)
            self.assertFalse(untouched.exists())

            if os.name != "nt":
                refused = subprocess.run([
                    sys.executable, str(bundle / "windows_offline_acceptance.py"),
                ], cwd=root, env=env, capture_output=True, text=True, timeout=10)
                self.assertEqual(refused.returncode, 3)
                self.assertIn("UNVERIFIED", refused.stdout)


if __name__ == "__main__":
    unittest.main()
