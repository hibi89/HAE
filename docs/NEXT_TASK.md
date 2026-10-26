# Next task after bootstrap

## Preflight (do not repeat if already verified)
Check repo private and branch refs `main`, `develop`, `REA_APP`, `feature/axflow-mvp`, file contents and actual commit SHAs. Verify working Git identity before modifying code. Read HANDOFF/STATUS/AGENTS/REQUIREMENTS; compare with source.

## Next substantive work: REA_APP R1
1. Present two implementation options: Python stdlib AST + Tree-sitter incremental option versus Tree-sitter everywhere; compare zero-cost, install friction and language coverage.
2. Obtain approval before first substantive implementation / dependencies; no customer/proprietary inputs.
3. On `REA_APP` branch under `tools/rea-app/`, implement read-only source inventory of a synthetic toy repository; ignore .git, node_modules, binary and secret-looking files by default; enforce file count and size caps.
4. Extract Python AST imports and file/line references; design TypeScript/JS parser adapter behind optional dependency (not all languages in MVP).
5. Return stable machine-readable JSON graph and human report with `observed` vs `inferred` label. Do not execute inspected repository code.
6. Unit and CLI tests: safe path checks, symlink escape, huge files, unsafe inputs, deterministic result, no source mutation.
7. Verify actual tests; update STATUS/HANDOFF with SHA, failures and remaining; only integrate to develop once reviewed.

## Following AX FLOW F1
Independent design approval → synthetic local CLI runner with typed plans and SQLite durable execution journal; minimal schedule and idempotent step example; no Gmail/customer OAuth or external data at first.
