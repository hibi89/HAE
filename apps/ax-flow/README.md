# HAE (Humanized Automation Ecosystem) — legacy `axflow` independent-runner prototype v0.1.0 (synthetic-only)

**Brand decision:** HAE replaces AX FLOW as final end-user platform name. The original Python module/CLI and folder remain unchanged pending Lightning Azent extraction; no customer-readiness claim.

**Status: verified synthetic runner, bounded request parser and localhost UI, not a customer-ready HAE product.** All work is original Python stdlib code. No n8n source, modified n8n runtime, customer data or remote API access involved.

## Selected architecture
1. Python 3 stdlib `sqlite3` + JSON IR, local CLI: cheap/install-free engine proof and deterministic tests (SELECTED).
2. Node.js workflow runner: more direct ecosystem integration for JS connectors but more dependency/runtime burden for the very first engine slice. May be revisited for adapters.

This is the baseline for Blueprint B. REA_APP remains a separate tool in `tools/rea-app/`. DBVORA remains a separate process/repository. HAE has an independent read-only client for DBVORA's versioned local SQLite inventory API; this branch's actual service integration is covered with synthetic local data below.

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
- Same-plan threaded run replay and SQLite idempotent writes are covered, but cross-process stress and parallel step scheduling are not verified. This proof does **not** establish exactly-once behavior for external APIs, transaction atomicity across arbitrary DBs, secure storage of customer data, authentication, schedule triggers, broad AI planning, OAuth, generic connectors, visible browser E2E, or Windows packaging.

## Test commands
From `apps/ax-flow/` with Python 3.11+:
```shell
python -m unittest discover -s tests -v
```
Latest full suite: Windows Python 3.11, **61/61 tests PASS**. This includes P0/P1 CLI/recovery/concurrency checks, CSV parsing/import/filter/replay, English/Korean intent recognition, localhost UI API preview/run/status for full import, filtered import, conditional import and read-only lookup, DBVORA contract validation, redirect refusal, response bounds, per-write approval, redacted receipts, bounded persistent interval ticks with injected-stop and hard-process-exit recovery plus concurrent tick deduplication, and a dependency-free zipapp CLI/UI smoke. Node syntax check for axflow/static/app.js and Python compilation also pass. A live HTTP smoke using DBVORA's unmodified `feature/p0-db-map@31b8257468d28743fb2d3767d1caa56938df756c` source inspected the synthetic business SQLite schema through HAE and confirmed its SHA-256 and mtime did not change. A visible browser E2E passes on an isolated two-row synthetic CSV: read-only lookup returns original row 2 and an approved full import stores both rows with a completed receipt. P29 reverified the current source UI with Korean task entry, generated plan, explicit write approval, a 2/2-step receipt, separate business/runtime databases, and no input values in the runtime DB. Current-source browser workflow was reverified in P29. P30 built the Windows zipapp (SHA-256 2c1f6f15af81c6cf302bd2e7f4bcb6753a2dc0b67d2126d820431b50c5964155), ran its bundled UI through explicit approval to a two-row receipt, and confirmed runtime/business DB separation and no runtime input values. Customer data and live providers remain unverified; the zipapp is not a signed installer. CI and clean third-party installs have not been run.

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

## Local interval trigger

An interval workflow uses a bounded trigger in its native IR:

```json
{"version":"axflow.ir.v0","trigger":{"type":"interval","every_seconds":60},"steps":[{"id":"source","op":"literal","value":{"source":"synthetic"}},{"id":"save","op":"sqlite_put","from":"source"}]}
```

Start it with the synthetic scheduler command and a persistent schedule ID:

```shell
python -m axflow schedule /path/to/interval-plan.json --synthetic --state /path/to/runtime.db --data /path/to/business.db --schedule-id LocalDemo --max-runs 100 --approve-writes
```

The first tick runs immediately; subsequent ticks follow the persisted one-second-to-one-day interval. `--max-runs` is required and bounded from 1 to 1000, and Ctrl+C also stops the foreground process. Runtime state records the plan hash, interval anchor and next tick. Tick run IDs are deterministic, so restarting after a process exit retries the pending tick and uses the engine's local idempotency keys. Reusing a schedule ID with a changed plan or interval fails closed. This scheduler is a local foreground process, not an OS service or cloud scheduler; it handles synthetic workflows only, and writes still require explicit approval.

