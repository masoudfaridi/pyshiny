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
* ``db_size_bytes()`` / ``size_mb()`` report the on-disk size of ``audit.db``
  (shown in the Logs tab); ``clear()`` compacts the file so the number drops.
* All logs live in ONE database file (``audit.db``). ``auth/log_backup.py``
  backs it up / restores it; ``purge_old()`` takes an automatic backup into
  ``db/log_backups/auto/`` BEFORE it deletes anything.
* ``analytics()`` computes the "user behaviour" report (logins, minutes of use,
  per user and overall) from the same table.
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

from auth import log_backup

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIT_DB_PATH = PROJECT_ROOT / "db" / "audit.db"

CATEGORIES = ("auth", "navigation", "security")
SEVERITIES = ("info", "warning", "critical")

# Record superadmin activity too? Default yes; AUDIT_LOG_SUPERADMIN=0 turns it off.
LOG_SUPERADMIN_ACTIVITY = os.environ.get("AUDIT_LOG_SUPERADMIN", "1").strip() != "0"

# Events that are recorded even when the actor is a superadmin and
# LOG_SUPERADMIN_ACTIVITY is off.
ALWAYS_LOG_EVENTS = frozenset(
    {
        "user_created", "user_updated", "role_changed", "user_deleted",
        "audit_settings_changed", "audit_cleared",
        "reauth_failed", "reauth_blocked_locked", "sensitive_action_confirmed",
        "accounts_backup_created", "accounts_backup_restored",
        "accounts_backup_deleted", "accounts_backup_imported",
        "accounts_backup_downloaded",
        "audit_backup_created", "audit_backup_restored", "audit_backup_deleted",
        "audit_backup_imported", "audit_backup_downloaded", "audit_auto_purged",
    }
)

# Retention / purge settings. The superadmin edits them in the Logs tab; they
# are stored in the ``audit_settings`` table. These are the defaults
# (navigation is high volume, so it is kept the shortest).
DEFAULT_SETTINGS = {
    "retention_days_navigation": 30,
    "retention_days_auth": 180,
    "retention_days_security": 365,
    "purge_interval_hours": 1,  # automatic purge runs at most once per this many hours
    "purge_backup_enabled": 1,  # 1 = back the logs up (db/log_backups/auto/) before an automatic purge
    "purge_backup_keep": 10,    # how many automatic backups to keep (oldest are removed)
}
# Settings an older caller may omit (they keep their stored value).
OPTIONAL_SETTINGS = frozenset({"purge_backup_enabled", "purge_backup_keep"})
SETTING_LIMITS = {  # inclusive (min, max)
    "retention_days_navigation": (1, 3650),
    "retention_days_auth": (1, 3650),
    "retention_days_security": (1, 3650),
    "purge_interval_hours": (1, 168),
    "purge_backup_enabled": (0, 1),
    "purge_backup_keep": (1, 100),
}
_RETENTION_KEY = {
    "navigation": "retention_days_navigation",
    "auth": "retention_days_auth",
    "security": "retention_days_security",
}

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
CREATE TABLE IF NOT EXISTS audit_settings (
    key   TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);
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


def _as_int(value) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError("not a whole number")
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError("not a whole number")
        return int(value)
    if isinstance(value, str):
        return int(value.strip())
    if isinstance(value, int):
        return value
    raise ValueError("not a whole number")


def validate_settings(values: dict) -> dict:
    """Return a clean ``{key: int}`` for every setting, or raise ValueError."""
    clean = {}
    for key, (low, high) in SETTING_LIMITS.items():
        if key not in values:
            if key in OPTIONAL_SETTINGS:
                continue
            raise ValueError(f"{key}: missing")
        try:
            number = _as_int(values[key])
        except (TypeError, ValueError):
            raise ValueError(f"{key}: must be a whole number") from None
        if not low <= number <= high:
            raise ValueError(f"{key}: must be between {low} and {high}")
        clean[key] = number
    return clean


def get_settings() -> dict:
    """Current settings (defaults for anything missing or out of range)."""
    settings = dict(DEFAULT_SETTINGS)
    try:
        con = _connect()
        try:
            rows = con.execute("SELECT key, value FROM audit_settings").fetchall()
        finally:
            con.close()
        for row in rows:
            limits = SETTING_LIMITS.get(row["key"])
            if limits and limits[0] <= row["value"] <= limits[1]:
                settings[row["key"]] = row["value"]
    except Exception:
        pass
    return settings


def save_settings(values: dict) -> dict:
    """Validate and store settings. Returns ``{key: [old, new]}`` of changes.
    No permission check: use ``auth.core.update_audit_settings`` (``@superadmin``)."""
    new = validate_settings(values)
    old = get_settings()
    con = _connect()
    try:
        for key, number in new.items():
            con.execute(
                "INSERT INTO audit_settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, number),
            )
        con.commit()
    finally:
        con.close()
    return {key: [old[key], new[key]] for key in new if old[key] != new[key]}


