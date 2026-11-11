"""Offline, source-free customer handoff for an existing REA_APP v0.3.0 bundle.

This is an independent, optional companion tool. It never executes or imports
analyzed code, and it never copies raw reports into the customer handoff.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

FILES = ("source-map.json", "change-impact.json", "functional-contracts.json")
ARTIFACTS = ("review.json", "review.html")
SCHEMAS = ("rea-app-source-map/v1", "rea-app-change-impact/v1", "rea-app-functional-contracts/v1")
VERSION = "rea-app-owner-delivery/v1"
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_COUNT = 10_000_000


class DeliveryError(ValueError):
    pass


def _regular_file(path: Path, limit: int = MAX_JSON_BYTES) -> bytes:
    # Do not follow a final symlink and do not read unbounded JSON.
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit or path.is_symlink():
        raise DeliveryError(f"invalid or oversized regular file: {path.name}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as handle:
        opened = os.fstat(handle.fileno())
        if (not stat.S_ISREG(opened.st_mode) or opened.st_size > limit
                or (opened.st_ino, opened.st_dev) != (info.st_ino, info.st_dev)):
            raise DeliveryError("file changed while opening")
        data = handle.read(limit + 1)
    if len(data) > limit or path.is_symlink():
        raise DeliveryError(f"unsafe or oversized file: {path.name}")
    return data


def _directory(path: Path) -> Path:
    path = path.expanduser().absolute()
    # Reject symlinked parents too, including an attacker-controlled input root.
    for part in (path, *path.parents):
        if part.is_symlink():
            raise DeliveryError("symbolic-link directory is not allowed")
    if not path.is_dir():
        raise DeliveryError("input directory does not exist")
    return path.resolve(strict=True)


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _encode(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _count(mapping: dict, name: str) -> int:
    value = mapping.get(name)
    if type(value) is not int or not (0 <= value <= MAX_COUNT):
        raise DeliveryError(f"invalid count: {name}")
    return value


def _load(bundle: Path) -> tuple[list[dict], dict[str, str]]:
    reports: list[dict] = []
    digests: dict[str, str] = {}
    for filename, schema in zip(FILES, SCHEMAS):
        data = _regular_file(bundle / filename)
        try:
            report = json.loads(data)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise DeliveryError(f"invalid JSON: {filename}") from exc
        if not isinstance(report, dict) or report.get("schema_version") != schema:
            raise DeliveryError(f"unsupported schema: {filename}")
        reports.append(report)
        digests[filename] = _hash(data)
    return reports, digests


def _review(reports: list[dict]) -> dict:
    source, impact, contracts = reports
    ss = source.get("summary")
    isummary = impact.get("summary")
    cs = contracts.get("summary")
    if not all(isinstance(item, dict) for item in (ss, isummary, cs)):
        raise DeliveryError("missing summary")
    snapshots = impact.get("snapshots")
    if not isinstance(snapshots, dict) or snapshots.get("current") != ss:
        raise DeliveryError("source map and current snapshot differ")
    keys = ("files_indexed", "source_files", "dependency_edges", "syntax_errors", "skipped_paths")
    output = {key: _count(ss, key) for key in keys}
    names = ("added_files", "removed_files", "modified_files", "added_modules", "removed_modules",
             "added_internal_dependencies", "removed_internal_dependencies", "added_contracts",
             "removed_contracts", "changed_contracts", "syntax_errors")
    output.update({key: _count(isummary, key) for key in names})
    output["exported_callable_contracts"] = _count(cs, "exported_callable_contracts")
    changed = impact.get("changed_files")
    observed = contracts.get("contracts")
    if not isinstance(changed, list) or not isinstance(observed, list):
        raise DeliveryError("missing changed-file or contract inventory")
    if len(changed) != sum(output[key] for key in ("added_files", "removed_files", "modified_files")):
        raise DeliveryError("changed-file count mismatch")
    if len(observed) != output["exported_callable_contracts"]:
        raise DeliveryError("callable count mismatch")
    if not isinstance(snapshots.get("baseline"), dict):
        raise DeliveryError("missing baseline")
    if output["syntax_errors"] != _count(snapshots["baseline"], "syntax_errors") + _count(ss, "syntax_errors"):
        raise DeliveryError("syntax-error count mismatch")
    if output["syntax_errors"]:
        raise DeliveryError("syntax errors detected: customer delivery is on HOLD")
    return {
        "schema": VERSION,
        "assurance": "summary_of_local_static_reports_only_not_runtime_or_legal_certification",
        "counts": output,
        "customer_release": "HOLD_PENDING_OWNER_ACCEPTANCE",
        "limitations": ["No source paths, code, secrets, source reports or original files are included.",
                        "Static JS/TS observations cannot prove runtime behavior or source reconstruction.",
                        "The owner must review rights, real Windows packaging, and any customer data."],
    }


def _html(review: dict) -> bytes:
    values = review["counts"]
    labels = ( ("files_indexed", "분석된 파일"), ("source_files", "JS/TS 파일"),
               ("dependency_edges", "의존성 관측"), ("modified_files", "수정된 파일"),
               ("added_files", "추가된 파일"), ("removed_files", "삭제된 파일"),
               ("changed_contracts", "변경된 함수 계약"), ("exported_callable_contracts", "관측된 함수 계약"),
               ("skipped_paths", "제외된 경로") )
    cells = "\n".join(f"<tr><th scope='row'>{label}</th><td>{values[key]}</td></tr>" for key,label in labels)
    return ("<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
            "<title>REA_APP 오프라인 검수</title><style>body{font:16px/1.65 system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;color:#17202c}"
            "h1{font-size:26px}table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #d4dce6;padding:10px;text-align:left}td{text-align:right;font-weight:650}"
            ".hold{font-weight:700;color:#92310b}footer{font-size:13px;color:#525c66;margin-top:30px}</style></head><body>"
            "<h1>REA_APP 소유자 검수 요약</h1><p>별도 승인된 로컬 분석 결과에서 숫자만 추출한 오프라인 보고서입니다.</p>"
            "<p class='hold'>상업 출시: 보류 — 소유자 최종 검수 필요</p><table><tbody>"
            + cells + "</tbody></table><footer>원본 코드, 파일 경로, 분석 원문은 포함하지 않습니다. "
            "정적 분석은 실행 결과나 권리 검증을 대신하지 않습니다. review.json 및 manifest.json의 SHA-256을 독립 확인하십시오."
            "</footer></body></html>\n").encode("utf-8")


def _validate_output_location(bundle: Path, output: Path) -> Path:
    output = output.expanduser().absolute()
    for part in (output, *output.parents):
        if part.is_symlink():
            raise DeliveryError("symbolic-link output path is not allowed")
    if output == bundle or bundle in output.parents or output in bundle.parents:
        raise DeliveryError("delivery folder must be separate from source reports")
    if output.exists():
        raise DeliveryError("delivery folder already exists; refusing overwrite")
    if not output.parent.is_dir():
        raise DeliveryError("delivery parent does not exist")
    return output


def build(bundle_path: Path, output_path: Path) -> None:
    bundle = _directory(bundle_path)
    output = _validate_output_location(bundle, output_path)
    reports, source_hashes = _load(bundle)
    review = _review(reports)
    contents = {"review.json": _encode(review), "review.html": _html(review)}
    manifest = _encode({"schema": VERSION, "bundle_sha256": source_hashes,
                        "delivery_sha256": {name: _hash(contents[name]) for name in ARTIFACTS}})
    output.mkdir(mode=0o700)
    try:
        for name in ARTIFACTS:
            with (output / name).open("xb") as handle:
                handle.write(contents[name])
        with (output / "manifest.json").open("xb") as handle:
            handle.write(manifest)
    except Exception:
        for name in (*ARTIFACTS, "manifest.json"):
            (output / name).unlink(missing_ok=True)
        output.rmdir()
        raise


def verify(bundle_path: Path, delivery_path: Path) -> None:
    bundle = _directory(bundle_path)
    delivery = _directory(delivery_path)
    if bundle == delivery or bundle in delivery.parents or delivery in bundle.parents:
        raise DeliveryError("overlapping source and delivery")
    reports, source_hashes = _load(bundle)
    expected = _review(reports)
    data = _regular_file(delivery / "manifest.json")
    try:
        manifest = json.loads(data)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError("invalid manifest") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != VERSION:
        raise DeliveryError("manifest schema mismatch")
    if manifest.get("bundle_sha256") != source_hashes:
        raise DeliveryError("changed input reports")
    content = {name: _regular_file(delivery / name) for name in ARTIFACTS}
    if manifest.get("delivery_sha256") != {name: _hash(content[name]) for name in ARTIFACTS}:
        raise DeliveryError("delivery file modified")
    if content["review.json"] != _encode(expected) or content["review.html"] != _html(expected):
        raise DeliveryError("review output differs from current reports")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local REA_APP source-free owner delivery, no external services")
    parser.add_argument("mode", choices=("build", "verify"))
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--delivery", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.mode == "build":
            build(args.bundle, args.delivery)
        else:
            verify(args.bundle, args.delivery)
    except (DeliveryError, OSError) as exc:
        print(f"HOLD: {exc}", file=sys.stderr)
        return 2
    print(f"PASS: REA_APP owner delivery {args.mode} (no customer release approval)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
