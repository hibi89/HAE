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

## Verification

From `tools/rea-app` run:

```powershell
python -m unittest discover -s tests -v
npm run test:parser
```

The synthetic tests cover deterministic output, ESM and CommonJS references,
alias/external resolution, cyclic imports, entry points, syntax errors, binary and
secret exclusions, symlink handling where the host allows symlink creation,
Windows reparse-attribute detection, empty repositories, scan caps, missing-parser
behavior, local value-flow evidence, ambiguous/reassigned binding exclusions,
exported callable signatures and source-tree integrity.

The Windows host used for the current verification denied junction creation
(`Access denied`). The reparse-attribute branch is unit-tested with synthetic
file attributes, but an actual filesystem junction fixture remains unverified.
