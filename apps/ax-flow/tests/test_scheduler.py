import json
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

from axflow.engine import Engine, InjectedStop, PlanError, validate
from axflow.runlog import inspect_run
from axflow.scheduler import interval_ticks


def interval_plan(every_seconds=1):
    return {"version": "axflow.ir.v0", "trigger": {"type": "interval", "every_seconds": every_seconds},
            "steps": [
                {"id": "source", "op": "literal", "value": {"source": "synthetic"}},
                {"id": "save", "op": "sqlite_put", "from": "source"},
                {"id": "read", "op": "sqlite_get", "from": "save"},
            ]}


class IntervalTriggerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "state.db"
        self.business = self.root / "business.db"
        self.engine = Engine(self.state, self.business)
        self.plan = interval_plan()

    def test_interval_trigger_bounds_and_manual_execution_guard(self):
        self.assertIs(validate(self.plan), self.plan)
        for invalid in (0, -1, 86401, True, 1.5):
            with self.subTest(interval=invalid), self.assertRaises(PlanError):
                validate(interval_plan(invalid))
        with self.assertRaises(PlanError):
            validate({**self.plan, "trigger": {"type": "cron", "expression": "* * * * *"}})
        with self.assertRaises(PlanError):
            self.engine.execute(self.plan, "MustSchedule", approve_writes=True)
        with self.assertRaises(PlanError):
            list(interval_ticks({"version": "axflow.ir.v0", "steps": self.plan["steps"]},
                                self.engine, "NotInterval", max_runs=1))

    def test_interval_cli_persists_ticks_and_resumes_after_process_restart(self):
        plan_path = self.root / "interval-plan.json"
        plan_path.write_text(json.dumps(self.plan), encoding="utf-8")
        command = [
            sys.executable, "-m", "axflow", "schedule", str(plan_path),
            "--state", str(self.state), "--data", str(self.business),
            "--schedule-id", "NightlyDemo", "--max-runs", "2", "--synthetic", "--approve-writes",
        ]
        cwd = Path(__file__).resolve().parents[1]
        first = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=15)
        self.assertEqual(first.returncode, 0, first.stderr)
        first_ticks = [json.loads(line) for line in first.stdout.splitlines()]
        self.assertEqual([item["tick"] for item in first_ticks], [0, 1])
        self.assertTrue(all(item["advanced"] is True for item in first_ticks))
        self.assertNotEqual(first_ticks[0]["run_id"], first_ticks[1]["run_id"])

        resumed_command = command.copy()
        resumed_command[12] = "1"
        resumed = subprocess.run(resumed_command, cwd=cwd, capture_output=True, text=True, timeout=15)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        third = json.loads(resumed.stdout)
        self.assertEqual(third["tick"], 2)
        self.assertEqual(inspect_run(self.state, third["run_id"])["status"], "completed")
        with closing(sqlite3.connect(self.state)) as con:
            self.assertEqual(con.execute(
                "SELECT next_tick FROM interval_schedules WHERE schedule_id='NightlyDemo'"
            ).fetchone()[0], 3)
        with closing(sqlite3.connect(self.business)) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM records").fetchone()[0], 3)

    def test_interrupted_due_tick_is_replayed_with_same_run_id(self):
        class StopAfterBusinessCommit(Engine):
            stop_once = True

            def execute(self, plan, run_id, *, approve_writes=False, interval_tick=False, **kwargs):
                if self.stop_once:
                    self.stop_once = False
                    return super().execute(
                        plan, run_id, approve_writes=approve_writes, interval_tick=interval_tick,
                        inject_stop_after_business=True,
                    )
                return super().execute(plan, run_id, approve_writes=approve_writes,
                                       interval_tick=interval_tick, **kwargs)

        with self.assertRaises(InjectedStop):
            list(interval_ticks(self.plan, StopAfterBusinessCommit(self.state, self.business),
                                "CrashSchedule", max_runs=1, approve_writes=True))
        with closing(sqlite3.connect(self.state)) as con:
            self.assertEqual(con.execute(
                "SELECT next_tick FROM interval_schedules WHERE schedule_id='CrashSchedule'"
            ).fetchone()[0], 0)
        with closing(sqlite3.connect(self.business)) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM records").fetchone()[0], 1)

        replay = list(interval_ticks(self.plan, Engine(self.state, self.business), "CrashSchedule",
                                     max_runs=1, approve_writes=True))
        self.assertEqual(replay[0]["tick"], 0)
        self.assertTrue(replay[0]["advanced"])
        with closing(sqlite3.connect(self.business)) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM records").fetchone()[0], 1)

    def test_concurrent_interval_workers_do_not_duplicate_the_due_tick_write(self):
        barrier = threading.Barrier(2)

        class SimultaneousEngine(Engine):
            def execute(self, plan, run_id, *, approve_writes=False, interval_tick=False, **kwargs):
                barrier.wait(timeout=5)
                return super().execute(plan, run_id, approve_writes=approve_writes,
                                       interval_tick=interval_tick, **kwargs)

        engines = [SimultaneousEngine(self.state, self.business) for _ in range(2)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(lambda engine=engine: list(interval_ticks(
                self.plan, engine, "RacingSchedule", max_runs=1, approve_writes=True
            ))) for engine in engines]
            results = [future.result(timeout=10) for future in futures]
        self.assertEqual([items[0]["tick"] for items in results], [0, 0])
        self.assertEqual(results[0][0]["run_id"], results[1][0]["run_id"])
        with closing(sqlite3.connect(self.state)) as con:
            self.assertEqual(con.execute(
                "SELECT next_tick FROM interval_schedules WHERE schedule_id='RacingSchedule'"
            ).fetchone()[0], 1)
        with closing(sqlite3.connect(self.business)) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM records").fetchone()[0], 1)

    def test_schedule_id_cannot_be_reused_for_a_different_workflow(self):
        list(interval_ticks(self.plan, self.engine, "PinnedSchedule", max_runs=1, approve_writes=True))
        changed = interval_plan(2)
        with self.assertRaises(PlanError):
            list(interval_ticks(changed, self.engine, "PinnedSchedule", max_runs=1, approve_writes=True))


if __name__ == "__main__":
    unittest.main()
