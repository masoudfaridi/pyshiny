"""``@confirm_with_password`` -- run a callback only after a confirmation dialog
AND the signed-in user's own account password.

Usage (inside a module server, directly above the callback)::

    @reactive.effect
    @reactive.event(input.btn_delete)
    @confirm_with_password(
        input,
        get_session_user,                      # app.py's _ensure_valid_session
        message={"en": "Delete everything?", "fa": "همه چیز حذف شود؟"},
        required_role="admin",                 # optional
    )
    def _on_delete():
        ...                                    # runs ONLY after the password is correct

Flow (one dialog at a time, per browser session)::

    click ──► [role check] ──► dialog 1: ``message`` ─Continue─► dialog 2: password
                  │ denied: toast, no dialog              │ wrong: error in the dialog
                  ▼                                        ▼ locked: dialog closes, toast
                                                    correct: dialog closes, callback runs

Security properties
-------------------
* The callback is only reachable from the password-submit handler, after
  ``verify_own_password`` succeeded. The decorated name is replaced by a
  function that merely opens the dialog, so the reactive event that is
  attached above it can never run the callback directly.
* The password is checked against the account of the user in the CURRENT
  session (re-read from SQLite). The user cannot type another username, and
  ``verify_own_password`` cannot be pointed at another account.
* Wrong passwords use the SAME lockout counters as the login form, so the
  dialog cannot be used to brute-force a hijacked session. Lockouts and
  failures are written to the audit log; the password never is.
* A confirmation expires (``timeout_seconds``, default 120): a dialog left open
  cannot be completed much later. If the signed-in user changed in between,
  the flow is aborted.
* Forged inputs are ignored: a submit/continue without the matching dialog
  step does nothing.
* ``required_role`` is checked BEFORE any dialog is shown (no point asking a
  password from someone who may not run the action). Denials are logged like
  any other ``@superadmin/@admin/...`` refusal.
* The callback runs inside ``user_context(<the validated user>)``, so
  decorated ``auth.core`` functions called by it see the right user.

Notes
-----
* ``message`` / ``title`` may be a plain string, a ``{"en": ..., "fa": ...}``
  dict (the one for ``i18n.APP_LANG`` is used, English as fallback) or the name
  of a key in ``i18n.STRINGS``. All fixed texts of the dialogs live in
  ``i18n.py`` (``reauth_*`` keys) in English and Persian.
* The function name of the decorated callback must be unique inside its module
  server: it is used to build the dialog's input ids.
"""
from __future__ import annotations

import functools
import re
import time

from shiny import reactive, ui

import i18n
from auth import audit
from auth.core import (
    LOGIN_LOCKOUT_SECONDS,
    ROLE_LEVELS,
    clear_login_failures,
    is_login_locked,
    register_login_failure,
    require_role,
    user_context,
    verify_own_password,
)

DEFAULT_TIMEOUT_SECONDS = 120


def _text(value) -> str:
    """Resolve a message/title: callable, per-language dict, i18n key or plain str."""
    if callable(value):
        value = value()
    if isinstance(value, dict):
        return str(
            value.get(i18n.APP_LANG)
            or value.get("en")
            or next(iter(value.values()), "")
        )
    if isinstance(value, str) and value in i18n.STRINGS.get(i18n.APP_LANG, {}):
        return i18n.t(value)
    return str(value)


