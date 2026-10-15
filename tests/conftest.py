"""Shared fixtures: isolated SQLite DB, role contexts, and path setup."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure project root is importable as `auth`, `tabs`, `app`.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def isolated_audit_db(tmp_path, monkeypatch):
    """Every test writes audit events to its own temp file, never db/audit.db."""
    from auth import audit

    monkeypatch.setattr(audit, "AUDIT_DB_PATH", tmp_path / "audit.db")
    yield audit


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    """Point auth.core.DB_PATH at a fresh temp database and seed defaults.

    The production module calls ``init_db()`` at import time against the real
    ``db/auth.db``. Every test that mutates users must use this fixture so the
    shared file is never touched.
    """
    import auth.core as core

    db_path = tmp_path / "auth.db"
    monkeypatch.setattr(core, "DB_PATH", db_path)
    # Reset in-process rate-limit state between tests.
    with core._login_lock:
        core._login_failures.clear()
    core.init_db()
    yield db_path
    with core._login_lock:
        core._login_failures.clear()


@pytest.fixture()
def superadmin_ctx(isolated_db):
    """Authenticate as the seeded superadmin inside a user_context."""
    import auth.core as core

    user = core.authenticate("superadmin", "ChangeMe123!")
    assert user is not None
    with core.user_context(user):
        yield user


@pytest.fixture()
def admin_ctx(isolated_db):
    import auth.core as core

    user = core.authenticate("admin", "Admin123!")
    assert user is not None
    with core.user_context(user):
        yield user


@pytest.fixture()
def user_ctx(isolated_db):
    import auth.core as core

    user = core.authenticate("user", "User123!")
    assert user is not None
    with core.user_context(user):
        yield user


@pytest.fixture()
def guest_ctx(isolated_db):
    import auth.core as core

    user = core.authenticate("guest", "Guest123!")
    assert user is not None
    with core.user_context(user):
        yield user


@pytest.fixture()
def anonymous_ctx(isolated_db):
    """No authenticated user (guest role by default)."""
    import auth.core as core

    with core.user_context(None):
        yield None
