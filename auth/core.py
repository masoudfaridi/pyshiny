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

from auth import audit, backup, log_backup
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

# Identification code: unique per account. ``generic`` (default) accepts 4-20
# letters / digits / ``-`` / ``_``; ``national_ir`` accepts only a valid
# 10-digit Iranian national code (checksum verified). Set it with the
# environment variable ID_CODE_MODE.
ID_CODE_MODE = os.environ.get("ID_CODE_MODE", "generic").strip().lower()
ID_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{3,19}$")
EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*\.[A-Za-z]{2,}$"
)
EMAIL_MAX_LEN = 254
PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")
# Persian (U+06F0..) and Arabic-Indic (U+0660..) digits -> ASCII digits.
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
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


def _ascii_digits(value) -> str:
    return str(value or "").translate(_DIGITS).strip()


def _valid_iranian_national_code(code: str) -> bool:
    """Checksum of the 10-digit Iranian national code."""
    if not re.fullmatch(r"[0-9]{10}", code) or len(set(code)) == 1:
        return False
    total = sum(int(code[i]) * (10 - i) for i in range(9))
    remainder = total % 11
    check = int(code[9])
    return check == remainder if remainder < 2 else check == 11 - remainder


def validate_id_code(value: str) -> str:
    """Normalize (ASCII digits, upper case) and validate an identification code.

    Uniqueness is enforced by the database (unique index) and reported by
    ``create_user`` / ``update_user`` as ``ValueError(err_id_code_exists)``.
    """
    code = _ascii_digits(value).upper()
    if not code:
        raise ValueError(t("err_id_code_required"))
    if ID_CODE_MODE == "national_ir":
        if not _valid_iranian_national_code(code):
            raise ValueError(t("err_id_code_national"))
    elif not ID_CODE_RE.fullmatch(code):
        raise ValueError(t("err_id_code_format"))
    return code


def validate_email(value: str) -> str:
    """Normalize (trimmed, lower case) and validate an e-mail address."""
    email = str(value or "").strip().lower()
    if not email:
        raise ValueError(t("err_email_required"))
    if len(email) > EMAIL_MAX_LEN or not EMAIL_RE.fullmatch(email):
        raise ValueError(t("err_email_format"))
    return email


def validate_phone(value: str) -> str:
    """Normalize and validate a phone number (7-15 digits, optional leading +).

    Spaces, dashes, dots and brackets are removed and Persian digits are
    converted; ``00`` at the start becomes ``+``.
    """
    phone = re.sub(r"[\s().-]", "", _ascii_digits(value))
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    if not phone:
        raise ValueError(t("err_phone_required"))
    if not PHONE_RE.fullmatch(phone):
        raise ValueError(t("err_phone_format"))
    return phone


def _raise_if_id_code_taken(exc: sqlite3.IntegrityError) -> None:
    """Turn the unique-index violation into a friendly ValueError (else re-raise)."""
    if "id_code" in str(exc):
        raise ValueError(t("err_id_code_exists")) from exc
    raise exc


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
    keys = row.keys()
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "is_active": int(row["is_active"]),
        "expire_date": row["expire_date"],
        "id_code": row["id_code"] if "id_code" in keys else None,
        "email": row["email"] if "email" in keys else None,
        "phone": row["phone"] if "phone" in keys else None,
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


