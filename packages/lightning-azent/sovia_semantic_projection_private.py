"""P43 PRIVATE: source-backed *synthetic* LA step facts -> sanitized SOVIA schema.

This adapter reads first-party HAEBridge.evidence() after real local SQLite
execution. It proves one-to-one step event coverage, then emits only public
generic aliases and policy metadata. No original step IDs, paths, run IDs,
payloads, event timestamps or credential scopes leave the function.

Do NOT use for real customer data without approved privacy, provenance and
semantic mapping review. Event times and agent names are synthetic replacements.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from lightning_azent.contract import prepare_plan
from lightning_azent.engine import PlanError
from lightning_azent.hae_bridge import HAEBridge

MAX_STEPS = 256
SUPPORTED = {
    "csv_read": ("synthetic_csv", "none"),
    "sqlite_import_csv": ("synthetic_sqlite", "local_write"),
}


def project_completed_synthetic_steps(bridge, plan, run_id, *,
                                      synthetic_acknowledged=False):
    if synthetic_acknowledged is not True:
        raise PlanError("synthetic SOVIA step projection approval required")
    if not isinstance(bridge, HAEBridge):
        raise PlanError("first-party HAEBridge required")
    prepared = prepare_plan(plan)
    steps = prepared.runtime_plan["steps"]
    if not 1 <= len(steps) <= MAX_STEPS:
        raise PlanError("LA step count unsupported for SOVIA projection")
    if any(step["op"] not in SUPPORTED for step in steps):
        raise PlanError("unsupported LA operation: no event projection")
    # This validates actual completed LA SQLite business receipts, step totals,
    # audit terminal and exact private run/plan/approval scope, but not human identity.
    evidence = bridge.evidence(plan, run_id)
    status, audit = evidence["status"], evidence["audit"]
    if (evidence.get("verified") is not True or
            status.get("status") != "completed" or
            status.get("steps_recorded") != len(steps)):
        raise PlanError("incomplete first-party LA evidence")
    observed = {}
    for row in audit["events"]:
        if type(row) is not dict:
            raise PlanError("invalid LA audit step event")
        kind = row.get("event_type")
        if not isinstance(kind, str):
            raise PlanError("invalid LA audit step type")
        if not kind.startswith("step_"):
            continue
        if kind not in ("step_completed", "step_skipped"):
            raise PlanError("failed or unknown LA step event")
        details = row.get("details")
        if type(details) is not dict or not isinstance(details.get("step_id"), str):
            raise PlanError("LA step event missing source ID")
        sid = details["step_id"]
        if sid in observed:
            raise PlanError("duplicate completed LA step event")
        observed[sid] = (kind, details.get("operation"))
    if set(observed) != {step["id"] for step in steps}:
        raise PlanError("LA audit does not cover exactly all planned steps")
    if any(observed[step["id"]][1] != step["op"] for step in steps):
        raise PlanError("LA observed operation differs from plan")
    if any(observed[step["id"]][0] != "step_completed" for step in steps):
        # Avoid inventing success event for a legitimately skipped step.
        raise PlanError("skipped LA step not a completed synthetic observation")
    if any(type(e) is not dict for e in audit["approval_receipts"]):
        raise PlanError("LA approval receipts malformed")

    public_steps, public_events = [], []
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for index, step in enumerate(steps, 1):
        op = step["op"]
        target, effect = SUPPORTED[op]
        alias = f"step{index:03d}"
        write = effect == "local_write"
        permission = bool(audit["approval_receipts"]) if write else True
        public_steps.append({
            "step_id": alias, "tool_code": op, "side_effect": effect,
            "target_code": target, "destination_domain": None,
            "permission_asserted": permission,
            "approval_ref": "synthetic_claim" if write and permission else None,
        })
        public_events.append({
            "event_id": alias,
            "occurred_at_utc": (now + timedelta(seconds=index)).isoformat().replace(
                "+00:00", "Z"),
            "agent_id": "synthetic_la_agent",
            "run_id": "synthetic_la_run",
            "tool_name": op, "target": target, "destination_domain": None,
            "permission_asserted": permission, "outcome": "ok",
            "source_pointer": f"synthetic:la_step{index}",
        })
    # Intentionally different policy authority from LA write approval:
    # first operation allowed, later write not auto-cleared by SOVIA.
    policy = {"allowed_tools": [steps[0]["op"]],
              "approved_destinations": [], "sensitive_targets": [],
              "max_tool_calls_per_minute": 100}
    return {
        "plan": {"schema_version": "sovia.plan_review.v1",
                 "plan_ref": "synthetic_la_sanitized", "steps": public_steps},
        "policy": {"schema_version": "1.0", "policy": policy},
        "observations": {"schema_version": "1.0", "policy": policy,
                         "events": public_events},
    }
