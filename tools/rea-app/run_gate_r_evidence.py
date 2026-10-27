"""Capture an attributable offline REA_APP Gate R run without network or installs.

Run from any working directory: python run_gate_r_evidence.py [--output-dir PATH].
The command only invokes the reviewed local verifier; it does not fetch packages.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIRED_MARKERS = (
    "SOURCE VERIFIED: 15/15",
    "PYTHON_ALL: PASS",
    "DEPENDENCY VERIFIED: @babel/parser@7.29.9",
    "NODE_PARSER: PASS",
    "SUMMARY: source=PASS, python=PASS, node=PASS",
)


def git_info() -> tuple[str | None, str | None]:
    """Collect local provenance only; no Git remote/network operations."""
    values: list[str | None] = []
    for args in (("rev-parse", "HEAD"), ("branch", "--show-current")):
        try:
            result = subprocess.run(
                ["git", "-C", str(ROOT), *args], capture_output=True,
                text=True, timeout=10, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            values.append(None)
            continue
        values.append(result.stdout.strip() if result.returncode == 0 else None)
    return values[0], values[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record source-pinned REA_APP Gate R evidence")
    parser.add_argument("--output-dir", type=Path, default=Path(tempfile.gettempdir()) / "rea-app-gate-r-results")
    parser.add_argument("--expected-branch", default="REA_APP")
    args = parser.parse_args(argv)
    try:
        output_root = args.output_dir.expanduser().resolve(strict=False)
        if output_root == ROOT or ROOT in output_root.parents:
            parser.error("results must be stored outside the source checkout")
        output_root.mkdir(parents=True, exist_ok=True)
        run_dir = Path(tempfile.mkdtemp(prefix="gate-r-", dir=output_root))
    except OSError as exc:
        print(f"OUTPUT BLOCKED: {type(exc).__name__}", file=sys.stderr)
        return 2
    sha, branch = git_info()
    command = [sys.executable, str(ROOT / "verify_gate_r.py")]
    start = datetime.now(timezone.utc)
    stdout, stderr, exit_code = "", "", -1
    try:
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=420, check=False,
        )
        stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
    except (OSError, subprocess.TimeoutExpired) as exc:
        stderr = f"RUN BLOCKED: {type(exc).__name__}: {exc}\n"
    finally:
        (run_dir / "stdout.txt").write_text(stdout, encoding="utf-8")
        (run_dir / "stderr.txt").write_text(stderr, encoding="utf-8")

    combined = stdout + "\n" + stderr
    markers = {marker: any(line.strip() == marker for line in combined.splitlines()) for marker in REQUIRED_MARKERS}
    tests = re.findall(r"^Ran (\d+) tests?\b", combined, flags=re.MULTILINE)
    skipped = re.findall(r"^OK \(skipped=(\d+)\)$", combined, flags=re.MULTILINE)
    valid_provenance = bool(sha and re.fullmatch(r"[0-9a-f]{40}", sha) and branch == args.expected_branch)
    passed = exit_code == 0 and valid_provenance and all(markers.values())
    record = {
        "schema_version": "rea-app-gate-r-evidence/v1",
        "source_checkout": str(ROOT),
        "git_head": sha,
        "git_branch": branch,
        "expected_branch": args.expected_branch,
        "utc_started": start.isoformat(),
        "utc_finished": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "verifier_exit_code": exit_code,
        "required_markers": markers,
        "python_unittest_ran_counts": [int(n) for n in tests],
        "python_unittest_skipped_counts": [int(n) for n in skipped],
        "status": "PASS" if passed else "PARTIAL_OR_FAIL",
        "caveat": "Local Gate R only; Windows-junction and service deployment checks are separate.",
    }
    (run_dir / "evidence.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"REA_APP GATE R: {record['status']} | checkout {sha or 'unknown'} | branch {branch or 'unknown'}")
    print(f"Local evidence: {run_dir}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
