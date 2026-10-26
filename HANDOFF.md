# HANDOFF — AX FLOW + REA_APP (bootstrap, 2026-10-27 KST)

1. **Goal/requirements/technology:** AX FLOW is a local-first natural-language automation product: file input + safe OAuth onboarding + plan/validate/run/recover with CLI and minimal web UI; optional DBVORA. REA_APP is a distinct app source analysis/reconstruction-assistance tool. Python 3.11+ proposed for initial static analysis and local executor; final technology remains subject to design/approval.
2. **Completed/change/decision:** GitHub private `hibi89/AX_FLOW` discovered empty; initial README created. Repo intended as private monorepo with separate source directories and branches. No features developed.
3. **Tests:** 0 executed / 0 passed / 0 failed; GitHub content/branches may be re-read to verify docs/bootstrap only. No Windows, browsers, OAuth, Gmail or production validation.
4. **State:** PLANNING/BOOTSTRAP; code NOT_STARTED. Next: initial REA_APP static analysis MVP design approval, then synthetic tests. AX FLOW runner follows.
5. **Errors/pivots:** Empty-repo 404 is expected, not a product bug. If remote read/write fails, record evidence, improve approach once, then provide local artifact and mark UNSYNCED instead of claiming success.
6. **Repository/branch/SHA/paths:** `hibi89/AX_FLOW` private, initial `main` SHA `8d528821097fcf6b983e52d9de804613cd8d8c3d`. Intended branches `main`, `develop`, `REA_APP`, `feature/axflow-mvp`; recheck actual HEADs after operations. Paths `apps/ax-flow/`, `tools/rea-app/`, `docs/`, AGENTS/REQUIREMENTS/STATUS/HANDOFF.
7. **Production/execution/environment:** No Vercel or deployed URL. Proposals: local CLI and localhost UI only; Python 3.11+ candidate, no runnable project yet.
8. **Originals/backups/credentials:** No code or data originals at bootstrap, aside from Git commits. No secrets, private source, customer DB or authentic external credentials supplied; no modifications to DBVORA/SMAX/SOVIA. Git history is current documentation rollback path.
9. **Next priorities/approvals:** Verify tree/branches/SHA → decide initial REA_APP analyzer architecture among documented alternatives → user's approval for substantive implementation → synthetic source fixture/parser/unit tests → AX FLOW proof-of-concept execution. Get approval for external data, OAuth registration, paid CI, security/visibility changes, production and customer usage. No n8n derivative commercialization assumption.
10. **KST checkpoint/verification scope/document baseline:** 2026-10-27 KST, repository metadata, initial README commit; **bootstrap final SHA and branch heads to verify live**. This document describes docs-only status, not an implementation result.

## New chat recovery
Read `HANDOFF.md` → `STATUS.md` → `AGENTS.md` → `REQUIREMENTS.md` → `docs/ARCHITECTURE.md` → `docs/NEXT_TASK.md` → actual source and tests. User `ㄱ` means next safe work unit. Do not repeat completed tasks.

## Verified bootstrap completion checkpoint (2026-10-27 KST)
1. **Goal:** AX FLOW end-user local automation, REA_APP source-analysis tool; distinct logical product directories, optional external DBVORA.
2. **Completed:** 14-file private repository documentation/source-layout bootstrap committed at `28271b5b8df6241d4a6be3a1e404b93d41379bb2`. Three branches successfully created from the documented main baseline: `REA_APP`, `develop`, `feature/axflow-mvp`. GitHub remote file reads verified every branch.
3. **Tests:** GitHub repository/branches/docs reads succeeded; 0 application unit/integration/browser/security/Windows tests run. No product implementation.
4. **Progress:** R0 initial repo setup DONE as verified documentation-only; R1 REA_APP analyzer is NEXT, not started.
5. **Issues:** Prior empty GitHub repository returned expected 404 until README init. No recurring failure or source restore needed.
6. **Repository:** `hibi89/AX_FLOW`, **private**, `main` stable, three feature/integration branches as above. Baseline commit `28271b5b8df6241d4a6be3a1e404b93d41379bb2`; status update subsequently `537b73cb91e5ba01241d89a8767f16792f674edc`. HEAD will advance with this handoff; verify all refs next time instead of presuming SHA.
7. **Production:** None, Vercel N/A, no CLI/application launch command yet; only GitHub Markdown.
8. **Safety/originals:** No pre-existing product code/data; original empty repo and README Git history retained; no secrets or auth data introduced; DBVORA/SMAX not changed.
9. **Next:** User decision on implementation design (A proposed Python CLI/local engine vs B OSS core integration), then work on REA_APP synthetic static analyzer in `REA_APP`. No deployment, customer source, OAuth apps or public access before approval.
10. **Time/proof:** 2026-10-27 KST. Confirmed GitHub private metadata, branch names, cross-branch file retrieval and commit author/committer `hibi89`. No full runtime tests exist.

