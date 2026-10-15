"""Authentication, password hashing, account expiration, rate limits, and RBAC."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date
from functools import wraps
from pathlib import Path

from auth import audit
from i18n import t

# Project root is one level above this package (auth/).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "auth.db"

# Higher numbers represent higher privileges.
ROLE_LEVELS = {
    "guest": 0,
    "user": 1,
    "admin": 2,
    "superadmin": 3,
}

USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
PASSWORD_MIN_LEN = 8
PASSWORD_MAX_LEN = 128

# Login brute-force protection (in-process; resets on app restart).
LOGIN_MAX_FAILURES = 5
LOGIN_LOCKOUT_SECONDS = 300
_login_failures: dict[str, list[float]] = {}
_login_lock = threading.Lock()

# Store the authenticated user for the current Shiny server execution context.
_current_user: ContextVar[dict | None] = ContextVar("current_user", default=None)


_PBKDF2_ITERATIONS = 600_000  # OWASP (2023+) minimum recommendation for PBKDF2-SHA256


def _hash_password(password: str, salt: bytes | None = None) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256 and a random salt.

    The iteration count is embedded in the stored string, so raising
    ``_PBKDF2_ITERATIONS`` in the future stays backward compatible with
    hashes generated under the old count -- ``_verify_password`` always
    reads the iteration count back out of the stored value instead of
    assuming the current constant.
    """
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


# Precomputed dummy hash so missing-user paths spend similar time to real verifies.
_DUMMY_PASSWORD_HASH = _hash_password("timing-protection-dummy-value")


def _verify_password(password: str, encoded: str) -> bool:
    """Verify a password against the stored PBKDF2 representation."""
    try:
        scheme, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        ).hex()
        return hmac.compare_digest(candidate, digest_hex)
    except (ValueError, TypeError):
        return False


def validate_username(username: str) -> str:
    """Normalize and validate a username."""
    username = (username or "").strip()
    if not USERNAME_RE.fullmatch(username):
        raise ValueError(t("err_username_format"))
    return username


def validate_password(
    password: str,
    *,
    strict: bool = False,
    field_name: str | None = None,
) -> str:
    """Validate password length and optional complexity rules.

    Superadmin-assigned passwords use strict=False (length only).
    Self-service password changes use strict=True.
    """
    field_name = field_name or t("field_password")
    if not password:
        raise ValueError(t("err_password_required", field=field_name))
    if len(password) < PASSWORD_MIN_LEN:
        raise ValueError(
            t("err_password_min", field=field_name, n=PASSWORD_MIN_LEN)
        )
    if len(password) > PASSWORD_MAX_LEN:
        raise ValueError(
            t("err_password_max", field=field_name, n=PASSWORD_MAX_LEN)
        )
    if strict:
        has_letter = any(c.isalpha() for c in password)
        has_digit = any(c.isdigit() for c in password)
        if not (has_letter and has_digit):
            raise ValueError(t("err_password_complexity", field=field_name))
    return password


def _normalize_expiry(expire_date: str | None, role: str) -> str | None:
    """Validate and normalize an optional expiration date for an account."""
    if role == "superadmin":
        return None
    if not expire_date:
        return None
    try:
        parsed = date.fromisoformat(str(expire_date))
    except ValueError as exc:
        raise ValueError(t("err_expiry_format")) from exc
    return parsed.isoformat()


def _is_expired(expire_date: str | None) -> bool:
    """Return True when an account expiration date has already passed."""
    if not expire_date:
        return False
    return date.today() > date.fromisoformat(expire_date)


def _session_dict(row: sqlite3.Row | dict) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "is_active": int(row["is_active"]),
        "expire_date": row["expire_date"],
    }


@contextmanager
def user_context(user: dict | None):
    """Temporarily bind an authenticated user to the current execution context."""
    token = _current_user.set(user)
    try:
        yield
    finally:
        _current_user.reset(token)


def current_user() -> dict | None:
    """Return the authenticated user for the current execution context."""
    return _current_user.get()


def current_role() -> str:
    """Return the current user's role or guest for an anonymous context."""
    user = current_user()
    return user["role"] if user else "guest"


def has_role(required_role: str) -> bool:
    """Return True when the authenticated user meets the required role level."""
    user = current_user()
    if user is None or not user.get("is_active"):
        return False
    if user.get("expire_date") and _is_expired(user["expire_date"]):
        return False
    return ROLE_LEVELS.get(user["role"], -1) >= ROLE_LEVELS[required_role]


