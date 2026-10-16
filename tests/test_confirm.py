"""@confirm_with_password: dialog flow, password check, lockout, expiry, logging."""
from __future__ import annotations

import json
import types

import pytest

import auth.core as core
import i18n
from auth import audit, confirm

PASSWORDS = {"superadmin": "ChangeMe123!", "admin": "Admin123!", "user": "User123!", "guest": "Guest123!"}


def _events(**kw):
    return audit.query_events(**kw)


class Harness:
    """A _Flow with every Shiny-facing hook replaced by a recorder."""

    def __init__(self, role="user", required_role=None, timeout=120):
        core.clear_login_failures(role)
        self.person = core.authenticate(role, PASSWORDS[role])
        self.person.update({"sid": "sess-9", "ip": "198.51.100.4", "ua": "UA"})
        self.calls, self.shown, self.toasts, self.removed = [], [], [], 0
        self.t = 1000.0

        def danger_action():
            self.calls.append(core.current_user()["username"])

        self.flow = confirm._Flow(
            danger_action, "reauth_danger_action", lambda: self.person,
            "Really?", None, required_role, timeout,
        )
        self.flow.show_modal = self.shown.append
        self.flow._build_modal = lambda step, error=None: (step, error)
        self.flow.remove_modal = self._remove
        self.flow.notify = lambda text, **kw: self.toasts.append((text, kw["type"]))
        self.flow.now = lambda: self.t

    def _remove(self):
        self.removed += 1

    def reach_password_step(self):
        self.flow.start()
        self.flow.on_continue()
        assert self.shown[-1] == ("password", None)


class TestHappyPath:
    def test_click_shows_confirmation_and_does_not_run(self, isolated_db):
        h = Harness()
        h.flow.start()
        assert h.shown == [("confirm", None)] and h.calls == []

    def test_continue_asks_for_the_password(self, isolated_db):
        h = Harness()
        h.reach_password_step()
        assert h.calls == []

    def test_correct_password_runs_callback_once_as_that_user(self, isolated_db):
        h = Harness()
        h.reach_password_step()
        h.flow.on_submit(PASSWORDS["user"])
        assert h.calls == ["user"] and h.removed == 1
        h.flow.on_submit(PASSWORDS["user"])  # double click / replay
        assert h.calls == ["user"]

    def test_cancel_at_either_step_never_runs(self, isolated_db):
        for stop_at in ("confirm", "password"):
            h = Harness()
            h.flow.start()
            if stop_at == "password":
                h.flow.on_continue()
            h.flow.on_cancel()
            h.flow.on_submit(PASSWORDS["user"])  # late submit after cancel
            assert h.calls == [] and h.removed == 1

    def test_success_is_audited_without_the_password(self, isolated_db):
        h = Harness()
        h.reach_password_step()
        h.flow.on_submit(PASSWORDS["user"])
        (row,) = _events(category="security")
        assert row["event"] == "sensitive_action_confirmed" and row["username"] == "user"
        assert json.loads(row["detail"]) == {"action": "danger_action"}
        assert (row["session_id"], row["ip"]) == ("sess-9", "198.51.100.4")
        assert PASSWORDS["user"] not in json.dumps(row)


