"""End-to-end contracts CLI smoke tests using synthetic prior scan evidence."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]


class ContractsCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="rea-contracts-cli-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source_map = self.root / "source-map.json"
        self.output = self.root / "output"
        self.fixture = {
            "schema_version": "rea-app-source-map/v1",
            "packages": [{"root": ".", "name": "demo"}],
            "function_contracts": [{
                "symbol": "parseOrder", "exported_as": "parseOrder", "kind": "FunctionDeclaration",
                "parameters": [{"name": "text", "type_annotation": "string"}],
                "return_type_annotation": "Order",
                "evidence": {"definition": {"path": "src/main.ts", "line": 3},
                             "export": {"path": "src/main.ts", "line": 3}},
                "implementation_body": "do-not-copy-this-source",
            }],
        }
        self.source_map.write_text(json.dumps(self.fixture), encoding="utf-8")

    def run_cli(self, source: Path | None = None, output: Path | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(TOOL_ROOT)
        return subprocess.run(
            [sys.executable, "-m", "rea_app", "contracts", str(source or self.source_map),
             "--output-dir", str(output or self.output)],
            cwd=TOOL_ROOT, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10, check=False,
        )

    def test_writes_evidenced_json_and_markdown_without_source_body(self) -> None:
        original = hashlib.sha256(self.source_map.read_bytes()).hexdigest()
        run = self.run_cli()
        self.assertEqual(run.returncode, 0, run.stderr)
        document = json.loads((self.output / "functional-contracts.json").read_text(encoding="utf-8"))
        markdown = (self.output / "functional-contracts.md").read_text(encoding="utf-8")
        self.assertEqual(document["summary"]["exported_callable_contracts"], 1)
        self.assertEqual(document["contracts"][0]["evidence"]["definition"], {"path": "src/main.ts", "line": 3})
        self.assertIn("src/main.ts:3", markdown)
        self.assertNotIn("do-not-copy-this-source", json.dumps(document) + markdown)
        self.assertEqual(hashlib.sha256(self.source_map.read_bytes()).hexdigest(), original)

    def test_repeat_execution_is_byte_identical(self) -> None:
        self.assertEqual(self.run_cli().returncode, 0)
        first = tuple((self.output / name).read_bytes() for name in ("functional-contracts.json", "functional-contracts.md"))
        self.assertEqual(self.run_cli().returncode, 0)
        self.assertEqual(first, tuple((self.output / name).read_bytes() for name in ("functional-contracts.json", "functional-contracts.md")))

    def test_invalid_schema_fails_without_partial_output(self) -> None:
        self.fixture["schema_version"] = "unsupported"
        self.source_map.write_text(json.dumps(self.fixture), encoding="utf-8")
        run = self.run_cli()
        self.assertEqual(run.returncode, 2)
        self.assertFalse(self.output.exists())

    def test_rejects_overwriting_source_map(self) -> None:
        self.output.mkdir()
        target = self.output / "functional-contracts.json"
        target.write_bytes(self.source_map.read_bytes())
        original = target.read_bytes()
        run = self.run_cli(source=target)
        self.assertEqual(run.returncode, 2)
        self.assertEqual(target.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
