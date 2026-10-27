"""Bounded, deterministic intent recognition for the synthetic local MVP."""
from __future__ import annotations

import re

from .engine import PlanError, validate
from .templates import build_template

MAX_REQUEST_CHARS = 512
_CSV = re.compile(r"(?<![A-Za-z0-9_])csv(?![A-Za-z0-9_])", re.IGNORECASE)
_SQLITE = re.compile(r"(?<![A-Za-z0-9_])sqlite(?:3)?(?![A-Za-z0-9_])", re.IGNORECASE)
_IMPORT_ACTION = re.compile(
    r"\b(?:import|ingest|load|save|store|write|insert|add)\b|가져오|불러오|저장|적재|넣어?",
    re.IGNORECASE,
)
_LOOKUP_ACTION = re.compile(
    r"\b(?:find|lookup|look\s+up|search|check|query|filter)\b|찾|조회|검색|확인",
    re.IGNORECASE,
)
_CONDITIONAL = re.compile(r"\b(?:if|when|only\s+if|only\s+when)\b|경우에만|때만", re.IGNORECASE)
_UNSUPPORTED = re.compile(
    r"\b(?:email|e-mail|http|https|api|webhook|gmail|sheets?|payment|pay|purchase|"
    r"delete|remove|drop|schedule|trigger|shell|command|script|browser|n8n|ai|llm|convert|coerce|cast|"
    r"translate|classify|deduplicate|clean|transform|upload|send)\b|"
    r"이메일|메일|결제|송금|구매|삭제|외부|웹훅|예약|스케줄|쉘|명령|스크립트|"
    r"번역|분류|중복제거|정리|변환|업로드|전송|실행|드롭",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"\b(?:don't|do not|not|without|never|no)\b|하지\s*말|말고|않아|아니",
    re.IGNORECASE,
)
_FIELD = r"[A-Za-z_][A-Za-z0-9_]{0,63}"
_NORMALIZE_FIELD = r"[A-Za-z_][A-Za-z0-9_]{0,31}"
_ENGLISH_NORMALIZE = re.compile(
    rf"(?:\b(?P<action>trim|strip|lowercase|lower|uppercase|upper)\s+"
    rf"(?:(?:the\s+)?(?:whitespace|spaces)\s+(?:in|from|around)\s+)?"
    rf"(?:the\s+)?(?P<field>{_NORMALIZE_FIELD})(?:\s+(?:column|field))?\b|"
    rf"\bconvert\s+(?:the\s+)?(?P<converted_field>{_NORMALIZE_FIELD})"
    rf"(?:\s+(?:column|field))?\s+to\s+(?:a\s+)?"
    r"(?P<target>number|numeric|string)(?:\s+value)?\b)",
    re.IGNORECASE,
)
_KOREAN_NORMALIZE = re.compile(
    rf"(?P<field>{_NORMALIZE_FIELD})\s*(?:열|컬럼)(?:의|을|를)?\s*"
    r"(?P<instruction>(?:(?:앞뒤)\s*)?공백\s*(?:을\s*)?(?:제거|정리)|"
    r"소문자(?:로\s*)?(?:변환|변경)|대문자(?:로\s*)?(?:변환|변경)|"
    r"(?:숫자|수치)(?:형)?(?:으로|로)\s*(?:변환|변경)|문자열(?:로)?\s*(?:변환|변경))",
    re.IGNORECASE,
)
_VALUE = r'(?:\"[^\"\r\n]{1,80}\"|\'[^\'\r\n]{1,80}\'|-?\d+(?:\.\d+)?|[A-Za-z가-힣_][A-Za-z0-9가-힣_-]{0,63})'
_ENGLISH_FILTER = re.compile(
    rf"(?<![A-Za-z0-9_])(?P<field>{_FIELD})\s*(?P<operator>>=|<=|==|=|>|<|equals?)\s*"
    rf"(?P<value>{_VALUE})(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_KOREAN_FILTER = re.compile(
    rf"(?P<field>{_FIELD})\s*(?:가|이|은|는)?\s*(?P<value>{_VALUE})\s*"
    r"(?P<qualifier>이상|초과|이하|미만|같은|인)(?:인)?",
    re.IGNORECASE,
)
_ORDERED = {">": "gt", ">=": "gte", "<": "lt", "<=": "lte"}


def _parse_scalar(raw: str, operator: str) -> tuple[object, str]:
    if raw[:1] in {"'", '"'}:
        return raw[1:-1], "identity"
    if operator in {"gt", "gte", "lt", "lte"} and re.fullmatch(r"-?\d+(?:\.\d+)?", raw):
        number = float(raw)
        return (int(number) if number.is_integer() else number), "number"
    return raw, "identity"


def _condition(task: str) -> tuple[str, str, object, str] | None:
    matches = list(_ENGLISH_FILTER.finditer(task)) + list(_KOREAN_FILTER.finditer(task))
    if not matches:
        return None
    if len(matches) != 1:
        raise PlanError("one explicit CSV field comparison is supported per request")
    match = matches[0]
    if match.groupdict().get("qualifier") is not None:
        operator = {
            "이상": "gte", "초과": "gt", "이하": "lte", "미만": "lt", "같은": "eq", "인": "eq",
        }[match.group("qualifier")]
    else:
        raw_operator = match.group("operator").casefold()
        operator = {"equals": "eq", "equal": "eq"}.get(raw_operator, _ORDERED.get(raw_operator, "eq"))
    value, transform = _parse_scalar(match.group("value"), operator)
    return match.group("field"), operator, value, transform


