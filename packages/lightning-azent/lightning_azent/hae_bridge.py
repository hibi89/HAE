"""Opt-in, synthetic-only HAE -> Lightning Azent consumer bridge (v0).

This is an explicit compatibility boundary, NOT a HAE UI cutover, an OAuth
broker, a cryptographic human-consent proof, or an independent SOVIA audit.
No filesystem is touched by review(); executor SQLite files are opened only
by an authorized synthetic execution through the existing LA executor.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any, Mapping

from .contract import PreparedPlan, prepare_plan, preflight_summary
from .engine import ApprovalRequired, IDENTIFIER, PlanError, canonical_json
from .runtime import LAExecutor

BRIDGE_VERSION = "hae.la-bridge.v0"
API_VERSION = "azent.api.v0"
AUDIT_VERSION = "metadata-only.v0"
WRITE_OPS = frozenset(("sqlite_put", "sqlite_import_csv"))


@dataclass(frozen=True)
class ReviewedWorkflow:
    """Ephemeral review result. Never persist or interpret it as user consent."""

    plan_sha256: str
    request_sha256: str
    run_id: str
    source_version: str
    requires_write_approval: bool
    summary: dict[str, Any]

    def public_view(self) -> dict[str, Any]:
        return {
            "bridge_version": BRIDGE_VERSION,
            "api_version": API_VERSION,
            "run_id": self.run_id,
            "source_version": self.source_version,
            "plan_sha256": self.plan_sha256,
            "request_sha256": self.request_sha256,
            "requires_write_approval": self.requires_write_approval,
            "preview": self.summary,
            "synthetic_only": True,
            "approved": False,
            "executed": False,
        }


class HAEBridge:
    """Safe, opt-in entry point for an eventual HAE consumer.

    The embedding HAE application must authenticate its own owner session and
    verify confirmation. Supplying a matching digest merely binds that app's
    already-confirmed decision to the exact run and validated plan; it does NOT
    prove who approved it. No automatic approval or external connector exists.
    """

    def __init__(self, executor: LAExecutor):
        self.executor = executor

    def _require_compatible_runtime(self) -> None:
        caps = self.executor.capabilities()
        if not isinstance(caps, dict) or caps.get("api_version") != API_VERSION:
            raise PlanError("unsupported Lightning Azent API version")
        if caps.get("audit_feed") != AUDIT_VERSION or caps.get("external_connectors") != []:
            raise PlanError("unsupported Lightning Azent audit or connector scope")
        if caps.get("scope") != "synthetic-local-only":
            raise PlanError("unsafe Lightning Azent runtime scope")

    @staticmethod
    def _prepare(plan: object, run_id: str) -> tuple[PreparedPlan, str, bool, str]:
        if not isinstance(run_id, str) or not IDENTIFIER.fullmatch(run_id):
            raise PlanError("HAE bridge requires a safe run_id")
        prepared = prepare_plan(plan)
        if prepared.runtime_plan.get("trigger", {"type": "manual"})["type"] != "manual":
            raise PlanError("interval plans must use the separate LA scheduler")
        plan_sha256 = hashlib.sha256(canonical_json(prepared.runtime_plan).encode("utf-8")).hexdigest()
        write_steps = [
            {"id": step["id"], "op": step["op"]}
            for step in prepared.runtime_plan["steps"] if step["op"] in WRITE_OPS
        ]
        approval_scope = {
            "bridge_version": BRIDGE_VERSION,
            "api_version": API_VERSION,
            "source_version": prepared.source_version,
            "run_id": run_id,
            "plan_sha256": plan_sha256,
            "write_steps": write_steps,
        }
        request_sha256 = hashlib.sha256(canonical_json(approval_scope).encode("utf-8")).hexdigest()
        return prepared, plan_sha256, bool(write_steps), request_sha256

    def review(self, plan: object, run_id: str) -> ReviewedWorkflow:
        self._require_compatible_runtime()
        prepared, plan_sha256, needs_write, request_sha256 = self._prepare(plan, run_id)
        # Redacted summary intentionally excludes plan values, CSV rows, paths and credentials.
        summary = preflight_summary(prepared)
        return ReviewedWorkflow(plan_sha256, request_sha256, run_id,
                                prepared.source_version, needs_write, summary)

    def execute(
        self, plan: object, run_id: str, *, synthetic: bool = False,
        confirmed_request_sha256: str | None = None, owner_confirmed: bool = False,
        resume: bool = False,
    ) -> object:
        self._require_compatible_runtime()
        if synthetic is not True:
            raise PlanError("HAE bridge execution is synthetic-only")
        if type(owner_confirmed) is not bool or type(resume) is not bool:
            raise PlanError("invalid HAE bridge flags")
        reviewed = self.review(plan, run_id)
        if reviewed.requires_write_approval:
            if owner_confirmed is not True or not isinstance(confirmed_request_sha256, str):
                raise ApprovalRequired("owner-confirmed scoped SQLite approval required")
            if not hmac.compare_digest(reviewed.request_sha256, confirmed_request_sha256):
                raise ApprovalRequired("approval scope does not match this run and plan")
        elif confirmed_request_sha256 is not None or owner_confirmed:
            # Keep read-only requests simple: never silently reinterpret extra approval.
            raise PlanError("read-only workflow must not carry write approval")
        if resume:
            return self.executor.resume(plan, run_id, approve_writes=reviewed.requires_write_approval)
        return self.executor.execute(plan, run_id, approve_writes=reviewed.requires_write_approval)

    def evidence(self, plan: object, run_id: str) -> dict[str, object]:
        """Read-only local receipt/status/audit; no original workflow data is returned."""
        self._require_compatible_runtime()
        self._prepare(plan, run_id)
        verification = self.executor.verify_receipts(plan, run_id)
        if not isinstance(verification, dict) or verification.get("verified") is not True:
            raise PlanError("Lightning Azent receipts not verified")
        status = self.executor.status(run_id)
        # A clean receipt check is not proof of a successful workflow. A missing,
        # running or failed run must never be advertised as completed evidence.
        if not isinstance(status, dict) or status.get("status") != "completed":
            raise PlanError("Lightning Azent run is not completed")
        if status.get("run_id") != run_id:
            raise PlanError("Lightning Azent status belongs to a different run")
        return {
            "bridge_version": BRIDGE_VERSION,
            "run_id": run_id,
            "verified": True,
            "status": status,
            "audit": self.executor.audit(run_id),
            "audit_version": AUDIT_VERSION,
            "independent_sovia_audit": False,
        }
