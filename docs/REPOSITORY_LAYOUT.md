# Repository / branch organization

```
hibi89/AX_FLOW (private)
  README.md, AGENTS.md, REQUIREMENTS.md, STATUS.md, HANDOFF.md
  docs/
    ARCHITECTURE.md, DATA_ARCHITECTURE.md, ACCEPTANCE_MATRIX.md,
    MASTER_SCHEDULE.md, ROADMAP.md, NEXT_TASK.md, DECISIONS.md,
    REPOSITORY_LAYOUT.md, REA_APP_RESEARCH_POLICY.md
  tools/rea-app/        # internally usable source-analysis tool
  apps/ax-flow/        # local CLI, runner, planner, connectors, UI
  apps/ax-flow/adapters/dbvora/    # planned adapter only, not DBVORA source copy
  .gitignore
```

## Branches (work tracks, NOT permanent standalone products)
- `main`: stable source of truth, docs, verified release commits
- `develop`: reviewed integration/regression
- `REA_APP`: separate source analyzer, located under tools/rea-app
- `feature/axflow-mvp`: AX FLOW independent execution engine / AI / user UI
- `feature/dbvora-integration`: AX FLOW ↔ independently maintained DBVORA contract/adapter/tests

All initial branches may have identical HEAD until coding starts. Source identity is in directories, never just branch name. Avoid long-lived divergent copies; integrate reviewed PRs through develop and promote main only when tested.

DBVORA remains **hibi89/DBVORA**, active work branch **feature/p0-db-map**. Never merge DBVORA's Git history or source tree automatically. Fetch approved API/contract and pin its revision for integration tests; do not edit DBVORA without separate review/approval.

If REA_APP and AX FLOW diverge in licensing, maintainers, independent release, or security needs, split the private monorepo later by explicit migration plan; no new repo now.
