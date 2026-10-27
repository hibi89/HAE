"""Real CLI bundle file generation with synthetic analysis results."""
from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rea_app import cli
from rea_app.graph import ParserError


class BundleCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rea-bundle-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.baseline = self.root / "baseline"
        self.current = self.root / "current"
        self.output = self.root / "output"
        self.baseline.mkdir()
        self.current.mkdir()
        (self.baseline / "app.ts").write_text("export const x = 1;\n", encoding="utf-8")
        (self.current / "app.ts").write_text("export const x = 2;\n", encoding="utf-8")
        self.args = argparse.Namespace(
            baseline=self.baseline, current=self.current, output_dir=self.output,
            max_files=100, max_file_bytes=1000, max_total_bytes=10000, parser_timeout=30,
            with_diagram=False,
        )
        self.source_report = {
            "schema_version": "rea-app-source-map/v1",
            "summary": {
                "files_indexed": 1, "source_files": 1, "dependency_edges": 1,
                "syntax_errors": 0,
            },
            "packages": [{"root": ".", "name": "example"}],
            "dependency_edges": [
                {"from_path": "src/main.ts", "to_path": "src/lib.ts",
                 "kind": "import", "resolution": "internal",
                 "evidence": {"path": "src/main.ts", "line": 1}},
            ],
            "function_contracts": [
                {"symbol": "load", "exported_as": "load", "kind": "FunctionDeclaration",
                 "parameters": [{"name": "id", "type_annotation": "string"}],
                 "return_type_annotation": "Result",
                 "evidence": {"definition": {"path": "app.ts", "line": 1},
                              "export": {"path": "app.ts", "line": 1}}},
            ],
        }
        self.impact_report = {
            "summary": {
                "syntax_errors": 0, "added_modules": 0, "removed_modules": 0,
                "added_internal_dependencies": 0, "removed_internal_dependencies": 0,
                "added_packages": 0, "removed_packages": 0, "changed_packages": 0,
            },
            "changed_files": [{"path": "app.ts", "status": "modified"}],
        }

    def fake_analysis(self):
        return (patch.object(cli, "walk_source", side_effect=["baseline_scan", "current_scan"]),
                patch.object(cli, "build_report", return_value=self.source_report),
                patch.object(cli, "build_change_impact", return_value=self.impact_report),
                patch.object(cli, "render_markdown", return_value="# Source map\n"),
                patch.object(cli, "render_change_impact_markdown", return_value="# Impact\n"))

    def run_faked(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            for fake in self.fake_analysis():
                stack.enter_context(fake)
            return cli._bundle(self.args)

    def test_generates_six_deterministic_outputs_with_evidence(self):
        prior = (self.baseline / "app.ts").read_bytes(), (self.current / "app.ts").read_bytes()
        self.assertEqual(self.run_faked(), 0)
        files = sorted(x.name for x in self.output.iterdir())
        self.assertEqual(files, ["change-impact.json", "change-impact.md", "functional-contracts.json",
                                 "functional-contracts.md", "source-map.json", "source-map.md"])
        contracts = json.loads((self.output / "functional-contracts.json").read_text(encoding="utf-8"))
        self.assertEqual(contracts["summary"]["exported_callable_contracts"], 1)
        self.assertEqual(contracts["contracts"][0]["evidence"]["definition"], {"path": "app.ts", "line": 1})
        self.assertIn("app.ts:1", (self.output / "functional-contracts.md").read_text(encoding="utf-8"))
        contents = {name: (self.output / name).read_bytes() for name in files}
        self.assertEqual(self.run_faked(), 0)
        self.assertEqual(contents, {name: (self.output / name).read_bytes() for name in files})
        self.assertEqual(prior, ((self.baseline / "app.ts").read_bytes(), (self.current / "app.ts").read_bytes()))

    def test_optional_diagram_writes_two_additional_viewable_outputs(self):
        self.args.with_diagram = True
        self.assertEqual(self.run_faked(), 0)
        self.assertEqual(len(list(self.output.iterdir())), 8)
        diagram = (self.output / "architecture.mmd").read_text(encoding="utf-8")
        markdown = (self.output / "architecture.md").read_text(encoding="utf-8")
        self.assertIn('src/main.ts', diagram)
        self.assertIn('src/lib.ts', diagram)
        self.assertIn('import @ 1', diagram)
        self.assertIn('```mermaid', markdown)
        first = {p.name: p.read_bytes() for p in self.output.iterdir()}
        self.assertEqual(self.run_faked(), 0)
        self.assertEqual(first, {p.name: p.read_bytes() for p in self.output.iterdir()})

    def test_optional_diagram_error_creates_no_partial_bundle(self):
        self.args.with_diagram = True
        self.source_report["dependency_edges"][0]["from_path"] = "../outside.ts"
        self.assertEqual(self.run_faked(), 2)
        self.assertFalse(self.output.exists())

    def test_reuses_current_report_instead_of_reparsing_current_tree(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            mocks = [stack.enter_context(fake) for fake in self.fake_analysis()]
            self.assertEqual(cli._bundle(self.args), 0)
            mocks[1].assert_called_once_with("current_scan", self.args.parser_timeout)
            mocks[2].assert_called_once_with(
                "baseline_scan", "current_scan", self.args.parser_timeout,
                current_report=self.source_report,
            )

    def test_rejects_overlapping_snapshots(self):
        self.args.current = self.baseline
        self.assertEqual(self.run_faked(), 2)
        self.assertFalse(self.output.exists())

    def test_parser_failure_writes_no_artifacts(self):
        with patch.object(cli, "walk_source", side_effect=["baseline_scan", "current_scan"]), \
             patch.object(cli, "build_report", side_effect=ParserError("parser unavailable")):
            self.assertEqual(cli._bundle(self.args), 3)
        self.assertFalse(self.output.exists())

    def test_cli_parser_registers_bundle(self):
        parsed = cli.build_argument_parser().parse_args(
            ["bundle", str(self.baseline), str(self.current), "--output-dir", str(self.output)]
        )
        self.assertEqual(parsed.command, "bundle")
        self.assertIs(parsed.handler, cli._bundle)


if __name__ == "__main__":
    unittest.main()
