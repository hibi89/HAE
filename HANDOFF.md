# HANDOFF — AX FLOW + REA_APP (bootstrap, 2026-10-27 KST)

1. **Goal/requirements/technology:** AX FLOW is a local-first natural-language automation product: file input + safe OAuth onboarding + plan/validate/run/recover with CLI and minimal web UI; optional DBVORA. REA_APP is a distinct app source analysis/reconstruction-assistance tool. Python 3.11+ proposed for initial static analysis and local executor; final technology remains subject to design/approval.
2. **Completed/change/decision:** GitHub private `hibi89/AX_FLOW` discovered empty; initial README created. Repo intended as private monorepo with separate source directories and branches. No features developed.
3. **Tests:** 0 executed / 0 passed / 0 failed; GitHub content/branches may be re-read to verify docs/bootstrap only. No Windows, browsers, OAuth, Gmail or production validation.
4. **State:** PLANNING/BOOTSTRAP; code NOT_STARTED. Next: initial REA_APP static analysis MVP design approval, then synthetic tests. AX FLOW runner follows.
5. **Errors/pivots:** Empty-repo 404 is expected, not a product bug. If remote read/write fails, record evidence, improve approach once, then provide local artifact and mark UNSYNCED instead of claiming success.
6. **Repository/branch/SHA/paths:** `hibi89/AX_FLOW` private, initial `main` SHA `8d528821097fcf6b983e52d9de804613cd8d8c3d`. Intended branches `main`, `develop`, `REA_APP`, `feature/axflow-mvp`; recheck actual HEADs after operations. Paths `apps/ax-flow/`, `tools/rea-app/`, `docs/`, AGENTS/REQUIREMENTS/STATUS/HANDOFF.
7. **Production/execution/environment:** No Vercel or deployed URL. Proposals: local CLI and localhost UI only; Python 3.11+ candidate, no runnable project yet.
8. **Originals/backups/credentials:** No code or data originals at bootstrap, aside from Git commits. No secrets, private source, customer DB or authentic external credentials supplied; no modifications to DBVORA/SMAX/SOVIA. Git history is current documentation rollback path.
9. **Next priorities/approvals:** Verify tree/branches/SHA → decide initial REA_APP analyzer architecture among documented alternatives → user's approval for substantive implementation → synthetic source fixture/parser/unit tests → AX FLOW proof-of-concept execution. Get approval for external data, OAuth registration, paid CI, security/visibility changes, production and customer usage. No n8n derivative commercialization assumption.
10. **KST checkpoint/verification scope/document baseline:** 2026-10-27 KST, repository metadata, initial README commit; **bootstrap final SHA and branch heads to verify live**. This document describes docs-only status, not an implementation result.

## New chat recovery
Read `HANDOFF.md` → `STATUS.md` → `AGENTS.md` → `REQUIREMENTS.md` → `docs/ARCHITECTURE.md` → `docs/NEXT_TASK.md` → actual source and tests. User `ㄱ` means next safe work unit. Do not repeat completed tasks.
