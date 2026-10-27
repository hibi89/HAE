## P53 — direct ESM re-exports in the current callable inventory

The current `source-map` and `functional-contracts` reports include explicit
`export { sourceName as publicName } from "./module"` callable signatures when
one re-export edge is uniquely resolved inside the selected root and the target
contains one matching direct callable. The contract records both the target
definition and façade export path:line evidence. Re-export chains, wildcard,
external, unresolved and ambiguous same-line exports are omitted. This bounded
rule also feeds baseline/current contract comparison without reparsing.

The P53 wheel was installed offline into a fresh Python 3.11.9 environment;
`npm ci` then installed the exact packaged Babel lock without lifecycle scripts.
The installed CLI produced all eight diagram-enabled bundle reports, including
the direct façade contract, with byte-identical rerun output and unchanged
synthetic sources. The wheel was not published; details and its hash are in
`STATUS.md` P53.

## P50 — installable Python wheel

REA_APP now builds a pure-Python wheel with a `rea-app` console command. The
wheel includes the Babel adapter, npm package manifest, and pinned lockfile.
Python requires 3.11 or newer; JS/TS parsing also requires Node.js 20 or newer
and `@babel/parser@7.29.9`. After installing the wheel, run `npm ci` with the
installed `rea_app` package directory as its prefix, then use `rea-app scan`,
`rea-app compare`, or `rea-app bundle`.

The local wheel was built and installed into a clean Python 3.11.9 venv; the
installed version command, synthetic scan, and six-report bundle worked with
the exact local Babel version. This host could not resolve `registry.npmjs.org`,
so the wheel's registry-based `npm ci` step has not been verified here. See
`STATUS.md` P50 for the wheel hash, Gate R counts, and evidence path.

## P49 — CommonJS default callable aliases

The exported callable comparison follows a direct CommonJS identifier assignment such as `module.exports = createUser` back to the unique `createUser` function declaration in the same module. An ESM default function and its CommonJS default assignment can therefore be compared with their explicit signature and export-kind evidence. This does not infer object-export contents, alias chains, reassignment, or runtime compatibility. The real-parser regression and full Gate R results are recorded in `STATUS.md` under P49.

## P48 — Unicode paths and dynamic import coverage limits

The source map preserves statically observed dynamic imports written as a string literal or a template without substitutions. When the relative target exists inside the selected project, the edge resolves like other imports. Computed imports such as `import(name)` or interpolated templates are recorded with `resolution: unresolved_dynamic`; the report does not expose the expression text or guess a target. Their source file and line remain available as evidence. This is syntax-level coverage and does not predict runtime module loading.

The adapter was verified with the pinned Babel parser using synthetic JavaScript/TypeScript fixtures, including a module with Unicode characters in its path. Gate R ran 66 Python tests (60 passed, 6 platform/environment skips) and the Node parser assertions passed; the separate QA suite passed 11/11. Evidence is recorded in repository `STATUS.md` under P48.

## P47 — compare exported callable contracts across snapshots

The existing `change-impact.json/.md` now show baseline/current callable API observations in `contract_changes`: added exports, exports no longer observed, and changed explicit signatures. Matching uses relative module path and exported name. Reported syntax fields include export kind, parameter shape/type flags, return annotation, async and generator; changes include evidence from both snapshots. The CLI prints the delta counts.

The current-snapshot `functional-contracts.json/.md` output uses the export-bearing module path; for direct ESM re-exports it also keeps a separate target-definition path and façade export path:line. Function bodies, actual default values, inferred types, side effects, and chained/wildcard/unresolved/ambiguous re-exports are omitted. A missing static contract is not a runtime compatibility verdict. The existing six/eight bundle file counts remain intact.

Verified with real Babel on a synthetic ESM-to-CommonJS API change: added/removed/changed exports, signature fields and path:line evidence; repeatable artifacts; source preservation; and no body/default-value leakage. P47 Gate R: 23/23 source pins, 65 Python tests (59 pass, 6 platform/environment skips), Node parser pass; QA 11/11 pass. See `STATUS.md` P47 for the evidence path and limits.

