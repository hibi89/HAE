"""Build one offline HAE + Lightning Azent synthetic MVP Python zipapp.

The output contains both independently developed Python packages and HAE's
localhost UI assets. It needs Python 3.11+ but no Git, pip, or network at
runtime. External SOVIA/DBVORA remain optional local services.

Example (HAE repo root, with LA checked out separately):
    python tools/package_hae_integrated.py --la-package la-source/packages/lightning-azent --output dist/hae-integrated.pyz
Then:
    python dist/hae-integrated.pyz serve --synthetic --engine-backend lightning-azent --input-root ... --state ... --data ...
"""
from __future__ import annotations

import argparse
import os
import shutil
import tempfile
import zipapp
from pathlib import Path


def _safe_package(folder: Path, marker: str) -> Path:
    path = Path(folder).expanduser().absolute()
    if not path.is_dir() or not (path / marker).is_file():
        raise FileNotFoundError("required integrated package source is missing")
    if path.is_symlink() or any(part.is_symlink() for part in path.rglob("*")):
        raise ValueError("refusing to package symlinked sources")
    return path.resolve(strict=True)


def build_integrated_zipapp(output: Path, la_package: Path) -> Path:
    root = Path(__file__).resolve().parents[1]
    hae = _safe_package(root / "apps" / "ax-flow" / "axflow", "__init__.py")
    la = _safe_package(la_package, "lightning_azent/__init__.py")
    target = Path(output).expanduser().absolute()
    if target.suffix.lower() != ".pyz":
        raise ValueError("output must end in .pyz")
    if not target.parent.is_dir():
        raise FileNotFoundError("output parent directory must already exist")
    if target.exists() or target.is_symlink():
        raise FileExistsError("refusing to overwrite an existing artifact")
    if any(target == src or src in target.parents for src in (hae, la)):
        raise ValueError("output must be outside package sources")
    with tempfile.TemporaryDirectory(prefix="hae-integrated-", dir=target.parent) as temporary:
        stage = Path(temporary)
        shutil.copytree(hae, stage / "axflow", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(la / "lightning_azent", stage / "lightning_azent",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        # The archive is constructed in the private staging directory, and only
        # moved to its final path after a successful complete build.
        archive = stage.parent / (stage.name + ".pyz")
        try:
            zipapp.create_archive(stage, target=archive, main="axflow.__main__:zipapp_main",
                                  compressed=True)
            if target.exists() or target.is_symlink():
                raise FileExistsError("refusing to overwrite an existing artifact")
            # POSIX rename() overwrites an existing target. Create the final
            # hard link atomically instead; on Windows rename() refuses an
            # existing target. Archive and target live on the same filesystem.
            try:
                if os.name == "nt":
                    archive.rename(target)
                else:
                    os.link(archive, target)
            except FileExistsError as exc:
                raise FileExistsError("refusing to overwrite an existing artifact") from exc
        finally:
            archive.unlink(missing_ok=True)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--la-package", required=True, type=Path,
                        help="source directory containing lightning_azent/__init__.py")
    parser.add_argument("--output", required=True, type=Path, help="new .pyz path")
    args = parser.parse_args()
    print("HAE + Lightning Azent offline zipapp: " +
          str(build_integrated_zipapp(args.output, args.la_package)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
