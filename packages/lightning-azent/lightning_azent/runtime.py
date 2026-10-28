"""Lightweight independent LA API facade over the source-owned SQLite core.

All supported-v0 validation and permissions are checked before opening a
runtime/business SQLite file. This is the API boundary for future HAE use.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterator

from .contract import PreparedPlan, capabilities, preflight_summary, prepare_plan
from .engine import ApprovalRequired, Engine, IDENTIFIER, PlanError, canonical_json
from .runlog import RunLogError, inspect_audit, inspect_business_ledger, inspect_completed_business_receipts, inspect_run
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
    def preflight(plan: object, *, allow_legacy: bool = True) -> dict[str, object]:
        """Return validated plan metadata without opening files or executing steps."""
        return preflight_summary(prepare_plan(plan, allow_legacy=allow_legacy))

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

    def resume(self, plan: object, run_id: str, *, approve_writes: bool = False) -> object:
        """Resume an existing manual run; never create a new run by accident.

        SQLite business receipts are idempotent for the supported local steps.
        This is not an exactly-once guarantee for external connectors.
        """
        # Ensure a matching plan and permission before touching the existing state.
        prepared = prepare_plan(plan)
        normalized = prepared.runtime_plan
        if not isinstance(run_id, str) or not IDENTIFIER.fullmatch(run_id):
            raise PlanError("run_id must be a safe identifier")
        if normalized.get("trigger", {"type": "manual"})["type"] != "manual":
            raise PlanError("schedule runs must resume through schedule()")
        if any(step["op"] == "csv_read" for step in normalized["steps"]) and self.input_root is None:
            raise PlanError("CSV workflows require an explicit input_root")
        if not approve_writes and any(step["op"] in _WRITE_OPS for step in normalized["steps"]):
            raise ApprovalRequired("explicit SQLite write approval required")
        # Match the persisted plan before Engine.__init__ opens either DB.
        # Engine.execute also checks the hash transactionally against races.
        existing = inspect_run(self.state_path, run_id)
        expected_hash = hashlib.sha256(canonical_json(normalized).encode("utf-8")).hexdigest()
        if existing["plan_sha256"] != expected_hash:
            raise PlanError("same run id cannot be reused with a different plan")
        try:
            inspect_business_ledger(self.business_path)
            inspect_completed_business_receipts(self.state_path, self.business_path, run_id, normalized)
        except RunLogError as exc:
            raise PlanError(str(exc)) from exc
        return self._new_engine().execute(normalized, run_id, approve_writes=approve_writes)

    def schedule(self, plan: object, schedule_id: str, *, max_runs: int = 1,
                 approve_writes: bool = False, clock=None, sleeper=None) -> Iterator[dict[str, object]]:
        """Validate immediately; initialize SQLite only when the iterator is consumed."""
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
        # Iterator creation is side-effect-free; actual iteration opens the ledgers.
        def scheduled_runs() -> Iterator[dict[str, object]]:
            yield from interval_ticks(
                normalized, self._new_engine(), schedule_id,
                max_runs=max_runs, approve_writes=approve_writes, **options,
            )

        return scheduled_runs()

    @staticmethod
    def validate(plan: object, *, allow_legacy: bool = True) -> dict[str, object]:
        """Validate an IR plan without creating runtime or business state."""
        prepared = prepare_plan(plan, allow_legacy=allow_legacy)
        return {
            "valid": True,
            "version": prepared.source_version,
            "runtime_compat_version": prepared.runtime_plan["version"],
            "steps": len(prepared.runtime_plan["steps"]),
        }

    def verify_receipts(self, plan: object, run_id: str) -> dict[str, object]:
        """Read-only integrity check for a persisted run and business receipts."""
        normalized = prepare_plan(plan).runtime_plan
        if not isinstance(run_id, str) or not IDENTIFIER.fullmatch(run_id):
            raise PlanError("run_id must be a safe identifier")
        try:
            existing = inspect_run(self.state_path, run_id)
        except RunLogError as exc:
            raise PlanError(str(exc)) from exc
        expected_hash = hashlib.sha256(canonical_json(normalized).encode("utf-8")).hexdigest()
        if existing["plan_sha256"] != expected_hash:
            raise PlanError("persisted run plan does not match supplied plan")
        try:
            inspect_business_ledger(self.business_path)
            inspect_completed_business_receipts(self.state_path, self.business_path, run_id, normalized)
        except RunLogError as exc:
            raise PlanError(str(exc)) from exc
        return {"run_id": run_id, "verified": True}

    def status(self, run_id: str) -> dict[str, object]:
        """Read-only status query; never initializes an absent runtime DB."""
        return inspect_run(self.state_path, run_id)

    def audit(self, run_id: str) -> dict[str, object]:
        """Read-only metadata event feed; workflow payloads and CSV rows are omitted."""
        return inspect_audit(self.state_path, run_id)
