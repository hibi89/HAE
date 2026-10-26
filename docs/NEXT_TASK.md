# Next work unit — 2026-10-27 KST (ACTIVE fast-track)

## Current checkpoint (P6 filtered planner and UI/API verification passed)

On feature/axflow-mvp@7190f5a3c8a238b1f33a948dd9a3df0d5e121b37, Windows Python 3.11.9 full suite is 47/47 PASS; JavaScript syntax and Python compilation pass. The planner supports full import, filtered import, conditional import and read-only match-count/original-row-number lookup. Filtered recovery preserves original row numbers and does not persist matching row payloads in receipts. P5 DBVORA synthetic API smoke remains verified at baseline commit 06ba9f011796090b84e4625bcd65ded848412e34.

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
