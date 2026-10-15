"""
Tab 07 -- Role-gated buttons (one tab, four buttons).

Everybody can SEE this tab and all four buttons (NAV_MIN_ROLE = "guest").
What protects each button is the *server side*: the action behind it is
wrapped by an RBAC decorator from the ``auth`` package.

    Button        Decorator       Who may run it
    -----------   -------------   ----------------------------------------
    Superadmin    @superadmin     superadmin
    Admin         @admin          admin, superadmin
    User          @user           user, admin, superadmin
    Guest         @guest          every signed-in account

Hierarchy is kept exactly as in ``auth.core``: a higher role always includes
the lower ones. When the role is too low (or the session is no longer valid)
the callback does NOT run the action; it shows an error toast instead.

Why the user is passed in as a function
---------------------------------------
Module servers start before login, so ``current_user()`` is empty there.
app.py therefore passes ``_ensure_valid_session`` (a function). It re-loads
the user from SQLite on every click, so a demoted / deactivated / expired
account loses access immediately and not only after the next page refresh.
The decorators are fail-closed: outside ``user_context(...)`` there is no
user, so every decorated action raises ``PermissionError``.
"""

from __future__ import annotations

from shiny import module, reactive, ui

from auth import admin, guest, superadmin, user, user_context
from i18n import APP_LANG

NAV_ID = "tab_07"
NAV_LABEL = "Access Buttons"
NAV_ICON = "bi-shield-lock"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"  # visible to everyone on purpose: the SERVER decides

MODULE_ID = "tab_07"

# Tab-local texts (no change to i18n.py needed). Keys per language.
_TEXTS = {
    "en": {
        "title": "Role-gated buttons",
        "intro": (
            "All four buttons are visible to everyone. Each one only works if "
            "your role is high enough; otherwise you get a notice."
        ),
        "btn_superadmin": "Superadmin button",
        "btn_admin": "Admin button",
        "btn_user": "User button",
        "btn_guest": "Guest button",
        "ok_superadmin": "Superadmin action completed.",
        "ok_admin": "Admin action completed.",
        "ok_user": "User action completed.",
        "ok_guest": "Guest action completed.",
        "denied": "You do not have access to this section.",
        "signin": "Your session is no longer valid. Please sign in again.",
    },
    "fa": {
        "title": "دکمه‌های وابسته به سطح دسترسی",
        "intro": (
            "هر چهار دکمه برای همه قابل مشاهده است. هر دکمه فقط در صورتی کار "
            "می‌کند که سطح دسترسی شما کافی باشد؛ در غیر این صورت پیام اطلاع‌رسانی "
            "نمایش داده می‌شود."
        ),
        "btn_superadmin": "دکمه سوپر ادمین",
        "btn_admin": "دکمه ادمین",
        "btn_user": "دکمه کاربر",
        "btn_guest": "دکمه مهمان",
        "ok_superadmin": "عملیات سوپر ادمین با موفقیت انجام شد.",
        "ok_admin": "عملیات ادمین با موفقیت انجام شد.",
        "ok_user": "عملیات کاربر با موفقیت انجام شد.",
        "ok_guest": "عملیات مهمان با موفقیت انجام شد.",
        "denied": "دسترسی به این بخش برای شما مقدور نیست.",
        "signin": "نشست شما دیگر معتبر نیست. لطفاً دوباره وارد شوید.",
    },
}


def _tx(key: str) -> str:
    return _TEXTS.get(APP_LANG, _TEXTS["en"]).get(key, _TEXTS["en"][key])


# ---------------------------------------------------------------------------
# The protected actions. Put the real work (DB writes, exports, ...) in here:
# the decorator guarantees it never runs for a role that is too low.
# ---------------------------------------------------------------------------
@superadmin
def _superadmin_action() -> str:
    return _tx("ok_superadmin")


@admin
def _admin_action() -> str:
    return _tx("ok_admin")


@user
def _user_action() -> str:
    return _tx("ok_user")


@guest
def _guest_action() -> str:
    return _tx("ok_guest")


def _attempt(action, get_session_user) -> None:
    """Run ``action`` as the current (re-validated) user and show a toast."""
    person = get_session_user()
    if person is None:
        ui.notification_show(_tx("signin"), type="error", duration=6)
        return
    try:
        with user_context(person):  # lets the decorator see this user
            message = action()
    except PermissionError:
        ui.notification_show(_tx("denied"), type="error", duration=6)
        return
    ui.notification_show(message, type="message", duration=4)


@module.ui
def _ui():
    return ui.div(
        ui.h3(_tx("title")),
        ui.p(_tx("intro")),
        ui.div(
            ui.input_action_button(
                "btn_superadmin", _tx("btn_superadmin"), class_="btn btn-danger me-2 mb-2"
            ),
            ui.input_action_button(
                "btn_admin", _tx("btn_admin"), class_="btn btn-warning me-2 mb-2"
            ),
            ui.input_action_button(
                "btn_user", _tx("btn_user"), class_="btn btn-primary me-2 mb-2"
            ),
            ui.input_action_button(
                "btn_guest", _tx("btn_guest"), class_="btn btn-secondary mb-2"
            ),
            class_="user-form-card",
        ),
        class_="tab-pane-content",
    )


@module.server
def _server(input, output, session, get_session_user):
    """``get_session_user`` returns the re-validated user dict, or None."""

    @reactive.effect
    @reactive.event(input.btn_superadmin)
    def _on_superadmin():
        _attempt(_superadmin_action, get_session_user)

    @reactive.effect
    @reactive.event(input.btn_admin)
    def _on_admin():
        _attempt(_admin_action, get_session_user)

    @reactive.effect
    @reactive.event(input.btn_user)
    def _on_user():
        _attempt(_user_action, get_session_user)

    @reactive.effect
    @reactive.event(input.btn_guest)
    def _on_guest():
        _attempt(_guest_action, get_session_user)


def panel():
    """Called by app.py every time the tab is shown."""
    return _ui(MODULE_ID)


def server(get_session_user):
    """Register once from app.py: ``tab_07.server(_ensure_valid_session)``."""
    _server(MODULE_ID, get_session_user=get_session_user)
