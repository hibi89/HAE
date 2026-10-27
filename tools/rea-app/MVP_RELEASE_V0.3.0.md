# REA_APP v0.3.0 — internal CLI MVP release record

**Status: INTERNAL_MVP_ACCEPTED (supported synthetic JS/TS scope).**
**Decision: 2026-10-28 KST.** This is a freeze/acceptance record, not a new source build, binary publication, external n8n study permission, Windows installer, or customer release.

## Version/source/provenance

- Repository: private `hibi89/HAE`, branch `REA_APP`.
- Reviewed functional code commit: `1ae3dac263a1a5c866434c8418fe7dbb1d3f1d48` (P53).
- Pre-freeze remote documentation HEAD: `3fd0ac452ea3255a24998f550aba3cbf9e6a263d`.
- Original frozen acceptance: `docs/TARGET_BLUEPRINT_V1.md` **A**. Only this REA_APP-supported scope is accepted, not the separate LA/HAE/DBVORA gates.
- Package: `rea_app-0.3.0-py3-none-any.whl`, reported built locally; 45,166 bytes; SHA-256 `006604be4da67fd3a9b4924c4de61b40dd58e21113c50b0f5f77e6f627a08465`. The wheel is **not in GitHub** and has not been published; its byte integrity is independently checkable only with the user's local artifact.

## User-visible MVP contract

Inputs: two independent, explicitly authorized **local** baseline/current source snapshots. JavaScript/TypeScript parser evidence is backed by pinned `@babel/parser@7.29.9` (Python >=3.11 and Node >=20). Python and unsupported languages are inventory-only and do not promise precise static call graphs.

Supported:
1. Read-only bounded file/package inventory and parser-backed JS/TS internal import/export links, entrypoints and file/line evidence.
2. Baseline/current module architecture and change-impact report with supported exported callable syntax/contract deltas.
3. Direct, uniquely resolved ESM named re-exports and explicit supported CommonJS callable assignments; unresolved/dynamic/wildcard/namespace/ambiguous cases are explicitly bounded.
4. One-shot `bundle` with **six** deterministic JSON/Markdown reports, optional `--with-diagram` for **eight** total files with Mermaid text/Markdown; `scan`, `compare`, `contracts`, `diagram` retained.
5. No customer-source execution, model-powered inference, secret extraction, or source-tree write-back.

Out of scope/deferred: P54 wildcard re-export expansion, graphical frontend, generated implementation/code transplant, full n8n parity, general JS/TS runtime behavior inference, clean Windows GUI installer, signed distribution, public package deployment, arbitrary-language reverse engineering.

## Recorded execution evidence (Codex Windows checkout; not re-run by chief in this freeze step)

- `python verify_gate_r.py`: reviewed source manifest **25/25**; Python **72 total, 66 passed, 6 skipped, 0 failed/errors**; exact Babel Node parser assertions **PASS**; exit **0**. Junction tests two executed/passed in permitted elevated environment. Other skips are environment/privilege and POSIX-specific; this is not a 72/72 PASS claim.
- QA: `python -m unittest discover -s qa -v` **11/11 PASS**.
- Evidence directory `E:\HAE\REA_APP_GATE_EVIDENCE\gate-r-vd4gdxam\evidence.json` (local to user's machine, **not** independently fetched here).
- Local package check: fresh Python 3.11.9 venv wheel install; locked `npm ci --ignore-scripts --no-audit --no-fund` **PASS**, exact `@babel/parser@7.29.9`; installed CLI `bundle --with-diagram` emitted **8 files**, reruns byte-identical, synthetic input checksums unchanged.
- Environment Windows 10 build 10.0.26200, Python 3.11.9. Other OS and real customer source have not been demonstrated.
- **Chief check this freeze:** GitHub branch, commit identity, P53 source diff, package metadata, CLI implementation, acceptance matrix and handoff inspected. Container `git ls-remote` cannot resolve github.com, so this session did **not** rerun complete private-source tests. No false independent PASS claimed.

## Reproducible developer smoke (illustrative; not executed in freeze step)

From the root of a clean, authorized checkout with exact Node parser already installed for the package:

```powershell
cd tools/rea-app
python verify_gate_r.py
python -m unittest discover -s qa -v
python -m rea_app bundle C:\synthetic-before C:\synthetic-after --output-dir C:\rea-reports --with-diagram
```

Input directories must be two real non-overlapping synthetic or explicitly permitted source snapshots. Reports must be outside both source roots. Do not run against real n8n source absent resolved permission and licensing review. `C:\synthetic-before` etc. are placeholders, not existing tested paths.

## Freeze/rollback and next consumer

- Code frozen at P53; no REA_APP source edits needed merely to announce internal MVP. This release record and handoff/status updates are documentation-only and preserve all existing test/code Git blobs.
- If a reproducible defect blocks LA research, create a narrowly scoped regression+repair; rerun Gate R at the new SHA before promoting it as the freeze baseline. Do not start optional P54 on current schedule.
- Next primary project: independent Lightning Azent engine, using public n8n product-behavior documentation and separately approved/licensed source evidence if later authorized. REA_APP is an internal read-only research aid and **never** a runtime dependency.
- No paid CI, secret/customer-data upload, public deployment, code copy from n8n or force push. Git commit history remains rollback mechanism.

**Release label means usable local internal MVP within the tested subset; it does not mean customer distribution, unrestricted use, or legal clearance for third-party source analysis.**
