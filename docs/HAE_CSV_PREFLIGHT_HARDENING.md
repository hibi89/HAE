# HAE CSV preflight hardening and optional Lightning Azent adapter

Date: 2026-10-29 (KST)

## Implemented

- Preview reuses the HAE engine CSV parser and operation evaluators. It checks path allowlists, existence/type, the 256 KiB size cap, UTF-8, CSV shape, bounded rows/columns/cells, requested column references, normalization, filters, and numeric conversion. It does not initialize or write either SQLite ledger.
- Approval binds the request, input path, generated run ID, backend capability fingerprint, and input SHA-256. Before a first execution or incomplete-run resume, HAE revalidates the file. A changed file invalidates the preview. The verified bytes are passed to execution; completed identical retries retain durable idempotency.
- Upload, API, UI, and engine agree on 256 KiB. The existing limit was retained.
- Windows symlinks, junctions, and other reparse points are rejected; the file handle identity and metadata are checked around open/read. A native junction test runs on Windows. Path resolution plus metadata checks are not an atomic open guarantee against a hostile local process.
- Same-run attempts use a per-run Windows named mutex or POSIX `flock` plus an in-process lock. Process death releases the OS lock. POSIX lock artifacts are deliberately not deleted because removing a lock inode can break exclusion.
- An explicit `lightning-azent` backend option checks package API/schema/capability compatibility, rejects unsupported operations without fallback, and executes against the approved bytes staged in a private temporary directory. The Lightning Azent source branch was not modified.
- Preview UI shows the selected engine and ordered step summary. No input row values are returned in preview metadata.

## Verification

- HAE full suite before the latest regression addition: 96/96 PASS on Windows Python 3.11.9 (53.986 s); `compileall` and `node --check` PASS. After adding a dedicated cross-process adapter test: the adapter suite passes 4/4 and `compileall` passes; the entire HAE suite was not rerun after that test-only addition.
- Lightning Azent reference package: 65/65 PASS on rerun with unrestricted temporary-file operations. Its first sandboxed run had 2 backup errors and 1 concurrency failure because Windows hardlink/temp-file operations were restricted; this was environmental, not a source change.
- Browser E2E: localhost synthetic CSV Preview PASS (1 row, 2 columns, 25 bytes), explicit approval, SQLite execution completed with one row. No external service or customer data used.
- HAE HTTP integration against the real Lightning Azent package: import, conditional filtered import, and read-only lookup all matched HAE results; preview created no SQLite files; same approval replay preserved the result. Missing or incompatible package failed closed.
- Two separate Windows processes were synchronized and released together through the HAE adapter with the same run ID. Both returned completed status; the write-approval audit event appeared once and the SQLite import contained two rows. This confirms cross-process replay serialization for requests routed through HAE.
- A 30-iteration direct-package process-race probe observed duplicate approval audit events in 18/30 runs while retaining one business row. HAE adapter serialization covers calls routed through HAE; the independent Lightning Azent branch remains read-only, so direct external package callers are outside this fix.

## Remaining limitations

- This remains a synthetic local MVP. No customer data, external connectors, OAuth, paid service, or public deployment was used.
- Windows path checks materially reject reparse points and detect observed replacements, but do not claim kernel-level atomicity against an actively hostile process racing path resolution.
- Direct concurrent calls to Lightning Azent outside the HAE adapter retain the observed duplicate-approval-audit race.
- Work duration for the whole multi-turn session was not instrumented; no total elapsed time is claimed.