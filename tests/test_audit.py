"""Audit log: policy for superadmin, hooks in auth.core, sanitising, retention."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

import auth.core as core
from auth import audit


def _events(**kw):
    return audit.query_events(**kw)


class TestLogEventPolicy:
    def test_regular_user_event_is_recorded(self, isolated_db):
        user = core.authenticate("user", "User123!")
        audit.log_event("auth", "login_success", user=user, ip="10.0.0.5", session_id="abc")
        (row,) = _events()
        assert (row["category"], row["event"], row["username"], row["role"]) == (
            "auth", "login_success", "user", "user",
        )
        assert row["ip"] == "10.0.0.5" and row["session_id"] == "abc"

    ROUTINE = (
        ("auth", "login_success"), ("auth", "logout"),
        ("navigation", "tab_opened"), ("navigation", "session_ended"),
    )

    def test_superadmin_activity_is_recorded_by_default(self, isolated_db):
        sa = core.authenticate("superadmin", "ChangeMe123!")
        for category, event in self.ROUTINE:
            audit.log_event(category, event, user=sa)
        rows = _events()
        assert len(rows) == 4
        assert {r["username"] for r in rows} == {"superadmin"}

    def test_opt_out_skips_superadmin_routine_activity(self, isolated_db, monkeypatch):
        monkeypatch.setattr(audit, "LOG_SUPERADMIN_ACTIVITY", False)
        sa = core.authenticate("superadmin", "ChangeMe123!")
        for category, event in self.ROUTINE:
            audit.log_event(category, event, user=sa)
        assert _events() == []

    def test_opt_out_still_records_account_management(self, isolated_db, monkeypatch):
        monkeypatch.setattr(audit, "LOG_SUPERADMIN_ACTIVITY", False)
        sa = core.authenticate("superadmin", "ChangeMe123!")
        audit.log_event("security", "user_deleted", user=sa)
        (row,) = _events()
        assert row["username"] == "superadmin" and row["event"] == "user_deleted"

    def test_anonymous_attack_on_superadmin_account_is_recorded(self, isolated_db):
        audit.log_event(
            "auth", "login_failed", username="superadmin", severity="warning",
            detail={"reason": "bad_credentials"},
        )
        (row,) = _events()
        assert row["username"] == "superadmin" and row["role"] is None

    def test_never_raises_on_bad_input(self, isolated_db):
        audit.log_event("nonsense", "x")
        audit.log_event("auth", "x", severity="loud")
        assert _events() == []

    def test_logging_failure_never_breaks_caller(self, isolated_db, monkeypatch):
        def boom():
            raise RuntimeError("disk full")

        monkeypatch.setattr(audit, "_connect", boom)
        audit.log_event("auth", "login_success", user={"role": "user", "username": "u"})


class TestSanitising:
    def test_control_chars_and_length(self, isolated_db):
        audit.log_event("auth", "login_failed", username="bad\nname\x00" + "x" * 500)
        (row,) = _events()
        assert "\n" not in row["username"] and "\x00" not in row["username"]
        assert len(row["username"]) <= 64

    def test_detail_is_json_and_cleaned(self, isolated_db):
        audit.log_event("security", "x", detail={"a": "line1\nline2", "n": 3})
        (row,) = _events()
        assert json.loads(row["detail"]) == {"a": "line1 line2", "n": 3}

    def test_oversized_detail_is_replaced(self, isolated_db):
        audit.log_event("security", "x", detail={"a": ["y" * 190] * 30})
        (row,) = _events()
        assert json.loads(row["detail"]) == {"truncated": True}


class TestCoreHooks:
    def test_decorator_denial_is_logged(self, admin_ctx):
        with pytest.raises(PermissionError):
            core.list_users()
        (row,) = _events(category="security")
        assert row["event"] == "access_denied" and row["username"] == "admin"
        assert json.loads(row["detail"]) == {
            "function": "list_users", "required_role": "superadmin",
        }

    def test_denial_without_session_is_logged_as_anonymous(self, isolated_db):
        with core.user_context(None):
            with pytest.raises(PermissionError):
                core.create_user("x" * 5, "Passw0rd!!", "user")
        (row,) = _events()
        assert row["event"] == "access_denied" and row["username"] is None

    def test_session_meta_travels_with_the_user_dict(self, isolated_db):
        user = core.authenticate("user", "User123!")
        user.update({"sid": "sess-1", "ip": "1.2.3.4", "ua": "UA"})
        with core.user_context(user):
            with pytest.raises(PermissionError):
                core.list_users()
        (row,) = _events()
        assert (row["session_id"], row["ip"], row["user_agent"]) == ("sess-1", "1.2.3.4", "UA")

    def test_user_lifecycle_is_logged_with_actor(self, superadmin_ctx):
        core.create_user("newbie", "Passw0rd!!", "user")
        uid = next(u["id"] for u in core.list_users() if u["username"] == "newbie")
        core.update_user(uid, "newbie", "user", True, expire_date="2030-01-01")
        core.delete_user(uid)
        events = [e["event"] for e in reversed(_events(category="security"))]
        assert events == ["user_created", "user_updated", "user_deleted"]
        assert {e["username"] for e in _events(category="security")} == {"superadmin"}

    def test_role_change_is_critical_when_superadmin_involved(self, superadmin_ctx):
        core.create_user("bob", "Passw0rd!!", "user")
        uid = next(u["id"] for u in core.list_users() if u["username"] == "bob")
        core.update_user(uid, "bob", "superadmin", True)
        row = _events(category="security")[0]
        assert row["event"] == "role_changed" and row["severity"] == "critical"
        assert json.loads(row["detail"])["changes"]["role"] == ["user", "superadmin"]

    def test_password_reset_logged_without_the_password(self, superadmin_ctx):
        core.create_user("carol", "Passw0rd!!", "user")
        uid = next(u["id"] for u in core.list_users() if u["username"] == "carol")
        core.update_user(uid, "carol", "user", True, new_password="Sup3rSecret!!")
        row = _events(category="security")[0]
        assert "Sup3rSecret" not in json.dumps(row)
        assert json.loads(row["detail"])["changes"] == {"password_reset": True}

    def test_noop_update_is_not_logged(self, superadmin_ctx):
        core.create_user("dave", "Passw0rd!!", "user")
        uid = next(u["id"] for u in core.list_users() if u["username"] == "dave")
        before = len(_events())
        core.update_user(uid, "dave", "user", True)
        assert len(_events()) == before

    def test_change_own_password_logged(self, user_ctx):
        core.change_own_password("User123!", "NewPass123")
        with pytest.raises(ValueError):
            core.change_own_password("wrong-password", "Another123")
        events = [e["event"] for e in reversed(_events(category="auth"))]
        assert events == ["password_changed", "password_change_failed"]


class TestLockoutSignal:
    def test_only_the_locking_failure_returns_true(self, isolated_db):
        results = [core.register_login_failure("victim") for _ in range(core.LOGIN_MAX_FAILURES + 2)]
        assert results.count(True) == 1
        assert results.index(True) == core.LOGIN_MAX_FAILURES - 1

    def test_empty_username(self, isolated_db):
        assert core.register_login_failure("") is False


class TestReadingTheLog:
    def test_superadmin_can_read(self, superadmin_ctx):
        audit.log_event("auth", "login_success", user={"role": "user", "username": "u"})
        assert len(core.list_audit_events()) == 1

    @pytest.mark.parametrize("ctx", ["admin_ctx", "user_ctx", "guest_ctx", "anonymous_ctx"])
    def test_everyone_else_is_denied(self, ctx, request):
        request.getfixturevalue(ctx)
        with pytest.raises(PermissionError):
            core.list_audit_events()

    def test_filters(self, isolated_db):
        audit.log_event("auth", "a", user={"role": "user", "username": "alice_1"})
        audit.log_event("security", "b", severity="critical", user={"role": "admin", "username": "bob"})
        assert [e["event"] for e in _events(category="auth")] == ["a"]
        assert [e["event"] for e in _events(severity="critical")] == ["b"]
        assert [e["event"] for e in _events(username="ALICE")] == ["a"]
        assert _events(username="%") == []  # LIKE wildcards are escaped

    def test_limit_is_clamped(self, isolated_db):
        for i in range(3):
            audit.log_event("auth", f"e{i}", user={"role": "user", "username": "u"})
        assert len(_events(limit=2)) == 2
        assert len(_events(limit=-5)) == 1


class TestRetention:
    def test_purge_uses_per_category_windows(self, isolated_db):
        audit.log_event("navigation", "old_nav", user={"role": "user", "username": "u"})
        audit.log_event("security", "old_sec", user={"role": "user", "username": "u"})
        audit.log_event("auth", "old_auth", user={"role": "user", "username": "u"})
        in_60_days = datetime.now(timezone.utc) + timedelta(days=60)
        assert audit.purge_old(now=in_60_days) == 1  # only navigation (30 d) expired
        assert {e["event"] for e in _events()} == {"old_sec", "old_auth"}
        in_400_days = datetime.now(timezone.utc) + timedelta(days=400)
        audit.purge_old(now=in_400_days)
        assert _events() == []


class TestLogsTabHelpers:
    def test_tab_contract(self):
        from tabs import tab_logs

        assert tab_logs.NAV_MIN_ROLE == "superadmin"
        assert tab_logs.NAV_GROUP is None

    def test_csv_injection_is_neutralised(self):
        from tabs import tab_logs

        text = tab_logs._rows_to_csv(
            [{"id": 1, "ts": "t", "category": "auth", "event": "login_failed",
              "severity": "warning", "username": "=HYPERLINK(\"http://x\")",
              "role": None, "ip": "1.1.1.1", "session_id": "s",
              "user_agent": "+cmd", "detail": '{"reason": "bad_credentials"}'}]
        )
        assert "'=HYPERLINK" in text and "'+cmd" in text
        assert "reason=bad_credentials" in text

    def test_limit_value(self):
        from tabs import tab_logs

        assert tab_logs._limit_value("500") == 500
        assert tab_logs._limit_value("999999") == 1000
        assert tab_logs._limit_value("abc") == 100
