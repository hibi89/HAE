## P24 — scanner credential-file exclusion hardening (2026-10-27 KST)

- Chief confirmed `REA_APP` HEAD `6b7f78ee93eccbf7f7afb457dbfd37cc025713ca` before changes. Original scanner excluded `.env` and names containing "secret"/"credential" but could open `.npmrc`, `.pypirc`, `.netrc`, `.git-credentials`, shell history, and `.docker/config.json` in normal file inventory. It hashed accepted file bytes rather than returning them, but the read itself was unnecessary for a code graph.
- **P24 change:** code commit `019e022d1404cbdfc600a0d40cd0ef521c7d9191` adds a conservative allowlist-independent **denylist of known credential files** and prunes private authentication directories before traversal. Tests initially created `322bfd236ddd7fb654302280e71c8d6567f54c45`, then hardened at `67155aa73445ca4ed33dd97d02a0adbc1fa4aa86` to assert explicit fixed excluded names and mocked descriptor non-access. `tools/rea-app/tests/test_scan_sensitive_exclusions.py`.
- **Alternatives:** (A) leave inventory hashing alone (does not meet least-collection goal); (B) skip known authentication filenames and directories before file-open **selected** (small, no new dependency, preserves normal JS/TS index); (C) whitelist only JS/TS/project manifests, avoid reading inventory-only data (would change change-impact coverage and compatibility). No customer source or secrets were used.
- **Verification honesty:** 2/2 focused **reproduced logic** checks pass in local isolated Python against synthetic temp fixtures (file + directory exclusions). Actual imported GitHub `REA_APP` Python suite, new 2 regression tests, pinned Babel Node parser tests, Windows behavior and full source-integrity verification **NOT RUN on P24 code SHA** because source checkout is not available in runner. Prior Windows 15/15 on the older SHA is historical evidence only. Gate R remains **PARTIAL**.
- **Residual limits:** Unknown sensitive file names, Windows reparse/junction constraints and actively rewritten parent directories remain out of general security guarantees; use authorized stable snapshots and do not claim universal secret detection. REA_APP has no runtime n8n scan rights from this change, and Lightning Azent/HAE have no code changes.
- **Next:** authorized checkout `cd tools/rea-app`: `python -m unittest discover -s tests -v`; `python -m unittest discover -s tests -p test_scan_sensitive_exclusions.py -v`; `npm run test:parser`. Report exact branch SHA/OS/versions/test counts and skip separately. Then resume independently specified Lightning Azent contract gate within approved n8n IP restrictions.

# REA_APP — Gate R independent chief review and Lightning Azent handoff
Date: 2026-10-27 KST. **Status: PARTIAL / current SHA not independently regression-tested.**

## Intended role
REA_APP is a **read-only source evidence tool** for authorized source roots. It is not Lightning Azent's engine and must not be packaged as its runtime dependency. Stage order: REA_APP verified → permitted external behavior/documentation research → independent Lightning Azent contracts and engine → AX FLOW platform. The separate AX FLOW planning source is `docs/LIGHTNING_AZENT_MASTER_PLAN.md` on `feature/axflow-mvp`.

## Verified provenance vs unverified new work
- The exact prior `REA_APP@ff7997f2fd7a5c195bc06a63f2535ec469c24eae` remote 13-file analyzer source was reconstructed and hash-checked 13/13 against GitHub in a prior controlled Windows run, then Python **15/15 PASS** and `npm run test:parser` PASS with installed `@babel/parser@7.29.9`. As of `96d1ced45c37064642dda79d0559be9f076269ce`, only root handoff/status/task docs changed from that known test baseline.
- This work unit inspects actual `scanner.py`, `cli.py`, `impact.py`, `README.md`, test declarations at `REA_APP@96d1ced...`; fixes a file-open race: scanner code commit `f39bc31525a47c9a4621a24e0ed7f3b612c2c3f1`; two focused tests commit `f6b868d977020e976a8e7f4363696f8eb3e095ec`; README commit `08d6edcb23abe2104683b548aa2a0205c8dbc951`.
- A local isolated POSIX descriptor reproduction found a replaced inode and rejected a symlink via `O_NOFOLLOW` (**2/2 PASS**) without running the private source tree. **Current SHA Python tests and Node parser tests NOT RUN.** Do not infer that old 15/15 still passes after modifying `scanner.py`.
- P23 fix rejects changes between preliminary stat and descriptor open; not a race-free sandbox. Parent-directory path replacement, Windows junction restrictions, and actively mutating concurrent filesystems remain limitations. Scans should use authorized stable snapshots rather than untrusted attacker-writable live trees.

