"""Verify an exact, reviewed REA_APP source snapshot before executing its tests.

No GitHub access, package installation, credentials, or input project is required.
Exit nonzero if any protected source blob differs from the P24 snapshot.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASELINE_COMMIT = "33f6d345f8d4577194248eed4543d602819d3192"

# Git blob IDs observed directly on the private REA_APP branch at BASELINE_COMMIT.
# This guards against stale/untracked workspace copies, not against malicious code.
SOURCE_BLOBS = {
    "rea_app/__init__.py": "e6d7269a82c761c70eda0d52ee1d858711d92b21",
    "rea_app/__main__.py": "bfdcd0c1158dff4fcc25157b317419f0a89dd33f",
    "rea_app/cli.py": "adf517ebada8af098b7e83cf42cf39f843f53e09",
    "rea_app/graph.py": "21ce725e93916ba2582a18663d522eaff00c9228",
    "rea_app/impact.py": "64eb59d63780248cc417bcdbad8d73e1e813d75c",
    "rea_app/scanner.py": "857bec57be22aba53e0d3063a25a1272cc5633ef",
    "babel_parser_adapter.cjs": "335e152310f6d5dd015477803af774ae35075d1e",
    "package.json": "f5f89ef63c5636b5be93391b83b11363dcec7ed1",
    "package-lock.json": "0bbde3cd132070df076a478a63056673687852d4",
    "tests/parser_adapter.test.cjs": "f55d15130ba19700be858c7e2a2b468c302e5033",
    "tests/test_cli.py": "6035ccc58fcfc8f2d8eceeba95b8d969ec257dc4",
    "tests/test_scan_open_races.py": "0601539e0a57807441fa31373339c689b2aa7439",
    "tests/test_scan_sensitive_exclusions.py": "3f40479907fe923137f9c018a57b2d3df08ba023",
}


def git_blob_id(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def check_source() -> bool:
    wrong = []
    for relative, expected in sorted(SOURCE_BLOBS.items()):
        source = ROOT / relative
        if not source.is_file() or source.is_symlink():
            wrong.append((relative, "MISSING_OR_LINK"))
            continue
        actual = git_blob_id(source.read_bytes())
        if actual != expected:
            wrong.append((relative, actual))
    # Unreviewed test modules must not be silently executed by discovery.
    # Byte-exact matching alone is insufficient if extra Python tests exist.
    for directory in ("rea_app", "tests"):
        for entry in (ROOT / directory).rglob("*"):
            if entry.suffix.lower() not in {".py", ".js", ".cjs", ".mjs", ".ts", ".tsx"}:
                continue
            relative = entry.relative_to(ROOT).as_posix()
            if relative not in SOURCE_BLOBS:
                wrong.append((relative, "UNREVIEWED_EXECUTABLE_SOURCE"))
    if wrong:
        for relative, actual in wrong:
            print(f"SOURCE MISMATCH {relative}: {actual}", file=sys.stderr)
        print("STOP: reviewed source manifest differs; tests not attributed to Gate R P24.", file=sys.stderr)
        return False
    print(f"SOURCE VERIFIED: {len(SOURCE_BLOBS)}/{len(SOURCE_BLOBS)} Git blobs match {BASELINE_COMMIT}", flush=True)
    return True


def execute(label: str, command: list[str]) -> bool:
    print(f"RUN {label}: {' '.join(command)}", flush=True)
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"{label} BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return False
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
    print(f"{label}: {'PASS' if result.returncode == 0 else 'FAIL'} (exit {result.returncode})", flush=True)
    return result.returncode == 0


def main() -> int:
    print(f"REA_APP P24 verification: Python {sys.version.split()[0]}, platform {sys.platform}", flush=True)
    if not check_source():
        return 2
    python_ok = execute("PYTHON_ALL", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    npm = shutil.which("npm")
    if not npm:
        print("NODE_PARSER BLOCKED: npm unavailable, not counted as PASS.", file=sys.stderr)
        return 1
    node_ok = execute("NODE_PARSER", [npm, "run", "test:parser"])
    print(f"SUMMARY: source=PASS, python={'PASS' if python_ok else 'FAIL'}, "
          f"node={'PASS' if node_ok else 'FAIL'}", flush=True)
    return 0 if python_ok and node_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
