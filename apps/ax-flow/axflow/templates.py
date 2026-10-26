"""Deterministic built-in workflow templates for the synthetic MVP."""
from __future__ import annotations

from .engine import PlanError, validate


def build_template(name: str, **params: object) -> dict:
    """Build one supported template and validate its native IR before returning it."""
    if name != "csv_to_sqlite":
        raise PlanError("unsupported template; available template: csv_to_sqlite")
    if set(params) != {"csv_path"} or not isinstance(params.get("csv_path"), str):
        raise PlanError("csv_to_sqlite requires only the csv_path parameter")

    plan = {
        "version": "axflow.ir.v0",
        "steps": [
            {"id": "input", "op": "csv_read", "path": params["csv_path"]},
            {"id": "imported", "op": "sqlite_import_csv", "from": "input"},
        ],
    }
    return validate(plan)
