"""Small Windows-friendly supervisor for the existing local HAE web app.

This module starts only localhost services. Business writes remain behind the
existing preview and explicit approval UI. It does not install dependencies,
elevate privileges, or keep running after the user closes this console.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import importlib
import os
from pathlib import Path
import sys
import threading
import time
from typing import Iterator
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener
import webbrowser


APP_NAME = "HAE"
DEFAULT_PORT = 8765
READY_TIMEOUT_SECONDS = 8.0


class LauncherError(RuntimeError):
    """A startup problem safe to show in the local console."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _configure_import_paths(root: Path) -> None:
    """Add known in-checkout source roots; never import arbitrary CWD modules."""
    candidates = [root / "apps" / "ax-flow"]
    for relative in (
        "packages/lightning-azent",
        "packages/lightning-azent/packages/lightning-azent",
    ):
        candidates.append(root / relative)
    for candidate in reversed(candidates):
        if candidate.is_dir() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))


def _choose_backend(root: Path, requested: str) -> tuple[str, str | None]:
    if requested not in {"auto", "axflow", "lightning-azent"}:
        raise LauncherError("Backend setting is invalid; choose auto, axflow, or lightning-azent.")
    if requested == "axflow":
        return "axflow", None

    _configure_import_paths(root)
    try:
        module = importlib.import_module("lightning_azent")
        executor_type = module.LAExecutor
        capabilities = executor_type.capabilities()
    except (ImportError, AttributeError, OSError):
        if requested == "lightning-azent":
            raise LauncherError(
                "Lightning Azent is not ready. Its local Python package is missing; "
                "HAE did not start in integrated mode."
            ) from None
        return "axflow", (
            "Lightning Azent is not installed in this checkout. HAE will start in "
            "its native local-engine mode; LA/SOVIA integration is unavailable."
        )
    except Exception:
        if requested == "lightning-azent":
            raise LauncherError("Lightning Azent capability check failed; integrated mode was not started.") from None
        return "axflow", (
            "Lightning Azent capability check failed. HAE will use its native local-engine mode; "
            "LA/SOVIA integration is unavailable."
        )

    if (not isinstance(capabilities, dict)
            or capabilities.get("api_version") != "azent.api.v0"
            or capabilities.get("scope") != "synthetic-local-only"
            or capabilities.get("legacy_ir_version") != "axflow.ir.v0"):
        if requested == "lightning-azent":
            raise LauncherError("Lightning Azent contract is incompatible; integrated mode was not started.")
        return "axflow", (
            "Lightning Azent contract is incompatible. HAE will use its native local-engine mode; "
            "LA/SOVIA integration is unavailable."
        )
    try:
        from .la_adapter import inspect_backend
        from .templates import build_template
        inspect_backend(build_template("csv_to_sqlite", csv_path="launcher-check.csv"))
    except Exception:
        if requested == "lightning-azent":
            raise LauncherError("Lightning Azent preflight failed; integrated mode was not started.") from None
        return "axflow", (
            "Lightning Azent preflight failed. HAE will use its native local-engine mode; "
            "LA/SOVIA integration is unavailable."
        )
    return "lightning-azent", None


def _data_root(configured: str | None = None) -> Path:
    raw = configured or os.environ.get("HAE_DATA_DIR")
    if raw:
        root = Path(raw).expanduser()
    else:
        app_data = os.environ.get("LOCALAPPDATA")
        if not app_data:
            raise LauncherError("Windows local app-data directory is unavailable; set HAE_DATA_DIR to a local folder.")
        root = Path(app_data) / APP_NAME
    try:
        root.mkdir(parents=True, exist_ok=True)
        if root.is_symlink() or not root.is_dir():
            raise LauncherError("HAE data location must be a normal local directory.")
        (root / "input").mkdir(exist_ok=True)
    except LauncherError:
        raise
    except OSError:
        raise LauncherError("HAE could not prepare its local app-data folders.") from None
    return root.resolve()


@contextmanager
def _instance_lock(lock_path: Path) -> Iterator[bool]:
    """Hold one OS byte/file lock for the lifetime of this launcher process."""
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        if lock_path.is_symlink():
            raise LauncherError("HAE instance lock path is unsafe.")
        handle = lock_path.open("a+b")
    except LauncherError:
        raise
    except OSError:
        raise LauncherError("HAE could not prepare its local instance lock.") from None

    locked = False
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                yield False
                return
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                yield False
                return
        locked = True
        yield True
    finally:
        if locked:
            try:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


