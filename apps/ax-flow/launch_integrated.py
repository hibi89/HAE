"""Offline HAE+Lightning Azent Windows bundle launcher (Python 3.11+).

This file is copied beside hae-integrated.pyz. It does not import the checkout,
install packages, fetch GitHub branches, elevate permissions, or authorize writes.
Only 127.0.0.1 is exposed by the packaged server. A fresh data root receives
synthetic example rows; business SQLite writes require explicit UI approval.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
import socket
import sqlite3
from pathlib import Path
import sys
import tempfile
import threading
import time
from typing import Iterator
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
from contextlib import closing
import webbrowser


class LaunchError(RuntimeError):
    """Safe, bounded startup error."""


@contextmanager
def single_instance(path: Path) -> Iterator[None]:
    """OS-released nonblocking launch lock; no stale PID files."""
    if path.is_symlink():
        raise LaunchError("Launcher lock path is unsafe.")
    with path.open("a+b") as lock:
        if os.name == "nt":
            import msvcrt
            if lock.seek(0, os.SEEK_END) == 0:
                lock.write(b"\0")
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise LaunchError("An HAE launcher is already running for this data directory.") from exc
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise LaunchError("An HAE launcher is already running for this data directory.") from exc
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def data_directory(configured: str | None) -> Path:
    raw = configured or os.environ.get("HAE_DATA_DIR")
    if raw is None:
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            raise LaunchError("Set HAE_DATA_DIR or provide --data-dir (Windows LOCALAPPDATA unavailable).")
        raw = str(Path(base) / "HAE")
    root = Path(raw).expanduser()
    if root.is_symlink():
        raise LaunchError("HAE data directory cannot be a symlink.")
    root.mkdir(parents=True, exist_ok=True)
    if not root.is_dir():
        raise LaunchError("HAE data directory must be a directory.")
    root = root.resolve()
    input_path = root / "input"
    if input_path.is_symlink():
        raise LaunchError("HAE input directory cannot be a symlink.")
    input_path.mkdir(exist_ok=True)
    if not input_path.is_dir():
        raise LaunchError("HAE input directory is not available.")
    sample = input_path / "contacts.csv"
    if sample.is_symlink():
        raise LaunchError("Synthetic example CSV cannot be a symlink.")
    if not sample.exists():
        try:
            with sample.open("xb") as file:
                file.write(b"id,name\n11,SyntheticAlice\n12,SyntheticBob\n")
        except FileExistsError:
            pass
    return root


def wait_for_backend(origin: str, server_thread: threading.Thread, timeout: float = 12.0) -> None:
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not server_thread.is_alive():
            raise LaunchError("Integrated HAE exited before the local API became ready.")
        try:
            with opener.open(Request(origin + "/api/health", headers={"Accept": "application/json"}),
                             timeout=0.6) as response:
                body = json.load(response)
            if (body.get("ready") is True
                    and body.get("engine_backend", {}).get("name") == "Lightning Azent"):
                return
        except (OSError, ValueError, HTTPError, URLError):
            pass
        time.sleep(0.08)
    raise LaunchError("Integrated HAE did not become ready on the selected local port.")


def require_free_port(port: int) -> None:
    """Check whether loopback can bind; the server bind remains authoritative."""
    try:
        with socket.socket() as probe:
            # Match HTTPServer's SO_REUSEADDR semantics: an expired TIME_WAIT
            # connection must not falsely report an occupied listening port.
            # A live listener is still rejected; the actual server bind is final.
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(("127.0.0.1", port))
    except OSError as exc:
        raise LaunchError("Local port " + str(port) +
                          " is unavailable. Choose another --port or close the existing server.") from exc


def verify_bundle(package: Path) -> None:
    """Real, isolated HAE/LA HTTP acceptance; never touch user's HAE data."""
    import sys

    sys.path.insert(0, str(package))
    from axflow.web import create_server

    with tempfile.TemporaryDirectory(prefix="hae-la-offline-e2e-") as tmp:
        root = Path(tmp)
        inputs = root / "input"
        inputs.mkdir()
        (inputs / "contacts.csv").write_bytes(
            b"id,name\n11,SyntheticAlice\n12,SyntheticBob\n"
        )
        state, business = root / "state.db", root / "business.db"

        def request(origin: str, method: str, endpoint: str, payload: dict | None = None):
            data = json.dumps(payload).encode("utf-8") if payload is not None else None
            headers = {"Origin": origin, "Content-Type": "application/json"} if data else {}
            req = Request(origin + endpoint, data=data, headers=headers, method=method)
            opener = build_opener(ProxyHandler({}))
            try:
                with opener.open(req, timeout=8) as response:
                    return response.status, json.load(response)
            except HTTPError as exc:
                with exc:
                    return exc.code, json.load(exc)

        def require(status: int, body: dict, expected: int, description: str):
            if status != expected:
                raise LaunchError(description + " returned HTTP " + str(status) +
                                  " instead of " + str(expected))
            return body

        def start():
            service = create_server(
                inputs, state, business, port=0, engine_backend="lightning-azent",
            )
            worker = threading.Thread(
                target=service.serve_forever, kwargs={"poll_interval": 0.05},
                daemon=True,
            )
            worker.start()
            return service, worker, "http://127.0.0.1:" + str(service.server_port)

        def stop(service, worker):
            service.shutdown()
            worker.join(timeout=5)
            service.server_close()
            if worker.is_alive():
                raise LaunchError("offline verification server did not stop")

        steps = 0
        service, worker, origin = start()
        try:
            status, body = request(origin, "GET", "/api/health")
            require(status, body, 200, "backend health")
            if (body.get("ready") is not True or
                    body.get("engine_backend", {}).get("name") != "Lightning Azent"):
                raise LaunchError("packaged Lightning Azent backend is not ready")
            steps += 1

            args = {"task": "Import this CSV into local SQLite", "csv_path": "contacts.csv"}
            status, preview = request(origin, "POST", "/api/preview", args)
            require(status, preview, 200, "read-only preview")
            if not preview.get("requires_approval") or state.exists() or business.exists():
                raise LaunchError("preview unexpectedly modified SQLite or omitted consent gate")
            steps += 1

            denied = {**args, "preview_id": preview["preview_id"], "approve_writes": False}
            status, refusal = request(origin, "POST", "/api/run", denied)
            require(status, refusal, 403, "write consent refusal")
            if state.exists() or business.exists():
                raise LaunchError("unapproved write modified SQLite")
            steps += 1

            status, run = request(origin, "POST", "/api/run", {**denied, "approve_writes": True})
            require(status, run, 200, "approved SQLite execution")
            if (run.get("status", {}).get("status") != "completed"
                    or run.get("workflow_status") != "completed"
                    or run.get("result", {}).get("imported_rows") != 2):
                raise LaunchError("LA execution did not complete 2 synthetic rows")
            first_id = run["run_id"]
            steps += 1

            status, audit = request(origin, "GET", "/api/la-audit?run_id=" + first_id)
            require(status, audit, 200, "durable LA audit")
            if (audit.get("approval_count", 0) < 1
                    or audit.get("total_events", 0) < 1
                    or "SyntheticAlice" in json.dumps(audit)):
                raise LaunchError("LA audit evidence is incomplete or disclosed source data")
            steps += 1

            status, preview2 = request(origin, "POST", "/api/preview", args)
            require(status, preview2, 200, "second preview")
            status, run2 = request(origin, "POST", "/api/run", {
                **args, "preview_id": preview2["preview_id"], "approve_writes": True,
            })
            require(status, run2, 200, "second approved SQLite execution")
            if run2.get("run_id") == first_id or run2.get("result", {}).get("imported_rows") != 2:
                raise LaunchError("second execution failed or duplicated the run ID")
            with closing(sqlite3.connect(business)) as connection:
                count = connection.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0]
            if count != 4:
                raise LaunchError("two LA executions did not persist four distinct rows")
            steps += 1
        finally:
            stop(service, worker)

        service, worker, origin = start()
        try:
            status, saved = request(origin, "GET", "/api/status?run_id=" + first_id)
            require(status, saved, 200, "restored run status")
            status, restored = request(origin, "GET", "/api/la-audit?run_id=" + first_id)
            require(status, restored, 200, "restored LA audit")
            if (saved.get("status") != "completed" or
                    restored.get("total_events", 0) < audit.get("total_events", 0)):
                raise LaunchError("LA SQLite run and audit were not restored after restart")
            steps += 1
        finally:
            stop(service, worker)
    if steps != 7:
        raise LaunchError("bundled E2E verification was incomplete")
    print("HAE + LA offline bundled HTTP/SQLite acceptance: 7/7 PASS", flush=True)


