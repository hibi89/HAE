"""Explicit owner-reviewed local synthetic workflow catalog CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .workflow_catalog import (
    WorkflowCatalogError, initialize_workflow_catalog, list_synthetic_workflows,
    save_synthetic_workflow, load_synthetic_workflow,
)


class _SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise WorkflowCatalogError("invalid synthetic workflow catalog arguments")


def main(argv=None):
    try:
        p = _SafeParser(prog="HAE synthetic workflow catalog")
        p.add_argument("command", choices=("init", "list", "save", "load"))
        p.add_argument("--catalog", type=Path, required=True)
        p.add_argument("--input-root", type=Path)
        p.add_argument("--task")
        p.add_argument("--csv")
        p.add_argument("--source-sha256")
        p.add_argument("--recipe-id")
        p.add_argument("--synthetic", action="store_true")
        p.add_argument("--ack-new-file", action="store_true")
        p.add_argument("--ack-save", action="store_true")
        a = p.parse_args(argv)
        if not a.synthetic:
            raise WorkflowCatalogError("synthetic-only catalog")
        if a.command == "init":
            if (a.input_root is not None or a.task is not None or a.csv is not None
                    or a.source_sha256 is not None or a.recipe_id is not None or a.ack_save):
                raise WorkflowCatalogError("unsupported init arguments")
            result = initialize_workflow_catalog(
                a.catalog, synthetic=True, acknowledge_new_file=a.ack_new_file)
        elif a.command == "list":
            if (a.input_root is not None or a.task is not None or a.csv is not None
                    or a.source_sha256 is not None or a.recipe_id is not None
                    or a.ack_save or a.ack_new_file):
                raise WorkflowCatalogError("unsupported list arguments")
            result = list_synthetic_workflows(a.catalog, synthetic=True)
        elif a.command == "save":
            if (a.input_root is None or a.task is None or a.csv is None
                    or a.source_sha256 is None or a.recipe_id is not None
                    or not a.ack_save or a.ack_new_file):
                raise WorkflowCatalogError("save requires owner approval and source identity")
            result = save_synthetic_workflow(
                a.catalog, a.input_root, a.task, a.csv, a.source_sha256,
                synthetic=True, approve_save=True)
        else:
            if (a.input_root is None or a.recipe_id is None or a.task is not None
                    or a.csv is not None or a.source_sha256 is not None
                    or a.ack_save or a.ack_new_file):
                raise WorkflowCatalogError("load requires the recipe id and current input root")
            result = load_synthetic_workflow(
                a.catalog, a.recipe_id, a.input_root, synthetic=True)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (WorkflowCatalogError, OSError, ValueError, TypeError):
        print('{"status":"HOLD","code":"HAE_SYNTHETIC_WORKFLOW_CATALOG_HOLD"}',
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
