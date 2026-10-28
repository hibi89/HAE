# Lightning Azent — independent engine contracts and offline conformance fixtures (DRAFT)

**2026-10-27 KST / historical design prework.** This is an ORIGINAL, independently specified behavior-contract draft derived from HAE's own `TARGET_BLUEPRINT_V1.md`, `REQUIREMENTS.md` and existing synthetic `apps/ax-flow/axflow/engine.py` source. **NOT** evidence of n8n architecture or permission to study, clone or embed n8n source. Current implementation and verification status is recorded below; design limits remain.

### Implementation update — 2026-10-28

At `hibi89/HAE/feature/lightning-azent@c85a93e2e30b0f290fad9123dcddda455be4a580`, Windows 10 build 26200 / Python 3.11.9 verification ran **65/65 LA tests**, **84/84 existing HAE tests**, and three actual local synthetic CLI flows (native run/resume, CSV filter/import/replay and interval ticks); a dedicated child-process hard exit after SQLite commit also resumed the same scheduled run without duplicating the business row. The verifier recorded **8 PASS / 0 FAIL / 1 SKIP**. Offline wheel build/install was skipped because the `wheel` module is absent. Runtime schema v2 stores transactionally scoped write-approval receipts and metadata-only run/step audit events, exposed as `azent.api.v0` capabilities plus Python/CLI audit read. Read-only comparison of the existing HAE consumer found it still imports `axflow` and has no LA package/API adapter; no HAE cutover is claimed. The following table's Unverified Azent gap column remains a design-time snapshot; use this addendum, README and exact-SHA verifier report for current implementation state.

## Boundaries
1. **REA_APP** supplies authorized source evidence and research artifacts, not a runtime dependency.
2. **Lightning Azent** will accept validated declarative plans and independently run supported operations on local synthetic inputs; no AI prose planner or GUI dependency. The existing `axflow.ir.v0` is a **compatibility fixture schema**, not an unreviewed promise that native `azent.ir.v0` already exists.
3. **HAE — Humanized Automation Ecosystem** owns end-user natural-language intake, UI, permission flow and supported broker integration. **DBVORA** remains an independent local read-only metadata/verified-recovery subsystem.
4. No unrestricted shell execution, generic network access, third-party OAuth, real customer data or silently approved writes. Every unsupported step or schema fails closed, with no write.
5. Strict version negotiation and old `axflow` compatibility facade are required before moving engine code. Never delete prior source before identical synthetic receipts/replay evidence.

## Six first-release independent behavior contracts (proposals)

| ID | Input / constraint | Required output and failure behavior | Existing local reference | Unverified Azent gap |
|---|---|---|---|---|
| LA-C01 Versioned typed IR | Exactly recognized `version`, allowed operations, earlier edge references and bounded step/spec size | Canonical version/error, reject unknown node, unknown field, cycles, duplicate IDs and nonfinite values before side effects | Native `azent.ir.v0`, legacy `axflow.ir.v0` compatibility, `capabilities()` reports `azent.api.v0` | HAE consumer negotiation and compatibility adapter not built |
| LA-C02 Deterministic data flow | Literal/map/field/condition/branch, input lineage and guarded steps | Only selected branch result propagated; skipped steps recorded, unsupported expression rejected; no arbitrary execution | `engine.py` conditional and `when` operation subset | General graph topology/merge item-lineage contract not signed |
| LA-C03 Scoped local data operations | Explicit selected input root, bounded CSV file, consent to write and separate synthetic SQLite paths | Original source unchanged; approved rows committed once; source SHA recorded; no row contents in ordinary status | `csv_read/csv_filter/sqlite_import_csv`; real Windows synthetic CLI run/replay passed | External connector registry and providers not implemented |
| LA-C04 Durable execution and replay | Stable run ID, plan fingerprint, checkpointed steps, interrupted local commit | Same run ID and plan reconstruct without duplicate local rows; conflicting plan fails; receipts redact rows; no global exactly-once claim | `engine.py`, `runlog.py`, `state_backup.py`; schema v2 approval/audit receipts and Windows full-suite proof | HAE/SOVIA consumers for the independent audit feed not connected |
| LA-C05 Trigger and bounded resource controls | Explicit manual or interval trigger (1–86400 seconds), retries/timeouts within declared bounds | Durable tick IDs, recoverable runs, no off-schedule execution; unsupported cron/webhook fail closed | `scheduler.py`, `engine.py` | Native Azent scheduler install/service lifecycle not implemented |
| LA-C06 Capability and approval boundary | Plan capability list and operation side-effect classification | Approve SQLite writes explicitly; future network/send/payment must demand separate scoped permissions; no secret in plan or log | Versioned `capabilities`, plan-hash-bound local write approvals, metadata-only audit export | Real OAuth/secret broker and network connectors not implemented |

