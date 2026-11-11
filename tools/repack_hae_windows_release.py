"""Assemble the checked-in HAE+LA zipapp into a native Windows test bundle.

Unlike build_hae_windows_bundle.py this does not require a separate LA checkout.
It copies the already-built and previously E2E-tested hae-integrated.pyz into
a NEW portable folder with both launchers and the native Windows acceptance.

Example:
    python tools/repack_hae_windows_release.py --output-dir dist/HAE-Windows
    dist\\HAE-Windows\\VERIFY-WINDOWS.cmd
"""
from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path


FILES = (
    "hae-integrated.pyz",
    "run-bundled.cmd",
    "launch_integrated.py",
    "VERIFY-WINDOWS.cmd",
    "windows_offline_acceptance.py",
)
README = (
    "HAE + Lightning Azent synthetic local MVP\n"
    "Requires Python 3.11+; no Git, pip or separate LA required at runtime.\n"
    "Start: double-click run-bundled.cmd\n"
    "Native Windows release check: double-click VERIFY-WINDOWS.cmd\n"
    "Synthetic HTTP/SQLite check only: run-bundled.cmd --verify\n"
    "Only synthetic CSV data is supported.\n"
)


def repack(output: Path) -> Path:
    source = Path(__file__).resolve().parents[1] / "apps" / "ax-flow"
    target = Path(output).expanduser().absolute()
    if not target.parent.is_dir():
        raise FileNotFoundError("output parent must already exist")
    if target.exists() or target.is_symlink():
        raise FileExistsError("refusing to overwrite an existing release folder")
    for filename in FILES:
        original = source / filename
        if original.is_symlink() or not original.is_file():
            raise FileNotFoundError("missing/unsafe release component: " + filename)
    with tempfile.TemporaryDirectory(prefix="hae-repack-", dir=target.parent) as temporary:
        stage = Path(temporary) / "HAE-Windows"
        stage.mkdir()
        for filename in FILES:
            shutil.copyfile(source / filename, stage / filename)
        (stage / "README.txt").write_text(README, encoding="utf-8")
        if target.exists() or target.is_symlink():
            raise FileExistsError("refusing to overwrite an existing release folder")
        stage.rename(target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = repack(args.output_dir)
    printable = str(result).encode("ascii", "backslashreplace").decode("ascii")
    print("Portable HAE Windows bundle: " + printable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
