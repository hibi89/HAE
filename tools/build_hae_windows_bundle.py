"""Build a distributable offline Windows folder containing HAE + real LA.

This creates a self-contained Python-code bundle for synthetic-only local work:
  HAE-Windows/run-bundled.cmd
  HAE-Windows/launch_integrated.py
  HAE-Windows/hae-integrated.pyz

Python 3.11+ must be installed on the target PC; no Git, pip, LA checkout,
or internet access is needed at runtime. The target directory must not exist.

Example:
  python tools/build_hae_windows_bundle.py --la-package la-source/packages/lightning-azent --output-dir dist/HAE-Windows
"""
from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

from package_hae_integrated import build_integrated_zipapp


def build_windows_bundle(destination: Path, la_package: Path) -> Path:
    source = Path(__file__).resolve().parents[1] / "apps" / "ax-flow"
    destination = destination.expanduser().absolute()
    if not destination.parent.is_dir():
        raise FileNotFoundError("output parent directory does not exist")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("refusing to overwrite an existing Windows bundle")
    with tempfile.TemporaryDirectory(prefix="hae-bundle-", dir=destination.parent) as temporary:
        staging = Path(temporary) / "HAE-Windows"
        staging.mkdir()
        for filename in ("run-bundled.cmd", "launch_integrated.py",
                         "VERIFY-WINDOWS.cmd", "windows_offline_acceptance.py"):
            original = source / filename
            if original.is_symlink() or not original.is_file():
                raise FileNotFoundError("Windows launcher source missing or unsafe: " + filename)
            shutil.copyfile(original, staging / filename)
        (staging / "README.txt").write_text(
            "HAE + Lightning Azent synthetic local MVP\n"
            "Requires Python 3.11+; no Git/pip/network at runtime.\n"
            "Start: double-click run-bundled.cmd\n"
            "Check Windows/NTFS: double-click VERIFY-WINDOWS.cmd\n"
            "HTTP/SQLite test only: run-bundled.cmd --verify\n"
            "Only synthetic CSV data is supported.\n",
            encoding="utf-8",
        )
        build_integrated_zipapp(staging / "hae-integrated.pyz", la_package)
        if destination.exists() or destination.is_symlink():
            raise FileExistsError("refusing to overwrite an existing Windows bundle")
        staging.rename(destination)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--la-package", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = build_windows_bundle(args.output_dir, args.la_package)
    printable = str(result).encode("ascii", "backslashreplace").decode("ascii")
    print("HAE offline Windows bundle: " + printable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
