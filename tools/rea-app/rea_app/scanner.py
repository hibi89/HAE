from __future__ import annotations

import os
import stat
import hashlib
from dataclasses import dataclass
from pathlib import Path


EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".next",
    ".cache",
    "dist",
    "build",
}
SOURCE_SUFFIXES = {".cjs", ".cts", ".js", ".jsx", ".mjs", ".mts", ".ts", ".tsx"}
MANIFEST_NAMES = {"package.json"}


class ScanError(Exception):
    """A bounded scan could not safely complete."""


@dataclass(frozen=True)
class ScanLimits:
    max_files: int = 5000
    max_file_bytes: int = 1_000_000
    max_total_bytes: int = 20_000_000


@dataclass
class ScannedFile:
    path: str
    size_bytes: int
    category: str
    content: str | None = None
    content_sha256: str = ""


@dataclass
class ScanResult:
    root: Path
    files: list[ScannedFile]
    skipped_files: list[dict[str, str | int]]
    limits: ScanLimits
    total_walked_bytes: int


def _is_secret_name(name: str) -> bool:
    lowered = name.casefold()
    if lowered == ".env" or lowered.startswith(".env.") or lowered.endswith(".env"):
        return True
    if any(fragment in lowered for fragment in ("secret", "credential", "private_key")):
        return True
    return lowered in {
        "id_rsa",
        "id_ed25519",
        "id_ecdsa",
        "authorized_keys",
        "known_hosts",
    } or Path(lowered).suffix in {".pem", ".key", ".p12", ".pfx", ".keystore"}


def _is_tsconfig(name: str) -> bool:
    lowered = name.casefold()
    return lowered == "tsconfig.json" or (
        lowered.startswith("tsconfig.") and lowered.endswith(".json")
    )


def _is_supported_source(path: Path) -> bool:
    return path.suffix.casefold() in SOURCE_SUFFIXES


def _inside_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_link_or_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    if os.name == "nt":
        try:
            attributes = getattr(path.lstat(), "st_file_attributes", 0)
        except OSError:
            return False
        return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return False


def walk_source(root_path: Path, limits: ScanLimits) -> ScanResult:
    try:
        root = root_path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise ScanError(f"source root cannot be resolved: {exc}") from exc
    if not root.is_dir():
        raise ScanError("source root must be an existing directory")
    if min(limits.max_files, limits.max_file_bytes, limits.max_total_bytes) <= 0:
        raise ScanError("all scan limits must be positive integers")

    scanned: list[ScannedFile] = []
    skipped: list[dict[str, str | int]] = []
    counted_files = 0
    total_bytes = 0

    def on_walk_error(error: OSError) -> None:
        raise ScanError(f"cannot inspect source directory: {error}") from error

    for current, directory_names, file_names in os.walk(root, topdown=True, followlinks=False, onerror=on_walk_error):
        current_path = Path(current)
        relative_directory = current_path.relative_to(root)
        kept_directories: list[str] = []
        for name in sorted(directory_names):
            candidate = current_path / name
            relative = (relative_directory / name).as_posix()
            if name.casefold() in EXCLUDED_DIRS:
                skipped.append({"path": relative, "reason": "excluded_directory"})
            elif _is_link_or_reparse_point(candidate):
                skipped.append({"path": relative, "reason": "symlink"})
            else:
                kept_directories.append(name)
        directory_names[:] = kept_directories

        for name in sorted(file_names):
            candidate = current_path / name
            relative = (relative_directory / name).as_posix()
            if _is_secret_name(name) or any(part.casefold() in {"secrets", "credentials"} for part in Path(relative).parts):
                skipped.append({"path": relative, "reason": "secret_name"})
                continue
            try:
                if _is_link_or_reparse_point(candidate):
                    skipped.append({"path": relative, "reason": "symlink"})
                    continue
                resolved = candidate.resolve(strict=True)
            except OSError as exc:
                skipped.append({"path": relative, "reason": f"unavailable:{type(exc).__name__}"})
                continue
            if not _inside_root(resolved, root):
                skipped.append({"path": relative, "reason": "outside_root"})
                continue
            try:
                file_stat = candidate.stat(follow_symlinks=False)
            except OSError as exc:
                skipped.append({"path": relative, "reason": f"unavailable:{type(exc).__name__}"})
                continue
            if not stat.S_ISREG(file_stat.st_mode):
                skipped.append({"path": relative, "reason": "not_regular_file"})
                continue

            counted_files += 1
            if counted_files > limits.max_files:
                raise ScanError(f"file-count limit exceeded ({limits.max_files})")
            total_bytes += file_stat.st_size
            if total_bytes > limits.max_total_bytes:
                raise ScanError(f"total-byte limit exceeded ({limits.max_total_bytes})")
            if file_stat.st_size > limits.max_file_bytes:
                skipped.append({"path": relative, "reason": "file_size_limit", "size_bytes": file_stat.st_size})
                continue

            should_read = _is_supported_source(candidate) or name.casefold() in MANIFEST_NAMES or _is_tsconfig(name)
            content: str | None = None
            try:
                # Reject a final-component symlink swap at open time on POSIX,
                # and reject a different file identity on supported platforms.
                # A pre-open resolve/stat check alone is subject to path races.
                flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(candidate, flags)
                with os.fdopen(descriptor, "rb") as handle:
                    opened_stat = os.fstat(handle.fileno())
                    if not stat.S_ISREG(opened_stat.st_mode):
                        skipped.append({"path": relative, "reason": "not_regular_file"})
                        continue
                    if (opened_stat.st_dev, opened_stat.st_ino) != (file_stat.st_dev, file_stat.st_ino):
                        skipped.append({"path": relative, "reason": "file_identity_changed"})
                        continue
                    # Hash every accepted file so compare mode can detect changes
                    # in inventory-only files without retaining their contents.
                    data = handle.read(limits.max_file_bytes + 1)
                if len(data) > limits.max_file_bytes or len(data) > file_stat.st_size:
                    skipped.append({"path": relative, "reason": "file_grew_past_limit"})
                    continue
                if b"\x00" in data:
                    skipped.append({"path": relative, "reason": "binary"})
                    continue
                if should_read:
                    try:
                        content = data.decode("utf-8-sig")
                    except UnicodeDecodeError:
                        skipped.append({"path": relative, "reason": "non_utf8_source"})
                        continue
            except OSError as exc:
                skipped.append({"path": relative, "reason": f"unreadable:{type(exc).__name__}"})
                continue

            if _is_supported_source(candidate):
                category = "javascript_typescript_source"
            elif name.casefold() in MANIFEST_NAMES:
                category = "package_manifest"
            elif _is_tsconfig(name):
                category = "typescript_config"
            else:
                category = "inventory_only"
            scanned.append(ScannedFile(
                relative,
                file_stat.st_size,
                category,
                content,
                hashlib.sha256(data).hexdigest(),
            ))

    scanned.sort(key=lambda item: item.path)
    skipped.sort(key=lambda item: (str(item["path"]), str(item["reason"])))
    return ScanResult(root, scanned, skipped, limits, total_bytes)

