import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'run_gate_r_evidence.py'
PASS_TEXT = '''SOURCE VERIFIED: 15/15 Git blobs match reviewed baseline\nPYTHON_ALL: PASS (exit 0)\nDEPENDENCY VERIFIED: @babel/parser@7.29.9\nNODE_PARSER: PASS (exit 0)\nSUMMARY: source=PASS, python=PASS, node=PASS\nRan 20 tests\nOK (skipped=1)\n'''

class TestEvidenceRunner(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        (self.repo / 'run_gate_r_evidence.py').write_bytes(SOURCE.read_bytes())
        self.results = self.root / 'results'
        subprocess.run(['git', 'init', '-q', '-b', 'REA_APP', str(self.repo)], check=True)
        (self.repo / 'README.md').write_text('fixture')
        subprocess.run(['git','-C',str(self.repo),'add','README.md'],check=True)
        subprocess.run(['git','-C',str(self.repo),'-c','user.name=QA Fixture','-c','user.email=qa@example.invalid','commit','-qm','fixture'],check=True)

    def execute(self,script, args=()):
        (self.repo / 'verify_gate_r.py').write_text(script)
        return subprocess.run([sys.executable,str(self.repo/'run_gate_r_evidence.py'),'--output-dir',str(self.results),*args],capture_output=True,text=True)

    def latest(self):
        folders = sorted(self.results.glob('gate-r-*'))
        self.assertTrue(folders)
        return json.loads((folders[-1]/'evidence.json').read_text())

    def test_pass_requires_provenance_and_all_markers(self):
        r=self.execute('print('+repr(PASS_TEXT)+')')
        self.assertEqual(r.returncode,0,r.stderr)
        v=self.latest();self.assertEqual(v['status'],'PASS')
        self.assertEqual(v['python_unittest_ran_counts'],[20]);self.assertEqual(v['python_unittest_skipped_counts'],[1])

    def test_missing_marker_fail_closed(self):
        r=self.execute('print("SOURCE VERIFIED: 15/15")')
        self.assertEqual(r.returncode,1)
        self.assertEqual(self.latest()['status'],'PARTIAL_OR_FAIL')

    def test_nonzero_verifier_exit_fail_closed(self):
        r=self.execute('print('+repr(PASS_TEXT)+')\nraise SystemExit(2)')
        self.assertEqual(r.returncode,1)
        self.assertEqual(self.latest()['verifier_exit_code'],2)

    def test_wrong_branch_rejected(self):
        r=self.execute('print('+repr(PASS_TEXT)+')',('--expected-branch','develop'))
        self.assertEqual(r.returncode,1)
        self.assertEqual(self.latest()['status'],'PARTIAL_OR_FAIL')

    def test_inside_checkout_output_rejected(self):
        (self.repo/'verify_gate_r.py').write_text('print("ok")')
        r=subprocess.run([sys.executable,str(self.repo/'run_gate_r_evidence.py'),'--output-dir',str(self.repo/'logs')],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0)
        self.assertFalse((self.repo/'logs').exists())

    def test_two_runs_create_distinct_folders(self):
        for _ in range(2):
            r=self.execute('print('+repr(PASS_TEXT)+')');self.assertEqual(r.returncode,0)
        self.assertEqual(len(list(self.results.glob('gate-r-*'))),2)

if __name__=='__main__':
    unittest.main()
