"""Stable, independently versioned Lightning Azent local-only workflow contract."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from .engine import (
    LEDGER_SCHEMA_VERSION, MAX_CSV_BYTES, MAX_CSV_ROWS, MAX_SPEC_BYTES, MAX_STEPS,
    PlanError, VERSION as LEGACY_VERSION, validate,
)

NATIVE_VERSION = "azent.ir.v0"
SUPPORTED_VERSIONS = (NATIVE_VERSION, LEGACY_VERSION)
OPERATIONS = (
    "literal", "field", "map", "condition", "branch",
    "csv_read", "csv_normalize", "csv_filter",
    "sqlite_put", "sqlite_import_csv", "sqlite_get",
)


@dataclass(frozen=True)
class PreparedPlan:
    """Original interface version plus a validated, independent engine-format plan."""

    source_version: str
    runtime_plan: dict


def prepare_plan(plan: object, *, allow_legacy: bool = True) -> PreparedPlan:
    """Convert ONLY the explicitly recognized native/legacy IR to the same bounded core.

    Unknown versions fail closed; this is not general n8n workflow import.
    No caller-owned dictionaries are modified.
    """
    if not isinstance(plan, dict):
        raise PlanError("Lightning Azent requires a versioned JSON object")
    version = plan.get("version")
    if version == NATIVE_VERSION:
        normalized = deepcopy(plan)
        normalized["version"] = LEGACY_VERSION
    elif version == LEGACY_VERSION and allow_legacy:
        normalized = deepcopy(plan)
    else:
        raise PlanError("unsupported Lightning Azent IR version")
    validate(normalized)
    return PreparedPlan(source_version=version, runtime_plan=normalized)


def preflight_summary(prepared: PreparedPlan) -> dict[str, object]:
    """Redacted, plan-only metadata for HAE consent/configuration before execution.

    Not an execution dry-run: does not open input files, databases or connectors.
    """
    runtime = prepared.runtime_plan
    operations = [{"id": step["id"], "op": step["op"]} for step in runtime["steps"]]
    return {
        "source_version": prepared.source_version,
        "runtime_version": runtime["version"],
        "trigger_type": runtime.get("trigger", {"type": "manual"})["type"],
        "steps": operations,
        "step_count": len(operations),
        "requires_write_approval": any(step["op"] in {"sqlite_put", "sqlite_import_csv"} for step in runtime["steps"]),
        "requires_input_root": any(step["op"] == "csv_read" for step in runtime["steps"]),
        "executes_workflow": False,
        "external_connectors_supported": False,
        "scope": "synthetic-local-only",
    }


def capabilities() -> dict[str, object]:
    """Describe only capabilities implemented by the local deterministic core."""
    return {
        "product": "Lightning Azent",
        "api_version": "azent.api.v0",
        "runtime_schema_version": LEDGER_SCHEMA_VERSION,
        "audit_feed": "metadata-only.v0",
        "write_approval_receipts": True,
        "native_ir_version": NATIVE_VERSION,
        "legacy_ir_version": LEGACY_VERSION,
        "implemented_operations": list(OPERATIONS),
        "triggers": ["manual", "interval"],
        "interval_min_seconds": 1,
        "interval_max_seconds": 86400,
        "max_steps": MAX_STEPS,
        "max_spec_bytes": MAX_SPEC_BYTES,
        "max_csv_bytes": MAX_CSV_BYTES,
        "max_csv_rows": MAX_CSV_ROWS,
        "external_connectors": [],
        "requires_approval_for": ["sqlite_put", "sqlite_import_csv"],
        "not_supported": [
            "arbitrary-shell", "arbitrary-network", "oauth", "external-side-effects",
            "cron", "webhook", "n8n-node-import",
        ],
        "scope": "synthetic-local-only",
    }
