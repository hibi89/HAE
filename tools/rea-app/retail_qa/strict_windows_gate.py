"""One-command fail-closed native Windows acceptance of frozen P53 and retail.

Runs original Gate R, exact Babel parser, genuine six-/eight-report P53 E2E,
retail tests, real NTFS junction and Edge/Chrome file://. No npm install,
secrets, cloud, costs, customer source data, or commercial release action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _cmd(args: list[str], cwd: Path) -> str:
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"command returned {r.returncode}: {args[0]} {r.stderr[-500:]}")
    return r.stdout.strip()


def run() -> dict[str, object]:
    if os.name != "nt":
        raise RuntimeError("BLOCKED: physical Windows10/11 runtime required")
    if sys.version_info < (3, 11):
        raise RuntimeError("BLOCKED: Python >=3.11 required")
    if not (ROOT / "rea_app" / "cli.py").is_file() or not (ROOT / "verify_gate_r.py").is_file():
        raise RuntimeError("BLOCKED: complete authorized P53 source checkout required")
    # Never certify a dirty or ambiguous checkout.
    branch = _cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], ROOT)
    if branch != "feature/rea-app-kmong-owner-delivery-20261112":
        raise RuntimeError(f"BLOCKED: unexpected branch {branch!r}")
    sha = _cmd(["git", "rev-parse", "HEAD"], ROOT)
    if _cmd(["git", "status", "--porcelain", "--untracked-files=no"], ROOT):
        raise RuntimeError("BLOCKED: tracked source modifications not allowed")
    suite = unittest.defaultTestLoader.discover(str(ROOT / "retail_qa"), pattern="test_*.py")
    def all_test_ids(node):
        for item in node:
            if isinstance(item, unittest.TestSuite):
                yield from all_test_ids(item)
            else:
                yield item.id()
    discovered = set(all_test_ids(suite))
    required_native = {
        "test_windows_native_acceptance.NativeWindowsAcceptanceTests.test_real_ntfs_junction_is_rejected_without_touching_target",
        "test_windows_native_acceptance.NativeWindowsAcceptanceTests.test_real_edge_or_chrome_renders_local_review_file",
    }
    if len(discovered) < 58 or not required_native.issubset(discovered):
        raise RuntimeError("BLOCKED: missing required retail/native Windows tests")
    print("RUN retail QA and real native Windows junction/browser gates", flush=True)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful() or result.skipped or result.testsRun != len(discovered):
        raise RuntimeError(f"BLOCKED: retail tests run={result.testsRun}, "
                           f"errors={len(result.errors)}, failures={len(result.failures)}, "
                           f"skips={len(result.skipped)}; all must pass")
    from p53_acceptance import perform
    print("RUN original P53 Gate R, pinned Babel7.29.9 and actual source-to-ZIP E2E", flush=True)
    proof = perform()  # Also checks six+eight real parser bundles and source immutability.
    if not all(isinstance(proof.get(mode), dict) and proof[mode].get("source_bound_verify")
               and proof[mode].get("deterministic_rerun") for mode in ("six", "eight")):
        raise RuntimeError("BLOCKED: original P53 six/eight E2E lacks evidence")
    if not proof.get("source_unchanged") or proof.get("customer_release") != "HOLD":
        raise RuntimeError("BLOCKED: original source immutability or HOLD state missing")
    # Build a real executable candidate once more on this exact Windows runtime.
    sys.path.insert(0, str(ROOT / "retail"))
    import build_zipapp
    with tempfile.TemporaryDirectory(prefix="rea-windows-release-candidate-") as temp:
        candidate = Path(temp) / "owner-review.pyz"
        pyz_sha = build_zipapp.build(ROOT / "retail", candidate)
        _cmd([sys.executable, str(candidate), "--help"], Path(temp))
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != pyz_sha:
            raise RuntimeError("BLOCKED: candidate bytes changed")
    if _cmd(["git", "rev-parse", "HEAD"], ROOT) != sha:
        raise RuntimeError("BLOCKED: source SHA changed during acceptance")
    return {"verdict": "TECHNICAL_GATE_PASS_RELEASE_STILL_HOLD",
            "commit_sha": sha, "branch": branch,
            "python": sys.version.split()[0], "platform": sys.platform,
            "retail_cases_passed": result.testsRun, "retail_skips": 0,
            "original_p53": proof, "retail_python_zipapp_sha256": pyz_sha,
            "buyer_rights_support_signing": "NOT_VERIFIED"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Native Windows full P53 + offline retail acceptance")
    parser.parse_args()
    try:
        evidence = run()
    except Exception as exc:
        print(f"BLOCKED/FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
