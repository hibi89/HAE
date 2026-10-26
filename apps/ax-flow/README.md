# AX FLOW — customer automation product (unimplemented)

Primary flow: user request / template + attachment → validated AI plan → permission/credential wizard → dry run → approved execution → local schedule/recovery + evidence.

Engine must run without GUI, store durable state in local SQLite, and keep cloud OAuth and DBVORA integrations as optional adapters. Never give the model unrestricted shell/DB/email powers. Source implementation begins in `feature/axflow-mvp` after design approval.

Current status: docs only; no engine, API or frontend.
