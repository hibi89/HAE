## Lightning Azent v0.1 native interface — staged, tests pending (2026-10-28 KST)

The independent package now exposes `azent.ir.v0` as a strictly versioned, bounded **native interface** mapped into the owner-authored `axflow.ir.v0` v0 core. `axflow.ir.v0` stays accepted for legacy HAE parity. Unknown IR versions/operations fail closed; native/legacy input dictionaries are not mutated. An independent `LAExecutor` provides `prepare`, `execute`, `schedule`, `status`, and `capabilities` with lazy database opening and explicit local write approval. No additional operation, connector, n8n code or OAuth support is implied.

Packaged console command: `lightning-azent` (Python >=3.11, zero runtime Python dependencies). Source CLI: `python -m lightning_azent --version`, `capabilities`, `validate`, `run`, `schedule`, `status`. Native sample `docs/lightning-azent/fixtures/native-conditional-route.json`; non-network synthetic input only. No release wheel built/published for LA.

From an authorized clean repository checkout at the exact `feature/lightning-azent` SHA:

```powershell
$env:PYTHONPATH="packages/lightning-azent"
python -m compileall -q packages/lightning-azent
python -m unittest discover -s packages/lightning-azent/tests -v
python -m lightning_azent --version
python -m lightning_azent capabilities
python -m lightning_azent validate docs/lightning-azent/fixtures/native-conditional-route.json
```

**All 21 new LA test definitions (7 initial + 5 CLI-denial + 9 native IR) are UNEXECUTED in this GitHub-only build session.** They include 3 real local synthetic workflows, rejection with no SQLite creation, native CLI run, version compatibility, and interval restart. Earlier REA_APP Windows Gate R results are for REA_APP only, not LA. Do not merge/switch HAE imports until the new tests and original HAE suite pass.

# Lightning Azent — isolated execution package (development stage)

Branch: `feature/lightning-azent`. Existing HAE app `apps/ax-flow/` and REA_APP branch are unchanged.

This directory stages the **owner-authored** HAE synthetic SQLite runner into a standalone import boundary. It is not derived from n8n code. Legacy `axflow.ir.v0` remains the sole accepted plan schema in this phase; `azent.ir.v0`, external connectors, secrets, hosted jobs and GUI are **not implemented**. Only synthetic/local data is supported.

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
