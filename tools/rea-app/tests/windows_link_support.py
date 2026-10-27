"""Small Windows junction helpers used by local-only regression fixtures."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


class JunctionUnavailable(RuntimeError):
    """The host cannot create a disposable directory junction."""


def create_directory_junction(link: Path, target: Path) -> None:
    if os.name != "nt":
        raise JunctionUnavailable("Windows junctions require Windows")
    if not target.is_dir() or link.exists():
        raise AssertionError("junction fixture requires an existing target and unused link path")
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if not powershell:
        raise JunctionUnavailable("PowerShell is unavailable")

    def literal(path: Path) -> str:
        return "'" + str(path).replace("'", "''") + "'"

    command = (
        "New-Item -ItemType Junction -Path " + literal(link)
        + " -Target " + literal(target) + " | Out-Null"
    )
    try:
        result = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise JunctionUnavailable(f"junction creation command unavailable: {type(exc).__name__}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise JunctionUnavailable(f"junction creation denied or unavailable: {detail[:240]}")
    item = link.lstat()
    if not getattr(item, "st_file_attributes", 0) & 0x400:
        raise AssertionError("PowerShell created a directory without the reparse-point attribute")


def remove_directory_junction(link: Path) -> None:
    """Remove only the junction itself, never the target directory."""
    if link.exists() or link.is_symlink():
        os.rmdir(link)