## P46 — compare module architecture across snapshots

`compare` and `bundle` now show how the resolved JS/TS module architecture differs between baseline and current snapshots. The existing `change-impact.json` and `.md` include added/removed source modules, module package-owner moves, added/removed resolved in-root dependencies, and added/removed/changed package boundaries or entrypoints. Dependency links include their kind and source path:line evidence. Console output summarizes the delta.

External or unresolved dependencies are excluded from the internal graph diff. A link is identified by its resolved source and target modules, so changing the import spelling while retaining the same resolved relationship is not counted as a topology change. The addition is backward-compatible at the file level: existing report names and default six / optional eight bundle outputs remain unchanged.

Verified with the pinned Babel parser on synthetic nested-package snapshots: module, package and dependency replacement; evidence lines; repeatable bytes; and unchanged input snapshots. Full P46 Gate R: 23/23 source pins, 64 Python tests (58 pass, 6 platform/environment skips), Node parser pass; separate QA 11/11 pass. Current evidence is recorded in repository `STATUS.md` P46.

## P45 — verified bundle scope and artifact paths

When `bundle` succeeds, its console summary now shows the analysis scope (indexed files, JS/TS files, dependency edges, and changed files) and an indexed list of every generated report path. This makes it clear which reports were written and what the run analyzed without changing the existing report schemas or filenames.

The default bundle still writes six reports. Adding `--with-diagram` writes eight, including `architecture.mmd` and `architecture.md`. Both paths passed genuine `@babel/parser@7.29.9` synthetic-project end-to-end acceptance with deterministic repeated output and unchanged input snapshots. The current Windows Gate R evidence and platform skips are recorded in the repository `STATUS.md` P45 entry.

## P44 — optional architecture diagram in one MVP bundle command (2026-10-27 KST)

```powershell
python -m rea_app bundle C:\baseline C:\current --output-dir C:\reports --with-diagram
```

The normal `bundle` command still produces its original six files. With `--with-diagram`, the same already generated current `source-map.json` also yields `architecture.mmd` and `architecture.md` (**8 total**) without another parser run. Graph nodes are resolved relative JS/TS module paths, links contain syntax-level import line evidence; no target code is executed or uploaded. A large/unrenderable graph is rejected before any output files are written, and users can simply omit `--with-diagram` to preserve the six-file workflow.

**Verification:** Reconstructed identical remote-candidate Git blobs of `rea_app/cli.py` (`b5c9e27c740a8f97335e61057a9276d71137dd96`) and `tests/test_bundle.py` (`484a874f967c770ad15e094ee2568342064596e4`) tested on Linux Python 3.13.5 in the isolated fixture: 22/22 focused tests PASS, including two new diagram-in-bundle cases and previous CLI contracts/diagram coverage. Mock analysis modules were used for bundle tests. Complete real Babel `@babel/parser@7.29.9` integration, Windows and full Gate R are **NOT YET VERIFIED**. No npm package was downloaded or substituted.

## P43 — visual architecture graph from an already saved source map

Run the new zero-dependency offline export after any `scan` or `bundle` that has produced `source-map.json`:

```powershell
python -m rea_app diagram C:\reports\source-map.json --output-dir C:\reports\diagram
```

It writes **`architecture.mmd`** and **`architecture.md`** (the latter embeds a Mermaid graph for GitHub preview). Nodes are relative JS/TS module paths; directed links show **resolved in-root imports and their original line numbers**. External dependencies, unresolved edges, project source bodies and absolute paths are never copied. It reads the saved bounded 10 MB report and **does not require the Babel parser or rerun source analysis**.

