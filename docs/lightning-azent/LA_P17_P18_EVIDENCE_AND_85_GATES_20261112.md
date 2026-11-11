# Lightning Azent P17–P18 — security/portable work toward 85% (2026-11-12 KST)

## 1. Scope and acceptance
- Owner request: prioritize independent Lightning Azent 70%→85% engineering milestone before already-85% HAE and frozen REA_APP.
- Source of truth: PRIVATE `hibi89/HAE@feature/lightning-azent` baseline `9dd2a6e10ffab6ea313e74366065c3333b1490b2`. Child branch `feature/la-p17-audit-evidence-20261112` exact **feature-source SHA `fd2b89ca2304fa9c259d798b2f925541b15f8a65`**, [Draft PR #2](https://github.com/hibi89/HAE/pull/2) unmerged.
- Historical baseline **70% provisional** from P16. **Current credited completion remains 70%, NOT 85**: there is no new executed exact-SHA test evidence yet. Code exists, but 15pp is conditional on actual verification.
- User-approved development scope is zero-network, local synthetic SQLite/CSV only. No release, paid CI, distribution to customers, live integrations, customer data/credentials, production, default app cutover or alteration of frozen original branch.

## 2. Designs compared
A. Modify core Engine/runlog transaction schema or replace HAE app runtime directly: migration/rollback and concurrent-path risk high, no need to change data format, may break original HAE/REA_APP, full regression costly.
B. Keep stable v0 engine contracts; add **fail-closed evidence and cached-result inspections at runtime facade** + independent deterministic stdlib package candidate, targeted real SQLite fault-injection and single local full-verification command: selected. Costs no external API/model/network or dependency; extra light code/test maintenance, source version kept. Existing rollback = revert feature branch or close PR; baseline untouched.

## 3. Implemented but not executed at this SHA
P17-A: `hae_bridge.py` checks LA `verify_receipts` references the exact run, complete persisted step status and plan SHA, fully bound `audit` identity and final `run_completed` with matching step_count and 64-char output digest, final event terminal, all write approval receipts matching same plan SHA and exact write step list, no false read-only approvals, completed `error_type=None`, second status read to reduce concurrent update false positives. Audit event metadata is **not authenticated or a SOVIA audit**.
P17-B: `LAExecutor.execute()` now checks an *existing completed* run's business ledger and committed write/import receipts and full step outcome counts before Engine's cache shortcut. Prevents silently returning cached success after deletion of an imported business row or step. `resume()` already had receipt guards. For brand-new or empty SQLite files, Engine remains migration authority; read-only facade checks are not race-free or distributed exactly-once enforcement.
P17-C: `test_hae_bridge.py` adds 8+ negative cases; `test_hae_to_la_e2e.py` adds 5 real intended HAE natural language→manual approval→LAExecutor→disposable SQLite fault-injection tests: deleted business row and step, missing completed audit, changed scope, replay after real resume. Both use existing stdlib `sqlite_test_utils` context closure on Windows.
P18: `build_portable_p18.py` creates source-only, deterministic ZIP_STORED `Lightning-Azent-0.1.0-synthetic-dev.pyz` with exact nine internal modules, top-level zipapp entry and unsigned JSON SHA manifest. No source CSV/user data/secret, no Python interpreter. `verify_portable_p18.py` independently checks exact 11-file archive inventory, bounded members, normalized SHA256 and optional separate `.pyz.sha256`. Fixed filename and hard-link new-only output prevent accidental overwrites. Includes 8 unexecuted tests for actual isolated zipapp CLI, capabilities/preflight, consent refusal, deterministic builds, archive tamper/extra member and no-overwrite. SHA **not digital signature**, not proof of publisher, race-free filesystem, customer safety or commercial license.
`verify_local.py --expected-branch feature/la-p17-audit-evidence-20261112` explicitly supports only this feature and existing original baseline; default remains `feature/lightning-azent`. No original source, history or older published wheel/ZIP modified.

## 4. Verification status, exact commands
- **NOT EXECUTED at `fd2b89ca2304fa9c259d798b2f925541b15f8a65`**: Python full LA tests, the real HAE→LA five old+five new E2E, source-only zipapp build+CLI, old HAE app suite, Windows native file lock/SQLite tests and optional wheel. No Github CI in source feature branch, no PR workflow run found. Do NOT infer tests passed from authored test files.
- Private repository couldn't be checked out into this isolated runtime (no network/authenticated git). No paid private Actions workflow was introduced or run without verified allowance/explicit approval.
- On owner-authorized clean clone, Python >=3.11, at exact branch and SHA, **one local command**:
  `python packages/lightning-azent/verify_local.py --expected-branch feature/la-p17-audit-evidence-20261112`
  Verifier must report SHA, LA suite count, original HAE suite, real CLI synthetic SQLite runs, Windows/new P17/P18 tests (from unittest discovery), PASS/FAIL/SKIP and emitted `verify_result.json`. No `--skip-legacy`/ `--skip-wheel` for full milestone if dependencies present. Offline wheel optional if modules unavailable => PARTIAL.
- Explicit optional standalone package verification after complete regression:
  `python packages/lightning-azent/build_portable_p18.py --output NEW_DIR/Lightning-Azent-0.1.0-synthetic-dev.pyz`
  `python packages/lightning-azent/verify_portable_p18.py --archive NEW_DIR/Lightning-Azent-0.1.0-synthetic-dev.pyz --sha256-file NEW_DIR/Lightning-Azent-0.1.0-synthetic-dev.pyz.sha256`
  `python -I -B NEW_DIR/Lightning-Azent-0.1.0-synthetic-dev.pyz capabilities`
- **Release readiness remains RELEASE HOLD** and HAE flagship current UI remains legacy `axflow` until separate owner-approved cutover.

## 5. Milestone scoring, conditional only
Baseline: 70 provisional. Conditional planned increments: P17 completed audited/bound full-E2E real SQLite and cached replay +6pp; P18 deterministic isolated dependency-free portable candidate with hash/tamper/consent test +4pp; P19 full LA original and HAE suites, actual native Windows/Win10+ CLI and SQLite recovery including resumed write/lock +5pp. **Only after exact-source PASS and explicit release blockers tracked could engineering rate reach 85% provisional. As of this handoff all increments UNVERIFIED, so official remains 70%.**

## 6. Remaining blockers and next steps
1. Run original `verify_local.py --expected-branch ...` on a trusted *fully authenticated* Windows checkout with Python 3.11.9; capture all source SHA and PASS/FAIL/SKIP. If a real test fails, fix exact cause; maximum one ineffective retry then pivot.
2. Do not alter signed/historical owner distribution or weaken original 65 LA/84 HAE regression. Validate Python 3.11 and 3.13, Windows deletion handles, no output of source payload, source hash unchanged, double execution idempotent.
3. Real SOVIA/DBVORA contract integration, customer UI OAuth/Sheets/Gmail, installed Windows acceptance, rights/security/privacy/support remain future full product gates, NOT part of synthetic-only completion claim. Cost or customer data transfer requires owner approval.
4. Merge Draft PR #2 only after target full tests and owner approval, or leave branch independent. No force-push. If no full suite available, leave 70 and report PARTIAL/UNVERIFIED, do not close release gate.

## 7. Repro and handoff
Source feature SHA `fd2b89ca2304fa9c259d798b2f925541b15f8a65`; branch was created at baseline `9dd2a6e10ffab6ea313e74366065c3333b1490b2`. GitHub identity author and committer are matched to authorized account hibi89; no email overrides were made. Product GitHub CI unrun at this SHA, Production/Vercel N/A. Original owner data/frozen REA_APP/HAE MVP unaffected. Updated 2026-11-12 KST; docs commit SHA to be read separately. Public hub records metadata only, not private code.
