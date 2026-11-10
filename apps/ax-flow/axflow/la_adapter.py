"""Opt-in HAE planner -> Lightning Azent v0 local consumer adapter.

Only owner-authenticated HAE code should provide a scoped confirmation digest.
The existing HAE GUI / HTTP routes intentionally remain on the old runtime.
"""
from __future__ import annotations

from .planner import plan_request


class HAEConsumer:
    """Bind HAE's bounded intent planner to an injected HAEBridge.

    Keeps HAE's original axflow planner as the sole authority for supported
    natural-language tasks and their typed IR. This does not parse arbitrary
    shell commands or authorize an LA write implicitly.
    """

    def __init__(self, bridge):
        if bridge is None or any(not callable(getattr(bridge, name, None))
                                 for name in ("review", "execute", "evidence")):
            raise TypeError("HAEConsumer requires a Lightning Azent HAEBridge")
        self.bridge = bridge

    def preview(self, task: str, csv_path: str, run_id: str) -> dict:
        plan = plan_request(task, csv_path)
        return self.bridge.review(plan, run_id).public_view()

    def execute(
        self, task: str, csv_path: str, run_id: str, *,
        synthetic: bool = False, owner_confirmed: bool = False,
        confirmed_request_sha256: str | None = None, resume: bool = False,
    ) -> object:
        plan = plan_request(task, csv_path)
        return self.bridge.execute(
            plan, run_id, synthetic=synthetic, owner_confirmed=owner_confirmed,
            confirmed_request_sha256=confirmed_request_sha256, resume=resume,
        )

    def evidence(self, task: str, csv_path: str, run_id: str) -> dict:
        plan = plan_request(task, csv_path)
        return self.bridge.evidence(plan, run_id)
