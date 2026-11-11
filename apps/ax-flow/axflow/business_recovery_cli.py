"""Synthetic-only, read-only independent SQLite backup/restore verifier."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .business_recovery_chain import RecoveryChainError, verify_synthetic_restore_chain


class _SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise RecoveryChainError("invalid synthetic SQLite recovery arguments")


def main(argv: list[str] | None = None) -> int:
    try:
        parser = _SafeParser(prog="HAE synthetic recovery verification")
        parser.add_argument("--source", type=Path, required=True)
        parser.add_argument("--backup", type=Path, required=True)
        parser.add_argument("--restored", type=Path, required=True)
        parser.add_argument("--source-sha256", required=True)
        parser.add_argument("--backup-sha256", required=True)
        parser.add_argument("--synthetic", action="store_true")
        args = parser.parse_args(argv)
        proof = verify_synthetic_restore_chain(
            args.source, args.backup, args.restored,
            expected_source_sha256=args.source_sha256,
            expected_backup_sha256=args.backup_sha256,
            synthetic=args.synthetic,
        )
        print(json.dumps({"status": "VERIFIED_SYNTHETIC_RESTORE_CHAIN",
                          "result": proof}, sort_keys=True))
        return 0
    except (RecoveryChainError, OSError, RuntimeError, ValueError):
        # No filename, SQL text, row content, or stack trace in diagnostics.
        print('{"status":"HOLD","code":"HAE_SYNTHETIC_RESTORE_CHAIN_HOLD"}',
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