## Local request UI
The localhost UI adds a narrow, deterministic English/Korean request parser for four synthetic CSV tasks: full import, one-field filtered import, import only when the filter matches, and read-only lookup of match count/original row numbers. Filters accept one explicit safe comparison; numeric thresholds use bounded numeric conversion. The lookup never returns or checkpoints matching row contents. The parser is rule-based and offline, not an LLM or general-purpose planner. Preview now parses the selected CSV through the engine's shared validator and evaluates requested normalization and filtering before returning PASS. It reports row count, column names and file size, and rejects missing files, encoding/CSV structure problems, size/row/column/cell limit violations, missing fields, and unconvertible values before approval. Preview does not instantiate the engine or create either SQLite database. The UI asks for write approval only when a plan writes SQLite, runs through the same engine, and displays redacted receipts and failure status. Upload, API and engine limits are consistently 256 KiB; the localhost service keeps a bounded temporary copy under the selected input folder and removes it when the server closes. The upload is loopback-only, capped at ten files per server session, and does not transmit data outside this PC. Its DBVORA panel can display schema/file-size metadata for the one database selected by the DBVORA service.

Each in-memory preview approval binds the request and run ID to the input SHA-256. Before a first run or incomplete-run resume, HAE reads and revalidates the source; a changed or newly invalid file invalidates the token and requires a new preview. It passes the verified byte snapshot into the engine so later file changes do not alter the content being executed. A retry of an already completed identical run returns the durable receipt without re-execution, preserving run-ID idempotency. The path check rejects symlink components and resolved paths outside the selected root. This is scoped to a user-controlled local input directory: it is not an atomic filesystem open against a hostile process concurrently replacing paths with reparse points during resolution.

Start it with an explicitly selected synthetic fixture folder and separate database paths:
```shell
python -m axflow serve --input-root "C:\axflow-demo\input" --state "C:\axflow-demo\state.db" --data "C:\axflow-demo\business.db" --synthetic --port 8765
```
Open the printed `http://127.0.0.1:8765/` URL. The input folder and database parent folders must already exist. The server binds only to `127.0.0.1`; HTTP clients cannot change the input/database paths. Preview tokens bind the request, source SHA-256 and one run ID so changed input cannot use an old approval and completed retries do not duplicate rows. Requests are same-origin, bounded to 8 KiB, and limited to 60 per minute. Stop the server with Ctrl+C. Do not use real customer files with this synthetic MVP.

### DBVORA read-only structure map

HAE calls only `GET /health` and `GET /api/inventory` from DBVORA. The base URL must be an explicit `http://127.0.0.1:<port>` origin; redirects and non-loopback hosts are rejected. Inventory responses are size-bounded, validated against `p0-01.v1`, and reduced to table/column/PK/FK, declared relationship, observed file-size, timestamp and provenance metadata. No table rows, SQL, or database path are requested or displayed. The DBVORA file itself must be selected by the separate DBVORA service; the HAE browser cannot choose an arbitrary file.

To connect, start the DBVORA API from an authorized DBVORA checkout on a different loopback port (8766 here) using a synthetic test database:
```powershell
python -m pip install -e ".[ui]"
python -c "import uvicorn; from dbvora.api import create_app; uvicorn.run(create_app(r'C:\axflow-demo\business.db', port=8766), host='127.0.0.1', port=8766)"
```

Then add `--dbvora-url http://127.0.0.1:8766` to the HAE `serve` command and press **구조 맵 새로고침** in the UI. The inspected DBVORA branch exposes an app factory but no packaged service command; the command above invokes that existing factory without changing DBVORA. The DBVORA server must be started separately. If it is absent or rejects the request, HAE shows an unavailable state. Contract and HTTP behavior are synthetic-fixture tested; an actual API smoke against a synthetic HAE business DB passed. Customer database use remains unverified and unauthorized.

