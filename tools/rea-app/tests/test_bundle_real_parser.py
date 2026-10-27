"""Real Babel-backed CLI acceptance: bundle all six reports from synthetic JS/TS snapshots.

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


if __name__ == "__main__":
    unittest.main()
