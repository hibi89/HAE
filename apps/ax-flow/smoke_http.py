"""Direct, dependency-free real-LA HTTP acceptance smoke (synthetic CSV only).

Run from apps/ax-flow with real LA on PYTHONPATH:
    python smoke_http.py
Exercises HTTP preview, approval, two actual SQLite writes, durable LA audit,
explicit restart recovery, idempotence and server restart. Nonzero exit on failure.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from axflow.web import create_server

TASK = "Import this CSV into local SQLite"


def request(origin: str, method: str, path: str, body: dict | None = None):
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json", "Origin": origin} if payload else {}
    req = Request(origin + path, data=payload, headers=headers, method=method)
    try:
        with urlopen(req, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class LocalService:
    def __init__(self, root: Path, state: Path, business: Path):
        self.server = create_server(root, state, business, port=0, engine_backend="lightning-azent")
        self.origin = "http://127.0.0.1:" + str(self.server.server_port)
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def check(status: int, body: dict, expected: int):
    if status != expected:
        raise AssertionError(f"HTTP {expected} expected, got {status}: {body}")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="hae-la-http-acceptance-") as folder:
        temp = Path(folder)
        inputs = temp / "input"
        inputs.mkdir()
        (inputs / "contacts.csv").write_bytes(b"id,name\n11,SyntheticAlice\n12,SyntheticBob\n")
        state, business = temp / "runtime.db", temp / "business.db"
        service = LocalService(inputs, state, business)
        try:
            def preview(resume_id=None):
                body = {"task": TASK, "csv_path": "contacts.csv"}
                if resume_id:
                    body["resume_run_id"] = resume_id
                status, data = request(service.origin, "POST", "/api/preview", body)
                check(status, data, 200)
                assert data["engine_backend"]["name"] == "Lightning Azent", data
                return data

            def run(token: str, approved=True):
                return request(service.origin, "POST", "/api/run", {
                    "task": TASK, "csv_path": "contacts.csv",
                    "preview_id": token, "approve_writes": approved,
                })

            first_preview = preview()
            assert not state.exists() and not business.exists(), "preview modified SQLite"
            status, rejected = run(first_preview["preview_id"], approved=False)
            check(status, rejected, 403)
            assert not state.exists() and not business.exists(), "rejected write modified SQLite"
            status, first = run(first_preview["preview_id"])
            check(status, first, 200)
            assert first["status"]["status"] == "completed"
            assert first["result"]["imported_rows"] == 2
            assert first["backend"]["name"] == "Lightning Azent"
            first_id = first["run_id"]
            print("1/6 PASS: preview, consent, first real SQLite write", flush=True)

            audit_path = "/api/la-audit?run_id=" + first_id
            status, la_audit = request(service.origin, "GET", audit_path)
            check(status, la_audit, 200)
            assert la_audit["approval_count"] >= 1
            assert la_audit["total_events"] >= 2
            assert "SyntheticAlice" not in json.dumps(la_audit)
            status, state_response = request(service.origin, "GET", "/api/status?run_id=" + first_id)
            check(status, state_response, 200)
            assert state_response["status"] == "completed"
            print("2/6 PASS: durable redacted LA execution audit", flush=True)

            second_preview = preview()
            status, second = run(second_preview["preview_id"])
            check(status, second, 200)
            assert second["run_id"] != first_id and second["result"]["imported_rows"] == 2
            with sqlite3.connect(business) as con:
                assert con.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0] == 4
            print("3/6 PASS: second independent LA run on existing SQLite ledger", flush=True)

            # Simulated interrupted run after business receipts were committed:
            # recovery must explicitly reapprove the SAME run ID.
            with sqlite3.connect(state) as con:
                con.execute("UPDATE runs SET status='failed' WHERE run_id=?", (first_id,))
            resumed_preview = preview(first_id)
            assert resumed_preview["resumes_run_id"] == first_id
            status, _ = run(resumed_preview["preview_id"], approved=False)
            assert status == 403
            status, resumed = run(resumed_preview["preview_id"])
            check(status, resumed, 200)
            assert resumed["run_id"] == first_id
            assert resumed["status"]["status"] == "completed"
            with sqlite3.connect(business) as con:
                assert con.execute(
                    "SELECT COUNT(*) FROM csv_records WHERE run_id=?", (first_id,)
                ).fetchone()[0] == 2, "resume duplicated SQLite rows"
            print("4/6 PASS: explicit recovery with idempotent SQLite receipt", flush=True)

            status, completed_recovery = request(service.origin, "POST", "/api/preview", {
                "task": TASK, "csv_path": "contacts.csv", "resume_run_id": first_id,
            })
            check(status, completed_recovery, 409)
            print("5/6 PASS: completed-run recovery is safely rejected", flush=True)
        finally:
            service.close()

        service = LocalService(inputs, state, business)
        try:
            status, persisted = request(service.origin, "GET", "/api/status?run_id=" + first_id)
            check(status, persisted, 200)
            assert persisted["status"] == "completed"
            status, audit_after_restart = request(service.origin, "GET", audit_path)
            check(status, audit_after_restart, 200)
            assert audit_after_restart["run_id"] == first_id
            assert audit_after_restart["total_events"] >= la_audit["total_events"]
            print("6/6 PASS: restart recovery of run status and LA audit", flush=True)
        finally:
            service.close()
    print("HAE -> Lightning Azent -> SQLite HTTP MVP: 6/6 PASS", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"HAE-LA acceptance FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
