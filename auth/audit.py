"""Audit log: authentication, navigation and security events in SQLite.

Design notes
------------
* Separate file ``db/audit.db`` (WAL mode): frequent navigation writes never
  lock the account database, and password backups stay free of log data.
* One table, ``audit_log``, with a ``category`` column:
    ``auth``       login ok/failed, logout, password change
    ``navigation`` tab opened, session ended
    ``security``   access denied, locked account, revoked session,
                   account / role changes, forged tab requests
* Logging never breaks the app: ``log_event`` swallows every exception.
* Never log secrets. Passwords and CAPTCHA answers are never passed in; the
  attempted username is stripped of control characters and length-capped
  (users sometimes type their password into the username field).
* Superadmin policy: every account is logged, superadmin included
  (``LOG_SUPERADMIN_ACTIVITY = True``, the default). Set the environment
  variable ``AUDIT_LOG_SUPERADMIN=0`` to skip a superadmin's own routine
  activity (login, logout, navigation, ...); even then the events in
  ``ALWAYS_LOG_EVENTS`` (account / role management) and anything done against
  the ``superadmin`` account by an anonymous visitor (failed logins, lockouts)
  are still recorded.
* This module imports nothing from ``auth.core`` (core imports this module).
  The superadmin-only read function lives in ``auth.core``
  (``list_audit_events``) so it can use the ``@superadmin`` decorator.
* The log is append-only from the application's point of view (no update or
  delete function exists besides the automatic retention purge). That is not
  tamper-proof against someone with write access to the file itself.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIT_DB_PATH = PROJECT_ROOT / "db" / "audit.db"

CATEGORIES = ("auth", "navigation", "security")
SEVERITIES = ("info", "warning", "critical")

# Record superadmin activity too? Default yes; AUDIT_LOG_SUPERADMIN=0 turns it off.
LOG_SUPERADMIN_ACTIVITY = os.environ.get("AUDIT_LOG_SUPERADMIN", "1").strip() != "0"

# Events that are recorded even when the actor is a superadmin and
# LOG_SUPERADMIN_ACTIVITY is off.
ALWAYS_LOG_EVENTS = frozenset(
    {"user_created", "user_updated", "role_changed", "user_deleted"}
)

# Retention in days per category (navigation is high volume, so shortest).
RETENTION_DAYS = {"auth": 180, "navigation": 30, "security": 365}

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_USERNAME_MAX = 64
_VALUE_MAX = 200
_UA_MAX = 200
_DETAIL_MAX = 2000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,
    category   TEXT NOT NULL CHECK(category IN ('auth','navigation','security')),
    event      TEXT NOT NULL,
    severity   TEXT NOT NULL DEFAULT 'info'
               CHECK(severity IN ('info','warning','critical')),
    user_id    INTEGER NULL,
    username   TEXT NULL,
    role       TEXT NULL,
    session_id TEXT NULL,
    ip         TEXT NULL,
    user_agent TEXT NULL,
    detail     TEXT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
CREATE INDEX IF NOT EXISTS idx_audit_cat_ts ON audit_log(category, ts);
CREATE INDEX IF NOT EXISTS idx_audit_username ON audit_log(username);
"""


