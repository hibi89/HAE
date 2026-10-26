# AX FLOW master engineering schedule — baseline v1 (2026-10-27 KST)

**Planning estimate, not guaranteed delivery.** Assumes one AI-assisted lead doing hands-on coding + independent tests, approximately 21–36 effective development/test hours per week, no paid cloud, synthetic data first, sequential critical path. Continuous calendar baseline: **Tue 2026-10-27 → Mon 2027-03-22 (21 weeks)**, approximately **445–750 focused engineering hours**. Expect **2–6 additional weeks** if auth verification, external customer availability, Windows fixes, unfamiliar upstream code, or limited working hours cause delays; date is not a contractual promise.

| Week | Date (KST) | Hours (range) | Owner/work branch | Deliverable / exit gate |
|---|---|---:|---|---|
| W1–W2 | 2026-10-27–11-09 | 40–65h | REA_APP | read-only source inventory, AST import map, evidence + synthetic regression |
| W3 | 2026-11-10–11-16 | 20–35h | REA_APP | licensed/authorized n8n functional study, independent flow/DB/execution specs |
| W4–W6 | 2026-11-17–12-07 | 70–110h | feature/axflow-mvp | typed IR, local CLI runner, runtime SQLite, separate business SQLite, resume/idempotency synthetic tests |
| W7–W9 | 2026-12-08–12-28 | 65–100h | feature/axflow-mvp | natural language plan → schema, templates, bounded CSV/XLSX file intake, dry-run and auto-repair |
| W10–W12 | 2026-12-29–2027-01-18 | 60–110h | feature/axflow-mvp | scoped Google OAuth, Gmail send + Sheets, approval/wizard, rate/duplicate/failure tests |
| W13–W14 | 2027-01-19–02-01 | 40–70h | feature/dbvora-integration | AX FLOW ↔ DBVORA authenticated read-only adapter, DB inventory/map/provenance, offline behavior; backup proof plan |
| W15–W16 | 2027-02-02–02-15 | 40–70h | feature/axflow-mvp | local customer web GUI, no-node flow, auth help, run history and DB management pane |
| W17–W19 | 2027-02-16–03-08 | 70–120h | develop | regression, source/backup/restore gate, prompt-injection/security tests, Windows packaging/browser, performance evidence |
| W20–W21 | 2027-03-09–03-22 | 40–70h | develop → main | 3–5 controlled real-world-shaped pilots, support/price hypothesis, full acceptance report and release decision |
| **Total** | **21 weeks** | **445–750h** | all | **Full feature completion is conditional on tests, DBVORA and authorization** |

## Milestone checkpoints
- **First 3 days (Oct 27–29):** REA_APP bounded source walker skeleton and synthetic test baseline if architecture approved and coding is available. Not a marketable MVP.
- **W2:** REA_APP core MVP; source report verified with synthetic fixtures.
- **W6:** locally executable workflow + runtime SQLite + separate business SQLite, data not yet OAuth.
- **W9:** natural-language/local-file technical preview and simulated repair.
- **W14:** end-to-end managed SQLite inventory and offline DBVORA bridge on fixtures (not yet Windows/customer readiness).
- **W19:** release candidate only if restore/injection/fault/browser/Windows gates all pass.
- **W21:** target final release review; **do not call completed if any mandatory gate failed**.

## Dependencies, concurrency and risk
- REA_APP R1 must be adequate for research, **not 100% complete** before AX FLOW starts; small independent AX FLOW data model design can run in parallel. n8n source is research only.
- F1 SQLite transaction/journal + a real business data adapter are prerequisites for reliable F2 file/AI and D1 DBVORA integration.
- Google OAuth app verification/scopes and consent may introduce unknown external waits; simulate connectors first, no fabricated successful authentication.
- DBVORA `feature/p0-db-map` latest documented 210 test definitions ≠ 210 passed; full latest-suite, Windows/NTFS/physical cut and customer release remain independently gated. AX FLOW cannot silently promote DBVORA readiness.
- API/service charges, users' credentials, real databases, license obligations and customer pilots need explicit approvals. Calendar slips when approvals are unavailable.
- Monthly review: compare estimate vs actual hours, test pass/fail, scope, dependencies. Do not extend scope silently or promise delivery date.
- Risk buffer **2–6 weeks** beyond W21 could move review into 2027-04/05; capture actual slips in STATUS/HANDOFF and update this baseline by versioned decision.

## Product distinction
`MVP_INTERNAL` at W6 is not saleable; `PILOT_CANDIDATE` at W14–W16 is not final. Full release includes automatic build/test/run **plus supported DBVORA management**, explicitly restored supported DB backups, OS security and real user acceptance. Price 590,000 KRW is a proposed assisted service value, not verified demand.
