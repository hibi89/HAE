"""Authorized full-checkout P53 -> customer review end-to-end acceptance.

Runs only on synthetic TS sources, never downloads packages or customer data.
Requires the original rea_app source and already installed locked Babel parser.
No commercial release decision is made by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
RETAIL = TOOL_ROOT / "retail"
sys.path.insert(0, str(RETAIL))
import candidate_cli as candidate
import owner_delivery as owner
import package_delivery as package

ARTIFACTS = (
    "source-map.json", "source-map.md", "change-impact.json", "change-impact.md",
    "functional-contracts.json", "functional-contracts.md",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snapshot(folder: Path) -> dict[str, str]:
    return {
        p.relative_to(folder).as_posix(): digest(p.read_bytes())
        for p in sorted(folder.rglob("*")) if p.is_file()
    }


def write_fixtures(root: Path) -> tuple[Path, Path]:
    before, after = root / "before", root / "after"
    for folder, value in ((before, "id.length"), (after, "id.length + 1")):
        (folder / "src").mkdir(parents=True)
        (folder / "package.json").write_text(
            '{"name":"synthetic-review-acceptance","main":"./src/main.ts"}\n',
            encoding="utf-8",
        )
        (folder / "src/main.ts").write_text(
            'import { load } from "./lib";\n'
            'export function run(id: string): number { return load(id); }\n',
            encoding="utf-8",
        )
        (folder / "src/lib.ts").write_text(
            f'export function load(id: string): number {{ return {value}; }}\n',
            encoding="utf-8",
        )
        # A synthetic marker exercises source-path/content exclusion from buyer output.
        (folder / "src/private-marker-ONLY-FOR-TEST.ts").write_text(
            'export const localSentinel = "SYNTHETIC_NEVER_IN_BUYER_ZIP";\n',
            encoding="utf-8",
        )
    return before, after


def execute_bundle(before: Path, after: Path, dest: Path, diagram: bool) -> None:
    cmd = [sys.executable, "-m", "rea_app", "bundle", str(before), str(after),
           "--output-dir", str(dest)]
    if diagram:
        cmd.append("--with-diagram")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(TOOL_ROOT)
    result = subprocess.run(cmd, cwd=TOOL_ROOT, env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=120)
    if result.returncode:
        raise RuntimeError(f"P53 bundle failed (exit {result.returncode}): {result.stderr[:1600]}")
    expected = set(ARTIFACTS) | ({"architecture.mmd", "architecture.md"} if diagram else set())
    found = {p.name for p in dest.iterdir()}
    if found != expected:
        raise AssertionError(f"P53 bundle files mismatch: {sorted(found ^ expected)}")
    source = owner._parse_json_strict((dest / "source-map.json").read_bytes())
    impact = owner._parse_json_strict((dest / "change-impact.json").read_bytes())
    contracts = owner._parse_json_strict((dest / "functional-contracts.json").read_bytes())
    require(source["schema_version"] == "rea-app-source-map/v1", "source-map schema mismatch")
    require(impact["schema_version"] == "rea-app-change-impact/v1", "change-impact schema mismatch")
    require(contracts["schema_version"] == "rea-app-functional-contracts/v1", "functional-contracts schema mismatch")
    require(source["summary"]["syntax_errors"] == 0, "parser syntax errors")
    require(impact["summary"]["syntax_errors"] == 0, "change-impact syntax errors")
    require(source["summary"]["source_files"] >= 3, "source fixture coverage incomplete")
    require(len(impact["changed_files"]) >= 1, "changed source file not observed")


def perform() -> dict[str, object]:
    missing = [p for p in (TOOL_ROOT / "rea_app" / "cli.py",
                           TOOL_ROOT / "rea_app" / "babel_parser_adapter.cjs") if not p.is_file()]
    if missing:
        raise RuntimeError("BLOCKED: authorized full P53 checkout missing (requires tools/rea-app/rea_app/cli.py and babel_parser_adapter.cjs)")
    gate_file = TOOL_ROOT / "verify_gate_r.py"
    if not gate_file.is_file():
        raise RuntimeError("BLOCKED: original P53 verify_gate_r.py missing")
    gate = subprocess.run([sys.executable, str(gate_file)], cwd=TOOL_ROOT,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=240)
    if gate.returncode != 0:
        raise RuntimeError(f"BLOCKED: original source+Python+exact Babel Gate R failed (exit {gate.returncode}): "
                           f"{(gate.stderr or gate.stdout)[-1400:]}")
    with tempfile.TemporaryDirectory(prefix="rea-p53-real-e2e-") as temp:
        root = Path(temp)
        before, after = write_fixtures(root)
        baseline_hash = snapshot(before)
        current_hash = snapshot(after)
        result: dict[str, object] = {}
        for diagram in (False, True):
            mode = "eight" if diagram else "six"
            report = root / f"{mode}-report"
            execute_bundle(before, after, report, diagram)
            first_report = snapshot(report)
            review, archive = root / f"{mode}-review", root / f"{mode}.zip"
            output_digest = candidate.prepare(report, review, archive)
            owner.verify(report, review)
            package.verify_zip(archive, report)
            with zipfile.ZipFile(archive) as z:
                require(set(z.namelist()) == set(package.ZIP_NAMES), "unexpected buyer ZIP members")
                blob = b"".join(z.read(name) for name in package.ZIP_NAMES)
                require(b"SYNTHETIC_NEVER_IN_BUYER_ZIP" not in blob, "source literal exposed in buyer ZIP")
                require(b"private-marker-ONLY-FOR-TEST" not in blob, "source path exposed in buyer ZIP")
            require(output_digest == digest(archive.read_bytes()), "archive checksum differs")
            require(snapshot(report) == first_report, "original P53 reports mutated")
            # A separate clean run must produce identical P53 report and buyer ZIP bytes.
            repeated = root / f"{mode}-repeat-report"
            execute_bundle(before, after, repeated, diagram)
            require(snapshot(repeated) == first_report, "P53 reports nondeterministic")
            repeated_review, repeated_zip = root / f"{mode}-repeat-review", root / f"{mode}-repeat.zip"
            second_digest = candidate.prepare(repeated, repeated_review, repeated_zip)
            require(output_digest == second_digest, "buyer ZIP hash nondeterministic")
            require(archive.read_bytes() == repeated_zip.read_bytes(), "buyer ZIP bytes nondeterministic")
            result[mode] = {"report_count": len(first_report), "customer_zip_sha256": output_digest,
                            "source_bound_verify": True, "deterministic_rerun": True}
        require(snapshot(before) == baseline_hash, "baseline source mutated")
        require(snapshot(after) == current_hash, "current source mutated")
        result["source_unchanged"] = True
        result["customer_release"] = "HOLD"
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="P53 real parser -> buyer ZIP synthetic acceptance; no external upload")
    parser.parse_args()
    try:
        out = perform()
    except Exception as exc:
        print(f"BLOCKED/FAIL: {exc}", file=sys.stderr)
        return 2
    print("PASS: P53 six+eight report to source-verified deterministic customer ZIP (synthetic only)")
    print(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
