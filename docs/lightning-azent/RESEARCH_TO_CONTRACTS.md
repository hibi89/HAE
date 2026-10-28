# Lightning Azent Gate N — official-document evidence → independent contracts

## Local implementation verification update — 2026-10-28

The table below preserves the earlier research snapshot; its historical `NOT RUN` entries are superseded for local MVP execution by `feature/lightning-azent@7df9aa1f419696ed04cf98ecc1fd99470db54cd9`. Windows 10 / Python 3.11.9 `verify_local.py` recorded 9 PASS / 0 FAIL / 1 SKIP: LA 65/65, existing HAE regression 84/84, preflight and four synthetic CLI flows passed. The conditional flow audits its skipped path and confirms no business writes. A separate committed test hard-exits a real child process immediately after a scheduled SQLite commit and confirms same-tick recovery with exactly one business row. Offline wheel packaging remains skipped because `wheel` is unavailable. The product integration and licensing gates below remain open; this evidence proves only the tested local engine slice.

Checkpoint: 2026-10-27 KST. **PARTIAL RESEARCH / SOURCE-INDEPENDENT PROTOTYPE.** This is not a claim that n8n internals, source code, or private workflows were inspected with REA_APP. REA_APP R1 is separately reported PASS at REA_APP@3fd0ac452ea3255a24998f550aba3cbf9e6a263d (Gate R 66 PASS / 6 SKIP; QA 11/11; real Babel and clean-wheel smoke logged). The runner itself has not rerun those tests.

## Legal boundary and method

Official n8n license says n8n's Sustainable Use License is source-available, **not an OSI open-source commercial-use grant**. Its source-use, derivatives and redistribution provisions limit uses; additional commercial arrangements may be required. Enterprise-only code has separate licensing. Sources:
- https://docs.n8n.io/sustainable-use-license/
- https://github.com/n8n-io/n8n/blob/master/LICENSE.md
- https://github.com/n8n-io/n8n/blob/master/LICENSE_EE.md

Only public *product-behavior documentation* was consulted for this note. No n8n source, UI assets, connector implementation, code fragments or executable n8n runtime were copied or run. Legal clearance for any n8n source study in a competing commercial product is **NOT ESTABLISHED**. If further source inspection is proposed, stop for explicit permission/legal review. Our implementation donor is **owner-controlled HAE code** from feature/axflow-mvp@30bb9eb979d1cd2c1180e0bcee419da60e182ed4, not n8n.

## Six evidence-linked, deliberately independent contracts

| Contract | Official documented observation (not internal implementation claim) | LA original contract / difference | Verification |
| --- | --- | --- | --- |
| LA-C01: typed workflow | n8n public documents describe workflows and steps/data mapping, but no specific internal IR schema was established from these pages: https://docs.n8n.io/data/data-mapping/data-mapping-ui/ | LA owns a strict, explicitly versioned JSON IR. Current extraction supports only legacy axflow.ir.v0; native azent.ir.v0 is not implemented. Unknown operations fail before side effects. | Current copied validator; independent parity tests committed, **NOT RUN** |
| LA-C02: flow/data provenance | n8n documents item linking between nodes via input-output association: https://docs.n8n.io/data/data-mapping/data-item-linking/item-linking-node-building/ | LA uses explicit step references, guarded condition/branch and synthetic payload lineage; NOT equivalent to n8n's item-linking implementation. | Synthetic guarded-branch fixture test **NOT RUN** |
| LA-C03: local-only data | n8n documents previous-node reference mapping, not our business SQLite semantics: https://docs.n8n.io/data/data-mapping/data-mapping-ui/ | LA supports CSV read/filter/import only inside selected local input root, bounded size and approved writes, separate runtime/business SQLite. No external connector. | Synthetic 2-row CSV import test **NOT RUN** |
| LA-C04: execution/replay | Official executions page describes Running, Success, Failed and Waiting plus retry of original/saved workflow: https://docs.n8n.io/workflows/executions/all-executions/ | LA maintains its own SQLite run ID, plan fingerprint, receipts and replay safeguards for local operations. No global exactly-once or n8n retry parity claim. | Existing HAE historical evidence; new LA branch **NOT RUN** |
| LA-C05: trigger/control | Public docs list trigger node categories and scheduled workflows: https://docs.n8n.io/ | LA intentionally supports only manual/interval (1–86400 seconds); other trigger kinds fail closed. No background Windows service or cron/webhook. | Two-tick synthetic interval test **NOT RUN** |
| LA-C06: credentials/policy | Official n8n documents node credential sharing and security audit of risky file/code nodes: https://docs.n8n.io/workflows/sharing/ and https://docs.n8n.io/hosting/securing/security-audit/ | LA has no provider credentials, no OAuth/secret storage and no network/shell execution. SQLite writes require an explicit boolean. Future external actions need separate approval and opaque broker handles owned by HAE. | Negative-operation and no-approval tests committed, **NOT RUN** |

All n8n entries above are OBSERVED only as product-documentation descriptions. LA entries are independent product DESIGN/EXISTING HAE OWNED SOURCE, not n8n behavior replication claims.

## Three acceptance fixtures — precise local-only MVP slice

- LA-F01 `docs/lightning-azent/fixtures/csv-filter-import.json` and original `orders.csv`: reject absent write approval, then insert two rows into distinct business SQLite; source SHA unchanged and replay no duplicate writes.
- LA-F02 `conditional-route.json`: true branch returns `{"route":"accepted"}` with no business writes; false branch is skipped.
- LA-F03 `interval-replay.json`: two synthetic due ticks yield distinct run IDs and two rows; resume preserves tick index; no real daemon or external actions.

The fixtures were drafted earlier and now have new LA-specific tests under `packages/lightning-azent/tests/test_mvp.py`. **Test existence does not imply executed PASS.**

## Selected design and remaining gates

A. Rename HAE `axflow` runtime in place: fast but risks breaking prior imports, CLI, and protected HAE work. Rejected.
B. Stage the owner-written local execution primitives unchanged into `packages/lightning-azent/lightning_azent`, then prove parity before switching HAE imports: selected. This incurs temporary duplication but preserves recovery via original HAE path and explicit Git history.
C. Copy/modify n8n code: not selected due independence/licensing risk.

**Gate N research is PARTIAL:** no source-based internal n8n observations or license clearance; source research is not a prerequisite for independently implementing these owner-authored, documentation-informed contracts. **Gate L is IMPLEMENTED-STAGING / UNVERIFIED** until an actual full Python test run, three synthetic fixtures, fresh import/CLI evidence and Windows safety checks are recorded against exact branch SHA. Do not merge into HAE, modify production or claim engine complete before that gate.
