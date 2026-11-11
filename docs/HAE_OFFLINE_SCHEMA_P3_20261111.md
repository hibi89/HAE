# HAE P3 synthetic offline SQLite schema and Windows console diagnostics (2026-11-11 KST)

## Decision and boundary
- A real provider/DBVORA/OAuth-connected direct business database introspection requires additional credentials, permissions and supported endpoint verification; no agreement to access customer files or remote services.
- B explicit synthetic-only read-only metadata from a single user-selected local SQLite file, plus console error portability, selected for zero external cost, reversible scope and leak prevention.
- Source `apps/ax-flow/axflow/schema_inventory.py` (explicit `synthetic=True`, absolute path, 32 MiB max, no active journal/WAL, symlink, multi-link or unsupported schema; SQLite `mode=ro` and `PRAGMA query_only=ON`).
- Default receipt includes table/column/foreign-key counts, source SHA256, size, `customer_ready:false`, `dbvora_remote_verified:false`, `release_gate:HOLD`; no source pathname, table identifier, column identifier or data row. Explicit local owner-review switch permits schema identifier visibility. This is neither DBVORA's actual HTTP inventory nor customer deployment/backup certification.
- CLI: `cd apps/ax-flow && python -m axflow.schema_inventory_cli --source /ABSOLUTE/SYNTHETIC.sqlite --synthetic`; `--owner-review-names` for owner-only table/column/FK names. Invalid/unapproved inputs return status 2 with no source path in error.

## Tests and current CI
- New isolated Linux Python test command `PYTHONPATH=/mnt/data/hae_feature_work python -m unittest discover -s /mnt/data/hae_feature_work/tests -p test_schema_inventory.py -v`: **14/14 PASS, 0 FAIL/SKIP**, includes integrity, no rows, consent, schema relation, weird quoted Korean identifiers, data preservation, WAL/links, CLI refusal, mutation SHA. Exact source bytes are in Git blobs at commit `4f19b367f0573a553b0f89965dca7fab32a5c09d`.
- Console/port regression change `8c016035958650002dc40dff5df1f7f58cdc3af5`: output-only `ascii/backslashreplace` for local Unicode path in Windows cp1252; no filesystem path canonicalization or foreign file modifications. Test checks actual unavailable-port wording without weakening lock/bind preflight. Ancillary Windows alias expectation tests compare resolved paths.
- [Actions run #42971560893](https://github.com/hibi89/HAE/actions/runs/42971560893): Windows and Linux **FAIL** in entire Python suite. [#42972148842](https://github.com/hibi89/HAE/actions/runs/42972148842): Linux Python full FAIL, Windows running at time of this documentation. Stale checked-in distribution still not source-identical, and additional native Windows regressions remain; do not claim full PASS.

## Product score and stop conditions
- Existing HAE 70%; synthetic local schema provenance and owner-review map partial R-08/R-09 +3%p = **73% provisional final product**. 85% not reached; no real DBVORA provider, real Google OAuth, customer workflows, release packaging, user Windows acceptance.
- **RELEASE HOLD**. Existing .pyz/ZIP and production/main not modified; no secrets or customer files, paid APIs, permissions or external network connections used. Separate release candidate requires owner approval. Git rollback previous `d192e98daca82ba13a4f1b02e234a4da87b1cbae`.
