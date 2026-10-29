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
from pathlib import Path
import subprocess
import sys
import time
from typing import Iterator
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
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


def wait_for_backend(origin: str, child: subprocess.Popen, timeout: float = 12.0) -> None:
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if child.poll() is not None:
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


def stop(child: subprocess.Popen) -> None:
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=4)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=4)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", help="private local data directory (default: LOCALAPPDATA/HAE)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="do not open the local UI automatically")
    parser.add_argument("--smoke", action="store_true",
                        help="start and verify bundled real LA backend, then cleanly stop")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        raise LaunchError("Python 3.11+ is required.")
    if not 1 <= args.port <= 65535:
        raise LaunchError("Port must be between 1 and 65535.")
    package = Path(__file__).resolve().with_name("hae-integrated.pyz")
    if not package.is_file() or package.is_symlink():
        raise LaunchError("Missing offline hae-integrated.pyz beside this launcher.")
    root = data_directory(args.data_dir)
    with single_instance(root / ".hae-bundle.lock"):
        command = [
            sys.executable, str(package), "serve", "--synthetic",
            "--engine-backend", "lightning-azent",
            "--input-root", str(root / "input"),
            "--state", str(root / "runtime.db"), "--data", str(root / "business.db"),
            "--port", str(args.port),
        ]
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)  # prove the zipapp stands alone
        child = subprocess.Popen(command, cwd=root, env=env, stdin=subprocess.DEVNULL)
        try:
            url = "http://127.0.0.1:" + str(args.port) + "/"
            wait_for_backend(url.rstrip("/"), child)
            print("HAE + Lightning Azent ready: " + url, flush=True)
            print("Synthetic CSV: " + str(root / "input" / "contacts.csv"), flush=True)
            if args.smoke:
                print("HAE offline Windows bundle readiness: PASS", flush=True)
                return 0
            if not args.no_browser:
                webbrowser.open(url)
            returncode = child.wait()
            if returncode != 0:
                raise LaunchError("The integrated HAE server exited unsuccessfully.")
            return 0
        except KeyboardInterrupt:
            return 0
        finally:
            stop(child)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (LaunchError, OSError) as exc:
        print("[HAE] " + str(exc), file=sys.stderr)
        raise SystemExit(1) from None
