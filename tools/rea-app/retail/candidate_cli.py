"""Single-command offline REA_APP delivery candidate with conservative rollback.

This is NOT a commercial release or a signature. Input reports remain read-only.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import stat
import sys
from pathlib import Path

import owner_delivery as owner
import package_delivery as package


def _file_identity(path: Path) -> tuple[int, int, bytes]:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise owner.DeliveryError("candidate file is no longer regular")
    return info.st_dev, info.st_ino, owner._regular_file(path)


def _rollback_owned(delivery: Path, archive: Path, snapshot: dict[str, tuple[int, int, bytes]],
                    zip_snapshot: tuple[int, int, bytes] | None) -> bool:
    """Remove only exact byte-and-inode matches. Never delete a replacement."""
    try:
        if zip_snapshot is not None and archive.exists():
            if _file_identity(archive) != zip_snapshot:
                return False
            archive.unlink()
        if delivery.is_dir() and not delivery.is_symlink():
            if {p.name for p in delivery.iterdir()} != set(snapshot):
                return False
            for name in snapshot:
                if _file_identity(delivery / name) != snapshot[name]:
                    return False
            for name in snapshot:
                (delivery / name).unlink()
            delivery.rmdir()
        return True
    except (OSError, owner.DeliveryError):
        return False


def prepare(bundle_path: Path, delivery_path: Path, archive_path: Path) -> str:
    source = owner._directory(bundle_path)
    delivery = owner._validate_output_location(source, delivery_path)
    archive = package._safe_new_zip(archive_path, source, delivery)
    if delivery.parent == source or source in delivery.parents:
        raise owner.DeliveryError("delivery cannot be under source")
    # All inputs must be valid before any final output is created.
    owner._review(owner._load(source)[0])
    owner.build(source, delivery)
    snapshot: dict[str, tuple[int, int, bytes]] = {}
    zip_snapshot = None
    try:
        snapshot = {name: _file_identity(delivery / name)
                    for name in (*owner.ARTIFACTS, "manifest.json")}
        owner.verify(source, delivery)
        package.pack(source, delivery, archive)
        zip_snapshot = _file_identity(archive)
        package.verify_zip(archive, source)
        owner.verify(source, delivery)
        if _file_identity(archive) != zip_snapshot:
            raise owner.DeliveryError("archive changed after final verification")
        return hashlib.sha256(zip_snapshot[2]).hexdigest()
    except (OSError, owner.DeliveryError):
        if not _rollback_owned(delivery, archive, snapshot, zip_snapshot):
            raise owner.DeliveryError("HOLD: partial outputs require manual review; none overwritten")
        raise


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="REA_APP offline candidate review; release remains HOLD")
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--delivery", type=Path, required=True)
    p.add_argument("--archive", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        digest = prepare(args.bundle, args.delivery, args.archive)
    except (owner.DeliveryError, OSError) as exc:
        print(f"HOLD: candidate review failed: {exc}", file=sys.stderr)
        return 2
    print(f"PASS: offline candidate verified; ZIP SHA256 {digest}; commercial RELEASE HOLD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
