# AX_FLOW — AI-first Local Automation Platform

> Status: **Planning / Bootstrap only.** No working software, OAuth connector, workflow execution engine, or customer deployment has been verified.

## Product purpose

AX FLOW turns natural-language requests, attached files, and authorized service connections into **tested, executable local automations**. It should ask for only necessary user actions (e.g. OAuth consent), hide node configuration by default, and expose inspectable CLI + optional GUI workflows.

The analysis tool **REA_APP (Reverse Engineering Anything — APP)** is a **different component**: it studies source-available applications, creates architecture/function specifications and test evidence, and helps design independent implementations. It is not the AX FLOW runtime and not a central orchestration platform.

## Repository policy

This is a **private monorepo for now**. Logical products use separate directories (`apps/ax-flow/`, `tools/rea-app/`) on branches that include shared docs. Branches are **changesets, not permanent alternative copies of products**.

- `main`: stable shared source of truth and handoff docs.
- `develop`: reviewed integration work (created during bootstrap).
- `REA_APP`: requested development/research branch for REA_APP. New REA_APP work lands in `tools/rea-app/`; preserve the ability to integrate by PR.
- `feature/axflow-mvp`: AX FLOW MVP implementation branch, isolated from REA_APP.

Never bring n8n proprietary/licensed source into this repository without a separately verified right to do so. Research functionality, clean-room specifications, licensing and third-party notices must be tracked.

## Start here

1. Read `HANDOFF.md` → `STATUS.md` → `AGENTS.md` → `REQUIREMENTS.md` → `docs/ARCHITECTURE.md` → `docs/NEXT_TASK.md`.
2. Inspect actual GitHub branch, SHA, existing source, permissions, and test history.
3. Compare design options and obtain approval for material new implementation or licensing/security changes.
4. On completion, update `STATUS.md` / `HANDOFF.md` with verified evidence.

See `docs/ROADMAP.md` and `docs/REPOSITORY_LAYOUT.md`.

**No production deployment**, paid service, customer database, credential or external data upload is authorized by this bootstrap.