def require_role(required_role: str):
    """Create a decorator that enforces hierarchical role-based access."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not has_role(required_role):
                audit.log_event(
                    "security",
                    "access_denied",
                    user=current_user(),
                    severity="warning",
                    detail={"function": fn.__name__, "required_role": required_role},
                )
                raise PermissionError(
                    f"Role '{required_role}' is required for {fn.__name__}; "
                    f"current role is '{current_role()}'."
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorator


superadmin = require_role("superadmin")
admin = require_role("admin")
user = require_role("user")
guest = require_role("guest")


def init_db() -> None:
    """Create the authentication schema and migrate older database files."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('superadmin','admin','user','guest')),
                is_active INTEGER NOT NULL DEFAULT 1,
                expire_date TEXT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        columns = {row[1] for row in con.execute("PRAGMA table_info(users)").fetchall()}
        if "expire_date" not in columns:
            con.execute("ALTER TABLE users ADD COLUMN expire_date TEXT NULL")

        con.execute("UPDATE users SET expire_date=NULL WHERE role='superadmin'")
        con.commit()

        defaults = [
            ("superadmin", "ChangeMe123!", "superadmin", None),
            ("admin", "Admin123!", "admin", None),
            ("user", "User123!", "user", None),
            ("guest", "Guest123!", "guest", None),
        ]
        for username, password, role, expire_date in defaults:
            con.execute(
                "INSERT OR IGNORE INTO users "
                "(username,password_hash,role,expire_date) VALUES(?,?,?,?)",
                (username, _hash_password(password), role, expire_date),
            )
        con.commit()


def get_user_by_id(user_id: int) -> dict | None:
    """Load a user row by id. Returns None when missing."""
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT id, username, role, is_active, expire_date "
            "FROM users WHERE id=?",
            (int(user_id),),
        ).fetchone()
        return _session_dict(row) if row else None


def refresh_session_user(session_user: dict | None) -> dict | None:
    """Re-load the user from the database and reject revoked/expired accounts.

    Call this before rendering protected UI or running sensitive actions so a
    disabled, demoted, or expired account cannot keep using a stale session.
    """
    if not session_user or "id" not in session_user:
        return None

    fresh = get_user_by_id(int(session_user["id"]))
    if fresh is None:
        return None
    if not fresh.get("is_active"):
        return None
    if fresh["role"] != "superadmin" and _is_expired(fresh.get("expire_date")):
        return None
    return fresh


def is_login_locked(username: str) -> tuple[bool, int]:
    """Return (locked?, seconds_remaining) for a username."""
    key = (username or "").strip().lower()
    if not key:
        return False, 0
    now = time.time()
    with _login_lock:
        stamps = [t for t in _login_failures.get(key, []) if now - t < LOGIN_LOCKOUT_SECONDS]
        _login_failures[key] = stamps
        if len(stamps) < LOGIN_MAX_FAILURES:
            return False, 0
        oldest = min(stamps)
        remaining = int(LOGIN_LOCKOUT_SECONDS - (now - oldest)) + 1
        return True, max(remaining, 1)


def register_login_failure(username: str) -> bool:
    """Record a failed login attempt for rate limiting.

    Returns True only when this failure is the one that locks the account
    (so the caller can log the lockout once, not on every later attempt).
    """
    key = (username or "").strip().lower()
    if not key:
        return False
    with _login_lock:
        stamps = _login_failures.setdefault(key, [])
        stamps.append(time.time())
        # Keep the window bounded.
        cutoff = time.time() - LOGIN_LOCKOUT_SECONDS
        _login_failures[key] = [t for t in stamps if t >= cutoff]
        return len(_login_failures[key]) == LOGIN_MAX_FAILURES


def clear_login_failures(username: str) -> None:
    """Clear failure history after a successful login."""
    key = (username or "").strip().lower()
    with _login_lock:
        _login_failures.pop(key, None)


def authenticate(username: str, password: str) -> dict | None:
    """Authenticate an active, non-expired account and return session fields.

    Always performs a password-hash verification step (including a dummy hash
    when the account is missing/invalid) to reduce username timing leaks.
    """
    username = (username or "").strip()
    password = password or ""

    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT id, username, password_hash, role, is_active, expire_date "
            "FROM users WHERE username=?",
            (username,),
        ).fetchone()

        if (
            not row
            or not row["is_active"]
            or (row["role"] != "superadmin" and _is_expired(row["expire_date"]))
        ):
            _verify_password(password, _DUMMY_PASSWORD_HASH)
            return None

        if not _verify_password(password, row["password_hash"]):
            return None

        return _session_dict(row)


@guest
def change_own_password(current_password: str, new_password: str) -> None:
    """Change the password of the currently authenticated user."""
    current = current_user()
    if current is None:
        raise PermissionError(t("err_auth_required"))

    new_password = validate_password(
        new_password, strict=True, field_name=t("field_new_password")
    )

    with sqlite3.connect(DB_PATH) as con:
        row = con.execute(
            "SELECT password_hash FROM users WHERE id=? AND is_active=1",
            (current["id"],),
        ).fetchone()
        if row is None or not _verify_password(current_password, row[0]):
            audit.log_event(
                "auth", "password_change_failed", user=current, severity="warning",
                detail={"reason": "wrong_current_password"},
            )
            raise ValueError(t("err_current_password"))

        con.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (_hash_password(new_password), current["id"]),
        )
        con.commit()
    audit.log_event("auth", "password_changed", user=current)


