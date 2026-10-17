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


class TestGuestDecorators:
    """Both self-service functions must be wrapped by exactly one @guest."""

    @pytest.mark.parametrize("name", ["change_own_password", "verify_own_password"])
    def test_wrapped_once_and_denied_without_session(self, isolated_db, name):
        function = getattr(core, name)
        assert hasattr(function, "__wrapped__")
        assert not hasattr(function.__wrapped__, "__wrapped__")  # not double-wrapped
        with core.user_context(None):
            with pytest.raises(PermissionError):
                function("x", "y") if name == "change_own_password" else function("x")
        row = _events(category="security")[0]
        assert row["event"] == "access_denied"
        assert json.loads(row["detail"])["function"] == name


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


class TestRetentionSettings:
    DEFAULTS = {
        "retention_days_navigation": 30,
        "retention_days_auth": 180,
        "retention_days_security": 365,
        "purge_interval_hours": 1,
    }

    def test_defaults(self, superadmin_ctx):
        assert core.get_audit_settings() == self.DEFAULTS

    def test_save_persists_and_returns_values(self, superadmin_ctx):
        new = {**self.DEFAULTS, "retention_days_navigation": 7, "purge_interval_hours": 6}
        assert core.update_audit_settings(new) == new
        assert core.get_audit_settings() == new
        assert audit.get_settings() == new  # stored in the database, not in memory

    def test_change_is_logged_with_old_and_new_values(self, superadmin_ctx):
        core.update_audit_settings({**self.DEFAULTS, "retention_days_auth": 90})
        row = _events(category="security")[0]
        assert row["event"] == "audit_settings_changed" and row["username"] == "superadmin"
        assert json.loads(row["detail"])["changes"] == {"retention_days_auth": [180, 90]}

    def test_saving_same_values_logs_nothing(self, superadmin_ctx):
        core.update_audit_settings(dict(self.DEFAULTS))
        assert _events() == []

    @pytest.mark.parametrize(
        "bad",
        [
            {"retention_days_navigation": 0},
            {"retention_days_auth": 3651},
            {"retention_days_security": -1},
            {"purge_interval_hours": 169},
            {"purge_interval_hours": None},
            {"retention_days_auth": 1.5},
            {"retention_days_auth": "abc"},
            {"retention_days_auth": True},
        ],
    )
    def test_invalid_values_are_rejected_and_not_saved(self, superadmin_ctx, bad):
        with pytest.raises(ValueError):
            core.update_audit_settings({**self.DEFAULTS, **bad})
        assert core.get_audit_settings() == self.DEFAULTS

    def test_missing_key_is_rejected(self, superadmin_ctx):
        with pytest.raises(ValueError):
            core.update_audit_settings({"retention_days_auth": 10})

    def test_whole_floats_and_numeric_strings_are_accepted(self, superadmin_ctx):
        core.update_audit_settings({**self.DEFAULTS, "retention_days_auth": 45.0,
                                    "retention_days_security": "400"})
        got = core.get_audit_settings()
        assert got["retention_days_auth"] == 45 and got["retention_days_security"] == 400

    def test_corrupt_stored_value_falls_back_to_default(self, isolated_db):
        con = audit._connect()
        con.execute("INSERT INTO audit_settings VALUES ('retention_days_auth', 99999)")
        con.commit(); con.close()
        assert audit.get_settings()["retention_days_auth"] == 180

    def test_purge_honours_saved_retention(self, superadmin_ctx):
        core.update_audit_settings({**self.DEFAULTS, "retention_days_navigation": 3,
                                    "retention_days_auth": 3})
        for category in ("navigation", "auth", "security"):
            audit.log_event(category, "e", user={"role": "user", "username": "u"})
        later = datetime.now(timezone.utc) + timedelta(days=10)
        audit.purge_old(now=later)
        left = {e["category"] for e in _events() if e["event"] == "e"}
        assert left == {"security"}  # security keeps 365 days

    @pytest.mark.parametrize(
        "fn_args",
        [
            ("get_audit_settings", ()),
            ("update_audit_settings", ({},)),
            ("audit_log_counts", ()),
            ("clear_audit_logs", (None,)),
        ],
    )
    @pytest.mark.parametrize("ctx", ["admin_ctx", "user_ctx", "guest_ctx", "anonymous_ctx"])
    def test_only_superadmin_may_use_settings_and_clear(self, ctx, fn_args, request):
        request.getfixturevalue(ctx)
        name, args = fn_args
        audit.log_event("auth", "keep_me", user={"role": "user", "username": "u"})
        with pytest.raises(PermissionError):
            getattr(core, name)(*args)
        assert audit.counts()["auth"] == 1  # nothing was deleted


class TestClearing:
    def _fill(self):
        for category in ("navigation", "navigation", "auth", "security"):
            audit.log_event(category, "x", user={"role": "user", "username": "u"})

    def test_counts(self, superadmin_ctx):
        self._fill()
        assert core.audit_log_counts() == {"auth": 1, "navigation": 2, "security": 1}

    @pytest.mark.parametrize("category", ["navigation", "auth", "security"])
    def test_clear_one_category_only(self, superadmin_ctx, category):
        self._fill()
        others = {c: n for c, n in audit.counts().items() if c != category}
        deleted = core.clear_audit_logs(category)
        after = audit.counts()
        assert deleted == {"navigation": 2, "auth": 1, "security": 1}[category]
        assert {c: n for c, n in after.items() if c != category and c != "security"} == {
            c: n for c, n in others.items() if c != "security"
        }
        assert after[category] == (1 if category == "security" else 0)  # + the audit_cleared row

    def test_clear_all_leaves_only_the_record_of_the_deletion(self, superadmin_ctx):
        self._fill()
        assert core.clear_audit_logs(None) == 4
        (row,) = _events()
        assert row["event"] == "audit_cleared" and row["severity"] == "critical"
        assert row["username"] == "superadmin"
        assert json.loads(row["detail"]) == {"scope": "all", "deleted": 4}

    def test_clear_unknown_category_is_rejected(self, superadmin_ctx):
        self._fill()
        with pytest.raises(ValueError):
            core.clear_audit_logs("everything")
        assert sum(audit.counts().values()) == 4

    def test_deletion_is_recorded_even_when_superadmin_logging_is_off(
        self, superadmin_ctx, monkeypatch
    ):
        monkeypatch.setattr(audit, "LOG_SUPERADMIN_ACTIVITY", False)
        core.clear_audit_logs("auth")
        assert [e["event"] for e in _events()] == ["audit_cleared"]


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

    def test_csv_href_round_trips(self):
        from urllib.parse import unquote

        from tabs import tab_logs

        href = tab_logs._csv_href("a,b\nمهمان,=x\n")
        assert href.startswith("data:text/csv;charset=utf-8,")
        assert unquote(href.split(",", 1)[1]) == "\ufeffa,b\nمهمان,=x\n"
        assert "\n" not in href and " " not in href

    def test_limit_value(self):
        from tabs import tab_logs

        assert tab_logs._limit_value("500") == 500
        assert tab_logs._limit_value("999999") == 1000
        assert tab_logs._limit_value("abc") == 100
