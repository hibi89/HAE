"""Explicit synthetic-only HAE business SQLite inspection and fresh-path copying."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .business_state_backup import (
    BusinessBackupError,
    inspect_business_state,
    backup_business_state,
    restore_business_state_pinned,
)


class _SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise BusinessBackupError("invalid offline business SQLite arguments")


def main(argv: list[str] | None = None) -> int:
    parser = _SafeParser(prog="HAE local business SQLite (synthetic-only)")
    parser.add_argument("command", choices=("inspect", "backup", "restore"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--ack-new-file", action="store_true")
    try:
        args = parser.parse_args(argv)
        if not args.synthetic:
            raise BusinessBackupError("synthetic-only offline acceptance is required")
        if args.command == "inspect":
            if args.destination is not None or args.expected_sha256 is not None or args.ack_new_file:
                raise BusinessBackupError("inspection requires source and synthetic flag only")
            result = inspect_business_state(args.source)
        elif args.command == "backup":
            if args.destination is None or not args.ack_new_file or args.expected_sha256 is not None:
                raise BusinessBackupError("backup needs a new destination and explicit acknowledgement")
            result = backup_business_state(args.source, args.destination)
        else:
            if args.destination is None or not args.ack_new_file or args.expected_sha256 is None:
                raise BusinessBackupError("restore needs new destination, expected SHA256 and acknowledgement")
            result = restore_business_state_pinned(
                args.source, args.destination, expected_sha256=args.expected_sha256
            )
        print(json.dumps({"command": args.command, "result": result},
                         ensure_ascii=False, sort_keys=True))
        return 0
    except (BusinessBackupError, OSError, ValueError):
        # No caller filename, row data, SQL text, secret, or stack trace.
        print('{"status":"ERROR","code":"HAE_BUSINESS_SQLITE_HOLD"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