## Remaining Blueprint gaps
Actual DBVORA service/customer provenance, independently verified source-preserving restore, independent security assessment, signed Windows installer, customer/release gates and broader supported scope remain open. P31 verified packaged UI wiring only against a synthetic contract stub. The local interval runner is foreground-only and has no GUI schedule editor or OS/cloud service integration. Keep customer data, OAuth, external writes and release claims blocked until authorized and independently verified.

## Local Windows zipapp package smoke

Build a standard-library-only `.pyz` from this branch, writing outside the source tree to a new file path whose parent already exists:

```powershell
python tools/package_axflow.py --output "C:\axflow-demo\axflow.pyz"
python "C:\axflow-demo\axflow.pyz" template --name csv_to_sqlite --csv contacts.csv --synthetic
```

The zipapp bundles the `axflow` Python package and its UI assets; it does not install dependencies or write to an existing artifact. `python -m unittest discover -s tests -v` builds and exercises a temporary package from outside the source tree, runs a synthetic SQLite CLI workflow, loads its localhost static UI assets, then previews and runs a synthetic import through the packaged UI API. This automated test alone proves a package/API smoke. P30 separately verified the packaged UI in a visible browser on synthetic local data. Neither result is a signed executable, installer, background service, customer-data approval or release gate.

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
### Explicit Lightning Azent development adapter

The optional `lightning-azent` backend is selected explicitly with `--engine-backend lightning-azent` on `serve`; it remains synthetic-local-only and never falls back to the HAE engine on a missing or incompatible package. Preview checks package capabilities and its plan-only preflight without opening SQLite. Run stages the exact approved CSV byte snapshot in a private temporary input root and invokes the package executor. HAE serializes attempts for a run ID across local processes using an OS lock. This does not change direct Lightning Azent package behavior for callers outside the HAE adapter; package-level cross-process audit races remain a separate reference-branch issue.

### P2 local integration: HAE → Lightning Azent → SOVIA → DBVORA

When serving with `--engine-backend lightning-azent`, optional `--sovia-root /path/to/SOVIA` calls the actual `sovia_la_observation_reconcile.reconcile()` after LA completes. The adapter passes a sanitized plan, plan-bound LA approval receipt scope, and metadata-only LA step events. The result is an **offline post-execution advisory**: SOVIA's contract explicitly reports unauthenticated evidence and `execution_authorized: false`; it is neither a real-time execution gate nor proof that an absent event did not occur. Missing or incompatible SOVIA is reported as unavailable and the overall integration is `partial`.

The audit summary is stored separately in `<state-file>.sovia-audit.sqlite`, never in the business DB and never with CSV row values. `/api/audit?run_id=...` returns the stored result; `/api/status` returns it together with a fresh DBVORA inventory when available. The audit store remains local metadata and is not authenticated against a hostile local filesystem administrator.

HAE reuses `--dbvora-url http://127.0.0.1:<port>` and its existing bounded client for the actual DBVORA `p0-01.v1` read-only inventory API. Configure that service to select the same synthetic business SQLite file HAE writes. DBVORA reports schema and measured file size; it does not inventory row data or include WAL/SHM bytes in its reported size. An unavailable DBVORA service yields an explicit partial integration result. No backup/restore interface is assumed.

The local integrated acceptance test can run when the three reference source trees are present next to HAE (or set `HAE_INTEGRATION_ROOT` to their parent):

```powershell
$env:HAE_INTEGRATION_ROOT = 'C:\hae-integration'
$env:PYTHONPATH = 'C:\hae-integration\apps\ax-flow;C:\hae-integration\packages\lightning-azent;C:\hae-integration\DBVORA'
python -m unittest tests.test_p2_integrated_e2e -v
```

That test uses only generated CSV rows and temporary SQLite files. It covers no-write preview and approval denial, malformed CSV and numeric conversion preflight, changed-input invalidation, LA execution, actual SOVIA reconciliation and persisted lookup, DBVORA's actual local API inventory, idempotent retry, and unavailable/incompatible component partial states. HAE's upload, API, and engine CSV limits remain aligned at 256 KiB; the JSON request allowance accounts for base64 and framing without raising the CSV payload limit. This does not establish a visible browser E2E, authenticated SOVIA evidence, hostile-process filesystem atomicity, customer-data readiness, or a release gate.
