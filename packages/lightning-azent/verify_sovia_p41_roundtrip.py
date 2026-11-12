"""P41 cross-repo OFFLINE synthetic acceptance in PRIVATE HAE CI.

Consumes exact public SOVIA P40 source checkout pinned by the workflow.
Actual first-party LA runs a fabricated local CSV through its SQLite engine.
The untrusted, source-free minimal projection is then checked by SOVIA's
real public P40 verifier; no private code or record is sent to public GitHub.
This proves a synthetic technical adapter contract, NOT human/authenticity.
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

TASK = "Import this CSV file into local SQLite"


def run(public_source: Path) -> dict:
    public = Path(public_source).resolve()
    if not public.is_dir():
        raise RuntimeError("PUBLIC_SOVIA_CHECKOUT_REQUIRED")
    sovia_owner = _load(public / "sovia_la_owner_review.py", "_private_p41_public_owner")
    sovia_check = _load(public / "sovia_la_minimal_projection.py", "_private_p41_public_check")
    with TemporaryDirectory(prefix="la-sovia-actual-synthetic-roundtrip-") as tmp:
        root = Path(tmp)
        review = root / "public-review"
        public_plan = public / "examples/demo_la_plan_review.json"
        policy = public / "examples/demo_policy.json"
        observations = public / "examples/demo_la_observations.json"
        produced = sovia_owner.create_bundle(public_plan, policy, observations, review)
        if produced["status"] != "SYNTHETIC_REVIEW_BUNDLE_CREATED_NOT_AUTHENTICATED":
            raise RuntimeError("PUBLIC_REVIEW_NOT_CREATED")
        baseline = json.loads((review / "review.json").read_text("utf-8"))
        fingerprint = baseline["plan_fingerprint_sha256"]

        original = root / "tiny-public-synthetic.csv"
        original.write_bytes(b"id,amount\n1,7\n2,8\n")
        original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
        state = root / "la-runtime.sqlite"
        business = root / "la-business.sqlite"
        bridge = HAEBridge(LAExecutor(state, business, root))
        owner = HAEConsumer(bridge)
        run_id = "SyntheticSOVIAActualP41"
        plan = plan_request(TASK, original.name)
        preview = owner.preview(TASK, original.name, run_id)
        if not (preview["requires_write_approval"] is True
                and preview["approved"] is False and not state.exists()):
            raise RuntimeError("UNAUTHORIZED_RUN_CREATED_PRE_EXECUTION")
        owner.execute(TASK, original.name, run_id, synthetic=True,
                      owner_confirmed=True,
                      confirmed_request_sha256=preview["request_sha256"])
        if not state.is_file() or not business.is_file():
            raise RuntimeError("REAL_LA_SQLITE_EXECUTION_MISSING")
        projection = export_local_synthetic_projection(
            bridge, plan, run_id,
            sovia_plan_fingerprint_sha256=fingerprint,
            synthetic_acknowledged=True)
        projection_raw = json.dumps(projection, sort_keys=True, separators=(",", ":"))
        if any(value in projection_raw for value in (
                run_id, original.name, "amount", "sqlite_import_csv", "run_id",
                "request_sha256", original_hash)):
            raise RuntimeError("PRIVATE_SOURCE_EXPORTED")
        public_input = root / "minimal-public-projection.json"
        public_input.write_text(projection_raw, encoding="utf-8")
        checked = sovia_check.compare_minimal_projection(
            public_input, review, acknowledge=True)
        if (checked["status"] != "REVIEW_REQUIRED_NOT_AUTHENTICATED" or
                checked["plan_fingerprint_claim_matches"] is not True or
                "PLAN_FINGERPRINT_MISMATCH" in checked["reasons"] or
                "PLANNED_STEP_COUNT_MISMATCH" in checked["reasons"] or
                checked["real_la_integration_verified"] is not False or
                checked["cross_run_identity_verified"] is not False or
                checked["execution_authorized"] is not False):
            raise RuntimeError("FIRST_PARTY_MINIMAL_CROSSCHECK_FAILED")
        if "SOVIA_RISK_FINDINGS_PRESENT" not in checked["reasons"]:
            raise RuntimeError("PUBLIC_RISK_FINDINGS_WERE_LOST")

        wrong = dict(projection)
        wrong["plan_fingerprint_sha256"] = "0" * 64 if fingerprint != "0" * 64 else "f" * 64
        public_input.write_text(json.dumps(wrong), encoding="utf-8")
        mismatch = sovia_check.compare_minimal_projection(
            public_input, review, acknowledge=True)
        if "PLAN_FINGERPRINT_MISMATCH" not in mismatch["reasons"]:
            raise RuntimeError("FOREIGN_PLAN_CLAIM_NOT_DETECTED")

        # Runtime business tamper must block any new public projection.
        with closing(sqlite3.connect(business)) as con:
            con.execute("DELETE FROM csv_records WHERE row_number=2")
            con.commit()
        try:
            export_local_synthetic_projection(
                bridge, plan, run_id,
                sovia_plan_fingerprint_sha256=fingerprint,
                synthetic_acknowledged=True)
        except PlanError:
            tamper_blocked = True
        else:
            tamper_blocked = False
        if not tamper_blocked:
            raise RuntimeError("TAMPERED_REAL_SQLITE_ACCEPTED")
        if original_hash != hashlib.sha256(original.read_bytes()).hexdigest():
            raise RuntimeError("ORIGINAL_SYNTHETIC_INPUT_MODIFIED")
        return {
            "status": "FIRST_PARTY_LA_SQLITE_TO_PUBLIC_SOVIA_P40_SYNTHETIC_PASS",
            "first_party_la_sqlite_executed": True,
            "original_input_unchanged": True,
            "private_payload_exported": False,
            "public_sovia_risk_findings_retained": True,
            "mismatched_sovia_claim_refused": True,
            "tampered_la_receipt_refused": True,
            "plan_identity_authenticated": False,
            "source_authenticated": False,
            "human_consent_authenticated": False,
            "customer_acceptance_verified": False,
            "commercial_release_approved": False,
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private synthetic first-party LA -> public SOVIA CI")
    parser.add_argument("--public-source", required=True)
    args = parser.parse_args(argv)
    result = run(Path(args.public_source))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
