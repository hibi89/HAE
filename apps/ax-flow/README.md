# AX FLOW independent runner — v0.1.0 (synthetic-only)

**Status: first executable engine slice, not a customer-ready AX FLOW product.** All work is original Python stdlib code. No n8n source, modified n8n runtime, customer data or remote API access involved.

## Selected architecture
1. Python 3 stdlib `sqlite3` + JSON IR, local CLI: cheap/install-free engine proof and deterministic tests (SELECTED).
2. Node.js workflow runner: more direct ecosystem integration for JS connectors but more dependency/runtime burden for the very first engine slice. May be revisited for adapters.

This is the baseline for Blueprint B. REA_APP remains a separate tool in `tools/rea-app/`. DBVORA is a separate process/repository; **no DBVORA connection exists yet**.

## Executable scope
- Strict `axflow.ir.v0` JSON plan validator; max 32 steps / 64KiB; allowed operations: `literal`, `field`, `map`, `condition`, `branch`, `sqlite_put`, `sqlite_get`.
- `map` supports only `identity`, `trim`, `lower`, `upper`, `number`, and scalar `string` transforms. `condition` supports typed `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, and bounded `contains` checks. `when` guards skip unselected steps and `branch` chooses one earlier result; no expression evaluation or user code execution exists.
- Runtime SQLite: `runs` and `steps` persistent status/results/receipts. Separate business SQLite: `records`, uniquely indexed by run and step for idempotent local writes.
- Step outcomes persist as `running`, `completed`, `failed`, or `skipped`; read-only `status` reports aggregate outcomes without step payloads. Existing P0 step receipts migrate to `completed`.
- No write operation without explicit `--approve-writes`. Synthetic-only CLI requires `--synthetic` and cannot call real HTTP, shells, browser or external providers.
- An injected stop **after business DB commit and before runtime receipt** is covered; re-executing the same run won't duplicate the business record. `run_id` reuse with a different IR hash is rejected.
- Same-plan threaded run replay and SQLite idempotent writes are covered, but cross-process stress and parallel step scheduling are not verified. This proof does **not** establish exactly-once behavior for external APIs, transaction atomicity across arbitrary DBs, secure storage of customer data, authentication, schedule triggers, GUI, OAuth, generic connectors, or Windows packaging.

## Test commands
From `apps/ax-flow/` with Python 3.11+:
```shell
python -m unittest discover -s tests -v
```
Latest P1 checkpoint: Windows Python 3.11, **15/15 tests PASS**. This includes existing P0 CLI/recovery/concurrency checks, IF/ELSE execution on both outcomes, mapping transforms, step-failure reporting, and migration of old receipts. CI and clean third-party installs have not been run.

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
Add an explicitly bounded retry and SQLite lock-wait timeout policy, then test a complete synthetic CSV→SQLite path. Keep runtime and business DB separate and preserve tests. A 5-week stretch plan is a target, not evidence of completion.

## 2026-10-27 — fast hackathon sprint / status-resume increment
Active user target: **3–5 days** (Oct 31 preferred), max **7-day verification** (Nov 2), limited scope; see `../../docs/SPRINT_7_DAY_HACKATHON.md`. Older plans superseded.

New supported synthetic CLI operations:
```sh
python -m axflow status --state /path/to/runtime.db --run-id Demo1 --synthetic
python -m axflow resume /path/to/plan.json --state /path/to/runtime.db --data /path/to/business.db --run-id Demo1 --approve-writes --synthetic
```
The `status` command reads the existing SQLite ledger in `mode=ro` and returns only run ID/status, aggregate step outcomes, recorded step count, plan hash and bounded error type, not input/output payload. The `resume` command reuses the existing deterministic `Engine.execute` recovery behavior and requires explicit write approval again. Both remain synthetic-only. A failed step records a failed run and error type; an interrupted post-write run can resume without duplicating its local business row. SQLite `BEGIN IMMEDIATE` serializes run claims: same run ID with a different plan is rejected, while concurrent replay of the same deterministic plan is protected by the business primary key. Threaded SQLite concurrency is tested; cross-process stress and parallel step execution are not verified.

### 2026-10-27 — P1 condition, transform and step-outcome slice
Validated plans can map fields with the fixed transform allowlist, compare values using the fixed operator allowlist, skip guarded steps, and select a prior result through an explicit branch. Tests cover both IF/ELSE paths with actual SQLite writes, failure outcome persistence, old-ledger migration, and read-only outcome counts. Runtime/business separation and explicit local write approval remain required. Retry and timeout budgets are the next atomic increment; no external API, customer data, auth or DBVORA behavior is included.

Evidence at the previous checkpoint: `axflow/runlog.py` and `tests/test_runlog.py` passed **2/2 Python tests**, with CLI status/missing-ID smoke. The current Windows verification and full suite are recorded in the latest root `STATUS.md` and `HANDOFF.md` checkpoint.
