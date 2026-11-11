"""Synthetic-only offline HAE metadata tool; no database writes or network."""
from __future__ import annotations

import argparse
import json
import sys
from .schema_inventory import SchemaInventoryError, inspect_offline_schema


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--synthetic', action='store_true', help='required; customer data is not accepted')
    parser.add_argument('--owner-review-names', action='store_true', help='show identifiers locally')
    arguments = parser.parse_args(argv)
    try:
        receipt = inspect_offline_schema(arguments.source, synthetic=arguments.synthetic,
                                         reveal_names=arguments.owner_review_names)
    except SchemaInventoryError:
        print('HAE schema inventory: HOLD (unsupported or unapproved local input)', file=sys.stderr)
        return 2
    print(json.dumps(receipt, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
