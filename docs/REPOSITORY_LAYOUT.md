# Monorepo layout and branch discipline

```
AX_FLOW/
  README.md, AGENTS.md, REQUIREMENTS.md, STATUS.md, HANDOFF.md
  docs/
    ARCHITECTURE.md, ROADMAP.md, REPOSITORY_LAYOUT.md,
    NEXT_TASK.md, DECISIONS.md, REA_APP_RESEARCH_POLICY.md
  apps/ax-flow/
    README.md           # customer-facing product; source to come
  tools/rea-app/
    README.md           # internal developer research tool; source to come
  .gitignore
```

`main`: stable base. `develop`: integrated changes reviewed and tested. `REA_APP`: REA_APP development branch (requested exact spelling). `feature/axflow-mvp`: first customer engine development branch. Keep product identity in paths, not merely in branch names: branches are versions of the WHOLE repository, merging does not permanently segregate product ownership.

Workflow: make a small change on work branch → run tests → update branch handoff → PR to develop → integration regression → PR to main if verified. Do not merge without tests or approval for high-risk changes.

Future split into two repositories remains possible if licensing, contributor access or release cycles diverge. No automatic mirroring between branches. DBVORA lives in its own repository and is only referenced through an adapter and interface contract.
