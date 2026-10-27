"""Loopback-only local UI/API for the bounded synthetic CSV template."""
from __future__ import annotations

import base64
import binascii
import json
import re
import tempfile
import threading
import time
import uuid
from collections import OrderedDict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .engine import ApprovalRequired, Engine, PlanError, StepRetryExhausted, StepTimeout
from .dbvora_client import DbvoraClient
from .planner import plan_request, requires_write_approval, workflow_name
from .runlog import RunLogError, inspect_run

MAX_BODY_BYTES = 8192
MAX_UPLOAD_BYTES = 512 * 1024
MAX_UPLOAD_BODY_BYTES = ((MAX_UPLOAD_BYTES + 2) // 3) * 4 + 4096
MAX_UPLOADS_PER_SERVER = 10
MAX_REQUESTS_PER_MINUTE = 60
_RUN_ID = re.compile(r"^Gui[A-Fa-f0-9]{12}$")
_PREVIEW_ID = re.compile(r"^[a-f0-9]{32}$")
_ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
}


class RequestError(ValueError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("unsupported JSON constant")


def create_server(
    input_root: Path,
    state_path: Path,
    business_path: Path,
    *,
    port: int = 8765,
    dbvora_url: str | None = None,
):
    """Create a localhost-only server. Paths are fixed at startup, never supplied by HTTP."""
    root = Path(input_root).expanduser().resolve(strict=True)
    state = Path(state_path).expanduser().resolve(strict=False)
    business = Path(business_path).expanduser().resolve(strict=False)
    if not root.is_dir():
        raise PlanError("CSV input root must be an existing directory")
    if state == business:
        raise PlanError("runtime and business SQLite files must be distinct")
    if not state.parent.is_dir() or not business.parent.is_dir():
        raise PlanError("both database parent directories must already exist")
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise PlanError("port must be an integer from 0 to 65535")

    class Handler(BaseHTTPRequestHandler):
        server_version = "AXFlowLocalUI"
        sys_version = ""

        def log_message(self, fmt: str, *args: object) -> None:
            # Avoid logging paths, run IDs or user-entered task text.
            return

        def _origin_values(self) -> set[str]:
            port_number = self.server.server_port
            return {f"http://127.0.0.1:{port_number}", f"http://localhost:{port_number}"}

        def _check_local_request(self, *, require_origin: bool = False) -> bool:
            expected_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host", "").casefold() not in expected_hosts:
                self._send_json(403, {"error": "loopback host required"})
                return False
            origin = self.headers.get("Origin")
            if require_origin and origin is None:
                self._send_json(403, {"error": "same-origin request required"})
                return False
            if origin is not None and origin not in self._origin_values():
                self._send_json(403, {"error": "cross-origin request rejected"})
                return False
            if not self.server.allow_request(self.client_address[0]):
                self._send_json(429, {"error": "local request limit exceeded"})
                return False
            return True

        def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
            )
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status: int, value: object) -> None:
            body = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
            self._send_bytes(status, body, "application/json; charset=utf-8")

        def _read_json(self, *, max_bytes: int = MAX_BODY_BYTES) -> dict:
            if self.headers.get_content_type() != "application/json":
                raise RequestError(415, "Content-Type must be application/json")
            length = self.headers.get("Content-Length")
            if length is None or not length.isdigit():
                raise RequestError(411, "Content-Length is required")
            size = int(length)
            if size > max_bytes:
                raise RequestError(413, "request body exceeds configured limit")
            if size == 0:
                raise RequestError(400, "JSON request body is required")
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise RequestError(400, "incomplete request body")
            try:
                value = json.loads(
                    raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant
                )
            except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
                raise RequestError(400, "invalid JSON request") from exc
            if not isinstance(value, dict):
                raise RequestError(400, "JSON body must be an object")
            return value

        @staticmethod
        def _require_fields(value: dict, fields: set[str]) -> None:
            if set(value) != fields:
                raise RequestError(400, "request fields are missing or unsupported")

        def do_GET(self) -> None:
            if not self._check_local_request():
                return
            parsed = urlsplit(self.path)
            if parsed.path in _ASSETS:
                filename, content_type = _ASSETS[parsed.path]
                try:
                    body = files("axflow").joinpath("static", filename).read_bytes()
                except (OSError, ModuleNotFoundError, TypeError):
                    self._send_json(500, {"error": "local UI asset unavailable"})
                    return
                self._send_bytes(200, body, content_type)
                return
            if parsed.path == "/api/status":
                query = parse_qs(parsed.query, keep_blank_values=True)
                run_ids = query.get("run_id", [])
                if set(query) != {"run_id"} or len(run_ids) != 1 or not _RUN_ID.fullmatch(run_ids[0]):
                    self._send_json(400, {"error": "a run ID from this UI is required"})
                    return
                try:
                    self._send_json(200, inspect_run(state, run_ids[0]))
                except RunLogError as exc:
                    self._send_json(404, {"error": str(exc)})
                return
            if parsed.path == "/api/dbvora":
                self._send_json(200, self.server.dbvora_client.fetch_inventory())
                return
            self._send_json(404, {"error": "route not found"})

        def do_POST(self) -> None:
            if not self._check_local_request(require_origin=True):
                return
            route = urlsplit(self.path).path
            if route not in {"/api/upload", "/api/preview", "/api/run"}:
                self._send_json(404, {"error": "route not found"})
                return
            run_id = None

            def send_failure(status_code: int, exc: Exception) -> None:
                payload = {"error": str(exc)[:240], "error_type": type(exc).__name__}
                if run_id is not None:
                    payload["run_id"] = run_id
                    try:
                        payload["status"] = inspect_run(state, run_id)
                    except RunLogError:
                        pass
                self._send_json(status_code, payload)

            try:
                body = self._read_json(
                    max_bytes=MAX_UPLOAD_BODY_BYTES if route == "/api/upload" else MAX_BODY_BYTES
                )
                if route == "/api/upload":
                    self._require_fields(body, {"filename", "content_base64"})
                    filename = body["filename"]
                    encoded = body["content_base64"]
                    if (
                        not isinstance(filename, str)
                        or not filename
                        or len(filename) > 255
                        or "/" in filename
                        or "\\" in filename
                        or any(ord(character) < 32 for character in filename)
                        or filename in {".", ".."}
                        or not filename.casefold().endswith(".csv")
                    ):
                        raise RequestError(415, "only a plain CSV file is supported")
                    max_encoded = ((MAX_UPLOAD_BYTES + 2) // 3) * 4
                    if not isinstance(encoded, str) or len(encoded) > max_encoded:
                        raise RequestError(413, "uploaded CSV exceeds 512 KiB")
                    try:
                        data = base64.b64decode(encoded, validate=True)
                    except (binascii.Error, ValueError) as exc:
                        raise RequestError(400, "invalid CSV upload encoding") from exc
                    if not data:
                        raise RequestError(400, "CSV file is empty")
                    if len(data) > MAX_UPLOAD_BYTES:
                        raise RequestError(413, "uploaded CSV exceeds 512 KiB")
                    try:
                        text = data.decode("utf-8-sig")
                    except UnicodeDecodeError as exc:
                        raise RequestError(415, "CSV must be UTF-8 text") from exc
                    if "\x00" in text:
                        raise RequestError(415, "CSV must be UTF-8 text")
                    content = text.encode("utf-8")
                    csv_path = self.server.save_csv_upload(content)
                    self._send_json(201, {"csv_path": csv_path, "size_bytes": len(content)})
                    return
                if route == "/api/preview":
                    self._require_fields(body, {"task", "csv_path"})
                    plan = plan_request(body["task"], body["csv_path"])
                    preview_id = self.server.save_preview(
                        body["task"], body["csv_path"], "Gui" + uuid.uuid4().hex[:12]
                    )
                    self._send_json(200, {
                        "validated": True,
                        "workflow": workflow_name(plan),
                        "requires_approval": requires_write_approval(plan),
                        "planner": "bounded local rules",
                        "preview_id": preview_id,
                        "plan": plan,
                    })
                    return

                self._require_fields(body, {"task", "csv_path", "preview_id", "approve_writes"})
                if not isinstance(body["approve_writes"], bool):
                    raise RequestError(400, "approve_writes must be a boolean")
                plan = plan_request(body["task"], body["csv_path"])
                if requires_write_approval(plan) and body["approve_writes"] is not True:
                    raise RequestError(403, "explicit local synthetic-write approval is required")
                preview_id = body["preview_id"]
                if not isinstance(preview_id, str) or not _PREVIEW_ID.fullmatch(preview_id):
                    raise RequestError(409, "a recent matching preview is required before execution")
                run_id = self.server.get_preview_run_id(preview_id, body["task"], body["csv_path"])
                if run_id is None:
                    raise RequestError(409, "preview expired or no longer matches the request")
                result = Engine(state, business, input_root=root).execute(
                    plan, run_id, approve_writes=body["approve_writes"]
                )
                status = inspect_run(state, run_id)
                self._send_json(200, {"run_id": run_id, "result": result, "status": status})
            except RequestError as exc:
                send_failure(exc.status, exc)
            except PlanError as exc:
                send_failure(422, exc)
            except ApprovalRequired as exc:
                send_failure(403, exc)
            except (StepRetryExhausted, StepTimeout) as exc:
                send_failure(409, exc)
            except (OSError, RunLogError, ValueError) as exc:
                send_failure(422, exc)
            except Exception as exc:  # Return a bounded error instead of a traceback to the browser.
                send_failure(500, RuntimeError("local workflow failed: " + type(exc).__name__))

    class LocalHTTPServer(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True

        def __init__(self, address, handler):
            super().__init__(address, handler)
            self.dbvora_client = DbvoraClient(dbvora_url)
            self._recent_requests: deque[float] = deque()
            self._rate_lock = threading.Lock()
            self._preview_lock = threading.Lock()
            self._previews: OrderedDict[str, tuple[float, str, str, str]] = OrderedDict()
            self._upload_lock = threading.Lock()
            self._upload_dir: tempfile.TemporaryDirectory | None = None
            self._upload_count = 0

        def save_csv_upload(self, content: bytes) -> str:
            with self._upload_lock:
                if self._upload_count >= MAX_UPLOADS_PER_SERVER:
                    raise RequestError(429, "local CSV upload limit reached; restart the server")
                if self._upload_dir is None:
                    self._upload_dir = tempfile.TemporaryDirectory(prefix="axflow-upload-", dir=root)
                token = uuid.uuid4().hex
                path = Path(self._upload_dir.name) / f"{token}.csv"
                with path.open("xb") as output:
                    output.write(content)
                self._upload_count += 1
                return path.relative_to(root).as_posix()

        def server_close(self) -> None:
            try:
                super().server_close()
            finally:
                if self._upload_dir is not None:
                    self._upload_dir.cleanup()
                    self._upload_dir = None

        def allow_request(self, client: str) -> bool:
            if client not in {"127.0.0.1", "::1"}:
                return False
            now = time.monotonic()
            with self._rate_lock:
                while self._recent_requests and now - self._recent_requests[0] > 60:
                    self._recent_requests.popleft()
                if len(self._recent_requests) >= MAX_REQUESTS_PER_MINUTE:
                    return False
                self._recent_requests.append(now)
                return True

        def save_preview(self, task: str, csv_path: str, run_id: str) -> str:
            token = uuid.uuid4().hex
            now = time.monotonic()
            with self._preview_lock:
                while self._previews and next(iter(self._previews.values()))[0] <= now:
                    self._previews.popitem(last=False)
                self._previews[token] = (now + 600, task, csv_path, run_id)
                while len(self._previews) > 60:
                    self._previews.popitem(last=False)
            return token

        def get_preview_run_id(self, token: str, task: str, csv_path: str) -> str | None:
            now = time.monotonic()
            with self._preview_lock:
                entry = self._previews.get(token)
                if entry is None:
                    return None
                expires, saved_task, saved_path, run_id = entry
                if expires <= now:
                    del self._previews[token]
                    return None
                if saved_task != task or saved_path != csv_path:
                    return None
                return run_id

    return LocalHTTPServer(("127.0.0.1", port), Handler)
