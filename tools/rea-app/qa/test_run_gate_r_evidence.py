"""Synthetic but executable Gate R evidence runner provenance tests."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "run_gate_r_evidence.py"
PASS_TEXT = (
    "SOURCE VERIFIED: 16/16 Git blobs match reviewed baseline\n"
    "PYTHON_ALL: PASS (exit 0)\n"
    "DEPENDENCY VERIFIED: @babel/parser@7.29.9\n"
    "NODE_PARSER: PASS (exit 0)\n"
    "SUMMARY: source=PASS, python=PASS, node=PASS\n"
    "Ran 20 tests\n"
    "OK (skipped=1)\n"
)


def blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


class TestEvidenceRunner(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="rea-p34-gate-evidence-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.out = self.root / "results"
        subprocess.run(["git", "init", "-q", "-b", "REA_APP", str(self.repo)], check=True)
        (self.repo / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
        (self.repo / "README.md").write_text("synthetic fixture\n", encoding="utf-8")
        self.commit("init fixture")

    def commit(self, label: str) -> None:
        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        subprocess.run([
            "git", "-C", str(self.repo), "-c", "user.name=QA Fixture",
            "-c", "user.email=qa@example.invalid", "commit", "--allow-empty", "-qm", label,
        ], check=True)

    def configure(self, verifier_script: str) -> None:
        data = verifier_script.encode("utf-8")
        (self.repo / "verify_gate_r.py").write_bytes(data)
        original = SOURCE.read_text(encoding="utf-8")
        self.assertIn('EXPECTED_VERIFIER_BLOB = "65f9534fd0669e545aa3acf0b78781ccb324f2d8"', original)
        custom = original.replace(
            'EXPECTED_VERIFIER_BLOB = "65f9534fd0669e545aa3acf0b78781ccb324f2d8"',
            'EXPECTED_VERIFIER_BLOB = "' + blob_id(data) + '"',
        )
        (self.repo / "run_gate_r_evidence.py").write_text(custom, encoding="utf-8")
        self.commit("authorize fixture verifier and runner")

    def run_runner(self, *extra: str):
        return subprocess.run([
            sys.executable, str(self.repo / "run_gate_r_evidence.py"),
            "--output-dir", str(self.out), *extra,
        ], capture_output=True, text=True, timeout=35)

    def execute(self, script: str, *extra: str):
        self.configure(script)
        return self.run_runner(*extra)

    def latest(self):
        folders = sorted(self.out.glob("gate-r-*"))
        self.assertTrue(folders)
        return json.loads((folders[-1] / "evidence.json").read_text(encoding="utf-8"))

    @staticmethod
    def success_script():
        return "print(" + repr(PASS_TEXT) + ")\n"

    def test_clean_verified_fixture_passes(self):
        r = self.execute(self.success_script())
        self.assertEqual(r.returncode, 0, r.stderr)
        x = self.latest()
        self.assertEqual(x["status"], "PASS")
        self.assertTrue(x["tool_worktree_clean"])
        self.assertTrue(x["reviewed_verifier_blob_matches"])
        self.assertEqual(x["python_unittest_ran_counts"], [20])
        self.assertEqual(x["python_unittest_skipped_counts"], [1])

    def test_missing_marker_fail_closed(self):
        r = self.execute('print("SOURCE VERIFIED: 16/16 Git blobs match baseline")\n')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.latest()["status"], "PARTIAL_OR_FAIL")

    def test_invalid_output_suffix_cannot_forge_success(self):
        r = self.execute(self.success_script().replace("PYTHON_ALL: PASS (exit 0)", "PYTHON_ALL: PASS (exit 2)"))
        self.assertEqual(r.returncode, 1)
        self.assertFalse(self.latest()["required_markers"]["python"])

    def test_source_counter_prefix_cannot_forge_success(self):
        r = self.execute(self.success_script().replace("16/16 Git blobs", "16/160 Git blobs"))
        self.assertEqual(r.returncode, 1)
        self.assertFalse(self.latest()["required_markers"]["source"])

    def test_nonzero_verifier_exit_fail_closed(self):
        r = self.execute(self.success_script() + "raise SystemExit(2)\n")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.latest()["verifier_exit_code"], 2)

    def test_wrong_branch_rejected(self):
        r = self.execute(self.success_script(), "--expected-branch", "develop")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.latest()["status"], "PARTIAL_OR_FAIL")

    def test_uncommitted_verifier_change_rejected(self):
        self.configure(self.success_script())
        with (self.repo / "verify_gate_r.py").open("a", encoding="utf-8") as handle:
            handle.write("# changed after provenance stamp\n")
        r = self.run_runner()
        self.assertEqual(r.returncode, 1)
        x = self.latest()
        self.assertFalse(x["tool_worktree_clean"])
        self.assertFalse(x["reviewed_verifier_blob_matches"])

    def test_clean_but_unreviewed_verifier_blob_rejected(self):
        self.configure(self.success_script())
        (self.repo / "verify_gate_r.py").write_text(self.success_script() + "# stealth edit\n")
        self.commit("change verifier without repinning runner")
        r = self.run_runner()
        self.assertEqual(r.returncode, 1)
        x = self.latest()
        self.assertTrue(x["tool_worktree_clean"])
        self.assertFalse(x["reviewed_verifier_blob_matches"])

    def test_untracked_executable_in_tool_checkout_rejected(self):
        self.configure(self.success_script())
        (self.repo / "surprise.py").write_text("print('unreviewed')\n")
        r = self.run_runner()
        self.assertEqual(r.returncode, 1)
        self.assertFalse(self.latest()["tool_worktree_clean"])

    def test_inside_checkout_output_rejected(self):
        self.configure(self.success_script())
        r = subprocess.run([
            sys.executable, str(self.repo / "run_gate_r_evidence.py"),
            "--output-dir", str(self.repo / "logs"),
        ], capture_output=True, text=True, timeout=35)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.repo / "logs").exists())

    def test_two_runs_create_distinct_folders(self):
        self.configure(self.success_script())
        for _ in range(2):
            self.assertEqual(self.run_runner().returncode, 0)
        self.assertEqual(len(list(self.out.glob("gate-r-*"))), 2)


if __name__ == "__main__":
    unittest.main()