class TestWrongPassword:
    def test_wrong_password_keeps_dialog_and_does_not_run(self, isolated_db):
        h = Harness()
        h.reach_password_step()
        h.flow.on_submit("not-my-password")
        assert h.calls == []
        assert h.shown[-1] == ("password", i18n.t("reauth_wrong_password"))
        h.flow.on_submit(PASSWORDS["user"])  # can still succeed afterwards
        assert h.calls == ["user"]

    def test_failure_is_audited(self, isolated_db):
        h = Harness()
        h.reach_password_step()
        h.flow.on_submit("nope")
        (row,) = _events(category="security")
        assert row["event"] == "reauth_failed" and row["severity"] == "warning"
        assert "nope" not in json.dumps(row)

    def test_empty_password_is_an_error_but_not_a_failed_attempt(self, isolated_db):
        h = Harness()
        h.reach_password_step()
        for _ in range(core.LOGIN_MAX_FAILURES + 2):
            h.flow.on_submit("")
        assert h.shown[-1] == ("password", i18n.t("reauth_empty_password"))
        assert core.is_login_locked("user") == (False, 0) or not core.is_login_locked("user")[0]
        assert _events() == []

    def test_repeated_failures_lock_the_account_and_close_the_dialog(self, isolated_db):
        h = Harness()
        h.reach_password_step()
        for _ in range(core.LOGIN_MAX_FAILURES):
            h.flow.on_submit("wrong")
        assert core.is_login_locked("user")[0]
        assert h.removed == 1 and h.toasts and h.toasts[-1][1] == "error"
        events = [e["event"] for e in reversed(_events(category="security"))]
        assert events.count("reauth_failed") == core.LOGIN_MAX_FAILURES
        assert events.count("account_locked") == 1
        # even the right password is refused while locked
        h.flow.start()
        h.flow.on_continue()
        h.flow.on_submit(PASSWORDS["user"])
        assert h.calls == []
        assert _events(category="security")[0]["event"] == "reauth_blocked_locked"
        core.clear_login_failures("user")

    def test_dialog_failures_share_the_login_counter(self, isolated_db):
        h = Harness()
        core.register_login_failure("user")  # failures made on the login form
        h.reach_password_step()
        for _ in range(core.LOGIN_MAX_FAILURES - 1):
            h.flow.on_submit("wrong")
        assert core.is_login_locked("user")[0]
        core.clear_login_failures("user")

    def test_success_clears_the_failure_counter(self, isolated_db):
        h = Harness()
        h.reach_password_step()
        h.flow.on_submit("wrong")
        h.flow.on_submit(PASSWORDS["user"])
        assert not core.is_login_locked("user")[0]


class TestRoleCheck:
    def test_too_low_role_gets_a_toast_and_no_dialog(self, isolated_db):
        h = Harness(role="user", required_role="admin")
        h.flow.start()
        assert h.shown == [] and h.calls == []
        assert h.toasts == [(i18n.t("reauth_denied"), "error")]
        row = _events(category="security")[0]
        assert row["event"] == "access_denied"
        assert json.loads(row["detail"])["function"] == "danger_action"

    @pytest.mark.parametrize("role", ["admin", "superadmin"])
    def test_sufficient_role_goes_through(self, isolated_db, role):
        h = Harness(role=role, required_role="admin")
        h.reach_password_step()
        h.flow.on_submit(PASSWORDS[role])
        assert h.calls == [role]


class TestForgedAndStaleInputs:
    def test_submit_without_any_dialog_is_ignored(self, isolated_db):
        h = Harness()
        h.flow.on_submit(PASSWORDS["user"])
        assert h.calls == [] and h.shown == []

    def test_submit_cannot_skip_the_confirmation_step(self, isolated_db):
        h = Harness()
        h.flow.start()  # step == "confirm"
        h.flow.on_submit(PASSWORDS["user"])
        assert h.calls == []

    def test_continue_without_start_is_ignored(self, isolated_db):
        h = Harness()
        h.flow.on_continue()
        assert h.shown == []

    def test_confirmation_expires(self, isolated_db):
        h = Harness(timeout=30)
        h.reach_password_step()
        h.t += 31
        h.flow.on_submit(PASSWORDS["user"])
        assert h.calls == [] and h.toasts[-1] == (i18n.t("reauth_expired"), "error")

    def test_still_valid_just_before_the_timeout(self, isolated_db):
        h = Harness(timeout=30)
        h.reach_password_step()
        h.t += 29
        h.flow.on_submit(PASSWORDS["user"])
        assert h.calls == ["user"]

    def test_different_user_in_the_session_aborts(self, isolated_db):
        h = Harness(role="user")
        h.reach_password_step()
        h.person = core.authenticate("admin", PASSWORDS["admin"])
        h.flow.on_submit(PASSWORDS["admin"])
        assert h.calls == [] and h.toasts[-1] == (i18n.t("reauth_signin"), "error")

    def test_signed_out_session_aborts(self, isolated_db):
        h = Harness()
        h.reach_password_step()
        h.person = None
        h.flow.on_submit(PASSWORDS["user"])
        assert h.calls == [] and h.toasts[-1] == (i18n.t("reauth_signin"), "error")

    def test_click_while_signed_out(self, isolated_db):
        h = Harness()
        h.person = None
        h.flow.start()
        assert h.shown == [] and h.toasts == [(i18n.t("reauth_signin"), "error")]

    def test_password_cannot_be_verified_for_someone_else(self, isolated_db):
        """verify_own_password only ever checks the user in context."""
        admin = core.authenticate("admin", PASSWORDS["admin"])
        with core.user_context(admin):
            assert core.verify_own_password(PASSWORDS["admin"]) is True
            assert core.verify_own_password(PASSWORDS["user"]) is False
        with core.user_context(None):
            with pytest.raises(PermissionError):
                core.verify_own_password("x")

    def test_permission_error_inside_callback_is_a_toast(self, isolated_db):
        h = Harness()

        @core.superadmin
        def needs_superadmin():
            return None

        h.flow.fn = needs_superadmin
        h.reach_password_step()
        h.flow.on_submit(PASSWORDS["user"])
        assert h.toasts[-1] == (i18n.t("reauth_denied"), "error")