@superadmin
def create_user(
    username: str,
    password: str,
    role: str,
    expire_date: str | None = None,
) -> None:
    """Create a new account. Only Superadmin users may call this function."""
    username = validate_username(username)
    # Superadmin-assigned passwords: length bounds only (no complexity rules).
    password = validate_password(password, strict=False)
    if role not in ROLE_LEVELS:
        raise ValueError(t("err_invalid_role"))
    expire_date = _normalize_expiry(expire_date, role)

    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            "INSERT INTO users(username,password_hash,role,expire_date) VALUES(?,?,?,?)",
            (username, _hash_password(password), role, expire_date),
        )
        con.commit()
    audit.log_event(
        "security",
        "user_created",
        user=current_user(),
        severity="critical" if role == "superadmin" else "info",
        detail={"target": username, "role": role, "expire_date": expire_date},
    )


@superadmin
def list_users() -> list[dict]:
    """Return all users. Only Superadmin users may call this function."""
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT id, username, role, is_active, expire_date, created_at "
            "FROM users ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]


@superadmin
def update_user(
    user_id: int,
    username: str,
    role: str,
    is_active: bool,
    new_password: str = "",
    expire_date: str | None = None,
) -> None:
    """Update account details. Only Superadmin users may call this function."""
    username = validate_username(username)
    if role not in ROLE_LEVELS:
        raise ValueError(t("err_invalid_role"))
    if new_password:
        # Superadmin-assigned passwords: length bounds only.
        new_password = validate_password(new_password, strict=False)
    expire_date = _normalize_expiry(expire_date, role)

    with sqlite3.connect(DB_PATH) as con:
        current = con.execute(
            "SELECT role, is_active, username, expire_date FROM users WHERE id=?",
            (user_id,),
        ).fetchone()
        if current is None:
            raise ValueError(t("err_user_not_found"))

        if current[0] == "superadmin" and current[1] and (
            role != "superadmin" or not is_active
        ):
            count = con.execute(
                "SELECT COUNT(*) FROM users WHERE role='superadmin' AND is_active=1"
            ).fetchone()[0]
            if count <= 1:
                raise ValueError(t("err_last_superadmin"))

        if new_password:
            con.execute(
                "UPDATE users SET username=?, role=?, is_active=?, expire_date=?, password_hash=? "
                "WHERE id=?",
                (
                    username,
                    role,
                    int(is_active),
                    expire_date,
                    _hash_password(new_password),
                    user_id,
                ),
            )
        else:
            con.execute(
                "UPDATE users SET username=?, role=?, is_active=?, expire_date=? WHERE id=?",
                (username, role, int(is_active), expire_date, user_id),
            )
        con.commit()

    changes = {}
    for field, old, new in (
        ("username", current[2], username),
        ("role", current[0], role),
        ("is_active", int(current[1]), int(is_active)),
        ("expire_date", current[3], expire_date),
    ):
        if old != new:
            changes[field] = [old, new]
    if new_password:
        changes["password_reset"] = True
    if changes:
        role_changed = "role" in changes
        touches_superadmin = "superadmin" in (current[0], role)
        audit.log_event(
            "security",
            "role_changed" if role_changed else "user_updated",
            user=current_user(),
            severity=(
                "critical"
                if role_changed and touches_superadmin
                else "warning" if role_changed or "password_reset" in changes else "info"
            ),
            detail={"target_id": int(user_id), "target": current[2], "changes": changes},
        )


@superadmin
def delete_user(user_id: int) -> None:
    """Delete an account. Only Superadmin users may call this function."""
    current = current_user()

    if current and int(current["id"]) == int(user_id):
        raise ValueError(t("err_delete_self"))

    with sqlite3.connect(DB_PATH) as con:
        row = con.execute(
            "SELECT role, is_active, username FROM users WHERE id=?", (user_id,)
        ).fetchone()
        if row is None:
            raise ValueError(t("err_user_not_found"))

        if row[0] == "superadmin" and row[1]:
            count = con.execute(
                "SELECT COUNT(*) FROM users WHERE role='superadmin' AND is_active=1"
            ).fetchone()[0]
            if count <= 1:
                raise ValueError(t("err_delete_last_superadmin"))

        con.execute("DELETE FROM users WHERE id=?", (user_id,))
        con.commit()
    audit.log_event(
        "security",
        "user_deleted",
        user=current,
        severity="critical" if row[0] == "superadmin" else "warning",
        detail={"target_id": int(user_id), "target": row[2], "role": row[0]},
    )


@superadmin
def list_audit_events(
    category: str | None = None,
    severity: str | None = None,
    username: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """Return audit events, newest first. Only Superadmin users may call this."""
    return audit.query_events(
        category=category, severity=severity, username=username, limit=limit
    )


init_db()
