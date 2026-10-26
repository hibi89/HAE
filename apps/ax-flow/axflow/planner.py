"""Bounded, deterministic intent recognition for the supported local MVP."""
from __future__ import annotations

import re

from .engine import PlanError
from .templates import build_template

MAX_REQUEST_CHARS = 512
_CSV = re.compile(r"(?<![A-Za-z0-9_])csv(?![A-Za-z0-9_])", re.IGNORECASE)
_SQLITE = re.compile(r"(?<![A-Za-z0-9_])sqlite(?:3)?(?![A-Za-z0-9_])", re.IGNORECASE)
_IMPORT_ACTION = re.compile(
    r"\b(?:import|ingest|load|save|store|write|insert|add)\b|"
    r"가져오|불러오|저장|적재|넣어?",
    re.IGNORECASE,
)
_UNSUPPORTED = re.compile(
    r"\b(?:email|e-mail|http|https|api|webhook|gmail|sheets?|payment|pay|purchase|"
    r"delete|remove|drop|schedule|trigger|shell|command|script|browser|n8n|ai|llm|"
    r"translate|classify|deduplicate|clean|transform|upload|send)\b|"
    r"이메일|메일|결제|송금|구매|삭제|외부|웹훅|예약|스케줄|쉘|명령|스크립트|"
    r"번역|분류|중복제거|정리|변환|업로드|전송|실행|드롭",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"\b(?:don't|do not|not|without|never|no)\b|하지\s*말|말고|않아|아니",
    re.IGNORECASE,
)


def plan_request(task: str, csv_path: str) -> dict:
    """Map a narrow English/Korean CSV→SQLite request to a validated IR plan.

    This is an offline rule-based parser, not an LLM. Unknown or compound requests
    fail closed instead of being approximated.
    """
    if not isinstance(task, str) or not task.strip() or len(task) > MAX_REQUEST_CHARS:
        raise PlanError("task must be 1–512 characters")
    if _NEGATION.search(task) or _UNSUPPORTED.search(task):
        raise PlanError("only a simple CSV-to-local-SQLite import request is supported")
    if not (_CSV.search(task) and _SQLITE.search(task) and _IMPORT_ACTION.search(task)):
        raise PlanError("describe importing a CSV into local SQLite")
    return build_template("csv_to_sqlite", csv_path=csv_path)
