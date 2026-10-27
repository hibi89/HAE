"""Render an evidence-only Mermaid architecture map from a saved REA_APP source map.

This tool never loads the analyzed project, runs source code, or consults a model.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DiagramError(ValueError):
    """The source-map's internal dependency edges are not safe to render."""


def _path(value: Any) -> str:
    if (not isinstance(value, str) or not value or len(value) > 1024 or
            value.startswith("/") or "\\" in value or "\x00" in value or
            (len(value) > 1 and value[1] == ":") or
            any(part in {"", ".", ".."} for part in value.split("/"))):
        raise DiagramError("dependency paths must be relative POSIX paths")
    return value


def _escape(value: str) -> str:
    """Use bounded, plain labels that cannot inject Mermaid statements."""
    return (value.replace("&", "&amp;").replace('"', "&quot;")
                 .replace("<", "&lt;").replace(">", "&gt;")
                 .replace("|", "&#124;").replace("[", "&#91;")
                 .replace("]", "&#93;").replace("`", "&#96;")
                 .replace("\n", " ").replace("\r", " "))


def render_architecture_mermaid(source_map: dict[str, Any]) -> str:
    if not isinstance(source_map, dict) or source_map.get("schema_version") != "rea-app-source-map/v1":
        raise DiagramError("expected rea-app-source-map/v1")
    edges = source_map.get("dependency_edges")
    if not isinstance(edges, list) or len(edges) > 50000:
        raise DiagramError("source map has missing or excessive dependency records")
    supported_kinds = {"import", "type_import", "require", "reexport", "dynamic_import"}
    internal: set[tuple[str, str, str, int]] = set()
    for edge in edges:
        if not isinstance(edge, dict):
            raise DiagramError("invalid dependency record")
        if edge.get("resolution") not in {"internal", "internal_alias"}:
            continue
        from_path, to_path = _path(edge.get("from_path")), _path(edge.get("to_path"))
        kind = edge.get("kind")
        evidence = edge.get("evidence")
        if kind not in supported_kinds or not isinstance(evidence, dict):
            raise DiagramError("missing dependency kind or evidence")
        line = evidence.get("line")
        if not isinstance(line, int) or isinstance(line, bool) or line < 1:
            raise DiagramError("invalid dependency line evidence")
        if _path(evidence.get("path")) != from_path:
            raise DiagramError("import evidence does not match source module")
        internal.add((from_path, to_path, kind, line))
    if len(internal) > 1000:
        raise DiagramError("Mermaid diagram exceeds 1000 internal edges")
    paths = sorted({path for a, b, _, _ in internal for path in (a, b)})
    if len(paths) > 500:
        raise DiagramError("Mermaid diagram exceeds 500 source modules")
    index = {path: f"n{i}" for i, path in enumerate(paths)}
    lines = ["flowchart LR"]
    for path in paths:
        lines.append(f'  {index[path]}["{_escape(path)}"]')
    for source, target, kind, line in sorted(internal):
        lines.append(f'  {index[source]} -->|"{kind} @ {line}"| {index[target]}')
    if not internal:
        lines.append('  empty["No resolved in-root JS/TS imports"]')
    return "\n".join(lines) + "\n"


def load_source_map_for_diagram(path: Path, max_bytes: int = 10_000_000) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            data = handle.read(max_bytes + 1)
    except OSError as exc:
        raise DiagramError("unable to read source-map file") from exc
    if len(data) > max_bytes:
        raise DiagramError("source-map file exceeds 10MB")
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DiagramError("invalid UTF-8 source-map JSON") from exc
    if not isinstance(parsed, dict):
        raise DiagramError("source-map must be a JSON object")
    return parsed
