"""Explicit local synthetic workflow recipe catalog; no automatic execution.

The catalog stores only a user's approved task and *relative synthetic CSV*
path plus pinned source/plan hashes, never CSV rows or OAuth credentials. Loading
always revalidates and requires a new preview and separate write approval.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from .engine import PlanError, canonical_json, preflight_csv_plan
from .planner import plan_request, workflow_name

MAX_RECIPES = 32
MAX_BYTES = 512 * 1024
_RECIPE = re.compile(r"^[a-f0-9]{24}$")
_SHA = re.compile(r"^[a-f0-9]{64}$")
_DDL = (
    "CREATE TABLE recipes("
    "recipe_id TEXT PRIMARY KEY CHECK(length(recipe_id)=24), "
    "task TEXT NOT NULL CHECK(length(task)<=512), "
    "csv_path TEXT NOT NULL CHECK(length(csv_path)<=512), "
    "source_sha256 TEXT NOT NULL CHECK(length(source_sha256)=64), "
    "plan_sha256 TEXT NOT NULL CHECK(length(plan_sha256)=64), "
    "workflow TEXT NOT NULL CHECK(length(workflow)<=64)"
    ")"
)


class WorkflowCatalogError(ValueError):
    """The reviewed workflow cannot be saved or loaded safely."""


def _deny() -> None:
    raise WorkflowCatalogError("HAE synthetic workflow catalog refused safely")


def _path(value: Path | str, *, exists: bool) -> Path:
    if not isinstance(value, (str, Path)) or not str(value) or len(str(value)) > 1024:
        _deny()
    path = Path(value).expanduser()
    if not path.is_absolute() or not path.parent.is_dir():
        _deny()
    for component in (path, *path.parents):
        if component.is_symlink():
            _deny()
    if exists:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 100 <= info.st_size <= MAX_BYTES:
            _deny()
    elif path.exists() or path.is_symlink():
        _deny()
    return path.resolve(strict=exists)


def _open(path: Path, *, write: bool):
    if any(Path(str(path) + part).exists() for part in ("-wal", "-shm", "-journal")):
        _deny()
    return sqlite3.connect(path.as_uri() + ("?mode=rw" if write else "?mode=ro"),
                           uri=True, timeout=2)


def _schema(db: sqlite3.Connection) -> None:
    if db.execute("PRAGMA user_version").fetchone() != (1,):
        _deny()
    if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        _deny()
    names = db.execute("SELECT name,type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
    if names != [("recipes", "table")]:
        _deny()
    fields = {column[1] for column in db.execute("PRAGMA table_info(recipes)")}
    if fields != {"recipe_id", "task", "csv_path", "source_sha256", "plan_sha256", "workflow"}:
        _deny()


def initialize_workflow_catalog(
    catalog_path: Path | str, *, synthetic: bool = False, acknowledge_new_file: bool = False,
) -> dict:
    if synthetic is not True or acknowledge_new_file is not True:
        _deny()
    created = False
    path = None
    try:
        path = _path(catalog_path, exists=False)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        os.close(fd)
        created = True
        with closing(sqlite3.connect(path, timeout=2)) as db, db:
            db.execute(_DDL)
            db.execute("PRAGMA user_version=1")
            _schema(db)
        return {"status": "INITIALIZED", "recipe_count": 0,
                "release_gate": "HOLD", "customer_ready": False}
    except (OSError, sqlite3.Error, RuntimeError, ValueError, TypeError):
        if created and path is not None:
            try:
                path.unlink()
            except OSError:
                pass
        _deny()


def list_synthetic_workflows(catalog_path: Path | str, *, synthetic: bool = False) -> dict:
    if synthetic is not True:
        _deny()
    try:
        path = _path(catalog_path, exists=True)
        with closing(_open(path, write=False)) as db:
            db.execute("PRAGMA query_only=ON")
            _schema(db)
            entries = db.execute(
                "SELECT recipe_id,workflow FROM recipes ORDER BY recipe_id LIMIT ?",
                (MAX_RECIPES + 1,),
            ).fetchall()
            if len(entries) > MAX_RECIPES:
                _deny()
        return {"recipe_count": len(entries),
                "recipes": [{"recipe_id": key, "workflow": name} for key, name in entries],
                "release_gate": "HOLD", "customer_ready": False}
    except (OSError, sqlite3.Error, RuntimeError, ValueError, TypeError):
        _deny()


def _bound_plan(task: str, csv_path: str, input_root: Path | str):
    if (not isinstance(task, str) or not isinstance(csv_path, str)
            or not task or len(task) > 512 or not csv_path or len(csv_path) > 512
            or csv_path.startswith(".axflow-upload-") or "\\"
               in csv_path):
        _deny()
    plan = plan_request(task, csv_path)
    snapshot, _ = preflight_csv_plan(plan, Path(input_root).expanduser())
    plan_sha = hashlib.sha256(canonical_json(plan).encode("utf-8")).hexdigest()
    return plan, snapshot["source_sha256"], plan_sha


def save_synthetic_workflow(
    catalog_path: Path | str, input_root: Path | str, task: str, csv_path: str,
    expected_source_sha256: str, *, synthetic: bool = False, approve_save: bool = False,
) -> dict:
    if (synthetic is not True or approve_save is not True
            or not isinstance(expected_source_sha256, str)
            or _SHA.fullmatch(expected_source_sha256) is None):
        _deny()
    try:
        plan, current_source_sha, plan_sha = _bound_plan(task, csv_path, input_root)
        if current_source_sha != expected_source_sha256:
            _deny()
        recipe_id = hashlib.sha256(canonical_json({
            "task": task, "csv_path": csv_path,
            "source_sha256": current_source_sha, "plan_sha256": plan_sha,
        }).encode("utf-8")).hexdigest()[:24]
        record = (recipe_id, task, csv_path, current_source_sha, plan_sha, workflow_name(plan))
        path = _path(catalog_path, exists=True)
        with closing(_open(path, write=True)) as db:
            _schema(db)
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT * FROM recipes WHERE recipe_id=?", (recipe_id,)).fetchone()
            if current is None:
                if db.execute("SELECT count(*) FROM recipes").fetchone()[0] >= MAX_RECIPES:
                    _deny()
                db.execute("INSERT INTO recipes VALUES (?,?,?,?,?,?)", record)
                status = "SAVED"
            elif current == record:
                status = "ALREADY_SAVED"
            else:
                _deny()
            db.commit()
        return {"status": status, "recipe_id": recipe_id, "workflow": workflow_name(plan),
                "source_sha256": current_source_sha, "plan_sha256": plan_sha,
                "needs_new_preview": True, "customer_ready": False, "release_gate": "HOLD"}
    except (PlanError, OSError, sqlite3.Error, RuntimeError, ValueError, TypeError):
        _deny()


def load_synthetic_workflow(
    catalog_path: Path | str, recipe_id: str, input_root: Path | str,
    *, synthetic: bool = False,
) -> dict:
    """Return owner-approved task/path only after validating the current source.

    This does not issue an execution token or approve a write. The caller MUST
    produce a fresh bounded preview before running a saved recipe.
    """
    if (synthetic is not True or not isinstance(recipe_id, str)
            or _RECIPE.fullmatch(recipe_id) is None):
        _deny()
    try:
        path = _path(catalog_path, exists=True)
        with closing(_open(path, write=False)) as db:
            db.execute("PRAGMA query_only=ON")
            _schema(db)
            record = db.execute(
                "SELECT recipe_id,task,csv_path,source_sha256,plan_sha256,workflow "
                "FROM recipes WHERE recipe_id=?", (recipe_id,),
            ).fetchone()
        if record is None:
            _deny()
        _, task, csv_path, source_sha, plan_sha, workflow = record
        plan, current_source_sha, current_plan_sha = _bound_plan(task, csv_path, input_root)
        if (source_sha != current_source_sha or plan_sha != current_plan_sha
                or workflow_name(plan) != workflow):
            _deny()
        return {"recipe_id": recipe_id, "task": task, "csv_path": csv_path,
                "workflow": workflow, "source_sha256": source_sha,
                "needs_new_preview": True, "write_approved": False,
                "customer_ready": False, "release_gate": "HOLD"}
    except (PlanError, OSError, sqlite3.Error, RuntimeError, ValueError, TypeError):
        _deny()
