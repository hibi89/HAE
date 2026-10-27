"""Output-file isolation regressions using only the audited CLI writer AST."""
from __future__ import annotations

import ast
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def load_writer():
    cli_file = Path(__file__).resolve().parents[1] / "rea_app" / "cli.py"
    module = ast.parse(cli_file.read_text(encoding="utf-8"), filename=str(cli_file))
    functions = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "_write_report"]
    if len(functions) != 1:
        raise AssertionError("expected exactly one _write_report function")
    namespace = {"Path": Path, "os": os, "tempfile": tempfile}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(cli_file), "exec"), namespace)
    return namespace["_write_report"]


class TestReportWriteSafety(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="rea-output-safety-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.reports = self.root / "reports"
        self.reports.mkdir()
        self.write_report = load_writer()

    def test_symlink_target_does_not_modify_other_file(self) -> None:
        outside = self.root / "protected.txt"
        outside.write_text("PRESERVE", encoding="utf-8")
        output = self.reports / "source-map.json"
        try:
            output.symlink_to(outside)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink fixture unavailable: {exc}")
        self.write_report(output, '{"ok":true}\n')
        self.assertEqual(outside.read_text(encoding="utf-8"), "PRESERVE")
        self.assertFalse(output.is_symlink())
        self.assertEqual(output.read_text(encoding="utf-8"), '{"ok":true}\n')

    def test_replaces_existing_report(self) -> None:
        output = self.reports / "source-map.json"
        output.write_text("OLD", encoding="utf-8")
        self.write_report(output, "NEW")
        self.assertEqual(output.read_text(encoding="utf-8"), "NEW")

    def test_replace_error_keeps_prior_report_and_removes_temp(self) -> None:
        output = self.reports / "source-map.json"
        output.write_text("OLD", encoding="utf-8")
        with patch.object(os, "replace", side_effect=OSError("synthetic replace failure")):
            with self.assertRaises(OSError):
                self.write_report(output, "NEW")
        self.assertEqual(output.read_text(encoding="utf-8"), "OLD")
        self.assertEqual(sorted(item.name for item in self.reports.iterdir()), ["source-map.json"])

    def test_utf8_output_and_no_temp_residue(self) -> None:
        output = self.reports / "source-map.md"
        self.write_report(output, "한글\nnext\n")
        self.assertEqual(output.read_bytes(), "한글\nnext\n".encode("utf-8"))
        self.assertEqual(sorted(item.name for item in self.reports.iterdir()), ["source-map.md"])


if __name__ == "__main__":
    unittest.main()
