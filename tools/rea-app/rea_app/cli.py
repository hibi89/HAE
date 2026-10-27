from __future__ import annotations

import argparse
import os
import tempfile
import json
import sys
from pathlib import Path

from . import __version__
from .contracts import ContractError, build_functional_contracts, load_source_map, render_functional_contracts_markdown
from .graph import ParserError, build_report, render_markdown
from .impact import build_change_impact, render_change_impact_markdown
from .scanner import ScanError, ScanLimits, walk_source


class OutputError(Exception):
    """The report destination is not safe or usable."""


def _prepare_output_path(source_root: Path, output_path: Path) -> Path:
    try:
        output = output_path.expanduser().resolve(strict=False)
    except OSError as exc:
        raise OutputError(f"output directory cannot be resolved: {exc}") from exc
    try:
        output.relative_to(source_root)
    except ValueError:
        pass
    else:
        raise OutputError("output directory must be outside the selected source root")
    if output.exists() and not output.is_dir():
        raise OutputError("output path exists and is not a directory")
    return output


def _prepare_compare_paths(baseline: Path, current: Path, output_path: Path) -> tuple[Path, Path, Path]:
    try:
        baseline_root = baseline.expanduser().resolve(strict=False)
        current_root = current.expanduser().resolve(strict=False)
        output = output_path.expanduser().resolve(strict=False)
    except OSError as exc:
        raise OutputError(f"comparison paths cannot be resolved: {exc}") from exc
    if not baseline_root.is_dir() or not current_root.is_dir():
        raise OutputError("baseline and current source roots must be existing directories")
    if baseline_root == current_root:
        raise OutputError("baseline and current source roots must be different")
    if baseline_root in current_root.parents or current_root in baseline_root.parents:
        raise OutputError("baseline and current source roots must not overlap")
    for root in (baseline_root, current_root):
        try:
            output.relative_to(root)
        except ValueError:
            continue
        raise OutputError("output directory must be outside both selected source roots")
    if output.exists() and not output.is_dir():
        raise OutputError("output path exists and is not a directory")
    return baseline_root, current_root, output


