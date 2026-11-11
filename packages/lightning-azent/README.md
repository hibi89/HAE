## 2026-11-12 P17/P18 — unverified 85%-target development, 70% credited / RELEASE HOLD

A private Draft PR [#2](https://github.com/hibi89/HAE/pull/2) contains stronger completed HAE evidence and cached LA replay integrity guards, plus a deterministic unsigned synthetic `.pyz` builder/verifier and 21 new intended negative/E2E/package tests. **No full test run has executed on the new source SHA yet, so 85% is NOT claimed; credited progress remains 70%.** Existing `feature/lightning-azent` is unchanged. Run `python packages/lightning-azent/verify_local.py --expected-branch feature/la-p17-audit-evidence-20261112` on the exact clean feature checkout and verify PASS/FAIL/SKIP before changing readiness. New package: `build_portable_p18.py --output NEW_DIR/Lightning-Azent-0.1.0-synthetic-dev.pyz`, then `verify_portable_p18.py --archive ... --sha256-file ...`; it is **unsigned/non-release/no customer data**. [Exact gates and limitations](../../docs/lightning-azent/LA_P17_P18_EVIDENCE_AND_85_GATES_20261112.md).

---

## Lightning Azent v0.1 native interface — Windows-verified MVP slice (2026-10-28 KST)

### Owner acceleration & plan-only preflight (2026-10-28)

From the HAE repository root, run **one offline command** on the owner's Windows Python 3.11+ checkout:

```powershell
python packages/lightning-azent/verify_local.py
```

The verifier checks Git SHA/clean branch, in-memory Python syntax, the full LA suite, native run/resume, a conditional branch, CSV import/replay, two interval ticks, the original HAE regression, and an offline isolated wheel smoke when local build dependencies permit it. It records PASS/FAIL/SKIP and command logs as `verify_result.json` in a unique temporary directory beside the checkout. All write scenarios use synthetic temporary SQLite and CSV. `--skip-legacy` or `--skip-wheel` reduce coverage. At **`7df9aa1f419696ed04cf98ecc1fd99470db54cd9`**, Windows verification recorded **9 PASS / 0 FAIL / 1 SKIP**: 65/65 LA tests, 84/84 existing HAE tests, preflight, and end-to-end CLI flows for native run/resume, conditional routing, CSV import/replay, and interval execution passed. Offline wheel build/install was skipped because the Python `wheel` module is absent; no dependency was downloaded or installed.

The new **read-only plan preview** for HAE review is:

```powershell
$env:PYTHONPATH="packages/lightning-azent"
python -m lightning_azent preflight docs/lightning-azent/fixtures/csv-filter-import.json
```

`LAExecutor.preflight(plan)` exposes the same validated, redacted metadata: input version, trigger, ordered step IDs/operations, CSV-root and local-write-approval needs. It does **not** read actual CSV data, execute a workflow, issue OAuth consent, contact connectors, create SQLite, or replace a true execution dry-run. Whole-package verification remains a release gate.

The independent package exposes `azent.ir.v0` as a strictly versioned, bounded **native interface** mapped into the owner-authored `axflow.ir.v0` v0 core. The legacy IR stays accepted for parity. Unknown IR versions/operations fail closed; input dictionaries are not mutated. `LAExecutor` provides `prepare`, `execute`, `resume`, `schedule`, `status`, metadata-only `audit`, and `capabilities`. `capabilities` reports `azent.api.v0`, runtime SQLite schema v2, and a `metadata-only.v0` audit feed. Runtime and business ledgers are preflighted read-only before either is initialized; schema migrations run transactionally and reject corrupt, incompatible, incomplete, or newer schemas before changing them.

Each approved SQLite write run records a local approval receipt bound to the plan SHA-256 and exact write steps. Run, step, failure, completion, and replay metadata are persisted and can be read using `LAExecutor.audit(run_id)` or `python -m lightning_azent audit --state state.sqlite --run-id RunID`. Audit output omits workflow payloads and CSV rows. This local execution history is not an independent SOVIA audit or tamper-proof log.

A `resume` request requires an existing manual run ID and the exact original normalized plan; missing runs, changed plans, missing write approval and a deleted business ledger are rejected before the engine initializes SQLite. For source CLI recovery use `python -m lightning_azent resume plan.json --state state.sqlite --data business.sqlite --run-id ExistingID --synthetic` and `--approve-writes` when required. No externally executed workflow replay is supported. Existing manual-run recovery also performs read-only SQLite business-ledger schema and quick-integrity checks before initializing Engine. It additionally cross-checks completed local SQLite write/import step checkpoints against existing business row receipts; a removed row blocks manual resume instead of returning an unverified cached success. Incomplete step writes remain eligible for idempotent retry. It refuses to recreate missing, empty, incompatible or damaged local business ledgers. These checks do not independently validate every historic business record or external side effect. For CLI CSV execution, a missing `--input-root` is also rejected before creating SQLite files.

Packaged console command: `lightning-azent` (Python >=3.11, zero runtime Python dependencies). Source CLI: `python -m lightning_azent --version`, `capabilities`, `validate`, `preflight`, `run`, `resume`, `schedule`, `status`, `audit`, `verify`. Native sample `docs/lightning-azent/fixtures/native-conditional-route.json`; non-network synthetic input only. No release wheel built or published for LA.

Local interval schedules use a persisted per-schedule OS file lock (Unix `flock`, Windows `msvcrt.locking`) to prevent concurrent duplicate execution from two local scheduler processes. A second runner for the same schedule ID fails closed with `PlanError`. Lock files persist in the runtime SQLite directory and **must not be deleted while a scheduler is active**, because another process could then lock a different inode. The lock opener rejects hardlinked/non-regular files before any lock-file write; on supported Unix platforms it also uses nonblocking file opening to avoid stalling on a planted FIFO. The full LA suite has run on Windows Python 3.11.9, including process-crash lock release and multi-process replay. Local scheduling remains a foreground command, not a distributed lock or guarantee for external side effects.

From an authorized clean repository checkout at the exact `feature/lightning-azent` SHA:

```powershell
$env:PYTHONPATH="packages/lightning-azent"
python -m compileall -q packages/lightning-azent
python -m unittest discover -s packages/lightning-azent/tests -v
python -m lightning_azent --version
python -m lightning_azent capabilities
python -m lightning_azent validate docs/lightning-azent/fixtures/native-conditional-route.json
```

**Current suite: 65 test definitions.** At `7df9aa1f419696ed04cf98ecc1fd99470db54cd9`, the full Windows verifier passed all 65 LA tests and all 84 existing HAE tests; it also passed preflight and four synthetic CLI flows. The conditional scenario returns the accepted route, audits the unselected branch as skipped, and writes no business rows. CSV filter→SQLite import/replay leaves source unchanged and deleted-row resume is refused; interval execution commits two durable rows. A real child-process crash immediately after a committed business write resumes the same tick without a duplicate row. The aggregate was **9 PASS / 0 FAIL / 1 SKIP**; offline wheel smoke was skipped because `wheel` is unavailable. No direct HAE-to-LA consumer adapter is present: `apps/ax-flow/` continues to use `axflow`, and the LA package remains separately importable. This local MVP verification does not complete SOVIA/DBVORA/HAE product integration.

# Lightning Azent — isolated execution package (development stage)

Branch: `feature/lightning-azent`. Existing HAE app `apps/ax-flow/` and REA_APP branch are unchanged.

This directory stages the **owner-authored** HAE synthetic SQLite runner into a standalone import boundary. It is not derived from n8n code. Both `azent.ir.v0` and legacy `axflow.ir.v0` are now accepted through the versioned bounded adapter; external connectors, secrets, hosted jobs and GUI are **not implemented**. Only synthetic/local data is supported.

## Focused developer checks

From the repo root on a compatible Python 3.11+ checkout:

```powershell
$env:PYTHONPATH="packages/lightning-azent"
python -m unittest discover -s packages/lightning-azent/tests -v
python -m lightning_azent validate docs/lightning-azent/fixtures/conditional-route.json
```

The independent CLI exposes `validate`, `run`, `status`, and `schedule`. Execution requires `--synthetic`, explicit `--state` and `--data` paths. SQLite writes further require `--approve-writes`; omitted authorization must not create business databases. Existing directories for database parents and selected CSV input root are required.

The sample tests use only disposable temporary SQLite files and synthetic fixture CSV. Three offline behaviors to verify: CSV filter→approved import→replay; read-only conditional branch; durable interval ticks. Status must redact payloads; unknown network/shell operations must fail closed. Compare exact results with protected `apps/ax-flow/tests/` before any migration. No customer data.

## Scope / blockers

- Stage copies of the owner-controlled `engine.py`, `scheduler.py`, `runlog.py`, and `state_backup.py` preserve existing `axflow.ir.v0` behavior intentionally; independent CLI was added.
- These new-path tests were executed in the complete Windows checkout at the documented SHA; no CI workflow was added and no production URL exists.
- Original HAE code has not been replaced. No source-delete or compatibility facade change is allowed before parity is measured.
- See `docs/lightning-azent/RESEARCH_TO_CONTRACTS.md` for Gate N official-doc and licensing boundaries.