class _Flow:
    """State machine of ONE decorated callback in ONE browser session.

    Kept free of reactive objects so it can be unit-tested: the four
    ``show_modal`` / ``remove_modal`` / ``notify`` / ``now`` hooks are plain
    attributes that tests replace.
    """

    def __init__(self, fn, prefix, get_session_user, message, title,
                 required_role, timeout_seconds):
        self.fn = fn
        self.name = fn.__name__
        self.prefix = prefix
        self.get_session_user = get_session_user
        self.message = message
        self.title = title
        self.required_role = required_role
        self.timeout = timeout_seconds
        self.step = None  # None | "confirm" | "password"
        self.user_id = None
        self.started = 0.0
        self.show_modal = ui.modal_show
        self.remove_modal = ui.modal_remove
        self.notify = ui.notification_show
        self.now = time.monotonic

    # ------------------------------------------------------------- helpers
    def _toast(self, text: str, kind: str = "error") -> None:
        try:
            self.notify(text, type=kind, duration=6)
        except RuntimeError:
            pass  # no active Shiny session (unit tests / shutdown): nothing to show

    def _log(self, event: str, person, severity: str = "info", **detail) -> None:
        audit.log_event(
            "security", event, user=person, severity=severity,
            detail={"action": self.name, **detail},
        )

    def _reset(self) -> None:
        self.step = None
        self.user_id = None

    def _abort(self, message_key: str) -> None:
        self._reset()
        self.remove_modal()
        self._toast(i18n.t(message_key))

    def _role_ok(self, person) -> bool:
        def gate():  # named after the action so the audit log shows which one
            return None

        gate.__name__ = self.name
        try:
            with user_context(person):
                require_role(self.required_role)(gate)()
            return True
        except PermissionError:
            return False

    def _checked(self, step: str):
        """The signed-in user if this input is legitimate right now, else None."""
        if self.step != step:
            return None  # stray / forged input: ignore silently
        person = self.get_session_user()
        if person is None or person.get("id") != self.user_id:
            self._abort("reauth_signin")
            return None
        if self.now() - self.started > self.timeout:
            self._abort("reauth_expired")
            return None
        return person

    # ------------------------------------------------------------- dialogs
    def _build_modal(self, step: str, error: str | None = None):
        p = self.prefix
        title = _text(self.title) if self.title else i18n.t("reauth_title")
        if step == "confirm":
            return ui.modal(
                ui.p(_text(self.message), class_="reauth-message"),
                title=title,
                footer=ui.div(
                    ui.input_action_button(
                        f"{p}_cancel", i18n.t("reauth_cancel"),
                        class_="btn btn-secondary me-2",
                    ),
                    ui.input_action_button(
                        f"{p}_continue", i18n.t("reauth_continue"),
                        class_="btn btn-primary",
                    ),
                ),
                easy_close=False,
            )
        body = [
            ui.p(i18n.t("reauth_password_intro"), class_="reauth-message"),
            ui.input_password(f"{p}_password", i18n.t("reauth_password_label")),
        ]
        if error:
            body.append(ui.div(error, class_="login-error"))
        return ui.modal(
            *body,
            title=title,
            footer=ui.div(
                ui.input_action_button(
                    f"{p}_cancel", i18n.t("reauth_cancel"),
                    class_="btn btn-secondary me-2",
                ),
                ui.input_action_button(
                    f"{p}_submit", i18n.t("reauth_submit"), class_="btn btn-danger"
                ),
            ),
            easy_close=False,
        )

    # ------------------------------------------------------------ handlers
    def start(self) -> None:
        """The click: check the role, then open dialog 1."""
        person = self.get_session_user()
        if person is None:
            self._toast(i18n.t("reauth_signin"))
            return
        if self.required_role and not self._role_ok(person):
            self._toast(i18n.t("reauth_denied"))
            return
        self.user_id = person.get("id")
        self.started = self.now()
        self.step = "confirm"
        self.show_modal(self._build_modal("confirm"))

    def on_continue(self) -> None:
        if self._checked("confirm") is None:
            return
        self.step = "password"
        self.show_modal(self._build_modal("password"))

    def on_cancel(self) -> None:
        if self.step is not None:
            self._reset()
            self.remove_modal()

    def on_submit(self, password: str) -> None:
        person = self._checked("password")
        if person is None:
            return
        if not password:  # not counted as a failed attempt
            self.show_modal(self._build_modal("password", i18n.t("reauth_empty_password")))
            return

        username = person["username"]
        locked, remaining = is_login_locked(username)
        if locked:
            self._log("reauth_blocked_locked", person, "warning", remaining_s=remaining)
            self._reset()
            self.remove_modal()
            self._toast(i18n.t("login_locked", remaining=remaining))
            return

        try:
            with user_context(person):
                correct = verify_own_password(password)
        except PermissionError:
            correct = False

        if not correct:
            just_locked = register_login_failure(username)
            self._log("reauth_failed", person, "warning")
            if just_locked:
                self._log(
                    "account_locked", person, "critical",
                    source="reauth", lock_seconds=LOGIN_LOCKOUT_SECONDS,
                )
                self._reset()
                self.remove_modal()
                _, remaining = is_login_locked(username)
                self._toast(i18n.t("login_locked", remaining=remaining))
                return
            self.show_modal(self._build_modal("password", i18n.t("reauth_wrong_password")))
            return

        # Correct password: close the dialog FIRST (a double click cannot run the
        # callback twice), then run it as the validated user.
        clear_login_failures(username)
        self._reset()
        self.remove_modal()
        self._log("sensitive_action_confirmed", person)
        try:
            with user_context(person):
                self.fn()
        except PermissionError:
            self._toast(i18n.t("reauth_denied"))


def confirm_with_password(
    input,
    get_session_user,
    *,
    message,
    title=None,
    required_role: str | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
):
    """Decorator factory; see the module docstring.

    ``input``            the module server's ``input``
    ``get_session_user`` returns the re-validated user dict or None
                         (app.py's ``_ensure_valid_session``)
    ``message``          text of the first dialog (str | {"en","fa"} | i18n key)
    ``title``            optional dialog title (same forms); default: "Confirm action"
    ``required_role``    optional minimum role, checked before any dialog
    ``timeout_seconds``  how long the confirmation stays valid
    """
    if required_role is not None and required_role not in ROLE_LEVELS:
        raise ValueError(f"unknown role: {required_role!r}")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    def decorator(fn):
        prefix = "reauth_" + (re.sub(r"\W", "_", fn.__name__).strip("_") or "action")
        flow = _Flow(fn, prefix, get_session_user, message, title,
                     required_role, timeout_seconds)

        def make_effect(suffix, button_id, handler):
            handler.__name__ = f"{prefix}__{suffix}"
            reactive.effect(reactive.event(input[button_id])(handler))

        make_effect("continue", f"{prefix}_continue", lambda: flow.on_continue())
        make_effect("cancel", f"{prefix}_cancel", lambda: flow.on_cancel())

        def submit():
            try:
                password = input[f"{prefix}_password"]()
            except Exception:  # input not present (forged submit): treated as empty
                password = ""
            flow.on_submit(password or "")

        make_effect("submit", f"{prefix}_submit", submit)

        @functools.wraps(fn)
        def trigger():
            flow.start()

        trigger.flow = flow  # exposed for tests / introspection
        return trigger

    return decorator
