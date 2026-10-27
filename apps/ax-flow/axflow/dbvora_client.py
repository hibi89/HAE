"""Bounded read-only client for DBVORA's local SQLite inventory API."""
from __future__ import annotations

import json
import re
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_TABLES = 1_000
MAX_COLUMNS_PER_TABLE = 500
MAX_FOREIGN_KEYS_PER_TABLE = 1_000
MAX_RELATIONSHIPS = 10_000
MAX_TEXT_LENGTH = 512
_DB_ID = re.compile(r"^[a-f0-9]{24}$")
_PROVENANCE_VALUES = {
    "cpu_usage": {"unavailable"},
    "relationships": {"declared_sqlite_foreign_keys"},
    "size_bytes": {"measured_local_filesystem"},
    "tables": {"measured_sqlite_catalog"},
}
_ACTIONS = {"NO ACTION", "RESTRICT", "SET NULL", "SET DEFAULT", "CASCADE"}


class DbvoraClientError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_base_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 256:
        raise ValueError("DBVORA URL must be a short loopback HTTP origin.")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise ValueError("DBVORA URL must include a valid loopback port.") from exc
    if (
        parts.scheme != "http"
        or parts.hostname != "127.0.0.1"
        or port is None
        or not 1 <= port <= 65535
        or parts.username is not None
        or parts.password is not None
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
    ):
        raise ValueError("DBVORA URL must be an HTTP origin on 127.0.0.1 with an explicit port.")
    return "http://127.0.0.1:" + str(port)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("unsupported JSON constant")


def _text(value: object, label: str, *, allow_empty: bool = False, max_length: int = MAX_TEXT_LENGTH) -> str:
    if (
        not isinstance(value, str)
        or len(value) > max_length
        or (not allow_empty and not value)
        or any(ord(char) < 32 for char in value)
    ):
        raise DbvoraClientError("INVALID_INVENTORY", "DBVORA returned invalid schema metadata.")
    return value


