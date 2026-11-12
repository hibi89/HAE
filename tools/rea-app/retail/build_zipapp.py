"""Deterministic offline Python zipapp candidate; NOT a signed customer release.

Packages only the optional retail companion. The original REA_APP parser,
customer sources, customer report bytes and any installed dependencies are excluded.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import os
import sys
import zipfile
from pathlib import Path

import owner_delivery as owner

PACKAGE_FILES = ("candidate_cli.py", "owner_delivery.py", "package_delivery.py")
ENTRYPOINT = b"from candidate_cli import main\nraise SystemExit(main())\n"
VERSION = "rea-app-offline-candidate-pyz/v1"
MAX_PACKAGE_BYTES = 1024 * 1024


def _archive_bytes(source: Path) -> bytes:
    source = owner._directory(source)
    members = {name: owner._regular_file(source / name) for name in PACKAGE_FILES}
    manifest = owner._encode({
        "schema": VERSION,
        "customer_release": "HOLD_PENDING_OWNER_ACCEPTANCE",
        "source_sha256": {name: owner._hash(members[name]) for name in PACKAGE_FILES},
    })
    members = {"__main__.py": ENTRYPOINT, **members, "MANIFEST.json": manifest}
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, data in members.items():
            meta = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            meta.compress_type = zipfile.ZIP_DEFLATED
            meta.external_attr = 0o100600 << 16
            z.writestr(meta, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    raw = mem.getvalue()
    if len(raw) > MAX_PACKAGE_BYTES:
        raise owner.DeliveryError("unexpected zipapp size")
    return raw


def build(source: Path, archive: Path) -> str:
    source = owner._directory(source)
    output = archive.expanduser().absolute()
    for parent in (output, *output.parents):
        if owner._is_link_or_reparse(parent):
            raise owner.DeliveryError("symbolic-link/reparse-point package path")
    if output.suffix.lower() != ".pyz" or not output.parent.is_dir():
        raise owner.DeliveryError("new .pyz file with existing parent required")
    if output.exists() or output == source or source in output.parents:
        raise owner.DeliveryError("refusing overwrite or package inside source directory")
    raw = _archive_bytes(source)
    # Exclusive creation is never an overwrite; do not touch original files.
    fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
        if owner._regular_file(output, MAX_PACKAGE_BYTES) != raw:
            raise owner.DeliveryError("new zipapp differs from in-memory build")
    except Exception:
        # On an unexpected I/O failure, preserve the location for manual review.
        # No unverified replacement is ever deleted by this builder.
        raise
    return hashlib.sha256(raw).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate local unsigned Python zipapp candidate (RELEASE HOLD)")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args(argv)
    try:
        digest = build(args.source, args.archive)
    except (owner.DeliveryError, OSError) as exc:
        print(f"HOLD: {exc}", file=sys.stderr)
        return 2
    print(f"PASS: offline pyz candidate sha256={digest}; commercial RELEASE HOLD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
