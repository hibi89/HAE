from __future__ import annotations

import json
import posixpath
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from .scanner import ScanResult, ScannedFile


NODE_BUILTINS = {
    "assert", "async_hooks", "buffer", "child_process", "cluster", "console",
    "crypto", "dgram", "diagnostics_channel", "dns", "events", "fs", "http",
    "http2", "https", "module", "net", "os", "path", "perf_hooks",
    "process", "punycode", "querystring", "readline", "repl", "stream",
    "string_decoder", "timers", "tls", "tty", "url", "util", "v8",
    "vm", "worker_threads", "zlib",
}
RESOLUTION_SUFFIXES = [".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"]


class ParserError(Exception):
    """The required syntax parser could not produce trustworthy output."""


def _parse_with_typescript(scan: ScanResult, timeout_seconds: int) -> dict[str, Any]:
    parse_files = [
        {"path": item.path, "content": item.content or ""}
        for item in scan.files
        if item.category in {"javascript_typescript_source", "typescript_config"}
    ]
    adapter = Path(__file__).resolve().parents[1] / "babel_parser_adapter.cjs"
    try:
        completed = subprocess.run(
            ["node", str(adapter)],
            input=json.dumps({"files": parse_files}, ensure_ascii=False, separators=(",", ":")),
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ParserError("JavaScript runtime unavailable; install Node.js 20 or newer") from exc
    except subprocess.TimeoutExpired as exc:
        raise ParserError(f"TypeScript parser timed out after {timeout_seconds} seconds") from exc
    if completed.returncode == 3:
        detail = completed.stderr.strip() or "install the pinned TypeScript dependency with npm install"
        raise ParserError(detail)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"parser exited with code {completed.returncode}"
        raise ParserError(detail)
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ParserError("TypeScript parser returned invalid JSON") from exc
    if not isinstance(parsed, dict) or not isinstance(parsed.get("files"), list):
        raise ParserError("TypeScript parser returned an unsupported response")
    return parsed


def _manifest_line(content: str, field: str) -> int:
    match = re.search(rf'^\s*"{re.escape(field)}"\s*:', content, re.MULTILINE)
    return content.count("\n", 0, match.start()) + 1 if match else 1


def _flatten_manifest_targets(value: Any, field: str) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    if isinstance(value, str):
        targets.append((field, value))
    elif isinstance(value, list):
        for item in value:
            targets.extend(_flatten_manifest_targets(item, field))
    elif isinstance(value, dict):
        for key in sorted(value):
            targets.extend(_flatten_manifest_targets(value[key], f"{field}.{key}"))
    return targets


def _package_metadata(files: dict[str, ScannedFile]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    packages: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for path, item in sorted(files.items()):
        if item.category != "package_manifest" or item.content is None:
            continue
        try:
            manifest = json.loads(item.content)
            if not isinstance(manifest, dict):
                raise ValueError("package.json root must be an object")
        except (json.JSONDecodeError, ValueError) as exc:
            diagnostics.append({"path": path, "line": 1, "kind": "invalid_package_manifest", "message": str(exc)})
            continue
        package_root = posixpath.dirname(path)
        dependencies: set[str] = set()
        for field in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
            values = manifest.get(field)
            if isinstance(values, dict):
                dependencies.update(str(name) for name in values)
        entrypoints: list[dict[str, Any]] = []
        for field in ("main", "module", "browser", "types", "typings", "exports", "bin"):
            if field not in manifest:
                continue
            for target_field, target in _flatten_manifest_targets(manifest[field], field):
                entrypoints.append({
                    "field": target_field,
                    "target": target,
                    "line": _manifest_line(item.content, field),
                    "evidence_path": path,
                    "status": "pending",
                    "resolved_path": None,
                    "basis": "package_manifest",
                })
        packages.append({
            "root": package_root or ".",
            "manifest_path": path,
            "name": manifest.get("name") if isinstance(manifest.get("name"), str) else None,
            "version": manifest.get("version") if isinstance(manifest.get("version"), str) else None,
            "dependencies": sorted(dependencies),
            "entrypoints": entrypoints,
            "_dependency_names": dependencies,
        })
    packages.sort(key=lambda item: (item["root"], item["manifest_path"]))
    return packages, diagnostics


def _package_for(path: str, packages: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = [
        package for package in packages
        if package["root"] == "." or path == package["root"] or path.startswith(package["root"].rstrip("/") + "/")
    ]
    return max(matches, key=lambda package: len(package["root"]), default=None)


def _within_relative_root(path: str) -> bool:
    normalized = posixpath.normpath(path)
    return normalized != ".." and not normalized.startswith("../") and not normalized.startswith("/")


def _source_variants(candidate: str, source_paths: set[str]) -> str | None:
    candidate = posixpath.normpath(candidate)
    possibilities = [candidate]
    suffix = PurePosixPath(candidate).suffix.casefold()
    if suffix in {".js", ".jsx", ".mjs", ".cjs"}:
        stem = candidate[: -len(suffix)]
        possibilities.extend(stem + extension for extension in RESOLUTION_SUFFIXES[:4])
    elif not suffix:
        possibilities.extend(candidate + extension for extension in RESOLUTION_SUFFIXES)
        possibilities.extend(posixpath.join(candidate, "index" + extension) for extension in RESOLUTION_SUFFIXES)
    return next((path for path in possibilities if path in source_paths), None)


def _nearest_tsconfig(importer: str, tsconfigs: list[dict[str, Any]]) -> dict[str, Any] | None:
    configs = []
    for config in tsconfigs:
        directory = posixpath.dirname(config["path"])
        if importer == directory or importer.startswith(directory.rstrip("/") + "/") or directory == "":
            configs.append(config)
    return max(configs, key=lambda config: len(posixpath.dirname(config["path"])), default=None)


def _resolve_alias(
    specifier: str,
    importer: str,
    tsconfigs: list[dict[str, Any]],
    source_paths: set[str],
) -> tuple[str | None, bool]:
    config = _nearest_tsconfig(importer, tsconfigs)
    if config is None:
        return None, False
    config_dir = posixpath.dirname(config["path"])
    base_url = config.get("base_url") or "."
    if PurePosixPath(base_url).is_absolute() or (len(base_url) > 1 and base_url[1] == ":"):
        return None, False
    base = posixpath.normpath(posixpath.join(config_dir, base_url))
    path_table = config.get("paths") if isinstance(config.get("paths"), dict) else {}
    ordered_patterns = sorted(path_table, key=lambda pattern: (-len(pattern.replace("*", "")), pattern))
    for pattern in ordered_patterns:
        if "*" in pattern:
            prefix, suffix = pattern.split("*", 1)
            if not specifier.startswith(prefix) or not specifier.endswith(suffix):
                continue
            capture = specifier[len(prefix): len(specifier) - len(suffix) if suffix else None]
        elif pattern == specifier:
            capture = None
        else:
            continue
        targets = path_table[pattern]
        if isinstance(targets, str):
            targets = [targets]
        for target in targets if isinstance(targets, list) else []:
            if not isinstance(target, str):
                continue
            replaced = target.replace("*", capture or "") if capture is not None else target
            candidate = posixpath.normpath(posixpath.join(base, replaced))
            if not _within_relative_root(candidate):
                return None, True
            resolved = _source_variants(candidate, source_paths)
            if resolved:
                return resolved, True
        return None, True
    return None, False


def _resolve_module(specifier: str, importer: str, tsconfigs: list[dict[str, Any]], source_paths: set[str]) -> dict[str, Any]:
    if specifier.startswith(("./", "../")):
        candidate = posixpath.normpath(posixpath.join(posixpath.dirname(importer), specifier))
        if not _within_relative_root(candidate):
            return {"resolution": "out_of_root", "to_path": None, "package_name": None, "declared_dependency": False}
        resolved = _source_variants(candidate, source_paths)
        return {
            "resolution": "internal" if resolved else "unresolved_relative",
            "to_path": resolved,
            "package_name": None,
            "declared_dependency": False,
        }

    aliased, matched_alias = _resolve_alias(specifier, importer, tsconfigs, source_paths)
    if aliased:
        return {"resolution": "internal_alias", "to_path": aliased, "package_name": None, "declared_dependency": False}
    if matched_alias:
        return {"resolution": "unresolved_alias", "to_path": None, "package_name": None, "declared_dependency": False}

    bare = specifier[5:] if specifier.startswith("node:") else specifier
    first = bare.split("/", 1)[0]
    package_name = "/".join(bare.split("/")[:2]) if bare.startswith("@") else first
    if specifier.startswith("node:") or first in NODE_BUILTINS:
        resolution = "node_builtin"
        package_name = None
    else:
        resolution = "external"
    return {"resolution": resolution, "to_path": None, "package_name": package_name, "declared_dependency": False}


def _resolve_entrypoint(entrypoint: dict[str, Any], package_root: str, source_paths: set[str]) -> None:
    target = entrypoint["target"].replace("\\", "/")
    if target.startswith(("/", "../")) or (len(target) > 1 and target[1] == ":"):
        entrypoint["status"] = "out_of_root"
        return
    candidate = posixpath.normpath(posixpath.join(package_root, target))
    if not _within_relative_root(candidate):
        entrypoint["status"] = "out_of_root"
        return
    resolved = _source_variants(candidate, source_paths)
    entrypoint["status"] = "resolved" if resolved else "unresolved"
    entrypoint["resolved_path"] = resolved


def _call_import_binding(callee: str, bindings: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
    direct = re.fullmatch(r"([A-Za-z_$][\w$]*)", callee)
    member = re.fullmatch(r"([A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*)", callee)
    if direct:
        local = direct.group(1)
        matches = [binding for binding in bindings if binding.get("local") == local]
        if len(matches) != 1:
            return None, None
        binding = matches[0]
        imported = binding.get("imported")
        if imported == "*":
            if binding.get("kind") == "require":
                return binding, "default"
            return None, None
        return binding, imported if isinstance(imported, str) else None
    if member:
        local, symbol = member.groups()
        matches = [binding for binding in bindings if binding.get("local") == local and binding.get("imported") == "*"]
        if len(matches) == 1:
            return matches[0], symbol
    return None, None


def build_report(scan: ScanResult, parser_timeout: int) -> dict[str, Any]:
    files = {item.path: item for item in scan.files}
    parsed = _parse_with_typescript(scan, parser_timeout)
    packages, diagnostics = _package_metadata(files)
    source_paths = {path for path, item in files.items() if item.category == "javascript_typescript_source"}
    tsconfigs = []
    for config in parsed.get("tsconfigs", []):
        if config.get("parse_error"):
            diagnostics.append({"path": config["path"], "line": 1, "kind": "invalid_tsconfig", "message": config["parse_error"]})
        else:
            tsconfigs.append(config)

    dependency_edges: list[dict[str, Any]] = []
    exports: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    resolved_call_edges: list[dict[str, Any]] = []
    resolved_edges_by_file: dict[str, dict[int, dict[str, Any]]] = {}
    parse_error_count = 0
    parser_files = {item["path"]: item for item in parsed.get("files", [])}

    for path in sorted(source_paths):
        parse_result = parser_files.get(path, {"parse_errors": [], "edges": [], "exports": [], "calls": []})
        for error in parse_result.get("parse_errors", []):
            parse_error_count += 1
            diagnostics.append({"path": path, "line": error.get("line", 1), "kind": "syntax_error", "message": error.get("message", "syntax could not be parsed")})
        from_package = _package_for(path, packages)
        for edge_index, edge in enumerate(parse_result.get("edges", [])):
            resolution = _resolve_module(edge["specifier"], path, tsconfigs, source_paths)
            target_package = _package_for(resolution["to_path"], packages) if resolution["to_path"] else None
            if resolution["package_name"] and from_package:
                resolution["declared_dependency"] = resolution["package_name"] in from_package["_dependency_names"]
            dependency_edge = {
                "from_path": path,
                "to_path": resolution["to_path"],
                "kind": edge["kind"],
                "specifier": edge["specifier"],
                "resolution": resolution["resolution"],
                "from_package": from_package.get("name") if from_package else None,
                "to_package": target_package.get("name") if target_package else resolution["package_name"],
                "declared_dependency": resolution["declared_dependency"],
                "evidence": {"path": path, "line": edge["line"]},
            }
            dependency_edges.append(dependency_edge)
            resolved_edges_by_file.setdefault(path, {})[edge_index] = dependency_edge
        for item in parse_result.get("exports", []):
            exports.append({
                "path": path,
                "name": item["name"],
                "source_name": item.get("source_name", item["name"]),
                "kind": item["kind"],
                "evidence": {"path": path, "line": item["line"]},
            })
        for item in parse_result.get("calls", []):
            calls.append({
                "path": path,
                "callee": item["callee"],
                "caller": item.get("caller", "<module>"),
                "evidence": {"path": path, "line": item["line"]},
                "resolution": "syntactic_reference",
            })

    exports_by_path: dict[str, list[dict[str, Any]]] = {}
    for item in exports:
        exports_by_path.setdefault(item["path"], []).append(item)
    for path in sorted(source_paths):
        parse_result = parser_files.get(path, {})
        bindings = parse_result.get("bindings", [])
        edge_map = resolved_edges_by_file.get(path, {})
        for call in parse_result.get("calls", []):
            binding, target_symbol = _call_import_binding(call["callee"], bindings)
            if binding is None or target_symbol is None or binding.get("kind") == "type_import":
                continue
            imported_edge = edge_map.get(binding.get("edge_index"))
            if not imported_edge or imported_edge["resolution"] not in {"internal", "internal_alias"} or not imported_edge["to_path"]:
                continue
            target_path = imported_edge["to_path"]
            target_exports = [
                item for item in exports_by_path.get(target_path, [])
                if item["name"] in {target_symbol, "*"}
            ]
            if len(target_exports) != 1:
                continue
            target_export = target_exports[0]
            resolved_call_edges.append({
                "from_path": path,
                "to_path": target_path,
                "caller": call.get("caller", "<module>"),
                "callee": call["callee"],
                "target_symbol": target_symbol,
                "resolution": "static_import_binding",
                "evidence": {
                    "call_site": {"path": path, "line": call["line"]},
                    "import_binding": imported_edge["evidence"],
                    "target_export": target_export["evidence"],
                },
            })

    for package in packages:
        for entrypoint in package["entrypoints"]:
            _resolve_entrypoint(entrypoint, package["root"], source_paths)
        if not package["entrypoints"]:
            for candidate in ("index.ts", "index.tsx", "index.js", "index.jsx", "src/index.ts", "src/index.js"):
                resolved = _source_variants(posixpath.join(package["root"], candidate), source_paths)
                if resolved:
                    package["entrypoints"].append({
                        "field": "conventional_index", "target": candidate, "line": 1,
                        "evidence_path": resolved, "status": "inferred", "resolved_path": resolved,
                        "basis": "conventional_index_filename",
                    })
        package.pop("_dependency_names", None)

    dependency_edges.sort(key=lambda edge: (edge["from_path"], edge["evidence"]["line"], edge["kind"], edge["specifier"], edge["to_path"] or ""))
    exports.sort(key=lambda item: (item["path"], item["evidence"]["line"], item["name"], item["kind"]))
    calls.sort(key=lambda item: (item["path"], item["evidence"]["line"], item["callee"]))
    resolved_call_edges.sort(key=lambda item: (item["from_path"], item["evidence"]["call_site"]["line"], item["to_path"], item["target_symbol"]))
    diagnostics.sort(key=lambda item: (item["path"], item["line"], item["kind"], item["message"]))

    file_records = []
    for item in scan.files:
        owner = _package_for(item.path, packages)
        file_records.append({
            "path": item.path,
            "size_bytes": item.size_bytes,
            "language": Path(item.path).suffix.casefold().lstrip(".") or "unknown",
            "analysis": item.category,
            "package": owner.get("name") if owner else None,
        })

    total_edges = len(dependency_edges)
    return {
        "schema_version": "rea-app-source-map/v1",
        "tool_version": "0.1.0",
        "parser": parsed.get("parser", "unknown"),
        "limits": {
            "max_files": scan.limits.max_files,
            "max_file_bytes": scan.limits.max_file_bytes,
            "max_total_bytes": scan.limits.max_total_bytes,
            "total_walked_bytes": scan.total_walked_bytes,
        },
        "summary": {
            "files_indexed": len(file_records), "source_files": len(source_paths),
            "packages": len(packages), "dependency_edges": total_edges,
            "internal_edges": sum(edge["resolution"] in {"internal", "internal_alias"} for edge in dependency_edges),
            "external_edges": sum(edge["resolution"] == "external" for edge in dependency_edges),
            "exports": len(exports), "call_sites": len(calls), "syntax_errors": parse_error_count,
            "resolved_call_edges": len(resolved_call_edges),
            "diagnostics": len(diagnostics), "skipped_paths": len(scan.skipped_files),
        },
        "files": file_records,
        "packages": packages,
        "dependency_edges": dependency_edges,
        "exports": exports,
        "calls": calls,
        "resolved_call_edges": resolved_call_edges,
        "skipped_files": scan.skipped_files,
        "diagnostics": diagnostics,
        "coverage": {
            "javascript_typescript": "TypeScript AST parser; import, export, require, dynamic import and syntactic call references",
            "python": "inventory only",
            "other_languages": "inventory only",
            "call_resolution": "direct imported calls with a unique in-root module edge and matching export are linked; other calls remain syntactic references",
            "data_flow": "not analyzed",
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# REA_APP source map", "",
        "The scan is read-only. The selected source root is omitted from this report; all paths are relative.", "",
        "## Summary", "",
        f"- Parser: `{report['parser']}`",
        f"- Files indexed: {summary['files_indexed']} ({summary['source_files']} JavaScript/TypeScript source files)",
        f"- Packages: {summary['packages']}",
        f"- Dependency edges: {summary['dependency_edges']} ({summary['internal_edges']} internal, {summary['external_edges']} external)",
        f"- Exports: {summary['exports']}; syntactic call sites: {summary['call_sites']}",
        f"- Statically linked imported calls: {summary['resolved_call_edges']}",
        f"- Parse errors: {summary['syntax_errors']}; skipped paths: {summary['skipped_paths']}", "",
        "## Coverage and limits", "",
        f"- JS/TS: {report['coverage']['javascript_typescript']}.",
        f"- Python: {report['coverage']['python']}; other languages: {report['coverage']['other_languages']}.",
        f"- Calls: {report['coverage']['call_resolution']}.",
        f"- Value/data flow: {report['coverage']['data_flow']}.",
        f"- File cap: {report['limits']['max_files']}; per-file cap: {report['limits']['max_file_bytes']} bytes; total cap: {report['limits']['max_total_bytes']} bytes.", "",
        "## Packages", "",
    ]
    if report["packages"]:
        for package in report["packages"]:
            lines.append(f"### `{package['name'] or package['root']}` — `{package['root']}`")
            if package["dependencies"]:
                lines.append("Declared dependencies: " + ", ".join(f"`{name}`" for name in package["dependencies"]))
            for entry in package["entrypoints"]:
                resolved = f" → `{entry['resolved_path']}`" if entry["resolved_path"] else ""
                lines.append(f"- `{entry['field']}` `{entry['target']}` ({entry['status']}; evidence `{entry['evidence_path']}:{entry['line']}`){resolved}")
            if not package["entrypoints"]:
                lines.append("- No package entry point was observed.")
            lines.append("")
    else:
        lines.extend(["No `package.json` boundaries were found.", ""])

    lines.extend(["## Dependency edges", ""])
    if report["dependency_edges"]:
        for edge in report["dependency_edges"]:
            target = f"`{edge['to_path']}`" if edge["to_path"] else f"`{edge['to_package'] or 'unresolved'}`"
            declared = " (declared)" if edge["declared_dependency"] else ""
            lines.append(f"- `{edge['evidence']['path']}:{edge['evidence']['line']}` — {edge['kind']} `{edge['specifier']}` → {target} [{edge['resolution']}{declared}]")
    else:
        lines.append("No import or re-export edges were observed.")
    lines.extend(["", "## Cross-module calls", ""])
    for item in report["resolved_call_edges"]:
        lines.append(
            f"- `{item['evidence']['call_site']['path']}:{item['evidence']['call_site']['line']}` — "
            f"`{item['caller']}.{item['callee']}` → `{item['to_path']}::{item['target_symbol']}`; "
            f"import evidence `{item['evidence']['import_binding']['path']}:{item['evidence']['import_binding']['line']}`, "
            f"export evidence `{item['evidence']['target_export']['path']}:{item['evidence']['target_export']['line']}`."
        )
    if not report["resolved_call_edges"]:
        lines.append("No statically imported calls met the supported binding and export checks.")
    lines.extend(["", "## Exports and call sites", ""])
    for item in report["exports"]:
        lines.append(f"- Export `{item['name']}` in `{item['path']}:{item['evidence']['line']}` ({item['kind']}).")
    for item in report["calls"]:
        lines.append(f"- Call `{item['callee']}` in `{item['path']}:{item['evidence']['line']}`; target resolution is syntactic only.")
    if not report["exports"] and not report["calls"]:
        lines.append("No exports or call expressions were observed.")
    lines.extend(["", "## Diagnostics and exclusions", ""])
    for item in report["diagnostics"]:
        lines.append(f"- `{item['path']}:{item['line']}` — {item['kind']}: {item['message']}")
    for item in report["skipped_files"]:
        size = f" ({item['size_bytes']} bytes)" if "size_bytes" in item else ""
        lines.append(f"- `{item['path']}` — skipped: {item['reason']}{size}.")
    if not report["diagnostics"] and not report["skipped_files"]:
        lines.append("No diagnostics or exclusions.")
    return "\n".join(lines) + "\n"
