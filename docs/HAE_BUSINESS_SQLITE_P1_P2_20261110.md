# HAE P1/P2: Offline Business SQLite Portability — 2026-11-10 KST

## Objective and integration boundary

HAE's `axflow.state_backup` already supports **runtime execution-ledger** backup/restore. Customer business data (`business.sqlite`/`business.db`) is a separate database and needs explicit scope, its own safety policy and reproducible restore evidence. This does **not** copy DBVORA's proprietary repo, assert DBVORA service availability, or enable cloud sync.

### Options compared

| Approach | Performance / cost | Reliability & maintenance | Decision |
|---|---|---|---|
| A. Full live DBVORA remote backup via HTTP or direct DB transfer | More automation, but OAuth/DBVORA provider contracts, API operations, data owners and live WAL complexity; current permissions unverified, possible external data movement | High coupling / release risks | HOLD |
| B. Derive standalone offline business snapshot from tested local `state_backup.py` no-overwrite pattern | 32MiB single-file SQLite, stdlib-only, no service, no cloud expenses | Preserves existing runtime interface and allows independent database source validation, easy rollback | **Selected** |

## Implemented artifacts

- `apps/ax-flow/axflow/business_state_backup.py` derived from existing local `state_backup.py` into **separate module**; `state_backup.py` and original runtime acceptance unchanged. Operations: `inspect_business_state`, `backup_business_state`, `restore_business_state_pinned`.
- Checks: 32MiB limit, ordinary offline rollback-mode SQLite (WAL/journal/-shm/-wal/virtual/table triggers/views excluded), 1–64 business tables, 1–1024 schema objects, SQLite integrity and foreign key validation, source SHA256, no target overwrite, source mutation detection. Staged SQLite backup uses Python's `sqlite3.Connection.backup`; POSIX no-clobber `os.link` and Windows same-volume `os.rename` preserve existing target. Failure cleanup is inherited from the baseline implementation.
- `inspect_business_state` outputs only a source fingerprint/size/table count/status; **not** row values, table names, raw SQL, file paths or credentials.
- `apps/ax-flow/axflow/business_db_cli.py` offers `python -m axflow.business_db_cli inspect|backup|restore` from `apps/ax-flow` directory. **Every command requires `--synthetic`.** Backup/restore also require `--destination` and `--ack-new-file`; restore additionally requires exact owner-selected `--expected-sha256` (64 lowercase hex). CLI rejects unknown options without echoing their values. Files remain on the owner's computer. **Do not use real customer DBs in this P1/P2 prototype.**
- The old `python -m axflow backup/restore` commands continue to handle runtime ledgers, *not* business databases. No external upload, service registration, credential reading, installer, scheduling, OAuth, database migration, original-state overwrite or auto-restore.

Example with an already created **synthetic, closed, rollback-journal** SQLite DB:

```bash
cd apps/ax-flow
python -m axflow.business_db_cli inspect --source /tmp/synthetic-business.sqlite --synthetic
python -m axflow.business_db_cli backup --source /tmp/synthetic-business.sqlite --destination /tmp/backup-new.sqlite --synthetic --ack-new-file
# Copy artifact_sha256 from the successful backup receipt; do not use an arbitrary hash.
python -m axflow.business_db_cli restore --source /tmp/backup-new.sqlite --destination /tmp/restore-new.sqlite --expected-sha256 <SHA256_FROM_BACKUP_RECEIPT> --synthetic --ack-new-file
```

Use Windows filesystem paths locally on Windows. `restore-new.sqlite` must not exist. Native Windows/Linux SHA, filesystem junction and no-clobber behavior need separate exact-SHA test evidence before any real operational use. Snapshot integrity verification is not an antivirus, privacy-compliance, entitlement, or customer-readiness certificate.

## Test evidence

- Development environment Python **3.13.5 Linux**: an independent, functionally equivalent standalone SQLite portability implementation + synthetic user-like CLI completed **27/27 unittest PASS, 0 FAIL**, and `python -m compileall` PASS; existing files preserved. This is **design-prototype evidence only**, NOT execution of the exact GitHub-generated `business_state_backup.py` module.
- GitHub new tests registered: `apps/ax-flow/tests/test_business_state_backup.py` **16 cases**, `test_business_db_cli.py` **8 cases**. At exact GitHub SHA, these are **written but NOT_RUN**. Run from `apps/ax-flow` with:
  `python -m unittest discover -s tests -p 'test_business*py' -v`
- These tests exercise synthetic actual SQLite records, digest-pinned restore, no overwrite, missing ack/unknown flag redaction, WAL and unsupported schemas, bad FK, checksum mismatch, symlink, atomic destination conflict. **GitHub Actions previously failed before runner initialization** on the private branch; do not claim CI PASS or repeatedly spend budget on identical failing jobs.
- Full HAE/Lightning Azent/DBVORA/Windows/owner OAuth/customer environment remains **UNVERIFIED**; no Vercel or hosted Production.

## Work acceptance and next steps

P1 read-only supported SQLite business inventory (customer source SHA and schema count only); P2 offline explicit-ack SHA-pinned backup→restore into **a new** local target. These advance the HAE product requirements R-08 and parts of R-09, but are **not an actual connected DBVORA backup API integration** and do not satisfy full commercial DoD.

Acceptance needed before release: exact code native Python3.11 and Windows10/11 fixture tests, Windows hardlink/rename/symlink/junction review, full HAE + LA local synthetic regression, explicit DBVORA linked-source integration/independent restore check, three nondeveloper pilot workflows, licensed OAuth/Gmail/Sheets auth, packaging, documented privacy and real customer permission. Until then **RELEASE HOLD**.

Owner product management metric is a provisional estimation against the entire final-product scope. `65% → 70%` may be considered a **development milestone** for the two new capabilities, not that 70% of required tests or real customer flows passed. If exact SHA tests fail, stop and correct the score/evidence.

Rollback: new HAE files and docs only on `feature/axflow-mvp`; baseline HEAD `42d8de5d56f74ec0fa1908f16e162b538fe704e3` remains the original rollback anchor. Do not edit `main` or `feature/lightning-azent`, user data, keys, external credentials or products.
