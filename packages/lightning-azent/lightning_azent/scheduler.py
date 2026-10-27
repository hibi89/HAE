"""Durable, local interval trigger for bounded synthetic workflows."""
from __future__ import annotations

import hashlib
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Iterator

from .engine import Engine, IDENTIFIER, PlanError, canonical_json, validate

MAX_SCHEDULE_RUNS = 1000


def _open_state(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path, timeout=5, isolation_level=None)


def _ensure_schedule(engine: Engine, plan: dict, schedule_id: str, now: float) -> tuple[int, float]:
    trigger = plan.get("trigger", {"type": "manual"})
    if trigger["type"] != "interval":
        raise PlanError("schedule command requires an interval trigger")
    if not isinstance(schedule_id, str) or not IDENTIFIER.fullmatch(schedule_id):
        raise PlanError("schedule_id must be a safe identifier")

    digest = hashlib.sha256(canonical_json(plan).encode("utf-8")).hexdigest()
    with closing(_open_state(engine.state_path)) as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS interval_schedules ("
            "schedule_id TEXT PRIMARY KEY, plan_hash TEXT NOT NULL, interval_seconds INTEGER NOT NULL, "
            "anchor_time REAL NOT NULL, next_tick INTEGER NOT NULL CHECK(next_tick >= 0))"
        )
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT plan_hash,interval_seconds,anchor_time,next_tick "
            "FROM interval_schedules WHERE schedule_id=?", (schedule_id,)
        ).fetchone()
        interval = trigger["every_seconds"]
        if row is None:
            con.execute(
                "INSERT INTO interval_schedules(schedule_id,plan_hash,interval_seconds,anchor_time,next_tick) "
                "VALUES (?,?,?,?,0)", (schedule_id, digest, interval, now)
            )
            con.commit()
            return 0, now
        if row[0] != digest or row[1] != interval:
            raise PlanError("schedule_id cannot be reused with a different plan or interval")
        return row[3], row[2]


def _advance_tick(engine: Engine, schedule_id: str, tick: int) -> bool:
    with closing(_open_state(engine.state_path)) as con:
        con.execute("BEGIN IMMEDIATE")
        updated = con.execute(
            "UPDATE interval_schedules SET next_tick=next_tick+1 "
            "WHERE schedule_id=? AND next_tick=?", (schedule_id, tick)
        )
        con.commit()
        return updated.rowcount == 1


def _run_id(schedule_id: str, tick: int) -> str:
    digest = hashlib.sha256(f"{schedule_id}:{tick}".encode("utf-8")).hexdigest()
    # Engine run IDs are capped at 32 safe identifier characters.
    return "S" + digest[:31]


def interval_ticks(
    plan: object,
    engine: Engine,
    schedule_id: str,
    *,
    max_runs: int,
    approve_writes: bool = False,
    clock=time.time,
    sleeper=time.sleep,
) -> Iterator[dict[str, object]]:
    """Run due ticks. Reopening the same schedule resumes its durable tick index."""
    plan = validate(plan)
    if isinstance(max_runs, bool) or not isinstance(max_runs, int) or not 1 <= max_runs <= MAX_SCHEDULE_RUNS:
        raise PlanError(f"max_runs must be from 1 to {MAX_SCHEDULE_RUNS}")
    tick, anchor = _ensure_schedule(engine, plan, schedule_id, clock())
    interval = plan["trigger"]["every_seconds"]
    emitted = 0
    while emitted < max_runs:
        due = anchor + tick * interval
        remaining = due - clock()
        if remaining > 0:
            sleeper(min(remaining, 0.25))
            continue
        run_id = _run_id(schedule_id, tick)
        result = engine.execute(plan, run_id, approve_writes=approve_writes, interval_tick=True)
        advanced = _advance_tick(engine, schedule_id, tick)
        yield {"tick": tick, "run_id": run_id, "result": result, "advanced": advanced}
        emitted += 1
        tick, anchor = _ensure_schedule(engine, plan, schedule_id, clock())

