"""Adapter to SOVIA's supported offline, post-execution advisory reconciliation."""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

class SOVIAUnavailable(RuntimeError):
    """SOVIA is not installed, or its offline review contract is incompatible."""


_OPS = {
    "csv_read": "csv_read",
    "csv_filter": "csv_filter",
    "csv_normalize": "csv_normalize",
    "condition": "condition",
    "branch": "branch",
    "sqlite_import_csv": "sqlite_import_csv",
    "sqlite_put": "sqlite_put",
    "sqlite_get": "sqlite_get",
    "literal": "literal",
    "field": "field",
    "map": "map",
}


def _load(root: Path):
    try:
        resolved = Path(root).expanduser().resolve(strict=True)
    except OSError as exc:
        raise SOVIAUnavailable("SOVIA offline observation reconciliation is unavailable") from exc
    if not resolved.is_dir() or not (resolved / "sovia_la_observation_reconcile.py").is_file():
        raise SOVIAUnavailable("SOVIA offline observation reconciliation is unavailable")
    text = str(resolved)
    if text not in sys.path:
        sys.path.insert(0, text)
    try:
        module = importlib.import_module("sovia_la_observation_reconcile")
        module_path = Path(module.__file__).resolve(strict=True)
        if (not callable(getattr(module, "reconcile", None))
                or module_path.parent != resolved):
            raise ImportError("reconcile contract missing")
        return module
    except Exception as exc:
        raise SOVIAUnavailable("SOVIA offline review contract is unavailable or incompatible") from exc


