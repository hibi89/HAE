"""Cross-platform dispatch tests: no real customer data or external services."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
import json
import io
from contextlib import redirect_stdout
from unittest.mock import patch


APP = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("hae_start", APP / "start_hae.py")
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class HaeStartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hae-route-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / "apps" / "ax-flow"
        self.app.mkdir(parents=True)
        self.env = {"LOCALAPPDATA": str(self.root / "local"), "HAE_NO_BROWSER": "1", "HAE_PORT": "18473"}

    def ship(self):
        (self.app / "launch_integrated.py").write_text("# verified synthetic launcher\n", encoding="utf-8")
        (self.app / "hae-integrated.pyz").write_bytes(b"not-a-real-archive")

    def select(self, env=None):
        return launcher.launch_command(self.root, env or self.env, sys.executable)

    def test_fresh_install_prefers_real_la_distribution_over_native_engine(self):
        self.ship()
        cmd, env, selected = self.select()
        self.assertEqual(selected, "integrated")
        self.assertEqual(cmd[0], sys.executable)
        self.assertEqual(Path(cmd[1]).resolve(), (self.app / "launch_integrated.py").resolve())
        self.assertEqual(cmd[2:], ["--no-browser", "--port", "18473"])
        self.assertEqual(env.get("LOCALAPPDATA"), self.env["LOCALAPPDATA"])

    def test_legacy_sqlite_is_not_silently_replaced_by_new_ledger(self):
        self.ship()
        data = self.root / "local" / "HAE"
        data.mkdir(parents=True)
        (data / "state.sqlite").write_bytes(b"EXISTING-USER-DATA")
        cmd, _, selected = self.select()
        self.assertEqual(selected, "preserved-legacy")
        self.assertIn("axflow.desktop_launcher", cmd)
        self.assertEqual((data / "state.sqlite").read_bytes(), b"EXISTING-USER-DATA")
        (data / "runtime.db").write_bytes(b"NEW-ENGINE-USER-DATA")
        self.assertEqual(self.select()[2], "preserved-legacy")
        self.assertEqual(self.select(dict(self.env, HAE_ENGINE_BACKEND="lightning-azent"))[2], "integrated")

    def test_explicit_modes_preserve_contract(self):
        self.ship()
        explicit_native = dict(self.env, HAE_ENGINE_BACKEND="axflow")
        explicit_la = dict(self.env, HAE_ENGINE_BACKEND="lightning-azent")
        self.assertEqual(self.select(explicit_native)[2], "legacy")
        self.assertEqual(self.select(explicit_la)[2], "integrated")

    def test_explicit_lightning_without_bundle_fails_closed(self):
        with self.assertRaisesRegex(launcher.StartError, "explicitly required"):
            self.select(dict(self.env, HAE_ENGINE_BACKEND="lightning-azent"))

    def test_missing_bundle_retains_native_fallback(self):
        cmd, env, selected = self.select()
        self.assertEqual(selected, "legacy")
        self.assertEqual(cmd[1:3], ["-m", "axflow.desktop_launcher"])
        self.assertEqual(Path(env["PYTHONPATH"].split(os.pathsep, 1)[0]).resolve(), self.app.resolve())

    def test_incomplete_bundle_fails_closed(self):
        (self.app / "hae-integrated.pyz").write_bytes(b"partial")
        with self.assertRaisesRegex(launcher.StartError, "incomplete"):
            self.select()

    def test_symlinked_bundle_fails_closed(self):
        target = self.root / "other.pyz"
        target.write_bytes(b"external")
        (self.app / "launch_integrated.py").write_text("# launcher\n")
        try:
            (self.app / "hae-integrated.pyz").symlink_to(target)
        except (NotImplementedError, OSError):
            self.skipTest("symlink unavailable")
        with self.assertRaisesRegex(launcher.StartError, "unsafe"):
            self.select()

    def test_bad_env_config_is_rejected_before_launch(self):
        self.ship()
        for value in ("0", "65536", "oops", "1 2", "-1"):
            with self.subTest(value=value), self.assertRaisesRegex(launcher.StartError, "HAE_PORT"):
                self.select(dict(self.env, HAE_PORT=value))
        with self.assertRaisesRegex(launcher.StartError, "HAE_ENGINE_BACKEND"):
            self.select(dict(self.env, HAE_ENGINE_BACKEND="remote"))

    def test_verify_argument_requires_integrated_bundle(self):
        with patch.object(launcher, "__file__", str(self.app / "start_hae.py")), patch.dict(os.environ, self.env, clear=True):
            self.assertEqual(launcher.main(["--verify"]), 2)

    def test_verify_uses_integrated_bundle_even_with_legacy_ledger(self):
        self.ship()
        data = self.root / "local" / "HAE"
        data.mkdir(parents=True)
        (data / "state.sqlite").write_bytes(b"EXISTING-USER-DATA")
        captured = []
        with patch.object(launcher, "__file__", str(self.app / "start_hae.py")), patch.dict(os.environ, self.env, clear=True), patch.object(launcher.subprocess, "call", side_effect=lambda cmd, **kwargs: captured.append(cmd) or 0):
            self.assertEqual(launcher.main(["--verify"]), 0)
        self.assertEqual(captured[0][-1], "--verify")
        self.assertEqual(Path(captured[0][1]).name, "launch_integrated.py")
        self.assertEqual((data / "state.sqlite").read_bytes(), b"EXISTING-USER-DATA")

    def test_verify_ignores_user_port_and_no_browser_flags(self):
        self.ship()
        commands = []
        with patch.object(launcher, "__file__", str(self.app / "start_hae.py")), patch.dict(os.environ, self.env, clear=True), patch.object(launcher.subprocess, "call", side_effect=lambda cmd, **kwargs: commands.append(cmd) or 0):
            self.assertEqual(launcher.main(["--verify"]), 0)
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0][0], sys.executable)
        self.assertEqual(Path(commands[0][1]).resolve(), (self.app / "launch_integrated.py").resolve())
        self.assertEqual(commands[0][2:], ["--verify"])

    def test_doctor_cli_checks_real_zip_without_launching_server(self):
        (self.app / "launch_integrated.py").write_text("# launcher\n", encoding="utf-8")
        with zipfile.ZipFile(self.app / "hae-integrated.pyz", "w") as archive:
            for name in ("__main__.py", "axflow/web.py", "lightning_azent/__init__.py"):
                archive.writestr(name, b"synthetic")
        captured = io.StringIO()
        with (patch.object(launcher, "__file__", str(self.app / "start_hae.py")),
              patch.dict(os.environ, self.env, clear=True),
              patch.object(launcher.subprocess, "call",
                           side_effect=AssertionError("doctor must never run backend")),
              redirect_stdout(captured)):
            self.assertEqual(launcher.main(["--doctor"]), 0)
        result = json.loads(captured.getvalue())
        self.assertEqual(result["status"], "OFFLINE_BUNDLE_STATIC_OK")
        self.assertFalse(result["runtime_executed"])
        self.assertEqual(result["release_gate"], "HOLD")
        self.assertFalse((self.root / "local").exists())

    def test_unknown_arguments_rejected(self):
        with patch.object(launcher, "__file__", str(self.app / "start_hae.py")), patch.dict(os.environ, self.env, clear=True):
            self.assertEqual(launcher.main(["--unknown"]), 2)

    def test_dispatch_invokes_selected_script_without_user_database_write(self):
        self.ship()
        ran = self.app / "launch_integrated.py"
        ran.write_text("import sys; print('ROUTE_TO_LA_OK'); print(' '.join(sys.argv[1:]))\n")
        cmd, env, _ = self.select()
        completed = subprocess.run(cmd, cwd=self.root, env=env, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("ROUTE_TO_LA_OK", completed.stdout)
        self.assertIn("--no-browser --port 18473", completed.stdout)
        self.assertFalse((self.root / "local").exists())


if __name__ == "__main__":
    unittest.main()
