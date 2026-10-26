# AX FLOW independent runner — v0.1.0 (synthetic-only)

**Status: verified synthetic runner plus deterministic template, not a customer-ready AX FLOW product.** All work is original Python stdlib code. No n8n source, modified n8n runtime, customer data or remote API access involved.

## Selected architecture
1. Python 3 stdlib `sqlite3` + JSON IR, local CLI: cheap/install-free engine proof and deterministic tests (SELECTED).
2. Node.js workflow runner: more direct ecosystem integration for JS connectors but more dependency/runtime burden for the very first engine slice. May be revisited for adapters.

This is the baseline for Blueprint B. REA_APP remains a separate tool in `tools/rea-app/`. DBVORA is a separate process/repository; **no DBVORA connection exists yet**.

## Executable scope
- Strict `axflow.ir.v0` JSON plan validator; max 32 steps / 64KiB; allowed operations: `literal`, `field`, `map`, `condition`, `branch`, `csv_read`, `sqlite_put`, `sqlite_get`, `sqlite_import_csv`.
- `map` supports only `identity`, `trim`, `lower`, `upper`, `number`, and scalar `string` transforms. `condition` supports typed `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, and bounded `contains` checks. `when` guards skip unselected steps and `branch` chooses one earlier result; no expression evaluation or user code execution exists.
- `sqlite_put` and `sqlite_get` may set `max_attempts` (1–3) and `timeout_ms` (1–5000; defaults 1 and 5000). Only transient SQLite `busy`/`locked` errors retry. The retry loop owns the wait budget; it does not retry validation, payload mismatch, or arbitrary external operations. Attempt counts persist with each step.
- `csv_read` accepts a relative `.csv` path only under an explicit `--input-root`. It rejects symlink traversal, path escape, non-UTF-8, malformed rows, unsafe/duplicate headers, files over 256 KiB, more than 1000 data rows, more than 64 columns, or cells over 4096 characters. `sqlite_import_csv` writes rows atomically to the separate business DB with run/step/row idempotency keys and source SHA-256 provenance.
- CSV rows remain in memory only while a run is active. The runtime ledger checkpoints the relative path, file hash, headers and row count; resume rereads the file and refuses a changed source. Business rows remain local and the CLI is still synthetic-only.
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
Latest full suite: Windows Python 3.11, **22/22 tests PASS** at P3. This includes P0/P1 CLI/recovery/concurrency checks, both IF/ELSE outcomes, mapping transforms, held-lock retry/timeout/recovery, CSV→SQLite import and replay, and generated-template → validate → actual CLI import. Unsupported templates, unsafe paths, missing `--synthetic`, and unused template command options are rejected. CI and clean third-party installs have not been run.

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

### Synthetic CSV → SQLite
Plan:
```json
{"version":"axflow.ir.v0","steps":[{"id":"input","op":"csv_read","path":"contacts.csv"},{"id":"imported","op":"sqlite_import_csv","from":"input"}]}
```
Run with an explicit fixture directory:
```shell
python -m axflow run /path/to/csv-plan.json --input-root /path/to/synthetic-input --synthetic --state /path/to/runtime.db --data /path/to/business.db --run-id CsvDemo1 --approve-writes
```
Imported rows are stored in the local business database's `csv_records` table. Use synthetic fixtures only; this does not authorize processing confidential data.

## Deterministic built-in template
The CLI can emit validated native IR for one fixed synthetic workflow without AI or network access:
```shell
python -m axflow template --name csv_to_sqlite --csv contacts.csv --synthetic
```
The command writes JSON to stdout only. `--csv` must be a safe relative `.csv` path under the `--input-root` supplied later to `run`; import still requires `--synthetic` and `--approve-writes`. Unsupported templates and extra parameters fail closed. This is a deterministic template, not natural-language planning.

## Next slice
Compare this executable MVP against the original Blueprint V1 and close the highest-priority supported-scope gaps, then implement a local GUI and complete browser-to-engine verification. Keep runtime and business DB separate and preserve tests. A 5-week stretch plan is a target, not evidence of completion.

## 2026-10-27 — fast hackathon sprint / status-resume increment
Active user target: **3–5 days** (Oct 31 preferred), max **7-day verification** (Nov 2), limited scope; see `../../docs/SPRINT_7_DAY_HACKATHON.md`. Older plans superseded.

New supported synthetic CLI operations:
```sh
python -m axflow status --state /path/to/runtime.db --run-id Demo1 --synthetic
python -m axflow resume /path/to/plan.json --state /path/to/runtime.db --data /path/to/business.db --run-id Demo1 --approve-writes --synthetic
```
The `status` command reads the existing SQLite ledger in `mode=ro` and returns only run ID/status, aggregate step outcomes, recorded step count, plan hash and bounded error type, not input/output payload. The `resume` command reuses the existing deterministic `Engine.execute` recovery behavior and requires explicit write approval again. Both remain synthetic-only. A failed step records a failed run and error type; an interrupted post-write run can resume without duplicating its local business row. SQLite `BEGIN IMMEDIATE` serializes run claims: same run ID with a different plan is rejected, while concurrent replay of the same deterministic plan is protected by the business primary key. Threaded SQLite concurrency is tested; cross-process stress and parallel step execution are not verified.

### 2026-10-27 — P1 condition, transform, outcomes and lock-budget slices
Validated plans can map fields with the fixed transform allowlist, compare values using the fixed operator allowlist, skip guarded steps, select a prior result through an explicit branch, and cap transient SQLite lock retries with a per-step wait budget. Tests cover both IF/ELSE paths with actual SQLite writes, failure outcome persistence, old-ledger migration, read-only outcome counts, a held-lock timeout and recovery after lock release. Runtime/business separation and explicit local write approval remain required. No external API, customer data, auth or DBVORA behavior is included.

Evidence at the previous checkpoint: `axflow/runlog.py` and `tests/test_runlog.py` passed **2/2 Python tests**, with CLI status/missing-ID smoke. The current Windows verification and full suite are recorded in the latest root `STATUS.md` and `HANDOFF.md` checkpoint.