def _migrate_schema(con: sqlite3.Connection) -> None:
    """Create / upgrade the ``users`` table (no default accounts are seeded here).

    Also used after a restore, so a backup taken with an older schema gets the
    newer columns (``id_code``, ``email``, ``phone``) and the unique index.
    """
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('superadmin','admin','user','guest')),
            is_active INTEGER NOT NULL DEFAULT 1,
            expire_date TEXT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            id_code TEXT NULL,
            email TEXT NULL,
            phone TEXT NULL
        )
        """
    )

    columns = {row[1] for row in con.execute("PRAGMA table_info(users)").fetchall()}
    for column in ("expire_date", "id_code", "email", "phone"):
        if column not in columns:
            con.execute(f"ALTER TABLE users ADD COLUMN {column} TEXT NULL")

    # NULL codes (accounts created before this field existed) may repeat;
    # every real code must be unique.
    con.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_id_code "
        "ON users(id_code) WHERE id_code IS NOT NULL"
    )
    con.execute("UPDATE users SET expire_date=NULL WHERE role='superadmin'")
    con.commit()


def init_db() -> None:
    """Create the authentication schema and migrate older database files."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as con:
        _migrate_schema(con)

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
            "SELECT id, username, role, is_active, expire_date, id_code, email, phone "
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
            "SELECT id, username, password_hash, role, is_active, expire_date, "
            "id_code, email, phone FROM users WHERE username=?",
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
def verify_own_password(password: str) -> bool:
    """True if ``password`` is the password of the CURRENT (signed-in) user.

    Used by ``@confirm_with_password``. It can only ever check the account of
    the user in ``user_context`` -- there is no way to test another account's
    password through it. Failed attempts are rate limited by the caller.
    """
    current = current_user()
    with sqlite3.connect(DB_PATH) as con:
        row = con.execute(
            "SELECT password_hash FROM users WHERE id=? AND is_active=1",
            (current["id"],),
        ).fetchone()
    return bool(password) and row is not None and _verify_password(password, row[0])


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


@guest
def update_own_profile(email: str, phone: str) -> None:
    """Change the e-mail and phone of the signed-in account.

    The identification code is NOT editable here: only a Superadmin can
    change it (user management).
    """
    current = current_user()
    if current is None:
        raise PermissionError(t("err_auth_required"))
    email = validate_email(email)
    phone = validate_phone(phone)

    with sqlite3.connect(DB_PATH) as con:
        cursor = con.execute(
            "UPDATE users SET email=?, phone=? WHERE id=? AND is_active=1",
            (email, phone, current["id"]),
        )
        con.commit()
    if cursor.rowcount == 0:
        raise ValueError(t("err_user_not_found"))
    audit.log_event(
        "auth", "profile_updated", user=current, detail={"fields": ["email", "phone"]}
    )


@superadmin
def create_user(
    username: str,
    password: str,
    role: str,
    expire_date: str | None = None,
    *,
    id_code: str,
    email: str,
    phone: str,
) -> None:
    """Create a new account. Only Superadmin users may call this function.

    ``id_code`` (unique), ``email`` and ``phone`` are required and validated;
    see ``validate_id_code`` / ``validate_email`` / ``validate_phone``.
    """
    username = validate_username(username)
    # Superadmin-assigned passwords: length bounds only (no complexity rules).
    password = validate_password(password, strict=False)
    if role not in ROLE_LEVELS:
        raise ValueError(t("err_invalid_role"))
    expire_date = _normalize_expiry(expire_date, role)
    id_code = validate_id_code(id_code)
    email = validate_email(email)
    phone = validate_phone(phone)

    with sqlite3.connect(DB_PATH) as con:
        try:
            con.execute(
                "INSERT INTO users(username,password_hash,role,expire_date,id_code,email,phone) "
                "VALUES(?,?,?,?,?,?,?)",
                (username, _hash_password(password), role, expire_date, id_code, email, phone),
            )
        except sqlite3.IntegrityError as exc:
            _raise_if_id_code_taken(exc)
        con.commit()
    audit.log_event(
        "security",
        "user_created",
        user=current_user(),
        severity="critical" if role == "superadmin" else "info",
        detail={
            "target": username,
            "role": role,
            "expire_date": expire_date,
            "id_code": id_code,
        },
    )


