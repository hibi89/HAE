"""Real Babel-backed CLI acceptance for six- and eight-report JS/TS bundles.

Run in an authorized tools/rea-app checkout after `npm ci`. This test never
falls back to a mock parser, and modifies only its private tempfile fixture.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    "source-map.json", "source-map.md",
    "change-impact.json", "change-impact.md",
    "functional-contracts.json", "functional-contracts.md",
)
DIAGRAM_ARTIFACTS = ARTIFACTS + ("architecture.mmd", "architecture.md")


class RealBundleMvpAcceptanceTests(unittest.TestCase):
    def test_bundle_import_impact_contracts_and_original_immutability(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rea-bundle-real-parser-") as temporary:
            root = Path(temporary)
            before, after, output = root / "baseline", root / "current", root / "reports"
            for directory in (before, after):
                (directory / "src").mkdir(parents=True)
                (directory / "package.json").write_text(
                    '{"name":"synthetic-example","main":"./src/main.ts"}\n',
                    encoding="utf-8",
                )
                (directory / "src/main.ts").write_text(
                    'import { load } from "./lib";\n'
                    'export function run(id: string): number { return load(id); }\n',
                    encoding="utf-8",
                )
            (before / "src/lib.ts").write_text(
                'export function load(id: string): number { return id.length; }\n',
                encoding="utf-8",
            )
            (after / "src/lib.ts").write_text(
                'export function load(id: string): number { return id.length + 1; }\n',
                encoding="utf-8",
            )

            def snapshot(directory: Path) -> dict[str, bytes]:
                return {path.relative_to(directory).as_posix(): path.read_bytes()
                        for path in sorted(directory.rglob("*")) if path.is_file()}

            before_bytes, after_bytes = snapshot(before), snapshot(after)
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(TOOL_ROOT)
            command = [sys.executable, "-m", "rea_app", "bundle", str(before),
                       str(after), "--output-dir", str(output)]

            def run() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    command, cwd=TOOL_ROOT, env=environment, text=True,
                    encoding="utf-8", errors="replace", capture_output=True,
                    check=False, timeout=90,
                )

            first = run()
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            self.assertEqual(set(path.name for path in output.iterdir()), set(ARTIFACTS))
            source = json.loads((output / "source-map.json").read_text(encoding="utf-8"))
            impact = json.loads((output / "change-impact.json").read_text(encoding="utf-8"))
            contracts = json.loads((output / "functional-contracts.json").read_text(encoding="utf-8"))
            self.assertIn(
                f"Analysis scope: {source['summary']['files_indexed']} files indexed, "
                f"{source['summary']['source_files']} JavaScript/TypeScript source files, "
                f"{source['summary']['dependency_edges']} dependency edges; "
                f"{len(impact['changed_files'])} changed files.",
                first.stdout,
            )
            for name in ARTIFACTS:
                self.assertIn(str(output / name), first.stdout)

            self.assertEqual(source["schema_version"], "rea-app-source-map/v1")
            edges = [edge for edge in source["dependency_edges"]
                     if edge["from_path"] == "src/main.ts" and edge["to_path"] == "src/lib.ts"]
            self.assertTrue(edges, "import must resolve to src/lib.ts")
            self.assertEqual(edges[0]["evidence"], {"path": "src/main.ts", "line": 1})
            self.assertIn({"path": "src/lib.ts", "status": "modified"},
                          [{"path": item["path"], "status": item["status"]}
                           for item in impact["changed_files"]])
            changed = next(item for item in impact["impacts"] if item["changed_path"] == "src/lib.ts")
            self.assertIn("src/main.ts", [item["path"] for item in changed["direct_dependents"]])
            self.assertTrue(any(item["path"] == "src/main.ts" for item in changed["impacted_entrypoints"]))
            self.assertEqual(contracts["schema_version"], "rea-app-functional-contracts/v1")
            exported = {(item["module"], item["exported_as"]): item for item in contracts["contracts"]}
            self.assertIn(("src/main.ts", "run"), exported)
            self.assertEqual(exported[("src/main.ts", "run")]["evidence"]["definition"],
                             {"path": "src/main.ts", "line": 2})
            self.assertIn("src/main.ts:2", (output / "functional-contracts.md").read_text(encoding="utf-8"))
            first_files = {name: (output / name).read_bytes() for name in ARTIFACTS}

            again = run()
            self.assertEqual(again.returncode, 0, again.stderr + again.stdout)
            self.assertEqual(first_files, {name: (output / name).read_bytes() for name in ARTIFACTS})
            self.assertEqual(before_bytes, snapshot(before))
            self.assertEqual(after_bytes, snapshot(after))

    def test_bundle_with_diagram_emits_eight_reports_deterministically(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rea-bundle-real-diagram-") as temporary:
            root = Path(temporary)
            before, after, output = root / "baseline", root / "current", root / "reports"
            for directory in (before, after):
                (directory / "src").mkdir(parents=True)
                (directory / "package.json").write_bytes(
                    b'{"name":"synthetic-example","main":"./src/main.ts"}\n'
                )
                (directory / "src/main.ts").write_bytes(
                    b'import { load } from "./lib";\n'
                    b'export function run(id: string): number { return load(id); }\n'
                )
            (before / "src/lib.ts").write_bytes(
                b'export function load(id: string): number { return id.length; }\n'
            )
            (after / "src/lib.ts").write_bytes(
                b'export function load(id: string): number { return id.length + 1; }\n'
            )

            def snapshot(directory: Path) -> dict[str, bytes]:
                return {path.relative_to(directory).as_posix(): path.read_bytes()
                        for path in sorted(directory.rglob("*")) if path.is_file()}

            before_bytes, after_bytes = snapshot(before), snapshot(after)
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(TOOL_ROOT)
            command = [sys.executable, "-m", "rea_app", "bundle", str(before),
                       str(after), "--output-dir", str(output), "--with-diagram"]

            def run() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    command, cwd=TOOL_ROOT, env=environment, text=True,
                    encoding="utf-8", errors="replace", capture_output=True,
                    check=False, timeout=90,
                )

            first = run()
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            self.assertIn("8 reports", first.stdout)
            self.assertEqual(set(path.name for path in output.iterdir()), set(DIAGRAM_ARTIFACTS))
            source = json.loads((output / "source-map.json").read_text(encoding="utf-8"))
            self.assertIn("Analysis scope:", first.stdout)
            for name in DIAGRAM_ARTIFACTS:
                self.assertIn(str(output / name), first.stdout)
            edge = next(item for item in source["dependency_edges"]
                        if item["from_path"] == "src/main.ts" and item["to_path"] == "src/lib.ts")
            self.assertEqual(edge["evidence"], {"path": "src/main.ts", "line": 1})
            diagram = (output / "architecture.mmd").read_text(encoding="utf-8")
            self.assertIn('"src/main.ts"', diagram)
            self.assertIn('"src/lib.ts"', diagram)
            self.assertIn('"import @ 1"', diagram)
            first_files = {name: (output / name).read_bytes() for name in DIAGRAM_ARTIFACTS}

            again = run()
            self.assertEqual(again.returncode, 0, again.stderr + again.stdout)
            self.assertEqual(first_files,
                             {name: (output / name).read_bytes() for name in DIAGRAM_ARTIFACTS})
            self.assertEqual(before_bytes, snapshot(before))
            self.assertEqual(after_bytes, snapshot(after))

    def test_bundle_compares_module_edges_and_package_boundaries(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rea-bundle-architecture-diff-") as temporary:
            root = Path(temporary)
            before, after, output = root / "baseline", root / "current", root / "reports"
            for directory in (before, after):
                (directory / "src").mkdir(parents=True)
                (directory / "package.json").write_bytes(
                    b'{"name":"synthetic-example","main":"./src/main.ts"}\n'
                )
                (directory / "src/main.ts").write_bytes(
                    b'export function run() { return read(); }\n'
                )
            (before / "packages/old/src").mkdir(parents=True)
            (before / "packages/old/package.json").write_bytes(b'{"name":"old-store"}\n')
            (before / "packages/old/src/index.ts").write_bytes(
                b'export function read() { return "old"; }\n'
            )
            (before / "src/main.ts").write_bytes(
                b'import { read } from "../packages/old/src/index";\n'
                b'export function run() { return read(); }\n'
            )
            (after / "packages/new/src").mkdir(parents=True)
            (after / "packages/new/package.json").write_bytes(b'{"name":"new-store"}\n')
            (after / "packages/new/src/index.ts").write_bytes(
                b'export function read() { return "new"; }\n'
            )
            (after / "src/main.ts").write_bytes(
                b'import { read } from "../packages/new/src/index";\n'
                b'export function run() { return read(); }\n'
            )

            def snapshot(directory: Path) -> dict[str, bytes]:
                return {path.relative_to(directory).as_posix(): path.read_bytes()
                        for path in sorted(directory.rglob("*")) if path.is_file()}

            before_bytes, after_bytes = snapshot(before), snapshot(after)
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(TOOL_ROOT)
            command = [sys.executable, "-m", "rea_app", "bundle", str(before),
                       str(after), "--output-dir", str(output)]

            def run() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    command, cwd=TOOL_ROOT, env=environment, text=True,
                    encoding="utf-8", errors="replace", capture_output=True,
                    check=False, timeout=90,
                )

            first = run()
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            impact = json.loads((output / "change-impact.json").read_text(encoding="utf-8"))
            architecture = impact["architecture_changes"]
            self.assertEqual(
                [item["path"] for item in architecture["modules"]["added"]],
                ["packages/new/src/index.ts"],
            )
            self.assertEqual(
                [item["path"] for item in architecture["modules"]["removed"]],
                ["packages/old/src/index.ts"],
            )
            self.assertEqual(
                [(item["from_path"], item["to_path"]) for item in architecture["dependencies"]["added"]],
                [("src/main.ts", "packages/new/src/index.ts")],
            )
            self.assertEqual(
                architecture["dependencies"]["added"][0]["evidence"],
                [{"kind": "import", "evidence": {"path": "src/main.ts", "line": 1}}],
            )
            self.assertEqual(
                [(item["from_path"], item["to_path"]) for item in architecture["dependencies"]["removed"]],
                [("src/main.ts", "packages/old/src/index.ts")],
            )
            self.assertEqual(
                [(item["root"], item["name"]) for item in architecture["packages"]["added"]],
                [("packages/new", "new-store")],
            )
            self.assertEqual(
                [(item["root"], item["name"]) for item in architecture["packages"]["removed"]],
                [("packages/old", "old-store")],
            )
            self.assertEqual(impact["summary"]["added_internal_dependencies"], 1)
            self.assertEqual(impact["summary"]["removed_internal_dependencies"], 1)
            self.assertIn("Architecture delta: +1/-1 modules", first.stdout)
            self.assertIn("+1/-1 resolved internal dependencies", first.stdout)
            self.assertIn("+1/-1 packages", first.stdout)
            self.assertIn("API contract delta: +1/-1 added/removed, 0 changed", first.stdout)
            markdown = (output / "change-impact.md").read_text(encoding="utf-8")
            self.assertIn("## Module architecture changes", markdown)
            self.assertIn("src/main.ts:1", markdown)
            self.assertIn("packages/new", markdown)

            first_files = {path.name: path.read_bytes() for path in output.iterdir()}
            again = run()
            self.assertEqual(again.returncode, 0, again.stderr + again.stdout)
            self.assertEqual(first_files, {path.name: path.read_bytes() for path in output.iterdir()})
            self.assertEqual(before_bytes, snapshot(before))
            self.assertEqual(after_bytes, snapshot(after))

    def test_bundle_compares_exported_callable_contracts_without_bodies_or_defaults(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rea-bundle-contract-diff-") as temporary:
            root = Path(temporary)
            before, after, output = root / "baseline", root / "current", root / "reports"
            for directory in (before, after):
                (directory / "src").mkdir(parents=True)
                (directory / "package.json").write_bytes(b'{"name":"contract-fixture"}\n')
            (before / "src/api.ts").write_bytes(
                b'export function run(id: string): number { return id.length; }\n'
                b'export function legacy(enabled?: boolean): boolean { return Boolean(enabled); }\n'
            )
            (after / "src/api.ts").write_bytes(
                b'exports.run = async function run(id: number = 9137): Promise<string> { '
                b'return "private-body-marker"; };\n'
                b'export function modern(): string { return "private-added-body"; }\n'
            )

            def snapshot(directory: Path) -> dict[str, bytes]:
                return {path.relative_to(directory).as_posix(): path.read_bytes()
                        for path in sorted(directory.rglob("*")) if path.is_file()}

            before_bytes, after_bytes = snapshot(before), snapshot(after)
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(TOOL_ROOT)
            command = [sys.executable, "-m", "rea_app", "bundle", str(before),
                       str(after), "--output-dir", str(output)]

            def run() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    command, cwd=TOOL_ROOT, env=environment, text=True,
                    encoding="utf-8", errors="replace", capture_output=True,
                    check=False, timeout=90,
                )

            first = run()
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            impact = json.loads((output / "change-impact.json").read_text(encoding="utf-8"))
            changes = impact["contract_changes"]
            self.assertEqual(
                [(item["module"], item["exported_as"]) for item in changes["added"]],
                [("src/api.ts", "modern")],
            )
            self.assertEqual(
                [(item["module"], item["exported_as"]) for item in changes["removed"]],
                [("src/api.ts", "legacy")],
            )
            changed = changes["changed"]
            self.assertEqual([(item["module"], item["exported_as"]) for item in changed],
                             [("src/api.ts", "run")])
            before_signature = changed[0]["baseline"]["signature"]
            after_signature = changed[0]["current"]["signature"]
            self.assertEqual(before_signature["export_kinds"], ["export"])
            self.assertEqual(after_signature["export_kinds"], ["commonjs_export"])
            self.assertEqual(before_signature["parameters"][0]["type_annotation"], "string")
            self.assertEqual(after_signature["parameters"][0]["type_annotation"], "number")
            self.assertTrue(after_signature["parameters"][0]["has_default"])
            self.assertTrue(after_signature["async"])
            self.assertEqual(after_signature["return_type_annotation"], "Promise<string>")
            self.assertEqual(changed[0]["current"]["evidence"]["definition"],
                             {"path": "src/api.ts", "line": 1})
            self.assertEqual(impact["summary"]["added_contracts"], 1)
            self.assertEqual(impact["summary"]["removed_contracts"], 1)
            self.assertEqual(impact["summary"]["changed_contracts"], 1)
            self.assertIn("API contract delta: +1/-1 added/removed, 1 changed", first.stdout)
            markdown = (output / "change-impact.md").read_text(encoding="utf-8")
            self.assertIn("## Exported callable contract changes", markdown)
            self.assertIn("src/api.ts:1", markdown)
            self.assertIn("id: number = <default>", markdown)
            self.assertIn("runtime compatibility verdict", " ".join(changes["limitations"]))
            for artifact in output.iterdir():
                content = artifact.read_bytes()
                self.assertNotIn(b"private-body-marker", content)
                self.assertNotIn(b"private-added-body", content)
                self.assertNotIn(b"9137", content)

            first_files = {path.name: path.read_bytes() for path in output.iterdir()}
            again = run()
            self.assertEqual(again.returncode, 0, again.stderr + again.stdout)
            self.assertEqual(first_files, {path.name: path.read_bytes() for path in output.iterdir()})
            self.assertEqual(before_bytes, snapshot(before))
            self.assertEqual(after_bytes, snapshot(after))

    def test_default_export_contract_tracks_commonjs_module_exports_alias(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rea-bundle-default-contract-") as temporary:
            root = Path(temporary)
            before, after, output = root / "baseline", root / "current", root / "reports"
            for directory in (before, after):
                (directory / "src").mkdir(parents=True)
                (directory / "package.json").write_bytes(b'{"name":"default-contract-fixture"}\n')
            (before / "src/api.ts").write_bytes(
                b'export default function createUser(id: string): User { return buildUser(id); }\n'
            )
            (after / "src/api.ts").write_bytes(
                b'function createUser(id: string): User { return buildUser(id, "private-cjs-body"); }\n'
                b'module.exports = createUser;\n'
            )

            def snapshot(directory: Path) -> dict[str, bytes]:
                return {path.relative_to(directory).as_posix(): path.read_bytes()
                        for path in sorted(directory.rglob("*")) if path.is_file()}

            before_bytes, after_bytes = snapshot(before), snapshot(after)
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(TOOL_ROOT)
            command = [sys.executable, "-m", "rea_app", "bundle", str(before),
                       str(after), "--output-dir", str(output)]

            def run() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    command, cwd=TOOL_ROOT, env=environment, text=True,
                    encoding="utf-8", errors="replace", capture_output=True,
                    check=False, timeout=90,
                )

            first = run()
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            impact = json.loads((output / "change-impact.json").read_text(encoding="utf-8"))
            changes = impact["contract_changes"]
            self.assertEqual(changes["added"], [])
            self.assertEqual(changes["removed"], [])
            self.assertEqual(
                [(item["module"], item["exported_as"]) for item in changes["changed"]],
                [("src/api.ts", "default")],
            )
            changed = changes["changed"][0]
            self.assertEqual(changed["baseline"]["signature"]["export_kinds"], ["default_export"])
            self.assertEqual(changed["current"]["signature"]["export_kinds"], ["commonjs_export"])
            self.assertEqual(changed["current"]["signature"]["parameters"][0]["type_annotation"], "string")
            self.assertEqual(changed["baseline"]["evidence"]["export"],
                             {"path": "src/api.ts", "line": 1, "name": "default"})
            self.assertEqual(changed["current"]["evidence"]["definition"],
                             {"path": "src/api.ts", "line": 1})
            self.assertEqual(changed["current"]["evidence"]["export"],
                             {"path": "src/api.ts", "line": 2, "name": "default"})
            contracts = json.loads((output / "functional-contracts.json").read_text(encoding="utf-8"))
            current_contract = next(item for item in contracts["contracts"]
                                    if item["module"] == "src/api.ts" and item["exported_as"] == "default")
            self.assertEqual(current_contract["symbol"], "createUser")
            for artifact in output.iterdir():
                self.assertNotIn(b"private-cjs-body", artifact.read_bytes())

            first_files = {path.name: path.read_bytes() for path in output.iterdir()}
            again = run()
            self.assertEqual(again.returncode, 0, again.stderr + again.stdout)
            self.assertEqual(first_files, {path.name: path.read_bytes() for path in output.iterdir()})
            self.assertEqual(before_bytes, snapshot(before))
            self.assertEqual(after_bytes, snapshot(after))

    def test_bundle_compares_direct_in_root_esm_reexport_contracts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rea-bundle-reexport-contract-") as temporary:
            root = Path(temporary)
            before, after, output = root / "baseline", root / "current", root / "reports"
            for directory in (before, after):
                (directory / "src").mkdir(parents=True)
                (directory / "package.json").write_bytes(b'{"name":"reexport-contract-fixture"}\n')
                (directory / "src/facade.ts").write_bytes(
                    b'export { run as publicRun } from "./api";\n'
                    b'export { run as chainedRun } from "./middle";\n'
                    b'export { run as externalRun } from "external-package";\n'
                    b'export { run as sameLineA } from "./api"; export { run as sameLineB } from "./api";\n'
                )
                (directory / "src/middle.ts").write_bytes(
                    b'export { run } from "./api";\n'
                )
            (before / "src/api.ts").write_bytes(
                b'export function run(id: string): number { return id.length; }\n'
            )
            (after / "src/api.ts").write_bytes(
                b'export function run(id: number): string { return String(id); }\n'
            )

            def snapshot(directory: Path) -> dict[str, bytes]:
                return {path.relative_to(directory).as_posix(): path.read_bytes()
                        for path in sorted(directory.rglob("*")) if path.is_file()}

            before_bytes, after_bytes = snapshot(before), snapshot(after)
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(TOOL_ROOT)
            command = [sys.executable, "-m", "rea_app", "bundle", str(before),
                       str(after), "--output-dir", str(output)]

            def run() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    command, cwd=TOOL_ROOT, env=environment, text=True,
                    encoding="utf-8", errors="replace", capture_output=True,
                    check=False, timeout=90,
                )

            first = run()
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            source = json.loads((output / "source-map.json").read_text(encoding="utf-8"))
            impact = json.loads((output / "change-impact.json").read_text(encoding="utf-8"))
            contracts_report = json.loads((output / "functional-contracts.json").read_text(encoding="utf-8"))
            changes = impact["contract_changes"]
            changed = {(item["module"], item["exported_as"]): item
                       for item in changes["changed"]}
            self.assertEqual(set(changed), {
                ("src/api.ts", "run"),
                ("src/facade.ts", "publicRun"),
                ("src/middle.ts", "run"),
            })
            facade = changed[("src/facade.ts", "publicRun")]
            self.assertEqual(facade["baseline"]["signature"]["export_kinds"], ["reexport"])
            self.assertEqual(facade["current"]["signature"]["parameters"][0]["type_annotation"], "number")
            self.assertEqual(facade["baseline"]["evidence"], {
                "definition": {"path": "src/api.ts", "line": 1},
                "export": {"path": "src/facade.ts", "line": 1, "name": "publicRun"},
            })
            direct_reexport = changed[("src/middle.ts", "run")]
            self.assertEqual(direct_reexport["baseline"]["signature"]["export_kinds"], ["reexport"])
            self.assertEqual(direct_reexport["current"]["signature"]["parameters"][0]["type_annotation"], "number")
            self.assertEqual(direct_reexport["baseline"]["evidence"], {
                "definition": {"path": "src/api.ts", "line": 1},
                "export": {"path": "src/middle.ts", "line": 1, "name": "run"},
            })
            self.assertNotIn(("src/facade.ts", "chainedRun"), changed)
            self.assertNotIn(("src/facade.ts", "externalRun"), changed)
            self.assertNotIn(("src/facade.ts", "sameLineA"), changed)
            self.assertNotIn(("src/facade.ts", "sameLineB"), changed)
            self.assertEqual(source["summary"]["function_contracts"], 3)
            observed_source_contracts = {
                (item["evidence"]["export"]["path"], item["exported_as"]): item
                for item in source["function_contracts"]
            }
            self.assertEqual(set(observed_source_contracts), set(changed))
            observed_interfaces = {
                (item["module"], item["exported_as"]): item
                for item in contracts_report["contracts"]
            }
            self.assertEqual(set(observed_interfaces), set(changed))
            interface = observed_interfaces[("src/facade.ts", "publicRun")]
            self.assertEqual(interface["package"], "reexport-contract-fixture")
            self.assertEqual(interface["symbol"], "run")
            self.assertEqual(interface["evidence"], {
                "definition": {"path": "src/api.ts", "line": 1},
                "export": {"path": "src/facade.ts", "line": 1},
            })
            self.assertIn("src/facade.ts::publicRun", (output / "functional-contracts.md").read_text(encoding="utf-8"))
            for artifact in output.iterdir():
                self.assertNotIn(b"return id.length", artifact.read_bytes())
                self.assertNotIn(b"return String(id)", artifact.read_bytes())

            first_files = {path.name: path.read_bytes() for path in output.iterdir()}
            again = run()
            self.assertEqual(again.returncode, 0, again.stderr + again.stdout)
            self.assertEqual(first_files, {path.name: path.read_bytes() for path in output.iterdir()})
            self.assertEqual(before_bytes, snapshot(before))
            self.assertEqual(after_bytes, snapshot(after))


if __name__ == "__main__":
    unittest.main()
