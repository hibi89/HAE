"""Concurrency contract for the independent local Lightning Azent scheduler."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import os
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import threading
import unittest

from lightning_azent.engine import ApprovalRequired, PlanError
from lightning_azent.scheduler import _schedule_lock, interval_ticks


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


    def test_separate_process_crash_releases_schedule_lock(self):
        """Prove a second process is excluded and an unclean exit frees the lock."""
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "runtime.sqlite"
            ready = Path(tmp) / "worker-ready"
            worker_code = """
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from lightning_azent.scheduler import _schedule_lock

state = Path(sys.argv[1])
ready = Path(sys.argv[2])
with _schedule_lock(SimpleNamespace(state_path=state), "SharedSchedule"):
    ready.write_text("locked", encoding="ascii")
    sys.stdin.buffer.read(1)
    os._exit(0)  # Simulates process death: no context-manager unlock call.
"""
            package = Path(__file__).resolve().parents[1]
            env = dict(os.environ)
            env["PYTHONPATH"] = str(package)
            child = subprocess.Popen(
                [sys.executable, "-c", worker_code, str(state), str(ready)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=tmp, env=env,
            )
            try:
                deadline = time.monotonic() + 5
                while not ready.is_file() and child.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(ready.is_file(), "worker did not acquire schedule lock")
                self.assertIsNone(child.poll(), "worker exited before lock contention")
                engine = SimpleNamespace(state_path=state)
                with self.assertRaisesRegex(PlanError, "already active"):
                    with _schedule_lock(engine, "SharedSchedule"):
                        self.fail("second process acquired existing schedule lock")
                # Locks are scoped by schedule ID even when sharing the same SQLite.
                with _schedule_lock(engine, "OtherSchedule"):
                    pass
            finally:
                if child.poll() is None:
                    try:
                        child.stdin.write(b"x")
                        child.stdin.flush()
                        child.wait(timeout=5)
                    except (OSError, subprocess.TimeoutExpired):
                        child.kill()
                        child.wait(timeout=5)
                child.stdin.close()
                child.stdout.close()
                child.stderr.close()
            self.assertEqual(child.returncode, 0)
            # Kernel must release the lock even though the child called os._exit.
            with _schedule_lock(SimpleNamespace(state_path=state), "SharedSchedule"):
                pass


    def test_invalid_interval_requests_do_not_create_schedule_state_or_lock(self):
        """Low-level iterator must reject unsafe requests before claiming a schedule."""
        bad_plans = (
            (
                "manual-trigger",
                {"version": "axflow.ir.v0", "trigger": {"type": "manual"},
                 "steps": [{"id": "value", "op": "literal", "value": 1}]},
                PlanError,
            ),
            (
                "no-write-approval",
                {"version": "axflow.ir.v0", "trigger": {"type": "interval", "every_seconds": 1},
                 "steps": [{"id": "value", "op": "literal", "value": 1},
                           {"id": "save", "op": "sqlite_put", "from": "value"}]},
                ApprovalRequired,
            ),
            (
                "missing-csv-root",
                {"version": "axflow.ir.v0", "trigger": {"type": "interval", "every_seconds": 1},
                 "steps": [{"id": "read", "op": "csv_read", "path": "orders.csv"}]},
                PlanError,
            ),
        )
        for name, plan, expected in bad_plans:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                engine = SimpleNamespace(state_path=Path(tmp) / "runtime.sqlite", input_root=None)
                with self.assertRaises(expected):
                    list(interval_ticks(plan, engine, "DeniedSchedule", max_runs=1,
                                        clock=lambda: 0.0, sleeper=lambda _: None))
                self.assertEqual(list(Path(tmp).iterdir()), [], "denied request left schedule files")


    def test_hardlinked_lock_does_not_mutate_other_file(self):
        """A malicious hardlink at the lock path must never modify its target."""
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "runtime.sqlite"
            victim = Path(tmp) / "original.csv"
            victim.write_bytes(b"customer-content")
            lock_file = state.with_name(
                f"{state.name}.la-{hashlib.sha256(b'SharedSchedule').hexdigest()[:16]}.lock"
            )
            os.link(victim, lock_file)
            try:
                with self.assertRaisesRegex(PlanError, "regular unlinked file"):
                    with _schedule_lock(SimpleNamespace(state_path=state), "SharedSchedule"):
                        self.fail("hardlinked path was accepted")
                self.assertEqual(victim.read_bytes(), b"customer-content")
                self.assertEqual(lock_file.read_bytes(), b"customer-content")
            finally:
                lock_file.unlink()



if __name__ == "__main__":
    unittest.main()
