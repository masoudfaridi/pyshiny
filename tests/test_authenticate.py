"""Authentication and default seeded accounts."""
from __future__ import annotations

import sqlite3

import pytest

import auth.core as core


DEFAULTS = [
    ("superadmin", "ChangeMe123!", "superadmin"),
    ("admin", "Admin123!", "admin"),
    ("user", "User123!", "user"),
    ("guest", "Guest123!", "guest"),
]


class TestSeededAccounts:
    @pytest.mark.parametrize("username,password,role", DEFAULTS)
    def test_default_login(self, isolated_db, username, password, role):
        session = core.authenticate(username, password)
        assert session is not None
        assert session["username"] == username
        assert session["role"] == role
        assert session["is_active"] == 1
        assert "id" in session
        assert "password_hash" not in session  # never leak hash into session

    def test_wrong_password(self, isolated_db):
        assert core.authenticate("superadmin", "wrong-password") is None

    def test_unknown_user(self, isolated_db):
        assert core.authenticate("nosuchuser", "whatever12") is None

    def test_strips_username_whitespace(self, isolated_db):
        session = core.authenticate("  admin  ", "Admin123!")
        assert session is not None
        assert session["username"] == "admin"

    def test_empty_credentials(self, isolated_db):
        assert core.authenticate("", "") is None
        assert core.authenticate(None, None) is None  # type: ignore[arg-type]


class TestInactiveAndExpired:
    def test_inactive_user_cannot_login(self, isolated_db):
        with sqlite3.connect(core.DB_PATH) as con:
            con.execute("UPDATE users SET is_active=0 WHERE username='user'")
            con.commit()
        assert core.authenticate("user", "User123!") is None

    def test_expired_user_cannot_login(self, isolated_db):
        with sqlite3.connect(core.DB_PATH) as con:
            con.execute(
                "UPDATE users SET expire_date='2000-01-01' WHERE username='user'"
            )
            con.commit()
        assert core.authenticate("user", "User123!") is None

    def test_superadmin_ignores_expiry_column(self, isolated_db):
        # Even if expire_date is set in DB, authenticate treats non-superadmin
        # expiry only; superadmin path skips expiry check.
        with sqlite3.connect(core.DB_PATH) as con:
            con.execute(
                "UPDATE users SET expire_date='2000-01-01' WHERE username='superadmin'"
            )
            con.commit()
        session = core.authenticate("superadmin", "ChangeMe123!")
        assert session is not None

    def test_future_expiry_allows_login(self, isolated_db):
        with sqlite3.connect(core.DB_PATH) as con:
            con.execute(
                "UPDATE users SET expire_date='2099-06-01' WHERE username='user'"
            )
            con.commit()
        assert core.authenticate("user", "User123!") is not None


class TestInitDbIdempotent:
    def test_second_init_keeps_users(self, isolated_db):
        with sqlite3.connect(core.DB_PATH) as con:
            count = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        assert count >= 4
        core.init_db()
        with sqlite3.connect(core.DB_PATH) as con:
            count2 = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        assert count2 == count