def counts() -> dict:
    """Number of stored rows per category."""
    result = {category: 0 for category in CATEGORIES}
    try:
        con = _connect()
        try:
            for row in con.execute(
                "SELECT category, COUNT(*) AS n FROM audit_log GROUP BY category"
            ):
                result[row["category"]] = row["n"]
        finally:
            con.close()
    except Exception:
        pass
    return result


def db_size_bytes() -> int:
    """Total size of the audit database on disk, in bytes.

    Counts the main file plus the WAL / shared-memory side files that SQLite
    keeps next to it (``audit.db-wal`` can be a large part of the footprint).
    A missing file counts as 0.
    """
    total = 0
    for suffix in ("", "-wal", "-shm"):
        try:
            total += os.path.getsize(f"{AUDIT_DB_PATH}{suffix}")
        except OSError:
            pass
    return total


def size_mb() -> float:
    """``db_size_bytes()`` in megabytes (1 MB = 1024 * 1024 bytes)."""
    return db_size_bytes() / (1024 * 1024)


def _compact(con: sqlite3.Connection) -> None:
    """Give freed space back to the file system so the reported size shrinks."""
    try:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.execute("VACUUM")
    except sqlite3.Error:
        pass  # compacting is cosmetic; never fail a clean-up because of it


def clear(category: str | None = None) -> int:
    """Delete all rows of one category (or every row when ``category`` is None).
    Returns the number of deleted rows. No permission check: use
    ``auth.core.clear_audit_logs`` (``@superadmin``)."""
    if category is not None and category not in CATEGORIES:
        raise ValueError(f"unknown category: {category}")
    con = _connect()
    try:
        if category is None:
            deleted = con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
            con.execute("DELETE FROM audit_log")
        else:
            deleted = con.execute(
                "SELECT COUNT(*) FROM audit_log WHERE category=?", (category,)
            ).fetchone()[0]
            con.execute("DELETE FROM audit_log WHERE category=?", (category,))
        con.commit()
        _compact(con)
    finally:
        con.close()
    return deleted


def purge_old(now: datetime | None = None) -> int:
    """Delete rows older than the configured per-category retention.

    When something is about to be deleted and ``purge_backup_enabled`` is on, the
    whole log database is first copied to ``db/log_backups/auto/``; if that
    backup fails nothing is deleted (data is never removed without a copy).
    Returns the number of deleted rows.
    """
    now = now or datetime.now(timezone.utc)
    settings = get_settings()
    cutoffs = {
        category: (now - timedelta(days=settings[key])).strftime("%Y-%m-%d %H:%M:%S")
        for category, key in _RETENTION_KEY.items()
    }
    removed = 0
    backup_name = None
    try:
        con = _connect()
        try:
            due = sum(
                con.execute(
                    "SELECT COUNT(*) FROM audit_log WHERE category=? AND ts<?", (category, cutoff)
                ).fetchone()[0]
                for category, cutoff in cutoffs.items()
            )
            if due == 0:
                return 0
            if settings["purge_backup_enabled"]:
                try:
                    backup_name = log_backup.create_auto(
                        AUDIT_DB_PATH, settings["purge_backup_keep"]
                    )["name"]
                except Exception:
                    return 0  # no backup, no deletion
            for category, cutoff in cutoffs.items():
                cur = con.execute(
                    "DELETE FROM audit_log WHERE category=? AND ts<?", (category, cutoff)
                )
                removed += cur.rowcount
            con.commit()
        finally:
            con.close()
    except Exception:
        return removed
    if removed:
        log_event(
            "security", "audit_auto_purged",
            detail={"removed": removed, "backup": backup_name or "disabled"},
        )
    return removed


# --------------------------------------------------------------------------
# Log database backup / restore (files: auth/log_backup.py)
# --------------------------------------------------------------------------
def restore_logs(name: str) -> dict:
    """Replace the stored logs with the rows of backup ``name`` (see log_backup)."""
    result = log_backup.restore(AUDIT_DB_PATH, name, prepare=lambda: _connect().close())
    con = _connect()
    try:
        _compact(con)
    finally:
        con.close()
    return result


# --------------------------------------------------------------------------
# User behaviour analytics
# --------------------------------------------------------------------------
PERIODS = ("24h", "7d", "30d", "90d", "all", "custom")
_PERIOD_DELTA = {
    "24h": timedelta(hours=24), "7d": timedelta(days=7),
    "30d": timedelta(days=30), "90d": timedelta(days=90),
}
# Events that carry ``duration_s`` (how long a signed-in session lasted).
SESSION_END_EVENTS = ("logout", "session_ended", "session_revoked")
_MAX_SESSION_SECONDS = 30 * 24 * 3600  # ignore absurd values
_TS_FMT = "%Y-%m-%d %H:%M:%S"


