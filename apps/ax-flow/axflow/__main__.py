"""CLI entrypoint: python -m axflow validate/run/serve."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import ApprovalRequired, Engine, PlanError, StepRetryExhausted, StepTimeout, validate
from .runlog import RunLogError, inspect_run
from .scheduler import interval_ticks
from .state_backup import StateBackupError, backup_runtime_state, restore_runtime_state
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
    p.add_argument("command", choices=("validate", "run", "resume", "status", "template", "serve", "schedule", "backup", "restore"))
    p.add_argument("plan", type=Path, nargs="?")
    p.add_argument("--name", help="built-in template name (template command)")
    p.add_argument("--csv", dest="csv_path", help="relative CSV path for csv_to_sqlite")
    p.add_argument("--state", type=Path)
    p.add_argument("--backup", type=Path, help="existing runtime ledger backup (restore command)")
    p.add_argument("--output", type=Path, help="new runtime ledger backup path (backup command)")
    p.add_argument("--data", type=Path)
    p.add_argument("--input-root", type=Path, help="explicit directory containing allowed synthetic CSV inputs")
    p.add_argument("--run-id")
    p.add_argument("--schedule-id", help="durable identifier for an interval-triggered synthetic workflow")
    p.add_argument("--max-runs", type=int, help="stop after this many due interval ticks (1-1000)")
    p.add_argument("--port", type=int, default=8765, help="loopback UI port for serve")
    p.add_argument("--dbvora-url", help="optional DBVORA loopback API origin, e.g. http://127.0.0.1:8766")
    p.add_argument("--dbvora-asset-source", type=Path,
                   help="serve only; explicit absolute synthetic SQLite path for read-only DBVORA asset verification")
    p.add_argument("--sovia-root", type=Path, help="optional local SOVIA source directory for post-execution advisory reconciliation")
    p.add_argument("--engine-backend", choices=("axflow", "lightning-azent"), default="axflow",
                   help="serve only; Lightning Azent is an explicit synthetic development backend")
    p.add_argument("--approve-writes", action="store_true")
    p.add_argument("--synthetic", action="store_true", help="mandatory: this MVP handles synthetic fixtures only")
    a = p.parse_args()
    try:
        if not a.synthetic:
            raise PlanError("MVP restricted to synthetic fixtures; include --synthetic")
        if a.command != "serve" and (a.dbvora_url is not None or a.dbvora_asset_source is not None or a.sovia_root is not None):
            raise PlanError("--dbvora-url and --sovia-root are only valid with serve")
        if a.command != "serve" and a.engine_backend != "axflow":
            raise PlanError("--engine-backend is only valid with serve")
        if a.command == "serve":
            if a.dbvora_asset_source is not None and a.dbvora_url is None:
                raise PlanError("--dbvora-asset-source also requires --dbvora-url")
            if (a.plan is not None or a.name is not None or a.csv_path is not None or a.run_id is not None or
                    a.schedule_id is not None or a.max_runs is not None or
                    a.approve_writes or a.backup is not None or a.output is not None or
                    a.input_root is None or a.state is None or a.data is None or
                    not 1 <= a.port <= 65535):
                raise PlanError(
                    "serve requires --input-root, --state, --data, --synthetic and port 1-65535; no plan or run options"
                )
            from .web import create_server

            server = create_server(
                a.input_root, a.state, a.data, port=a.port, dbvora_url=a.dbvora_url,
                dbvora_asset_source=a.dbvora_asset_source,
                synthetic_asset_allowed=a.synthetic,
                engine_backend=a.engine_backend, sovia_root=a.sovia_root,
            )
            print(f"HAE local UI ({a.engine_backend}): http://127.0.0.1:{server.server_port}/", flush=True)
            try:
                server.serve_forever(poll_interval=0.2)
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
            return 0
        if a.command == "template":
            if (a.plan is not None or a.state is not None or a.data is not None or
                    a.input_root is not None or a.run_id is not None or a.schedule_id is not None or
                    a.max_runs is not None or a.approve_writes or a.backup is not None or
                    a.output is not None or a.port != 8765):
                raise PlanError("template accepts only --name, --csv and --synthetic")
            plan = build_template(a.name, csv_path=a.csv_path) if a.csv_path is not None else build_template(a.name)
            print(json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2))
            return 0
        if a.command == "status":
            if (a.state is None or a.run_id is None or a.schedule_id is not None or a.max_runs is not None or
                    a.backup is not None or a.output is not None):
                raise PlanError("status requires --state and --run-id")
            print(json.dumps(inspect_run(a.state, a.run_id), ensure_ascii=False, sort_keys=True))
            return 0
        if a.command == "backup":
            if (a.plan is not None or a.state is None or a.output is None or a.backup is not None or
                    a.data is not None or a.input_root is not None or a.run_id is not None or
                    a.schedule_id is not None or a.max_runs is not None or a.name is not None or
                    a.csv_path is not None or a.approve_writes or a.port != 8765):
                raise PlanError("backup requires only --state, --output and --synthetic")
            result = backup_runtime_state(a.state, a.output)
            print(json.dumps({"command": "backup", "result": result}, ensure_ascii=False, sort_keys=True))
            return 0
        if a.command == "restore":
            if (a.plan is not None or a.state is None or a.backup is None or a.output is not None or
                    a.data is not None or a.input_root is not None or a.run_id is not None or
                    a.schedule_id is not None or a.max_runs is not None or a.name is not None or
                    a.csv_path is not None or a.approve_writes or a.port != 8765):
                raise PlanError("restore requires only --backup, --state and --synthetic")
            result = restore_runtime_state(a.backup, a.state)
            print(json.dumps({"command": "restore", "result": result}, ensure_ascii=False, sort_keys=True))
            return 0
        if a.backup is not None or a.output is not None:
            raise PlanError("--backup and --output are only valid with backup or restore")
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
        if a.command == "schedule":
            if (a.state is None or a.data is None or a.schedule_id is None or a.max_runs is None or a.run_id is not None or
                    a.name is not None or a.csv_path is not None or a.backup is not None or a.output is not None):
                raise PlanError("schedule requires a workflow, --state, --data, --schedule-id and --max-runs")
            engine = Engine(a.state, a.data, input_root=a.input_root)
            try:
                for tick in interval_ticks(
                    plan, engine, a.schedule_id, max_runs=a.max_runs,
                    approve_writes=a.approve_writes,
                ):
                    print(json.dumps({"schedule_id": a.schedule_id, **tick}, ensure_ascii=False, sort_keys=True), flush=True)
            except KeyboardInterrupt:
                print(json.dumps({"schedule_id": a.schedule_id, "status": "stopped"}), flush=True)
            return 0
        if a.schedule_id is not None or a.max_runs is not None:
            raise PlanError("--schedule-id and --max-runs are only valid with schedule")
        if a.state is None or a.data is None or a.run_id is None:
            raise PlanError("run requires --state, --data and --run-id")
        result = Engine(a.state, a.data, input_root=a.input_root).execute(
            plan, a.run_id, approve_writes=a.approve_writes
        )
        print(json.dumps({"run_id": a.run_id, "status": "completed", "result": result}, ensure_ascii=False, sort_keys=True))
        return 0
    except (PlanError, ApprovalRequired, StepRetryExhausted, StepTimeout, StateBackupError,
            RunLogError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"AX FLOW stopped safely: {exc}", file=sys.stderr)
        return 2


def zipapp_main() -> None:
    """Preserve CLI exit status through zipapp's imported-main wrapper."""
    raise SystemExit(main())


if __name__ == "__main__":
    raise SystemExit(main())
