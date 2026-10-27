from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rea_app.contracts import ContractError, build_functional_contracts, load_source_map, render_functional_contracts_markdown


class FunctionalContractsTests(unittest.TestCase):
    def sample(self):
        return {"schema_version": "rea-app-source-map/v1",
                "packages": [{"root": ".", "name": "root"}, {"root": "pkg", "name": "nested"}],
                "function_contracts": [{
                    "symbol": "load", "exported_as": "load", "kind": "FunctionDeclaration",
                    "async": True, "generator": False,
                    "parameters": [{"name": "id", "type_annotation": "string"}, {"name": "flag", "has_default": True}],
                    "return_type_annotation": "Promise<Result>",
                    "evidence": {"definition": {"path": "pkg/a.ts", "line": 3},
                                 "export": {"path": "pkg/a.ts", "line": 4}},
                    "source_body": "do-not-export-private-source",
                }]}

    def test_deterministic_contract_without_source_code(self):
        doc = build_functional_contracts(self.sample())
        self.assertEqual(doc, build_functional_contracts(self.sample()))
        self.assertEqual(doc["contracts"][0]["package"], "nested")
        self.assertEqual(doc["contracts"][0]["evidence"]["definition"]["line"], 3)
        self.assertNotIn("do-not-export-private-source", json.dumps(doc))
        self.assertIn("= <default>", render_functional_contracts_markdown(doc))

    def test_empty_contract_list_is_valid(self):
        fixture = self.sample()
        fixture["function_contracts"] = []
        self.assertEqual(build_functional_contracts(fixture)["summary"]["exported_callable_contracts"], 0)

    def test_rejects_bad_schema(self):
        fixture = self.sample()
        fixture["schema_version"] = "wrong"
        with self.assertRaises(ContractError):
            build_functional_contracts(fixture)

    def test_rejects_escaping_paths(self):
        for name in ("/tmp/a.ts", "../a.ts", "C:/a.ts", "pkg/../a.ts"):
            with self.subTest(name=name):
                fixture = self.sample()
                fixture["function_contracts"][0]["evidence"]["definition"]["path"] = name
                with self.assertRaises(ContractError):
                    build_functional_contracts(fixture)

    def test_loader_rejects_invalid_json_and_large_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "map.json"
            path.write_text(json.dumps(self.sample()), encoding="utf-8")
            self.assertEqual(load_source_map(path)["schema_version"], "rea-app-source-map/v1")
            with self.assertRaises(ContractError):
                load_source_map(path, max_bytes=10)
            path.write_bytes(b"{no")
            with self.assertRaises(ContractError):
                load_source_map(path)


if __name__ == "__main__":
    unittest.main()
