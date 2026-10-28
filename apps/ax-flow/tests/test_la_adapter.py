"""Synthetic-only acceptance for HAE's explicit Lightning Azent adapter."""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.request import Request, urlopen

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))
LA_PACKAGE = REPO_ROOT / "packages" / "lightning-azent"
if LA_PACKAGE.is_dir():
    sys.path.insert(0, str(LA_PACKAGE))

from axflow.engine import Engine
from axflow.planner import plan_request
from axflow.web import create_server
from axflow.la_adapter import BackendUnavailable, inspect_backend


class LightningAzentAdapterTests(unittest.TestCase):
    def test_backend_version_mismatch_fails_closed(self):
        plan = plan_request("Import this CSV into local SQLite", "contacts.csv")

        class IncompatibleExecutor:
            @staticmethod
            def capabilities():
                return {"api_version": "azent.api.v9", "legacy_ir_version": "axflow.ir.v0",
                        "implemented_operations": [step["op"] for step in plan["steps"]],
                        "scope": "synthetic-local-only"}

            @staticmethod
            def preflight(_plan):
                return {"runtime_version": "axflow.ir.v0"}

        fake_package = SimpleNamespace(__version__="9.0", LAExecutor=IncompatibleExecutor)
        with patch("axflow.la_adapter.importlib.import_module", return_value=fake_package):
            with self.assertRaisesRegex(BackendUnavailable, "incompatible"):
                inspect_backend(plan)

    def test_missing_package_fails_closed(self):
        plan = plan_request("Import this CSV into local SQLite", "contacts.csv")
        with patch("axflow.la_adapter.importlib.import_module", side_effect=ImportError("synthetic missing package")):
            with self.assertRaisesRegex(BackendUnavailable, "unavailable"):
                inspect_backend(plan)

    @unittest.skipUnless(LA_PACKAGE.is_dir(), "Lightning Azent sibling package is not present in this checkout")
    def test_http_flow_uses_real_lightning_backend_and_matches_axflow(self):
        from axflow.engine import MAX_CSV_BYTES
        self.assertEqual(MAX_CSV_BYTES, 256 * 1024)
        with tempfile.TemporaryDirectory(prefix="hae-la-adapter-") as folder:
            root = Path(folder)
            inputs = root / "input"
            inputs.mkdir()
            contacts = b"id,name\n11,Alice\n12,Bob\n"
            sales = b"amount,id\n120,11\n80,12\n"
            (inputs / "contacts.csv").write_bytes(contacts)
            (inputs / "sales.csv").write_bytes(sales)
            state, business = root / "la-state.db", root / "la-business.db"
            server = create_server(
                inputs, state, business, port=0, engine_backend="lightning-azent",
            )
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
            thread.start()
            self.addCleanup(server.server_close)
            self.addCleanup(thread.join, 3)
            self.addCleanup(server.shutdown)
            origin = f"http://127.0.0.1:{server.server_port}"

            def post_json(route: str, payload: dict):
                request = Request(
                    origin + route, data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "Origin": origin}, method="POST",
                )
                with urlopen(request, timeout=5) as response:
                    return response.status, json.loads(response.read().decode("utf-8"))

            flows = [
                ("Import this CSV into local SQLite", "contacts.csv", True),
                ("이 CSV에서 amount가 100 이상일 때만 로컬 SQLite에 저장해줘", "sales.csv", True),
                ("이 CSV에서 id가 11인 행을 찾아줘", "contacts.csv", False),
            ]
            outcomes = []
            self.assertFalse(state.exists())
            self.assertFalse(business.exists())
            for index, (task, csv_path, approved) in enumerate(flows):
                status, preview = post_json("/api/preview", {"task": task, "csv_path": csv_path})
                self.assertEqual(status, 200, preview)
                self.assertEqual(preview["engine_backend"]["name"], "Lightning Azent")
                self.assertEqual(preview["engine_backend"]["api_version"], "azent.api.v0")
                self.assertEqual(preview["engine_backend"]["preflight"]["executes_workflow"], False)

                plan = preview["plan"]
                baseline = Engine(root / f"base-state-{index}.db", root / f"base-business-{index}.db",
                                  input_root=inputs).execute(
                    plan, f"BaseRun{index}", approve_writes=approved,
                )
                status, outcome = post_json("/api/run", {
                    "task": task, "csv_path": csv_path, "preview_id": preview["preview_id"],
                    "approve_writes": approved,
                })
                self.assertEqual(status, 200, outcome)
                self.assertEqual(outcome["status"]["status"], "completed")
                self.assertEqual(outcome["result"], baseline)
                self.assertEqual(outcome["backend"]["name"], "Lightning Azent")
                self.assertIn("events", outcome["audit"])
                self.assertNotIn("Alice", json.dumps(outcome["audit"]))
                outcomes.append((task, csv_path, preview["preview_id"], outcome))

            self.assertEqual(outcomes[0][3]["result"]["imported_rows"], 2)
            self.assertEqual(outcomes[1][3]["result"]["imported_rows"], 1)
            self.assertEqual(outcomes[2][3]["result"]["matched_count"], 1)
            retry_task, retry_path, retry_preview, first = outcomes[0]
            (inputs / "contacts.csv").write_bytes(b"id,name\n99,ChangedAfterSuccess\n")
            status, replay = post_json("/api/run", {
                "task": retry_task, "csv_path": retry_path,
                "preview_id": retry_preview, "approve_writes": True,
            })
            self.assertEqual(status, 200, replay)
            self.assertEqual(replay["result"], first["result"])
            with closing(sqlite3.connect(business)) as con:
                self.assertEqual(con.execute(
                    "SELECT COUNT(*) FROM csv_records WHERE run_id=?", (first["run_id"],)
                ).fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()


