## Lightning Azent P2 execution gate — 2026-10-28 KST

- `feature/lightning-azent` now includes versioned `azent.ir.v0` adapter, typed LAExecutor API, lazy SQLite initialization after approved/validated request, local-only CLI, stand-alone wheel metadata, native conditional fixture and **21 unexecuted** Python unittest definitions across 3 files. No feature work on frozen REA_APP P54.
- **FIRST:** On a connected Python 3.11+ checkout, run `python -m compileall -q packages/lightning-azent`; set `$env:PYTHONPATH="packages/lightning-azent"` and run `python -m unittest discover -s packages/lightning-azent/tests -v`. Record exact branch SHA, OS, Python version, outcomes, source/input SHA. Fix only reproducing defects and rerun.
- **SECOND:** Run original `apps/ax-flow/tests` on the unchanged original HAE engine. Compare old `axflow.ir.v0` vs new `azent.ir.v0` three distinct fixtures (CSV filtered 2-row import with ID replay; branch route; interval two ticks plus restart and third tick). Assert no source CSV mutation, redacted run status, no DB file created on denial.
- **THIRD:** Install isolated `packages/lightning-azent` wheel in fresh venv and execute `lightning-azent --version`, `capabilities`, `validate`, `run`, `status`, `schedule`. Only then migrate the HAE consumer to LA native version with schema handshake and non-write preflight; preserve old HAE CLI/imports until E2E pass.
- **DO NOT:** report unexecuted tests as pass; expose shell/network/OAuth, bypass approval, merge to main or change production/customer data, use paid CI, or copy n8n source.

## LA P1b — execute source-pinned current tests, then three E2E flows (2026-10-28 KST)

- New code is on `feature/lightning-azent`. CLI preflights identifiers, trigger match, schedule bounds, and explicit SQLite write approval before Engine opens SQLite; **12 new-branch Python test definitions** exist across two files but no real execution result yet. Do not call this 12 PASS.
- On authorized Windows checkout: `git switch feature/lightning-azent; git pull --ff-only; $env:PYTHONPATH="packages/lightning-azent"; python -m unittest discover -s packages/lightning-azent/tests -v`. Then `python -m compileall -q packages/lightning-azent`, and rerun unmodified `apps/ax-flow/tests` on original source with the same interpreter.
- Validate the 3 actual synthetic paths with independent LA CLI: CSV filter->approved 2-row import and same-ID replay; guarded conditional branch; interval two-tick restart. Confirm SQLite row counts, original CSV hash, redacted receipts, valid run/schedule IDs, unsupported-node denial and no SQLite created on invalid/denied requests.
- If any failure occurs, investigate and patch just the reproducing defect; record OS/Python/runtime/commit, count PASS/SKIP/FAIL, source fixtures SHA, DB state, stdout/stderr, HAE baseline parity. Avoid docs-only churn. No HAE import migration before passing tests.
- REA_APP MVP v0.3.0 remains frozen and n8n commercial-source licensing review remains independent; do not copy n8n code or use customer data.

## Lightning Azent P1 — independently execute three offline workflows (2026-10-27 KST)

1. **Source of truth:** `feature/lightning-azent`, staged from original HAE `feature/axflow-mvp@30bb9eb979d1cd2c1180e0bcee419da60e182ed4`. Do not alter the completed REA_APP `REA_APP@3fd0ac452ea3255a24998f550aba3cbf9e6a263d` for P54 while building LA.
2. **Verify actual branch HEAD**, author/committer, new package files and exact source copy. On an authorized clean local checkout: `$env:PYTHONPATH="packages/lightning-azent"; python -m unittest discover -s packages/lightning-azent/tests -v`. Add Python compileall and three manual CLI fixture runs; identify any import, state, CLI or Windows-specific failure before coding next features. Record SHA/OS/command/count. No fake test success from static fixture existence.
3. **Test acceptance:** CSV fixture inserts exactly two rows only with approval; run ID replay adds none; original CSV SHA unchanged. Guarded branch selects accepted; interval two ticks have stable distinct IDs and no duplicate local rows after resumed tick. Unknown network/shell step, missing synthetic opt-in and missing explicit write approval must fail closed.
4. **Baseline parity:** rerun `apps/ax-flow/tests/` against unmodified original app on the same OS. No HAE import change or old engine removal until all three new flows + original compatibility are evidence-backed.
5. **Scope:** official-document research recorded at `docs/lightning-azent/RESEARCH_TO_CONTRACTS.md`; no n8n code copied, and source/legal use remains separate. Do not claim Gate N source approval or node-level parity. Preserve `axflow.ir.v0`; propose native `azent.ir.v0` only after current parity passes.
6. **Resource/permissions:** no customer data, public deployment, external connector credentials, CI billing, broad network access, DBVORA changes, or unapproved file mutation. Continue after first failed regression with a targeted minimal correction, then rerun.

## Next after draft Azent fixtures (2026-10-27 KST)
1. **Gate R first:** verify `REA_APP@33f6d345f8d4577194248eed4543d602819d3192` in authorized connected runner (Python unittest full+targeted P23/P24, Node parser pinned tests) and record source SHAs/OS/counts and Windows-specific SKIP. Do not equate file inspection with PASS.
2. Draft original generic contracts and runnable-shape fixtures exist at `docs/lightning-azent/FUNCTIONAL_CONTRACTS_DRAFT.md` and `docs/lightning-azent/fixtures/`. The three plans are in **legacy `axflow.ir.v0` only**, not an Azent implementation or validated integration. Do not advance Gate N/L from JSON parsing.
3. After permitted n8n behavior research and Gate R acceptance, review six contracts, test baseline legacy engine in a real checkout with source-preservation proof, then create standalone Azent engine branch/package only after architecture signoff.
4. HAE branding final; `hibi89/AX_FLOW` is the legacy technical repo ID. No new customer-facing UI, OAuth, commercial deployment or paid CI in this task.

## NEXT — HAE product name supersedes legacy AX FLOW (owner decision, 2026-10-27)
Use **HAE (Humanized Automation Ecosystem)** in all new customer-facing docs/UI and planning. Keep **Lightning Azent** for the independently developed workflow engine and **REA_APP** for technology analysis. Old AX_FLOW repository, axflow code/CLI/IR identifiers remain unchanged; do not silently rename any imported module, branch, package, endpoint or schema.
Continue active REA_APP → Lightning Azent → HAE acceptance order; no release or completion score changes from brand update. The remainder below is retained history/task context.

## Next — REA_APP → LIGHTNING AZENT → AX FLOW (owner 2026-10-27)
**Latest architectural order and source of truth:** `docs/LIGHTNING_AZENT_MASTER_PLAN.md`, naming/sequence adopted in `docs/DECISIONS.md` ADR-010 to ADR-012. This is the current plan; previous P49 small-feature task queue remains historical, not authorization to continue expanding AX FLOW first.

1. On `REA_APP` branch confirm exact SHA and re-run actual Python+Node parser tests on a connected executable checkout; classify FAIL/PASS/SKIP honestly. Synthetic research evidence remains local/authorized.
2. Lawfully research six bounded n8n behavior families (IR/data flow, triggers, execution state/retry, item mapping, connector permissions, credential boundaries); provide versioned, evidenced **independent functional contracts and fixtures**, no copied n8n source.
3. Chief approves Lightning Azent v0.1 contract; only then design separate `packages/lightning-azent/` (proposed, not created) and compatibility-preserving extraction from current `axflow` engine. Engine operates independently of AX FLOW/REA_APP.
4. Run real regression/Windows fail-safe & recovery, benchmark unsupported items fairly. Reconnect AX FLOW planner/UI only after engine tests pass. Preserve current hackathon-pinned synthetic code.
5. Exact P48/P49 repository full suite is unverified. No new repo, paid CI, OAuth, production hosting, customer data or n8n code transplant without owner approval.

