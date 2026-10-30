"""Read-only, offline HAE launcher preflight; not a runtime or customer certification."""
from __future__ import annotations

import json
from pathlib import Path
import stat
import sys
import zipfile

MAX_ARCHIVE_BYTES = 12 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 256
MAX_EXPANDED_BYTES = 40 * 1024 * 1024
REQUIRED_ENTRIES = frozenset({"__main__.py", "axflow/web.py", "lightning_azent/__init__.py"})


def _archive_ok(archive: Path) -> bool:
    """Validate zipapp structure and CRC without importing or extracting code."""
    if archive.is_symlink() or not archive.is_file():
        return False
    try:
        if not 0 < archive.stat().st_size <= MAX_ARCHIVE_BYTES:
            return False
        with zipfile.ZipFile(archive) as package:
            infos = package.infolist()
            if not 0 < len(infos) <= MAX_ARCHIVE_ENTRIES:
                return False
            names = set()
            expanded = 0
            for item in infos:
                name = item.filename
                mode = item.external_attr >> 16
                if (not name or "\\" in name or name.startswith("/")
                        or any(part in {".", ".."} for part in name.split("/"))
                        or ":" in name.split("/")[0]
                        or any(ord(c) < 32 or ord(c) == 127 for c in name)
                        or stat.S_ISLNK(mode) or name in names):
                    return False
                names.add(name)
                expanded += item.file_size
                if expanded > MAX_EXPANDED_BYTES:
                    return False
            if not REQUIRED_ENTRIES.issubset(names):
                return False
            return package.testzip() is None
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, EOFError):
        return False


def diagnose(root: Path, env: dict[str, str], selected: str) -> dict:
    """Never start an engine, read CSV/SQLite values, create files or reveal paths."""
    root = Path(root)
    data_value = env.get("HAE_DATA_DIR")
    local = env.get("LOCALAPPDATA")
    data = Path(data_value) if data_value else Path(local) / "HAE" if local else None
    unsafe_data = data is not None and data.is_symlink()
    bundle = root / "apps" / "ax-flow" / "hae-integrated.pyz"
    launcher = root / "apps" / "ax-flow" / "launch_integrated.py"
    installed = selected == "integrated"
    valid_bundle = (launcher.is_file() and not launcher.is_symlink()
                    and _archive_ok(bundle)) if installed else False
    if unsafe_data:
        code = "UNSAFE_DATA_ROOT"
    elif sys.version_info < (3, 11):
        code = "PYTHON_TOO_OLD"
    elif installed and not valid_bundle:
        code = "OFFLINE_BUNDLE_INVALID"
    elif installed:
        code = "OFFLINE_BUNDLE_STATIC_OK"
    elif selected == "preserved-legacy":
        code = "EXISTING_LEGACY_PRESERVED"
    else:
        code = "LEGACY_ONLY"
    return {
        "schema": "hae-offline-preflight-v1",
        "status": code,
        "selected_backend": selected,
        "archive_integrity_checked": bool(installed and valid_bundle),
        "files_or_databases_modified": False,
        "network_access_performed": False,
        "runtime_executed": False,
        "customer_ready": False,
        "release_gate": "HOLD",
        "next_action": ("RUN_ISOLATED_VERIFY" if code == "OFFLINE_BUNDLE_STATIC_OK"
                        else "REVIEW_LOCAL_CONFIGURATION"),
    }


def preflight_json(root: Path, env: dict[str, str], selected: str) -> tuple[int, str]:
    result = diagnose(root, env, selected)
    ok = result["status"] in {"OFFLINE_BUNDLE_STATIC_OK", "EXISTING_LEGACY_PRESERVED", "LEGACY_ONLY"}
    return (0 if ok else 2, json.dumps(result, sort_keys=True, ensure_ascii=False))
