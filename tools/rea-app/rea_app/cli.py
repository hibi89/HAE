from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .graph import ParserError, build_report, render_markdown
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


def _write_report(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


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
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()
    if args.command == "scan" and args.parser_timeout <= 0:
        parser.error("--parser-timeout must be positive")
    return args.handler(args)