def _url(port: int) -> str:
    return f"http://127.0.0.1:{port}/"


def _hae_is_ready(port: int, timeout: float = 0.5) -> bool:
    request = Request(_url(port), headers={"Accept": "text/html"})
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=timeout) as response:
            if response.status != 200 or "text/html" not in response.headers.get("Content-Type", ""):
                return False
            body = response.read(65537)
        return len(body) <= 65536 and b"HAE" in body
    except (OSError, URLError, ValueError):
        return False


def _wait_until_ready(port: int, timeout: float = READY_TIMEOUT_SECONDS) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _hae_is_ready(port, timeout=min(0.5, max(0.05, deadline - time.monotonic()))):
            return True
        time.sleep(0.1)
    return False


def _open_browser(port: int) -> bool:
    try:
        return bool(webbrowser.open(_url(port), new=2, autoraise=True))
    except (OSError, webbrowser.Error):
        return False


def _reuse_existing(port: int, *, no_browser: bool) -> None:
    print(f"HAE is already running at {_url(port)}.")
    if not no_browser and not _open_browser(port):
        print("The browser did not open automatically; use the local URL above.")


def _optional_sovia_root(root: Path) -> Path | None:
    configured = os.environ.get("HAE_SOVIA_ROOT")
    candidate = Path(configured).expanduser() if configured else root / "SOVIA"
    if candidate.is_dir() and (candidate / "sovia_la_observation_reconcile.py").is_file():
        return candidate.resolve()
    return None


def _configured_dbvora_url() -> str | None:
    return os.environ.get("HAE_DBVORA_URL") or None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the existing HAE local web application.")
    parser.add_argument("--port", type=int, default=os.environ.get("HAE_PORT", str(DEFAULT_PORT)))
    parser.add_argument("--data-dir", help="local app-data folder (defaults to %LOCALAPPDATA%\\HAE)")
    parser.add_argument("--backend", choices=("auto", "axflow", "lightning-azent"),
                        default=os.environ.get("HAE_ENGINE_BACKEND", "auto"))
    parser.add_argument("--no-browser", action="store_true", help="keep the local URL in this console without opening a browser")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be from 1 through 65535")
    return args


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        print("HAE needs Python 3.11 or newer. Install it, then run HAE-Start.cmd again.", file=sys.stderr)
        return 2

    args = _parse_args(argv)
    root = _repo_root()
    try:
        backend, warning = _choose_backend(root, args.backend)
        data_root = _data_root(args.data_dir)
    except LauncherError as exc:
        print(f"HAE did not start: {exc}", file=sys.stderr)
        return 2

    port = args.port
    lock_path = data_root / "launcher.lock"
    with _instance_lock(lock_path) as acquired:
        if not acquired:
            if _hae_is_ready(port):
                _reuse_existing(port, no_browser=args.no_browser)
                return 0
            print("Another HAE launcher is starting with this data folder. No second server was started.", file=sys.stderr)
            return 2

        if warning:
            print(f"HAE notice: {warning}", file=sys.stderr, flush=True)

        try:
            from .web import create_server
            server = create_server(
                data_root / "input", data_root / "state.sqlite", data_root / "business.sqlite",
                port=port, dbvora_url=_configured_dbvora_url(),
                engine_backend=backend, sovia_root=_optional_sovia_root(root),
            )
        except OSError:
            if _hae_is_ready(port):
                _reuse_existing(port, no_browser=args.no_browser)
                return 0
            print(f"HAE could not bind to 127.0.0.1:{port}; the port is already in use or unavailable.", file=sys.stderr)
            return 2
        except Exception:
            print("HAE could not prepare its local server. No business operation was run.", file=sys.stderr)
            return 2

        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2},
                                  name="hae-local-server", daemon=False)
        thread.start()
        try:
            if not _wait_until_ready(port):
                print("HAE server did not pass its local readiness check; stopping it.", file=sys.stderr)
                return 2
            print(f"HAE is ready ({backend}) at {_url(port)}.", flush=True)
            if not args.no_browser and not _open_browser(port):
                print("The browser did not open automatically; use the local URL above.", flush=True)
            print("Keep this window open while using HAE. Press Ctrl+C here to stop it.", flush=True)
            while thread.is_alive():
                thread.join(timeout=0.5)
            return 0
        except KeyboardInterrupt:
            print("Stopping HAE local server…", flush=True)
            return 0
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