def _parse_day(value) -> datetime | None:
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def known_users() -> list[str]:
    """Names of accounts that ever appear as the actor of a logged event."""
    con = _connect()
    try:
        return [
            row[0] for row in con.execute(
                "SELECT DISTINCT username FROM audit_log "
                "WHERE user_id IS NOT NULL AND username IS NOT NULL ORDER BY username"
            )
        ]
    finally:
        con.close()


def _json_field(raw, key):
    try:
        data = json.loads(raw) if raw else None
    except ValueError:
        return None
    return data.get(key) if isinstance(data, dict) else None


def analytics(
    period: str = "30d",
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    username: str | None = None,
    role: str | None = None,
    categories=None,
    severity: str | None = None,
    tz_offset_minutes: int = 0,
    now: datetime | None = None,
) -> dict:
    """Descriptive statistics about how accounts use the application.

    Filters: ``period`` (``24h 7d 30d 90d all custom``; ``custom`` uses the
    local calendar days ``date_from`` .. ``date_to`` inclusive), one exact
    ``username``, a ``role``, a subset of ``categories`` (auth / navigation /
    security) and a ``severity``. ``tz_offset_minutes`` (browser offset from
    UTC) only shifts the hour / weekday / day buckets and the displayed times.

    "Usage minutes" are the sum of ``duration_s`` of the events that end a
    session (``logout``, ``session_ended``, ``session_revoked``) inside the
    period; a session that is still open is counted when it ends.
    No permission check: use ``auth.core.audit_analytics`` (``@superadmin``).
    """
    if period not in PERIODS:
        raise ValueError(f"unknown period: {period}")
    offset = max(-14 * 60, min(14 * 60, int(tz_offset_minutes or 0)))
    now = now or datetime.now(timezone.utc)
    cats = list(CATEGORIES) if categories is None else [c for c in categories if c in CATEGORIES]

    start = end = None
    if period in _PERIOD_DELTA:
        start = (now - _PERIOD_DELTA[period]).strftime(_TS_FMT)
        end = (now + timedelta(seconds=1)).strftime(_TS_FMT)
    elif period == "custom":
        first, last = _parse_day(date_from), _parse_day(date_to)
        if first and last and last < first:
            first, last = last, first
        if first:
            start = (first - timedelta(minutes=offset)).strftime(_TS_FMT)
        if last:
            end = (last + timedelta(days=1) - timedelta(minutes=offset)).strftime(_TS_FMT)

    where, params = [], []
    if start:
        where.append("ts>=?"); params.append(start)
    if end:
        where.append("ts<?"); params.append(end)
    name = (username or "").strip()
    if name:
        where.append("username=?"); params.append(name)
    if role:
        where.append("role=?"); params.append(role)
    if severity in SEVERITIES:
        where.append("severity=?"); params.append(severity)
    where.append("category IN (%s)" % ",".join("?" * len(cats)) if cats else "0")
    params += cats
    base = " AND ".join(where)

    def local(ts):
        if not ts:
            return None
        return (datetime.strptime(ts, _TS_FMT) + timedelta(minutes=offset)).strftime(_TS_FMT)

    shift = f"{offset:+d} minutes"
    con = _connect()
    try:
        users: dict[str, dict] = {}
        for row in con.execute(
            "SELECT username, MAX(role) AS role, COUNT(*) AS events, "
            "SUM(event='login_success') AS logins, SUM(event='tab_opened') AS tab_views, "
            "SUM(severity IN ('warning','critical')) AS alerts, "
            "MAX(CASE WHEN event='login_success' THEN ts END) AS last_login, "
            "MAX(ts) AS last_seen, COUNT(DISTINCT substr(ts,1,10)) AS active_days, "
            "COUNT(DISTINCT ip) AS ips "
            f"FROM audit_log WHERE {base} AND user_id IS NOT NULL AND username IS NOT NULL "
            "GROUP BY username",
            params,
        ):
            users[row["username"]] = {
                "username": row["username"], "role": row["role"], "events": row["events"],
                "logins": row["logins"] or 0, "failed_logins": 0,
                "sessions": 0, "total_seconds": 0, "max_seconds": 0,
                "tab_views": row["tab_views"] or 0, "alerts": row["alerts"] or 0,
                "last_login": local(row["last_login"]), "last_seen": local(row["last_seen"]),
                "active_days": row["active_days"], "ips": row["ips"], "top_tab": None,
            }

        failed_total, failed_unknown, failed_reasons = 0, 0, {}
        for row in con.execute(
            f"SELECT username, detail, COUNT(*) AS n FROM audit_log WHERE {base} "
            "AND event='login_failed' GROUP BY username, detail", params,
        ):
            failed_total += row["n"]
            reason = _json_field(row["detail"], "reason") or "unknown"
            failed_reasons[reason] = failed_reasons.get(reason, 0) + row["n"]
            if row["username"] in users:
                users[row["username"]]["failed_logins"] += row["n"]
            else:
                failed_unknown += row["n"]

        marks = ",".join("?" * len(SESSION_END_EVENTS))
        for row in con.execute(
            f"SELECT username, detail FROM audit_log WHERE {base} AND user_id IS NOT NULL "
            f"AND event IN ({marks})", params + list(SESSION_END_EVENTS),
        ):
            seconds = _json_field(row["detail"], "duration_s")
            record = users.get(row["username"])
            if (record is None or isinstance(seconds, bool)
                    or not isinstance(seconds, (int, float))
                    or not 0 <= seconds <= _MAX_SESSION_SECONDS):
                continue
            record["sessions"] += 1
            record["total_seconds"] += seconds
            record["max_seconds"] = max(record["max_seconds"], seconds)

        tab_counts: dict[str, int] = {}
        per_user_tabs: dict[str, dict[str, int]] = {}
        for row in con.execute(
            f"SELECT username, detail, COUNT(*) AS n FROM audit_log WHERE {base} "
            "AND event='tab_opened' GROUP BY username, detail", params,
        ):
            tab = _json_field(row["detail"], "tab") or "?"
            tab_counts[tab] = tab_counts.get(tab, 0) + row["n"]
            bucket = per_user_tabs.setdefault(row["username"], {})
            bucket[tab] = bucket.get(tab, 0) + row["n"]
        for username_, tabs in per_user_tabs.items():
            if username_ in users:
                users[username_]["top_tab"] = max(tabs, key=tabs.get)

        by_category = {c: 0 for c in CATEGORIES}
        for row in con.execute(
            f"SELECT category, COUNT(*) AS n FROM audit_log WHERE {base} GROUP BY category", params
        ):
            by_category[row["category"]] = row["n"]
        top_events = [
            (row["event"], row["n"]) for row in con.execute(
                f"SELECT event, COUNT(*) AS n FROM audit_log WHERE {base} "
                "GROUP BY event ORDER BY n DESC, event LIMIT 10", params,
            )
        ]
        alerts_total = con.execute(
            f"SELECT COUNT(*) FROM audit_log WHERE {base} AND severity IN ('warning','critical')",
            params,
        ).fetchone()[0]

        by_hour = [0] * 24
        for row in con.execute(
            f"SELECT strftime('%H', ts, ?) AS h, COUNT(*) AS n FROM audit_log WHERE {base} GROUP BY h",
            [shift] + params,
        ):
            by_hour[int(row["h"])] = row["n"]
        by_weekday = [0] * 7  # SQLite %w: 0 = Sunday
        for row in con.execute(
            f"SELECT strftime('%w', ts, ?) AS d, COUNT(*) AS n FROM audit_log WHERE {base} GROUP BY d",
            [shift] + params,
        ):
            by_weekday[int(row["d"])] = row["n"]
        by_day = [
            {"day": row["d"], "events": row["n"], "logins": row["l"] or 0}
            for row in con.execute(
                "SELECT strftime('%Y-%m-%d', ts, ?) AS d, COUNT(*) AS n, "
                f"SUM(event='login_success') AS l FROM audit_log WHERE {base} GROUP BY d ORDER BY d",
                [shift] + params,
            )
        ][-60:]
    finally:
        con.close()

    rows = sorted(users.values(), key=lambda r: (-r["total_seconds"], -r["logins"], r["username"]))
    sessions = sum(r["sessions"] for r in rows)
    total_seconds = sum(r["total_seconds"] for r in rows)
    summary = {
        "users": len(rows),
        "events": sum(by_category.values()),
        "logins": sum(r["logins"] for r in rows),
        "failed_logins": failed_total,
        "failed_unknown": failed_unknown,
        "sessions": sessions,
        "total_seconds": total_seconds,
        "avg_session_seconds": (total_seconds / sessions) if sessions else 0,
        "avg_seconds_per_user": (total_seconds / len(rows)) if rows else 0,
        "longest_session_seconds": max((r["max_seconds"] for r in rows), default=0),
        "tab_views": sum(r["tab_views"] for r in rows),
        "alerts": alerts_total,
    }
    return {
        "range": {"from": local(start), "to": local(end), "tz_offset_minutes": offset},
        "summary": summary,
        "users": rows,
        "by_category": by_category,
        "by_hour": by_hour,
        "by_weekday": by_weekday,
        "by_day": by_day,
        "top_tabs": sorted(tab_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10],
        "top_events": top_events,
        "failed_reasons": sorted(failed_reasons.items(), key=lambda kv: (-kv[1], kv[0])),
    }
