# AX FLOW — master delivery schedule (v2, 2026-10-27 KST)

**ACTIVE PLAN: 2 weeks REA_APP + independently coded n8n-like runner, followed by 3 weeks AX FLOW + concurrent DBVORA readiness and integrated test. Total target 5 weeks, Oct 27–Nov 30, 2026.**

The former 21-week baseline is superseded, preserved in Git history. This aggressive target is conditional on focused work, a frozen limited v1 scope, supportable licenses, owner permissions, and available DBVORA acceptance. It does not guarantee a production-ready universal automation platform or every n8n connector. Detailed per-day tasks and exit criteria: [FAST_TRACK_5_WEEK.md](FAST_TRACK_5_WEEK.md). Frozen target: [TARGET_BLUEPRINT_V1.md](TARGET_BLUEPRINT_V1.md). Codex tasks: [CODEX_EXTRA_HIGH_ORDER.md](CODEX_EXTRA_HIGH_ORDER.md).

| Week / dates KST | Engineering phase | Exit evidence |
|---|---|---|
| W1 10/27–11/02 | REA_APP read-only JS/TS source analysis MVP by day 3, then lawful n8n architecture/spec study | actual local graph CLI, deterministic fixtures/tests, source+line evidence and clean-room contracts |
| W2 11/03–11/09 | **Our own** basic runner, typed IR, SQLite runtime ledger + business-data adapter, triggers/branch/error paths | 3 synthetic end-to-end executions, duplicate/restart/fail-safe tests |
| W3 11/10–11/16 | AX FLOW NL/template→IR, auto-config/test, local GUI; hackathon deadline protection | no manual JSON/node for supported workflow, bounded repair, real GUI smoke |
| W4 11/17–11/23 | OAuth/connector safety and DBVORA adapter in parallel | authorized provider scope, read-only supported DB inventory and offline state tests |
| W5 11/24–11/30 | integrated E2E with DBVORA, restart/security/Windows, packaging and trial | exact SHA+tests; linked SQLite map and supported restore proof if separately accepted |

**Do not conflate milestones:** Week 2 CLI proof != customer-ready; W5 v1 acceptance depends on DBVORA source-specific restore/Windows and provider permissions. If blocked, report PARTIAL with remaining gates and revised calendar, not completed.

### Cross-project scheduling conflict
Three hackathon hard deadlines fall in W3: KIC Nov 12 10:00 KST, PayPal Nov 13 05:00 KST, UGREEN Nov 16 16:45 KST. Submission or external account/license gates take precedence; the five-week date is a stretch target, not an obligation to skip essential release or competition evidence. Actual available coding hours are unknown and must be tracked rather than fabricated.

### Working style
MVP within **2–3 days** → compare with frozen blueprint → fill functional gaps → add broader security/reliability/Windows compatibility → supported-v1 integration & productization. Minimum source safety from day 1. Scope discipline and chief/Codex division per [CODEX_EXTRA_HIGH_ORDER.md](CODEX_EXTRA_HIGH_ORDER.md). 