**Note:** Documentation-only branches should be aligned to this latest main handoff checkpoint before independent feature development; verify with branch SHA after synchronization.

## 2026-10-27 KST — latest DB-required scope handoff (supersedes old optional-DBVORA description)

1. **Goal/technology:** AX FLOW customer product must automatically convert language/files into validated IR, auto-configure and dry-run/test/recover local workflows; internal SQLite journal and business data plane mandatory. Full product requires DBVORA-managed supported database visibility/backup/restore integration. REA_APP is distinct developer research tool; Python 3.11+ / SQLite / CLI / localhost GUI proposed.
2. **Completed and rationale:** Verified current AX_FLOW private repo docs and DBVORA independent feature source. Designed independent DBVORA read-only service adapter vs merging its code; select adapter for clear permission/rollback boundary. Wrote schedule and acceptance criteria; no actual product code implemented.
3. **Tests:** GitHub content/branch and metadata inspection only. **0/0 product tests**, no integration/browser/Windows/OAuth/customer acceptance; DBVORA prior per-feature tests do not establish current entire suite success.
4. **State:** R0 documents/branches organized, DB management requirement recorded; REA_APP R1 PENDING; AX FLOW runner/AI/GUI and DBVORA adapter NOT_STARTED; no product ready.
5. **Failure/recovery:** No implementation failures. DBVORA full-suite and Windows/unavailable service are known **unverified**, not claimed product defects. Do not use actual customer DB before independent synthetic tests and approval. No repeated ineffective attempts.
6. **Repo/branches/SHA:** hibi89/AX_FLOW private, main, develop, REA_APP, feature/axflow-mvp, planned/new feature/dbvora-integration branch. Prior verified main source `7de40d342ed2454ed63794a1322db05096193357`; GitHub must be re-queried for new documentation HEAD after writes. Critical paths docs/MASTER_SCHEDULE.md, docs/DATA_ARCHITECTURE.md, docs/ACCEPTANCE_MATRIX.md, docs/NEXT_TASK.md. DBVORA stays hibi89/DBVORA on active feature/p0-db-map; separate source/release.
7. **Production/environment:** local-first, no deployed URL, Vercel N/A. Proposed Python 3.11+ and SQLite; no executable app yet and no HTTP/service E2E.
8. **Originals/backup/auth:** all old files preserved through Git history; no secrets, customer DB or original n8n code committed. No changes to DBVORA repo or source data; credentials planned only OS secret broker.
9. **Next/approval:** verify final branch parity/docs SHA; get approval for substantive code design then implement REA_APP static AST source analyzer with synthetic tests; later AX FLOW CLI/runtime SQLite+business SQLite; then AI/file/OAuth; DBVORA integration adapter; full acceptance. Paid cloud, external data, real OAuth registration, customer DB access/mutation, public deployment need prior approval.
10. **KST/checkpoint/test scope:** 2026-10-27 KST; source files and architecture reviewed through GitHub connector, schedule is an **estimate** (21 weeks 445–750 hours, conditional). Document commit SHA cannot self-reference; resolve from GitHub remote main HEAD. Author/committer and branch comparisons must be checked after commit.