def reconcile(plan: dict, run_id: str, plan_sha256: str, la_status: object,
              la_audit: object, *, approved: bool, sovia_root: Path | None) -> dict[str, object]:
    """Call SOVIA's actual reconcile() over sanitized HAE plan and LA metadata.

    SOVIA documents this contract as offline/advisory. The adapter deliberately
    preserves its unauthenticated evidence and no-runtime-gate limitations.
    """
    if sovia_root is None:
        raise SOVIAUnavailable("SOVIA root is not configured")
    if not re.fullmatch(r"[a-f0-9]{64}", plan_sha256):
        raise SOVIAUnavailable("HAE plan fingerprint is invalid")
    module = _load(sovia_root)
    # SOVIA's PII heuristic rejects long opaque token strings. Use a 128-bit
    # correlation reference there; the complete SHA-256 remains in HAE's
    # adapter envelope and is verified against both LA receipts.
    plan_ref = "plan:" + plan_sha256[:32]
    normalized_steps = []
    for step in plan.get("steps", []):
        operation = step.get("op") if isinstance(step, dict) else None
        tool = _OPS.get(operation)
        if tool is None:
            raise SOVIAUnavailable("SOVIA adapter does not support this HAE operation")
        is_write = operation in {"sqlite_import_csv", "sqlite_put"}
        normalized_steps.append({
            "step_id": step["id"], "tool_code": tool,
            "side_effect": "local_write" if is_write else "none",
            "target_code": "business_sqlite" if is_write else None,
            "permission_asserted": bool(approved) if is_write else None,
            "approval_ref": "la-approval:" + run_id if is_write and approved else None,
        })

    receipts = la_audit.get("approval_receipts") if isinstance(la_audit, dict) else None
    expected_write_scope = [
        {"step_id": step["id"], "operation": step["op"]}
        for step in plan.get("steps", [])
        if isinstance(step, dict) and step.get("op") in {"sqlite_import_csv", "sqlite_put"}
    ]
    receipt_matches = bool(approved and isinstance(receipts, list) and any(
        isinstance(item, dict) and isinstance(item.get("scope"), dict)
        and item["scope"].get("plan_sha256") == plan_sha256
        and item["scope"].get("write_steps") == expected_write_scope
        for item in receipts
    ))
    event_rows = la_audit.get("events") if isinstance(la_audit, dict) else None
    status_matches = (isinstance(la_status, dict) and la_status.get("run_id") == run_id
                      and la_status.get("plan_sha256") == plan_sha256)
    audit_matches = (isinstance(la_audit, dict) and la_audit.get("run_id") == run_id
                     and la_audit.get("plan_sha256") == plan_sha256)
    if not status_matches or not audit_matches or not isinstance(event_rows, list):
        raise SOVIAUnavailable("LA execution evidence is incomplete or does not match the approved plan")

    events: dict[str, tuple[str, int, str]] = {}
    retries = 0
    failed_attempts: set[str] = set()
    for index, event in enumerate(event_rows):
        if not isinstance(event, dict) or not isinstance(event.get("details"), dict):
            continue
        details = event["details"]
        sid = details.get("step_id")
        kind = event.get("event_type")
        if kind == "step_completed" and isinstance(sid, str):
            attempts = details.get("attempt_count", 1)
            if isinstance(attempts, int) and not isinstance(attempts, bool) and attempts > 1:
                retries += attempts - 1
            events[sid] = ("observed", index, kind)
        elif kind == "step_skipped" and isinstance(sid, str):
            events[sid] = ("observed", index, kind)
        elif kind == "step_failed" and isinstance(sid, str):
            failed_attempts.add(sid)
            events[sid] = ("failed", index, kind)
    observations = []
    executed = []
    skipped = []
    failed = []
    unverifiable = []
    for step in normalized_steps:
        sid = step["step_id"]
        event = events.get(sid)
        if event is None:
            state, evidence = "unknown", None
            unverifiable.append(sid)
        else:
            state, index, event_kind = event
            evidence = f"la-audit:{run_id}:event:{index}"
            if state == "failed":
                failed.append(sid)
            elif event_kind == "step_skipped":
                skipped.append(sid)
            else:
                executed.append(sid)
        observations.append({
            "step_id": sid, "tool_code": step["tool_code"],
            "side_effect": step["side_effect"], "state": state,
            "evidence_ref": evidence,
            **({"target_code": step["target_code"]} if step["target_code"] else {}),
        })

    sovia_plan = {"schema_version": "sovia.plan_review.v1", "plan_ref": plan_ref,
                  "steps": normalized_steps}
    policy = {"schema_version": "1.0", "policy": {
        "allowed_tools": sorted(set(_OPS.values())),
        "sensitive_targets": ["business_sqlite"],
    }}
    envelope = {"schema_version": "sovia.observation.v1", "plan_ref": plan_ref,
                "observations": observations}
    try:
        review = module.reconcile(sovia_plan, policy, envelope)
    except Exception as exc:
        code = str(exc) if re.fullmatch(r"[A-Z0-9_]{1,80}", str(exc)) else type(exc).__name__
        raise SOVIAUnavailable("SOVIA review rejected the adapter contract: " + code) from exc
    if not isinstance(review, dict) or review.get("schema_version") != "sovia.plan_observation_review.v1":
        raise SOVIAUnavailable("SOVIA returned an incompatible review contract")
    # The engine guarantees explicit approval before a write. If SOVIA's LA
    # audit receipt is missing, report approval evidence as unconfirmed.
    return {
        "available": True,
        "mode": "post_execution_advisory",
        "run_id": run_id,
        "plan_version": plan.get("version"),
        "plan_sha256": plan_sha256,
        "approval": {"requested": bool(approved), "la_receipt_matched": receipt_matches,
                     "scope": [item["step_id"] for item in normalized_steps
                               if item["side_effect"] == "local_write"]},
        "execution": {
            "status": la_status.get("status"),
            "executed_steps": executed,
            "skipped_steps": skipped,
            "failed_steps": failed,
            "failed_attempt_steps": sorted(failed_attempts),
            "retry_count": retries,
            "unverifiable_steps": unverifiable,
            "policy_findings": review.get("findings", []),
            "policy_violation_state": "advisory_unverified",
            "evidence_source": "Lightning Azent metadata-only audit feed",
            "evidence_authenticated": False,
            "observation_scope": "Available LA step events only; event absence is not proof of non-execution.",
        },
        "review": review,
    }
