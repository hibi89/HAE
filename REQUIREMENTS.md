# Requirements — AX FLOW + REA_APP (2026-10-27 KST)

## Agreed product intent
### AX FLOW
1. Natural language is the primary control surface. Customers must not manually choose nodes, compose JSON or understand CLI/API details to get a supported task working.
2. Optionally choose an automation from a template catalog, attach CSV/XLSX/PDF or other explicitly supported input, or describe a task directly.
3. Planner infers shortest supportable route, explains required data/auth in plain Korean, and asks only genuinely necessary questions.
4. OAuth/API keys use least privileges, first-party consent and local secret storage; no credential pasting to model or silent approval.
5. Build workflow, dry run, verify result with evidence, ask for appropriate authorization, execute, schedule, recover and show observable logs/status. Risky actions need confirmation.
6. Local-first, CLI-capable deterministic runtime; small optional GUI/dashboard that hides irrelevant integrations, supports advanced inspection when needed.
7. No mandatory external DB for business data. Embed SQLite for engine state; Gmail/Google Sheets/cloud services are optional **external stores**, managed only via authorized connectors.
8. No mandatory cloud hosting; polling/local scheduling first, inbound webhooks via explicitly opted-in relay later. Free tier is not an availability guarantee.
9. Support optional DBVORA integration via standard scoped metadata APIs, not by merging DBVORA repository/code.
10. Commercial positioning: proposed 590,000 KRW assisted single-workflow implementation package, **unvalidated proposal**, not proof of buyers or guaranteed software price.

### REA_APP
1. Independently analyze authorized project source structures (files, dependencies, key call/data paths), output evidence-linked architecture report, help plan and verify changes.
2. First research target: source-available workflow automation (n8n functional study within applicable licensing/contract permissions); must distinguish first-party documentation, permissible source, proprietary terms and clean-room code.
3. Support eventual repair/extension and independent reimplementation, but never promise full replication of opaque/closed products.
4. The initial MVP uses static parsing/indexing before optional AI explanation; avoid loading an entire repository into one prompt.
5. REA_APP is a **development tool**, not AX FLOW runtime, not DBVORA, not a universal management suite.

## Non-goals at first MVP
No universal "automate anything" guarantee, no 24/7 operation on a powered-off PC, no bypass of OAuth/antibot controls, no mass third-party app integration, no pay-to-use API without approval, no n8n code-resale/white labeling, no real customer data and no production SLA.

## Acceptance gates
REA_APP: deterministic synthetic repository inventory/import graph and traceable report, tested with repeatable fixtures, memory/time caps and provenance. AX FLOW: a single synthetic workflow created via validated plan, executed with local SQLite, observed by CLI and restart recovery tested. OAuth/Gmail/customer deployment are subsequent separately approved/verified gates.
