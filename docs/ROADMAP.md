# Roadmap (planning, not dates promised)

| Gate | Work | Evidence required |
| --- | --- | --- |
| R0 Bootstrap | Repo, security boundaries, docs, branch plan | metadata, refs, file fetch, commit SHA |
| R1 REA_APP core | Local repo inventory, imports/dependencies, source provenance, deterministic summary | real execution against synthetic fixtures, unit tests |
| R2 REA_APP n8n research | Permitted functional/architectural descriptions only; license audit | evidence-linked spec and clean-room review, no copied source |
| F1 AX FLOW local runner | Typed workflow spec, scheduler, SQLite job state, dry run, deterministic tasks | unit+integration+crash recovery tests |
| F2 AI UX | Natural language → validated plan; templates and file intake | independent validator, injection/error tests, manual acceptance |
| F3 Connector/Auth | Gmail send and Sheets with minimal OAuth scopes, consent | actual auth + explicit opt-in external action tests |
| F4 Optional GUI | Localhost UI for plan/auth/status, no node selection needed | browser/network/console/HTML tests |
| F5 DBVORA interface | read-only metadata and report contract | compatibility tests; separate DBVORA code and approvals |
| F6 Customer pilot | installation, permission audit, support budget, signed package and commercial checks | controlled customer acceptance; price/sales evidence |

Pricing hypothesis: 590,000 KRW assisted one-workflow install/service, no actual buyers confirmed. Prioritize supported narrow workflows before claiming general automation.
