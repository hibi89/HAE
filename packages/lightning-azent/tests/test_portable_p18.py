"""P18 isolated zipapp, detached checksum and real CLI synthetic tests."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from sqlite_test_utils import sqlite_connection

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from build_portable_p18 import NAME, package_bytes, publish_new
from verify_portable_p18 import PortableError, verify

FIXTURE = REPO / "docs" / "lightning-azent" / "fixtures" / "csv-filter-import.json"


class PortableP18Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="la-portable-p18-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.archive = self.root / NAME

    def build(self):
        result = publish_new(self.archive)
        self.assertEqual("LA_SYNTHETIC_ZIPAPP_BUILT_UNSIGNED", result["status"])
        return result

    def cli(self, *args, expected=0):
        run = subprocess.run([sys.executable, "-I", "-B", str(self.archive),
                              *[str(x) for x in args]],
                             cwd=self.root, text=True, capture_output=True, timeout=35)
        self.assertEqual(expected, run.returncode, run.stderr + run.stdout)
        return run

    def test_byte_reproducibility_and_inventory(self):
        first = package_bytes()
        second = package_bytes()
        self.assertEqual(first, second)
        self.build()
        self.assertEqual(first, self.archive.read_bytes())
        self.assertEqual(11, verify(self.archive)["file_count"])
        self.assertFalse(verify(self.archive)["release_approved"])
        with ZipFile(self.archive) as z:
            self.assertNotIn(".env", " ".join(z.namelist()))
            self.assertFalse(any(name.endswith((".db", ".sqlite", ".csv"))
                                 for name in z.namelist()))
            self.assertEqual("la.zipapp.synthetic.p18.v1",
                             json.loads(z.read("LA_MANIFEST.json"))["schema_version"])

    def test_actual_clean_zipapp_no_network_cli(self):
        self.build()
        self.assertTrue(self.cli("--version").stdout.strip())
        caps = json.loads(self.cli("capabilities").stdout)
        self.assertEqual("synthetic-local-only", caps["scope"])
        self.assertEqual([], caps["external_connectors"])
        self.assertEqual("azent.api.v0", caps["api_version"])

    def test_real_zipapp_plan_preflight_readonly(self):
        self.build()
        before = FIXTURE.read_bytes()
        plan = json.loads(self.cli("preflight", FIXTURE).stdout)
        self.assertFalse(plan["executes_workflow"])
        self.assertTrue(plan["requires_write_approval"])
        self.assertEqual(before, FIXTURE.read_bytes())
        self.assertFalse(list(self.root.glob("*.sqlite")))

    def test_detached_checksum_and_existing_path_preserved(self):
        result = self.build()
        attached = self.archive.with_name(NAME + ".sha256")
        self.assertEqual(result["sha256"], verify(self.archive, attached)["sha256"])
        before = self.archive.read_bytes()
        with self.assertRaises(ValueError):
            publish_new(self.archive)
        self.assertEqual(before, self.archive.read_bytes())

    def test_integrity_fails_if_detached_sha_forged(self):
        self.build()
        digest = self.archive.with_name(NAME + ".sha256")
        digest.write_text("0" * 64 + "  " + NAME + "\n", encoding="ascii")
        with self.assertRaisesRegex(PortableError, "CHECKSUM_MISMATCH"):
            verify(self.archive, digest)

    def test_archive_extra_member_rejected(self):
        self.build()
        with ZipFile(self.archive, "a", compression=ZIP_STORED) as z:
            z.writestr("unexpected.sh", "curl bad.example")
        with self.assertRaisesRegex(PortableError, "INVENTORY"):
            verify(self.archive)

    def test_changed_member_refused_without_manifest_change(self):
        self.build()
        changed = self.root / "changed.pyz"
        with ZipFile(self.archive) as original, ZipFile(changed, "w",
                                                         compression=ZIP_STORED) as output:
            for info in original.infolist():
                raw = original.read(info.filename)
                if info.filename == "lightning_azent/hae_bridge.py":
                    raw += b"\n# changed\n"
                output.writestr(info, raw)
        with self.assertRaisesRegex(PortableError, "TAMPERED"):
            verify(changed)

    def test_unapproved_customer_run_never_creates_database(self):
        self.build()
        plan = self.root / "plan.json"
        plan.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
        state = self.root / "state.sqlite"
        business = self.root / "business.sqlite"
        denied = self.cli("run", plan, "--state", state, "--data", business,
                          "--run-id", "SyntheticP18", "--synthetic", expected=2)
        self.assertFalse(state.exists())
        self.assertFalse(business.exists())


if __name__ == "__main__":
    unittest.main()
