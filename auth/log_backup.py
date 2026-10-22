"""Backup and restore of the audit-log database (``db/audit.db``).

Layout (next to the database, so a Docker ``db/`` volume keeps it all)::

    db/log_backups/                       manual / prerestore / uploaded backups
    db/log_backups/auto/                  automatic backups taken BEFORE a purge

File names: ``audit-YYYYMMDD-HHMMSS[-manual|-auto|-prerestore|-uploaded].db``.

* ``auto``  - made by ``audit.purge_old()`` right before old rows are deleted by
  the automatic retention clean-up. They live in their own folder; only the
  newest ``keep`` of them are kept (setting ``purge_backup_keep``).
* ``manual`` - made by a Superadmin from the Logs tab.
* ``prerestore`` - safety copy of the current logs, made before a restore.
* ``uploaded`` - a file a Superadmin imported (validated first).

Restore does NOT swap the file under the running application: the rows of the
backup replace the rows of ``audit_log`` inside one transaction (the retention
settings stay as they are). That also works for backups with another page
size and while other sessions keep writing. A backup is accepted only when it
is a healthy SQLite file with an ``audit_log`` table that has the expected
columns.

No permission checks here: application code uses the ``@superadmin`` wrappers
in ``auth.core`` (they also write the audit entries). This module imports
nothing from ``auth.core`` / ``auth.audit`` (``audit`` imports this module).
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from auth import backup as engine
from i18n import t

KINDS = ("manual", "auto", "prerestore", "uploaded")
AUTO_SUBDIR = "auto"
_COLUMNS = (
    "id", "ts", "category", "event", "severity", "user_id", "username", "role",
    "session_id", "ip", "user_agent", "detail",
)


def _validate(path: Path) -> None:
    try:
        with closing(engine._check_integrity(path)) as con:
            columns = {row[1] for row in con.execute("PRAGMA table_info(audit_log)").fetchall()}
            if not set(_COLUMNS) <= columns:
                raise ValueError(t("err_backup_invalid"))
    except sqlite3.DatabaseError as exc:
        raise ValueError(t("err_backup_invalid")) from exc


SPEC = engine.Spec(
    prefix="audit",
    folder="log_backups",
    kinds=KINDS,
    validate=_validate,
    subdirs={"auto": AUTO_SUBDIR},
)


def is_valid_name(name) -> bool:
    return engine.valid_name(SPEC, name)


def create(db_path: Path, kind: str = "manual") -> dict:
    return engine.engine_create(SPEC, db_path, kind)


def list_backups(db_path: Path) -> list[dict]:
    return engine.engine_list(SPEC, db_path)


def delete(db_path: Path, name: str) -> None:
    engine.engine_delete(SPEC, db_path, name)


def read_bytes(db_path: Path, name: str) -> bytes:
    return engine.engine_read(SPEC, db_path, name)


def import_bytes(db_path: Path, data: bytes) -> dict:
    return engine.engine_import(SPEC, db_path, data)


def auto_folder(db_path: Path) -> Path:
    """Folder of the automatic (pre-purge) backups."""
    return engine.folder_for(SPEC, db_path, "auto")


def create_auto(db_path: Path, keep: int) -> dict:
    """Automatic backup before a purge; afterwards only the newest ``keep`` stay."""
    info = create(db_path, "auto")
    autos = sorted(
        (p for p in auto_folder(db_path).iterdir() if p.is_file() and is_valid_name(p.name)),
        key=lambda p: p.name,
        reverse=True,
    )
    for old in autos[max(1, int(keep)):]:
        old.unlink(missing_ok=True)
    return info


def stats(db_path: Path) -> dict:
    """``{"count": n, "bytes": total size of all log backups}``."""
    items = list_backups(db_path)
    return {"count": len(items), "bytes": sum(item["size"] for item in items)}


def restore(db_path: Path, name: str, prepare=None) -> dict:
    """Replace the logs with the rows of backup ``name``.

    ``prepare()`` (optional) makes sure the live database has its schema.
    A ``-prerestore`` safety copy is made first. Returns
    ``{"restored": info, "safety": info, "rows": n}``.
    """
    source = engine.path_of(SPEC, db_path, name)
    _validate(source)
    if prepare is not None:
        prepare()
    safety = create(db_path, "prerestore")
    columns = ", ".join(_COLUMNS)
    con = sqlite3.connect(Path(db_path).resolve().as_uri(), uri=True, timeout=10)
    try:
        con.execute("ATTACH DATABASE ? AS bk", (f"{source.resolve().as_uri()}?mode=ro",))
        try:
            con.execute("BEGIN IMMEDIATE")
            con.execute("DELETE FROM main.audit_log")
            con.execute(
                f"INSERT INTO main.audit_log ({columns}) SELECT {columns} FROM bk.audit_log"
            )
            con.commit()
        except sqlite3.Error as exc:
            con.rollback()
            raise ValueError(t("err_backup_invalid")) from exc
        rows = con.execute("SELECT COUNT(*) FROM main.audit_log").fetchone()[0]
        con.execute("DETACH DATABASE bk")
    finally:
        con.close()
    return {"restored": engine._info(SPEC, source), "safety": safety, "rows": rows}
