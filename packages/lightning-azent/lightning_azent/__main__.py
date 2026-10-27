"""Local-only CLI for a bounded, synthetic Lightning Azent engine."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from .engine import ApprovalRequired, Engine, PlanError, StepRetryExhausted, StepTimeout, MAX_SPEC_BYTES, validate
from .runlog import RunLogError, inspect_run
from .scheduler import interval_ticks


def _unique(pairs: list[tuple[str, object]]) -> dict:
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


def _reject_constant(value: str) -> None:
    raise ValueError("non-finite JSON value is prohibited")


def _read_plan(path: Path) -> dict:
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
    return validate(plan)


def main() -> int:
    parser = argparse.ArgumentParser(prog="lightning-azent")
    parser.add_argument("command", choices=("validate", "run", "status", "schedule"))
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
        if args.command == "status":
            if args.plan is not None or args.state is None or args.run_id is None:
                raise PlanError("status requires --state and --run-id without a plan")
            result = inspect_run(args.state, args.run_id)
        else:
            if args.plan is None:
                raise PlanError("this command requires a plan JSON path")
            plan = _read_plan(args.plan)
            if args.command == "validate":
                result = {"valid": True, "version": plan["version"],
                          "steps": len(plan["steps"])}
            else:
                if not args.synthetic or args.state is None or args.data is None:
                    raise PlanError("execution requires --synthetic, --state and --data")
                engine = Engine(args.state, args.data, input_root=args.input_root)
                if args.command == "run":
                    if not args.run_id:
                        raise PlanError("run requires --run-id")
                    result = engine.execute(plan, args.run_id,
                                            approve_writes=args.approve_writes)
                else:
                    if not args.schedule_id:
                        raise PlanError("schedule requires --schedule-id")
                    result = list(interval_ticks(
                        plan, engine, args.schedule_id,
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
