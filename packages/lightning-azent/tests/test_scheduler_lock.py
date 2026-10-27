"""Concurrency contract for the independent local Lightning Azent scheduler."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest

from lightning_azent.engine import PlanError
from lightning_azent.scheduler import interval_ticks


class SchedulerLockTests(unittest.TestCase):
    def test_same_schedule_does_not_double_execute_and_restarts_at_next_tick(self):
        plan = {
            "version": "axflow.ir.v0",
            "trigger": {"type": "interval", "every_seconds": 1},
            "steps": [{"id": "value", "op": "literal", "value": "synthetic"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "runtime.sqlite"
            entered = threading.Event()
            release = threading.Event()
            seen = []

            class FakeEngine:
                def __init__(self, *, block: bool = False):
                    self.state_path = state
                    self.block = block

                def execute(self, plan, run_id, *, approve_writes=False, interval_tick=False):
                    seen.append(run_id)
                    if self.block:
                        entered.set()
                        if not release.wait(timeout=4):
                            raise AssertionError("the blocked worker was never released")
                    return {"value": "synthetic"}

            def run(engine, now):
                return list(interval_ticks(plan, engine, "SharedSchedule", max_runs=1,
                                           clock=lambda: now, sleeper=lambda _: None))

            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(run, FakeEngine(block=True), 0.0)
                self.assertTrue(entered.wait(timeout=3), "first scheduler did not enter execution")
                second = pool.submit(run, FakeEngine(), 0.0)
                try:
                    with self.assertRaisesRegex(PlanError, "already active"):
                        second.result(timeout=3)
                finally:
                    release.set()
                one = first.result(timeout=3)

            self.assertEqual(len(seen), 1)
            self.assertEqual(one[0]["tick"], 0)
            self.assertTrue(one[0]["advanced"])
            next_tick = run(FakeEngine(), 10.0)
            self.assertEqual(next_tick[0]["tick"], 1)
            self.assertTrue(next_tick[0]["advanced"])
            self.assertEqual(len(seen), 2)
            self.assertNotEqual(seen[0], seen[1])


if __name__ == "__main__":
    unittest.main()
