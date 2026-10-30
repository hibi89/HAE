"""G84: SHA-pinned genuine HAE -> Lightning Azent -> SQLite local acceptance.

Separate, temporary Python zipapp only. Never replaces shipped binaries, opens
customer data, calls NAS/providers, or exports private HAE/LA source to UGREEN.
Requires three existing owner-controlled source checkouts and explicit consent.
The public UGREEN G83 acceptance verifies the packaged *real* private engine.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from package_hae_integrated import build_integrated_zipapp

HAE_ROOT = Path(__file__).resolve().parents[1]
G82_WEB_BLOB = "ef093554750e28c0be7967d3a49e48649878d448"
G83_UGREEN_COMMIT = "45e09ae506b5ffed11b143f1e0387a4e7bfc303a"
LA_COMMIT = "9cba6424dadf3fadb0ccd6ed10040e322c4a62fa"
WEB_PATH = "apps/ax-flow/axflow/web.py"
APPROVAL = "--execute-synthetic-only"
PUBLIC_G83_FILES = ("tools/verify_hae_la_local_e2e.py", "tools/flowpilot_hae_bridge.py")


class NativeGateError(ValueError):
    """Source or owner consent fails the immutable G84 gate."""


def _git(folder: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(folder), *args],
        capture_output=True, text=True, check=False, timeout=8,
    )
    if result.returncode:
        raise NativeGateError("required Git source check failed")
    return result.stdout.strip()


def verify_public_source_integrity(root: Path, baseline: str = G83_UGREEN_COMMIT) -> None:
    """Allow newer documentation commits without accepting altered verification code."""
    try:
        _git(root, "merge-base", "--is-ancestor", baseline, "HEAD")
    except NativeGateError as exc:
        raise NativeGateError("UGREEN checkout does not descend from G83") from exc
    for path in PUBLIC_G83_FILES:
        baseline_blob = _git(root, "rev-parse", f"{baseline}:{path}")
        current_blob = _git(root, "hash-object", "--path", path, path)
        if current_blob != baseline_blob:
            raise NativeGateError("G83 verification code integrity mismatch")


def validate_sources(la_package: Path, ugreen_root: Path, confirmed: bool) -> tuple[Path, Path]:
    if confirmed is not True:
        raise NativeGateError("explicit owner synthetic execution consent required")
    if sys.version_info < (3, 11):
        raise NativeGateError("Python 3.11+ required")

    la_package = la_package.expanduser().resolve(strict=True)
    ugreen_root = ugreen_root.expanduser().resolve(strict=True)
    if (not (la_package / "lightning_azent" / "__init__.py").is_file()
            or not (ugreen_root / "tools" / "verify_hae_la_local_e2e.py").is_file()
            or not (ugreen_root / "tools" / "flowpilot_hae_bridge.py").is_file()):
        raise NativeGateError("genuine LA package or public G83 verification source absent")

    verify_public_source_integrity(ugreen_root)
    if _git(la_package, "rev-parse", "HEAD") != LA_COMMIT:
        raise NativeGateError("Lightning Azent checkout does not match pinned source")
    actual_web_blob = _git(HAE_ROOT, "hash-object", "--path", WEB_PATH, WEB_PATH)
    if actual_web_blob != G82_WEB_BLOB:
        raise NativeGateError("private HAE web source differs from reviewed G82 API")
    # A working-tree source change could otherwise be accidentally packaged.
    if _git(HAE_ROOT, "status", "--porcelain", "--", "apps/ax-flow/axflow"):
        raise NativeGateError("HAE package source has uncommitted changes")
    if _git(la_package, "status", "--porcelain", "--", "lightning_azent"):
        raise NativeGateError("LA package source has uncommitted changes")
    if _git(ugreen_root, "status", "--porcelain", "--", "tools"):
        raise NativeGateError("UGREEN verifier source has uncommitted changes")
    return la_package, ugreen_root


def run_g84(la_package: Path, ugreen_root: Path, *, execute_synthetic_only: bool = False) -> dict:
    la_package, ugreen_root = validate_sources(
        la_package, ugreen_root, execute_synthetic_only
    )
    with TemporaryDirectory(prefix="hae-g84-native-") as temporary:
        artifact = Path(temporary) / "g84-hae-la-temporary.pyz"
        build_integrated_zipapp(artifact, la_package)
        pinned_sha = sha256(artifact.read_bytes()).hexdigest()

        # Independent source parity: runtime archive really contains the source
        # of the reviewed private G82 HAE and selected LA commit.
        with ZipFile(artifact) as archive:
            if (archive.read("axflow/web.py")
                    != (HAE_ROOT / WEB_PATH).read_bytes()):
                raise NativeGateError("packaged HAE source differs from reviewed G82")
            if (archive.read("lightning_azent/__init__.py")
                    != (la_package / "lightning_azent" / "__init__.py").read_bytes()):
                raise NativeGateError("packaged LA source differs from pinned checkout")

        # Import only the immutable PUBLIC G83 verifier. The private code stays
        # inside an owner-local temporary archive and generated synthetic DBs.
        sys.path.insert(0, str(ugreen_root / "tools"))
        try:
            from verify_hae_la_local_e2e import run_acceptance
            result = run_acceptance(
                artifact, pinned_sha,
                execute_synthetic_only=True, require_g82_pending_id=True,
            )
        finally:
            sys.path.remove(str(ugreen_root / "tools"))

        if (result.get("status") != "REAL_HAE_LA_LOCAL_SYNTHETIC_E2E_PASS"
                or result.get("g82_pending_identity_verified") is not True
                or result.get("independent_sqlite_payload_verified") is not True
                or result.get("sqlite_business_rows") != 2
                or result.get("la_audit_persisted_after_restart") is not True
                or result.get("read_only_recovery_no_duplicate_write") is not True):
            raise NativeGateError("genuine HAE/LA/SQLite G82 identity or receipt gate failed")
        return {
            "status": "G84_GENUINE_HAE_LA_SQLITE_E2E_PASS",
            "verification": "G82_PRIVATE_RUNTIME_G83_PUBLIC_ACCEPTANCE",
            "hae_web_git_blob": G82_WEB_BLOB,
            "la_source_commit": LA_COMMIT,
            "ugreen_verifier_commit": G83_UGREEN_COMMIT,
            "temporary_zipapp_sha256": pinned_sha,
            "independent_sqlite_payload_verified": True,
            "pending_run_id_bound_to_approval": True,
            "sqlite_business_rows": 2,
            "read_only_recovery_without_duplicate_write": True,
            "original_binary_replaced": False,
            "real_nas_verified": False,
            "devpost_submitted": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--la-package", type=Path, required=True)
    parser.add_argument("--ugreen-root", type=Path, required=True)
    parser.add_argument(APPROVAL, action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run_g84(
            args.la_package, args.ugreen_root,
            execute_synthetic_only=args.execute_synthetic_only,
        )
    except Exception as exc:
        # No filesystem names, CSV cells, SQLite error text or private paths.
        result = {
            "status": "G84_NATIVE_E2E_NOT_VERIFIED",
            "error_type": type(exc).__name__,
            "failure_gate": str(exc) if isinstance(exc, NativeGateError) else "runtime-or-packaging",
            "original_binary_replaced": False,
            "real_nas_verified": False,
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "G84_GENUINE_HAE_LA_SQLITE_E2E_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
