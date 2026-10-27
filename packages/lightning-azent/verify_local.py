"""Single-command, offline Lightning Azent verifier (Python >= 3.11).

From HAE repository root: python packages/lightning-azent/verify_local.py
Logs + report are stored under an isolated system-temp directory, not in Git.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sqlite3
from contextlib import closing
import subprocess
import sys
import tempfile
import time

PKG = Path(__file__).resolve().parent
ROOT = PKG.parents[1]
FIX = ROOT / "docs" / "lightning-azent" / "fixtures"
ORIGINAL = ROOT / "apps" / "ax-flow"
EXPECTED_MIN_TESTS = 49


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline, synthetic-only HAE/LA verification")
    ap.add_argument("--skip-legacy", action="store_true")
    ap.add_argument("--skip-wheel", action="store_true")
    ap.add_argument("--timeout", type=int, default=240)
    opts = ap.parse_args()
    if not 10 <= opts.timeout <= 1800:
        ap.error("--timeout must be 10..1800 seconds")

    work = Path(tempfile.mkdtemp(prefix="la-verify-"))
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(PKG),
               PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1",
               PIP_CONFIG_FILE=os.devnull)
    checks = []
    report = {"started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "branch": None, "sha": None, "dirty": None,
              "python": sys.version.split()[0], "platform": platform.platform(),
              "temporary_directory": str(work), "checks": checks}
    python = sys.executable

    def run(name, args, *, extra_env=None):
        proc = subprocess.run(args, cwd=ROOT, env=extra_env or env,
                              text=True, encoding="utf-8", errors="replace",
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=opts.timeout)
        output = proc.stdout
        (work / (name + ".log")).write_text(output, encoding="utf-8")
        if proc.returncode:
            raise RuntimeError(f"{name}: exit {proc.returncode}; " +
                               "\n".join(output.splitlines()[-15:]))
        return output

    def require(condition, explanation):
        if not condition:
            raise RuntimeError(explanation)

    def command_json(name, args):
        return json.loads(run(name, [python, "-B", "-m", "lightning_azent", *args]))

    def provenance():
        require((ROOT / ".git").exists(), "Git checkout required, not a partial copy")
        report["sha"] = run("git_head", ["git", "rev-parse", "HEAD"]).strip()
        report["branch"] = run("git_branch", ["git", "branch", "--show-current"]).strip()
        report["dirty"] = bool(run("git_dirty", ["git", "status", "--porcelain",
                                                "--untracked-files=no"]).strip())
        require(report["branch"] == "feature/lightning-azent", "Wrong Git branch")
        require(not report["dirty"], "Tracked source tree is dirty; keep receipt SHA exact")
        require(sys.version_info >= (3, 11), "Requires Python >= 3.11")
        return {"sha": report["sha"]}

    def syntax():
        sources = sorted(PKG.rglob("*.py"))
        require(bool(sources), "No LA Python source found")
        for path in sources:
            compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
        return {"syntax_files": len(sources)}

    def regression(name, tests, extra_env=None, min_tests=1):
        output = run(name, [python, "-B", "-m", "unittest", "discover",
                            "-s", str(tests), "-v"], extra_env=extra_env)
        match = re.findall(r"Ran (\d+) tests?", output)
        require(bool(match) and int(match[-1]) >= min_tests, "Missing tests in " + name)
        skipped = re.findall(r"skipped=(\d+)", output)
        count = int(match[-1])
        skip = int(skipped[-1]) if skipped else 0
        return {"total": count, "passed": count - skip, "failed": 0,
                "skipped": skip, "log": name + ".log"}

    def preflight():
        plan = str(FIX / "csv-filter-import.json")
        info = command_json("preflight_csv", ["preflight", plan])
        require(info.get("step_count") == 3 and
                info.get("requires_input_root") is True and
                info.get("requires_write_approval") is True and
                info.get("executes_workflow") is False and
                info.get("external_connectors_supported") is False and
                all(set(step) == {"id", "op"} for step in info.get("steps", [])),
                "Preflight metadata leak or incorrect permission classification")
        return {"source_version": info["source_version"], "steps": 3,
                "read_only": True}

    def native():
        folder = work / "native"; folder.mkdir()
        plan = str(FIX / "native-conditional-route.json")
        state, data = str(folder / "state.sqlite"), str(folder / "data.sqlite")
        valid = command_json("native_validate", ["validate", plan])
        require(valid.get("valid") is True and valid.get("version") == "azent.ir.v0",
                "Native version validation failed")
        arguments = ["--state", state, "--data", data, "--run-id", "NativeSmoke",
                     "--synthetic"]
        first = command_json("native_run", ["run", plan, *arguments])
        resumed = command_json("native_resume", ["resume", plan, *arguments])
        status = command_json("native_status", ["status", "--state", state,
                                                 "--run-id", "NativeSmoke"])
        require(first == resumed == {"route": "accepted"} and
                status.get("status") == "completed", "Native run/resume mismatch")
        with closing(sqlite3.connect(state)) as db:
            require(db.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1,
                    "Native duplicate run record")
        return {"run": "NativeSmoke", "idempotent": True}

    def csv():
        folder = work / "csv"; folder.mkdir()
        source = folder / "orders.csv"
        shutil.copyfile(FIX / "orders.csv", source)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        state, data = str(folder / "state.sqlite"), str(folder / "data.sqlite")
        plan = str(FIX / "csv-filter-import.json")
        arguments = ["--state", state, "--data", data, "--input-root", str(folder),
                     "--run-id", "CsvSmoke", "--synthetic", "--approve-writes"]
        without_approval = [x for x in arguments if x != "--approve-writes"]
        refusal = subprocess.run(
            [python, "-B", "-m", "lightning_azent", "run", plan, *without_approval],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=opts.timeout)
        require(refusal.returncode == 2 and "ApprovalRequired" in refusal.stderr,
                "Expected approval gate to reject the CSV run")
        require(not Path(state).exists() and not Path(data).exists(),
                "Rejected CSV run must not initialize databases")
        invalid_id = subprocess.run(
            [python, "-B", "-m", "lightning_azent", "run", plan,
             *[("bad/id" if x == "CsvSmoke" else x) for x in arguments]],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=opts.timeout)
        require(invalid_id.returncode == 2 and "PlanError" in invalid_id.stderr,
                "Invalid run ID must be rejected")
        require(not Path(state).exists() and not Path(data).exists(),
                "Invalid run ID initialized SQLite files")
        first = command_json("csv_run", ["run", plan, *arguments])
        again = command_json("csv_resume", ["resume", plan, *arguments])
        with closing(sqlite3.connect(data)) as db:
            count = db.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0]
        require(first == again and count == 2, "CSV import or resume mismatch")
        require(hashlib.sha256(source.read_bytes()).hexdigest() == digest,
                "Synthetic input source changed")
        # Completed business rows must not silently disappear on manual resume.
        with closing(sqlite3.connect(data)) as db:
            db.execute("DELETE FROM csv_records WHERE rowid = (SELECT MIN(rowid) FROM csv_records)")
            db.commit()
        tampered = subprocess.run(
            [python, "-B", "-m", "lightning_azent", "resume", plan, *arguments],
            cwd=ROOT, env=env, text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=opts.timeout,
        )
        (work / "csv_missing_receipt_denial.log").write_text(
            tampered.stdout + "\n" + tampered.stderr, encoding="utf-8")
        require(tampered.returncode == 2 and "PlanError" in tampered.stderr,
                "Resume accepted missing completed CSV business receipt")
        with closing(sqlite3.connect(data)) as db:
            require(db.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0] == count - 1,
                    "Resume unexpectedly rewrote tampered business receipts")
        return {"business_rows_before_tamper": count, "input_unchanged": True,
                "missing_receipt_resume_denied": True}

    def interval():
        folder = work / "interval"; folder.mkdir()
        state, data = str(folder / "state.sqlite"), str(folder / "data.sqlite")
        output = command_json("interval_schedule", [
            "schedule", str(FIX / "interval-replay.json"),
            "--state", state, "--data", data, "--schedule-id", "IntervalSmoke",
            "--max-runs", "2", "--synthetic", "--approve-writes"])
        require(isinstance(output, list) and len(output) == 2 and
                [x.get("tick") for x in output] == [0, 1] and
                all(x.get("advanced") is True for x in output), "Interval replay failed")
        with closing(sqlite3.connect(data)) as db:
            count = db.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        require(count == 2, "Interval business receipts mismatch")
        return {"ticks": 2, "business_rows": count}

    def wheel():
        if any(importlib.util.find_spec(p) is None for p in ("pip", "setuptools", "wheel")):
            return {"skip": "offline packaging modules missing"}
        # setuptools can create build/egg-info: build only from disposable copy.
        copied = work / "package_source"
        shutil.copytree(PKG, copied, ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", "build", "dist", "*.egg-info"))
        wheels = work / "wheels"; wheels.mkdir()
        run("offline_wheel", [python, "-B", "-m", "pip", "wheel", "--no-index",
                              "--no-deps", "--no-build-isolation", "--wheel-dir",
                              str(wheels), str(copied)])
        artifacts = list(wheels.glob("lightning_azent-*.whl"))
        require(len(artifacts) == 1, "Expected one LA wheel")
        installed = work / "installed"
        run("wheel_install", [python, "-B", "-m", "pip", "install", "--no-index",
                              "--no-deps", "--target", str(installed), str(artifacts[0])])
        test_env = dict(env, PYTHONPATH=str(installed))
        version = run("installed_cli_version",
                      [python, "-B", "-m", "lightning_azent", "--version"],
                      extra_env=test_env).strip()
        require(bool(version), "Installed console version empty")
        return {"wheel": artifacts[0].name, "version": version}

    tasks = [
        ("git_provenance", provenance),
        ("syntax", syntax),
        ("plan_preflight", preflight),
        ("la_full_regression", lambda: regression("la_unittest", PKG / "tests",
                                                 min_tests=EXPECTED_MIN_TESTS)),
        ("native_cli_resume", native),
        ("csv_import_replay", csv),
        ("interval_two_ticks", interval),
        ("legacy_regression", lambda: regression(
            "legacy_unittest", ORIGINAL / "tests",
            extra_env=dict(env, PYTHONPATH=os.pathsep.join([str(ORIGINAL), str(PKG)])))),
        ("offline_wheel", wheel),
    ]
    failed = False
    for name, task in tasks:
        started = time.monotonic()
        record = {"name": name, "status": "PASS"}
        try:
            if name == "legacy_regression" and (opts.skip_legacy or
                                                not (ORIGINAL / "tests").is_dir()):
                record.update(status="SKIP", reason="legacy tests skipped or unavailable")
            elif name == "offline_wheel" and opts.skip_wheel:
                record.update(status="SKIP", reason="--skip-wheel")
            else:
                value = task()
                if "skip" in value:
                    record.update(status="SKIP", reason=value["skip"])
                else:
                    record["detail"] = value
        except Exception as error:
            failed = True
            record.update(status="FAIL", error=str(error))
        record["elapsed_seconds"] = round(time.monotonic() - started, 2)
        checks.append(record)
        print(f"[{record['status']}] {name}", flush=True)
        if failed:
            print(record["error"], file=sys.stderr)
            break  # Fail closed at first safety gate; keep subsequent evidence pending.

    summary = {state: sum(x["status"] == state for x in checks)
               for state in ("PASS", "FAIL", "SKIP")}
    skipped_cases = sum(item.get("detail", {}).get("skipped", 0) for item in checks)
    partial = summary["SKIP"] > 0 or skipped_cases > 0
    overall = "FAIL" if failed else ("PARTIAL" if partial else "PASS")
    report.update(finished_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  overall=overall, summary=summary,
                  skipped_test_cases=skipped_cases, release_ready=(overall == "PASS"))
    destination = work / "verify_result.json"
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                           encoding="utf-8")
    print(f"RESULT {report['overall']} PASS={summary['PASS']} "
          f"FAIL={summary['FAIL']} SKIP={summary['SKIP']}")
    print(f"SHA {report['sha'] or 'not verified'}")
    print(f"REPORT {destination}")
    return 1 if failed else (3 if partial else 0)


if __name__ == "__main__":
    raise SystemExit(main())
