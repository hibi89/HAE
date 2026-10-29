"""Select the shipped integrated HAE+LA launcher without losing legacy state.

The existing HAE-Start.cmd calls this with an already verified Python 3.11+.
No remote source, installer, credential or migration is performed here.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


class StartError(RuntimeError):
    """Fail closed on an incomplete or unsafe local launcher."""


def launch_command(root: Path, environment: dict[str, str], python: str) -> tuple[list[str], dict[str, str], str]:
    root = Path(root).resolve(strict=True)
    app = root / "apps" / "ax-flow"
    preference = environment.get("HAE_ENGINE_BACKEND", "auto").strip().lower()
    if preference not in {"auto", "axflow", "lightning-azent"}:
        raise StartError("HAE_ENGINE_BACKEND must be auto, axflow or lightning-azent")

    launch = app / "launch_integrated.py"
    package = app / "hae-integrated.pyz"
    present = launch.exists() or launch.is_symlink() or package.exists() or package.is_symlink()
    if preference != "axflow" and present:
        if (not launch.is_file() or launch.is_symlink()
                or not package.is_file() or package.is_symlink()):
            raise StartError("Integrated HAE bundle is incomplete or unsafe; no fallback was used")

    env = dict(environment)
    port = env.get("HAE_PORT")
    if port is not None:
        if not port.isascii() or not port.isdecimal() or not 1 <= int(port) <= 65535:
            raise StartError("HAE_PORT must be an integer from 1 through 65535")
    args = ["--no-browser"] if env.get("HAE_NO_BROWSER") == "1" else []
    if port is not None:
        args.extend(["--port", port])

    configured_data = env.get("HAE_DATA_DIR")
    local = env.get("LOCALAPPDATA")
    data = Path(configured_data or str(Path(local) / "HAE")) if (configured_data or local) else None
    legacy_present = (data is not None and
                      any((data / filename).exists() for filename in ("state.sqlite", "business.sqlite")))
    integrated_present = (data is not None and
                          any((data / filename).exists() for filename in ("runtime.db", "business.db")))
    keep_legacy = preference == "auto" and legacy_present and not integrated_present
    if preference != "axflow" and present and not keep_legacy:
        return [python, str(launch), *args], env, "integrated"

    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(app) + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
    # Explicit LA fallback is still fail-closed in desktop_launcher if no LA
    # source package is installed; 'auto' keeps existing native behavior.
    return [python, "-m", "axflow.desktop_launcher", *args], env, (
        "preserved-legacy" if keep_legacy else "legacy"
    )


def main() -> int:
    try:
        root = Path(__file__).resolve().parents[2]
        cmd, env, selected = launch_command(root, os.environ, sys.executable)
        print("HAE launcher: " + selected, flush=True)
        if selected == "preserved-legacy":
            print("Existing HAE SQLite data detected; no automatic engine or data migration.", flush=True)
        return subprocess.call(cmd, env=env, cwd=str(root))
    except (StartError, OSError, ValueError) as exc:
        print("HAE did not start: " + str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
