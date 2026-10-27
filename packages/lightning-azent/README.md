## Lightning Azent v0.1 native interface — staged, tests pending (2026-10-28 KST)

The independent package now exposes `azent.ir.v0` as a strictly versioned, bounded **native interface** mapped into the owner-authored `axflow.ir.v0` v0 core. `axflow.ir.v0` stays accepted for legacy HAE parity. Unknown IR versions/operations fail closed; native/legacy input dictionaries are not mutated. An independent `LAExecutor` provides `prepare`, `execute`, `resume`, `schedule`, `status`, and `capabilities` with lazy database opening and explicit local write approval. No additional operation, connector, n8n code or OAuth support is implied.

A `resume` request requires an existing manual run ID and the exact original normalized plan; missing runs, changed plans, missing write approval and a deleted business ledger are rejected before the engine initializes SQLite. For source CLI recovery use `python -m lightning_azent resume plan.json --state state.sqlite --data business.sqlite --run-id ExistingID --synthetic` and `--approve-writes` when required. No externally executed workflow replay is supported. For CLI CSV execution, a missing `--input-root` is also rejected before creating SQLite files.

Packaged console command: `lightning-azent` (Python >=3.11, zero runtime Python dependencies). Source CLI: `python -m lightning_azent --version`, `capabilities`, `validate`, `run`, `resume`, `schedule`, `status`. Native sample `docs/lightning-azent/fixtures/native-conditional-route.json`; non-network synthetic input only. No release wheel built/published for LA.

Local interval schedules use a persisted per-schedule OS file lock (Unix `flock`, Windows `msvcrt.locking`) to prevent concurrent duplicate execution from two local scheduler processes. A second runner for the same schedule ID fails closed with `PlanError`. Lock files persist in the runtime SQLite directory and **must not be deleted while a scheduler is active**, because another process could then lock a different inode. Process exit releases the OS-held lock; the deterministic SQLite run ID and receipts permit resuming an interrupted tick. This is not a distributed/cloud lock or a guarantee for external side effects. Windows locking behavior still needs native testing.

From an authorized clean repository checkout at the exact `feature/lightning-azent` SHA:

```powershell
$env:PYTHONPATH="packages/lightning-azent"
python -m compileall -q packages/lightning-azent
python -m unittest discover -s packages/lightning-azent/tests -v
python -m lightning_azent --version
python -m lightning_azent capabilities
python -m lightning_azent validate docs/lightning-azent/fixtures/native-conditional-route.json
```

**All 29 LA test definitions (7 initial + 6 CLI-denial + 9 native IR + 6 recovery + 1 concurrency) are NOT RUN AS A FULL SUITE in this GitHub-only build session.** They include 3 real local synthetic workflows, rejection with no SQLite creation, native CLI run, version compatibility, and interval restart. Earlier REA_APP Windows Gate R results are for REA_APP only, not LA. Do not merge/switch HAE imports until the new tests and original HAE suite pass.

# Lightning Azent — isolated execution package (development stage)

Branch: `feature/lightning-azent`. Existing HAE app `apps/ax-flow/` and REA_APP branch are unchanged.

This directory stages the **owner-authored** HAE synthetic SQLite runner into a standalone import boundary. It is not derived from n8n code. Both `azent.ir.v0` and legacy `axflow.ir.v0` are now accepted through the versioned bounded adapter; external connectors, secrets, hosted jobs and GUI are **not implemented**. Only synthetic/local data is supported.

## Developer test commands (NOT EXECUTED by this GitHub connector session)

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
- These new-path tests are **UNVERIFIED** until run from a complete checkout; no CI workflow was added and no production URL exists.
- Original HAE code has not been replaced. No source-delete or compatibility facade change is allowed before parity is measured.
- See `docs/lightning-azent/RESEARCH_TO_CONTRACTS.md` for Gate N official-doc and licensing boundaries.
