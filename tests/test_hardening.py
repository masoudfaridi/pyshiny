"""Regression tests for the security / robustness hardening pass."""
from __future__ import annotations

import asyncio
import os
import shutil
import sqlite3
import stat

import pytest

from tests.conftest import contact


# --------------------------------------------------------------- first run
class TestSeeding:
    def _fresh(self, tmp_path, monkeypatch, **env):
        import auth.core as core

        for key in ("DEMO_ACCOUNTS", "INITIAL_SUPERADMIN_PASSWORD"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setattr(core, "DB_PATH", tmp_path / "auth.db")
        core.init_db()
        with sqlite3.connect(core.DB_PATH) as con:
            names = [r[0] for r in con.execute("SELECT username FROM users ORDER BY id")]
        return core, names

    def test_production_default_is_one_superadmin_with_random_password(self, tmp_path, monkeypatch):
        core, names = self._fresh(tmp_path, monkeypatch)
        assert names == ["superadmin"]
        assert core.authenticate("superadmin", "ChangeMe123!") is None
        secret_file = tmp_path / core.INITIAL_PASSWORD_FILENAME
        assert secret_file.is_file()
        assert stat.S_IMODE(secret_file.stat().st_mode) == 0o600
        password = secret_file.read_text(encoding="utf-8").strip().splitlines()[-1]
        assert core.authenticate("superadmin", password) is not None

    def test_password_from_environment(self, tmp_path, monkeypatch):
        core, names = self._fresh(
            tmp_path, monkeypatch, INITIAL_SUPERADMIN_PASSWORD="anything-goes"
        )
        assert names == ["superadmin"]
        assert core.authenticate("superadmin", "anything-goes") is not None
        assert not (tmp_path / core.INITIAL_PASSWORD_FILENAME).exists()

    def test_demo_accounts_are_opt_in(self, tmp_path, monkeypatch):
        core, names = self._fresh(tmp_path, monkeypatch, DEMO_ACCOUNTS="1")
        assert names == ["superadmin", "admin", "user", "guest"]

    def test_deleted_account_is_not_recreated_on_restart(self, superadmin_ctx):
        import auth.core as core

        admin_id = next(u["id"] for u in core.list_users() if u["username"] == "admin")
        core.delete_user(admin_id)
        core.init_db()  # = application restart
        assert "admin" not in {u["username"] for u in core.list_users()}
        assert core.authenticate("admin", "Admin123!") is None

    def test_password_file_removed_after_superadmin_changes_password(self, tmp_path, monkeypatch):
        core, _ = self._fresh(tmp_path, monkeypatch)
        secret_file = tmp_path / core.INITIAL_PASSWORD_FILENAME
        password = secret_file.read_text(encoding="utf-8").strip().splitlines()[-1]
        person = core.authenticate("superadmin", password)
        with core.user_context(person):
            core.change_own_password(password, "NewPassw0rd")
        assert not secret_file.exists()


# ---------------------------------------------------- session invalidation
class TestSessionVersion:
    def test_other_sessions_end_after_own_password_change(self, isolated_db):
        import auth.core as core

        laptop = core.authenticate("user", "User123!")
        phone = core.authenticate("user", "User123!")
        with core.user_context(laptop):
            core.change_own_password("User123!", "Changed123")
        assert core.refresh_session_user(phone) is None
        assert core.refresh_session_user(laptop) is None  # app.py re-issues its own
        assert core.refresh_session_user({"id": laptop["id"]}) is not None

    def test_superadmin_reset_signs_the_target_out(self, superadmin_ctx):
        import auth.core as core

        victim = core.authenticate("user", "User123!")
        row = next(u for u in core.list_users() if u["username"] == "user")
        core.update_user(row["id"], "user", "user", True, "x" * 8)
        assert core.refresh_session_user(victim) is None

    def test_profile_edit_keeps_the_session(self, superadmin_ctx):
        import auth.core as core

        person = core.authenticate("user", "User123!")
        row = next(u for u in core.list_users() if u["username"] == "user")
        core.update_user(row["id"], "user", "user", True, "", **contact("user"))
        assert core.refresh_session_user(person) is not None


# ------------------------------------------------------------- lockouts
class TestLockoutState:
    def test_checking_unknown_names_stores_nothing(self, isolated_db):
        import auth.core as core

        for i in range(200):
            core.is_login_locked(f"nobody-{i}")
        assert core._login_failures == {}

    def test_keys_are_length_capped(self, isolated_db):
        import auth.core as core

        core.register_login_failure("x" * 10_000)
        assert all(len(k) <= core._LOCKOUT_KEY_MAX for k in core._login_failures)

    def test_change_password_form_is_rate_limited(self, isolated_db):
        import auth.core as core

        person = core.authenticate("user", "User123!")
        with core.user_context(person):
            for _ in range(core.LOGIN_MAX_FAILURES):
                with pytest.raises(ValueError):
                    core.change_own_password("wrong", "Another123")
            assert core.is_login_locked("user")[0]
            with pytest.raises(ValueError):  # even the right password is refused now
                core.change_own_password("User123!", "Another123")

    def test_overlong_credentials_are_rejected_cheaply(self, isolated_db):
        import auth.core as core

        assert core.authenticate("superadmin", "x" * 100_000) is None
        assert core.authenticate("u" * 10_000, "whatever") is None


# ------------------------------------------------------- untrusted backups
class TestBackupValidation:
    def _copy(self, isolated_db, tmp_path):
        target = tmp_path / "candidate.db"
        shutil.copy(isolated_db, target)
        return target

    def test_trigger_in_uploaded_file_is_rejected(self, isolated_db, tmp_path):
        from auth import backup

        bad = self._copy(isolated_db, tmp_path)
        with sqlite3.connect(bad) as con:
            con.execute(
                "CREATE TRIGGER promote AFTER UPDATE ON users BEGIN "
                "UPDATE users SET role='superadmin'; END"
            )
        with pytest.raises(ValueError):
            backup.validate_backup_file(bad)

    def test_unknown_role_is_rejected(self, isolated_db, tmp_path):
        from auth import backup

        bad = tmp_path / "roles.db"
        with sqlite3.connect(bad) as con:
            con.execute(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT,"
                " role TEXT, is_active INTEGER, expire_date TEXT)"
            )
            con.execute("INSERT INTO users VALUES (1,'a','x','superadmin',1,NULL)")
            con.execute("INSERT INTO users VALUES (2,'b','x','root',1,NULL)")
        with pytest.raises(ValueError):
            backup.validate_backup_file(bad)

    def test_clean_copy_is_accepted(self, isolated_db, tmp_path):
        from auth import backup

        backup.validate_backup_file(self._copy(isolated_db, tmp_path))

    def test_backup_files_are_private(self, superadmin_ctx):
        import auth.core as core
        from auth import backup

        info = core.create_backup()
        path = backup.backup_path(core.DB_PATH, info["name"])
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


# --------------------------------------------------------- content tabs
class TestTabGate:
    def test_fail_closed_without_session_function(self):
        from tabs._access import gate

        assert gate(None, "guest")() is False

    @pytest.mark.parametrize(
        "role, min_role, expected",
        [("guest", "superadmin", False), ("admin", "admin", True),
         ("superadmin", "user", True), ("hacker", "guest", False)],
    )
    def test_role_levels(self, role, min_role, expected):
        from tabs._access import gate

        assert gate(lambda: {"role": role}, min_role)() is expected

    def test_signed_out_is_denied(self):
        from tabs._access import gate

        assert gate(lambda: None, "guest")() is False

    @pytest.mark.parametrize("value", [None, "abc", "nan", "inf", float("-inf")])
    def test_finite_rejects_bad_numbers(self, value):
        from tabs._access import finite

        with pytest.raises((TypeError, ValueError)):
            finite(value)


# ------------------------------------------------------- HTTP middleware
def _call(middleware, method="GET", path="/", headers=(), body=b""):
    sent = []

    async def inner(scope, receive, send):
        while True:
            message = await receive()
            if not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        sent.append(message)

    mw = middleware(inner, max_upload_bytes=100)
    scope = {"type": "http", "method": method, "path": path, "headers": list(headers)}
    asyncio.run(mw(scope, receive, send))
    return sent


class TestSecurityMiddleware:
    def test_headers_added(self):
        from security import SecurityMiddleware

        start = _call(SecurityMiddleware)[0]
        headers = dict(start["headers"])
        assert headers[b"x-frame-options"] == b"DENY"
        assert headers[b"x-content-type-options"] == b"nosniff"
        assert b"frame-ancestors 'none'" in headers[b"content-security-policy"]

    def test_large_upload_refused(self):
        from security import SecurityMiddleware

        sent = _call(SecurityMiddleware, "POST", "/session/x/upload/y",
                     headers=[(b"content-length", b"1000")])
        assert sent[0]["status"] == 413

    def test_lying_content_length_still_stopped(self):
        from security import SecurityMiddleware

        with pytest.raises(ValueError):
            _call(SecurityMiddleware, "POST", "/session/x/upload/y",
                  headers=[(b"content-length", b"10")], body=b"x" * 1000)

    def test_small_upload_passes(self):
        from security import SecurityMiddleware

        sent = _call(SecurityMiddleware, "POST", "/session/x/upload/y",
                     headers=[(b"content-length", b"5")], body=b"hello")
        assert sent[0]["status"] == 200


def test_app_exports_wrapped_asgi_app():
    import app

    assert callable(app.app)
    assert app.app.app is app.shiny_app


def test_resolve_tab_never_returns_forbidden_tab():
    import app

    for role in ("guest", "user", "admin", "superadmin", "unknown"):
        for requested in [None, "nope", *app.TAB_LOOKUP]:
            tab = app.resolve_tab(role, requested)
            assert app._tab_allowed(role, tab)
