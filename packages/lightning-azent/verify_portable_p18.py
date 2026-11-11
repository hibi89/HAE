"""Read-only verifier for standalone synthetic LA developer zipapp.

Checks exact inventory/bytes and optional detached digest. NOT code signing,
publisher authentication, real HAE acceptance or commercial approval.
"""
from __future__ import annotations
import argparse
import hashlib
import hmac
import io
import json
from pathlib import Path
import re
import stat
import sys
from zipfile import ZipFile, ZIP_STORED, BadZipFile

VERSION = "la.zipapp.synthetic.p18.v1"
MODULES = (
    "__init__.py", "__main__.py", "contract.py", "engine.py",
    "hae_bridge.py", "runlog.py", "runtime.py", "scheduler.py",
    "state_backup.py",
)
EXPECTED = {"__main__.py", "LA_MANIFEST.json"} | {
    "lightning_azent/" + name for name in MODULES
}
MAX_SIZE = 2_097_152
MAX_MEMBER = 1_048_576
SHA = re.compile(r"^[0-9a-f]{64}$")


class PortableError(ValueError):
    pass


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _unique(pairs):
    result = {}
    for name, item in pairs:
        if name in result:
            raise PortableError("MANIFEST_DUPLICATE_KEY")
        result[name] = item
    return result


def verify(path, digest_path=None):
    source = Path(path)
    if not source.is_file() or source.is_symlink() or source.stat().st_size > MAX_SIZE:
        raise PortableError("ZIPAPP_SOURCE_REFUSED")
    binary = source.read_bytes()
    if len(binary) > MAX_SIZE:
        raise PortableError("ZIPAPP_SIZE_REFUSED")
    actual_sha = sha(binary)
    if digest_path is not None:
        checksum = Path(digest_path)
        if (not checksum.is_file() or checksum.is_symlink() or
                checksum.stat().st_size > 256):
            raise PortableError("CHECKSUM_SOURCE_REFUSED")
        expected = (actual_sha + "  " + source.name + "\n").encode("ascii")
        if not hmac.compare_digest(checksum.read_bytes(), expected):
            raise PortableError("CHECKSUM_MISMATCH")
    try:
        with ZipFile(io.BytesIO(binary)) as archive:
            names = [item.filename for item in archive.infolist()]
            if len(names) != len(EXPECTED) or set(names) != EXPECTED:
                raise PortableError("ARCHIVE_INVENTORY_REFUSED")
            for item in archive.infolist():
                kind = (item.external_attr >> 16) & 0o170000
                if (item.is_dir() or item.flag_bits & 1 or
                        item.compress_type != ZIP_STORED or
                        item.file_size > MAX_MEMBER or
                        kind not in (0, stat.S_IFREG)):
                    raise PortableError("ARCHIVE_ENTRY_REFUSED")
            raw_manifest = archive.read("LA_MANIFEST.json")
            if len(raw_manifest) > 16384:
                raise PortableError("MANIFEST_TOO_LARGE")
            manifest = json.loads(raw_manifest.decode("utf-8"), object_pairs_hook=_unique)
            if (type(manifest) is not dict or
                    set(manifest) != {"schema_version", "release_approved",
                                      "synthetic_only", "files"} or
                    manifest["schema_version"] != VERSION or
                    manifest["release_approved"] is not False or
                    manifest["synthetic_only"] is not True or
                    type(manifest["files"]) is not dict or
                    set(manifest["files"]) != EXPECTED - {"LA_MANIFEST.json"}):
                raise PortableError("MANIFEST_SCHEMA_REFUSED")
            for name, record in manifest["files"].items():
                if (type(record) is not dict or
                        set(record) != {"sha256", "bytes"} or
                        type(record["sha256"]) is not str or
                        not SHA.fullmatch(record["sha256"]) or
                        type(record["bytes"]) is not int or
                        not 0 <= record["bytes"] <= MAX_MEMBER):
                    raise PortableError("MANIFEST_MEMBER_REFUSED")
                blob = archive.read(name)
                if (len(blob) != record["bytes"] or
                        not hmac.compare_digest(sha(blob), record["sha256"])):
                    raise PortableError("ZIPAPP_MEMBER_TAMPERED")
    except (BadZipFile, UnicodeError, json.JSONDecodeError, OSError, RuntimeError) as exc:
        raise PortableError("ZIPAPP_MALFORMED") from exc
    return {"status": "LA_SYNTHETIC_ZIPAPP_CONSISTENT_UNSIGNED",
            "sha256": actual_sha, "file_count": len(EXPECTED),
            "release_approved": False, "publisher_authenticated": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspect unsigned LA developer package")
    parser.add_argument("--archive", required=True)
    parser.add_argument("--sha256-file")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(verify(args.archive, args.sha256_file), sort_keys=True))
        return 0
    except (PortableError, OSError, ValueError):
        print(json.dumps({"status": "REJECTED", "error_code": "LA_ZIPAPP_VERIFY_REFUSED"}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
