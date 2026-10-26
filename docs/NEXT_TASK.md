# NEXT TASK — after DB-required architecture plan (2026-10-27 KST)

## Preconditions already verified
Repo hibi89/AX_FLOW is private, initial docs published. Branches main, develop, REA_APP, feature/axflow-mvp existed and were identical at earlier bootstrap checkpoint. User asked for dedicated DBVORA integration branch. Verify its actual existence and HEAD before work; do not assume docs means code.

## First code gate: REA_APP R1
1. From `REA_APP` branch, choose between Python AST-first (recommended zero-extra-dependency Python MVP, optional Tree-sitter for JS/TS) and Tree-sitter-first (broader languages but install/runtime complexity). Approval gate for substantive coding/dependencies.
2. Create only synthetic fixtures, read-only bounded repo walker, safe path/symlink rules, Python AST import graph with file/line evidence and deterministic JSON + human report in `tools/rea-app/`.
3. Run source inventory, graph, mutation/symlink/error limit tests. Note actual test counts and hash verification.
4. Update STATUS/HANDOFF and commit with actual SHA; move to permissible n8n functional study only with license provenance review.
5. In parallel define AX FLOW v0 typed IR schema and separate internal/business SQLite data model, but do not touch customer credentials or real customer data.

## Later DB gate (separate branch feature/dbvora-integration)
1. Confirm current hibi89/DBVORA `feature/p0-db-map` SHA and read newest HANDOFF/STATUS/code. Its latest documented 210 test definitions do not equal 210 passes on current head, and Windows acceptance is pending.
2. Design versioned, authenticated **read-only** localhost metadata contract for one user-selected SQLite DB first. DBVORA `/api/inventory` exists now but multi-asset generalized API does NOT.
3. Build AX FLOW adapter against fixtures/stubs and independently verified DBVORA real service, including authorized asset enrollment, offline failure, relationship provenance, schema upgrades, no raw rows, no source mutations.
4. Read-only UI DB map; backup/restore integration only through explicit consent and DBVORA's separately validated safety gates. No direct public server write endpoint or secret forwarding.
5. Update both repositories' contracts only if separately approved; do not silently alter DBVORA production or feature branch.

## Completion checkpoint
Review docs/MASTER_SCHEDULE.md weekly, record actual effort vs baseline. No claims of product-ready until docs/ACCEPTANCE_MATRIX.md tests all pass including DBVORA and Windows/GUI/customer cases. No paid API, external upload, provider OAuth app, public port, production or customer database without explicit approval. User `ㄱ` means next safe work unit.
