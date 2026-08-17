"""Session refresh and get_user_by_id."""
from __future__ import annotations

import sqlite3

import pytest

import auth.core as core


class TestGetUserById:
    def test_found(self, isolated_db):
        session = core.authenticate("admin", "Admin123!")
        row = core.get_user_by_id(session["id"])
        assert row is not None
        assert row["username"] == "admin"
        assert "password_hash" not in row

    def test_missing(self, isolated_db):
        assert core.get_user_by_id(999999) is None


class TestRefreshSessionUser:
    def test_valid_session(self, isolated_db):
        session = core.authenticate("user", "User123!")
        fresh = core.refresh_session_user(session)
        assert fresh is not None
        assert fresh["username"] == "user"
        assert fresh["role"] == "user"

    def test_none_session(self, isolated_db):
        assert core.refresh_session_user(None) is None
        assert core.refresh_session_user({}) is None

    def test_revoked_inactive(self, isolated_db):
        session = core.authenticate("user", "User123!")
        with sqlite3.connect(core.DB_PATH) as con:
            con.execute("UPDATE users SET is_active=0 WHERE id=?", (session["id"],))
            con.commit()
        assert core.refresh_session_user(session) is None

    def test_expired_account(self, isolated_db):
        session = core.authenticate("user", "User123!")
        with sqlite3.connect(core.DB_PATH) as con:
            con.execute(
                "UPDATE users SET expire_date='2000-01-01' WHERE id=?",
                (session["id"],),
            )
            con.commit()
        assert core.refresh_session_user(session) is None

    def test_role_change_reflected(self, isolated_db):
        session = core.authenticate("user", "User123!")
        with sqlite3.connect(core.DB_PATH) as con:
            con.execute(
                "UPDATE users SET role='admin' WHERE id=?", (session["id"],)
            )
            con.commit()
        fresh = core.refresh_session_user(session)
        assert fresh is not None
        assert fresh["role"] == "admin"

    def test_deleted_user(self, isolated_db):
        session = core.authenticate("guest", "Guest123!")
        with sqlite3.connect(core.DB_PATH) as con:
            con.execute("DELETE FROM users WHERE id=?", (session["id"],))
            con.commit()
        assert core.refresh_session_user(session) is None