## Gap review against Gate R and target REA_APP blueprint

| Evidence / requirement | Observed implementation | Chief gate |
|---|---|---|
| Bounded read-only walk | `scanner.py` limits 5,000 files / 1 MB per file / 20 MB total; secret/symlink/known generated dirs excluded, final-component file race partly mitigated | Historical PASS; updated current HEAD unverified |
| JS/TS syntax parser and graph | Pinned `@babel/parser@7.29.9`, `babel_parser_adapter.cjs`, `graph.py` path/line-linked imports, local/static call relations, entrypoints | Historical exact-source PASS; not broad semantics |
| Change impact | `impact.py` uses both-snapshot resolved dependency edges and SHA-256 internally, reports relative paths and static reachable dependents | Historical PASS; runtime impact not inferred |
| Licensing/dependency | Babel MIT notice in `THIRD_PARTY_NOTICES.md`, no n8n code vendored | Recorded, must recheck before commercial distribution |
| No original source writes | Analyzer does not execute target code, writes reports outside the source; previous hash proof | Updated HEAD fresh fixture/source-integrity run pending |
| Windows reparse paths and concurrent races | Mocked reparse detection; real Windows junction creation denied previously | SKIP/UNVERIFIED, not a PASS |
| Complete JS/TS semantic data flow, arbitrary Python AST | Explicitly out of current support | Not required for Gate R v0.3, future separately scoped |

## Research source and IP / legal gate (important)
- Official n8n docs: `https://docs.n8n.io/` — public workflow-level information is available; no third-party repository was scanned this work unit.
- Official n8n Community/SUL explanation: `https://github.com/n8n-io/n8n-docs/blob/main/docs/n8n-community-license/README.md` — n8n is fair-code with commercial reuse restrictions, not permissively MIT/Apache licensed.
- Official n8n EULA effective **2026-08-27**: `https://n8n.io/legal/eula/`. The EULA contains restrictions concerning reverse engineering and use of covered software/services for competitive product development, competitive analysis and benchmarking. **Applicability depends on contractual relationship and applicable law; this is a legal-review flag, not a categorical determination about reading public documentation.** Before using REA_APP against n8n's repository or running n8n for Lightning Azent research, obtain review of scope, access rights, license revision and source-use permissions. Do not copy n8n implementation, prompts, node definitions or proprietary assets.
- Permissible/independent initial design while review pending: our own abstract requirements (versioned workflow IR, deterministic scheduling, bounded retries, scoped approvals, durable run receipts, explicit data provenance) and original synthetic fixture tests. Public documentation can inform feature lists subject to legal clearance; no n8n source code is needed to establish generic concepts.

## Next safe atomic execution
1. In an existing **authorized connected** checkout pinned to current `REA_APP` HEAD, `cd tools/rea-app`, `python -m unittest discover -s tests -v`, `npm ci` only if installation approved/necessary, `npm run test:parser`. Check dependency integrity and commands, report environment/PASS/FAIL/SKIP. Do not start paid CI or claim current green without evidence.
2. Specifically run `python -m unittest discover -s tests -p 'test_scan_open_races.py' -v` with secure source/fixture, verify Windows regular replacement; POSIX final-component symlink test naturally skips on Windows. Confirm source/input hashes unchanged for **normal** supported scanning.
3. Review concurrency hardening and ancestor reparse/race limitations for explicit accepted threat model; no guarantees of securely reading arbitrary hostile live dirs.
4. Only after verified Gate R and permissions, develop `docs/lightning-azent` original behavior contracts (graph/lineage, triggers, retry+receipts, mapping, connector approvals, credentials), and three original offline fixtures. Evidence distinguishes observed external behavior from design inference.
5. Keep Lightning Azent standalone engine implementation and AX FLOW platform expansion on their designated later gates.

## Source/rollback/deployment
GitHub private `hibi89/AX_FLOW`, `REA_APP` branch, paths `tools/rea-app/rea_app/scanner.py`, `tools/rea-app/tests/test_scan_open_races.py`, `tools/rea-app/README.md`. No customer files, credentials, downstream runtime changes or n8n source touched. Git revert after checking HEAD if regression found; no force push. No production/URL because CLI-only local analyzer. Report exact newest HEAD from subsequent commit check.
