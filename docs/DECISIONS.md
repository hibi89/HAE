# Decisions and pending approvals

2026-10-27 — Owner set public-facing tentative product name **AX FLOW** and renamed an initially empty REA_APP repository to `hibi89/AX_FLOW`; confirmed private. Owner explicitly requested a `REA_APP` branch and additional basic organization.

ADR-001 (PROPOSED): Private monorepo with separate source directories `apps/ax-flow` and `tools/rea-app`, stable main, develop integration, separate feature branches. Honors a single repository while avoiding project identity tied only to branches. Split later if independent permissions/releases are needed.
ADR-002 (PROPOSED): Local-first Python core, CLI and minimal web UX; external AI/OAuth opt-in; optional separate DBVORA API.
ADR-003 (REQUIRED): No n8n source/asset inclusion or modified derivative commercial distribution unless explicitly legally cleared. Prefer independent implementation with documented provenance.
ADR-004 (REQUIRED): Owner approves paid services, external data, customer accounts, security/visibility changes, real file mutation, production release.

None of these are claims of completed software functionality; technical architecture awaits final approval for implementation.
