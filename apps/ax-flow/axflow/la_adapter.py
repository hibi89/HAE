"""Explicit development-only adapter for the optional Lightning Azent package.

The adapter validates the independent package contract before use. CSV execution
uses the exact byte snapshot approved by HAE, staged in a private temporary root.
"""
from __future__ import annotations

import hashlib
import importlib
import tempfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from .engine import VERSION as HAE_IR_VERSION, _exclusive_run, canonical_json


class BackendUnavailable(RuntimeError):
    """The selected optional backend is missing or incompatible."""


def _load_backend(plan: object):
    try:
        package = importlib.import_module("lightning_azent")
        executor_type = package.LAExecutor
    except (ImportError, AttributeError) as exc:
        raise BackendUnavailable("Lightning Azent development backend is unavailable") from exc

    try:
        capabilities = executor_type.capabilities()
        summary = executor_type.preflight(plan)
    except Exception as exc:
        raise BackendUnavailable("Lightning Azent development backend contract check failed") from exc
    operations = {step.get("op") for step in plan["steps"] if isinstance(step, dict)}
    supported = capabilities.get("implemented_operations") if isinstance(capabilities, dict) else None
    if (not isinstance(capabilities, dict)
            or not isinstance(summary, dict)
            or capabilities.get("api_version") != "azent.api.v0"
            or capabilities.get("legacy_ir_version") != HAE_IR_VERSION
            or summary.get("runtime_version") != HAE_IR_VERSION
            or not isinstance(supported, list)
            or not all(isinstance(operation, str) for operation in supported)
            or not operations.issubset(set(supported))
            or capabilities.get("scope") != "synthetic-local-only"):
        raise BackendUnavailable("Lightning Azent development backend is incompatible; no fallback was used")
    version = getattr(package, "__version__", None)
    if not isinstance(version, str) or not version:
        raise BackendUnavailable("Lightning Azent package version is unavailable")
    fingerprint = hashlib.sha256(canonical_json({
        "package_version": version,
        "api_version": capabilities["api_version"],
        "runtime_schema_version": capabilities.get("runtime_schema_version"),
        "legacy_ir_version": capabilities["legacy_ir_version"],
        "implemented_operations": sorted(supported),
        "max_csv_bytes": capabilities.get("max_csv_bytes"),
        "max_csv_rows": capabilities.get("max_csv_rows"),
        "max_steps": capabilities.get("max_steps"),
    }).encode("utf-8")).hexdigest()
    return executor_type, summary, {
        "name": "Lightning Azent",
        "api_version": capabilities["api_version"],
        "package_version": version,
        "runtime_schema_version": capabilities.get("runtime_schema_version"),
        "capability_fingerprint": fingerprint,
    }


def inspect_backend(plan: object) -> dict[str, object]:
    """Run LA's plan-only preflight and capability handshake; never open SQLite."""
    _, summary, identity = _load_backend(plan)
    return {**identity, "preflight": summary}


@contextmanager
def _executor_for_snapshot(executor_type, state_path: Path, business_path: Path,
                           input_root: Path, snapshot: dict[str, object] | None,
                           expected_sha256: str | None):
    if snapshot is None:
        yield executor_type(state_path, business_path, input_root=input_root)
        return

    raw = snapshot.get("raw_bytes")
    relative = snapshot.get("source_path")
    digest = snapshot.get("source_sha256")
    if (not isinstance(raw, bytes) or not isinstance(relative, str)
            or not isinstance(digest, str) or digest != expected_sha256
            or hashlib.sha256(raw).hexdigest() != digest):
        raise BackendUnavailable("approved CSV snapshot is incomplete or inconsistent")
    parts = PurePosixPath(relative).parts
    if (not parts or PurePosixPath(relative).is_absolute()
            or any(part in {"", ".", ".."} for part in parts)
            or PurePosixPath(relative).suffix.lower() != ".csv"):
        raise BackendUnavailable("approved CSV snapshot path is invalid")
    with tempfile.TemporaryDirectory(prefix="hae-la-input-") as folder:
        staged_root = Path(folder)
        staged_file = staged_root.joinpath(*parts)
        staged_file.parent.mkdir(parents=True, exist_ok=True)
        with staged_file.open("xb") as stream:
            stream.write(raw)
            stream.flush()
        if hashlib.sha256(staged_file.read_bytes()).hexdigest() != digest:
            raise BackendUnavailable("approved CSV snapshot staging verification failed")
        yield executor_type(state_path, business_path, input_root=staged_root)


def execute(plan: object, run_id: str, *, state_path: Path, business_path: Path,
            input_root: Path, approve_writes: bool,
            csv_snapshot: dict[str, object] | None = None,
            expected_csv_sha256: str | None = None) -> dict[str, object]:
    """Execute with LA under HAE's per-run process lock and return receipts/audit."""
    executor_type, _, backend = _load_backend(plan)
    with _exclusive_run(Path(state_path).resolve(), run_id):
        with _executor_for_snapshot(
            executor_type, Path(state_path), Path(business_path), Path(input_root),
            csv_snapshot, expected_csv_sha256,
        ) as executor:
            result = executor.execute(plan, run_id, approve_writes=approve_writes)
            status = executor.status(run_id)
            audit = executor.audit(run_id)
    return {"result": result, "status": status, "audit": audit, "backend": backend}