**Next chat:** HANDOFF → STATUS → AGENTS → REQUIREMENTS → docs/MASTER_SCHEDULE → docs/DATA_ARCHITECTURE → docs/ACCEPTANCE_MATRIX → docs/NEXT_TASK → actual source. `ㄱ` advances next authorized safe step.

## 2026-10-27 — latest owner correction / FAST-TRACK handoff (authoritative schedule over 21-week history)
1. **Goal:** REA_APP source analyzer for authorized JS/TS code → n8n functionality study (license checked) → native new-code runner → AX FLOW AI-driven configuration/testing GUI; parallel independently maintained DBVORA integration.
2. **Decision:** 2 weeks for first two outputs, **another 3 weeks** for AX FLOW+DBVORA integration = **5-week scope-limited v1 target Oct27–Nov30**, no 21-week plan as active. Working MVP by first 2–3 days, then blueprint comparison and gaps.
3. **Test evidence:** GitHub docs only; **0 runtime/product tests** and no Windows/browser/real OAuth/integrated DBVORA acceptance. No Codex job is already running merely because a task doc exists.
4. **Progress:** R0 docs complete; REA_APP analyzer/RUNNER/AI/GUI/DBVORA bridge NOT_STARTED. All release acceptance gates still apply.
5. **Risks:** JS/TS parser integration, n8n license boundaries, n8n feature parity explicitly excluded; live OAuth/DBVORA Windows+restore tests depend on third-party readiness, hackathon KIC/PayPal/UGREEN submission deadlines Nov12/13/16 overlap W3.
6. **Repo/branch:** hibi89/AX_FLOW private; main for master docs, REA_APP for analyzer, feature/axflow-mvp for native runner and UI, feature/dbvora-integration for bridge, develop review. Confirm actual SHA after writes; no third-party source copying.
7. **Environment/deploy:** Python 3.11+ and a bounded JS/TS AST parser adapter as candidate; local CLI + SQLite, optional GUI. NO app launch, no customer release or production.
8. **Originals:** Preserve Git history of 21-week docs; existing main code/docs not rewritten unsafely; never mutate customer source or DBVORA repo. No secrets/API tokens provided.
9. **Next:** docs/CODEX_EXTRA_HIGH_ORDER.md exact first 72h; blueprint docs/TARGET_BLUEPRINT_V1.md; active dates docs/FAST_TRACK_5_WEEK.md and docs/MASTER_SCHEDULE.md. Chief independent evidence review after each slice; owner approval for real external effects/security costs.
10. **KST checkpoint:** 2026-10-27; GitHub docs edits only at time of handoff; no live software test numbers to claim. Resolve HEAD and compare branches before Codex acts.

Recovery: read this latest appended block before older 21-week historical notes. Keep all independently tested gates, but time-box features and report PARTIAL rather than falsely claiming universal functionality. User `ㄱ` advances work; no background task implied.

