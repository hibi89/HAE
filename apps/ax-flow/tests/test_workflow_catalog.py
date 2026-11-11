"""Local owner-controlled synthetic recipe persistence and fail-closed reload."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
import sqlite3
import tempfile
import unittest

from axflow.workflow_catalog import (
    WorkflowCatalogError, initialize_workflow_catalog,
    list_synthetic_workflows, save_synthetic_workflow, load_synthetic_workflow,
)


class SyntheticWorkflowCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hae-recipe-catalog-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "input"
        self.inputs.mkdir()
        self.csv = self.inputs / "data.csv"
        self.csv.write_bytes(b"id,amount\n1,50\n2,300\n")
        self.sha = hashlib.sha256(self.csv.read_bytes()).hexdigest()
        self.catalog = self.root / "recipes.sqlite"
        self.task = "Import this CSV where amount > 100 into SQLite"

    def init(self):
        return initialize_workflow_catalog(
            self.catalog, synthetic=True, acknowledge_new_file=True)

    def save(self, *, task=None, sha=None, ack=True):
        return save_synthetic_workflow(
            self.catalog, self.inputs, self.task if task is None else task,
            "data.csv", self.sha if sha is None else sha,
            synthetic=True, approve_save=ack,
        )

    def test_explicit_init_and_restart_reload_no_exec(self):
        self.assertEqual(self.init()["recipe_count"], 0)
        original = self.csv.read_bytes()
        receipt = self.save()
        self.assertEqual(receipt["status"], "SAVED")
        self.assertTrue(receipt["needs_new_preview"])
        self.assertEqual(self.save()["status"], "ALREADY_SAVED")
        listings = list_synthetic_workflows(self.catalog, synthetic=True)
        self.assertEqual(listings["recipe_count"], 1)
        self.assertNotIn("data.csv", str(listings))
        self.assertNotIn(self.task, str(listings))
        loaded = load_synthetic_workflow(
            self.catalog, receipt["recipe_id"], self.inputs, synthetic=True)
        self.assertEqual(loaded["task"], self.task)
        self.assertEqual(loaded["csv_path"], "data.csv")
        self.assertFalse(loaded["write_approved"])
        self.assertTrue(loaded["needs_new_preview"])
        self.assertEqual(original, self.csv.read_bytes())
        self.assertFalse((self.root / "runtime.sqlite").exists())

    def test_save_without_owner_ack_refused_no_file_write(self):
        self.init()
        before = self.catalog.read_bytes()
        with self.assertRaises(WorkflowCatalogError):
            self.save(ack=False)
        self.assertEqual(self.catalog.read_bytes(), before)

    def test_invalid_source_sha_refused(self):
        self.init()
        with self.assertRaises(WorkflowCatalogError):
            self.save(sha="0"*64)
        self.assertEqual(list_synthetic_workflows(self.catalog, synthetic=True)["recipe_count"], 0)

    def test_mutated_csv_refused_when_loading(self):
        self.init()
        saved = self.save()
        self.csv.write_bytes(b"id,amount\n1,999\n")
        with self.assertRaises(WorkflowCatalogError):
            load_synthetic_workflow(self.catalog, saved["recipe_id"], self.inputs,
                                    synthetic=True)

    def test_unsupported_external_intent_never_saved(self):
        self.init()
        with self.assertRaises(WorkflowCatalogError):
            self.save(task="Send Gmail and transfer this CSV now")
        self.assertEqual(list_synthetic_workflows(self.catalog, synthetic=True)["recipe_count"], 0)

    def test_rejects_symlink_alias_and_corrupt_catalog(self):
        self.init()
        link = self.root / "alias.sqlite"
        try:
            link.symlink_to(self.catalog)
        except (OSError, NotImplementedError):
            self.skipTest("symlink unavailable")
        with self.assertRaises(WorkflowCatalogError):
            list_synthetic_workflows(link, synthetic=True)
        self.catalog.write_bytes(b"corrupted")
        with self.assertRaises(WorkflowCatalogError):
            list_synthetic_workflows(self.catalog, synthetic=True)

    def test_init_rejects_existing_file(self):
        self.catalog.write_bytes(b"KEEP")
        with self.assertRaises(WorkflowCatalogError):
            self.init()
        self.assertEqual(self.catalog.read_bytes(), b"KEEP")

    def test_unsupported_version_refused_without_migration(self):
        self.init()
        with sqlite3.connect(self.catalog) as db:
            db.execute("PRAGMA user_version=99")
        with self.assertRaises(WorkflowCatalogError):
            self.save()

    def test_cli_init_save_list_and_load_are_safe(self):
        def run(*args):
            return subprocess.run([sys.executable, "-m", "axflow.workflow_catalog_cli",
                *args, "--synthetic"], capture_output=True, text=True, timeout=12)
        self.assertEqual(run("init", "--catalog", str(self.catalog),
                             "--ack-new-file").returncode, 0)
        saved = run("save", "--catalog", str(self.catalog), "--input-root", str(self.inputs),
                    "--task", self.task, "--csv", "data.csv", "--source-sha256", self.sha,
                    "--ack-save")
        self.assertEqual(saved.returncode, 0, saved.stderr)
        recipe = json.loads(saved.stdout)
        self.assertEqual(recipe["status"], "SAVED")
        listed = run("list", "--catalog", str(self.catalog))
        self.assertEqual(json.loads(listed.stdout)["recipe_count"], 1)
        loaded = run("load", "--catalog", str(self.catalog), "--input-root", str(self.inputs),
                     "--recipe-id", recipe["recipe_id"])
        self.assertEqual(loaded.returncode, 0, loaded.stderr)
        self.assertFalse(json.loads(loaded.stdout)["write_approved"])
        self.assertTrue(json.loads(loaded.stdout)["needs_new_preview"])

    def test_cli_missing_synthetic_flag_refuses_without_leaking(self):
        proc = subprocess.run([sys.executable, "-m", "axflow.workflow_catalog_cli",
            "init", "--catalog", str(self.catalog), "--ack-new-file"],
            capture_output=True, text=True, timeout=12)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(self.catalog.exists())
        self.assertNotIn(str(self.catalog), proc.stderr)

    def test_missing_owner_flag_creates_nothing(self):
        with self.assertRaises(WorkflowCatalogError):
            initialize_workflow_catalog(self.catalog, synthetic=True)
        self.assertFalse(self.catalog.exists())


if __name__ == "__main__":
    unittest.main()