def _nonnegative_int(value: object, label: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise DbvoraClientError("INVALID_INVENTORY", "DBVORA returned invalid schema metadata.")
    return value


def _names(value: object) -> list[str | None]:
    if not isinstance(value, list) or len(value) > MAX_COLUMNS_PER_TABLE:
        raise DbvoraClientError("INVALID_INVENTORY", "DBVORA returned invalid schema metadata.")
    result: list[str | None] = []
    for item in value:
        result.append(None if item is None else _text(item, "column"))
    return result


def normalize_inventory(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict) or payload.get("contract_version") != "p0-01.v1" or payload.get("engine") != "sqlite":
        raise DbvoraClientError("UNSUPPORTED_CONTRACT", "DBVORA returned an unsupported inventory contract.")
    db_id = payload.get("db_id")
    if not isinstance(db_id, str) or not _DB_ID.fullmatch(db_id):
        raise DbvoraClientError("INVALID_INVENTORY", "DBVORA returned invalid schema metadata.")
    size_bytes = _nonnegative_int(payload.get("size_bytes"), "size_bytes", 16 * 1024**4)
    size_scope = _text(payload.get("size_scope"), "size_scope", max_length=128)
    observed_at = _text(payload.get("observed_at"), "observed_at", max_length=64)

    raw_tables = payload.get("tables")
    if not isinstance(raw_tables, list) or len(raw_tables) > MAX_TABLES:
        raise DbvoraClientError("INVALID_INVENTORY", "DBVORA returned invalid schema metadata.")
    tables: list[dict[str, object]] = []
    seen_tables: set[str] = set()
    for raw_table in raw_tables:
        if not isinstance(raw_table, dict):
            raise DbvoraClientError("INVALID_INVENTORY", "DBVORA returned invalid schema metadata.")
        name = _text(raw_table.get("name"), "table name")
        if name in seen_tables:
            raise DbvoraClientError("INVALID_INVENTORY", "DBVORA returned duplicate table metadata.")
        seen_tables.add(name)
        raw_columns = raw_table.get("columns")
        if not isinstance(raw_columns, list) or len(raw_columns) > MAX_COLUMNS_PER_TABLE:
            raise DbvoraClientError("INVALID_INVENTORY", "DBVORA returned invalid schema metadata.")
        columns: list[dict[str, object]] = []
        for raw_column in raw_columns:
            if not isinstance(raw_column, dict):
                raise DbvoraClientError("INVALID_INVENTORY", "DBVORA returned invalid schema metadata.")
            nullable = raw_column.get("nullable_declared")
            if not isinstance(nullable, bool):
                raise DbvoraClientError("INVALID_INVENTORY", "DBVORA returned invalid schema metadata.")
            columns.append({
                "name": _text(raw_column.get("name"), "column name"),
                "type": _text(raw_column.get("type"), "column type", allow_empty=True, max_length=256),
                "nullable_declared": nullable,
                "pk_position": _nonnegative_int(raw_column.get("pk_position"), "pk_position", MAX_COLUMNS_PER_TABLE),
                "hidden": _nonnegative_int(raw_column.get("hidden"), "hidden", 3),
            })

        raw_foreign_keys = raw_table.get("foreign_keys")
        if not isinstance(raw_foreign_keys, list) or len(raw_foreign_keys) > MAX_FOREIGN_KEYS_PER_TABLE:
            raise DbvoraClientError("INVALID_INVENTORY", "DBVORA returned invalid schema metadata.")
        foreign_keys: list[dict[str, object]] = []
        for raw_key in raw_foreign_keys:
            if not isinstance(raw_key, dict):
                raise DbvoraClientError("INVALID_INVENTORY", "DBVORA returned invalid schema metadata.")
            on_update = _text(raw_key.get("on_update"), "on_update", max_length=32)
            on_delete = _text(raw_key.get("on_delete"), "on_delete", max_length=32)
            if on_update not in _ACTIONS or on_delete not in _ACTIONS:
                raise DbvoraClientError("INVALID_INVENTORY", "DBVORA returned invalid schema metadata.")
            foreign_keys.append({
                "id": _nonnegative_int(raw_key.get("id"), "foreign key id", MAX_FOREIGN_KEYS_PER_TABLE),
                "to_table": _text(raw_key.get("to_table"), "foreign key table"),
                "from_columns": _names(raw_key.get("from_columns")),
                "to_columns": _names(raw_key.get("to_columns")),
                "on_update": on_update,
                "on_delete": on_delete,
            })
        tables.append({"name": name, "columns": columns, "foreign_keys": foreign_keys})
    tables.sort(key=lambda table: str(table["name"]))

    raw_relationships = payload.get("relationships")
    if not isinstance(raw_relationships, list) or len(raw_relationships) > MAX_RELATIONSHIPS:
        raise DbvoraClientError("INVALID_INVENTORY", "DBVORA returned invalid schema metadata.")
    relationships: list[dict[str, object]] = []
    for item in raw_relationships:
        if not isinstance(item, dict) or item.get("evidence") != "declared_foreign_key":
            raise DbvoraClientError("INVALID_INVENTORY", "DBVORA returned invalid relationship metadata.")
        relationships.append({
            "from_table": _text(item.get("from_table"), "relationship table"),
            "from_columns": _names(item.get("from_columns")),
            "to_table": _text(item.get("to_table"), "relationship table"),
            "to_columns": _names(item.get("to_columns")),
            "evidence": "declared_foreign_key",
        })
    relationships.sort(key=lambda item: (
        str(item["from_table"]), str(item["to_table"]), json.dumps(item["from_columns"], sort_keys=True)
    ))

    raw_provenance = payload.get("provenance")
    if not isinstance(raw_provenance, dict) or len(raw_provenance) > 16:
        raise DbvoraClientError("INVALID_INVENTORY", "DBVORA returned invalid provenance metadata.")
    provenance: dict[str, str] = {}
    for key, allowed_values in _PROVENANCE_VALUES.items():
        value = raw_provenance.get(key)
        if isinstance(value, str) and value in allowed_values:
            provenance[key] = value
    return {
        "contract_version": "p0-01.v1",
        "db_id": db_id,
        "engine": "sqlite",
        "size_bytes": size_bytes,
        "size_scope": size_scope,
        "observed_at": observed_at,
        "provenance": provenance,
        "tables": tables,
        "relationships": relationships,
    }


class DbvoraClient:
    def __init__(self, base_url: str | None = None, *, timeout_seconds: float = 1.5):
        self.base_url = validate_base_url(base_url) if base_url is not None else None
        if not 0 < timeout_seconds <= 5:
            raise ValueError("DBVORA timeout must be in the range (0, 5] seconds.")
        self.timeout_seconds = timeout_seconds
        self._opener = build_opener(_NoRedirect)

    def _get(self, path: str) -> object:
        assert self.base_url is not None
        request = Request(
            self.base_url + path,
            headers={"Accept": "application/json", "Cache-Control": "no-store"},
            method="GET",
        )
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                if response.getcode() != 200:
                    raise DbvoraClientError("HTTP_" + str(response.getcode()), "DBVORA rejected the local request.")
                if response.headers.get_content_type() != "application/json":
                    raise DbvoraClientError("INVALID_RESPONSE", "DBVORA returned a non-JSON response.")
                length = response.headers.get("Content-Length")
                if length is not None:
                    if not length.isascii() or not length.isdigit():
                        raise DbvoraClientError("INVALID_RESPONSE", "DBVORA returned an invalid response length.")
                    if len(length) > len(str(MAX_RESPONSE_BYTES)) or int(length) > MAX_RESPONSE_BYTES:
                        raise DbvoraClientError("RESPONSE_TOO_LARGE", "DBVORA response exceeds the local size limit.")
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except DbvoraClientError:
            raise
        except HTTPError as exc:
            status = exc.code
            exc.close()
            raise DbvoraClientError("HTTP_" + str(status), "DBVORA rejected the local request.") from None
        except (URLError, OSError, TimeoutError, HTTPException):
            raise DbvoraClientError("UNAVAILABLE", "DBVORA local service is unavailable.") from None
        except ValueError:
            raise DbvoraClientError("INVALID_RESPONSE", "DBVORA returned an invalid response.") from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise DbvoraClientError("RESPONSE_TOO_LARGE", "DBVORA response exceeds the local size limit.")
        try:
            return json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
            raise DbvoraClientError("INVALID_RESPONSE", "DBVORA returned invalid JSON.") from None

    def fetch_inventory(self) -> dict[str, object]:
        if self.base_url is None:
            return {
                "available": False,
                "error_code": "NOT_CONFIGURED",
                "message": "Configure a loopback DBVORA URL to view database metadata.",
            }
        try:
            health = self._get("/health")
            if not isinstance(health, dict) or health.get("ok") is not True or health.get("mode") != "local-read-only":
                raise DbvoraClientError("INVALID_HEALTH", "DBVORA is not reporting its read-only local mode.")
            inventory = normalize_inventory(self._get("/api/inventory"))
        except DbvoraClientError as exc:
            return {"available": False, "error_code": exc.code, "message": exc.message}
        return {"available": True, **inventory}
