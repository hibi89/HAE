# REA_APP 95% target — original P53 Gate R + retail E2E harness, 2026-11-12 KST

## 1. Goal / scope / technology
Keep frozen REA_APP v0.3.0/P53 Python3.11+ and pinned Node20+ @babel/parser@7.29.9 untouched. Move the optional offline buyer-review companion from synthetic report-shaped tests toward actual P53 source→report→ZIP integration. Full product P95 is a goal, not an accepted score.

## 2. Architecture and design selection
A. Copy/change original parser/engine into retail candidate: faster coupling but risks the frozen 25-file Gate R manifest, licenses and cross-branch merges.
B. Read-only independent P53 integration acceptance script using the existing CLI, original Gate R and retail candidate: less maintenance, no API/hosting charges, original code unchanged. **Selected B**.
Trigger is explicit `python retail_qa/p53_acceptance.py` inside an authorized full `tools/rea-app` checkout; no scheduler, network calls or automatic dependency installation. Flow: original source manifest+Python+exact Babel Gate R → two synthetic local JS/TS snapshots → P53 6-report then 8-report bundle → owner review/ZIP → source-backed verification → determinism and privacy checks. Only synthetic test files. On missing original source, malformed report or failed validation: exit nonzero with BLOCKED/FAIL, no commercial release or silent retry.

## 3. Implemented
- New `tools/rea-app/retail_qa/p53_acceptance.py`: explicitly runs protected `verify_gate_r.py`, which validates 25 Git source blobs, original Python tests and pinned Babel; creates controlled TS source snapshots and runs the actual `python -m rea_app bundle` 6/8 report commands, then source-backed `candidate_cli.prepare`.
- Checks P53 v1 report schemas, zero syntax errors, actual modified file detection, exact expected output names, SHA256, no copied synthetic path/text in four fixed buyer ZIP members, unchanged baseline/current source hashes and report bytes, and independent second-run byte determinism for both bundle and delivery.
- Uses explicit fail-closed `require` checks (not Python `assert` removable by optimization).
- New `tools/rea-app/retail_qa/test_p53_acceptance_preflight.py`: two isolated tests for missing original source failing closed and deterministic synthetic fixtures; original 39 retail QA retained.

## 4. Actual executed evidence / not executed
- Product GitHub feature HEAD and functional test SHA: `f0dbf651a7ee45a131cf23d125f727bfb428860c`.
- New exact remote Git Blob IDs: harness `db5a1441e68ff417b2cc8e39ff4f7c24085d1cf1`; test `60bcee4c7fcd7e8846825aab1731d4f38c9da9fe`. Both matched local authored/executed source files.
- Linux Python3.13.5 `python -m unittest discover -s retail_qa -p 'test_*.py' -q`: **41 PASS / 0 FAIL / 0 SKIP** (39 existing + 2 preflight); `python -m compileall -q retail retail_qa` PASS.
- `python retail_qa/p53_acceptance.py` in scoped local reconstruction: **exit 2 BLOCKED** as expected: original `rea_app/cli.py` and `babel_parser_adapter.cjs` are not mounted. Hence **P53 full Gate R + actual Babel parser E2E NOT EXECUTED**, no P53 PASS claimed.
- Linux Chromium 144 real `file://` via Playwright on generated owner HTML explicitly returned `net::ERR_BLOCKED_BY_ADMINISTRATOR`. This is an environment restriction, not a verified buyer Windows failure.
- Original Gate R source read directly from private GitHub: protected 25 blob list includes the frozen P53 implementation and parser contract; unchanged analyzer branch. No Actions workflow job or authorized Windows consumer execution this turn.

## 5. Product assessment and stop
**REA_APP 85% provisional retained, target 95% NOT ACHIEVED, RELEASE HOLD / SALE NO-GO.** The validated increment is the reusable integration acceptance harness and fail-closed preflight, not successful whole-application or customer certification. Do not boost completion based only on new tests or docs.

## 6. Repository / branches / SHA / paths
Private `hibi89/HAE@feature/rea-app-kmong-owner-delivery-20261112`, source/test `f0dbf651a7ee45a131cf23d125f727bfb428860c`; new paths `tools/rea-app/retail_qa/p53_acceptance.py` and `test_p53_acceptance_preflight.py`. The original `REA_APP@2fe581b683f6a49779e71058cddbfd165871593a`, original P53 reviewed `1ae3dac263a1a5c866434c8418fe7dbb1d3f1d48`, main, other HAE/LA branches and existing sales package remain unmodified.

## 7. Production / environment / execution
No Vercel or Production URL (N/A). Current Linux Python3.13.5 scoped only; native Windows10/11, actual pinned Babel runtime, fresh wheel, installed buyer scenario and external customer pilot unverified. No paid CI was dispatched or dependency fetched.
Full authorized checkout run order:
```bash
cd tools/rea-app
python verify_gate_r.py
python -m unittest discover -s retail_qa -p 'test_*.py' -v
python retail_qa/p53_acceptance.py
```
Install locked Babel dependencies only after owner confirms any network/billing implications, and never run third-party code without rights.

## 8. Security, data and recoverability
Only synthetic TS fixture data, no customer files, API keys, unlicensed n8n source, cloud upload, permission/release change or domain modification. Previous code commits are rollback points. Retail ZIP intentionally contains only fixed review summaries/manifest/README; SHA receipts are unsigned integrity checks, not authentication. Conservative candidate rollback does not promise crash-atomic output.

## 9. Next action and acceptance gates
1. Run original whole-checkout P53 source+Python+Babel Gate R and new script at same exact commit on an authorized runner with locked dependencies, inspect PASS/FAIL/SKIP and provenance.
2. Run real native Windows10/11 Edge/Chrome offline `file://`, ZIP extract/CLI, Python3.11, source immutability and verified Windows-specific path/security cases.
3. Check retail NOTICE, dependency redistribution rights, customer privacy, supported-source claims, signing/support/refunds and controlled buyer-style pilot. Rescore P95 only after evidence; paid hosted CI/customer data/commercial publication require prior approval.

## 10. Time, validation boundary and handoff
Checked 2026-11-12 KST against actual GitHub code and local isolated execution. **41/41 scoped PASS** + expected **P53 BLOCKED exit 2**. Exact original whole repo integration, native Windows, CI, buyer acceptance **NOT VERIFIED**. Keep this boundary and current 85% until evidence arrives.
