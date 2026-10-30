import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile
from hae_doctor import diagnose, preflight_json


class OfflineDoctorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.app = self.root / "apps" / "ax-flow"
        self.app.mkdir(parents=True)
        self.env = {"LOCALAPPDATA": str(self.root / "local"), "HAE_ENGINE_BACKEND": "auto"}

    def bundle(self, *, entries=None):
        (self.app / "launch_integrated.py").write_text("# synthetic", encoding="utf-8")
        with zipfile.ZipFile(self.app / "hae-integrated.pyz", "w") as z:
            for name in entries or ("__main__.py", "axflow/web.py", "lightning_azent/__init__.py"):
                z.writestr(name, b"synthetic")

    def test_valid_integrated_bundle_never_executes_or_touches_data(self):
        self.bundle()
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        code, body = preflight_json(self.root, self.env, "integrated")
        result = json.loads(body)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "OFFLINE_BUNDLE_STATIC_OK")
        self.assertEqual(result["next_action"], "RUN_ISOLATED_VERIFY")
        self.assertFalse(result["customer_ready"])
        self.assertFalse(result["runtime_executed"])
        self.assertNotIn(str(self.root), body)
        self.assertEqual(before, sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*")))
        self.assertFalse((self.root / "local").exists())

    def test_missing_or_corrupt_integrated_bundle_fail_closed(self):
        self.assertEqual(diagnose(self.root, self.env, "integrated")["status"], "OFFLINE_BUNDLE_INVALID")
        self.bundle()
        (self.app / "hae-integrated.pyz").write_bytes(b"corrupt")
        self.assertEqual(preflight_json(self.root, self.env, "integrated")[0], 2)

    def test_missing_expected_engine_files_fail_closed(self):
        self.bundle(entries=("__main__.py", "axflow/web.py"))
        self.assertEqual(diagnose(self.root, self.env, "integrated")["status"], "OFFLINE_BUNDLE_INVALID")

    def test_unsafe_zip_member_or_crc_rejected(self):
        self.bundle(entries=("__main__.py", "axflow/web.py", "lightning_azent/__init__.py", "../bad"))
        self.assertEqual(preflight_json(self.root, self.env, "integrated")[0], 2)

    def test_legacy_data_detection_never_reads_or_migrates_data(self):
        data = self.root / "local" / "HAE"
        data.mkdir(parents=True)
        original = b"PRIVATE-DO-NOT-READ"
        (data / "state.sqlite").write_bytes(original)
        code, body = preflight_json(self.root, self.env, "preserved-legacy")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(body)["status"], "EXISTING_LEGACY_PRESERVED")
        self.assertEqual((data / "state.sqlite").read_bytes(), original)
        self.assertNotIn("PRIVATE", body)

    def test_data_root_symlink_refused_if_supported(self):
        real = self.root / "real"
        real.mkdir()
        link = self.root / "pointer"
        try:
            link.symlink_to(real, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("no symlink fixture privileges")
        env = dict(self.env, HAE_DATA_DIR=str(link))
        code, body = preflight_json(self.root, env, "legacy")
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(body)["status"], "UNSAFE_DATA_ROOT")
        self.assertNotIn(str(link), body)

    def test_legacy_only_is_explicitly_not_certified(self):
        code, body = preflight_json(self.root, self.env, "legacy")
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(body)["customer_ready"])
        self.assertEqual(json.loads(body)["release_gate"], "HOLD")


if __name__ == "__main__":
    unittest.main()
