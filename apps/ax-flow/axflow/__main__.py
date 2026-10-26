"""CLI entrypoint: python -m axflow validate/run."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import ApprovalRequired, Engine, PlanError, StepRetryExhausted, StepTimeout, validate
from .runlog import RunLogError, inspect_run
from .templates import build_template


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"unsupported JSON constant: {value}")


def main() -> int:
    p = argparse.ArgumentParser(prog="axflow")
    p.add_argument("command", choices=("validate", "run", "resume", "status", "template"))
    p.add_argument("plan", type=Path, nargs="?")
    p.add_argument("--name", help="built-in template name (template command)")
    p.add_argument("--csv", dest="csv_path", help="relative CSV path for csv_to_sqlite")
    p.add_argument("--state", type=Path)
    p.add_argument("--data", type=Path)
    p.add_argument("--input-root", type=Path, help="explicit directory containing allowed synthetic CSV inputs")
    p.add_argument("--run-id")
    p.add_argument("--approve-writes", action="store_true")
    p.add_argument("--synthetic", action="store_true", help="mandatory: this MVP handles synthetic fixtures only")
    a = p.parse_args()
    try:
        if not a.synthetic:
            raise PlanError("MVP restricted to synthetic fixtures; include --synthetic")
        if a.command == "template":
            if (a.plan is not None or a.state is not None or a.data is not None or
                    a.input_root is not None or a.run_id is not None or a.approve_writes):
                raise PlanError("template accepts only --name, --csv and --synthetic")
            plan = build_template(a.name, csv_path=a.csv_path) if a.csv_path is not None else build_template(a.name)
            print(json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2))
            return 0
        if a.command == "status":
            if a.state is None or a.run_id is None:
                raise PlanError("status requires --state and --run-id")
            print(json.dumps(inspect_run(a.state, a.run_id), ensure_ascii=False, sort_keys=True))
            return 0
        if a.plan is None:
            raise PlanError("validate, run and resume require a workflow JSON file")
        if a.plan.stat().st_size > 65536:
            raise PlanError("workflow file exceeds 64 KiB")
        plan = json.loads(
            a.plan.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
        validate(plan)
        if a.command == "validate":
            print("VALIDATED (synthetic-only)")
            return 0
        if a.state is None or a.data is None or a.run_id is None:
            raise PlanError("run requires --state, --data and --run-id")
        result = Engine(a.state, a.data, input_root=a.input_root).execute(
            plan, a.run_id, approve_writes=a.approve_writes
        )
        print(json.dumps({"run_id": a.run_id, "status": "completed", "result": result}, ensure_ascii=False, sort_keys=True))
        return 0
    except (PlanError, ApprovalRequired, StepRetryExhausted, StepTimeout,
            RunLogError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"AX FLOW stopped safely: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
