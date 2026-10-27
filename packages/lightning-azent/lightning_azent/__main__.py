"""Local-only CLI for a bounded, synthetic Lightning Azent engine."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from . import __version__
from .contract import PreparedPlan, capabilities, preflight_summary, prepare_plan
from .engine import ApprovalRequired, IDENTIFIER, PlanError, StepRetryExhausted, StepTimeout, MAX_SPEC_BYTES
from .runlog import RunLogError, inspect_run
from .runtime import LAExecutor
from .scheduler import MAX_SCHEDULE_RUNS


def _unique(pairs: list[tuple[str, object]]) -> dict:
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


def _reject_constant(value: str) -> None:
    raise ValueError("non-finite JSON value is prohibited")


def _read_plan(path: Path) -> PreparedPlan:
    if not path.is_file() or path.stat().st_size > MAX_SPEC_BYTES:
        raise PlanError("plan must be an existing, bounded JSON file")
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_SPEC_BYTES:
            raise PlanError("plan exceeds the size limit")
        plan = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                          parse_constant=_reject_constant)
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        raise PlanError("plan is not valid bounded UTF-8 JSON") from exc
    return prepare_plan(plan)


def main() -> int:
    parser = argparse.ArgumentParser(prog="lightning-azent")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("command", choices=("capabilities", "validate", "preflight", "run", "resume", "status", "schedule"))
    parser.add_argument("plan", nargs="?", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--input-root", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--schedule-id")
    parser.add_argument("--max-runs", type=int, default=1)
    parser.add_argument("--approve-writes", action="store_true")
    parser.add_argument("--synthetic", action="store_true",
                        help="required for execution; real customer data is not supported")
    args = parser.parse_args()
    try:
        if args.command == "capabilities":
            if args.plan is not None:
                raise PlanError("capabilities accepts no plan argument")
            result = capabilities()
        elif args.command == "status":
            if args.plan is not None or args.state is None or args.run_id is None:
                raise PlanError("status requires --state and --run-id without a plan")
            result = inspect_run(args.state, args.run_id)
        else:
            if args.plan is None:
                raise PlanError("this command requires a plan JSON path")
            prepared = _read_plan(args.plan)
            plan = prepared.runtime_plan
            if args.command == "validate":
                result = LAExecutor.validate({**plan, "version": prepared.source_version})
            elif args.command == "preflight":
                result = preflight_summary(prepared)
            else:
                if not args.synthetic or args.state is None or args.data is None:
                    raise PlanError("execution requires --synthetic, --state and --data")
                # Validate the request before Engine.__init__ creates SQLite files.
                # Invalid identifiers/triggers/bounds must remain side-effect-free.
                trigger_type = plan.get("trigger", {"type": "manual"})["type"]
                if args.command in {"run", "resume"}:
                    if not isinstance(args.run_id, str) or not IDENTIFIER.fullmatch(args.run_id):
                        raise PlanError("run requires a safe --run-id")
                    if trigger_type != "manual":
                        raise PlanError("interval workflows require the schedule command")
                else:
                    if not isinstance(args.schedule_id, str) or not IDENTIFIER.fullmatch(args.schedule_id):
                        raise PlanError("schedule requires a safe --schedule-id")
                    if trigger_type != "interval":
                        raise PlanError("schedule requires an interval trigger")
                    if not 1 <= args.max_runs <= MAX_SCHEDULE_RUNS:
                        raise PlanError(f"--max-runs must be 1..{MAX_SCHEDULE_RUNS}")
                if args.input_root is None and any(step["op"] == "csv_read" for step in plan["steps"]):
                    raise PlanError("CSV workflows require an explicit --input-root")
                if not args.approve_writes and any(step["op"] in {"sqlite_put", "sqlite_import_csv"} for step in plan["steps"]):
                    raise ApprovalRequired("explicit --approve-writes required for local SQLite writes")
                if args.command == "resume":
                    # The facade verifies a persisted run exists before DB initialization.
                    result = LAExecutor(args.state, args.data, args.input_root).resume(
                        plan, args.run_id, approve_writes=args.approve_writes)
                else:
                    executor = LAExecutor(args.state, args.data, args.input_root)
                    if args.command == "run":
                        result = executor.execute(plan, args.run_id,
                                                approve_writes=args.approve_writes)
                    else:
                        result = list(executor.schedule(
                            plan, args.schedule_id,
                            max_runs=args.max_runs,
                            approve_writes=args.approve_writes))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
        return 0
    except (PlanError, ApprovalRequired, RunLogError, StepRetryExhausted,
            StepTimeout, OSError, ValueError, sqlite3.Error) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
