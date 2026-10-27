"""Evidence-only functional contract export from a REA_APP source map."""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any


class ContractError(ValueError):
    """Unsupported or incomplete source-map evidence."""


def _path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ContractError("evidence must use relative POSIX paths")
    if value.startswith("/") or len(value) > 1 and value[1] == ":" or any(
        part in {".", ".."} for part in value.split("/")
    ):
        raise ContractError("evidence must remain inside the source root")
    return value


def _evidence(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError("missing path-line evidence")
    line = value.get("line")
    if not isinstance(line, int) or isinstance(line, bool) or line < 1:
        raise ContractError("invalid evidence line")
    return {"path": _path(value.get("path")), "line": line}


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 4096 or "\x00" in value:
        raise ContractError("invalid interface text")
    return value


def build_functional_contracts(source_map: dict[str, Any]) -> dict[str, Any]:
    """Produce deterministic public interface facts, never implementation bodies."""
    if not isinstance(source_map, dict) or source_map.get("schema_version") != "rea-app-source-map/v1":
        raise ContractError("expected rea-app-source-map/v1")
    raw = source_map.get("function_contracts")
    packages = source_map.get("packages")
    if not isinstance(raw, list) or not isinstance(packages, list):
        raise ContractError("missing exported contracts or package boundaries")
    if len(raw) > 10000 or len(packages) > 5000:
        raise ContractError("contract export limits exceeded")
    boundaries = []
    for item in packages:
        if not isinstance(item, dict):
            raise ContractError("invalid package metadata")
        root = item.get("root")
        boundaries.append((root if root == "." else _path(root), _optional_text(item.get("name"))))
    output = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("evidence"), dict):
            raise ContractError("invalid callable")
        definition = _evidence(item["evidence"].get("definition"))
        exported = _evidence(item["evidence"].get("export"))
        module = definition["path"]
        if exported["path"] != module:
            raise ContractError("cross-file re-export signatures are not inferred")
        params = item.get("parameters")
        if not isinstance(params, list) or len(params) > 100:
            raise ContractError("invalid callable parameters")
        parameters = []
        for param in params:
            if not isinstance(param, dict):
                raise ContractError("invalid callable parameter")
            parameters.append({
                "name": _optional_text(param.get("name")),
                "pattern": _optional_text(param.get("pattern")),
                "type_annotation": _optional_text(param.get("type_annotation")),
                "optional": bool(param.get("optional", False)),
                "rest": bool(param.get("rest", False)),
                "has_default": bool(param.get("has_default", False)),
            })
        matching = [p for p in boundaries if p[0] == "." or module.startswith(p[0].rstrip("/") + "/")]
        root, package = max(matching, key=lambda x: len(x[0])) if matching else (None, None)
        output.append({
            "module": module, "package_root": root, "package": package,
            "exported_as": _optional_text(item.get("exported_as")),
            "symbol": _optional_text(item.get("symbol")),
            "kind": _optional_text(item.get("kind")),
            "async": bool(item.get("async", False)),
            "generator": bool(item.get("generator", False)),
            "parameters": parameters,
            "return_type_annotation": _optional_text(item.get("return_type_annotation")),
            "evidence": {"definition": definition, "export": exported},
            "confidence": "explicit_syntax_only",
        })
    output.sort(key=lambda x: (x["module"], x["exported_as"] or "", x["symbol"] or "", x["evidence"]["definition"]["line"]))
    return {
        "schema_version": "rea-app-functional-contracts/v1",
        "source_map_schema": "rea-app-source-map/v1",
        "assurance": "static_syntax_evidence_only",
        "summary": {"exported_callable_contracts": len(output)},
        "contracts": output,
        "limitations": [
            "Observed interfaces only; behavior, side effects and executable replacement code are not inferred.",
            "No inferred types, source bodies, default values, dynamic dispatch or cross-file re-exports.",
        ],
    }


def render_functional_contracts_markdown(report: dict[str, Any]) -> str:
    lines = ["# REA_APP functional contracts", "",
             "Independent evidence-only interface inventory; no source implementation is reproduced.", "",
             f"Exported callable contracts: {report['summary']['exported_callable_contracts']}", ""]
    for item in report["contracts"]:
        args = []
        for p in item["parameters"]:
            name = p["name"] or "<pattern>"
            if p["rest"]:
                name = "..." + name
            if p["optional"]:
                name += "?"
            if p["type_annotation"]:
                name += ": " + p["type_annotation"]
            if p["has_default"]:
                name += " = <default>"
            args.append(name)
        signature = "(" + ", ".join(args) + ")"
        if item["return_type_annotation"]:
            signature += " -> " + item["return_type_annotation"]
        evidence = item["evidence"]
        lines.append(
            f"- {item['module']}::{item['exported_as']} {signature}; definition "
            f"{evidence['definition']['path']}:{evidence['definition']['line']}, "
            f"export {evidence['export']['path']}:{evidence['export']['line']}"
        )
    if not report["contracts"]:
        lines.append("No evidenced exported JS/TS callables.")
    lines.extend(["", "## Limitations", ""])
    lines.extend("- " + item for item in report["limitations"])
    return "\n".join(lines) + "\n"


def load_source_map(path: Path, max_bytes: int = 10_000_000) -> dict[str, Any]:
    if path.stat().st_size > max_bytes:
        raise ContractError("source map exceeds 10MB")
    with path.open("rb") as handle:
        data = handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ContractError("source map exceeds 10MB")
    try:
        report = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("invalid UTF-8 JSON source map") from exc
    if not isinstance(report, dict):
        raise ContractError("source map must be a JSON object")
    return report
