"""Explicit, synthetic-only local metadata registry CLI. No customer DB support."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .asset_registry import (
    AssetRegistryError, initialize_synthetic_registry, read_synthetic_registry,
    register_synthetic_asset, verify_registered_synthetic_asset,
)
from .dbvora_client import DbvoraClient


class _SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise AssetRegistryError("invalid synthetic registry arguments")


def main(argv: list[str] | None = None) -> int:
    try:
        p = _SafeParser(prog="HAE synthetic metadata registry")
        p.add_argument("command", choices=("init", "list", "register", "verify"))
        p.add_argument("--registry", type=Path, required=True)
        p.add_argument("--source", type=Path)
        p.add_argument("--dbvora-url")
        p.add_argument("--ack-new-file", action="store_true")
        p.add_argument("--ack-owner", action="store_true")
        p.add_argument("--synthetic", action="store_true")
        a = p.parse_args(argv)
        if not a.synthetic:
            raise AssetRegistryError("synthetic-only registry")
        if a.command == "init":
            if a.source is not None or a.dbvora_url is not None or a.ack_owner:
                raise AssetRegistryError("unsupported init flags")
            result = initialize_synthetic_registry(
                a.registry, synthetic=True, acknowledge_new_file=a.ack_new_file)
        elif a.command == "list":
            if a.source is not None or a.dbvora_url is not None or a.ack_owner or a.ack_new_file:
                raise AssetRegistryError("unsupported list flags")
            result = read_synthetic_registry(a.registry, synthetic=True)
        elif a.command == "register":
            if (a.source is None or a.dbvora_url is None or a.ack_new_file
                    or not a.ack_owner):
                raise AssetRegistryError("explicit register flags required")
            result = register_synthetic_asset(
                a.registry, a.source, DbvoraClient(a.dbvora_url),
                synthetic=True, acknowledge_owner=True,
            )
        else:
            if a.source is None or a.dbvora_url is None or a.ack_owner or a.ack_new_file:
                raise AssetRegistryError("explicit verification flags required")
            result = verify_registered_synthetic_asset(
                a.registry, a.source, DbvoraClient(a.dbvora_url), synthetic=True,
            )
        print(json.dumps(result, sort_keys=True, ensure_ascii=False))
        return 0
    except (AssetRegistryError, OSError, ValueError, TypeError):
        print('{"status":"HOLD","code":"HAE_SYNTHETIC_REGISTRY_HOLD"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
