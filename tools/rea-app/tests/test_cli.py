from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL_ROOT))
from rea_app import scanner
from rea_app.scanner import ScanLimits, walk_source

def snapshot(root: Path) -> dict[str, tuple[str, bytes | str]]:
    result: dict[str, tuple[str, bytes | str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[relative] = ("symlink", os.readlink(path))
        elif path.is_file():
            result[relative] = ("file", path.read_bytes())
    return result


class ReaAppCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="rea-app-test-")
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        self.output = self.base / "reports"
        self.source.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, relative: str, content: str | bytes) -> Path:
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
        return path

    def run_scan(self, *options: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        process_env = os.environ.copy()
        process_env["PYTHONPATH"] = str(TOOL_ROOT)
        if env:
            process_env.update(env)
        return subprocess.run(
            [sys.executable, "-m", "rea_app", "scan", str(self.source), "--output-dir", str(self.output), *options],
            cwd=TOOL_ROOT,
            env=process_env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )

    def create_graph_fixture(self) -> Path | None:
        self.write(
            "package.json",
            '{\n'
            '  "name": "fixture-app",\n'
            '  "version": "1.0.0",\n'
            '  "main": "./src/main.ts",\n'
            '  "exports": { ".": "./src/main.ts" },\n'
            '  "dependencies": { "react": "18.0.0" }\n'
            '}\n',
        )
        self.write("tsconfig.json", '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}\n')
        self.write(
            "src/main.ts",
            'import { add as sum } from "@/math";\n'
            'import type { Config } from "./types";\n'
            'import React from "react";\n'
            'import { value } from "./cycle.js";\n'
            'import bridge from "./bridge.cjs";\n'
            'export const run = (config: Config) => sum(value) + React + bridge;\n'
            'run({ enabled: true });\n',
        )
        self.write("src/cycle.ts", 'import { run } from "./main";\nexport const value = run;\n')
        self.write("src/math.ts", "export function add(a: number, b: number) { return a + b; }\n")
        self.write("src/types.ts", "export interface Config { enabled: boolean }\n")
        self.write(
            "src/bridge.cjs",
            'const { createRequire } = require(\n'
            '  "node:module"\n'
            ');\n'
            'const dep = require(\n'
            '  "../vendor/dep.cjs"\n'
            ');\n'
            'module.exports = dep;\n'
            'exports.named = function named() {};\n',
        )
        self.write("vendor/dep.cjs", "module.exports = 1;\n")
        self.write("src/broken.ts", "export const = ;\n")
        self.write(".env.production", "API_KEY=not-for-analysis\n")
        self.write("image.bin", b"\x00\x01\xffbinary")
        self.write("node_modules/ignored.ts", "export const ignored = true;\n")
        self.write(".git/ignored.js", "export const ignored = true;\n")
        outside = self.base / "outside.ts"
        outside.write_text("export const outside = true;\n", encoding="utf-8")
        link = self.source / "outside-link.ts"
        try:
            os.symlink(outside, link)
            return link
        except (OSError, NotImplementedError):
            return None

    def test_deterministic_graph_evidence_and_source_unchanged(self) -> None:
        link = self.create_graph_fixture()
        before = snapshot(self.source)
        first = self.run_scan()
        self.assertEqual(first.returncode, 1, first.stderr + first.stdout)
        report_path = self.output / "source-map.json"
        markdown_path = self.output / "source-map.md"
        self.assertTrue(report_path.is_file())
        self.assertTrue(markdown_path.is_file())
        first_json = report_path.read_bytes()
        first_markdown = markdown_path.read_bytes()
        report = json.loads(first_json)

        self.assertEqual(report["schema_version"], "rea-app-source-map/v1")
        self.assertEqual(report["parser"], "@babel/parser@7.29.9")
        self.assertGreaterEqual(report["summary"]["dependency_edges"], 8)
        edges = report["dependency_edges"]
        alias = next(edge for edge in edges if edge["specifier"] == "@/math")
        self.assertEqual(alias["resolution"], "internal_alias")
        self.assertEqual(alias["to_path"], "src/math.ts")
        self.assertEqual(alias["evidence"], {"path": "src/main.ts", "line": 1})
        external = next(edge for edge in edges if edge["specifier"] == "react")
        self.assertEqual(external["resolution"], "external")
        self.assertTrue(external["declared_dependency"])
        cjs = next(edge for edge in edges if edge["specifier"] == "../vendor/dep.cjs")
        self.assertEqual(cjs["resolution"], "internal")
        self.assertEqual(cjs["evidence"]["line"], 4)
        self.assertTrue(any(edge["from_path"] == "src/main.ts" and edge["to_path"] == "src/cycle.ts" for edge in edges))
        self.assertTrue(any(edge["from_path"] == "src/cycle.ts" and edge["to_path"] == "src/main.ts" for edge in edges))
        self.assertTrue(any(item["name"] == "default" and item["kind"] == "commonjs_export" for item in report["exports"]))
        self.assertTrue(any(item["kind"] == "commonjs_export" and item["name"] == "named" for item in report["exports"]))
        self.assertTrue(any(entry["resolved_path"] == "src/main.ts" for entry in report["packages"][0]["entrypoints"]))
        self.assertTrue(any(item["kind"] == "syntax_error" and item["path"] == "src/broken.ts" for item in report["diagnostics"]))
        self.assertNotIn(".env.production", {item["path"] for item in report["files"]})
        self.assertTrue(any(item["path"] == ".env.production" and item["reason"] == "secret_name" for item in report["skipped_files"]))
        self.assertTrue(any(item["path"] == "image.bin" and item["reason"] == "binary" for item in report["skipped_files"]))
        self.assertFalse(any(item["path"].startswith("node_modules/") for item in report["files"]))
        if link:
            self.assertTrue(any(item["path"] == "outside-link.ts" and item["reason"] == "symlink" for item in report["skipped_files"]))

        second = self.run_scan()
        self.assertEqual(second.returncode, 1, second.stderr + second.stdout)
        self.assertEqual(report_path.read_bytes(), first_json)
        self.assertEqual(markdown_path.read_bytes(), first_markdown)
        self.assertEqual(snapshot(self.source), before)

    def test_zero_file_repository_is_a_valid_empty_inventory(self) -> None:
        result = self.run_scan()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads((self.output / "source-map.json").read_text(encoding="utf-8"))
        self.assertEqual(report["summary"]["files_indexed"], 0)
        self.assertEqual(report["dependency_edges"], [])

    def test_file_count_cap_fails_closed_without_partial_reports(self) -> None:
        self.write("a.ts", "export const a = 1;\n")
        self.write("b.ts", "export const b = 2;\n")
        result = self.run_scan("--max-files", "1")
        self.assertEqual(result.returncode, 2)
        self.assertIn("file-count limit exceeded", result.stderr)
        self.assertFalse(self.output.exists())

    def test_total_byte_cap_fails_closed(self) -> None:
        self.write("large.ts", "export const value = 'a value larger than the cap';\n")
        result = self.run_scan("--max-total-bytes", "8")
        self.assertEqual(result.returncode, 2)
        self.assertIn("total-byte limit exceeded", result.stderr)
        self.assertFalse(self.output.exists())

    def test_oversized_individual_file_is_skipped_and_reported(self) -> None:
        self.write("notes.txt", "0123456789abcdef\n")
        result = self.run_scan("--max-file-bytes", "8", "--max-total-bytes", "128")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads((self.output / "source-map.json").read_text(encoding="utf-8"))
        self.assertTrue(any(item["path"] == "notes.txt" and item["reason"] == "file_size_limit" for item in report["skipped_files"]))

    def test_output_inside_source_root_is_rejected(self) -> None:
        result = self.run_scan("--output-dir", str(self.source / "reports"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("outside the selected source root", result.stderr)
        self.assertEqual(list(self.source.iterdir()), [])

    def test_missing_parser_fails_with_coverage_limitation(self) -> None:
        self.write("main.ts", "export const value = 1;\n")
        result = self.run_scan(env={"NODE_PATH": ""})
        self.assertEqual(result.returncode, 3)
        self.assertIn("parser unavailable", result.stderr)
        self.assertFalse(self.output.exists())

    def test_link_detection_skips_path_before_reading_it(self) -> None:
        linked = self.write("outside-link.ts", "export const must_not_be_read = true;\n")
        before = snapshot(self.source)
        real_check = scanner._is_link_or_reparse_point
        with patch.object(
            scanner,
            "_is_link_or_reparse_point",
            side_effect=lambda path: path == linked or real_check(path),
        ):
            result = walk_source(self.source, ScanLimits())
        self.assertNotIn("outside-link.ts", {item.path for item in result.files})
        self.assertTrue(any(item["path"] == "outside-link.ts" and item["reason"] == "symlink" for item in result.skipped_files))
        self.assertEqual(snapshot(self.source), before)


if __name__ == "__main__":
    unittest.main()
