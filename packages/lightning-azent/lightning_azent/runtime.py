"""Lightweight independent LA API facade over the source-owned SQLite core.

All supported-v0 validation and permissions are checked before opening a
runtime/business SQLite file. This is the API boundary for future HAE use.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from .contract import PreparedPlan, capabilities, prepare_plan
from .engine import ApprovalRequired, Engine, IDENTIFIER, PlanError
from .runlog import inspect_run
from .scheduler import MAX_SCHEDULE_RUNS, interval_ticks

_WRITE_OPS = frozenset(("sqlite_put", "sqlite_import_csv"))


class LAExecutor:
    """Local-only v0 execution facade, with lazy SQLite initialization.

    Both native azent.ir.v0 and legacy axflow.ir.v0 map to identical internal
    v0 operation semantics. Do not use with customer data until release gates.
    """

    def __init__(self, state_path: Path, business_path: Path, input_root: Path | None = None):
        self.state_path = Path(state_path)
        self.business_path = Path(business_path)
        self.input_root = Path(input_root) if input_root is not None else None

    @staticmethod
    def prepare(plan: object, *, allow_legacy: bool = True) -> PreparedPlan:
        return prepare_plan(plan, allow_legacy=allow_legacy)

    @staticmethod
    def capabilities() -> dict[str, object]:
        return capabilities()

    def _new_engine(self) -> Engine:
        return Engine(self.state_path, self.business_path, input_root=self.input_root)

    def execute(self, plan: object, run_id: str, *, approve_writes: bool = False) -> object:
        prepared = prepare_plan(plan)
        normalized = prepared.runtime_plan
        if not isinstance(run_id, str) or not IDENTIFIER.fullmatch(run_id):
            raise PlanError("run_id must be a safe identifier")
        if normalized.get("trigger", {"type": "manual"})["type"] != "manual":
            raise PlanError("scheduled plans require schedule()")
        if any(step["op"] == "csv_read" for step in normalized["steps"]) and self.input_root is None:
            raise PlanError("CSV workflows require an explicit input_root")
        if not approve_writes and any(step["op"] in _WRITE_OPS for step in normalized["steps"]):
            raise ApprovalRequired("explicit SQLite write approval required")
        return self._new_engine().execute(normalized, run_id, approve_writes=approve_writes)

    def schedule(self, plan: object, schedule_id: str, *, max_runs: int = 1,
                 approve_writes: bool = False, clock=None, sleeper=None) -> Iterator[dict[str, object]]:
        """Return a lazily executing iterator; validate before DB creation on iteration."""
        prepared = prepare_plan(plan)
        normalized = prepared.runtime_plan
        if not isinstance(schedule_id, str) or not IDENTIFIER.fullmatch(schedule_id):
            raise PlanError("schedule_id must be a safe identifier")
        if normalized.get("trigger", {"type": "manual"})["type"] != "interval":
            raise PlanError("schedule requires an interval trigger")
        if isinstance(max_runs, bool) or not isinstance(max_runs, int) or not 1 <= max_runs <= MAX_SCHEDULE_RUNS:
            raise PlanError("invalid max_runs")
        if any(step["op"] == "csv_read" for step in normalized["steps"]) and self.input_root is None:
            raise PlanError("CSV workflows require an explicit input_root")
        if not approve_writes and any(step["op"] in _WRITE_OPS for step in normalized["steps"]):
            raise ApprovalRequired("explicit SQLite write approval required")
        options = {}
        if clock is not None:
            options["clock"] = clock
        if sleeper is not None:
            options["sleeper"] = sleeper
        return interval_ticks(
            normalized, self._new_engine(), schedule_id,
            max_runs=max_runs, approve_writes=approve_writes, **options,
        )

    def status(self, run_id: str) -> dict[str, object]:
        """Read-only status query; never initializes an absent runtime DB."""
        return inspect_run(self.state_path, run_id)
