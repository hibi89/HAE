# AX FLOW independent runner — v0.1.0 (synthetic-only)

**Status: first executable engine slice, not a customer-ready AX FLOW product.** All work is original Python stdlib code. No n8n source, modified n8n runtime, customer data or remote API access involved.

## Selected architecture
1. Python 3 stdlib `sqlite3` + JSON IR, local CLI: cheap/install-free engine proof and deterministic tests (SELECTED).
2. Node.js workflow runner: more direct ecosystem integration for JS connectors but more dependency/runtime burden for the very first engine slice. May be revisited for adapters.

This is the baseline for Blueprint B. REA_APP remains a separate tool in `tools/rea-app/`. DBVORA is a separate process/repository; **no DBVORA connection exists yet**.

## Executable scope
- Strict `axflow.ir.v0` JSON plan validator; max 32 steps / 64KiB; allowed operations: `literal`, `field`, `sqlite_put`, `sqlite_get`.
- Runtime SQLite: `runs` and `steps` persistent status/results/receipts. Separate business SQLite: `records`, uniquely indexed by run and step for idempotent local writes.
- No write operation without explicit `--approve-writes`. Synthetic-only CLI requires `--synthetic` and cannot call real HTTP, shells, browser or external providers.
- An injected stop **after business DB commit and before runtime receipt** is covered; re-executing the same run won't duplicate the business record. `run_id` reuse with a different IR hash is rejected.
- This proof does **not** establish concurrent/parallel execution safety, exactly-once behavior for external APIs, transaction atomicity across arbitrary DBs, secure storage of customer data, authentication, schedule triggers, branch expression engine, GUI, OAuth, generic connectors, or Windows packaging.

## Test commands
From `apps/ax-flow/` with Python 3.11+ (tested here on Linux Python 3.13.5):
```shell
python -m unittest discover -s tests -v
```
Observed: 5/5 tests PASS locally on the exact source bytes subsequently uploaded and re-read from GitHub. CI, Windows and clean third-party installs were NOT run for this engine.

For a manual synthetic demo, create a JSON file outside the repo:
```json
{"version":"axflow.ir.v0","steps":[{"id":"seed","op":"literal","value":{"title":"sample"}},{"id":"store","op":"sqlite_put","from":"seed"},{"id":"read","op":"sqlite_get","from":"store"}]}
```
Then, from `apps/ax-flow/` in an existing temporary directory:
```shell
python -m axflow validate /path/to/plan.json --synthetic
python -m axflow run /path/to/plan.json --synthetic --state /path/to/runtime.db --data /path/to/business.db --run-id Demo1 --approve-writes
```
Both database parent folders must already exist. This stores test fixture values in SQLite and is **not authorized for confidential/customer data**.

## Next slice
Fault-injection, concurrent-run lease/locking semantics, explicit plan schema/version migration, retry/timeout policy, conditions/branches, safe HTTP stub. Then validated CLI `test/status/resume` with receipts and Windows proof. Keep runtime and business DB separate and preserve tests. User's 5-week stretch plan remains a target, not evidence of completion.

## 2026-10-27 — fast hackathon sprint / status-resume increment
Active user target: **3–5 days** (Oct 31 preferred), max **7-day verification** (Nov 2), limited scope; see `../../docs/SPRINT_7_DAY_HACKATHON.md`. Older plans superseded.

New supported synthetic CLI operations:
```sh
python -m axflow status --state /path/to/runtime.db --run-id Demo1 --synthetic
python -m axflow resume /path/to/plan.json --state /path/to/runtime.db --data /path/to/business.db --run-id Demo1 --approve-writes --synthetic
```
The `status` command reads the existing SQLite ledger in `mode=ro` and returns only run ID/status, recorded step count, plan hash and bounded error type, not input/output payload. The `resume` command reuses the existing deterministic `Engine.execute` recovery behavior and requires explicit write approval again. Both remain synthetic-only. A failed step records a failed run and error type; an interrupted post-write run can resume without duplicating its local business row. SQLite `BEGIN IMMEDIATE` serializes run claims: same run ID with a different plan is rejected, while concurrent replay of the same deterministic plan is protected by the business primary key. Threaded SQLite concurrency is tested; cross-process stress and parallel step execution are not verified.

Evidence at the previous checkpoint: `axflow/runlog.py` and `tests/test_runlog.py` passed **2/2 Python tests**, with CLI status/missing-ID smoke. The current Windows verification and full suite are recorded in the latest root `STATUS.md` and `HANDOFF.md` checkpoint.
