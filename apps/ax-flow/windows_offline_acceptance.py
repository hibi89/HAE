"""Native Windows verification of the *distributed* HAE + LA offline bundle.

Run from an extracted HAE-Windows folder:
    python windows_offline_acceptance.py
or double-click VERIFY-WINDOWS.cmd.

Never prints PASS on Linux or a non-native Windows environment. This verifier
runs the real packaged LA HTTP/SQLite workflow in an ephemeral directory,
then validates NTFS/Win32 handle-sharing, parent-junction refusal and the
UTF-16 MAX_PATH refusal without using customer records.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
PYZ = HERE / "hae-integrated.pyz"
CMD = HERE / "run-bundled.cmd"
RESULT_CODE_UNVERIFIED = 3


class NativeWindowsTests(unittest.TestCase):
    def setUp(self):
        if os.name != "nt":
            self.skipTest("native Windows is required")
        if ctypes.sizeof(wintypes.HANDLE) != 8:
            self.skipTest("64-bit Windows Python required for HANDLE tests")
        self.temp = tempfile.TemporaryDirectory(prefix="hae-ntfs-accept-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _imports(self):
        from axflow import engine
        return engine

    def test_01_win64_csv_handle_closes_and_denies_writer(self):
        engine = self._imports()
        input_root = self.root / "입력 데이터"
        input_root.mkdir()
        csv_file = input_root / "contacts.csv"
        csv_file.write_bytes(b"id,name\n1,SyntheticAlice\n")
        with engine._open_csv_readonly(csv_file, input_root) as stream:
            self.assertEqual(stream.read(), b"id,name\n1,SyntheticAlice\n")
            with self.assertRaises(OSError):
                with csv_file.open("r+b"):
                    pass
        # Must release the Win32 HANDLE, not merely the Python reference.
        with csv_file.open("r+b") as writer:
            writer.write(b"id,name\n1,SyntheticAlice\n")

    def test_02_junction_swap_to_outside_is_refused(self):
        engine = self._imports()
        input_root = self.root / "input"
        nested = input_root / "nested"
        nested.mkdir(parents=True)
        outside = self.root / "outside"
        outside.mkdir()
        (nested / "contacts.csv").write_bytes(b"id\n1\n")
        (outside / "contacts.csv").write_bytes(b"id\n2\n")
        original = engine._open_csv_readonly
        moved = input_root / "nested-before-swap"
        junction_created = False

        @contextmanager
        def swap_parent_then_open(path, root):
            nonlocal junction_created
            if path == nested / "contacts.csv":
                nested.rename(moved)
                created = subprocess.run(
                    ["cmd.exe", "/d", "/c", "mklink", "/J",
                     str(nested), str(outside)],
                    capture_output=True, text=True, errors="replace", timeout=10,
                )
                if created.returncode != 0:
                    moved.rename(nested)
                    raise AssertionError("NTFS junction setup failed; not a pass")
                junction_created = True
            with original(path, root) as stream:
                yield stream

        plan = {"version": "axflow.ir.v0", "steps": [
            {"id": "source", "op": "csv_read", "path": "nested/contacts.csv"}
        ]}
        try:
            with patch.object(engine, "_open_csv_readonly", swap_parent_then_open):
                with self.assertRaisesRegex(engine.PlanError, "outside --input-root"):
                    engine.preflight_csv_plan(plan, input_root)
            self.assertTrue(junction_created, "junction race must actually execute")
        finally:
            if junction_created:
                nested.rmdir()  # remove junction itself, NOT destination
            if moved.exists():
                moved.rename(nested)

    def test_03_utf16_max_path_rejected_before_file_io(self):
        engine = self._imports()
        # Ensure the path is long in UTF-16 code units, not just code points.
        input_root = self.root / ("z" * 65)
        input_root.mkdir()
        path = ("😀" * 100) + "/contacts.csv"
        plan = {"version": "axflow.ir.v0", "steps": [
            {"id": "source", "op": "csv_read", "path": path}
        ]}
        with self.assertRaisesRegex(engine.PlanError, "supported Windows path length"):
            engine.preflight_csv_plan(plan, input_root)
        self.assertFalse((self.root / "state.db").exists())
        self.assertFalse((self.root / "business.db").exists())


def main() -> int:
    if os.name != "nt" or ctypes.sizeof(wintypes.HANDLE) != 8:
        print("HAE WINDOWS RELEASE: UNVERIFIED (requires 64-bit native Windows)")
        return RESULT_CODE_UNVERIFIED
    if not PYZ.is_file() or not CMD.is_file():
        print("HAE WINDOWS RELEASE: FAIL (offline bundle incomplete)")
        return 1

    # Bundle is the ONLY Python import source; no Git checkout or LA wheel.
    sys.path.insert(0, str(PYZ))

    with tempfile.TemporaryDirectory(prefix="hae-win-release-") as temp:
        untouched = Path(temp) / "must-not-create-user-data"
        verify = subprocess.run(
            ["cmd.exe", "/d", "/c",
             'call "' + str(CMD) + '" --verify --data-dir "' + str(untouched) + '"'],
            cwd=HERE, capture_output=True, text=True, errors="replace", timeout=60,
        )
        print(verify.stdout.strip())
        if (verify.returncode != 0 or "7/7 PASS" not in verify.stdout
                or untouched.exists()):
            print("HAE WINDOWS RELEASE: FAIL (CMD real HTTP/SQLite E2E)")
            return 1

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NativeWindowsTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if (result.testsRun != 3 or result.errors or result.failures
            or result.skipped or not result.wasSuccessful()):
        print("HAE WINDOWS RELEASE: FAIL / UNVERIFIED (native NTFS tests)")
        return 1

    print("HAE WINDOWS RELEASE: 4/4 PASS (CMD real E2E + 3 NTFS gates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
