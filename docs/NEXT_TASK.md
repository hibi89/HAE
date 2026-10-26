# Next work unit — 2026-10-27 KST (ACTIVE fast-track)

**Owner decision supersedes 21-week plan:** first 2 weeks REA_APP + own n8n-like runner; next 3 weeks AX FLOW + parallel DBVORA integration. Read docs/FAST_TRACK_5_WEEK.md, docs/TARGET_BLUEPRINT_V1.md, docs/CODEX_EXTRA_HIGH_ORDER.md before any implementation.

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