def _connect() -> sqlite3.Connection:
    AUDIT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(AUDIT_DB_PATH, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(_SCHEMA)
    return con


def _clean(value, limit: int = _VALUE_MAX) -> str | None:
    """Strip control characters (log injection) and cap the length."""
    if value is None:
        return None
    text = _CONTROL_RE.sub(" ", str(value)).strip()
    return text[:limit]


def _clean_detail(detail) -> str | None:
    if not detail:
        return None

    def walk(obj):
        if isinstance(obj, dict):
            return {str(_clean(k, 60)): walk(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [walk(v) for v in obj]
        if isinstance(obj, (bool, int, float)) or obj is None:
            return obj
        return _clean(obj)

    text = json.dumps(walk(detail), ensure_ascii=False, default=str)
    if len(text) > _DETAIL_MAX:
        text = json.dumps({"truncated": True})
    return text


def client_ip(http_conn) -> str | None:
    """Best-effort client IP from a Starlette connection.

    ``X-Forwarded-For`` is spoofable unless a trusted reverse proxy sets it,
    so it is only honoured when the env var ``TRUST_PROXY_HEADERS=1``.
    """
    try:
        if os.environ.get("TRUST_PROXY_HEADERS", "").strip() == "1":
            forwarded = http_conn.headers.get("x-forwarded-for")
            if forwarded:
                return _clean(forwarded.split(",")[0], 64)
        client = http_conn.client
        return _clean(client.host, 64) if client else None
    except Exception:
        return None


def session_meta(session) -> dict:
    """Session id / IP / user-agent for a Shiny session (never raises)."""
    meta = {"sid": None, "ip": None, "ua": None}
    try:
        meta["sid"] = _clean(session.id, 64)
    except Exception:
        pass
    try:
        conn = session.http_conn
        meta["ip"] = client_ip(conn)
        meta["ua"] = _clean(conn.headers.get("user-agent"), _UA_MAX)
    except Exception:
        pass
    return meta


def log_event(
    category: str,
    event: str,
    *,
    user: dict | None = None,
    username: str | None = None,
    severity: str = "info",
    detail: dict | None = None,
    session_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Record one event. Never raises.

    ``user`` is the acting (authenticated) account, or None for an anonymous
    actor. ``username`` is used when there is no ``user`` (failed login: the
    typed name). Session fields default to the keys ``sid``/``ip``/``ua`` that
    app.py attaches to the session user dict.
    """
    try:
        if category not in CATEGORIES or severity not in SEVERITIES:
            return
        role = user.get("role") if user else None
        if (
            role == "superadmin"
            and not LOG_SUPERADMIN_ACTIVITY
            and event not in ALWAYS_LOG_EVENTS
        ):
            return  # opt-out mode: superadmin's own routine activity is skipped

        user = user or {}
        name = _clean(user.get("username") or username, _USERNAME_MAX)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        con = _connect()
        try:
            con.execute(
                "INSERT INTO audit_log "
                "(ts,category,event,severity,user_id,username,role,session_id,ip,user_agent,detail) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ts,
                    category,
                    _clean(event, 64),
                    severity,
                    user.get("id"),
                    name,
                    role,
                    _clean(session_id or user.get("sid"), 64),
                    _clean(ip or user.get("ip"), 64),
                    _clean(user_agent or user.get("ua"), _UA_MAX),
                    _clean_detail(detail),
                ),
            )
            con.commit()
        finally:
            con.close()
    except Exception:
        pass


def query_events(
    category: str | None = None,
    severity: str | None = None,
    username: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """Return newest-first events. No permission check here: use
    ``auth.core.list_audit_events`` (``@superadmin``) from application code."""
    limit = max(1, min(int(limit), 5000))
    where, params = [], []
    if category in CATEGORIES:
        where.append("category=?")
        params.append(category)
    if severity in SEVERITIES:
        where.append("severity=?")
        params.append(severity)
    name = (username or "").strip()
    if name:
        escaped = name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("username LIKE ? ESCAPE '\\'")
        params.append(f"%{escaped}%")
    sql = "SELECT * FROM audit_log"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    con = _connect()
    try:
        return [dict(row) for row in con.execute(sql, params).fetchall()]
    finally:
        con.close()


def purge_old(now: datetime | None = None) -> int:
    """Delete rows older than the per-category retention. Returns row count."""
    now = now or datetime.now(timezone.utc)
    removed = 0
    try:
        con = _connect()
        try:
            for category, days in RETENTION_DAYS.items():
                cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
                cur = con.execute(
                    "DELETE FROM audit_log WHERE category=? AND ts<?", (category, cutoff)
                )
                removed += cur.rowcount
            con.commit()
        finally:
            con.close()
    except Exception:
        pass
    return removed
