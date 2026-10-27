"""Build a dependency-free AX FLOW zipapp for local Windows smoke testing."""
from __future__ import annotations

import argparse
import shutil
import tempfile
import zipapp
from pathlib import Path


def build_zipapp(output: Path) -> Path:
    repository = Path(__file__).resolve().parents[1]
    package = repository / "apps" / "ax-flow" / "axflow"
    target = Path(output).expanduser().resolve(strict=False)
    if not package.is_dir():
        raise FileNotFoundError("AX FLOW package directory is missing")
    if not target.parent.is_dir():
        raise FileNotFoundError("output parent directory must already exist")
    if target.exists():
        raise FileExistsError("refusing to overwrite an existing package")
    if target == package or package in target.parents:
        raise ValueError("package output must stay outside the source package")
    if any(path.is_symlink() for path in package.rglob("*")):
        raise ValueError("refusing to package a source tree containing symlinks")

    with tempfile.TemporaryDirectory(prefix="axflow-package-", dir=target.parent) as temp:
        staging = Path(temp) / "axflow"
        shutil.copytree(
            package,
            staging,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        zipapp.create_archive(
            Path(temp),
            target=target,
            main="axflow.__main__:zipapp_main",
            interpreter=None,
            compressed=True,
        )
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new .pyz path; parent must exist")
    args = parser.parse_args()
    path = build_zipapp(args.output)
    print(f"AX FLOW zipapp built: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
