# Decisions and pending approvals

2026-10-27 — Owner set public-facing tentative product name **AX FLOW** and renamed an initially empty REA_APP repository to `hibi89/AX_FLOW`; confirmed private. Owner explicitly requested a `REA_APP` branch and additional basic organization.

ADR-001 (PROPOSED): Private monorepo with separate source directories `apps/ax-flow` and `tools/rea-app`, stable main, develop integration, separate feature branches. Honors a single repository while avoiding project identity tied only to branches. Split later if independent permissions/releases are needed.
ADR-002 (PROPOSED): Local-first Python core, CLI and minimal web UX; external AI/OAuth opt-in; optional separate DBVORA API.
ADR-003 (REQUIRED): No n8n source/asset inclusion or modified derivative commercial distribution unless explicitly legally cleared. Prefer independent implementation with documented provenance.
ADR-004 (REQUIRED): Owner approves paid services, external data, customer accounts, security/visibility changes, real file mutation, production release.

None of these are claims of completed software functionality; technical architecture awaits final approval for implementation.

## 2026-10-27 — database included in full AX FLOW acceptance (architectural decision)

**User intent clarified:** customer-facing natural-language AX FLOW must not merely emit JSON. It must auto-configure and test workflows, and **data management/database visibility is a completion requirement**, not a decorative add-on.

- ADR-005 ADOPTED BY USER REQUIREMENT: local SQLite job/status state from F1, explicit business database connectors for F1/F3, DBVORA visibility and verified archive/recovery interface before full-bundle sign-off. A pure Gmail/send action does not need a duplicate business DB; Gmail is authoritative for sent mail.
- ADR-006 DESIGN SELECTION (documentation; no implementation): **independent DBVORA local process + versioned read-only API** over copying DBVORA into AX FLOW. Compare costs/security/maintenance in docs/ARCHITECTURE.md and docs/DATA_ARCHITECTURE.md. Initial AX FLOW-side feature branch `feature/dbvora-integration`.
- ADR-007 SAFETY: no automatic full source-data mirroring, no raw user data in workflow logs or GitHub, no backup/restore until source integrity and separate restore are verified; all data operations opt-in with least privilege.
- ADR-008 SCHEDULE BASELINE: 21 engineering weeks / 445–750 focused implementation-test hours as **planning estimate**, 2026-10-27 to 2027-03-22 if work proceeds continuously, plus 2–6 week risk buffer where needed; see master schedule. External Google approval/pilot availability is not under direct control.
- No paid cloud/third-party transmission, customer DB changes, changes to DBVORA repository, or commercial release approved.

## 2026-10-27 — owner-driven FAST TRACK supersedes 21-week baseline

Owner clarified hard planning intent: **REA_APP + n8n-inspired wholly independent runner in up to 2 weeks, then AX FLOW + concurrent DBVORA completion and supported integration testing in another 3 weeks, total 5 weeks**. This overrides prior 21-week planning *for scheduled work*, not the complete safety/product acceptance requirements. “n8n modification” must be interpreted as research of permissible architecture and new independent implementation, not copying/forking n8n customer source. Owner prefers working 2–3-day MVP before progressive feature-gap closure and later broader hardening.

ADR-009: freeze a scope-limited v1 blueprint; Codex GPT-6 Extra-High is implementation/test agent while chief GPT-6 owns architecture/acceptance; feature growth deferred if W1/W2 fails. Both programs remain distinct tools. The 2026 3-hackathon deadlines overlap W3, and available coding hours/provider gates can invalidate the stretch deadline. No Codex session/background work is started by publishing docs.

Active master schedule: docs/MASTER_SCHEDULE.md (v2). Detailed day/week work: docs/FAST_TRACK_5_WEEK.md; frozen target: docs/TARGET_BLUEPRINT_V1.md; Codex: docs/CODEX_EXTRA_HIGH_ORDER.md. Original 21-week baseline retained in Git history.
