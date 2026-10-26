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
