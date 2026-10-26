"""CLI entrypoint: python -m axflow validate/run."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import ApprovalRequired, Engine, PlanError, validate


def main() -> int:
    p = argparse.ArgumentParser(prog="axflow")
    p.add_argument("command", choices=("validate", "run"))
    p.add_argument("plan", type=Path)
    p.add_argument("--state", type=Path)
    p.add_argument("--data", type=Path)
    p.add_argument("--run-id")
    p.add_argument("--approve-writes", action="store_true")
    p.add_argument("--synthetic", action="store_true", help="mandatory: this MVP handles synthetic fixtures only")
    a = p.parse_args()
    try:
        if not a.synthetic:
            raise PlanError("MVP restricted to synthetic fixtures; include --synthetic")
        if a.plan.stat().st_size > 65536:
            raise PlanError("workflow file exceeds 64 KiB")
        plan = json.loads(a.plan.read_text(encoding="utf-8"))
        validate(plan)
        if a.command == "validate":
            print("VALIDATED (synthetic-only)")
            return 0
        if a.state is None or a.data is None or a.run_id is None:
            raise PlanError("run requires --state, --data and --run-id")
        result = Engine(a.state, a.data).execute(plan, a.run_id, approve_writes=a.approve_writes)
        print(json.dumps({"run_id": a.run_id, "status": "completed", "result": result}, ensure_ascii=False, sort_keys=True))
        return 0
    except (PlanError, ApprovalRequired, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"AX FLOW stopped safely: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
