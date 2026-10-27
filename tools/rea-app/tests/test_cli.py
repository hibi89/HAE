from __future__ import annotations

import json
import os
import shutil
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
            'import { answer } from "../packages/lib/src/index";\n'
            'export const run = (config: Config) => sum(value) + React + bridge + answer();\n'
            'run({ enabled: true });\n',
        )
        self.write("src/cycle.ts", 'import { run } from "./main";\nexport function value() { return run(); }\n')
        self.write(
            "src/multiline.ts",
            'import {\n'
            '  value as aliasValue,\n'
            '} from "./cycle";\n'
            'export const read = () => aliasValue();\n',
        )
        self.write("src/math.ts", "export function add(a: number, b: number) { return a + b; }\n")
        self.write("src/types.ts", "export interface Config { enabled: boolean }\n")
        self.write("packages/lib/package.json", '{"name":"fixture-lib","version":"2.0.0","main":"./src/index.ts"}\n')
        self.write("packages/lib/src/index.ts", "export function answer() { return 42; }\n")
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
        self.assertEqual(report["tool_version"], "0.3.0")
        self.assertEqual(report["parser"], "@babel/parser@7.29.9")
        self.assertEqual(report["summary"]["packages"], 2)
        self.assertGreaterEqual(report["summary"]["dependency_edges"], 9)
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
        cross_package = next(edge for edge in edges if edge["specifier"] == "../packages/lib/src/index")
        self.assertEqual(cross_package["from_package"], "fixture-app")
        self.assertEqual(cross_package["to_package"], "fixture-lib")
        self.assertTrue(any(edge["from_path"] == "src/main.ts" and edge["to_path"] == "src/cycle.ts" for edge in edges))
        self.assertTrue(any(edge["from_path"] == "src/cycle.ts" and edge["to_path"] == "src/main.ts" for edge in edges))
        multiline = next(edge for edge in edges if edge["from_path"] == "src/multiline.ts")
        self.assertEqual(multiline["evidence"]["line"], 1)
        self.assertEqual(multiline["to_path"], "src/cycle.ts")
        imported_call = next(edge for edge in report["resolved_call_edges"] if edge["target_symbol"] == "add")
        self.assertEqual(imported_call["to_path"], "src/math.ts")
        self.assertEqual(imported_call["target_symbol"], "add")
        self.assertEqual(imported_call["evidence"]["import_binding"], {"path": "src/main.ts", "line": 1})
        self.assertEqual(imported_call["evidence"]["target_export"], {"path": "src/math.ts", "line": 1})
        multiline_call = next(edge for edge in report["resolved_call_edges"] if edge["from_path"] == "src/multiline.ts")
        self.assertEqual(multiline_call["target_symbol"], "value")
        self.assertEqual(multiline_call["evidence"]["call_site"]["line"], 4)
        package_call = next(edge for edge in report["resolved_call_edges"] if edge["target_symbol"] == "answer")
        self.assertEqual(package_call["to_path"], "packages/lib/src/index.ts")
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

    def test_value_flow_reports_simple_aliases_and_uses_without_guessing_mutations(self) -> None:
        self.write(
            "src/flows.ts",
            "export function relay(input: string) {\n"
            "  const copy = input;\n"
            "  const cleaned = sanitize(copy);\n"
            "  deliver(\n"
            "    cleaned,\n"
            "  );\n"
            "  return (\n"
            "    cleaned\n"
            "  );\n"
            "}\n"
            "export function shadow(value: string) {\n"
            "  const safe = value;\n"
            "  { const value = 'local'; consume(value); }\n"
            "  publish(safe);\n"
            "}\n"
            "export function reassigned(initial: string) {\n"
            "  let current = initial;\n"
            "  current = normalize(current);\n"
            "  consume(current);\n"
            "}\n",
        )
        before = snapshot(self.source)
        result = self.run_scan()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        json_path = self.output / "source-map.json"
        markdown_path = self.output / "source-map.md"
        first_json = json_path.read_bytes()
        first_markdown = markdown_path.read_bytes()
        report = json.loads(first_json)
        flows = report["value_flow_edges"]

        alias = next(item for item in flows if item["kind"] == "alias")
        self.assertEqual((alias["scope"], alias["from_symbol"], alias["to_symbol"]), ("relay", "input", "copy"))
        self.assertEqual(alias["evidence"]["source_binding"], {"path": "src/flows.ts", "line": 1})
        self.assertEqual(alias["evidence"]["source_reference"], {"path": "src/flows.ts", "line": 2})
        self.assertEqual(alias["evidence"]["target_binding"], {"path": "src/flows.ts", "line": 2})

        call_result = next(item for item in flows if item["kind"] == "call_result")
        self.assertEqual((call_result["from_callee"], call_result["to_symbol"]), ("sanitize", "cleaned"))
        self.assertEqual(call_result["evidence"]["producer"], {"path": "src/flows.ts", "line": 3})

        sink = next(item for item in flows if item["kind"] == "call_argument" and item["to_callee"] == "deliver")
        self.assertEqual((sink["from_symbol"], sink["argument_index"]), ("cleaned", 0))
        self.assertEqual(sink["evidence"]["source_use"], {"path": "src/flows.ts", "line": 5})
        self.assertEqual(sink["evidence"]["call_site"], {"path": "src/flows.ts", "line": 4})
        returned = next(item for item in flows if item["kind"] == "return")
        self.assertEqual(returned["from_symbol"], "cleaned")
        self.assertEqual(returned["evidence"]["source_use"]["line"], 8)
        self.assertEqual(returned["evidence"]["return_site"]["line"], 7)

        self.assertFalse(any(item.get("from_symbol") == "value" for item in flows))
        self.assertFalse(any(item.get("from_symbol") == "current" or item.get("to_symbol") == "current" for item in flows))
        self.assertEqual(report["summary"]["value_flow_edges"], len(flows))
        self.assertIn("Local value-flow observations", first_markdown.decode("utf-8"))
        self.assertNotIn('"local"', first_json.decode("utf-8"))

        repeat = self.run_scan()
        self.assertEqual(repeat.returncode, 0, repeat.stderr + repeat.stdout)
        self.assertEqual(json_path.read_bytes(), first_json)
        self.assertEqual(markdown_path.read_bytes(), first_markdown)
        self.assertEqual(snapshot(self.source), before)

    def test_exported_function_contracts_include_only_explicit_syntax_and_evidence(self) -> None:
        self.write(
            "src/contracts.ts",
            "export async function load(id: string, options?: { cache: boolean }): Promise<Result> { return await source('private-body-text'); }\n"
            "export const transform = (value: string, count = 9137): string => value;\n"
            "function helper(input: Payload): void {}\n"
            "export { helper as publicHelper };\n"
            "export default function (input: Payload): Promise<Response> { return route(input); }\n",
        )
        before = snapshot(self.source)
        result = self.run_scan()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report_path = self.output / "source-map.json"
        markdown_path = self.output / "source-map.md"
        report_bytes = report_path.read_bytes()
        report = json.loads(report_bytes)
        contracts = report["function_contracts"]
        self.assertEqual(report["summary"]["function_contracts"], 4)

        load = next(item for item in contracts if item["exported_as"] == "load")
        self.assertEqual(load["kind"], "FunctionDeclaration")
        self.assertTrue(load["async"])
        self.assertEqual(load["parameters"][0]["type_annotation"], "string")
        self.assertTrue(load["parameters"][1]["optional"])
        self.assertEqual(load["parameters"][1]["type_annotation"], "{ cache: boolean }")
        self.assertEqual(load["return_type_annotation"], "Promise<Result>")
        self.assertEqual(load["evidence"]["definition"], {"path": "src/contracts.ts", "line": 1})
        self.assertEqual(load["evidence"]["export"], {"path": "src/contracts.ts", "line": 1, "name": "load"})

        transform = next(item for item in contracts if item["exported_as"] == "transform")
        self.assertTrue(transform["parameters"][1]["has_default"])
        self.assertNotIn("default_value", transform["parameters"][1])
        self.assertEqual(transform["return_type_annotation"], "string")
        helper = next(item for item in contracts if item["exported_as"] == "publicHelper")
        self.assertEqual(helper["symbol"], "helper")
        default = next(item for item in contracts if item["exported_as"] == "default")
        self.assertEqual(default["symbol"], "default")
        self.assertEqual(default["return_type_annotation"], "Promise<Response>")

        json_text = report_bytes.decode("utf-8")
        markdown_text = markdown_path.read_text(encoding="utf-8")
        self.assertNotIn("private-body-text", json_text)
        self.assertNotIn("9137", json_text)
        self.assertIn("Exported function contracts", markdown_text)
        self.assertIn("count = <default>", markdown_text)
        self.assertIn("export evidence `src/contracts.ts:4`", markdown_text)
        repeat = self.run_scan()
        self.assertEqual(repeat.returncode, 0, repeat.stderr + repeat.stdout)
        self.assertEqual(report_path.read_bytes(), report_bytes)
        self.assertEqual(snapshot(self.source), before)

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
        isolated_tool = self.base / "isolated-tool"
        shutil.copytree(TOOL_ROOT / "rea_app", isolated_tool / "rea_app")
        shutil.copy2(TOOL_ROOT / "babel_parser_adapter.cjs", isolated_tool)
        process_env = os.environ.copy()
        process_env["PYTHONPATH"] = str(isolated_tool)
        process_env["NODE_PATH"] = ""
        result = subprocess.run(
            [sys.executable, "-m", "rea_app", "scan", str(self.source),
             "--output-dir", str(self.output)],
            cwd=isolated_tool,
            env=process_env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
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

    def test_windows_reparse_attribute_is_treated_as_link(self) -> None:
        class ReparsePath:
            def __init__(self, attributes: int) -> None:
                self.attributes = attributes

            def is_symlink(self) -> bool:
                return False

            def lstat(self):
                return type("StatResult", (), {"st_file_attributes": self.attributes})()

        with patch.object(scanner.os, "name", "nt"):
            self.assertTrue(scanner._is_link_or_reparse_point(ReparsePath(0x400)))
            self.assertFalse(scanner._is_link_or_reparse_point(ReparsePath(0)))


if __name__ == "__main__":
    unittest.main()