@superadmin
def list_users() -> list[dict]:
    """Return all users. Only Superadmin users may call this function."""
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT id, username, role, is_active, expire_date, created_at, "
            "id_code, email, phone FROM users ORDER BY id"
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
    *,
    id_code: str | None = None,
    email: str | None = None,
    phone: str | None = None,
) -> None:
    """Update account details. Only Superadmin users may call this function.

    ``id_code`` / ``email`` / ``phone``: ``None`` keeps the stored value; any
    other value (an empty string included) is validated and saved, so a
    required field cannot be blanked.
    """
    username = validate_username(username)
    if role not in ROLE_LEVELS:
        raise ValueError(t("err_invalid_role"))
    if new_password:
        # Superadmin-assigned passwords: length bounds only.
        new_password = validate_password(new_password, strict=False)
    expire_date = _normalize_expiry(expire_date, role)
    if id_code is not None:
        id_code = validate_id_code(id_code)
    if email is not None:
        email = validate_email(email)
    if phone is not None:
        phone = validate_phone(phone)

    with sqlite3.connect(DB_PATH) as con:
        current = con.execute(
            "SELECT role, is_active, username, expire_date, id_code, email, phone "
            "FROM users WHERE id=?",
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

        new_id_code = current[4] if id_code is None else id_code
        new_email = current[5] if email is None else email
        new_phone = current[6] if phone is None else phone

        fields = {
            "username": username,
            "role": role,
            "is_active": int(is_active),
            "expire_date": expire_date,
            "id_code": new_id_code,
            "email": new_email,
            "phone": new_phone,
        }
        if new_password:
            fields["password_hash"] = _hash_password(new_password)
        assignments = ", ".join(f"{column}=?" for column in fields)
        try:
            con.execute(
                f"UPDATE users SET {assignments} WHERE id=?",
                (*fields.values(), user_id),
            )
        except sqlite3.IntegrityError as exc:
            _raise_if_id_code_taken(exc)
        con.commit()

    changes = {}
    for field, old, new in (
        ("username", current[2], username),
        ("role", current[0], role),
        ("is_active", int(current[1]), int(is_active)),
        ("expire_date", current[3], expire_date),
        ("id_code", current[4], new_id_code),
    ):
        if old != new:
            changes[field] = [old, new]
    # E-mail / phone are personal data: the log records THAT they changed, not the values.
    for field, old, new in (("email", current[5], new_email), ("phone", current[6], new_phone)):
        if old != new:
            changes[field] = "changed"
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


@superadmin
def get_audit_settings() -> dict:
    """Retention days per category and the automatic-purge interval (hours)."""
    return audit.get_settings()


@superadmin
def update_audit_settings(values: dict) -> dict:
    """Validate and save the audit settings. Raises ValueError on bad values."""
    changes = audit.save_settings(values)
    if changes:
        audit.log_event(
            "security",
            "audit_settings_changed",
            user=current_user(),
            severity="warning",
            detail={"changes": changes},
        )
    return audit.get_settings()


@superadmin
def audit_log_counts() -> dict:
    """Stored row count per category."""
    return audit.counts()


@superadmin
def audit_log_size_mb() -> float:
    """Total on-disk size of all logs (``db/audit.db``) in megabytes."""
    return audit.size_mb()


@superadmin
def clear_audit_logs(category: str | None = None) -> int:
    """Delete one category's rows (``category=None`` deletes everything).

    The deletion itself is recorded *afterwards* in the Security log, so even
    "clear all" leaves one row saying who wiped what and how many rows.
    """
    deleted = audit.clear(category)
    audit.log_event(
        "security",
        "audit_cleared",
        user=current_user(),
        severity="critical",
        detail={"scope": category or "all", "deleted": deleted},
    )
    return deleted


# --------------------------------------------------------------------------
# Backup / restore of the accounts database (logic in auth/backup.py)
# --------------------------------------------------------------------------
@superadmin
def create_backup() -> dict:
    """Save a consistent copy of the accounts database. Returns the backup info."""
    info = backup.create(DB_PATH, "manual")
    audit.log_event(
        "security", "accounts_backup_created", user=current_user(),
        detail={"backup": info["name"], "size": info["size"]},
    )
    return info


@superadmin
def list_backups() -> list[dict]:
    """All account-database backups, newest first."""
    return backup.list_backups(DB_PATH)


@superadmin
def restore_backup(name: str) -> dict:
    """Replace the accounts database with backup ``name`` (a safety copy of the
    current database is made first). Returns ``{"restored", "safety", "users"}``."""
    result = backup.restore(DB_PATH, name, migrate=_migrate_schema)
    with _login_lock:
        _login_failures.clear()  # old lockouts belong to the old data
    audit.log_event(
        "security", "accounts_backup_restored", user=current_user(), severity="critical",
        detail={
            "backup": result["restored"]["name"],
            "safety_backup": result["safety"]["name"],
            "users": result["users"],
        },
    )
    return result


@superadmin
def delete_backup(name: str) -> None:
    """Delete one backup file."""
    backup.delete(DB_PATH, name)
    audit.log_event(
        "security", "accounts_backup_deleted", user=current_user(),
        severity="warning", detail={"backup": name},
    )


@superadmin
def read_backup(name: str) -> bytes:
    """Raw bytes of a backup (for download). The file holds password hashes."""
    data = backup.read_bytes(DB_PATH, name)
    audit.log_event(
        "security", "accounts_backup_downloaded", user=current_user(),
        severity="warning", detail={"backup": name, "size": len(data)},
    )
    return data


@superadmin
def import_backup(data: bytes) -> dict:
    """Validate an uploaded database file and store it as a new backup."""
    info = backup.import_bytes(DB_PATH, data)
    audit.log_event(
        "security", "accounts_backup_imported", user=current_user(),
        severity="warning", detail={"backup": info["name"], "size": info["size"]},
    )
    return info


# --------------------------------------------------------------------------
# Audit-log database: backup / restore, user behaviour analytics
# --------------------------------------------------------------------------
@superadmin
def audit_analytics(**filters) -> dict:
    """User-behaviour report (see ``audit.analytics`` for the filters)."""
    return audit.analytics(**filters)


@superadmin
def audit_known_users() -> list[str]:
    """Account names that appear in the logs (for the analytics user filter)."""
    return audit.known_users()


@superadmin
def create_log_backup() -> dict:
    """Save a consistent copy of the log database (``db/log_backups/``)."""
    audit._connect().close()  # make sure the database file and its table exist
    info = log_backup.create(audit.AUDIT_DB_PATH, "manual")
    audit.log_event(
        "security", "audit_backup_created", user=current_user(),
        detail={"backup": info["name"], "size": info["size"]},
    )
    return info


@superadmin
def list_log_backups() -> list[dict]:
    """Log backups (manual, automatic, imported ...), newest first."""
    return log_backup.list_backups(audit.AUDIT_DB_PATH)


@superadmin
def log_backup_stats() -> dict:
    """``{"count": n, "bytes": size}`` of all log backups."""
    return log_backup.stats(audit.AUDIT_DB_PATH)


@superadmin
def restore_log_backup(name: str) -> dict:
    """Replace the stored logs with backup ``name`` (a safety copy is made first)."""
    result = audit.restore_logs(name)
    # Written AFTER the restore, so this entry survives it.
    audit.log_event(
        "security", "audit_backup_restored", user=current_user(), severity="critical",
        detail={
            "backup": result["restored"]["name"],
            "safety_backup": result["safety"]["name"],
            "rows": result["rows"],
        },
    )
    return result


@superadmin
def delete_log_backup(name: str) -> None:
    """Delete one log backup file."""
    log_backup.delete(audit.AUDIT_DB_PATH, name)
    audit.log_event(
        "security", "audit_backup_deleted", user=current_user(),
        severity="warning", detail={"backup": name},
    )


@superadmin
def read_log_backup(name: str) -> bytes:
    """Raw bytes of a log backup (for download)."""
    data = log_backup.read_bytes(audit.AUDIT_DB_PATH, name)
    audit.log_event(
        "security", "audit_backup_downloaded", user=current_user(),
        severity="warning", detail={"backup": name, "size": len(data)},
    )
    return data


@superadmin
def import_log_backup(data: bytes) -> dict:
    """Validate an uploaded log database and store it as a new backup."""
    info = log_backup.import_bytes(audit.AUDIT_DB_PATH, data)
    audit.log_event(
        "security", "audit_backup_imported", user=current_user(),
        severity="warning", detail={"backup": info["name"], "size": info["size"]},
    )
    return info


init_db()
