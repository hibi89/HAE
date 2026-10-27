# HAE (Humanized Automation Ecosystem) and REA_APP — requirements (2026-10-27 KST)

**Naming amendment:** HAE supersedes the former AX FLOW product name. This is a brand update; all requirement IDs and technical completion gates remain unchanged. Lightning Azent is the planned independent engine. Current `axflow` source names remain for compatibility.

## Product goal, now confirmed
HAE must go beyond AI JSON output: **customer instruction/template + optional files → validated internal workflow IR → automatic configuration → only necessary OAuth/API consent → dry-run and tests → error diagnosis/safe repair → approved live execution → scheduling, monitoring, recovery, and database visibility.** No manual node setup or copied JSON required of end users.

## Mandatory HAE requirements
R-01. Natural-language and suggested-template intake; minimize questions; helpful plain Korean instructions for unavoidable external authentication/permissions.
R-02. Customer-file intake with strict allowlist, provenance, size/type limits and local default; CSV first, XLSX/PDF later with explicit parsing and confidentiality handling.
R-03. Internal **typed JSON workflow IR (schema+version)** separated from AI-generated prose; validation, idempotency classification, allowed connectors, rollback/compensation and per-step receipts.
R-04. Deterministic local CLI runner independent of GUI. AI may plan/diagnose but cannot run unrestricted shell or modify customer sources unsupervised.
R-05. Auto-fill supported integration settings; scoped secret broker/OAuth in OS secure store; provider consent and high-risk live actions require user authorization. No plaintext token in plans, logs or model context.
R-06. Dry-run, fixtures, simulated failures, controlled retries, observed results and bounded auto-repair. For ambiguous remote responses, verify before resending or request review. Don't promise global exactly-once.
R-07. **Embedded SQLite engine database, mandatory from first runtime MVP**: versioned workflow definitions, job/step state, run IDs, approvals, checkpoints, receipts, audit records and idempotency keys; transactional schema upgrades/backups; no customer email body duplication by default.
R-08. **Business data plane mandatory for full product**: explicit SQLite dataset read/write adapter and a provider-neutral asset registry/typed metadata contract. PostgreSQL and Google Sheets adapter coverage planned; no universal full-DB capabilities claimed for SaaS.
R-09. **DBVORA integration mandatory for full bundled-product acceptance**: approved DB asset link, SQLite schema/table/column/FK map, measured size/status where possible, read-only inventory API, offline/disconnected handling and independently verified backup/restore of supported sources. DBVORA remains a separate private repo/process and keeps its own safety controls. Initial engine MVP may be accepted before this final gate.
R-10. Data owner chooses storage; no automatic migration, mirroring, source DB mutation, cross-account discovery, full Gmail sync or automatic customer DB deletion. Google Sheets can be a data sink without being an actual SQL DB engine.
R-11. Local-first, CLI + minimal GUI, irrelevant plugins hidden, optional approved webhook relay/cloud later. PC must run for local schedules.
R-12. Security from first MVP: localhost binding, CSRF/origin/path validation, prompt injection resistance, least privilege, outbound safeguards and fail-closed recovery; no external transmission by default.
R-13. Evidence-based performance comparison (latency, memory, retries, operator interventions), reproducible regression tests and local/Windows validation before commercial claim.

## REA_APP
R-A1. Inventory authorized source trees, parsers/imports/data paths, evidence-linked architecture and change-impact report. No entire large repo in one prompt.
R-A2. Observe n8n within verified license/contract permissions; no unlicensed source copying, UI cloning or code transplantation into HAE.
R-A3. Provide useful static-analysis MVP first, then permitted n8n research and independent specs; retain REA_APP as separate internal tool.

## Full completion (not just MVP)
1. A nondeveloper can create, authorize, validate, deploy and supervise **three supported end-to-end automations** (local CSV→SQLite, Google Sheets→local storage, authorized Gmail report) without selecting nodes/editing JSON; use safely prepared synthetic data first.
2. Workflow restart recovery and duplicate external-action protections are verified under fault injection.
3. DBVORA panel shows linked supported SQLite DB → tables → columns/relations, measured size/provenance, and backed-up source can be restored independently without source mutation (for supported DB/source types only).
4. Auth, logs, file input, UI, customer Windows package and real browser tests pass; signed or explicitly characterized distribution; documented privacy and limits.
5. At least 3 controlled customer-style pilot workflows complete and yield support-time/performance evidence; commercial contract and license review complete. Pricing hypothesis 590,000 KRW per assisted single-workflow service is NOT market acceptance evidence.

## Explicit limits
No promise to automate literally every app, operate with a powered-off local PC, bypass OAuth/antibot, read cloud provider internals, eliminate all outages, or resell n8n derivatives. Real customer data, public ports, OAuth app registration, paid services and customer deployment need approval.