def _write_report(path: Path, content: str) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _scan(args: argparse.Namespace) -> int:
    try:
        limits = ScanLimits(args.max_files, args.max_file_bytes, args.max_total_bytes)
        scan = walk_source(args.source, limits)
        output = _prepare_output_path(scan.root, args.output_dir)
        report = build_report(scan, args.parser_timeout)
        markdown = render_markdown(report)
        output.mkdir(parents=True, exist_ok=True)
        _write_report(output / "source-map.json", json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        _write_report(output / "source-map.md", markdown)
    except ScanError as exc:
        print(f"REA_APP scan stopped safely: {exc}", file=sys.stderr)
        return 2
    except OutputError as exc:
        print(f"REA_APP output rejected: {exc}", file=sys.stderr)
        return 2
    except ParserError as exc:
        print(f"REA_APP coverage unavailable: {exc}", file=sys.stderr)
        return 3
    except OSError as exc:
        print(f"REA_APP could not write the report: {exc}", file=sys.stderr)
        return 2

    print(
        f"REA_APP indexed {report['summary']['files_indexed']} files; "
        f"{report['summary']['dependency_edges']} dependency edges; "
        f"{report['summary']['syntax_errors']} syntax errors."
    )
    print(f"Reports: {output / 'source-map.json'} and {output / 'source-map.md'}")
    return 1 if report["summary"]["syntax_errors"] else 0


def _compare(args: argparse.Namespace) -> int:
    try:
        baseline_root, current_root, output = _prepare_compare_paths(
            args.baseline, args.current, args.output_dir,
        )
        limits = ScanLimits(args.max_files, args.max_file_bytes, args.max_total_bytes)
        baseline = walk_source(baseline_root, limits)
        current = walk_source(current_root, limits)
        report = build_change_impact(baseline, current, args.parser_timeout)
        markdown = render_change_impact_markdown(report)
        json_text = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        output.mkdir(parents=True, exist_ok=True)
        _write_report(output / "change-impact.json", json_text)
        _write_report(output / "change-impact.md", markdown)
    except ScanError as exc:
        print(f"REA_APP comparison stopped safely: {exc}", file=sys.stderr)
        return 2
    except OutputError as exc:
        print(f"REA_APP comparison rejected: {exc}", file=sys.stderr)
        return 2
    except ParserError as exc:
        print(f"REA_APP comparison coverage unavailable: {exc}", file=sys.stderr)
        return 3
    except OSError as exc:
        print(f"REA_APP could not write the comparison report: {exc}", file=sys.stderr)
        return 2

    print(
        f"REA_APP compared {report['snapshots']['baseline']['files_indexed']} baseline and "
        f"{report['snapshots']['current']['files_indexed']} current files; "
        f"{len(report['changed_files'])} indexed paths changed."
    )
    print(f"Reports: {output / 'change-impact.json'} and {output / 'change-impact.md'}")
    return 1 if report["summary"]["syntax_errors"] else 0


def _contracts(args: argparse.Namespace) -> int:
    """Export independent interface evidence from a previously saved source map."""
    try:
        source_map_path = args.source_map.expanduser().resolve(strict=True)
        output = args.output_dir.expanduser().resolve(strict=False)
        filenames = ("functional-contracts.json", "functional-contracts.md")
        if any(source_map_path == output / name for name in filenames):
            raise OutputError("contract output must not overwrite the input source map")
        if output.exists() and not output.is_dir():
            raise OutputError("output path exists and is not a directory")
        report = build_functional_contracts(load_source_map(source_map_path))
        markdown = render_functional_contracts_markdown(report)
        output.mkdir(parents=True, exist_ok=True)
        _write_report(output / filenames[0], json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        _write_report(output / filenames[1], markdown)
    except (ContractError, OutputError, FileNotFoundError, OSError) as exc:
        print(f"REA_APP contract export stopped: {exc}", file=sys.stderr)
        return 2
    print(f"REA_APP exported {len(report['contracts'])} interface contracts.")
    print(f"Reports: {output / filenames[0]} and {output / filenames[1]}")
    return 0


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rea-app",
        description="Build a deterministic, read-only source inventory and JS/TS import graph.",
    )
    parser.add_argument("--version", action="version", version=f"rea-app {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("scan", help="scan an explicitly selected source root")
    scan.add_argument("source", type=Path, help="authorized local source directory")
    scan.add_argument("--output-dir", type=Path, required=True, help="report directory outside the source root")
    scan.add_argument("--max-files", type=int, default=5000)
    scan.add_argument("--max-file-bytes", type=int, default=1_000_000)
    scan.add_argument("--max-total-bytes", type=int, default=20_000_000)
    scan.add_argument("--parser-timeout", type=int, default=30)
    scan.set_defaults(handler=_scan)
    compare = commands.add_parser("compare", help="compare two authorized source roots and report dependency impact")
    compare.add_argument("baseline", type=Path, help="authorized baseline source snapshot")
    compare.add_argument("current", type=Path, help="authorized current source snapshot")
    compare.add_argument("--output-dir", type=Path, required=True, help="report directory outside both source roots")
    compare.add_argument("--max-files", type=int, default=5000)
    compare.add_argument("--max-file-bytes", type=int, default=1_000_000)
    compare.add_argument("--max-total-bytes", type=int, default=20_000_000)
    compare.add_argument("--parser-timeout", type=int, default=30)
    compare.set_defaults(handler=_compare)
    contracts = commands.add_parser("contracts", help="export evidence-only interfaces from a saved source-map.json")
    contracts.add_argument("source_map", type=Path, help="existing REA_APP source-map.json")
    contracts.add_argument("--output-dir", type=Path, required=True, help="local contract output directory")
    contracts.set_defaults(handler=_contracts)
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()
    if args.command in {"scan", "compare"} and args.parser_timeout <= 0:
        parser.error("--parser-timeout must be positive")
    if args.command in {"scan", "compare"} and min(args.max_files, args.max_file_bytes, args.max_total_bytes) <= 0:
        parser.error("scan limits must be positive")
    return args.handler(args)

