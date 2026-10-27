### Gate R verifier self-tests (2026-10-27 KST)

The byte-exact `tests/test_verify_gate_r.py` file was executed against a byte-exact local reconstruction of `verify_gate_r.py` (both files matched their GitHub blob IDs). Result on Python 3.13.5 / Linux: **5 tests, 5 PASS**, covering known Git blob fingerprint, accepted reviewed fixture, tampered source rejection, unreviewed test rejection and symlink rejection. Windows symlink permissions require separate handling. The verification manifest now includes **14** reviewed modules/tests. This **does not** constitute a full REA_APP Python/Node suite run on an authenticated repository checkout; those remain pending.

## Reproducible Gate R P24 verifier

The `verify_gate_r.py` helper is a **local/offline verification entrypoint** for the reviewed REA_APP P24 sources. It checks the Git blob IDs of 14 source, adapter, package and test files against the reviewed `REA_APP@e6775a5b3bc17c2049238e0d505ec31e384d53ff` tree **before** running the Python and Node parser tests. It also refuses unreviewed executable modules/tests inside `rea_app/` or `tests/`. It uses an already installed Python, Node and pinned Babel dependency; **it does not run npm ci or install anything**.

From an existing authorized local checkout or reconstructed exact source tree, with `@babel/parser@7.29.9` already installed:

```powershell
cd tools/rea-app
python verify_gate_r.py
```

A passing result requires `SOURCE VERIFIED: 14/14`, `PYTHON_ALL: PASS`, `NODE_PARSER: PASS`, and exit status zero. Exact Python test counts and platform-specific skips remain visible in `unittest` output; do not convert a skipped Windows symlink test into PASS. A missing/mismatched source file, unexpected Python/JS test module, unavailable npm, or any failed suite causes a nonzero result. If any of the 13 reviewed source files change, verify the new exact GitHub SHA, review the diff and update the pinned manifest intentionally; **do not bypass the gate**.

**Evidence limitation:** The verifier's script and GitHub commits are published; the actual current REA_APP full test suite has **not yet run in this conversation's container** because a private authenticated checkout is unavailable. The script itself does not create CI, run background work, deploy, or claim Gate R readiness.

# REA_APP source analyzer

REA_APP is a local, read-only source inventory and architecture-evidence tool. It
does not execute inspected code, modify the selected source tree, collect secrets,
or send source to a service. The first supported parser adapter uses the pinned
Babel JavaScript/TypeScript parser; Python and other files
are inventory-only in this MVP.

## Run

Install Node.js 20+ and the pinned parser package from this directory:

```powershell
npm ci
python -m rea_app scan C:\path\to\authorized\source --output-dir C:\path\to\reports
```

Both the source root and report directory must be selected explicitly. Reports
are written as `source-map.json` and `source-map.md`; the report directory must
be outside the source root. Defaults cap the scan at 5,000 files, 1 MB per file,
20 MB total and 30 seconds of parser time. Adjust these limits explicitly when
needed; a total count/byte cap stops the scan without writing partial reports.

Compare two authorized snapshots with:

```powershell
python -m rea_app compare C:\path\to\baseline C:\path\to\current --output-dir C:\path\to\reports
```

The roots must be different, non-overlapping directories and the report
directory must be outside both. The comparison applies the same file and byte
caps to each snapshot and writes `change-impact.json` and `change-impact.md`.
It detects added, removed and modified indexed files by SHA-256, then follows
resolved in-root JS/TS dependency edges from both snapshots to report direct
and transitive dependents with import-line evidence and affected package
entrypoints. SHA-256 fingerprints are used internally to detect edits but are
not included in the report; file contents and absolute source paths are also
omitted. It is static reachability: it does not infer runtime impact,
Python dependencies, dynamic resolution or external package internals. Skipped
paths and scan coverage are called out so excluded or capped files are not
treated as compared.

