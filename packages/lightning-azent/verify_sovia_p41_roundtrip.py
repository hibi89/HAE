"""P43 private exact-SHA real HAE→LA SQLite steps to PUBLIC SOVIA P40.

No upload of private code or customer data. The public repo is checked out
into this PRIVATE CI workspace at a pinned commit. Synthetic source only.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory


def _load(path, alias):
    source = Path(path).resolve()
    if not source.is_file():
        raise RuntimeError("PINNED_PUBLIC_SOVIA_COMPONENT_MISSING")
    spec = spec_from_file_location(alias, source)
    if spec is None or spec.loader is None:
        raise RuntimeError("PINNED_PUBLIC_SOVIA_COMPONENT_INVALID")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PACKAGE_ROOT = Path(__file__).resolve().parent
PRIVATE_REPO_ROOT = PACKAGE_ROOT.parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))
sys.path.insert(0, str(PRIVATE_REPO_ROOT / "apps" / "ax-flow"))

from axflow.planner import plan_request
from axflow.la_adapter import HAEConsumer
from lightning_azent import LAExecutor
from lightning_azent.engine import PlanError
from lightning_azent.hae_bridge import HAEBridge
from sovia_projection_private import export_local_synthetic_projection
from sovia_semantic_projection_private import project_completed_synthetic_steps

TASK = "Import this CSV file into local SQLite"


def run(public_source: Path) -> dict:
    public = Path(public_source).resolve()
    if not public.is_dir():
        raise RuntimeError("PUBLIC_SOVIA_CHECKOUT_REQUIRED")
    owner_review = _load(public / "sovia_la_owner_review.py", "_p43_public_owner")
    minimal = _load(public / "sovia_la_minimal_projection.py", "_p43_public_minimal")
    with TemporaryDirectory(prefix="la-sovia-p43-semantic-") as tmp:
        root = Path(tmp)
        source = root / "synthetic-orders.csv"
        source.write_bytes(b"id,amount\n1,7\n2,8\n")
        original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        state, business = root / "runtime.sqlite", root / "business.sqlite"
        bridge = HAEBridge(LAExecutor(state, business, root))
        consumer = HAEConsumer(bridge)
        run_id = "SyntheticSemanticP43"
        plan = plan_request(TASK, source.name)
        preview = consumer.preview(TASK, source.name, run_id)
        if not (preview["requires_write_approval"] and not preview["approved"]
                and not state.exists()):
            raise RuntimeError("IMPLICIT_LA_SQLITE_EXECUTION_DETECTED")
        consumer.execute(TASK, source.name, run_id, synthetic=True,
                         owner_confirmed=True,
                         confirmed_request_sha256=preview["request_sha256"])
        if not state.is_file() or not business.is_file():
            raise RuntimeError("REAL_LA_SQLITE_NOT_EXECUTED")

        projection = project_completed_synthetic_steps(
            bridge, plan, run_id, synthetic_acknowledged=True)
        text = json.dumps(projection, sort_keys=True)
        for prohibited in (run_id, source.name, "amount", "request_sha256",
                           original_hash, "source_file", "sqlite3.Connection"):
            if prohibited in text:
                raise RuntimeError("PRIVATE_LA_DATA_PROJECTION_LEAK")
        plan_file = root / "redacted-plan.json"
        policy_file = root / "redacted-policy.json"
        events_file = root / "redacted-observations.json"
        for path, key in ((plan_file, "plan"), (policy_file, "policy"),
                          (events_file, "observations")):
            path.write_text(json.dumps(projection[key], sort_keys=True), encoding="utf-8")
        output = root / "sovia-review"
        result = owner_review.create_bundle(plan_file, policy_file, events_file, output)
        if result["status"] != "SYNTHETIC_REVIEW_BUNDLE_CREATED_NOT_AUTHENTICATED":
            raise RuntimeError("REAL_SEMANTIC_SOVIA_RECONCILE_NOT_CREATED")
        review = json.loads((output / "review.json").read_text("utf-8"))
        if (review["planned_steps"] != 2 or review["observed_events"] != 2 or
                review["matched_step_ids"] != 2 or
                review["reconciliation_finding_count"] != 0 or
                review["plan_risk_finding_count"] < 1):
            raise RuntimeError("LA_AUDIT_TO_SOVIA_STEP_SEMANTICS_MISMATCH")

        minimal_doc = export_local_synthetic_projection(
            bridge, plan, run_id,
            sovia_plan_fingerprint_sha256=review["plan_fingerprint_sha256"],
            synthetic_acknowledged=True)
        minimal_path = root / "minimal-projection.json"
        minimal_path.write_text(json.dumps(minimal_doc, sort_keys=True), encoding="utf-8")
        evaluated = minimal.compare_minimal_projection(minimal_path, output,
                                                        acknowledge=True)
        if (evaluated["status"] != "REVIEW_REQUIRED_NOT_AUTHENTICATED" or
                evaluated["plan_fingerprint_claim_matches"] is not True or
                evaluated["real_la_integration_verified"] is not False or
                evaluated["cross_run_identity_verified"] is not False or
                evaluated["review_risk_count"] < 1):
            raise RuntimeError("LA_MINIMAL_SOVIA_RISK_FALSE_CLEAR")

        # Missing a genuine LA step audit event must fail source export
        # before a new SOVIA reconciliation can be produced.
        with closing(sqlite3.connect(state)) as conn:
            conn.execute(
                "DELETE FROM audit_events WHERE run_id=? AND event_type='step_completed' "
                "AND details_json LIKE ?", (run_id, '%"step_id":"input"%'))
            conn.commit()
        try:
            project_completed_synthetic_steps(
                bridge, plan, run_id, synthetic_acknowledged=True)
        except PlanError:
            missing_event_rejected = True
        else:
            missing_event_rejected = False
        if not missing_event_rejected:
            raise RuntimeError("MISSING_FIRST_PARTY_STEP_EVENT_FALSE_MATCH")
        if hashlib.sha256(source.read_bytes()).hexdigest() != original_hash:
            raise RuntimeError("ORIGINAL_SYNTHETIC_SOURCE_MODIFIED")
        return {
            "status": "REAL_SYNTHETIC_LA_SQLITE_STEPS_TO_SOVIA_AUDIT_PASS",
            "actual_first_party_la_sqlite": True,
            "matched_sanitized_step_count": review["matched_step_ids"],
            "unapproved_la_write_still_flagged_by_sovia_policy": True,
            "original_source_unchanged": True,
            "missing_la_step_event_rejected": True,
            "raw_private_data_exported": False,
            "human_identity_authenticated": False,
            "real_customer_scope_verified": False,
            "commercial_release_approved": False,
        }


def main(argv=None):
    p = argparse.ArgumentParser(description="PRIVATE CI synthetic real LA→SOVIA semantic parity")
    p.add_argument("--public-source", required=True)
    args = p.parse_args(argv)
    print(json.dumps(run(Path(args.public_source)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
