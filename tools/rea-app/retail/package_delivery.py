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
import zlib
from pathlib import Path

import owner_delivery as owner

ZIP_SCHEMA = "rea-app-offline-review-zip/v1"
ZIP_NAMES = ("README.txt", "manifest.json", "review.html", "review.json")
README = ("REA_APP 오프라인 고객 검수용 요약입니다.\n"
          "review.html은 네트워크 없이 열립니다.\n"
          "원본 코드/상세 경로/원본 보고서가 이 ZIP에 포함되지 않습니다.\n"
          "SHA-256 무결성은 별도 소유자 도구로 확인할 수 있으나 전자서명이나 판매 승인이 아닙니다.\n").encode("utf-8")
MAX_ARCHIVE = 32 * 1024 * 1024
COUNTS = frozenset((
    "files_indexed", "source_files", "dependency_edges", "syntax_errors", "skipped_paths",
    "added_files", "removed_files", "modified_files", "added_modules", "removed_modules",
    "added_internal_dependencies", "removed_internal_dependencies", "added_contracts",
    "removed_contracts", "changed_contracts", "exported_callable_contracts",
))
LIMITATIONS = [
    "No source paths, code, secrets, source reports or original files are included.",
    "Static JS/TS observations cannot prove runtime behavior or source reconstruction.",
    "The owner must review rights, real Windows packaging, and any customer data.",
]


def _canonical_unsigned_payload(receipt: object, review: object, data: dict[str, bytes]) -> None:
    """Check internal format; cannot authenticate an unsigned producer."""
    if not isinstance(receipt, dict) or set(receipt) != {
        "schema", "bundle_sha256", "delivery_sha256",
    }:
        raise owner.DeliveryError("unexpected receipt fields")
    if not isinstance(review, dict) or set(review) != {
        "schema", "assurance", "counts", "customer_release", "limitations",
    }:
        raise owner.DeliveryError("unexpected review fields")
    counts = review.get("counts")
    if not isinstance(counts, dict) or set(counts) != COUNTS or any(
        type(value) is not int or not 0 <= value <= owner.MAX_COUNT
        for value in counts.values()
    ):
        raise owner.DeliveryError("invalid review metrics")
    if (review.get("assurance") !=
            "summary_of_local_static_reports_only_not_runtime_or_legal_certification"
            or review.get("customer_release") != "HOLD_PENDING_OWNER_ACCEPTANCE"
            or review.get("limitations") != LIMITATIONS):
        raise owner.DeliveryError("review assurance or HOLD changed")
    if data["review.json"] != owner._encode(review):
        raise owner.DeliveryError("noncanonical review JSON")
    if data["review.html"] != owner._html(review):
        raise owner.DeliveryError("HTML differs from review JSON")
    if not isinstance(receipt.get("bundle_sha256"), dict) or set(receipt["bundle_sha256"]) != set(owner.FILES):
        raise owner.DeliveryError("source report digests absent")
    if any(not isinstance(value, str) or len(value) != 64
           or any(char not in "0123456789abcdef" for char in value)
           for value in receipt["bundle_sha256"].values()):
        raise owner.DeliveryError("invalid SHA-256 source digest")
    if not isinstance(receipt.get("delivery_sha256"), dict) or set(receipt["delivery_sha256"]) != set(owner.ARTIFACTS):
        raise owner.DeliveryError("output digests absent")




def _safe_new_zip(path: Path, source_dir: Path, delivery_dir: Path) -> Path:
    output = path.expanduser().absolute()
    for parent in (output, *output.parents):
        if owner._is_link_or_reparse(parent):
            raise owner.DeliveryError("symbolic-link/reparse-point archive path")
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
    # Rebind precisely the bytes that will enter the ZIP to the original
    # source reports. Earlier owner.verify may race with a later file swap.
    reports, fresh_digests = owner._load(source)
    expected_review = owner._review(reports)
    if (contents["review.json"] != owner._encode(expected_review)
            or contents["review.html"] != owner._html(expected_review)):
        raise owner.DeliveryError("delivery contents changed after owner verification")
    expected_manifest = owner._encode({
        "schema": owner.VERSION,
        "bundle_sha256": fresh_digests,
        "delivery_sha256": {
            name: owner._hash(contents[name]) for name in owner.ARTIFACTS
        },
    })
    if contents["manifest.json"] != expected_manifest:
        raise owner.DeliveryError("receipt changed after owner verification")
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
    except Exception as exc:
        # Never unlink after a failed write: another writer may have replaced
        # the just-created archive path. Preserve partial output for review.
        raise owner.DeliveryError("ZIP write failed; partial archive left untouched for manual review") from exc


def verify_zip(zip_path: Path, bundle_path: Path | None = None) -> None:
    path = zip_path.expanduser().absolute()
    for parent in (path, *path.parents):
        if owner._is_link_or_reparse(parent):
            raise owner.DeliveryError("symbolic-link/reparse-point archive path")
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
    except (zipfile.BadZipFile, RuntimeError, OSError, EOFError, zlib.error) as exc:
        raise owner.DeliveryError("invalid ZIP data") from exc
    # Reject hidden data outside ZIP members, alternate headers/metadata,
    # and ZIP comments. The delivery writer is intentionally deterministic.
    expected_stream = io.BytesIO()
    with zipfile.ZipFile(expected_stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as canonical:
        for name in ZIP_NAMES:
            meta = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            meta.compress_type = zipfile.ZIP_DEFLATED
            meta.external_attr = (0o100600 << 16)
            canonical.writestr(meta, data[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    if expected_stream.getvalue() != raw:
        raise owner.DeliveryError("noncanonical ZIP bytes: hidden payload or altered metadata")
    if data["README.txt"] != README:
        raise owner.DeliveryError("README modified")
    try:
        receipt = owner._parse_json_strict(data["manifest.json"])
        review = owner._parse_json_strict(data["review.json"])
    except (ValueError, UnicodeError) as exc:
        raise owner.DeliveryError("invalid review/receipt JSON") from exc
    if not isinstance(receipt, dict) or receipt.get("schema") != owner.VERSION:
        raise owner.DeliveryError("receipt schema invalid")
    if not isinstance(review, dict) or review.get("schema") != owner.VERSION:
        raise owner.DeliveryError("review schema invalid")
    _canonical_unsigned_payload(receipt, review, data)
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
