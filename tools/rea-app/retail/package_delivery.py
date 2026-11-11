"""Deterministic offline customer ZIP for independently verified REA_APP owner deliveries.

No analyzed source or raw report is ever packaged. Archive validation without
an original bundle proves local integrity only, not provenance or authenticity.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import stat
import sys
import zipfile
from pathlib import Path

import owner_delivery as owner

ZIP_SCHEMA = "rea-app-offline-review-zip/v1"
ZIP_NAMES = ("README.txt", "manifest.json", "review.html", "review.json")
README = ("REA_APP 오프라인 고객 검수용 요약입니다.\n"
          "review.html은 네트워크 없이 열립니다.\n"
          "원본 코드/상세 경로/원본 보고서가 이 ZIP에 포함되지 않습니다.\n"
          "SHA-256 무결성은 별도 소유자 도구로 확인할 수 있으나 전자서명이나 판매 승인이 아닙니다.\n").encode("utf-8")
MAX_ARCHIVE = 32 * 1024 * 1024


def _safe_new_zip(path: Path, source_dir: Path, delivery_dir: Path) -> Path:
    output = path.expanduser().absolute()
    for parent in (output, *output.parents):
        if parent.is_symlink():
            raise owner.DeliveryError("symbolic-link archive path")
    if output.suffix.lower() != ".zip":
        raise owner.DeliveryError("archive must have .zip extension")
    if output.exists() or not output.parent.is_dir():
        raise owner.DeliveryError("archive exists or parent unavailable")
    if output in (source_dir, delivery_dir) or source_dir in output.parents or delivery_dir in output.parents:
        raise owner.DeliveryError("archive path must remain outside report and delivery folders")
    return output


def pack(bundle_path: Path, delivery_path: Path, zip_path: Path) -> None:
    source = owner._directory(bundle_path)
    delivery = owner._directory(delivery_path)
    owner.verify(source, delivery)
    archive = _safe_new_zip(zip_path, source, delivery)
    contents = {
        "README.txt": README,
        "manifest.json": owner._regular_file(delivery / "manifest.json"),
        "review.html": owner._regular_file(delivery / "review.html"),
        "review.json": owner._regular_file(delivery / "review.json"),
    }
    # O_EXCL guards concurrent writers; no preexisting file is overwritten.
    fd = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                for name in ZIP_NAMES:
                    meta = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
                    meta.compress_type = zipfile.ZIP_DEFLATED
                    meta.external_attr = (0o100600 << 16)
                    z.writestr(meta, contents[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    except Exception:
        archive.unlink(missing_ok=True)
        raise


def verify_zip(zip_path: Path, bundle_path: Path | None = None) -> None:
    path = zip_path.expanduser().absolute()
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise owner.DeliveryError("symbolic-link archive path")
    raw = owner._regular_file(path, MAX_ARCHIVE)
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            entries = z.infolist()
            names = tuple(item.filename for item in entries)
            if names != ZIP_NAMES:
                raise owner.DeliveryError("unexpected, duplicate or reordered ZIP entries")
            for item in entries:
                if item.file_size > owner.MAX_JSON_BYTES or item.compress_size > MAX_ARCHIVE:
                    raise owner.DeliveryError("oversized ZIP entry")
                if item.flag_bits & 1:
                    raise owner.DeliveryError("encrypted ZIP entries unsupported")
                if item.is_dir() or stat.S_ISLNK(item.external_attr >> 16):
                    raise owner.DeliveryError("directory/symlink ZIP entries forbidden")
            data = {name: z.read(name) for name in ZIP_NAMES}
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise owner.DeliveryError("invalid ZIP data") from exc
    if data["README.txt"] != README:
        raise owner.DeliveryError("README modified")
    try:
        receipt = json.loads(data["manifest.json"])
        review = json.loads(data["review.json"])
    except (ValueError, UnicodeError) as exc:
        raise owner.DeliveryError("invalid review/receipt JSON") from exc
    if not isinstance(receipt, dict) or receipt.get("schema") != owner.VERSION:
        raise owner.DeliveryError("receipt schema invalid")
    if not isinstance(review, dict) or review.get("schema") != owner.VERSION:
        raise owner.DeliveryError("review schema invalid")
    if receipt.get("delivery_sha256") != {n: owner._hash(data[n]) for n in owner.ARTIFACTS}:
        raise owner.DeliveryError("ZIP delivery hash mismatch")
    if not isinstance(receipt.get("bundle_sha256"), dict) or set(receipt["bundle_sha256"]) != set(owner.FILES):
        raise owner.DeliveryError("source report digests absent")
    if bundle_path is not None:
        reports, digests = owner._load(owner._directory(bundle_path))
        expected = owner._review(reports)
        if receipt["bundle_sha256"] != digests:
            raise owner.DeliveryError("source report hash mismatch")
        if data["review.json"] != owner._encode(expected) or data["review.html"] != owner._html(expected):
            raise owner.DeliveryError("review differs from source-derived output")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="REA_APP offline customer ZIP; no external services")
    p.add_argument("mode", choices=("pack", "verify-zip"))
    p.add_argument("--bundle", type=Path)
    p.add_argument("--delivery", type=Path)
    p.add_argument("--archive", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.mode == "pack":
            if args.bundle is None or args.delivery is None:
                raise owner.DeliveryError("pack requires --bundle and --delivery")
            pack(args.bundle, args.delivery, args.archive)
        else:
            verify_zip(args.archive, args.bundle)
    except (owner.DeliveryError, OSError) as exc:
        print(f"HOLD: {exc}", file=sys.stderr)
        return 2
    print(f"PASS: offline review ZIP {args.mode}; commercial release remains HOLD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