The walker also excludes authentication dotfiles (`.npmrc`, `.pypirc`, `.netrc`,
`.git-credentials`, `.envrc`), shell history, Terraform state files, and
credential directories (`.ssh`, `.aws`, `.azure`, `.docker`, `.kube`, `.gnupg`,
`secrets`, `credentials`) before opening them. These are intentionally not
indexed. This is a denylist defense for supported stable source snapshots,
not a guarantee that arbitrary unknown secrets or live attacker-writable
folder swaps cannot be read. The added P24 tests are committed but require
full repo regression in an authorized checkout.

The walker skips common generated/dependency directories, secret-named files,
symlinks, binaries, non-UTF-8 source and oversized individual files. Package
boundaries, declared dependencies, package entry points, JS/TS imports/re-exports,
CommonJS `require`, exports and syntactic call sites include relative path and
line evidence. `tsconfig` path aliases are resolved when their targets are inside
the selected root. External package calls are classified from the import syntax
and package manifest only. A direct imported call is linked only when its static
module edge and matching target export are both observed. Other call sites remain
syntactic observations. Within one function or module scope, the analyzer also
reports simple identifier aliases, values returned from direct calls, identifiers
passed as direct call arguments, and direct identifier returns. It omits duplicate
or reassigned bindings. These are syntax-level observations, not control-flow-aware
taint analysis or cross-module value-flow claims; the tool does not execute code.

The report also records observed callable exports and their explicit parameter
and return type annotations. It includes names, optional/rest/default-presence
flags, and definition/export line evidence. It never records default values or
function bodies, and it does not infer types or describe function behavior.

For JS/TS, the report also recognizes direct path arguments to a bounded set of
Node `fs` read/write/list/delete APIs. It records safe relative string literals
with source-line evidence. Dynamic paths are marked without values, while
absolute, parent-relative, sensitive and unusual literals are redacted;
shadowed or reassigned bindings are omitted. Relative paths are not resolved
against the process working directory, and no file operation is executed.

## Verification

From `tools/rea-app` run:

```powershell
python -m unittest discover -s tests -v
npm run test:parser
```

The synthetic tests cover deterministic output, two-snapshot change and impact
reports, overlap/output/cap rejection, ESM and CommonJS references,
alias/external resolution, cyclic imports, entry points, syntax errors, binary and
secret exclusions, symlink handling where the host allows symlink creation,
Windows reparse-attribute detection, empty repositories, scan caps, missing-parser
behavior, local value-flow evidence, ambiguous/reassigned binding exclusions,
static Node fs path evidence/redaction, exported callable signatures and
source-tree integrity.

The Windows host used for the current verification denied junction creation
(`Access denied`). The reparse-attribute branch is unit-tested with synthetic
file attributes, but an actual filesystem junction fixture remains unverified.

## File-identity guard (P23)

A race between resolving/stat-ing an input and actually opening it could otherwise read a replaced file. The scanner now uses `O_NOFOLLOW` for the final input path component when the OS supports it, and compares the opened descriptor's device/inode with the earlier stat before accepting bytes. A path that changes identity is skipped with `file_identity_changed`; an open-time link refusal is reported as unreadable. Two synthetic regression cases are committed under `tests/test_scan_open_races.py` (replacement of a regular file; POSIX final-component symlink swap). The earlier normal-path scan behavior is unchanged.

**Limit:** This is a bounded final-component/identity guard, not a guarantee against all ancestor-directory replacement races or hostile concurrent filesystem changes. Windows junction tests still require a permitted Windows host. Use only explicitly authorized, suitably trusted source snapshots.

**Verification state:** Prior exact remote source (`ff7997f2...`) passed Python 15/15 and Node parser tests on Windows; the later `96d1ced...` revision only changed handoff/status/next-task docs. This P23 code + its two new tests were committed through the GitHub connector but **the current REA_APP branch full suite has not been run**. A standalone local POSIX file-open behavior reproduction checked identity mismatch and `O_NOFOLLOW` outcomes (2/2 PASS), which is not equivalent to running `tests/test_scan_open_races.py` or the complete package.
