"""P41: produce a source-free, UNSIGNED synthetic SOVIA projection from real LA SQLite.

Only an explicitly acknowledged *local synthetic* LA run is supported. The
first-party HAEBridge validates the real plan, run status, read-only business
receipts, audit terminal and write approval receipts BEFORE this projection.
No private plan, run ID, target, source paths or event details leave this API.
The public SOVIA fingerprint is caller-asserted and does NOT prove cross-run
identity, source authentication or owner consent.
"""
from __future__ import annotations

import re

from lightning_azent.contract import prepare_plan
from lightning_azent.engine import PlanError
from lightning_azent.hae_bridge import HAEBridge

PUBLIC_SCHEMA = "sovia.la_minimal_projection.synthetic.v1"
PUBLIC_SOURCE_KIND = "DECLARED_LA_LIKE_SYNTHETIC"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_STEPS = 1000
MAX_AUDIT = 4096
OUTCOMES = ("completed", "skipped", "failed", "running")


def export_local_synthetic_projection(
    bridge: HAEBridge, plan: object, run_id: str, *,
    sovia_plan_fingerprint_sha256: str,
    synthetic_acknowledged: bool = False,
) -> dict:
    """Read verified LA SQLite evidence and return ONLY P40 public aggregate fields.

    This projection intentionally cannot certify authenticity or a genuine
    owner-approved mapping between LA and SOVIA plan canonicalization.
    """
    if synthetic_acknowledged is not True:
        raise PlanError("explicit synthetic SOVIA projection acknowledgement required")
    if not isinstance(bridge, HAEBridge):
        raise PlanError("first-party HAEBridge required")
    if (type(sovia_plan_fingerprint_sha256) is not str or
            SHA256.fullmatch(sovia_plan_fingerprint_sha256) is None):
        raise PlanError("synthetic SOVIA fingerprint must be 64 lowercase hex")
    prepared = prepare_plan(plan)
    plan_steps = len(prepared.runtime_plan["steps"])
    if not 1 <= plan_steps <= MAX_STEPS:
        raise PlanError("unsupported synthetic LA step count")
    # First-party LA evidence() requires complete, same-run validated status,
    # audited terminal, same-run approval scope and read-only business receipts.
    evidence = bridge.evidence(plan, run_id)
    status = evidence["status"]
    audit = evidence["audit"]
    if (evidence.get("verified") is not True or
            evidence.get("independent_sovia_audit") is not False or
            status.get("status") != "completed" or
            status.get("steps_recorded") != plan_steps):
        raise PlanError("LA source cannot be represented as a completed synthetic claim")
    outcomes = status.get("step_outcomes")
    if type(outcomes) is not dict or set(outcomes) != set(OUTCOMES):
        raise PlanError("LA step outcomes not supported")
    for key in OUTCOMES:
        if type(outcomes[key]) is not int or not 0 <= outcomes[key] <= MAX_STEPS:
            raise PlanError("LA outcome counter invalid")
    if (sum(outcomes.values()) != plan_steps or
            outcomes["failed"] != 0 or outcomes["running"] != 0):
        raise PlanError("LA completion is not consistent")
    events = audit.get("events")
    approvals = audit.get("approval_receipts")
    if (type(events) is not list or not 1 <= len(events) <= MAX_AUDIT or
            type(approvals) is not list or len(approvals) > MAX_AUDIT):
        raise PlanError("LA audit cannot be represented safely")
    if events[-1].get("event_type") not in ("run_completed", "run_replayed"):
        raise PlanError("LA audit lacks final event")
    if not any(x.get("event_type") == "run_completed" for x in events):
        raise PlanError("LA audit missing completion claim")

    # Fixed fields are the *entire* public output. Do not copy source dicts.
    # The SOVIA plan fingerprint is not LA's private plan hash; caller
    # confirms mapping later. Even an exact match is not authentication.
    return {
        "schema_version": PUBLIC_SCHEMA,
        "source_kind": PUBLIC_SOURCE_KIND,
        "synthetic_only": True,
        "source_authenticated": False,
        "approval_authenticated": False,
        "stream_completeness_verified": False,
        "plan_fingerprint_sha256": sovia_plan_fingerprint_sha256,
        "run_status": "completed",
        "steps": {
            "declared": plan_steps,
            "recorded": status["steps_recorded"],
            "completed": outcomes["completed"],
            "skipped": outcomes["skipped"],
            "failed": outcomes["failed"],
            "running": outcomes["running"],
        },
        "audit": {
            "event_count": len(events),
            "terminal_completion_claimed": True,
            "write_approval_claims": len(approvals),
        },
    }