For test evidence, an isolated Python 3.13.5 synthetic report was fed into the real `diagram` CLI. New tests cover determinism, correct internal edges and evidence, empty graph, label escaping, invalid paths/lines, malformed or oversized input, and repeated real subprocess output. **6/6 new tests PASS** and **20/20 total locally executable tests PASS** against byte-exact candidate files in the standalone contracts/bundle fixture. This local environment's unrelated scanner/graph/impact imports were test stubs; **actual Babel parser 7.29.9 and full JS/TS `bundle` remain unavailable and unverified**. Rendered `.mmd` output is syntactically authored text, not a browser-rendered visual regression test.

## P42 — real Babel-backed bundle acceptance test

A new synthetic-project integration test runs the **actual** `python -m rea_app bundle` subprocess twice and checks six output files, resolved import path/line, changed dependency impact, affected package entrypoint, callable contract path/line, deterministic output and unchanged originals. It does not mock scanning or parsing.

From an authorized complete checkout after installing pinned `@babel/parser@7.29.9` with `npm ci`:
```powershell
cd tools/rea-app
python -m unittest discover -s tests -p "test_bundle_real_parser.py" -v
```

The test itself is Python-syntax-compiled in the isolated runner and matches its reviewed GitHub blob; **it has not been run successfully** because the current host does not have `@babel/parser@7.29.9` and DNS for npm endpoints is unavailable. This is a recorded integration gate, not a claimed MVP PASS. No mocked parser fallback, production deployment or paid CI has been introduced.

## P40 — One-command MVP report bundle

Run against two different, non-overlapping **authorized local source snapshots** after `npm ci` installs the pinned `@babel/parser@7.29.9` in `tools/rea-app`:

```powershell
python -m rea_app bundle C:\source-baseline C:\source-current --output-dir C:\rea-reports
```

The new `bundle` command writes six files in one output folder: `source-map.json/.md`, `change-impact.json/.md`, and `functional-contracts.json/.md`. It reuses the existing bounded read-only scan, parser-accurate graph, changed-file dependency impact, and evidence-only callable contracts. No original source is modified and no model/third-party service is invoked. Both selected source trees must not overlap; the output folder must be outside both. Parser or analysis failure before output generation creates **no bundle**. File writes are per-file atomic; the six-file group is **not** all-or-nothing if a disk error occurs during output.

Two designs considered: a single CLI orchestrator reusing the current analyzer (**implemented now**) and a deeper parser/impact cache refactor (deferred to after functioning MVP due greater regression surface). For a small fixture, the first design minimizes implementation risk; it does reparse the current snapshot when calculating change impact, so performance can be improved later.

**Evidence:** Exact source blob `8234acca278e6af9a15f73cf841ff7e4fedf6a80` and new `tests/test_bundle.py` blob `2db41dc5d0d2efb91e27ec8efe36a79e3383279b` match isolated Python 3.13.5 executed copies. Bundle orchestration tests **4/4 PASS** using mocked graph/scan/impact (real report file generation), plus earlier contracts unit and CLI tests **9/9 PASS**, total **13/13 PASS**. Full Babel-backed `bundle` across real JS/TS source and full Gate R remain **UNVERIFIED** because exact Babel runtime is not installed in this isolated environment.


## Functional contracts export (first blueprint-gap implementation)

From an existing locally generated source-map.json, export a separate versioned, evidence-only interface contract with no additional Node parser invocation:

```powershell
python -m rea_app contracts C:\reports\source-map.json --output-dir C:\reports\contracts
```

Writes `functional-contracts.json` and `functional-contracts.md`. Only explicitly observed JS/TS exported callable signatures, package association, and source path/line evidence are included. The output does not contain function bodies, source snippets, default values or invented behavior. Input schema must be rea-app-source-map/v1; report size is bounded at 10 MB. This is an **interface-only blueprint gap closure**, not independent implementation code or n8n reproduction. CLI compatibility and complete Babel suite remain subject to real full-checkout verification.

## P34 — verified local evidence capture (2026-10-27 KST)

