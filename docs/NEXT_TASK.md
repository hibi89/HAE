# Next work unit — 2026-10-27 KST (ACTIVE fast-track)

**Owner decision supersedes 21-week plan:** first 2 weeks REA_APP + own n8n-like runner; next 3 weeks AX FLOW + parallel DBVORA integration. Read docs/FAST_TRACK_5_WEEK.md, docs/TARGET_BLUEPRINT_V1.md, docs/CODEX_EXTRA_HIGH_ORDER.md before any implementation.

## Codex first authorized implementation unit (MVP D1–D3, REA_APP branch)
1. Verify hibi89/AX_FLOW current HEAD and read HANDOFF/STATUS/AGENTS/REQUIREMENTS/docs + actual code.
2. Build read-only bounded source walker and parser-accurate JS/TS import/export graph with file/line provenance under tools/rea-app. Python AST optional. Use a permissible local AST parser (TypeScript compiler API/Tree-sitter) with pinned version; no code copied from n8n.
3. Design small synthetic JS/TS fixture, run CLI end-to-end, return deterministic JSON+Markdown. Fail closed on huge/binary/secret/symlink/file escape cases. Never execute inspected code or mutate the source root.
4. Fix test failures; report **actual** commands, PASS/FAIL/SKIP, exact commit SHA and target blueprint gaps. Avoid asking owner to do work Codex can do itself. No blanket “finished” claim from skeleton.
5. D4–D6 permitted n8n study and original behavior contracts; D7–D14 independent executor remains a planning target only and is on hold until chief review. Do not implement the standalone AX FLOW engine before that review.

## Chief review gate
Compare every completed small module against docs/TARGET_BLUEPRINT_V1.md, identify high-priority missing features, and allow Codex to implement immediately within approved scope. First design decisions preselected for speed (bounded Python CLI + AST parser adapter, native JSON IR, SQLite, local-first). Escalate new paid costs/licensing, public visibility, user secrets, real external API/DB operations or destructive effects only.

## DBVORA parallel work
AX FLOW-side feature/dbvora-integration branch only. Check independent DBVORA source/API/Windows gate before committing adapter claims. No dependency on a nonexistent universal API; safe read-only SQLite inventory first. Preserve separate runtime and business SQLite.

## Safety
The active 2026 hackathon deadlines overlap Week 3; don't override submission priorities. 5-week target is conditional, no automatic background execution. Update STATUS/HANDOFF when actual implementation/test results change.

## 2026-10-27 KST — MVP checkpoint
The first REA_APP CLI MVP is implemented and its 8 Python integration tests plus the Node parser-adapter assertions pass on synthetic input. The physical symlink/junction test is limited by this Windows sandbox's link-creation permissions; the scanner's link branch is covered with a test double. The clone/DNS and local `.git` write failures, parser version adjustment, output-write workaround and exact GitHub commit SHA are recorded in `STATUS.md` and `HANDOFF.md`.

The blueprint call-evidence gap is closed for a supported subset: direct imported calls are linked only with a unique in-root module edge and matching export. Multiline ESM and nested package boundaries pass in synthetic tests. Remaining coverage limits are recorded in `STATUS.md` and `HANDOFF.md`.

Next work unit: perform bounded n8n architecture and licensing research using official product documentation, then summarize independent behavior contracts for trigger/step execution, persistence, credentials, retries and errors. Do not copy n8n source/UI/node code or implement the standalone AX FLOW engine during this stage.

## 2026-10-27 KST — n8n documentation findings and gate

Completed this docs-only pass against official n8n documentation and the n8n Help Center:

- **Graph execution:** webhook, polling, and other event/time triggers start runs; a single run is started by its eventing trigger. Workflows created from n8n 1.0 finish branches one at a time in canvas top-to-bottom/left-to-right order; workflow settings can change the execution order.
- **Queue architecture:** main intake handles triggers/webhooks and enqueues execution IDs in Redis; workers load workflow data from the shared database, run it, write results/status to the database, and notify main via Redis. Main, workers, and webhook processors share `N8N_ENCRYPTION_KEY`. Queue mode is not a SQLite deployment target.
- **Recovery:** manual retry is a new execution that reuses results from completed nodes. The failed node receives saved input and processes all its items again, so a partial side effect within that node may duplicate; retrying a sub-workflow node reruns that sub-workflow. Error workflows receive a different payload for trigger activation errors; execution ID/URL require a saved execution.
- **Persistence:** execution save settings are configurable. Pruning defaults to enabled and removes finished records when they exceed 14 days or 10,000 records; new/running/waiting executions are excluded. The database must be backed up before supported encryption-key rotation.
- **Commercial boundary:** the official current SUL FAQ says internal organization authoring is permitted in Community, while customer-facing automation authoring/configuration, hosted service or white-label use requires a commercial license. Treat this as a product-boundary signal only; get written guidance from n8n before any commercial integration decision.

Sources: [execution order](https://docs.n8n.io/build/flow-logic/understand-execution-order.md), [trigger/action types](https://docs.n8n.io/connect/create-nodes/plan-your-node/choose-a-node-type.md), [retry](https://docs.n8n.io/build/understand-workflows/understand-executions/view-all-executions.md), [errors](https://docs.n8n.io/build/flow-logic/handle-errors-gracefully.md), [queue mode](https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/enable-queue-mode.md), [execution retention](https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/manage-execution-data.md), [key rotation](https://docs.n8n.io/deploy/host-n8n/configure-n8n/security/rotate-encryption-keys.md), [SUL FAQ](https://support.n8n.io/article/can-i-use-your-license-for-my-use-case).

Verification on synthetic fixtures: `python -m unittest discover -s tools/rea-app/tests -v` — **8 passed**; `npm --prefix tools/rea-app run test:parser` — **PASS**. One first test command omitted `NODE_PATH`, causing 3 expected parser-unavailable failures; setting it to the installed global Babel parser location made the entire suite pass. A standalone credentials environment-variable docs page was inaccessible; encryption-key evidence was cross-checked from queue-mode and key-rotation docs. No n8n source or runtime used.

**Hold point:** before any independent AX FLOW runner/engine work, chief review must compare the passing REA_APP scope and remaining blueprint gaps. Current REA_APP limits: Python AST, value/data-flow, physical symlink/junction and clean npm install validation, Windows packaging, and authorized real-source validation. The next task is to decide which of these merit a bounded follow-up; do not start the standalone engine before review.
