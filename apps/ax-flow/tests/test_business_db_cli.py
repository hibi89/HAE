"""HAE synthetic-only local business SQLite CLI smoke/security acceptance."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


class BusinessDbCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hae-business-cli-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "business.sqlite"
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("CREATE TABLE csv_records(run_id TEXT, amount INTEGER, sensitive TEXT)")
            con.execute("INSERT INTO csv_records VALUES('synthetic1',123,'PRIVATE_CLIENT_831')")

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "axflow.business_db_cli", *map(str, args)],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=20
        )

    def test_inspect_no_private_data(self):
        r = self.run_cli("inspect", "--source", self.db, "--synthetic")
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(r.stdout)["result"]
        self.assertEqual(report["table_count"], 1)
        self.assertNotIn("PRIVATE_CLIENT_831", r.stdout + r.stderr)
        self.assertNotIn(str(self.db), r.stdout + r.stderr)

    def test_backup_restore_owner_ack_and_pinned_sha(self):
        backup, restored = self.root / "backup.sqlite", self.root / "restored.sqlite"
        result = self.run_cli("backup", "--source", self.db, "--destination", backup,
                              "--synthetic", "--ack-new-file")
        self.assertEqual(result.returncode, 0, result.stderr)
        digest = json.loads(result.stdout)["result"]["artifact_sha256"]
        self.assertEqual(digest, hashlib.sha256(backup.read_bytes()).hexdigest())
        result = self.run_cli("restore", "--source", backup, "--destination", restored,
                              "--synthetic", "--ack-new-file", "--expected-sha256", digest)
        self.assertEqual(result.returncode, 0, result.stderr)
        with closing(sqlite3.connect(restored)) as con:
            self.assertEqual(con.execute("SELECT sensitive FROM csv_records").fetchone()[0],
                             "PRIVATE_CLIENT_831")

    def test_no_synthetic_flag_refuses_write(self):
        path = self.root / "not-approved.sqlite"
        result = self.run_cli("backup", "--source", self.db, "--destination", path,
                              "--ack-new-file")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(path.exists())

    def test_no_explicit_write_ack_refuses_write(self):
        path = self.root / "not-approved.sqlite"
        result = self.run_cli("backup", "--source", self.db, "--destination", path,
                              "--synthetic")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(path.exists())

    def test_wrong_restore_sha_refuses_write(self):
        backup, restored = self.root / "backup.sqlite", self.root / "blocked.sqlite"
        proof = self.run_cli("backup", "--source", self.db, "--destination", backup,
                             "--synthetic", "--ack-new-file")
        self.assertEqual(proof.returncode, 0, proof.stderr)
        result = self.run_cli("restore", "--source", backup, "--destination", restored,
                              "--synthetic", "--ack-new-file", "--expected-sha256", "0"*64)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(restored.exists())

    def test_argparse_never_echoes_secret_argument(self):
        res = self.run_cli("inspect", "--source", self.db, "--synthetic",
                           "--token=PRIVATE_SECRET_921")
        self.assertEqual(res.returncode, 2)
        self.assertEqual(res.stdout, "")
        self.assertNotIn("PRIVATE_SECRET_921", res.stderr)

    def test_existing_target_preserved(self):
        target = self.root / "existing.sqlite"
        target.write_bytes(b"UNMODIFIED_OWNER_FILE")
        r = self.run_cli("backup", "--source", self.db, "--destination", target,
                         "--synthetic", "--ack-new-file")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(target.read_bytes(), b"UNMODIFIED_OWNER_FILE")

    def test_inspection_does_not_accept_write_flags(self):
        r = self.run_cli("inspect", "--source", self.db, "--synthetic", "--ack-new-file")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")


if __name__ == "__main__":
    unittest.main()