**Contract status:** Draft only. These are our own desired semantics, not externally observed facts. Research evidence and legal-use review, then chief acceptance, are prerequisites for declaring Gate N complete.

## Three original synthetic executable-shape fixtures

Fixture root: `docs/lightning-azent/fixtures/`. JSON documents use the EXISTING legacy `axflow.ir.v0` version so they can serve as backward-compatibility tests later. They are not yet native Azent documents.

### LA-F01 — CSV filter → approved SQLite import
- Inputs: `orders.csv` contains rows (1,99,low), (2,100,edge), (3,150,high) with header `id,amount,label`; plan `csv-filter-import.json`.
- Behavior: `csv_read` → typed numeric `csv_filter(amount gte 100)` → `sqlite_import_csv`.
- Expected result: exactly **two approved imported business rows**, source contents+SHA unchanged, runtime and business SQLite separate, no approval => no writes. Replay same run ID/plan must not add duplicates. Unsupported or malformed input must fail closed.

### LA-F02 — deterministic guarded conditional branch
- Inputs: `conditional-route.json`, literal `{amount:150,label:sample}`.
- Behavior: `condition(amount gte 100)` true; `yes` guarded true, `no` guarded false, final `branch`.
- Expected result: `{route:"accepted"}`, false branch skipped with clear recorded state, **zero business writes**. A future negative variant (amount 99) must select `{route:"rejected"}`. Verify actual engine path when executable tests are available.

### LA-F03 — durable interval execution and restart
- Inputs: `interval-replay.json` specifies `trigger={"type":"interval","every_seconds":1}`, literal `{source:"synthetic"}`, `sqlite_put` and `sqlite_get`.
- Expected result: two scheduled due ticks have distinct stable run IDs and exactly two local business records; reopening same schedule advances to tick 2; interrupted tick replays its previous run ID without duplicating local writes; explicit approval mandatory. This is a **controlled test fixture**, not a production daemon.

## Evidence checklist to promote each fixture from DRAFT to PASS
- Exact GitHub **branch+SHA**, source blob fidelity to checked-out files, OS, Python/Node versions, commands and exit codes.
- Execute REA_APP Gate R current Python suite + Babel tests first; account for Windows POSIX-only SKIP and root path races honestly.
- Then run each existing legacy plan validator and engine/CLI fixture in disposable directories; compare status, SQLite counts/receipts, original source SHA and repeated/restart execution. **No consumer/business data.**
- After chief accepts original contracts, implement `packages/lightning-azent/` on separately coordinated feature branch and independently re-run all three through native Azent CLI without HAE/REA_APP installed. Run old HAE `axflow` tests to prove compatibility.
- Record failures, known limitations, unsupported n8n capabilities and rollback. Do not equate fixture existence, JSON parsing or earlier unrelated test results with PASS.

## Existing acceptance blockers / no hidden scope expansion
- REA_APP `REA_APP@33f6d345f8d4577194248eed4543d602819d3192` includes P23/P24 code that still lacks exact-current-SHA full suite confirmation.
- Current HAE feature checkpoint before this draft: `feature/axflow-mvp@c34c84afc0a21bc5e1b026068caade08262a3b06`. Prior P48/P49 full suite unexecuted, synthetic 91% estimate is not customer readiness.
- Existing HAE HTTP upload 512 KiB vs engine CSV read 256 KiB requires later cross-layer reconciliation; these small fixtures are not affected.
- n8n software/source analysis for competitive development remains subject to exact legal license/permission review. No n8n code, model-generated shell actions, third-party provider keys or new paid CI are part of this draft.
