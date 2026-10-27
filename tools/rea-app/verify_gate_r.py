"""Verify an exact, reviewed REA_APP source snapshot before executing its tests.

No GitHub access, package installation, credentials, or input project is required.
Exit nonzero if any protected source blob differs from the P24 snapshot.
"""
from __future__ import annotations

import hashlib
import stat
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASELINE_COMMIT = "3a1a023533a7c070c35be5abbf06bc185a87471b"

# Git blob IDs observed directly on the private REA_APP branch at BASELINE_COMMIT.
# This guards against stale/untracked workspace copies, not against malicious code.
SOURCE_BLOBS = {
    "rea_app/__init__.py": "e6d7269a82c761c70eda0d52ee1d858711d92b21",
    "rea_app/__main__.py": "bfdcd0c1158dff4fcc25157b317419f0a89dd33f",
    "rea_app/cli.py": "028bec00c6c84ef5ded2d01d95ebb69661db2f2b",
    "rea_app/graph.py": "21ce725e93916ba2582a18663d522eaff00c9228",
    "rea_app/impact.py": "a57a2c594a87bc7f69272c3b21c104788622ee94",
    "rea_app/contracts.py": "99418bfcf649866182a841e72fccaa37433d6071",
    "rea_app/scanner.py": "ac3b5960378924c29e24c87cc58b67c315818c8a",
    "babel_parser_adapter.cjs": "335e152310f6d5dd015477803af774ae35075d1e",
    "package.json": "f5f89ef63c5636b5be93391b83b11363dcec7ed1",
    "package-lock.json": "0bbde3cd132070df076a478a63056673687852d4",
    "tests/parser_adapter.test.cjs": "f55d15130ba19700be858c7e2a2b468c302e5033",
    "tests/test_cli.py": "6035ccc58fcfc8f2d8eceeba95b8d969ec257dc4",
    "tests/test_bundle.py": "5862a93762cce0370d1b47966c66ed940e507370",
    "tests/test_bundle_real_parser.py": "48a10d179c609762ef2af8c22154752b18e28c44",
    "tests/test_report_write_safety.py": "f3dc3251e560f739325343b71039e628321e7446",
    "tests/test_contracts.py": "64ea0c82b787ce76cdeaba526fbe21355647dd83",
    "tests/test_contracts_cli.py": "a39b0139b64157a6d138dde01c833e18bc3fd771",
    "tests/test_scan_open_races.py": "59aa669caadcbb31fc5a96629002196728c31a80",
    "tests/test_scan_snapshot_integrity.py": "a309e31b5b6c015d993fe39da90fcf93088261f0",
    "tests/test_scan_sensitive_exclusions.py": "3f40479907fe923137f9c018a57b2d3df08ba023",
    "tests/test_verify_gate_r.py": "f1e9745e3139050e6ef10bf331c91f6431790136",
}


def git_blob_id(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def check_source() -> bool:
    # Inspect parent directories before reading any reviewed file. A linked
    # directory can otherwise hold matching child blobs outside the checkout.
    for directory in ("rea_app", "tests"):
        candidate = ROOT / directory
        try:
            metadata = candidate.lstat()
        except OSError:
            metadata = None
        if metadata is None or not stat.S_ISDIR(metadata.st_mode) or (
            getattr(metadata, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            print(f"SOURCE MISMATCH {directory}: MISSING_OR_LINK_DIRECTORY", file=sys.stderr)
            print("STOP: reviewed source directory is missing or linked.", file=sys.stderr)
            return False
    wrong = []
    for relative, expected in sorted(SOURCE_BLOBS.items()):
        source = ROOT / relative
        try:
            file_stat = source.lstat()
        except OSError:
            file_stat = None
        if file_stat is None or not stat.S_ISREG(file_stat.st_mode) or (
            getattr(file_stat, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
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
    print(f"SOURCE VERIFIED: {len(SOURCE_BLOBS)}/{len(SOURCE_BLOBS)} Git blobs match reviewed manifest (analyzer baseline {BASELINE_COMMIT})", flush=True)
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



def parser_dependency_pinned() -> bool:
    """Verify the installed Babel parser version, not merely the lockfile text."""
    node = shutil.which("node")
    if not node:
        print("NODE_PARSER BLOCKED: node is unavailable.", file=sys.stderr)
        return False
    command = [node, "-p", "require('@babel/parser/package.json').version"]
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"NODE_PARSER BLOCKED: dependency inspection {type(exc).__name__}", file=sys.stderr)
        return False
    installed = result.stdout.strip()
    if result.returncode != 0 or installed != "7.29.9":
        print("NODE_PARSER BLOCKED: require exact installed @babel/parser@7.29.9; "
              f"observed {installed!r} (exit {result.returncode}).", file=sys.stderr)
        return False
    print("DEPENDENCY VERIFIED: @babel/parser@7.29.9", flush=True)
    return True


def main() -> int:
    print(f"REA_APP P24 verification: Python {sys.version.split()[0]}, platform {sys.platform}", flush=True)
    if not check_source():
        return 2
    python_ok = execute("PYTHON_ALL", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    npm = shutil.which("npm")
    if not npm:
        print("NODE_PARSER BLOCKED: npm unavailable, not counted as PASS.", file=sys.stderr)
        return 1
    node_ok = parser_dependency_pinned() and execute("NODE_PARSER", [npm, "run", "test:parser"])
    print(f"SUMMARY: source=PASS, python={'PASS' if python_ok else 'FAIL'}, "
          f"node={'PASS' if node_ok else 'FAIL'}", flush=True)
    return 0 if python_ok and node_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
