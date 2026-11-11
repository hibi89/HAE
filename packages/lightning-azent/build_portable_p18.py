"""P18 deterministic, source-only LA zipapp candidate (unsigned, synthetic).

No install, network, model, customer files, build backend or old wheel mutation.
This developer utility refuses to overwrite a preexisting package or digest.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_STORED

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "lightning_azent"
NAME = "Lightning-Azent-0.1.0-synthetic-dev.pyz"
FORMAT = "la.zipapp.synthetic.p18.v1"
MODULES = (
    "__init__.py", "__main__.py", "contract.py", "engine.py",
    "hae_bridge.py", "runlog.py", "runtime.py", "scheduler.py",
    "state_backup.py",
)
HEADER = "from lightning_azent.__main__ import main\nraise SystemExit(main())\n"
MAX_SIZE = 2_097_152


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def package_bytes():
    if not SOURCE.is_dir():
        raise ValueError("LA_SOURCE_NOT_FOUND")
    names = {p.name for p in SOURCE.iterdir() if p.suffix == ".py"}
    if names != set(MODULES):
        raise ValueError("LA_SOURCE_INVENTORY_CHANGED")
    files = {"__main__.py": HEADER.encode("utf-8")}
    for name in MODULES:
        raw = (SOURCE / name).read_bytes()
        raw.decode("utf-8")
        files["lightning_azent/" + name] = raw.replace(b"\r\n", b"\n")
    manifest = {"schema_version": FORMAT, "release_approved": False,
                "synthetic_only": True,
                "files": {name: {"sha256": _sha(raw), "bytes": len(raw)}
                          for name, raw in sorted(files.items())}}
    files["LA_MANIFEST.json"] = (
        json.dumps(manifest, sort_keys=True, ensure_ascii=False,
                   separators=(",", ":")) + "\n").encode("utf-8")
    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_STORED, allowZip64=False) as z:
        for name, raw in sorted(files.items()):
            item = ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            item.create_system = 3
            item.external_attr = 0o100644 << 16
            item.compress_type = ZIP_STORED
            z.writestr(item, raw)
    result = output.getvalue()
    if len(result) > MAX_SIZE:
        raise ValueError("LA_PACKAGE_TOO_LARGE")
    return result


def publish_new(output):
    target = Path(output).absolute()
    if target.name != NAME or not target.parent.is_dir():
        raise ValueError("LA_OUTPUT_REQUIRES_FIXED_NAME_AND_EXISTING_PARENT")
    digest = target.with_name(target.name + ".sha256")
    if target.exists() or digest.exists() or target.is_symlink() or digest.is_symlink():
        raise ValueError("LA_OUTPUT_EXISTS")
    raw = package_bytes()
    checksum = (_sha(raw) + "  " + target.name + "\n").encode("ascii")
    # Use staged files and atomic hard-link publication: never silently
    # overwrite an existing owner's file even if another process creates it.
    published = []
    with tempfile.TemporaryDirectory(prefix=".la-p18-", dir=target.parent) as tmp:
        stages = [Path(tmp) / "package", Path(tmp) / "digest"]
        for stage, data in zip(stages, (raw, checksum)):
            stage.write_bytes(data)
        try:
            for stage, final in zip(stages, (target, digest)):
                os.link(stage, final)
                published.append(final)
        except Exception:
            for path in published:
                path.unlink(missing_ok=True)
            raise
    return {"status": "LA_SYNTHETIC_ZIPAPP_BUILT_UNSIGNED",
            "filename": target.name, "sha256": _sha(raw),
            "bytes": len(raw), "release_approved": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build isolated LA synthetic-only .pyz")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(publish_new(args.output), sort_keys=True))
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"status": "REJECTED", "error_code": "LA_BUILD_REFUSED"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