## Next after P49 — blueprint-first validation (2026-10-27 KST)
1. **Do not repeat isolated proxy tests as a substitute for repository regression.** P49 source commit `9fe52ceea79d2251c953b0c17dcb33ce5cab0010`, test `3704eb86b2ca758432b4b104907637a61aabf150`; isolated Python stdlib opener reproduction 2/2 PASS only. P48 HTTP test also committed but unexecuted. Run actual `apps/ax-flow/` full suite + syntax + Windows loopback when an authorized source checkout/executor is available.
2. Review `docs/BLUEPRINT_CODE_AUDIT_2026-10-27.md` against frozen `TARGET_BLUEPRINT_V1.md`: limited core is present, full product gates F4/F5/D2/F6/F7/F8/B1 still open. Existing acceptance 91% heuristic not updated.
3. **Next candidate P50 (requires reviewed safe design):** make preview a read-only bounded CSV parsing/preflight, explicitly distinguish IR validation vs dry run, pin input SHA at run approval to avoid stale-source execution. Compare no-write parser proof vs disposable DB simulation; prefer minimum safe implementation. No unauthorized external actions, source mutations or secrets.
4. **Size-contract discrepancy:** HTTP upload 512 KiB but engine `MAX_CSV_BYTES` 256 KiB. Do not silently reduce user-visible capacity or raise engine memory budget. First decide compatible approved limit / resource budget; test 256/512 boundaries before claiming attached-file support.
5. Continue `feature/axflow-mvp` only. No standalone unrelated engine, public hosting, paid CI, DBVORA source edits, OAuth or real customer data. Update STATUS/HANDOFF with exact SHA/evidence after changes.

## P47 complete — reject deeply nested JSON (2026-10-27 13:37 KST)
A 1,200-level nested JSON request previously escaped the JSON parser's handled-error list and returned HTTP 500 with `RecursionError`. The parser now catches that exception and returns the bounded HTTP 400 invalid-JSON response. A new test verifies that the response contains no internal exception detail and creates no upload staging directory.

**Verification:** targeted regression 1/1 PASS; full Windows suite 81/81 PASS; Node syntax PASS; changed-file whitespace scan clean.

## Next atomic task — review remaining local gaps
Use the original blueprint and current matrix to select another locally verifiable item. Keep general AI/provider work, OAuth, DBVORA source restore, independent security approval, signed customer distribution, and standalone engine work behind their existing gates. Do not edit the shared matrix from this branch.

## P45 complete — reject a stale runtime backup
The test committed one synthetic run-status change after the backup stage was created and before the source-after fingerprint. The backup rejected the changed source, published no artifact, removed the stage, and the only business-visible row change was the injected test mutation.

## P46 complete — bounded local CSV attachment (2026-10-27 13:31 KST)
Added a file picker for one UTF-8 `.csv` file, up to 512 KiB. The loopback-only upload route accepts at most 10 files per server session, rejects unsafe names/invalid base64/non-UTF-8 data, stages a generated-name copy under the selected input folder, and deletes that staging directory when the server closes. File contents and absolute paths are not returned or logged. The existing preview and explicit SQLite write approval remain required. The standalone engine was not modified.

**Verification:** UI API suite 15/15 PASS; packaged API suite 6/6 PASS; full Windows Python suite 80/80 PASS; Node syntax PASS; changed-file whitespace scan clean.

**Failure record:** default sandbox loopback was denied with WinError 10013; the local-only test request was authorized and then passed. The test-first run found the expected absent route. An initial implementation rerun exposed test fixtures with doubled Python escapes for newlines and invalid UTF-8; those fixtures were corrected before all reruns passed.

F4 remains PARTIAL: general AI, other arbitrary attachment types, and AI repair are not implemented. The shared matrix remains 91% PARTIAL, and the engine hold and external approval gates remain in force.

## Next atomic task — review remaining safe gaps
Compare the remaining F4/F5/D2/F6/F7/F8/B1 evidence with the original blueprint. Work only on another locally verifiable item that does not require credentials, customer data, DBVORA source changes, independent security approval, signed distribution, or standalone-engine implementation. Do not edit the shared acceptance matrix from this branch.

**Verification:** targeted test 1/1 PASS in 0.366 s; full Windows Python suite **77/77 PASS** in 40.902 s with synthetic local-loopback access; Node syntax/UI provenance and whitespace/conflict audit PASS. First attempt rolled back its own fixture change because the test omitted an explicit SQLite commit; the fixture was corrected and both reruns passed. Product code was unchanged. F2 stays PASS; estimate **91% PARTIAL**.

## Next atomic task — reconcile remaining acceptance gaps
Re-read the original requirements and acceptance matrix against the current code and test evidence. Choose the next runnable, local synthetic gap only. Hold DBVORA source restore, OAuth, external credentials, independent security review, signed/customer distribution, and commercial evidence until their required authorization or evidence is available. Do not implement a standalone engine.