## 2026-10-27 KST — AX FLOW independent runner first code slice (CURRENT, feature/axflow-mvp)
1. **Goal:** Customer-facing eventual AX FLOW independently coded engine; first synthetic SQLite state/IR runner under `apps/ax-flow/` with REA_APP separate, DBVORA eventual independent adapter.
2. **Completed:** Chief reviewed REA_APP bounded synthetic acceptance and released independent engine hold for v0.1.0 ONLY. Added validate/run local Python CLI, strictly limited native JSON IR `axflow.ir.v0`, fixed step registry, local runtime vs business SQLite, explicit write approval and idempotent local write replay; docs updated.
3. **Tests:** Local Linux Python 3.13.5 `python -m unittest discover -s tests -v` from `apps/ax-flow`: **5/5 PASS**. Four source file blob SHAs match uploaded GitHub contents exactly. GitHub Actions, Windows/real DB/provider/GUI/security suite **NOT TESTED**.
4. **Current status:** **ENGINE_B_SLICE_1_VERIFIED_SYNTHETIC**, not completed Blueprint B. REA_APP synthetic MVP gate previously cleared; AX FLOW NLP/GUI/DBVORA/external auth all NOT_STARTED.
5. **Failure/repair:** REA_APP Codex previously had remote UTF-8 blob truncation repaired on REA_APP branch; this runner's four uploaded source blobs independently matched local Git hash-object. No runner test failures. Critical remaining risk: SQLite event receipts are not globally atomic with arbitrary external effects; protect with idempotency keys and explicit unknown-status recovery in future.
6. **Branches/SHAs:** `hibi89/AX_FLOW` PRIVATE, work branch `feature/axflow-mvp`. New source code commits start `f52f7e129cb4ab03b73869c5c5eaa6926309e6cb` and pass test file upload at `2a4342e6c6ebacf490d37e0aebd3b4bcabd2a146`; docs follow. Confirm latest HEAD by remote GitHub query after modifications.
7. **Environment:** stdlib Python 3; no production/service/Vercel, no Windows package. CLI `python -m axflow validate <file> --synthetic` or `python -m axflow run <file> --synthetic --state ... --data ... --run-id ... --approve-writes`. Parent dirs must exist.
8. **Originals/security:** No n8n source copied, no customer secrets/data/external accounts read/written; original main unaffected, feature branch isolated. Synthetic data saved locally with step outputs; **do not use real customer data**.
9. **NEXT:** Add run status and explicit safe resume CLI, retry/error statuses, richer pure transforms/conditions; test concurrent claims and crash/restart; no general API/OAuth before approved scoped credentials. DBVORA adapter remains separate branch. Follow `docs/FAST_TRACK_5_WEEK.md`.
10. **Time/approval:** 2026-10-27 KST. User need not run any commands now. Engineering progress measured by actual test evidence; this is not a fully usable AX FLOW product. No schedule or percentage claim changed.

## 2026-10-27 — sprint acceleration / CLI status and resume
1. **Goal:** 3–5-day preferred, 7-day maximum requested review for reusable, *scope-limited* AX FLOW vertical slice (own engine, natural-language/template, SQLite, DBVORA read-only view), not full universal commercial system.
2. **Completed:** feature/axflow-mvp added read-only ledger `axflow/runlog.py`, optional CLI `status` and `resume`, tests/test_runlog.py, extra CLI integration test. Original `axflow.ir.v0` runner preserved. docs/SPRINT_7_DAY_HACKATHON.md, MASTER_SCHEDULE and ROADMAP updated.
3. **Executed tests:** isolated runlog unittest **2/2 PASS**, stubbed-engine CLI status + missing-id smoke PASS. Source blobs from GitHub byte-identical to locally exercised copies. **Combined full runner test suite on latest remote head still PENDING**; prior 5/5 engine tests were on older slice.
4. **Progress:** D1 first engine code + status/resume integrated, not a completed D5 full product. REA_APP is a separate 0.3.0 bounded analyzer; natural language/DBVORA/GUI/external auth not implemented.
5. **Failures/risk:** no new failing runlog tests; concurrent claims, cross-DB transaction generalization, Windows clean install remain unverified. Real outgoing actions/payments require separate user approval; avoid exposing step payloads in status.
6. **Repo/branch:** hibi89/AX_FLOW private, active branch feature/axflow-mvp. Re-read remote HEAD and test code to establish final SHA. main contains matching active schedule but does not receive unverified engine code.
7. **Environment:** local Python stdlib, synthetic SQLite fixture. No deploy, Windows or real provider tested. CLI supports validate/run/resume/status with synthetic flag.
8. **Source/privacy:** no third-party n8n code or live customer data/credentials; source is in isolated branch. Separate runtime and business SQLite paths.
9. **Next task:** execute full latest test suite and verify real CLI status/resume; then condition/data transform/CSV→SQLite step and natural-language template; then DBVORA readonly integration and Windows E2E. Follow daily release gates in docs/SPRINT_7_DAY_HACKATHON.md.
10. **KST:** 2026-10-27. The user 7-day calendar is a sprint aim, not a guarantee. Flag PARTIAL if any mandatory demo gate remains red.
