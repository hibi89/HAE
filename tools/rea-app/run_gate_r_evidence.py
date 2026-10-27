"""Capture an attributable offline REA_APP Gate R run without network or installs.

Run from any working directory: python run_gate_r_evidence.py [--output-dir PATH].
The command only invokes the reviewed local verifier; it does not fetch packages.
"""
from __future__ import annotations

import argparse
import hashlib
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
# Pin the trusted Gate R entrypoint as well as its manifest-protected inputs.
# Update this fingerprint deliberately whenever verify_gate_r.py is reviewed.
EXPECTED_VERIFIER_BLOB = "65f9534fd0669e545aa3acf0b78781ccb324f2d8"
REQUIRED_LINES = {
    "source": re.compile(r"^SOURCE VERIFIED: 16/16 Git blobs match .+$"),
    "python": re.compile(r"^PYTHON_ALL: PASS \(exit 0\)$"),
    "babel": re.compile(r"^DEPENDENCY VERIFIED: @babel/parser@7\.29\.9$"),
    "node": re.compile(r"^NODE_PARSER: PASS \(exit 0\)$"),
    "summary": re.compile(r"^SUMMARY: source=PASS, python=PASS, node=PASS$"),
}


def git_blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def git_info() -> tuple[str | None, str | None, bool]:
    """Collect local, narrowly scoped provenance; do not query remotes."""
    results = []
    for args in (("rev-parse", "HEAD"), ("branch", "--show-current"),
                 ("status", "--porcelain", "--untracked-files=all", "--", ".")):
        try:
            result = subprocess.run(
                ["git", "-C", str(ROOT), *args], capture_output=True,
                text=True, timeout=10, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            results.append(None)
            continue
        results.append(result.stdout.strip() if result.returncode == 0 else None)
    return results[0], results[1], results[2] == ""


def checked_verifier_blob() -> str | None:
    try:
        target = ROOT / "verify_gate_r.py"
        if not target.is_file() or target.is_symlink():
            return None
        return git_blob_id(target.read_bytes())
    except OSError:
        return None


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
    sha, branch, worktree_clean = git_info()
    verifier_blob = checked_verifier_blob()
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
    output_lines = [line.strip() for line in combined.splitlines()]
    markers = {label: any(pattern.fullmatch(line) for line in output_lines)
               for label, pattern in REQUIRED_LINES.items()}
    tests = re.findall(r"^Ran (\d+) tests?\b", combined, flags=re.MULTILINE)
    skipped = re.findall(r"^OK \(skipped=(\d+)\)$", combined, flags=re.MULTILINE)
    valid_provenance = bool(sha and re.fullmatch(r"[0-9a-f]{40}", sha) and branch == args.expected_branch)
    verified_verifier = verifier_blob == EXPECTED_VERIFIER_BLOB
    passed = (exit_code == 0 and valid_provenance and worktree_clean
              and verified_verifier and all(markers.values()))
    record = {
        "schema_version": "rea-app-gate-r-evidence/v1",
        "source_checkout": str(ROOT),
        "git_head": sha,
        "git_branch": branch,
        "expected_branch": args.expected_branch,
        "tool_worktree_clean": worktree_clean,
        "reviewed_verifier_blob_expected": EXPECTED_VERIFIER_BLOB,
        "reviewed_verifier_blob_actual": verifier_blob,
        "reviewed_verifier_blob_matches": verified_verifier,
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
