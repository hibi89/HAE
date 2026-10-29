"""Run the remaining HAE Windows-only release gates; never certify on Linux.

From a HAE checkout with Python 3.11+:
    python apps/ax-flow/windows_acceptance.py

Required evidence:
  1. Windows .cmd launcher executes REAL bundled 7-step LA HTTP/SQLite E2E.
  2. CSV Windows share-mode writer refusal (Win32 handle lifetime).
  3. Parent-junction swap escape rejected by NTFS handle identity.
  4. UTF-16 MAX_PATH boundary checked before filesystem access.

Exits nonzero if any test fails, skips, or if this is not Windows. The .cmd
verifier uses only synthetic temporary SQLite files, not the user HAE data.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "apps" / "ax-flow"
WIN_TESTS = (
    "test_engine.TestEngine.test_csv_snapshot_handle_denies_concurrent_writer",
    "test_engine.TestEngine.test_csv_open_rejects_parent_junction_swap_outside_input_root",
    "test_engine.TestEngine.test_preflight_rejects_path_over_windows_max_before_filesystem_access",
)


def run_windows_acceptance() -> int:
    if os.name != "nt":
        print("HAE Windows release: UNVERIFIED (requires native Windows, no emulator override)")
        return 3

    report = {
        "platform": "windows",
        "package_e2e": "not_run",
        "ntfs_tests": "not_run",
        "passed": False,
    }
    bundled = APP / "hae-integrated.pyz"
    launcher = APP / "run-bundled.cmd"
    if not bundled.is_file() or not launcher.is_file():
        print("HAE Windows release: FAIL (shipped package or .cmd launcher missing)")
        return 2

    with tempfile.TemporaryDirectory(prefix="hae-windows-acceptance-") as tmp:
        # This path must remain completely absent. --verify operates exclusively
        # on its own synthetic TemporaryDirectory, never on --data-dir.
        guarded = Path(tmp) / "real-user-data-must-remain-absent"
        verification = subprocess.run(
            ["cmd.exe", "/d", "/s", "/c", str(launcher),
             "--verify", "--data-dir", str(guarded)],
            cwd=APP, capture_output=True, text=True,
            errors="replace", timeout=60,
        )
        if (verification.returncode != 0 or
                "7/7 PASS" not in verification.stdout or guarded.exists()):
            print("HAE Windows release: FAIL (bundled real LA HTTP/SQLite E2E or isolation)")
            report["package_e2e"] = "failed"
            print(json.dumps(report, sort_keys=True))
            return 1
        report["package_e2e"] = "passed"

    # Load exact Windows-only tests and refuse skipped tests. Some Windows
    # runners may prohibit junction creation; that is not a verified PASS.
    sys.path.insert(0, str(APP))
    sys.path.insert(0, str(APP / "tests"))
    suite = unittest.defaultTestLoader.loadTestsFromNames(WIN_TESTS)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    expected_count = len(WIN_TESTS)
    if (result.testsRun != expected_count or result.failures or result.errors
            or result.skipped or not result.wasSuccessful()):
        report["ntfs_tests"] = "failed_or_unverified"
        print(json.dumps(report, sort_keys=True))
        return 1

    report["ntfs_tests"] = "passed"
    report["passed"] = True
    print("HAE Windows release: 4/4 PASS (bundled LA E2E + 3 native NTFS tests)")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_windows_acceptance())