def _normalization(task: str) -> tuple[re.Match[str], str, str] | None:
    matches = [(match, "english")
               for match in _ENGLISH_NORMALIZE.finditer(task)]
    matches.extend((match, "korean") for match in _KOREAN_NORMALIZE.finditer(task))
    if not matches:
        return None
    if len(matches) != 1:
        raise PlanError("one explicit CSV column normalization is supported per request")
    match, action = matches[0]
    if action == "korean":
        instruction = match.group("instruction")
        if "공백" in instruction:
            transform = "trim"
        elif "소문자" in instruction:
            transform = "lower"
        elif "대문자" in instruction:
            transform = "upper"
        elif "문자열" in instruction:
            transform = "string"
        else:
            transform = "number"
        field = match.group("field")
    else:
        english_action = match.group("action")
        if english_action is None:
            transform = "string" if match.group("target").casefold() == "string" else "number"
            field = match.group("converted_field")
        else:
            english_action = english_action.casefold()
            transform = "trim" if english_action in {"trim", "strip"} else (
                "lower" if english_action in {"lower", "lowercase"} else "upper"
            )
            field = match.group("field")
    return match, field, transform


def _base_steps(csv_path: str) -> list[dict]:
    plan = build_template("csv_to_sqlite", csv_path=csv_path)
    return [plan["steps"][0]]


def workflow_name(plan: dict) -> str:
    operations = [step["op"] for step in plan["steps"]]
    if "csv_normalize" in operations and "sqlite_import_csv" in operations:
        return "csv_normalize_import"
    if "branch" in operations and "sqlite_import_csv" in operations:
        return "csv_conditional_import"
    if "csv_filter" in operations and "sqlite_import_csv" in operations:
        return "csv_filtered_import"
    if "csv_filter" in operations:
        return "csv_lookup"
    return "csv_to_sqlite"


def requires_write_approval(plan: dict) -> bool:
    return any(step["op"] in {"sqlite_put", "sqlite_import_csv"} for step in plan["steps"])


def plan_request(task: str, csv_path: str) -> dict:
    """Convert one supported English/Korean CSV request into validated native IR.

    Supported intents are full import, bounded single-column normalization followed
    by import, comparison-filtered import, conditional import, and read-only row-count
    lookup. Everything else fails closed.
    """
    if not isinstance(task, str) or not task.strip() or len(task) > MAX_REQUEST_CHARS:
        raise PlanError("task must be 1–512 characters")
    if _NEGATION.search(task):
        raise PlanError("this request includes an unsupported or negated action")
    normalization = _normalization(task)
    unsupported_task = task
    if normalization is not None:
        match, _, _ = normalization
        unsupported_task = task[:match.start()] + task[match.end():]
    if _UNSUPPORTED.search(unsupported_task):
        raise PlanError("this request includes an unsupported or negated action")
    if not _CSV.search(task):
        raise PlanError("describe a supported task using a CSV file")

    predicate = _condition(task)
    conditional = bool(_CONDITIONAL.search(task))
    imports = bool(_IMPORT_ACTION.search(task))
    has_sqlite = bool(_SQLITE.search(task))
    lookup = bool(_LOOKUP_ACTION.search(task))

    if normalization is not None and not (imports and has_sqlite):
        raise PlanError("CSV normalization requires an explicit local SQLite save action")

    def normalized_source(steps: list[dict]) -> str:
        if normalization is None:
            return "input"
        match, field, transform = normalization
        steps.append({"id": "normalized", "op": "csv_normalize", "from": "input",
                      "transforms": {field: transform}})
        return "normalized"

    if conditional:
        if not (predicate and imports and has_sqlite):
            raise PlanError("conditional import requires one CSV comparison and a local SQLite save action")
        steps = _base_steps(csv_path)
        source = normalized_source(steps)
        steps.extend([
            {"id": "filtered", "op": "csv_filter", "from": source, "field": predicate[0],
             "operator": predicate[1], "value": predicate[2], "transform": predicate[3]},
            {"id": "has_matches", "op": "condition", "from": "filtered", "field": "matched_count",
             "operator": "gt", "value": 0},
            {"id": "imported", "op": "sqlite_import_csv", "from": "filtered",
             "when": {"condition": "has_matches", "equals": True}},
            {"id": "empty", "op": "literal", "value": {"imported_rows": 0, "matched_rows": 0},
             "when": {"condition": "has_matches", "equals": False}},
            {"id": "result", "op": "branch", "condition": "has_matches", "then": "imported", "else": "empty"},
        ])
    elif imports and has_sqlite:
        steps = _base_steps(csv_path)
        source = normalized_source(steps)
        if predicate:
            steps.extend([
                {"id": "filtered", "op": "csv_filter", "from": source, "field": predicate[0],
                 "operator": predicate[1], "value": predicate[2], "transform": predicate[3]},
                {"id": "imported", "op": "sqlite_import_csv", "from": "filtered"},
            ])
        else:
            if normalization is None:
                return build_template("csv_to_sqlite", csv_path=csv_path)
            steps.append({"id": "imported", "op": "sqlite_import_csv", "from": source})
    elif lookup and predicate:
        steps = _base_steps(csv_path)
        steps.append({"id": "result", "op": "csv_filter", "from": "input", "field": predicate[0],
                      "operator": predicate[1], "value": predicate[2], "transform": predicate[3]})
    else:
        raise PlanError("describe importing CSV to SQLite or finding CSV rows with one explicit field comparison")

    return validate({"version": "axflow.ir.v0", "steps": steps})
