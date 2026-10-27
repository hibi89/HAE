from __future__ import annotations

from collections import deque
from typing import Any

from .graph import build_report
from .scanner import ScanResult


def _file_index(scan: ScanResult) -> dict[str, dict[str, Any]]:
    return {
        item.path: {
            "path": item.path,
            "size_bytes": item.size_bytes,
            "category": item.category,
            "sha256": item.content_sha256,
        }
        for item in scan.files
    }


def _reverse_dependencies(
    named_reports: list[tuple[str, dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for snapshot, report in named_reports:
        for edge in report["dependency_edges"]:
            if edge["resolution"] not in {"internal", "internal_alias"} or not edge["to_path"]:
                continue
            key = (edge["from_path"], edge["to_path"])
            grouped.setdefault(key, []).append({
                "snapshot": snapshot,
                "kind": edge["kind"],
                "specifier": edge["specifier"],
                "evidence": edge["evidence"],
            })

    reverse: dict[str, list[dict[str, Any]]] = {}
    for (source, target), evidence in sorted(grouped.items()):
        evidence.sort(key=lambda item: (
            0 if item["snapshot"] == "current" else 1,
            item["evidence"]["path"],
            item["evidence"]["line"],
            item["kind"],
            item["specifier"],
        ))
        reverse.setdefault(target, []).append({
            "from_path": source,
            "to_path": target,
            "evidence": evidence,
        })
    for edges in reverse.values():
        edges.sort(key=lambda edge: (edge["from_path"], edge["to_path"]))
    return reverse


def _dependents(changed_path: str, reverse: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    queue = deque([(changed_path, [])])
    seen = {changed_path}
    found: list[dict[str, Any]] = []
    while queue:
        dependency, chain = queue.popleft()
        for edge in reverse.get(dependency, []):
            importer = edge["from_path"]
            if importer in seen:
                continue
            next_chain = [edge, *chain]
            seen.add(importer)
            found.append({
                "path": importer,
                "distance": len(next_chain),
                "dependency_chain": next_chain,
            })
            queue.append((importer, next_chain))
    return sorted(found, key=lambda item: (item["distance"], item["path"]))


def _entrypoint_impacts(
    changed_path: str,
    dependent_paths: set[str],
    named_reports: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    impacted = dependent_paths | {changed_path}
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, int]] = set()
    for snapshot, report in named_reports:
        for package in report["packages"]:
            for entrypoint in package["entrypoints"]:
                path = entrypoint.get("resolved_path")
                if not path or path not in impacted:
                    continue
                key = (
                    snapshot,
                    package["manifest_path"],
                    entrypoint["field"],
                    path,
                    entrypoint["line"],
                )
                if key in seen:
                    continue
                seen.add(key)
                results.append({
                    "snapshot": snapshot,
                    "package": package["name"],
                    "manifest_path": package["manifest_path"],
                    "field": entrypoint["field"],
                    "path": path,
                    "evidence": {
                        "path": entrypoint["evidence_path"],
                        "line": entrypoint["line"],
                    },
                })
    return sorted(results, key=lambda item: (
        item["path"], item["snapshot"], item["manifest_path"], item["field"],
    ))


def _skipped_coverage(named_scans: list[tuple[str, ScanResult]], cap: int = 250) -> dict[str, Any]:
    skipped = [
        {"snapshot": snapshot, "path": item["path"], "reason": item["reason"]}
        for snapshot, scan in named_scans
        for item in scan.skipped_files
    ]
    skipped.sort(key=lambda item: (item["snapshot"], item["path"], item["reason"]))
    return {
        "skipped_path_count": len(skipped),
        "skipped_paths": skipped[:cap],
        "skipped_paths_truncated": len(skipped) > cap,
        "note": "Paths skipped by either bounded scan were not content-compared; see each source-map coverage record.",
    }


def _inline_code(value: str) -> str:
    text = value.replace("\r", " ").replace("\n", " ")
    delimiter = "`"
    while delimiter in text:
        delimiter += "`"
    return f"{delimiter} {text} {delimiter}"


def _package_owner(path: str, packages_by_root: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    candidate = path
    while True:
        package = packages_by_root.get(candidate)
        if package is not None:
            return package
        if "/" not in candidate:
            break
        candidate = candidate.rsplit("/", 1)[0]
    return packages_by_root.get(".")


def _module_architecture(report: dict[str, Any]) -> dict[str, Any]:
    packages_by_root = {
        package["root"]: {
            "root": package["root"],
            "name": package.get("name"),
        }
        for package in report["packages"]
    }
    packages = {}
    for package in report["packages"]:
        entrypoints = [
            {
                "field": entry.get("field"),
                "resolved_path": entry.get("resolved_path"),
                "status": entry.get("status"),
            }
            for entry in package["entrypoints"]
        ]
        entrypoints.sort(key=lambda item: (
            item["field"] or "", item["resolved_path"] or "", item["status"] or "",
        ))
        packages[package["root"]] = {
            "root": package["root"],
            "name": package.get("name"),
            "entrypoints": entrypoints,
        }

    modules = {}
    for item in report["files"]:
        if item["analysis"] != "javascript_typescript_source":
            continue
        owner = _package_owner(item["path"], packages_by_root)
        modules[item["path"]] = {
            "path": item["path"],
            "package": owner,
        }

    dependencies: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for edge in report["dependency_edges"]:
        if edge["resolution"] not in {"internal", "internal_alias"} or not edge["to_path"]:
            continue
        key = (edge["from_path"], edge["to_path"])
        dependencies.setdefault(key, []).append({
            "kind": edge["kind"],
            "evidence": edge["evidence"],
        })
    for evidence in dependencies.values():
        evidence.sort(key=lambda item: (
            item["evidence"]["path"], item["evidence"]["line"], item["kind"],
        ))
    return {"modules": modules, "packages": packages, "dependencies": dependencies}


def _architecture_changes(baseline_report: dict[str, Any], current_report: dict[str, Any]) -> dict[str, Any]:
    before = _module_architecture(baseline_report)
    after = _module_architecture(current_report)

    before_modules, after_modules = before["modules"], after["modules"]
    common_modules = set(before_modules) & set(after_modules)
    module_package_changes = [
        {
            "path": path,
            "baseline": before_modules[path]["package"],
            "current": after_modules[path]["package"],
        }
        for path in sorted(common_modules)
        if before_modules[path]["package"] != after_modules[path]["package"]
    ]

    before_packages, after_packages = before["packages"], after["packages"]
    common_packages = set(before_packages) & set(after_packages)
    package_changes = {
        "added": [after_packages[root] for root in sorted(set(after_packages) - set(before_packages))],
        "removed": [before_packages[root] for root in sorted(set(before_packages) - set(after_packages))],
        "changed": [
            {
                "root": root,
                "baseline": before_packages[root],
                "current": after_packages[root],
            }
            for root in sorted(common_packages)
            if before_packages[root] != after_packages[root]
        ],
    }

    before_dependencies, after_dependencies = before["dependencies"], after["dependencies"]

    def describe_dependencies(
        dependencies: dict[tuple[str, str], list[dict[str, Any]]],
        keys: set[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        return [
            {
                "from_path": source,
                "to_path": target,
                "evidence": dependencies[(source, target)],
            }
            for source, target in sorted(keys)
        ]

    module_changes = {
        "added": [after_modules[path] for path in sorted(set(after_modules) - set(before_modules))],
        "removed": [before_modules[path] for path in sorted(set(before_modules) - set(after_modules))],
        "package_changes": module_package_changes,
    }
    dependency_changes = {
        "added": describe_dependencies(after_dependencies, set(after_dependencies) - set(before_dependencies)),
        "removed": describe_dependencies(before_dependencies, set(before_dependencies) - set(after_dependencies)),
    }
    return {
        "baseline": {
            "modules": len(before_modules),
            "packages": len(before_packages),
            "internal_dependencies": len(before_dependencies),
        },
        "current": {
            "modules": len(after_modules),
            "packages": len(after_packages),
            "internal_dependencies": len(after_dependencies),
        },
        "modules": module_changes,
        "dependencies": dependency_changes,
        "packages": package_changes,
    }


def _callable_signature(item: dict[str, Any], export_kinds: set[str] | list[str]) -> dict[str, Any]:
    return {
        "export_kinds": sorted(export_kinds),
        "parameters": [
            {
                "name": parameter.get("name"),
                "pattern": parameter.get("pattern"),
                "type_annotation": parameter.get("type_annotation"),
                "optional": bool(parameter.get("optional", False)),
                "rest": bool(parameter.get("rest", False)),
                "has_default": bool(parameter.get("has_default", False)),
            }
            for parameter in item["parameters"]
        ],
        "return_type_annotation": item.get("return_type_annotation"),
        "async": bool(item.get("async", False)),
        "generator": bool(item.get("generator", False)),
    }


def _callable_contracts(report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    export_kinds: dict[tuple[str, str], set[str]] = {}
    for item in report["exports"]:
        key = (item["path"], item["name"])
        export_kinds.setdefault(key, set()).add(item["kind"])

    contracts = {}
    direct_by_symbol: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in report["function_contracts"]:
        module = item["evidence"]["definition"]["path"]
        exported_as = item["exported_as"]
        key = (module, exported_as)
        direct_by_symbol.setdefault(key, []).append(item)
        contracts[key] = {
            "module": module,
            "exported_as": exported_as,
            "signature": _callable_signature(item, export_kinds.get(key, set())),
            "evidence": item["evidence"],
            "assurance": "explicit_syntax_only",
        }

    reexport_edges: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for edge in report["dependency_edges"]:
        if edge["kind"] != "reexport":
            continue
        evidence = edge["evidence"]
        reexport_edges.setdefault((edge["from_path"], evidence["line"]), []).append(edge)

    reexports_by_symbol: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in report["exports"]:
        if item["kind"] != "reexport":
            continue
        key = (item["path"], item["name"])
        reexports_by_symbol.setdefault(key, []).append(item)

    for key, items in reexports_by_symbol.items():
        if len(items) != 1 or key in contracts:
            continue
        exported = items[0]
        edges = reexport_edges.get((exported["path"], exported["evidence"]["line"]), [])
        if len(edges) != 1:
            continue
        edge = edges[0]
        if edge["resolution"] not in {"internal", "internal_alias"}:
            continue
        target_path = edge["to_path"]
        target_symbol = exported["source_name"]
        candidates = direct_by_symbol.get((target_path, target_symbol), [])
        if not target_path or len(candidates) != 1:
            continue
        target = candidates[0]
        contracts[key] = {
            "module": exported["path"],
            "exported_as": exported["name"],
            "signature": _callable_signature(target, ["reexport"]),
            "evidence": {
                "definition": target["evidence"]["definition"],
                "export": {
                    "path": exported["path"],
                    "line": exported["evidence"]["line"],
                    "name": exported["name"],
                },
            },
            "assurance": "explicit_syntax_only",
        }
    return contracts


def _contract_changes(baseline_report: dict[str, Any], current_report: dict[str, Any]) -> dict[str, Any]:
    before = _callable_contracts(baseline_report)
    after = _callable_contracts(current_report)
    before_keys, after_keys = set(before), set(after)
    common = before_keys & after_keys
    return {
        "comparison_basis": "Module path and exported symbol; explicit parameter and return syntax, async/generator flags, and observed direct ESM/CommonJS export or ESM re-export kind.",
        "limitations": [
            "Only unambiguous exported callable contracts with observed syntax are compared; absence is not a runtime compatibility verdict.",
            "Direct, uniquely resolved in-root ESM re-exports inherit one matching target callable signature; re-export chains, wildcard exports, inferred types, default values, function bodies, and side effects are not compared.",
        ],
        "baseline_count": len(before),
        "current_count": len(after),
        "added": [after[key] for key in sorted(after_keys - before_keys)],
        "removed": [before[key] for key in sorted(before_keys - after_keys)],
        "changed": [
            {
                "module": key[0],
                "exported_as": key[1],
                "baseline": before[key],
                "current": after[key],
            }
            for key in sorted(common)
            if before[key]["signature"] != after[key]["signature"]
        ],
    }


def build_change_impact(
    baseline: ScanResult,
    current: ScanResult,
    parser_timeout: int,
    *,
    current_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    baseline_report = build_report(baseline, parser_timeout)
    if current_report is None:
        current_report = build_report(current, parser_timeout)
    named_reports = [("baseline", baseline_report), ("current", current_report)]
    architecture = _architecture_changes(baseline_report, current_report)
    contracts = _contract_changes(baseline_report, current_report)
    before = _file_index(baseline)
    after = _file_index(current)
    paths = sorted(set(before) | set(after))
    changed_files: list[dict[str, Any]] = []

    for path in paths:
        old = before.get(path)
        new = after.get(path)
        if old is None:
            status = "added"
        elif new is None:
            status = "removed"
        elif old["sha256"] != new["sha256"]:
            status = "modified"
        else:
            continue
        changed_files.append({
            "path": path,
            "status": status,
            # Keep fingerprints private to the comparison; reports need the
            # status and evidence, not reusable content fingerprints.
            "baseline": {key: old[key] for key in ("size_bytes", "category")} if old else None,
            "current": {key: new[key] for key in ("size_bytes", "category")} if new else None,
        })

    reverse = _reverse_dependencies(named_reports)
    impacts: list[dict[str, Any]] = []
    for item in changed_files:
        dependents = _dependents(item["path"], reverse)
        impacts.append({
            "changed_path": item["path"],
            "direct_dependents": [entry for entry in dependents if entry["distance"] == 1],
            "transitive_dependents": [entry for entry in dependents if entry["distance"] > 1],
            "impacted_entrypoints": _entrypoint_impacts(
                item["path"],
                {entry["path"] for entry in dependents},
                named_reports,
            ),
        })

    return {
        "schema_version": "rea-app-change-impact/v1",
        "tool_version": "0.3.0",
        "analysis": "bounded_static_dependency_impact",
        "snapshots": {
            "baseline": baseline_report["summary"],
            "current": current_report["summary"],
        },
        "summary": {
            "added_files": sum(item["status"] == "added" for item in changed_files),
            "removed_files": sum(item["status"] == "removed" for item in changed_files),
            "modified_files": sum(item["status"] == "modified" for item in changed_files),
            "direct_dependent_records": sum(len(item["direct_dependents"]) for item in impacts),
            "transitive_dependent_records": sum(len(item["transitive_dependents"]) for item in impacts),
            "impacted_entrypoint_records": sum(len(item["impacted_entrypoints"]) for item in impacts),
            "syntax_errors": baseline_report["summary"]["syntax_errors"] + current_report["summary"]["syntax_errors"],
            "added_modules": len(architecture["modules"]["added"]),
            "removed_modules": len(architecture["modules"]["removed"]),
            "module_package_changes": len(architecture["modules"]["package_changes"]),
            "added_internal_dependencies": len(architecture["dependencies"]["added"]),
            "removed_internal_dependencies": len(architecture["dependencies"]["removed"]),
            "added_packages": len(architecture["packages"]["added"]),
            "removed_packages": len(architecture["packages"]["removed"]),
            "changed_packages": len(architecture["packages"]["changed"]),
            "added_contracts": len(contracts["added"]),
            "removed_contracts": len(contracts["removed"]),
            "changed_contracts": len(contracts["changed"]),
        },
        "changed_files": changed_files,
        "impacts": impacts,
        "architecture_changes": architecture,
        "contract_changes": contracts,
        "coverage": {
            "dependency_basis": "Resolved in-root JavaScript/TypeScript import, re-export and require edges from both snapshots.",
            "limits": "Static dependency reachability only; runtime behavior, Python dependencies, dynamic resolution, and external package internals are not inferred.",
            "baseline": baseline_report["coverage"],
            "current": current_report["coverage"],
            "skipped_paths": _skipped_coverage([("baseline", baseline), ("current", current)]),
        },
    }


def render_change_impact_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# REA_APP change impact", "",
        "This report compares two explicitly selected source snapshots. Paths are relative; file hashes identify changes without including file contents.", "",
        "## Summary", "",
        f"- Added: {summary['added_files']}; removed: {summary['removed_files']}; modified: {summary['modified_files']}",
        f"- Direct dependent records: {summary['direct_dependent_records']}; transitive: {summary['transitive_dependent_records']}",
        f"- Impacted package entrypoints: {summary['impacted_entrypoint_records']}",
        f"- Syntax errors across both snapshots: {summary['syntax_errors']}", "",
        f"- Architecture: +{summary['added_modules']}/-{summary['removed_modules']} modules; "
        f"+{summary['added_internal_dependencies']}/-{summary['removed_internal_dependencies']} internal dependencies; "
        f"+{summary['added_packages']}/-{summary['removed_packages']} packages; "
        f"{summary['changed_packages']} changed package boundaries.", "",
        f"- Callable contracts: +{summary['added_contracts']}/-{summary['removed_contracts']} added/removed; "
        f"{summary['changed_contracts']} signature changes.", "",
        "## Changed files", "",
    ]
    if not report["changed_files"]:
        lines.append("No indexed file changes were observed.")
    for item in report["changed_files"]:
        lines.append(f"- `{item['status']}` `{item['path']}`")
        impact = next(entry for entry in report["impacts"] if entry["changed_path"] == item["path"])
        for kind in ("direct_dependents", "transitive_dependents"):
            for dependent in impact[kind]:
                lines.append(f"  - {kind.replace('_', ' ')}: `{dependent['path']}`")
                for edge in dependent["dependency_chain"]:
                    evidence = ", ".join(
                        f"{entry['snapshot']} `{entry['evidence']['path']}:{entry['evidence']['line']}`"
                        for entry in edge["evidence"]
                    )
                    lines.append(f"    - `{edge['from_path']}` depends on `{edge['to_path']}` ({evidence})")
        for entry in impact["impacted_entrypoints"]:
            lines.append(
                f"  - impacted entrypoint `{entry['package'] or entry['manifest_path']}` "
                f"({entry['snapshot']} `{entry['path']}`, evidence `{entry['evidence']['path']}:{entry['evidence']['line']}`)"
            )
    architecture = report["architecture_changes"]
    lines.extend(["", "## Module architecture changes", ""])
    lines.append(
        f"Baseline: {architecture['baseline']['modules']} modules, {architecture['baseline']['packages']} packages, "
        f"{architecture['baseline']['internal_dependencies']} internal dependencies. Current: "
        f"{architecture['current']['modules']} modules, {architecture['current']['packages']} packages, "
        f"{architecture['current']['internal_dependencies']} internal dependencies."
    )
    for kind in ("added", "removed"):
        for item in architecture["modules"][kind]:
            package = item["package"]
            owner = f" (package `{package['name'] or package['root']}`)" if package else ""
            lines.append(f"- {kind.title()} module `{item['path']}`{owner}.")
    for item in architecture["modules"]["package_changes"]:
        lines.append(
            f"- Module `{item['path']}` moved package boundary from "
            f"`{(item['baseline'] or {}).get('name') or (item['baseline'] or {}).get('root') or 'none'}` to "
            f"`{(item['current'] or {}).get('name') or (item['current'] or {}).get('root') or 'none'}`."
        )
    for kind in ("added", "removed"):
        for item in architecture["dependencies"][kind]:
            lines.append(f"- {kind.title()} dependency `{item['from_path']}` → `{item['to_path']}`.")
            for evidence in item["evidence"]:
                location = evidence["evidence"]
                lines.append(f"  - {evidence['kind']} evidence `{location['path']}:{location['line']}`")
    for kind in ("added", "removed"):
        for item in architecture["packages"][kind]:
            lines.append(f"- {kind.title()} package `{item['name'] or item['root']}` at `{item['root']}`.")
    for item in architecture["packages"]["changed"]:
        lines.append(
            f"- Changed package boundary `{item['root']}`: "
            f"`{item['baseline']['name'] or item['root']}` → `{item['current']['name'] or item['root']}`."
        )
    if not any((
        architecture["modules"]["added"], architecture["modules"]["removed"],
        architecture["modules"]["package_changes"], architecture["dependencies"]["added"],
        architecture["dependencies"]["removed"], architecture["packages"]["added"],
        architecture["packages"]["removed"], architecture["packages"]["changed"],
    )):
        lines.append("No module, package boundary, or resolved internal dependency changes were observed.")
    lines.append("Only bounded JS/TS source modules and resolved in-root dependency edges are compared; this is not runtime architecture discovery.")
    contracts = report["contract_changes"]
    lines.extend(["", "## Exported callable contract changes", ""])
    lines.append(
        f"Observed callable contracts: {contracts['baseline_count']} baseline, "
        f"{contracts['current_count']} current."
    )

    def format_contract(item: dict[str, Any]) -> str:
        signature = item["signature"]
        parameters = []
        for parameter in signature["parameters"]:
            label = parameter["name"] or parameter["pattern"] or "<parameter>"
            if parameter["rest"]:
                label = "..." + label
            if parameter["optional"]:
                label += "?"
            if parameter["type_annotation"]:
                label += ": " + parameter["type_annotation"]
            if parameter["has_default"]:
                label += " = <default>"
            parameters.append(label)
        prefix = "async " if signature["async"] else ""
        prefix += "generator " if signature["generator"] else ""
        result = f"{prefix}({', '.join(parameters)})"
        if signature["return_type_annotation"]:
            result += " -> " + signature["return_type_annotation"]
        if signature["export_kinds"]:
            result += " [" + ", ".join(signature["export_kinds"]) + "]"
        return result

    for kind in ("added", "removed"):
        for item in contracts[kind]:
            evidence = item["evidence"]["definition"]
            lines.append(
                f"- {kind.title()} {_inline_code(item['module'] + '::' + item['exported_as'])} "
                f"{_inline_code(format_contract(item))}; "
                f"evidence {_inline_code(evidence['path'] + ':' + str(evidence['line']))}."
            )
    for item in contracts["changed"]:
        old_evidence = item["baseline"]["evidence"]["definition"]
        new_evidence = item["current"]["evidence"]["definition"]
        lines.append(f"- Changed {_inline_code(item['module'] + '::' + item['exported_as'])}:")
        lines.append(
            f"  - baseline {_inline_code(format_contract(item['baseline']))}; "
            f"evidence {_inline_code(old_evidence['path'] + ':' + str(old_evidence['line']))}"
        )
        lines.append(
            f"  - current {_inline_code(format_contract(item['current']))}; "
            f"evidence {_inline_code(new_evidence['path'] + ':' + str(new_evidence['line']))}"
        )
    if not any((contracts["added"], contracts["removed"], contracts["changed"])):
        lines.append("No exported callable additions, removals, or observed signature changes.")
    lines.append(
        "Contract differences reflect explicitly observed syntax only. Default values and function bodies are omitted; "
        "a missing contract means it was not observed in the bounded snapshot, not a runtime compatibility verdict."
    )
    coverage = report["coverage"]
    lines.extend([
        "", "## Coverage limits", "",
        coverage["limits"],
        f"Skipped paths: {coverage['skipped_paths']['skipped_path_count']} "
        f"(showing {len(coverage['skipped_paths']['skipped_paths'])}; "
        f"truncated: {str(coverage['skipped_paths']['skipped_paths_truncated']).lower()}).",
        "",
    ])
    return "\n".join(lines)

