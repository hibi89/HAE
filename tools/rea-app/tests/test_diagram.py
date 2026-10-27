"""Real file-based Mermaid export from synthetic saved source-map JSON."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rea_app.diagram import DiagramError, load_source_map_for_diagram, render_architecture_mermaid


class DiagramTests(unittest.TestCase):
    def fixture(self):
        return {"schema_version": "rea-app-source-map/v1", "dependency_edges": [
            {"from_path": "src/main.ts", "to_path": "src/lib.ts", "kind": "import",
             "resolution": "internal", "evidence": {"path": "src/main.ts", "line": 1}},
            {"from_path": "src/lib.ts", "to_path": None, "kind": "import",
             "resolution": "external", "evidence": {"path": "src/lib.ts", "line": 2}},
        ]}

    def test_in_root_edges_only_and_stable_output(self):
        result = render_architecture_mermaid(self.fixture())
        self.assertEqual(result, render_architecture_mermaid(self.fixture()))
        self.assertEqual(result.count("-->|"), 1)
        self.assertIn('n0["src/lib.ts"]', result)
        self.assertIn('n1["src/main.ts"]', result)
        self.assertIn('n1 -->|"import @ 1"| n0', result)
        self.assertNotIn("node_modules", result)

    def test_unsafe_paths_and_evidence_rejected(self):
        for candidate in ('../secret.ts', 'C:/secret.ts', 'a/../../escape.ts', 'foo\\bar.ts'):
            with self.subTest(candidate=candidate):
                doc = self.fixture()
                doc["dependency_edges"][0]["from_path"] = candidate
                with self.assertRaises(DiagramError):
                    render_architecture_mermaid(doc)
        doc = self.fixture()
        doc["dependency_edges"][0]["evidence"]["line"] = 0
        with self.assertRaises(DiagramError):
            render_architecture_mermaid(doc)

    def test_empty_graph_is_valid(self):
        doc = self.fixture()
        doc["dependency_edges"] = []
        self.assertIn("No resolved", render_architecture_mermaid(doc))

    def test_escapes_mermaid_label_text(self):
        doc = self.fixture()
        doc["dependency_edges"][0]["from_path"] = 'src/weird"|.ts'
        doc["dependency_edges"][0]["evidence"]["path"] = 'src/weird"|.ts'
        out = render_architecture_mermaid(doc)
        self.assertIn("&quot;", out)
        self.assertIn("&#124;", out)

    def test_load_saved_report_and_bounded_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source-map.json"
            path.write_text(json.dumps(self.fixture()), encoding="utf-8")
            self.assertEqual(load_source_map_for_diagram(path), self.fixture())
            with self.assertRaises(DiagramError):
                load_source_map_for_diagram(path, max_bytes=5)
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(DiagramError):
                load_source_map_for_diagram(path)


if __name__ == "__main__":
    unittest.main()

class DiagramCliSmokeTests(unittest.TestCase):
    def test_real_diagram_cli_writes_viewable_mermaid_and_preserves_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source-map.json"
            target = root / "results"
            payload = {"schema_version": "rea-app-source-map/v1", "dependency_edges": [
                {"from_path": "src/main.ts", "to_path": "src/lib.ts", "kind": "import",
                 "resolution": "internal", "evidence": {"path": "src/main.ts", "line": 1}},
            ]}
            source.write_text(json.dumps(payload), encoding="utf-8")
            before = source.read_bytes()
            import os
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
            cmd = [sys.executable, "-m", "rea_app", "diagram", str(source), "--output-dir", str(target)]
            first = subprocess.run(cmd, cwd=Path(__file__).resolve().parents[1], env=environment,
                                   text=True, capture_output=True, check=False, timeout=10)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(sorted(p.name for p in target.iterdir()), ["architecture.md", "architecture.mmd"])
            mermaid = (target / "architecture.mmd").read_bytes()
            markdown = (target / "architecture.md").read_text(encoding="utf-8")
            self.assertIn(b'flowchart LR', mermaid)
            self.assertIn('```mermaid', markdown)
            self.assertEqual(source.read_bytes(), before)
            second = subprocess.run(cmd, cwd=Path(__file__).resolve().parents[1], env=environment,
                                    text=True, capture_output=True, check=False, timeout=10)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual((target / "architecture.mmd").read_bytes(), mermaid)
            source.write_text('{bad', encoding='utf-8')
            failed = subprocess.run(cmd, cwd=Path(__file__).resolve().parents[1], env=environment,
                                    text=True, capture_output=True, check=False, timeout=10)
            self.assertEqual(failed.returncode, 2)
            self.assertEqual((target / "architecture.mmd").read_bytes(), mermaid)