class TestDecorator:
    def _decorate(self, monkeypatch, **kw):
        registered = []
        fake = types.SimpleNamespace(
            effect=lambda fn: registered.append(fn) or fn,
            event=lambda *a: (lambda fn: fn),
        )
        monkeypatch.setattr(confirm, "reactive", fake)

        class FakeInput:
            def __getitem__(self, key):
                return lambda: "pw"

        inputs = FakeInput()
        ran = []

        @confirm.confirm_with_password(inputs, lambda: None, message="m", **kw)
        def _on_click():
            ran.append(True)

        return _on_click, registered, ran

    def test_decorated_name_only_opens_the_dialog(self, isolated_db, monkeypatch):
        trigger, registered, ran = self._decorate(monkeypatch)
        trigger()  # no signed-in user -> toast path, never the callback
        assert ran == []
        assert hasattr(trigger, "flow") and trigger.__name__ == "_on_click"

    def test_registers_continue_cancel_and_submit_handlers(self, isolated_db, monkeypatch):
        _, registered, _ = self._decorate(monkeypatch)
        assert sorted(f.__name__ for f in registered) == [
            "reauth_on_click__cancel", "reauth_on_click__continue", "reauth_on_click__submit",
        ]

    def test_invalid_arguments(self, monkeypatch):
        with pytest.raises(ValueError):
            confirm.confirm_with_password(None, None, message="m", required_role="root")
        with pytest.raises(ValueError):
            confirm.confirm_with_password(None, None, message="m", timeout_seconds=0)

    @pytest.mark.parametrize(
        "value, lang, expected",
        [
            ("plain text", "en", "plain text"),
            ({"en": "English", "fa": "فارسی"}, "fa", "فارسی"),
            ({"en": "English", "fa": "فارسی"}, "en", "English"),
            ({"en": "English"}, "fa", "English"),  # falls back to English
            ("reauth_title", "fa", None),  # i18n key -> translated
            (lambda: "from callable", "en", "from callable"),
        ],
    )
    def test_message_forms(self, monkeypatch, value, lang, expected):
        monkeypatch.setattr(i18n, "APP_LANG", lang)
        expected = expected or i18n.STRINGS[lang]["reauth_title"]
        assert confirm._text(value) == expected


class TestDialogTexts:
    @pytest.mark.parametrize("lang", ["en", "fa"])
    def test_every_state_has_a_text_in_both_languages(self, lang):
        for key in (
            "reauth_title", "reauth_continue", "reauth_cancel", "reauth_password_intro",
            "reauth_password_label", "reauth_submit", "reauth_wrong_password",
            "reauth_empty_password", "reauth_expired", "reauth_signin", "reauth_denied",
        ):
            assert i18n.STRINGS[lang][key].strip()

    def test_dialogs_build(self):
        f = confirm._Flow(lambda: None, "reauth_x", lambda: None, "m", None, None, 10)
        f._build_modal("confirm")
        f._build_modal("password")
        f._build_modal("password", "some error")
