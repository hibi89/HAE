from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from unittest.mock import patch

from axflow import desktop_launcher as launcher


class DesktopLauncherTests(unittest.TestCase):
    def test_data_root_is_created_without_business_or_runtime_databases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "local" / "HAE"
            with patch.dict(os.environ, {}, clear=True):
                actual = launcher._data_root(str(root))
            self.assertEqual(actual, root.resolve())
            self.assertTrue((actual / "input").is_dir())
            self.assertFalse((actual / "state.sqlite").exists())
            self.assertFalse((actual / "business.sqlite").exists())

    def test_missing_lightning_defaults_to_named_native_mode(self):
        with patch.object(launcher.importlib, "import_module", side_effect=ImportError):
            backend, warning = launcher._choose_backend(Path("/fixture"), "auto")
        self.assertEqual(backend, "axflow")
        self.assertIn("LA/SOVIA integration is unavailable", warning)

    def test_required_missing_lightning_fails_closed(self):
        with patch.object(launcher.importlib, "import_module", side_effect=ImportError):
            with self.assertRaisesRegex(launcher.LauncherError, "not ready"):
                launcher._choose_backend(Path("/fixture"), "lightning-azent")

    def test_incompatible_lightning_contract_does_not_claim_integrated_mode(self):
        class FakeExecutor:
            @staticmethod
            def capabilities():
                return {"api_version": "azent.api.v0", "scope": "external", "legacy_ir_version": "axflow.ir.v0"}

        class FakeModule:
            LAExecutor = FakeExecutor

        with patch.object(launcher.importlib, "import_module", return_value=FakeModule):
            backend, warning = launcher._choose_backend(Path("/fixture"), "auto")
        self.assertEqual(backend, "axflow")
        self.assertIn("contract is incompatible", warning)

    def test_instance_lock_prevents_duplicate_and_releases_after_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "launcher.lock"
            with launcher._instance_lock(path) as first:
                self.assertTrue(first)
                with launcher._instance_lock(path) as second:
                    self.assertFalse(second)
            with launcher._instance_lock(path) as restarted:
                self.assertTrue(restarted)

    def test_port_parser_rejects_out_of_range_port(self):
        with self.assertRaises(SystemExit):
            launcher._parse_args(["--port", "65536"])

    def test_sovia_root_requires_the_supported_reconcile_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "SOVIA"
            candidate.mkdir()
            self.assertIsNone(launcher._optional_sovia_root(root))
            (candidate / "sovia_la_observation_reconcile.py").write_text("# synthetic fixture\n", encoding="utf-8")
            self.assertEqual(launcher._optional_sovia_root(root), candidate.resolve())

    def test_duplicate_instance_reuses_live_server_without_opening_another_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "local"
            with launcher._instance_lock(data / "launcher.lock") as first:
                self.assertTrue(first)
                with patch.object(launcher, "_hae_is_ready", return_value=True), \
                     patch.object(launcher.webbrowser, "open") as open_browser:
                    self.assertEqual(launcher.main(["--data-dir", str(data), "--backend", "axflow", "--no-browser"]), 0)
                    open_browser.assert_not_called()

    def test_port_conflict_is_reported_without_creating_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "local"
            output = StringIO()
            with patch.object(launcher, "_hae_is_ready", return_value=False), \
                 patch("axflow.web.create_server", side_effect=OSError("synthetic bind refusal")), \
                 redirect_stderr(output):
                result = launcher.main(["--data-dir", str(data), "--backend", "axflow", "--no-browser"])
            self.assertEqual(result, 2)
            self.assertIn("port is already in use", output.getvalue())
            self.assertFalse((data / "business.sqlite").exists())
            self.assertFalse((data / "state.sqlite").exists())


if __name__ == "__main__":
    unittest.main()
