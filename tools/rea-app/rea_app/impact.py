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
        },
        "changed_files": changed_files,
        "impacts": impacts,
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