def _console_safe_path(path: Path) -> str:
    """Print a local path safely even when Windows stdout uses cp1252/mbcs.

    Filesystem paths are not changed; only the diagnostic representation is
    escaped when it contains characters outside ASCII. No hidden fallback.
    """
    return str(path).encode("ascii", "backslashreplace").decode("ascii")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", help="private local data directory (default: LOCALAPPDATA/HAE)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="do not open the local UI automatically")
    parser.add_argument("--smoke", action="store_true",
                        help="start and verify bundled real LA backend, then cleanly stop")
    parser.add_argument("--verify", action="store_true",
                        help="run isolated 7-step real HTTP/SQLite E2E without touching user files")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        raise LaunchError("Python 3.11+ is required.")
    if not 1 <= args.port <= 65535:
        raise LaunchError("Port must be between 1 and 65535.")
    package = Path(__file__).resolve().with_name("hae-integrated.pyz")
    if not package.is_file() or package.is_symlink():
        raise LaunchError("Missing offline hae-integrated.pyz beside this launcher.")
    if args.smoke and args.verify:
        raise LaunchError("--smoke and --verify cannot be used together")
    if args.verify:
        verify_bundle(package)
        return 0
    root = data_directory(args.data_dir)
    with single_instance(root / ".hae-bundle.lock"):
        require_free_port(args.port)
        # Import both packages from the verified offline zipapp itself.
        # Run the server in THIS process: an abrupt console/parent termination
        # cannot leave a detached LA HTTP worker behind on Windows.
        sys.path.insert(0, str(package))
        from axflow.web import create_server

        try:
            server = create_server(
                root / "input", root / "runtime.db", root / "business.db",
                port=args.port, engine_backend="lightning-azent",
            )
        except OSError as exc:
            raise LaunchError("Could not bind HAE to the selected local port.") from exc
        server_thread = threading.Thread(
            target=server.serve_forever,
            kwargs={"poll_interval": 0.1},
            name="HAE-local-HTTP",
            daemon=True,
        )
        server_thread.start()
        try:
            url = "http://127.0.0.1:" + str(args.port) + "/"
            wait_for_backend(url.rstrip("/"), server_thread)
            print("HAE + Lightning Azent ready: " + url, flush=True)
            print("Synthetic CSV: " + _console_safe_path(root / "input" / "contacts.csv"), flush=True)
            if args.smoke:
                print("HAE offline Windows bundle readiness: PASS", flush=True)
                return 0
            if not args.no_browser:
                webbrowser.open(url)
            while server_thread.is_alive():
                server_thread.join(timeout=0.2)
            raise LaunchError("Integrated HAE local server exited unexpectedly.")
        except KeyboardInterrupt:
            return 0
        finally:
            server.shutdown()
            server_thread.join(timeout=5)
            server.server_close()

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (LaunchError, OSError) as exc:
        print("[HAE] " + str(exc), file=sys.stderr)
        raise SystemExit(1) from None