## P41 complete — Windows DBVORA snapshot flush boundary diagnosed
Read the exact DBVORA archive source and reproduced its staged-file read-only `fsync` failure on this Windows host (`OSError errno 9)); read/write `fsync` passed. A separate synthetic SQLite online backup and independent restore passed integrity/foreign-key/row checks with unchanged source SHA, size and mtime. This is platform diagnosis only; no product archive/restore passed and no DBVORA code changed.

The first temporary harness left a SQLite file locked because connections were not explicitly closed; the cleanup failure was fixed with `contextlib.closing`, the capability harness reran cleanly, and only its verified temp directory was removed. D2 remains NOT_STARTED. Progress remains **90% PARTIAL**.

## Next atomic task — AX FLOW runtime-ledger backup/restore
Implement the smallest local backup and fresh-path restore for the existing runtime SQLite ledger, if supported by the current CLI architecture. Require `--synthetic`, refuse pre-existing destinations, preserve source databases, and verify the restored ledger with independent integrity and run-status reads. Keep artifacts under new temporary test paths. Do not modify DBVORA or implement a standalone engine.

## P40 complete — precision-safe CSV numeric conversion
The engine now accepts bounded, exact decimal notation and rejects malformed syntax, underflow, overflow, non-finite values, unsafe integers and values that round to a different decimal. Engine, API and packaged CLI tests cover the same synthetic success/failure matrix. Invalid input is rejected before business writes, source files remain unchanged, and packaged CLI failures return code 2.

**Verification:** Windows Python 3.11.9 full suite **71/71 PASS** in 35.200 s with authorized loopback; engine suite 31/31; Node syntax/UI regression and changed-file whitespace/conflict audit PASS. Failures and recovery are recorded in STATUS. Progress remains **90% PARTIAL**.

## Next atomic task — isolated SQLite backup/restore acceptance
Inspect the existing runtime/business SQLite backup paths and the supported DBVORA snapshot contract. Work only on disposable synthetic databases and a new temporary destination. If an independently restored copy can be verified without touching the source, add the smallest test-first acceptance and record source hash/integrity. Do not retry a failed publication blindly, modify DBVORA, use real data, or implement a standalone engine; if the Windows flush gate blocks this, preserve the failure evidence and move to another safe, unblocked core gap.

## P39 complete — natural-language numeric/string normalization and zipapp exit status
Added bounded English/Korean number/string column conversion planning. The API stores valid decimal input as a numeric JSON value; malformed numeric input fails before business writes with unchanged CSV. A packaged test exposed a real reporting bug: zipapp invoked the CLI but dropped its returned exit status, so a safe failure looked successful to scripts. The package now calls a wrapper that raises `SystemExit(main())`; invalid packaged conversion exits 2 and writes no business rows.

**Verification:** Windows Python full suite **70/70 PASS** in 30.156 s with authorized synthetic loopback; Node syntax/UI regression PASS. Progress remains **90% PARTIAL**.

## Next atomic task — numeric transform boundary validation
Add a small table-driven synthetic regression across engine, API and packaged CLI for finite decimals, integer notation, exponent notation, leading/trailing whitespace, blank values, NaN/Infinity and overflow. Confirm accepted values are finite/canonical and every invalid value fails before business writes with source bytes unchanged. Make code changes only if tests expose a concrete defect. Update the test/failure record and commit.

## P38 complete — packaged normalization/import verified
The current Windows zipapp was built outside the source tree and ran a synthetic normalization → filter → SQLite import from its packaged CLI. It reported 2 imported rows and duplicate source row 2, preserved source rows [1, 2], stored both duplicates, left the CSV hash/size/mtime unchanged, and kept row values out of the runtime DB and receipt. Package tests 4/4 PASS; full suite 67/67 PASS in 28.694 s; Node checks/UI regression PASS. No listener or site remains open. Progress remains **90% PARTIAL**.

## Next atomic task — bounded type conversion in natural-language planning
Add one explicit English/Korean phrase for converting a named CSV column to number/string using the existing safe `csv_normalize` transform. Keep one column per request and require SQLite import. Test successful numeric conversion in a filter/import flow, malformed numbers failing before business writes, unsupported or ambiguous conversions failing closed, source immutability, and packaged/API execution. Run full Python and Node regressions, update acceptance evidence, then commit.

## P37 complete — concurrent same-run test configured its bounded retry budget
The cross-process regression intentionally starts two workers for one run ID. Its previous fixture used the default `max_attempts=1`, so one transient SQLite lock correctly exhausted the configured budget. The test now explicitly requests the supported bounded budget of three attempts and 5000 ms; production defaults and executor behavior are unchanged.

**Verification:** repeated the test **20 times, 20/20 PASS**; full Windows Python suite **66/66 PASS** in 28.296 s with synthetic loopback; Node syntax/UI checks and `git diff --check` PASS. Progress remains **90% PARTIAL**.

## Next atomic task — packaged CSV normalization workflow
Build the current stdlib Windows zipapp into a new temporary folder, run a synthetic CSV normalization → filter → SQLite workflow using the packaged CLI, and verify the duplicate receipt, preserved source hash/row numbers, separate DBs, runtime redaction, and cleanup. No browser site, signing, external login, customer data or deployment is needed. Do not overwrite existing artifacts.

## P36 complete — DBVORA Windows synthetic archive capability check
Read and hash-verified the pinned DBVORA archive CLI/source, then invoked its snapshot command on a disposable synthetic SQLite source in separate output directories. The source SHA-256, size and mtime were unchanged; no snapshot was published. The CLI returned exit 2, `PUBLISH_FAILED`, “Staged artifact could not be flushed safely.” Since the snapshot stage could not publish, no archive/restore command was run and D2 remains NOT_STARTED. The CLI did not reveal a lower-level OS error; do not guess one. Windows/NTFS is not covered by DBVORA's recorded Linux synthetic pass.

P36 temporary source and fixture were removed. Six old synthetic log files under the prior `.verification-temp` tree remain locked despite no visible listener/Python process; process-level inspection was denied by CIM, so no process was killed. No site needs to remain open. Progress remains **90% PARTIAL**.

## Next atomic task — reproduce the cross-process same-run lock case
The AX FLOW full suite passed 66/66, but one targeted run of `test_cross_process_same_run_replay_is_idempotent` reached the configured SQLite busy cap once; its isolated rerun and final full suite passed. Reproduce this against the current committed source with a synthetic repeatable harness, identify whether concurrent step execution can produce a legitimate bounded failure, then make the smallest fix that preserves idempotency and failure reporting. Add a deterministic regression that proves the chosen contract and run the complete suite. Do not hide the race by only changing the expected result or relaxing the assertion.


## P35 complete — bounded CSV normalization and duplicate reporting
Added a fail-closed, validated single-column normalization step and a narrow English/Korean planner path. The flow keeps rows in memory, preserves original row numbers and source SHA-256, reports exact duplicate rows after transformation, retains rather than deletes them, and never writes row payloads into runtime receipts. Normalization can precede filtering and SQLite import. Failure tests prove invalid numeric conversions stop before business writes; restart tests prove replay remains idempotent.

**Verification:** Windows Python 3.11.9 full suite **66/66 PASS** in 28.609 s with authorized synthetic loopback. Node syntax checks, UI provenance regression, and package tests PASS. Source CSV hashes remained unchanged. P35 raises the heuristic estimate to **90% PARTIAL** (A100/B95/C95/D95/E65); no customer or release gate closes.

Failure record: an old exact-result assertion initially omitted the new duplicate summary fields and was corrected. The cross-process SQLite busy-cap test failed once in a targeted engine run, but an isolated rerun and the final full suite passed. P34's visible browser attempt was skipped before navigation because the Windows helper could not verify the current URL; no site needs to remain open.

## Next atomic task — inspect and test synthetic DBVORA backup/restore
Read the pinned `hibi89/DBVORA` `feature/p0-db-map@31b8257468d28743fb2d3767d1caa56938df756c` source and existing operator instructions for a supported local backup/restore command. Do not change DBVORA source. If the workflow runs without additional approval or external authentication, create disposable synthetic SQLite source, backup and restore copies under a temporary folder and verify restored schema/data/FKs plus unchanged source SHA/size/mtime. Exercise corruption/restart checks only when the supported interface permits them. Never restore over an original or customer path. If Windows/host support or permissions block the operation, stop and record the exact cause; do not repeat the denied WSL/Docker setup. No website is needed.

## P33 complete — packaged AX FLOW connected to actual DBVORA
Built a 32,191-byte Windows zipapp (SHA-256 `7b29c766c26a331cf0bef88c20120be950a00f72712653d8a20ac0cfcea1b6df`) from the current remote AX FLOW source. Its packaged local server read a synthetic database through the exact DBVORA `feature/p0-db-map@31b8257468d28743fb2d3767d1caa56938df756c` API. Table/FK metadata arrived; row markers and paths did not; POST was rejected; source hash/size/mtime stayed fixed. Packaged UI assets served. All test services, package, source copy and fixture were removed; no TCP connection remains.

**Progress: 89% PARTIAL** (A100/B95/C95/D95/E60). No product source changed. The full Python suite remains P32's 61/61 PASS.

## Next
D2 archive/restore remains the clearest safe acceptance gap, but it was not run: WSL returned `E_ACCESSDENIED`, and the DBVORA HTTP service exposes read-only operations. Do not test on customer data or pretend the API offers restore. Continue other permission-free code/verification gaps; OAuth, independent review, signed/customer release and commercial proof retain their gates. No site needs to remain open.

## P32 complete — actual DBVORA source/API integration
On AX FLOW `feature/axflow-mvp`, the current 61-test Python suite and Node provenance regression passed. A temporary synthetic SQLite fixture with a declared FK was served by the exact DBVORA `feature/p0-db-map@31b8257468d28743fb2d3767d1caa56938df756c` API, then read through AX FLOW's `/api/dbvora`. FK metadata arrived; row markers and source paths did not; DBVORA rejected POST; the source file hash/size/mtime were unchanged and no WAL/SHM appeared. Local browser/API test resources were removed. **Progress remains 88% PARTIAL.**

Failure record: default sandbox loopback tests failed with WinError 10013 (9 failures/10 errors); authorized loopback rerun passed 61/61. Temporary integration-harness path, import-root, future-import ordering and retained SQLite handle errors were fixed; final integration passed and cleaned up. WSL status returned `E_ACCESSDENIED`, so D2 archive/restore was not run on an unsupported Windows filesystem.

## Next
Continue with one distinct permission-free acceptance gap. D2 remains unverified until a supported synthetic-only archive/restore run is available; do not use a customer DB or claim restore from a stub. OAuth, customer/release, independent review and commercial checks retain their explicit gates. No extra website needs to be left open.

## P31 complete — packaged DBVORA provenance and offline state
A temporary Windows zipapp connected only to a synthetic loopback contract stub. Packaged UI/API safely displayed the allowlisted provenance and table metadata; injected paths/markup were absent. After taking the stub offline, the UI showed offline state and cleared provenance/tables/relations. Temporary processes, tab, artifact and fixtures were removed. **88% PARTIAL** remains; this does not prove actual DBVORA installation/customer behavior or restore.

## Remaining work boundary
Before starting the next item, compare the acceptance matrix for a distinct permission-free gap. D2 restore, F5 OAuth consent, F7 independent review, F8 signed/customer release and B1 commercial validation require their stated owner/external prerequisites; do not simulate their acceptance with a synthetic stub.

## P30 complete — Windows zipapp browser workflow
The built zipapp (SHA-256 `2c1f6f15af81c6cf302bd2e7f4bcb6753a2dc0b67d2126d820431b50c5964155`) completed the synthetic browser flow with explicit write approval and a 2/2-step, 2-row receipt. Read-only checks confirmed separate business/runtime SQLite files and no input data in runtime storage. Temporary package, server, browser tab and fixture were removed; port 8774 is closed. A–E estimate is **88% PARTIAL** (A100/B95/C95/D95/E55).

## Next atomic task — packaged provenance via synthetic contract stub
If continuing, run the packaged UI against a loopback-only synthetic DBVORA API fixture and verify the provenance labels and offline state. Do not change DBVORA source or use a customer database; keep restore and external consent gated.

## P29 complete — current-source browser workflow replay
The visible browser ran a Korean natural-language CSV request through preview and explicit write approval to a completed 2-row SQLite receipt. Separate DB integrity check confirmed exact business rows and no input values in runtime storage. The temporary loopback server, tab, fixture and port were cleaned up. P27 remains the latest full Python suite at 61/61. A–E progress remains **87% PARTIAL**; P16/P19 already verified this bounded Blueprint C requirement.

## Next atomic task — packaged Windows browser flow
Build the existing stdlib zipapp outside the source tree, launch it on a fresh loopback port using a disposable synthetic CSV, and verify the same preview → approval → completed receipt in a temporary browser tab. Check DB separation and clean up the tab/server/fixture. Do not sign or install it as a customer package.

## P28 complete — UI provenance disclosure and offline clearing
Commit `99058617d8b35806b02be41a84fcd7ec5bee1c66` shows the allowlisted “CPU 사용량: 제공되지 않음” state and clears previous provenance after an offline refresh. The actual `app.js` passed an isolated Node VM DOM regression for safe rendering, path/markup suppression, and offline clearing; both JS syntax checks passed. Python full suite remains at P27's 61/61 PASS. Progress remains **87% PARTIAL**.

## Next atomic task
Continue by selecting one remaining permission-free, synthetic Blueprint acceptance gap and actually verifying it. Keep DB restore, OAuth, customer data, independent review, signing/release, and independent engine expansion on hold unless the required approval is provided. No new design document or website is needed.

## P27 complete — provenance API/UI boundary verified
Code/test commit `e4cf683ce061645ee5400b7eb0e6f7f8fd45888e` allowlists DBVORA provenance at the adapter and renders fixed safe descriptions in the browser. Windows Python suite **61/61 PASS**; JS syntax PASS. An isolated synthetic API/UI check confirmed customer-like paths and hostile markup are omitted, with no injected DOM node. Failure causes and recovery are recorded in STATUS/HANDOFF. Progress remains **87% PARTIAL**.

## Next atomic task — continue only with a permission-free Blueprint gap
Compare the remaining acceptance rows with the original blueprint and code, pick a synthetic local test that closes evidence, then run it and record the actual outcome. Do not access customer data, create OAuth consent, restore DBs, request elevation, sign/release, deploy publicly, or expand the independent engine. No new design document or open website is needed; P5 at `http://127.0.0.1:8767/` remains open.

## P26 complete — Windows junction fixture could not be created
An unprivileged PowerShell directory-junction attempt returned Access is denied before link creation. AX FLOW did not run; the synthetic target stayed intact and no DB write occurred. Fixture cleanup passed. Do not elevate. This is SKIPPED, not an acceptance pass. P20's file-symlink creation was separately denied with WinError 1314. Progress remains **87% PARTIAL**.

## Next atomic task — identify a permission-free Blueprint gap
Use the existing TARGET_BLUEPRINT_V1 and ACCEPTANCE_MATRIX to select one remaining acceptance that needs no customer data, OAuth, DBVORA write/restore, deployment, signing, independent security approval, OS elevation, or new design document. Run its actual synthetic test, record failures and causes, then update STATUS/HANDOFF/NEXT_TASK and commit.

## P25 complete — full synthetic AX FLOW suite passes
Windows Python 3.11.9: python -m unittest discover -s tests -v from apps/ax-flow — **60/60 PASS** in 25.384 seconds with loopback permission enabled. The default-sandbox attempt had 9 failures / 10 errors: WinError 10013 blocked loopback mocks/UI; seven DBVORA assertions therefore saw UNAVAILABLE. Cross-process replay also hit its SQLite busy cap once, then passed on rerun. No source changed. See STATUS/HANDOFF for the full failure record. Progress remains **87% PARTIAL**.

## Next atomic task — Windows reparse-point boundary probe
Try a directory junction fixture in a temporary synthetic input root without elevation, then run the existing CSV path guard against a CSV reachable only through that junction. Verify it refuses before any business DB write. If the OS refuses fixture creation, record the exact error and mark SKIPPED; do not elevate or change OS policy. Keep P5 open and unchanged. Update the acceptance matrix only if the evidence changes a row.

## P24 complete — DBVORA FK relationship verified in isolated UI
The current AX FLOW UI was connected to a separate synthetic SQLite database through the pinned DBVORA read-only API. The browser rendered employees.department_id → departments.id, and the FK persisted after schema-map refresh. API/UI redaction assertions passed; the database hash and mtime did not change and no WAL/SHM files were created. Both test servers and the synthetic DB were removed. P5 at http://127.0.0.1:8767/ remains open and unchanged. See STATUS/HANDOFF for exact source SHAs and evidence. Tracking estimate: **87% PARTIAL** (A100/B95/C95/D95/E50).

## Current boundary — evidence matrix and gated release items
The acceptance matrix had become stale and reported every test as NOT RUN; it is being reconciled with P17–P24 and the REA_APP P22/P23 evidence. Current strict release status is **PARTIAL**, not customer-ready. D2 source-preserving restore, OAuth consent, customer/security validation, signed Windows distribution and commercial proof remain unstarted or approval-gated. Keep independent AX FLOW engine implementation on hold pending chief review. No new design document is needed.

## Next atomic task
After the evidence matrix update is committed, select one permission-free verification gap against the original blueprint, use only synthetic local fixtures, run the relevant real test, capture any failure and cause, then update STATUS/HANDOFF/NEXT_TASK and commit. Avoid broadening scope; do not touch customer data, credentials, DBVORA writes/restore, public deployment, signing, or independent security certification without approval.

## P23 complete — REA_APP self-scan is deterministic and read-only
Two scans of `tools/rea-app` itself indexed 12 files, found 6 dependency edges and had no syntax errors. JSON and Markdown reports were byte-identical, and a full source-tree SHA-256 stayed unchanged. Reports and fixtures were removed without upload. Python tests 11/11 and Node parser tests passed in P22.

## Current boundary — approval-gated full-product release evidence
Current product tracking remains **86% / PARTIAL**. The remaining work is not represented as complete: independently verified DBVORA source-preserving restore, independent security assessment, signed Windows distribution and customer/release evidence. Hold those until their owner approvals are available, and keep independent AX FLOW engine implementation on hold for chief review. No additional design document is needed. The P5 DBVORA preview remains open at `http://127.0.0.1:8767/`.

## P22 complete — REA_APP branch and bounded analyzer checks passed
Remote `REA_APP@1409d9d383e1515a1c19350252a1c7a6f534d04d`: Python tests **11/11 PASS**, Node parser assertions PASS. Two independent synthetic CLI scans emitted the same JSON and Markdown, indexing 3 files with 1 import edge and 0 syntax errors. All code/test blobs match remote; the local package-lock JSON is semantically identical despite a trailing newline difference. The local checkout has no Git commit; do not claim local HEAD.

## Next atomic task — analyze REA_APP source with itself
Run the bounded scanner on `tools/rea-app` itself, placing reports outside that selected source root. Capture file hashes before and after, confirm no source mutation, and verify deterministic JSON/Markdown across separate output directories. The project is user-authorized and the scanner is read-only; do not upload its report. No new website is needed; keep the connected P5 view open at `http://127.0.0.1:8767/`.

## P21 complete — configured DBVORA offline state is clear and bounded (2026-10-27 KST)
A separate synthetic UI pointed at a confirmed-closed loopback DBVORA port. It reported the service unavailable and how to retry; no table metadata, database/CSV content, path, run receipt or local database file appeared. The connected P5 preview was left untouched. Test server and synthetic fixtures were removed. Progress advances to **86% / PARTIAL** (A100/B95/C95/D90/E50).

A first port probe had a one-line syntax typo; the corrected probe confirmed the port was closed. This was a harness typo, not a product failure.

## Next atomic task — re-verify the REA_APP bounded MVP on its branch
Fetch the exact `REA_APP` branch head, confirm the local analyzer source matches, run its Python and Node tests, and exercise deterministic JSON/Markdown output on the synthetic fixture. Record only source-backed behavior and verify the source root remains unchanged. No additional website is needed; keep the P5 DBVORA review at `http://127.0.0.1:8767/` open. Then perform a concise A–E evidence audit. Do not elevate the blocked symlink test or perform restore, customer-data, OAuth, public-release or independent-engine work without its existing approval.

## P20 complete — Windows symlink fixture blocked by OS privilege (2026-10-27 KST)
Unprivileged Python `Path.symlink_to` failed with `OSError [WinError 1314]`, so no link was created and AX FLOW did not run. The synthetic fixture was removed. Do not elevate for this check. Normal path traversal and absolute-path preview rejection passed in P19; real symlink traversal remains SKIPPED.

## Next atomic task — DBVORA unavailable-state UI acceptance
Run an isolated synthetic AX FLOW UI with `--dbvora-url` set to a closed loopback endpoint. Confirm the panel explicitly reports unavailable state, remains bounded, and does not leak file paths or row contents. Do not alter the connected P5 preview at `http://127.0.0.1:8767/`. Stop the temporary server and remove its fixture after verification. Then update STATUS/HANDOFF/NEXT_TASK; no app source change unless a reproducible defect is found.

## P19 complete — UI rejects unsupported requests and path escape (2026-10-27 KST)
In an isolated synthetic browser run, an unsupported email request was rejected with no run receipt and a disabled run button. Traversal (`../escape.csv`) and an absolute Windows path were rejected during preview. No runtime/business database appeared and no run was invoked. Full Windows Python 3.11.9 suite: **60/60 PASS** with localhost permission.

The first restricted server process printed its ready message but was unreachable from the browser; restarting it with local loopback permission resolved the issue. This was sandbox networking, not a product failure. The P19 server was stopped and its synthetic fixture folder removed. Progress remains **84% / PARTIAL**.

## Next atomic task — real Windows symlink boundary check
Attempt to create an unprivileged symlink fixture inside a temporary synthetic input root and verify that AX FLOW refuses to traverse it before any business write. If the OS denies link creation, record the exact privilege error and leave the check SKIPPED; do not elevate or alter OS policy. Then continue permission-free Blueprint gaps. No new website is needed; keep the P5 DBVORA review at `http://127.0.0.1:8767/` open.

## P18 complete — four bounded CSV intents verified through the local UI (2026-10-27 KST)
Filtered import saved 2 synthetic rows; lookup returned one match at source row 1 without row values; conditional import saved 2; no-match conditional saved 0. The full import and DBVORA-linked schema/refresh flow are recorded in P17. Write flows remained disabled without explicit synthetic-data approval. Full Windows Python 3.11.9 suite: **60/60 PASS** with loopback permission.

The first sandboxed suite attempt was blocked by localhost socket policy (WinError 10013; 8 failures/10 errors); the exact rerun with loopback permission passed. Conditional receipts correctly show one skipped mutually exclusive branch (5 completed / 6 total). The isolated port 8768 server is stopped; synthetic fixture and DB files were removed, but its small captured logs are still held open.

A–E heuristic: **84%** (A100/B95/C95/D80/E50); product remains PARTIAL. No user-visible site needs to be opened for the next task; keep the P5 review panel at `http://127.0.0.1:8767/` open.

## Next atomic task — fail-closed planner/UI acceptance
Run an isolated synthetic browser check for (1) an unsupported task and (2) absolute/traversal CSV paths. Confirm the UI displays bounded actionable errors, does not enable or produce a run receipt, and leaves the synthetic business DB unchanged. Use a separate temporary fixture/server; do not disturb the open P5 review. If all checks pass, run the full suite and update STATUS/HANDOFF/NEXT_TASK. Fix code only if a reproducible defect is found and within the current authorization. Continue to hold customer data, OAuth, external writes, DBVORA restore/release, and independent-engine expansion behind their review/approval gates.

## Latest verified fix — Windows CLI help encoding (2026-10-27 KST)
On `feature/axflow-mvp@86ac854bd633e3a312aa54a5300e2f78f634dbfd`, default CP949 Windows console help now prints successfully after replacing two U+2013 characters with ASCII hyphens. Both `python -m axflow --help` and `python -m axflow serve --help` pass. The full Windows Python 3.11.9 suite is **60/60 PASS** with permitted loopback tests. The first failure was a real help-output encoding defect; no execution logic changed. Overall remains PARTIAL at the existing 79% heuristic.

## P17 complete — source-backed DBVORA schema visible in AX FLOW (2026-10-27 KST)
The synthetic CSV→SQLite workflow wrote two rows; the actual pinned DBVORA source read that business DB, and AX FLOW's visible local panel rendered its table, columns/PKs and measured size. Refresh passed. The API/UI withheld row values and source path; DB hash/mtime stayed unchanged. No declared FK exists in this import schema, so the UI accurately showed none. The full Windows Python 3.11.9 suite remains **60/60 PASS**.

A first service attempt started before the synthetic DB existed and returned expected `FILE_UNAVAILABLE`; a hyphenated run ID was safely refused before writes. Fixture-first startup and an underscore-only run ID passed. Overall readiness is **83% PARTIAL** on A100/B95/C90/D80/E50 (equal weights); this replaces the previous 79% estimate. The chief-review hold on new independent-engine work remains active.

**Keep open:** AX FLOW + DBVORA synthetic panel `http://127.0.0.1:8767/`; previous P16 review site `http://127.0.0.1:8765/`.

## P10 complete — interval hard-crash replay (60/60 full-suite pass)

## P16 — local UI read-only and import E2E verified
The visible local UI now completes both a read-only lookup and a write-approved synthetic import. Querying `id=2` returned one match at original row 2 with row contents withheld. The approved import of the same two-row fixture returned a completed receipt (2/2 steps, 2 saved rows); a separate SQLite query confirmed stored row numbers 1 and 2. The UI guard bug that required write approval even for read-only plans is fixed.

Python full suite **60/60 PASS** with authorized loopback permission; `node --check axflow/static/app.js` PASS. Default-sandbox localhost tests initially failed from WinError 10013; the permitted rerun passed. A duplicate stale synthetic server on port 8765 caused a one-row mismatch; only the isolated two-row server remains. Progress heuristic is **79% / PARTIAL** (A100/B95/C90/D60/E50). DBVORA live linkage, restore, customer data, security review, signed installer, and customer/release evidence remain open. The standalone AX FLOW engine remains on hold for chief review.

**Next:** attempt the permitted DBVORA read-only browser linkage only with the actual separate service/source; otherwise retain an explicit unavailable state. Do not start engine expansion before the morning review.


## P15 — localhost UI ready for review
Managed session `32804` serves the synthetic UI at `http://127.0.0.1:8765/`; listener and HTTP GET 200 were verified. Live `POST /api/preview` returned 200 for `csv_to_sqlite` (2 steps, write approval required) and created no DB files. Only two rows in a temporary synthetic CSV are configured; no run was initiated. Codex browser-open is queued, and visual click/render remains unverified. The earlier detached process did not persist; managed execution solved that. No source changed; progress remains 77% / PARTIAL.

The actual CLI scheduler was killed at `os._exit(73)` after its synthetic business DB commit and before the runtime receipt. Restart replayed tick 0 with the same deterministic run ID, completed the run, advanced the schedule once, and kept one business row. Scheduler tests passed 6/6; full suite passed 60/60 under permitted loopback; Node syntax and compilation of 17 Python files passed. Commits: `a2a7c9ce5915c86f0de0dce754e7fdac450d68f5`, `c952fcfdfc9f8cabf25c9656ed4f18c0c6319ac3`.

Resolved run failures: wrong unittest cwd (`ModuleNotFoundError`), sandboxed loopback denial (`WinError 10013`, 8 failures/10 errors), PowerShell wildcard not expanded for `py_compile`, and test assertion placement corrected before the passing rerun. Product estimate remains **77%** and PARTIAL; browser E2E, separately approved restore, independent review, signed installer, and customer/release evidence remain open.

## n8n structure review — official docs and source (2026-10-27)
- **Workflow model:** the editor composes connected nodes as a graph. Branch ordering is a defined workflow semantic: current v1 completes a branch before moving to the next, with canvas position deciding order; a visual fork does not imply parallel execution. [Components](https://docs.n8n.io/build/understand-workflows/workflow-components/) · [Branch order](https://docs.n8n.io/build/flow-logic/understand-execution-order)
- **Runtime and recovery:** the core `WorkflowExecute` owns status/cancellation, a node execution stack and execution data; its suspend operation parks at a node boundary so persisted waiting state can resume. The UI supports retries using either the current saved workflow or the original workflow snapshot. [Core executor](https://github.com/n8n-io/n8n/blob/master/packages/core/src/execution-engine/workflow-execute.ts) · [Executions](https://docs.n8n.io/build/understand-workflows/understand-executions/)
- **Data lineage:** item links preserve which input item produced each output (including fan-out and multi-input cases). AX FLOW currently preserves CSV source row numbers and hashes, but does not provide general item-level lineage. [Item linking](https://docs.n8n.io/data/data-mapping/data-item-linking/item-linking-node-building/)
- **Scale topology:** queue mode separates the main instance (triggers) from Redis-enqueued execution IDs and workers (execution + DB persistence); n8n does not recommend SQLite for queue mode. This distributed topology is outside the current local MVP. [Queue mode](https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/enable-queue-mode)
- **Custom code and license:** Code-node JavaScript/Python is run through task runners; n8n recommends external runner isolation for production because workflow code otherwise risks access to credentials and environment secrets. The current MVP's no-user-code rule is an intentional safety boundary. Current SUL guidance says customer-configurable n8n automations through a product require a commercial license even when the n8n UI is hidden. [Task runners](https://docs.n8n.io/deploy/host-n8n/configure-n8n/set-up-task-runners) · [License FAQ](https://support.n8n.io/article/can-i-use-your-license-for-my-use-case)

**Implication for this MVP:** keep local synthetic execution and current idempotent checkpointing; do not add queue infrastructure, arbitrary code, or n8n dependencies. Do not claim n8n parity. If the product later grows, validate a versioned graph IR, item lineage, original-vs-current workflow retry semantics, and isolated credential/runtime boundaries as separate tested features. No n8n code, assets, or trademarks were copied. This research task has no application test; no source code changed. Progress remains **77%**. Next code unit should close a bounded Blueprint gap (or use the already specified offline template), then run the suite and update this checkpoint.

## Previous checkpoint — P9 local boundary fixes passed (2026-10-27 KST)

`feature/axflow-mvp`: response hardening `30be45331ea71b5a39cd2530764664dd8620d565`, regressions `2da4b40ebfeec92b0fb589c75392c3e962e5ffb7`. Windows Python 3.11.9 DBVORA client suite 9/9; full suite 59/59; Node syntax and Python compilation pass. Hostile 5000-digit Content-Length and deeply nested JSON now fail closed. Read-only code review verified loopback-only binding/client, Host/Origin gate, capped/rate-limited requests, CSP/no-store, DOM textContent, and redirect-disabled GET-only bounded DBVORA client.

A–E progress heuristic: **77%** (A100/B95/C80/D60/E50); product remains PARTIAL. This review is not independent certification. Remaining: visible browser click/render, OS-denied symlink fixture, running DBVORA browser view and separately authorized restore, signed installer, customer/release evidence, independent security review. No new site needs opening; existing localhost tab remains at `http://127.0.0.1:8765/`.

**NEXT ATOMIC TASK:** continue with only permission-free quality gates; preserve explicit notes for any release gate requiring user or external authorization. Do not merge to main/develop or claim 100% until required evidence exists.

---

## Current checkpoint (P8 zipapp/package API smoke passed — 2026-10-27 KST)

Branch `feature/axflow-mvp` P8 commits end at `c1219d2d55b0ea1cbd195fcdbcb9ec386220e83e`. Windows Python 3.11.9: package tests 3/3, full suite 57/57; JS syntax and py_compile pass. A stdlib `.pyz` ran from outside the source tree with no `PYTHONPATH`; CLI synthetic SQLite and packaged UI GET/preview/approved-run passed. The completion receipt did not expose the fixture row. Overwrite was rejected without changing artifact SHA.

A–E heuristic: **76%** (A100/B95/C80/D60/E45); status PARTIAL. Still open: visible browser click/render, DBVORA browser view and independent restore, security assessment, signed installer, customer/release gates. The host denied creating a symlink fixture, so that path is unverified. No extra site needs opening; existing `http://127.0.0.1:8765/` is the P6 UI and schedule controls are CLI-only.

**NEXT ATOMIC TASK:** conduct a read-only review of loopback/origin checks, file/database path boundaries, privacy/redaction, interval tick persistence and zipapp contents against Blueprint E. Add regression tests only for concrete findings; run the complete suite before claiming closure. Do not touch customer data, credentials, DBVORA restore or deployment.

---

## Current checkpoint (P7 interval trigger passed — 2026-10-27 KST)

Code/test chain on `feature/axflow-mvp` ends at `bef87cce42960cb31daaeb10b8e2ede0698a5748`; hard-crash test commit `ce1316c430fe90c67a76bdd29c63ec7e82687889`. Windows Python 3.11.9: scheduler tests 5/5; complete suite 54/54; JS syntax and Python compile pass. IR supports bounded manual/interval triggers; local schedule state pins plan hash and due tick. Restart replays the same deterministic tick; concurrent workers do not duplicate its SQLite write. Every schedule call requires `--max-runs 1..1000`; writes require explicit approval.

A–E heuristic: **72%** (A100/B95/C70/D60/E35); product remains PARTIAL. Remaining: visual browser click/render E2E, source-preserving DBVORA restore, security assessment, Windows package/install review, customer/release gates. The existing `http://127.0.0.1:8765/` page remains the P6 UI; no new site needs opening and it has no schedule controls. DBVORA service is stopped.

**NEXT ATOMIC TASK:** build a standard-library-only Windows `.pyz` package outside the source tree. Make UI assets load through `importlib.resources`; test the packaged CLI and localhost page GET without installing dependencies. Treat this as a package smoke only, not a signed installer or release.

---

## Current checkpoint (P6 process-crash and cross-process replay passed — 2026-10-27 KST)

Branch `feature/axflow-mvp`: P6 code `7190f5a3c8a238b1f33a948dd9a3df0d5e121b37`, process-recovery regression tests `d90644e28ab46c48091a1b0fb0329af0b1d15eb9`. Windows Python 3.11.9 engine tests 27/27 and full suite 49/49 pass. A child process was terminated with `os._exit(73)` after the synthetic CSV business commit but before the runtime receipt; resume completed with no duplicate rows. Two independent processes replaying one run produced one durable write. First test invocation and helper failed due test harness import paths; both corrected and fully rerun.

Blueprint gaps: local interval trigger; visible-browser click/render E2E; independently verified source-preserving DBVORA restore; security assessment; Windows installer; customer/release gates. Product remains PARTIAL. Updated A–E equal-weight tracking estimate: 70% (A100/B85/C70/D60/E35), not acceptance or release readiness. P6 localhost UI is `http://127.0.0.1:8765/`; refresh the already-open tab. DBVORA service is separate and currently unavailable.

**NEXT ATOMIC TASK:** implement a bounded local interval trigger for a synthetic workflow with persisted due ticks, duplicate-run protection, explicit cancellation/stop and a bounded run count. Test restart/recovery, missed/due tick semantics, and no duplicate business writes. Do not connect external schedulers or customer data. Then re-run the full suite and update STATUS/HANDOFF.

---

# Next work unit — 2026-10-27 KST (ACTIVE fast-track)

## Current checkpoint (P6 filtered planner and UI/API verification passed)

On feature/axflow-mvp@7190f5a3c8a238b1f33a948dd9a3df0d5e121b37, Windows Python 3.11.9 full suite is 47/47 PASS; JavaScript syntax and Python compilation pass. The planner supports full import, filtered import, conditional import and read-only match-count/original-row-number lookup. Filtered recovery preserves original row numbers and does not persist matching row payloads in receipts. P5 DBVORA synthetic API smoke remains verified at baseline commit 06ba9f011796090b84e4625bcd65ded848412e34. Post-commit localhost smoke: page GET 200; Korean read-only lookup preview/run on synthetic ID 42 returned one match on source row 1 and no raw value.

Blueprint A–E progress estimate: 68% heuristic (A 100, B 75, C 70, D 60, E 35; equal weights). Product state remains PARTIAL. The visible browser click/render flow, interval triggers, hard-kill/cross-process runner tests, restore, security review, installer and customer/release gates are still open.

**Next:** add actual subprocess hard-crash recovery and cross-process same-run replay tests. The authorized n8n behavior review is already recorded from official docs; no code/assets were copied. Keep customer data, OAuth, DBVORA writes and public deployment behind existing approval gates. Visible browser E2E remains unverified because the UI helper previously stopped at its URL-confidence check.

## Codex first authorized implementation unit (MVP D1–D3, REA_APP branch)
1. Verify hibi89/AX_FLOW current HEAD and read HANDOFF/STATUS/AGENTS/REQUIREMENTS/docs + actual code.
2. Build read-only bounded source walker and parser-accurate JS/TS import/export graph with file/line provenance under tools/rea-app. Python AST optional. Use a permissible local AST parser (TypeScript compiler API/Tree-sitter) with pinned version; no code copied from n8n.
3. Design small synthetic JS/TS fixture, run CLI end-to-end, return deterministic JSON+Markdown. Fail closed on huge/binary/secret/symlink/file escape cases. Never execute inspected code or mutate the source root.
4. Fix test failures; report **actual** commands, PASS/FAIL/SKIP, exact commit SHA and target blueprint gaps. Avoid asking owner to do work Codex can do itself. No blanket “finished” claim from skeleton.
5. D4–D6 permitted n8n study and original behavior contracts; D7–D14 independent executor on feature/axflow-mvp. Refer to work order for exact limits.

## Chief review gate
Compare every completed small module against docs/TARGET_BLUEPRINT_V1.md, identify high-priority missing features, and allow Codex to implement immediately within approved scope. First design decisions preselected for speed (bounded Python CLI + AST parser adapter, native JSON IR, SQLite, local-first). Escalate new paid costs/licensing, public visibility, user secrets, real external API/DB operations or destructive effects only.

## DBVORA parallel work
AX FLOW-side feature/dbvora-integration branch only. Check independent DBVORA source/API/Windows gate before committing adapter claims. No dependency on a nonexistent universal API; safe read-only SQLite inventory first. Preserve separate runtime and business SQLite.

## Safety
The active 2026 hackathon deadlines overlap Week 3; don't override submission priorities. 5-week target is conditional, no automatic background execution. Update STATUS/HANDOFF when actual implementation/test results change.

## 2026-10-27 KST — chief review passed; independent runner B slice 1 implemented

The earlier `USER HOLD` on starting B is now **resolved by chief architecture review of REA_APP Blueprint A synthetic scope**; this does NOT certify real-world REA_APP completeness. See current `feature/axflow-mvp` STATUS/HANDOFF and code under `apps/ax-flow/`.

**NEXT ATOMIC TASK (feature/axflow-mvp):** implement status/resume CLI for current synthetic SQLite ledger and safe failure-state reporting; add tests for staged interruption, unknown run IDs, double-call/concurrent same-run collisions and malicious IR inputs. Do not start new SaaS integrations. Preserve synthetic-only test guard, state/data DB separation and local idempotency proof. Require exact git blob SHA checks after every remote upload because REA_APP past transport truncated one large blob.

**After next gate:** add condition/transform, rate/retry/time budget, restricted HTTP test stub; then connect planner/GUI and DBVORA only after supported interface validations. No full Blueprint B completion claimed.

## 2026-10-27 — NEW TOP PRIORITY (7-day sprint)
Supersedes the older 5-week sequencing. Read `docs/SPRINT_7_DAY_HACKATHON.md`. **Target Oct 31 integrated supported-scope MVP, review no later than Nov 2 (subject to actual tests).**

**P0 now passes** on Windows / Python 3.11 at `feature/axflow-mvp@5e7e05dac27336e87a02d847316b654e82cacbac`: full `python -m unittest discover -s tests -v` reports 12/12 PASS, including run/resume/status, malformed inputs, threaded duplicate claims and no-duplicate SQLite replay. Continue immediately with P1 condition + pure transform + bounded retry/timeout and per-step outcomes, then the synthetic CSV→SQLite path. Keep CI, cross-process stress, Windows packaging and customer data claims marked UNVERIFIED until actually tested.

**Then D4–D5:** constrained natural-language/template → native IR → auto-config/test and basic local GUI, DBVORA read-only SQLite inventory; supported end-to-end demo must be real. Reuse selectively in KIC/PayPal/UGREEN with their submission constraints; UGREEN Skill ZIP stays Markdown-only, PayPal live financial order path requires actual authorized provider evidence, KIC prelim is PDF-only.

**Do not block on 100% REA_APP completeness**; use approved bounded analyzer and maintain separate follow-up environment tests. Full AX FLOW commercial/product gates remain separate; do not downgrade tests to declare a 7-day commercial release.

## 2026-10-27 KST — P0 passed; P1 implementation is next

The current Windows full-suite baseline had 8 teardown failures from SQLite handles left open when `TemporaryDirectory` removed files. The engine and read-only runlog now close connections deterministically, and the regression tests close their own fixture handles. The latest full suite passes **12/12**. Run claims are serialized with `BEGIN IMMEDIATE`; same-ID/different-plan conflicts are rejected, exact same-plan replay is idempotent, and handled failures persist `failed` plus a bounded error type. Restart/resume after the injected post-business-commit stop passes without a duplicate row.

**P1:** Add safe conditions/IF-ELSE, pure map/transform operators, and step-level completed/failed outcomes. Add explicit bounded retry and timeout budgets; do not retry non-idempotent writes automatically. Define an explicit bounded branch IR so unknown expressions stay rejected. Verify at least three distinct offline workflows, including conditions and data transforms. Then continue into P2 CSV→SQLite. Local CLI/SQLite work requires no website to remain open.

**Limits:** threaded SQLite tests passed, but cross-process stress and parallel step execution remain unverified. Hard process termination may leave a run marked `running`; resume only after the old process is confirmed stopped. Keep the synthetic-only guard and separate runtime/business DB files.

## 2026-10-27 KST — P1 condition/transform slice passed

The prior P0-only status is superseded by `feature/axflow-mvp@e0dd9959dd624ee58321fac34761f9525445ee42`. Windows Python 3.11 full suite: **15/15 PASS**. The commit adds allowlisted mapping transforms, typed conditions, boolean `when` guards, explicit branch routing, durable `running/completed/failed/skipped` step outcomes, migration of existing receipts, and aggregate outcome reporting from read-only status. The passing suite checks both branch outcomes with actual SQLite writes, safe rejection of unsupported transforms/operators, failure recording, old-ledger migration, and P0 behavior.

The implementation surfaced and repaired: (1) stale assertions after status output and step counting changed, (2) an uncommitted legacy database fixture, and (3) an actual concurrent same-run duplicate step-row insert. The final 15-test Windows run passed after these fixes. No browser is needed for current CLI work.

**NEXT ATOMIC TASK:** implement a bounded SQLite lock-wait timeout and retry cap (maximum three attempts, only transient SQLite busy/locked errors, no non-idempotent external operations); add a deterministic held-lock test that asserts timeout, retry count, failed step/run status, and successful replay after lock release. Keep each runtime/business DB separate and the synthetic/write-approval guards. Update the runlog and test commands, then commit and verify exact uploaded blobs. After that, implement the synthetic CSV→SQLite vertical path. GUI/browser verification will be announced before starting.

## 2026-10-27 KST — P1 retry/timeout passed; CSV vertical path next

The preceding P1 task passed on Windows Python 3.11 at `feature/axflow-mvp@767d2ad49a31f5849775fb1a1a61ca5966381f0f`; full command `python -m unittest discover -s tests -v` reports **17/17 PASS**. SQLite steps can opt into `max_attempts` 1–3 and `timeout_ms` 1–5000. Only transient busy/locked errors retry. The held-lock regression checks attempt count, `StepRetryExhausted`, a short-deadline `StepTimeout`, and successful same-run replay after unlock.

Observed Windows-specific failure: built-in SQLite `timeout=0.1` took about 0.48 s under an exclusive file lock, longer than the requested budget. The engine now configures nonwaiting busy handling and owns retry backoff/deadline; the new Windows test passes. Scheduling overhead can still exceed a monotonic deadline slightly; there is no hard preemption of arbitrary code.

**NEXT ATOMIC TASK:** build the synthetic CSV→SQLite path. Validate a bounded local CSV fixture (encoding, header, row/column/byte limits, duplicate/missing columns), map rows to deterministic run/row keys, require explicit write approval, and prove idempotent resume after an injected interruption. Reject malformed/oversized input before writes. Run the complete test suite, update status/handoff, and commit only on PASS. GUI/browser stage will be announced before opening.

## 2026-10-27 KST — P2 CSV→SQLite passed; lawful n8n study and templates next

P2 passed on Windows Python 3.11 at `feature/axflow-mvp@ebc2bbfdf05e51fc82732fce73da849146872b43`; full `python -m unittest discover -s tests -v` is **20/20 PASS**. The actual CLI flow reads a local `.csv` under explicit `--input-root` and atomically writes `csv_records` in the separate business database. It requires `--approve-writes`. Import is idempotent by run/step/row, carries the source SHA, and resumes after a post-commit injected stop. The runtime stores only the relative source path, SHA, headers and row count. Changed input on resume is rejected.

Limits are enforced and tested: 256 KiB, 1000 data rows, 64 columns, 4096 chars per cell, UTF-8/BOM, unique safe identifier headers, exact row widths; malformed/invalid UTF-8, missing files, unsupported extensions and path traversal fail before business writes. Code rejects symlink components; an actual symlink fixture was not run on this Windows host. XLSX/PDF and arbitrary human-readable headers are out of scope.

**NEXT ATOMIC TASK:** perform the user-authorized n8n behavior analysis against current public/authorized material and official licensing text. Record only evidence-backed functional behavior contracts; no code/assets/trademarks/connector copying. In parallel, add one deterministic built-in template that generates native IR, can be validated and exercised entirely offline with synthetic fixtures, and fails closed on unsupported requests. Then local GUI remains a separate user-notified step before any visible browser is opened. Full AX FLOW and DBVORA acceptance remain PARTIAL.

