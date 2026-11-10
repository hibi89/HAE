# Lightning Azent P15 — completed-run evidence integrity fix (2026-11-10 KST)

## Goal
Correct P13 evidence facade: `verify_receipts(plan,run_id)` checks a plan and completed-write receipts, but it can be true on a not-yet-completed run; the prior bridge hard-coded `verified: True` without checking the actual run status. The private `runlog.inspect_run` schema returns `run_id`, `status`, step counts and plan SHA. A truthful completed-run receipt requires the same run ID and `status == completed`.

## Design alternatives
- Broad change to the LA engine/runlog schema: higher regression and migration risk, touches existing state, unnecessary for the evidence-consumer flaw.
- **Selected:** fail closed at the optional `HAEBridge.evidence` boundary (no new dependencies/API/DB writes, no old engine modifications). Require `verification` dict `verified is True`, a status dict, exact `run_id`, and completed state; otherwise raise PlanError. Only fetch audit after those checks.

## Changes / exact blobs
- `packages/lightning-azent/lightning_azent/hae_bridge.py`: Git blob `1feb0e7ed745c4d650adcb8799e1d8239c9a9cbc`.
- `packages/lightning-azent/tests/test_hae_bridge.py`: Git blob `9f03b0e7e86bd033e542812632304d7112a037a0`.
- 3 added tests cover pending/running/failed/unknown status, other run ID/missing status, and malformed/false receipt proof, all fail closed.

## Executed acceptance
- Linux Python 3.13.5, local isolated source with LA runtime/contract and HAE planner **boundary stubs**: `PYTHONPATH=. python -B -m unittest discover -s tests -p test_hae_bridge.py -v` **17 PASS / 0 FAIL / 0 SKIP**, plus HAE consumer `test_la_adapter.py` **7 PASS / 0 FAIL** (24 total).
- Python `compile` real new bridge and test file PASS. Local `git hash-object` values for both files matched exact GitHub-created blobs above.
- Verified actual `runlog.py` source returns status/run_id. This is structural inspection, not an E2E execution.
- **NOT RUN**: P14 five real HAE→LA SQLite E2E definitions, original LA full suite and HAE 84 tests at this SHA, Windows installation/GUI/Production/customer workflows. Private checkout unavailable from container; no paid/unknown-cost GitHub Actions initiated.

## Completion and blockers
**Estimated Lightning Azent commercial final progress 68% → 69% provisional (+1pp)** for a real safety/correctness gap and executed isolated regression; **70% NOT VERIFIED**. Full integration and local Windows checks are required, and P15 does not convert receipt integrity into cryptographic audit/consent. RELEASE HOLD.
No owner/customer data, OAuth, token, SOVIA/DBVORA, remote providers, original GUI routes, original package/branch or Production altered.

## Recovery and next step
Git history backs up original source. Revert only this P15 commit to restore previous optional facade (but reintroduces false positive). From a clean authorized full checkout run `python packages/lightning-azent/verify_local.py` once; it discovers P14 + P15 cases and the original LA and HAE suites. For failed E2E, fix the measured failing code and repeat only necessary tests, preserving all original business SQLite. Check run SHA and command logs before 70% recognition.
