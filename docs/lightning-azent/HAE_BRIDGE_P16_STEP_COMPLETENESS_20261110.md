# Lightning Azent P16 — completed run must have complete step evidence

**Date:** 2026-11-10 KST. **Repo:** private `hibi89/HAE@feature/lightning-azent`.

## Purpose and implementation
P15 made `HAEBridge.evidence()` reject non-completed run status and wrong run_id. However an accidental or tampered top-level `completed` flag, or a plan-hash mismatch, could still cause success if persisted step records are incomplete. P16 extends the same **optional evidence facade**; no original engine, runlog or user service behavior changes.

Require:
1. Actual `status.plan_sha256` equals canonical validated plan hash from the user-supplied plan.
2. `steps_recorded` is a genuine int and equals the number of validated steps.
3. `step_outcomes` has nonnegative **int** counts, zero running/failed, and completed+skipped exactly equals the planned steps. `skipped` is supported for legal guarded branch decisions.
4. Any mismatch throws PlanError, never `verified: true`. Still require P15 receipt and exact run_id checks.

Compared strategies: (A) schema version migration/engine-wide ledger change — greater rollback risk, duplicated contract; (B) local consumer evidence gate — chosen zero dependency, no new storage or permission, source-preserving.

**New exact Git object blobs:** `hae_bridge.py` `3b65da2ac0483d1f6c2989c0af566f1289a60c69`; `test_hae_bridge.py` `960ed2fd77ae9964c71a8178cbbd9c970231e028`. Confirmed GitHub object SHAs exactly match local `git hash-object`. P15 predecessor source `1feb0e7ed745c4d650adcb8799e1d8239c9a9cbc`.

## Executed verification
- Container: Linux Python3.13.5.
- Actual changed code and tests compiled (syntax PASS).
- Isolated LA bridge `python -B -m unittest discover -s tests -p test_hae_bridge.py -q`: **20 PASS / 0 FAIL**. Three new regression cases specifically reject status plan mismatch, incomplete or malformed persisted step count, missing/failed/running states. P15 tests continue passing.
- Existing HAE `test_la_adapter.py` isolated with planner double: **7 PASS / 0 FAIL**. Total **27 passing boundary-level tests** at identical source blobs. This is not full LA/native SQLite E2E.
- GitHub `runlog.inspect_run` source inspected: emits `run_id`, `status`, `plan_sha256`, `steps_recorded`, `step_outcomes` and `error_type`. LA engine writes guarded `skipped` step statuses, which this gate permits.
- **NOT RUN** at P16: full LA tests (~73+ with P14 and P15/P16), original HAE suite, actual cross-component SQLite E2E, Windows GUI/installer and customer pilot. No private CI runner invoked (free quota not verified). No Vercel/Production service for LA.

## Progress accounting and release
Project-manager final-product scope **provisional assessment: 69% → 70% (+1pp)** from this independent, tested fail-closed integrity boundary. Together P15/P16 correct two separate status and step-provenance false-success paths. **This 70% is a planning estimate, NOT an end-to-end validated 70% milestone or release acceptance.** RELEASE HOLD remains until real original-engine integration, Windows, auth/OS consent, DBVORA and SOVIA are verified. No original UI/prod routing, customer files, secrets, deployment or billing changed.

## Exact handoff / rollback
Git history stores baseline and supports normal revert P16 if existing legitimate status format is incompatible; never force-push. Next command on authorized clean Windows checkout: `python packages/lightning-azent/verify_local.py`. Capture SHA and PASS/FAIL/SKIP; its test discovery includes both P14 E2E and P16 verification. If it fails, repair measured regression before recognizing full implementation. The existing customer GUI remains bound to legacy `axflow`; no silent cutover.