In an authorized **clean** `REA_APP` checkout with reviewed `verify_gate_r.py` and installed `@babel/parser@7.29.9`, run `python run_gate_r_evidence.py` from this directory. This runner now pins the reviewed verifier's Git blob, requires clean scoped Git status, exact branch and commit metadata, and exact 15/15/Python/Node success lines including zero exit code. The local output directory contains `evidence.json`, `stdout.txt`, `stderr.txt`; no upload or installation occurs. Synthetic provenance regressions **11/11 PASS** on Linux/Python 3.13.5, but full analyzer/real Babel/Windows integration is still **UNVERIFIED**. See `P34_PROVENANCE_GATE.md`.

## P32 report-write safety

Reports now write a temporary UTF-8 file under the selected output folder, flush/fsync it and atomically replace each final file. Existing report symlink targets are not followed; on replacement failure the old report remains and the temporary file is removed. Four synthetic focused writer tests PASS on Linux. JSON and Markdown are not committed as one atomic pair, and live output parent-directory races and Windows-native behavior remain unverified. Gate R verifier now pins 15 source/test files. See P32_OUTPUT_WRITE_SAFETY.md.

## P31 — file-level reparse attributes now rejected (2026-10-27 KST)

The offline `verify_gate_r.py` validates every reviewed manifest path as a regular file via `lstat`, rejecting Windows reparse attributes before reading bytes. One new unittest simulates a flagged regular-file reparse point and a nonregular file: both unexpected acceptances occurred before repair; post-repair exact local verifier/self-test execution **9/9 PASS**. This is a synthetic attribute test on Linux, not actual Windows-junction verification. See `tools/rea-app/P31_FILE_REPARSE_GUARD.md`. The full Python analyzer and genuine Babel parser Gate R suites remain unrun.

## P30 — verifier now rejects linked source directories (2026-10-27 KST)

The offline `verify_gate_r.py` now checks that `rea_app/` and `tests/` are real directories (not symlinks or Windows reparse-point directories) **before** reading any reviewed manifest file. `tests/test_verify_gate_r.py` adds two directory-link subcases. A local byte-exact reconstruction executed focused Python **8/8 PASS**, with the new subcases reproducing failures on the old verifier. See `tools/rea-app/P30_PARENT_DIR_GUARD.md`. Full 14-file Python analysis, real Babel tests and actual Windows junction tests remain pending. This is not a release sign-off.

### P27 — installed parser version must match (2026-10-27 KST)

`python verify_gate_r.py` now checks the **locally installed** `@babel/parser` metadata through Node before calling the Node parser test. The installed version must be exactly `7.29.9`, matching the lockfile; a missing dependency or mismatched version fails. No dependencies are installed by the verifier.

The verifier's self-test expanded from 5 to **7 cases**, and its current source/test Git blobs match the committed files. Python self-tests **7/7 PASS** in an isolated Linux environment. Two Node package-metadata simulations confirmed acceptance/rejection (**2/2**); these are not a full analyzer integration or real Babel parser suite. The 14-file exact-source gate, actual Python analyzer tests and genuine Node parser test must still run in an authorized checkout for REA_APP Gate R sign-off.

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

Install Python 3.11+ and Node.js 20+, then install the locked parser package:

```powershell
npm ci --prefix rea_app --ignore-scripts --no-audit --no-fund
python -m rea_app scan C:\path\to\authorized\source --output-dir C:\path\to\reports
```

To install the Python package into the active environment instead of running
from a source checkout:

```powershell
python -m pip install .
$reaAppPackage = python -c "import pathlib, rea_app; print(pathlib.Path(rea_app.__file__).parent)"
npm ci --prefix $reaAppPackage --ignore-scripts --no-audit --no-fund
rea-app --version
rea-app scan C:\path\to\authorized\source --output-dir C:\path\to\reports
```

The Python wheel includes the parser adapter and the exact npm manifest and
lockfile. Install Babel beside the installed adapter with the shown `npm ci`
command; it installs `@babel/parser@7.29.9` without running dependency lifecycle
scripts. A source checkout uses the same command with `rea_app` as the prefix.

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
npm --prefix rea_app run test:parser
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
