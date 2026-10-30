"""
Python Shiny Dashboard, built with Shiny for Python.
=================================================================

Folder structure
-----------------
app.py            This file. Reads NAV_* metadata + panel() from each tab
                   module below and assembles the sidebar and page.
tabs/tab_0N.py     One file per sidebar entry: its label/icon/group, and
                   its (simple) content.
auth/              Authentication package (RBAC, passwords, expiration).
db/                SQLite database (auth.db).
static/            CSS and JavaScript assets (static/css, static/js).
i18n.py            Bilingual (English / Persian) UI strings + the APP_LANG switch.

How the sidebar is built
--------------------------
Each tab module exposes:
    NAV_ID      unique id, e.g. "tab_01"
    NAV_LABEL   text shown in the sidebar, e.g. "Dashboard v1"
    NAV_ICON    a Bootstrap Icons class (only used for top-level items)
    NAV_GROUP   "dashboard" to nest under the Dashboard group, or None
                for a flat, top-level item
    panel()     a function returning that tab's UI content

app.py just loops over TABS, reads that metadata, and builds:
  1) the nested/collapsible sidebar menu, and
  2) a lookup table used to render whichever tab is currently selected.

Adding a new tab
------------------
1. Copy an existing tabs/tab_0N.py to the next number and edit its
   NAV_ID / NAV_LABEL / NAV_ICON / NAV_GROUP / panel().
2. Import it below and add it to the TABS list (its position there is
   its position in the sidebar).
3. If it should start a *new* collapsible group, add one line to GROUPS.
"""

import base64
import hashlib
import json
import os
import time
from pathlib import Path

from shiny import App, reactive, render, ui
from shiny.types import SilentException
import sqlite3

from auth import (
    LOGIN_LOCKOUT_SECONDS,
    ROLE_LEVELS,
    audit,
    authenticate,
    backup,
    change_own_password,
    clear_login_failures,
    confirm_with_password,
    create_backup,
    create_user,
    current_role,
    current_user,
    delete_backup,
    delete_user,
    generate_captcha,
    get_user_by_id,
    import_backup,
    is_login_locked,
    list_backups,
    list_users,
    read_backup,
    refresh_session_user,
    register_login_failure,
    restore_backup,
    update_own_profile,
    update_user,
    user_context,
    validate_email,
    validate_id_code,
    validate_password,
    validate_phone,
    validate_username,
    verify_captcha,
)

from security import SecurityMiddleware
from i18n import APP_LANG, DIRECTION, IS_RTL, js_bundle, role_label, t
from tabs._forms import password_input, text_input, with_input_attrs
from tabs import tab_01, tab_02, tab_03, tab_04, tab_05, tab_06, tab_07, tab_account, tab_users, tab_logs

APP_DIR = Path(__file__).parent
STATIC_DIR = APP_DIR / "static"

# Order here = order shown in the sidebar, top to bottom.
# tab_logs is deliberately the LAST entry (superadmin only).
TABS = [tab_01, tab_02, tab_03, tab_04, tab_05, tab_06, tab_07, tab_account, tab_users, tab_logs]
TAB_LOOKUP = {tab.NAV_ID: tab for tab in TABS}
DEFAULT_TAB_ID = "tab_04"  # guest-accessible default so lower roles land on a valid page

_last_purge = 0.0  # time of the last automatic audit-log purge (interval: Logs tab settings)

# A signed-in session ends after this many hours even if it stays connected
# (a browser tab left open on a shared PC). 0 disables the limit.
try:
    SESSION_MAX_SECONDS = max(0.0, float(os.environ.get("SESSION_MAX_HOURS", "12"))) * 3600
except ValueError:
    SESSION_MAX_SECONDS = 12 * 3600
# Failed sign-in attempts (wrong CAPTCHA or password) one browser session may
# make; after that the page must be reloaded. Slows down scripted guessing
# without letting anyone lock a victim's ACCOUNT by mistyping CAPTCHAs.
SESSION_MAX_LOGIN_FAILURES = 10

# A "group" is not a tab by itself -- it's just a collapsible header in the
# sidebar for every tab whose NAV_GROUP matches its key.
GROUPS = {
    "dashboard": {"label": t("nav_dashboard"), "icon": "bi-speedometer2"},
}


def read_asset(*parts: str) -> str:
    """Read a text asset from the static/ directory."""
    return (STATIC_DIR.joinpath(*parts)).read_text(encoding="utf-8")


def asset_url(*parts: str) -> str:
    """URL of a static file with a content hash, e.g. ``css/styles.css?v=1a2b3c4d``.

    The files are served as separate, cacheable requests (they used to be
    inlined into every page load); the hash changes whenever the file does, so
    browsers never keep a stale copy after an update.
    """
    digest = hashlib.sha256(STATIC_DIR.joinpath(*parts).read_bytes()).hexdigest()[:10]
    return "/".join(parts) + "?v=" + digest


def _flat_link(tab, active_id: str = DEFAULT_TAB_ID) -> ui.Tag:
    """A single, top-level sidebar link (no children)."""
    return ui.tags.a(
        ui.tags.i(class_=f"bi {tab.NAV_ICON} nav-icon"),
        ui.tags.span(tab.NAV_LABEL),
        href="javascript:void(0)",
        class_="sidebar-link" + (" active" if tab.NAV_ID == active_id else ""),
        data_nav_id=tab.NAV_ID,
    )


def _group_block(group_key: str, children: list, active_id: str = DEFAULT_TAB_ID) -> ui.Tag:
    """A collapsible group header (e.g. "Dashboard") plus its sub-links."""
    group = GROUPS[group_key]
    submenu_id = f"submenu-{group_key}"

    toggle = ui.tags.a(
        ui.tags.i(class_=f"bi {group['icon']} nav-icon"),
        ui.tags.span(group["label"]),
        ui.tags.i(class_="bi bi-chevron-down chevron"),
        href="javascript:void(0)",
        class_="sidebar-link group-toggle",
        data_bs_toggle="collapse",
        data_bs_target=f"#{submenu_id}",
        role="button",
        aria_expanded="true",
        aria_controls=submenu_id,
    )

    sub_links = ui.tags.div(
        *[
            ui.tags.a(
                child.NAV_LABEL,
                href="javascript:void(0)",
                class_="sidebar-link sub-link"
                + (" active" if child.NAV_ID == active_id else ""),
                data_nav_id=child.NAV_ID,
            )
            for child in children
        ],
        id=submenu_id,
        class_="collapse show",
    )

    return ui.tags.div(toggle, sub_links, class_="nav-group")


def _tab_allowed(role: str, tab) -> bool:
    """True when ``role`` may see ``tab`` (unknown roles count as level 0)."""
    return ROLE_LEVELS.get(role, 0) >= ROLE_LEVELS.get(getattr(tab, "NAV_MIN_ROLE", "guest"), 0)


def resolve_tab(role: str, requested: str | None):
    """The tab to show: the requested one if this role may see it, else the
    default tab, else the first tab the role may see."""
    tab = TAB_LOOKUP.get(requested or DEFAULT_TAB_ID) or TAB_LOOKUP[DEFAULT_TAB_ID]
    if _tab_allowed(role, tab):
        return tab
    if _tab_allowed(role, TAB_LOOKUP[DEFAULT_TAB_ID]):
        return TAB_LOOKUP[DEFAULT_TAB_ID]
    return next((candidate for candidate in TABS if _tab_allowed(role, candidate)), TABS[0])


def build_sidebar(role: str = "guest", active_id: str = DEFAULT_TAB_ID) -> ui.Tag:
    """Walks TABS in order and hides links above the current user role."""
    nodes = []
    rendered_groups = set()

    visible_tabs = [t for t in TABS if _tab_allowed(role, t)]

    for tab in visible_tabs:
        group_key = getattr(tab, "NAV_GROUP", None)

        if group_key is None:
            nodes.append(_flat_link(tab, active_id))
            continue

        if group_key in rendered_groups:
            continue  # this group's children were all added the first time
        rendered_groups.add(group_key)

        children = [t for t in visible_tabs if getattr(t, "NAV_GROUP", None) == group_key]
        nodes.append(_group_block(group_key, children, active_id))

    return ui.tags.nav(*nodes, class_="sidebar-nav")


def build_main_content() -> ui.Tag:
    """The single content slot; server-side code swaps what's inside it."""
    return ui.output_ui("active_panel")


def login_ui() -> ui.Tag:
    return ui.div(
        ui.div(
            ui.div(
                ui.tags.i(class_="bi bi-shield-lock login-icon"),
                ui.h2(t("login_title")),
                ui.p(t("login_subtitle"), class_="login-subtitle"),
                ui.input_text(
                    "login_username", t("username"), placeholder=t("username"),
                    width="100%", autocomplete="username",
                ),
                with_input_attrs(
                    ui.input_password(
                        "login_password", t("password"), placeholder=t("password"), width="100%",
                    ),
                    autocomplete="current-password",
                ),
                ui.div(
                    ui.tags.label(t("login_security_check"), class_="form-label"),
                    ui.output_ui("login_captcha_ui"),
                    ui.input_text(
                        "login_captcha",
                        None,
                        placeholder=t("login_captcha_placeholder"),
                        width="100%",
                        autocomplete="off",
                        spellcheck="false",
                    ),
                    class_="login-captcha-block",
                ),
                ui.input_action_button("login_button", t("login_button"), class_="btn btn-primary w-100"),
                ui.output_ui("login_message"),
                ui.p(t("login_hint"), class_="login-hint"),
                class_="login-card",
            ),
            class_="login-page",
        )
    )


def dashboard_ui(role: str, active_id: str = DEFAULT_TAB_ID) -> ui.Tag:
    return ui.div(
        ui.tags.header(
            ui.tags.div(
                # Big, always-visible sidebar toggle. static/js/custom.js wires it
                # to the sidebar's built-in collapse control (see setupSidebarToggle).
                ui.tags.button(
                    ui.tags.i(class_="bi bi-list"),
                    id="sidebar-toggle-btn",
                    class_="sidebar-toggle-btn",
                    type="button",
                    title=t("sidebar_toggle"),
                    aria_label=t("sidebar_toggle"),
                    aria_expanded="true",
                    aria_controls="app-sidebar",
                ),
                ui.tags.div(
                    ui.tags.i(class_="bi bi-hexagon-fill"),
                    ui.tags.span(t("brand"), class_="brand-text"),
                    class_="brand",
                ),
                class_="topbar-left",
            ),
            ui.tags.div(
                ui.tags.i(class_="bi bi-hexagon-fill"),
                ui.tags.a(
                    ui.tags.span("github: https://github.com/masoudfaridi/pyshiny", class_="brand-text"),
                    href="https://github.com/masoudfaridi/pyshiny",
                    target="_blank",
                ),
                class_="brand brand-center",
            ),
            ui.tags.div(
                ui.tags.div(
                    ui.tags.span(role_label(current_role()), class_="role-badge"),
                    ui.tags.span(current_user()["username"], class_="username-badge"),
                    # Live clock, filled by static/js/custom.js from the device's
                    # clock: Persian -> Jalali date + weekday + time; English -> Gregorian.
                    ui.tags.span(
                        ui.tags.i(class_="bi bi-calendar3"),
                        ui.tags.span("", id="topbar-datetime-text", class_="topbar-datetime-text"),
                        id="topbar-datetime",
                        class_="topbar-datetime",
                    ),
                    ui.input_action_button(
                        "logout_button",
                        ui.tags.span(
                            ui.tags.i(class_="bi bi-box-arrow-right"),
                            " " + t("logout"),
                        ),
                        class_="logout-button",
                    ),
                    class_="topbar-user",
                ),
                ui.tags.div(
                    ui.tags.div(
                        ui.tags.button(
                            ui.tags.i(class_="bi bi-type"),
                            ui.tags.span(t("font_button"), id="font-current-label"),
                            ui.tags.i(class_="bi bi-chevron-down"),
                            class_="font-button", type="button", aria_label=t("font_aria"),
                        ),
                        ui.tags.div(
                            ui.tags.div(t("font_menu_title"), class_="font-menu-title"),
                            ui.tags.div(
                                ui.tags.label(t("font_body"), for_="font-select-ui"),
                                ui.tags.select(id="font-select-ui", class_="font-select"),
                                class_="font-role-row",
                            ),
                            ui.tags.div(
                                ui.tags.label(t("font_headings"), for_="font-select-heading"),
                                ui.tags.select(id="font-select-heading", class_="font-select"),
                                class_="font-role-row",
                            ),
                            ui.tags.div(
                                ui.tags.label(t("font_navigation"), for_="font-select-nav"),
                                ui.tags.select(id="font-select-nav", class_="font-select"),
                                class_="font-role-row",
                            ),
                            class_="font-menu",
                        ),
                        class_="font-picker",
                    ),
                    ui.tags.div(
                        ui.tags.button(
                            ui.tags.span("", id="theme-current-swatch", class_="theme-swatch"),
                            ui.tags.span(t("theme_light-blue"), id="theme-current-label"),
                            ui.tags.i(class_="bi bi-chevron-down"),
                            class_="theme-button", type="button", aria_label=t("theme_aria"),
                        ),
                        ui.tags.div(
                            ui.tags.div(t("theme_light_title"), class_="theme-section-title"),
                            ui.tags.div(class_="theme-options-light"),
                            ui.tags.div(t("theme_dark_title"), class_="theme-section-title"),
                            ui.tags.div(class_="theme-options-dark"),
                            class_="theme-menu",
                        ),
                        class_="theme-picker",
                    ),
                    class_="topbar-controls",
                ),
                class_="topbar-right",
            ),
            class_="topbar",
        ),
        # Plain flex layout (sidebar + content) instead of bslib's layout_sidebar:
        # we control collapsing ourselves (see setupSidebarToggle in custom.js),
        # so the menu can never get stuck hidden, and the content fills the page.
        ui.div(
            ui.tags.aside(build_sidebar(role, active_id), id="app-sidebar", class_="app-sidebar"),
            ui.div(id="sidebar-backdrop", class_="app-sidebar-backdrop"),
            ui.tags.main(ui.output_ui("active_panel"), class_="app-main"),
            class_="app-body",
        ),
        class_="app-shell",
    )


def build_app_shell() -> ui.Tag:
    return ui.div(ui.output_ui("root_ui"), id="root-container")


# =============================================================================
# LANGUAGE + DIRECTION  (English / LTR  <->  Persian / RTL)
# =============================================================================
# Everything is driven by ONE setting: APP_LANG in i18n.py (or the APP_LANG
# environment variable). Nothing needs to be commented / uncommented here.
#
#   APP_LANG = "en"  -> English, dir="ltr", css/bootstrap.css
#   APP_LANG = "fa"  -> Persian, dir="rtl", css/bootstrap.rtl.css
#
# APP_DIR_MODE is exposed to JavaScript so the Font picker shows the correct
# font list (static/fonts/ltr vs static/fonts/rtl). window.APP_I18N carries the
# few strings that the browser-side script (static/js/custom.js) needs.
# =============================================================================

APP_DIR_MODE = DIRECTION  # "ltr" or "rtl", derived from APP_LANG


def _inline_json(data: dict) -> str:
    """JSON that is safe to embed inside an inline <script> element."""
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


app_ui = ui.page_fillable(
    ui.tags.link(
        rel="stylesheet",
        href="css/bootstrap.rtl.css" if IS_RTL else "css/bootstrap.css",
    ),
    ui.tags.link(rel="stylesheet", href="vendor/bootstrap-icons/bootstrap-icons.min.css"),
    ui.tags.link(rel="stylesheet", href="css/fonts.css"),
    ui.tags.link(rel="stylesheet", href=asset_url("css", "styles.css")),
    ui.tags.script(src=asset_url("js", "custom.js")),
    ui.tags.script(
        f"document.documentElement.setAttribute('dir','{DIRECTION}');"
        f"document.documentElement.setAttribute('lang','{APP_LANG}');"
        f"window.APP_DIR_MODE='{APP_DIR_MODE}';"
        f"window.APP_LANG='{APP_LANG}';"
        f"window.APP_I18N={_inline_json(js_bundle())};"
    ),
    build_app_shell(),
    class_="app-shell-root",
)


def server(input, output, session):
    logged_in_user = reactive.Value(None)
    login_error = reactive.Value("")
    create_message = reactive.Value("")
    create_modal_message = reactive.Value("")  # errors shown inside the create popup
    create_prefill = reactive.Value({})        # values to restore when the popup reopens
    account_message = reactive.Value("")
    profile_message = reactive.Value("")
    users_refresh = reactive.Value(0)
    backups_refresh = reactive.Value(0)
    editing_user_id = reactive.Value(None)
    # Values captured when a password-protected button is clicked and used when
    # the callback runs after the password was confirmed (per browser session).
    pending: dict = {}
    edit_modal_message = reactive.Value("")
    captcha_hash = reactive.Value(None)
    captcha_expires = reactive.Value(None)
    captcha_image = reactive.Value("")
    captcha_nonce = reactive.Value(0)
    # (id, username, role) of the signed-in account, or None. The page shell is
    # rebuilt ONLY when this changes -- not when e-mail / phone are edited.
    shell_key = reactive.Value(None)

    # --- audit log helpers (see auth/audit.py) -------------------------------
    global _last_purge
    if time.time() - _last_purge > audit.get_settings()["purge_interval_hours"] * 3600:
        _last_purge = time.time()
        audit.purge_old()

    meta = audit.session_meta(session)  # {"sid", "ip", "ua"}
    state = {"login_at": None, "last_tab": None, "login_failures": 0}  # per-session, not reactive

    def _log(category, event, user=None, *, username=None, severity="info", detail=None):
        audit.log_event(
            category,
            event,
            user=user,
            username=username,
            severity=severity,
            detail=detail,
            session_id=meta["sid"],
            ip=meta["ip"],
            user_agent=meta["ua"],
        )

    def _session_seconds():
        started = state["login_at"]
        return round(time.monotonic() - started) if started is not None else None

    def _revoke_reason(user) -> str:
        try:
            row = get_user_by_id(int(user["id"]))
        except Exception:
            return "unknown"
        if row is None:
            return "account_deleted"
        if not row.get("is_active"):
            return "account_disabled"
        if row.get("session_version") != user.get("session_version", row.get("session_version")):
            return "password_changed"
        return "account_expired"

    def _note_login_failure(username, reason):
        state["login_failures"] += 1
        # A wrong CAPTCHA proves nothing about the password, so it must not count
        # towards the ACCOUNT lockout (otherwise anyone could lock any account,
        # superadmin included, just by submitting junk). It only counts per session.
        just_locked = register_login_failure(username) if reason != "captcha" else False
        _log(
            "auth", "login_failed", username=username,
            severity="warning", detail={"reason": reason},
        )
        if just_locked:
            _log(
                "security", "account_locked", username=username, severity="critical",
                detail={"lock_seconds": LOGIN_LOCKOUT_SECONDS},
            )

    def _on_ended():
        # Browser closed / connection lost while signed in.
        try:
            with reactive.isolate():
                person = logged_in_user()
            if person:
                _log("navigation", "session_ended", person,
                     detail={"duration_s": _session_seconds()})
        except Exception:
            pass

    session.on_ended(_on_ended)

    # Register content-tab modules once (namespaces tab_01-..., tab_02-..., ...).
    # This is the Python equivalent of calling moduleServer() for each tab in R.
    # Must NOT run inside login or active_panel.
    # Content-tab servers are registered further down, after
    # _ensure_valid_session exists: they re-check the role on every render.

    def _issue_captcha():
        # Generate a fresh offline image CAPTCHA and store only its hash in session state.
        data_url, answer_hash, expires_at = generate_captcha()
        captcha_image.set(data_url)
        captcha_hash.set(answer_hash)
        captcha_expires.set(expires_at)
        captcha_nonce.set(captcha_nonce() + 1)

    def _ensure_valid_session() -> dict | None:
        # Re-load the user from SQLite so revoked/expired sessions are dropped.
        user = logged_in_user()
        fresh = refresh_session_user(user)
        if fresh is None:
            if user is not None:
                _log("security", "session_revoked", user, severity="warning",
                     detail={"reason": _revoke_reason(user), "duration_s": _session_seconds()})
                state["login_at"] = None
                state["last_tab"] = None
                logged_in_user.set(None)
            return None
        # Attach session id / IP / UA so decorator denials (auth.core) can log them.
        fresh = {**fresh, **{k: v for k, v in meta.items() if v}}
        if (
            fresh["username"] != user.get("username")
            or fresh["role"] != user.get("role")
            or int(fresh["is_active"]) != int(user.get("is_active") or 0)
            or fresh.get("expire_date") != user.get("expire_date")
            or fresh.get("id_code") != user.get("id_code")
            or fresh.get("email") != user.get("email")
            or fresh.get("phone") != user.get("phone")
        ):
            logged_in_user.set(dict(fresh))
        return fresh

    # tab_07 (role-gated buttons) receives the *validating* getter, not the raw
    # reactive value, so each click re-checks the account in SQLite. It must be
    # registered after _ensure_valid_session is defined, and only once.
    tab_07.server(_ensure_valid_session)
    tab_logs.server(_ensure_valid_session)
    # Server-side role gate for every content tab (a hidden sidebar link is not
    # access control: a crafted page could still bind tab_01-hist, for example).
    for content_tab in (tab_01, tab_02, tab_03, tab_04, tab_05, tab_06):
        content_tab.server(_ensure_valid_session)

    def _sign_out(event: str | None = None, severity: str = "info", **detail) -> None:
        """Forget the signed-in user of this browser session (optionally logged)."""
        with reactive.isolate():
            person = logged_in_user()
        if person and event:
            _log("auth", event, person, severity=severity,
                 detail={"duration_s": _session_seconds(), **detail})
        state["login_at"] = None
        state["last_tab"] = None
        logged_in_user.set(None)
        pending.clear()

    def _reissue_session() -> None:
        """Re-read the signed-in account after it changed its OWN password (or a
        restore): this session stays valid, every other session of it is closed."""
        with reactive.isolate():
            person = logged_in_user()
        fresh = refresh_session_user({"id": person["id"]}) if person else None
        if fresh is not None:
            logged_in_user.set(fresh)

    @reactive.effect
    def _sync_shell_key():
        user = _ensure_valid_session()
        key = (user["id"], user["username"], user["role"]) if user else None
        with reactive.isolate():
            if shell_key() != key:
                shell_key.set(key)

    @reactive.effect
    def _session_lifetime():
        # Ends a signed-in session after SESSION_MAX_HOURS, even if left open.
        reactive.invalidate_later(60)
        started = state["login_at"]
        if not SESSION_MAX_SECONDS or started is None:
            return
        if time.monotonic() - started > SESSION_MAX_SECONDS:
            _sign_out("session_expired", reason="max_lifetime")
            login_error.set(t("login_session_expired"))

    @reactive.effect
    def _ensure_captcha_ready():
        # Issue the first CAPTCHA when the login screen is shown.
        if logged_in_user() is None and not captcha_image():
            _issue_captcha()

    @render.ui
    def root_ui():
        if shell_key() is None:
            return login_ui()
        with reactive.isolate():
            user = logged_in_user()
            try:
                requested = input.sidebar_nav()
            except Exception:
                requested = None
        if not user:
            return login_ui()
        active = resolve_tab(user["role"], requested).NAV_ID
        with user_context(user):
            return dashboard_ui(user["role"], active)

    @render.ui
    def login_captcha_ui():
        # CAPTCHA image + refresh control on the login form.
        captcha_nonce()
        src = captcha_image() or ""
        return ui.div(
            ui.tags.img(
                src=src,
                alt=t("login_captcha_alt"),
                class_="login-captcha-image",
            ),
            ui.tags.button(
                ui.tags.i(class_="bi bi-arrow-clockwise"),
                type="button",
                id="captcha_refresh_btn",
                title=t("login_refresh"),
                aria_label=t("login_refresh"),
                class_="btn btn-outline-secondary login-captcha-refresh",
            ),
            class_="login-captcha-row",
        )

    @reactive.effect
    @reactive.event(input.captcha_refresh)
    def _refresh_captcha():
        _issue_captcha()

    @reactive.effect
    @reactive.event(input.login_submit, input.login_button)
    def _login():
        # login_submit is set from JS after fields are flushed to avoid stale values.
        try:
            username = (input.login_username() or "").strip()
            password = input.login_password() or ""
            captcha_answer = input.login_captcha() or ""
        except (AttributeError, TypeError):
            login_error.set(t("login_invalid"))
            _issue_captcha()
            return

        if state["login_failures"] >= SESSION_MAX_LOGIN_FAILURES:
            _log("security", "login_blocked_session", username=username, severity="warning",
                 detail={"failures": state["login_failures"]})
            login_error.set(t("login_session_limit"))
            return

        locked, remaining = is_login_locked(username)
        if locked:
            _log("security", "login_blocked_locked", username=username,
                 severity="warning", detail={"remaining_s": remaining})
            login_error.set(t("login_locked", remaining=remaining))
            _issue_captcha()
            return

        if not verify_captcha(captcha_answer, captcha_hash(), captcha_expires()):
            _note_login_failure(username, "captcha")
            login_error.set(t("login_captcha_invalid"))
            _issue_captcha()
            return

        # Single-use CAPTCHA: invalidate after the first verification attempt.
        captcha_hash.set(None)
        captcha_expires.set(None)

        user = authenticate(username, password)
        if user is None:
            _note_login_failure(username, "bad_credentials")
            login_error.set(t("login_invalid"))
            _issue_captcha()
            return

        clear_login_failures(username)
        login_error.set("")
        state["login_at"] = time.monotonic()
        state["last_tab"] = None
        state["login_failures"] = 0
        _log("auth", "login_success", user)
        logged_in_user.set(user)
        # A fresh CAPTCHA is drawn when the login page is shown again (logout),
        # not now: no image work for a page nobody sees.
        captcha_image.set("")

    @render.ui
    def login_message():
        message = login_error()
        return ui.div(message, class_="login-error") if message else ui.div()

    @render.ui
    def account_message_ui():
        # Display the latest password-change status message.
        message = account_message()
        if not message:
            return ui.div()
        return ui.div(message, class_="user-create-message")

    @reactive.effect
    @reactive.event(input.logout_button)
    def _logout():
        _sign_out("logout")
        login_error.set("")
        create_message.set("")
        account_message.set("")
        profile_message.set("")
        pending.clear()

    @render.ui
    def active_panel():
        user = _ensure_valid_session()
        if not user:
            return ui.div()
        selected = DEFAULT_TAB_ID
        try:
            value = input.sidebar_nav()
            if value:
                selected = value
        except Exception:
            pass

        # Not allowed / unknown -> default tab or the first one this role may see.
        tab = resolve_tab(user["role"], selected)
        with user_context(user):
            return tab.panel()

    @reactive.effect
    @reactive.event(input.sidebar_nav)
    def _log_navigation():
        # One row per tab change (consecutive repeats of the same tab are skipped).
        # A forged / not-permitted tab id is a security event, not navigation.
        current = _ensure_valid_session()
        if not current:
            return
        nav_id = input.sidebar_nav()
        tab = TAB_LOOKUP.get(nav_id)
        if tab is None:
            _log("security", "unknown_tab_request", current, severity="warning",
                 detail={"tab": nav_id})
            return
        required = getattr(tab, "NAV_MIN_ROLE", "guest")
        if ROLE_LEVELS.get(current["role"], -1) < ROLE_LEVELS.get(required, 0):
            _log("security", "unauthorized_tab_request", current, severity="warning",
                 detail={"tab": nav_id, "required_role": required})
            return
        if state["last_tab"] != nav_id:
            state["last_tab"] = nav_id
            _log("navigation", "tab_opened", current, detail={"tab": nav_id})

    @render.ui
    def profile_message_ui():
        message = profile_message()
        if not message:
            return ui.div()
        return ui.div(message, class_="user-create-message")

    @reactive.effect
    @reactive.event(input.profile_save_button)
    def _update_profile_event():
        # Own e-mail / phone. The identification code is not editable here.
        current = _ensure_valid_session()
        if not current:
            return
        try:
            with user_context(current):
                update_own_profile(input.profile_email(), input.profile_phone())
        except (PermissionError, ValueError) as exc:
            profile_message.set(str(exc))
            return
        profile_message.set(t("account_profile_saved"))
        _ensure_valid_session()  # refresh the cached session user (e-mail / phone)

    @reactive.effect
    @reactive.event(input.change_password_button)
    def _change_password_event():
        # Change the password for the currently authenticated account.
        current = _ensure_valid_session()
        if not current:
            return

        new_password = input.new_own_password()
        confirm_password = input.new_own_password_confirm()
        if new_password != confirm_password:
            account_message.set(t("account_mismatch"))
            return

        try:
            with user_context(current):
                change_own_password(
                    input.current_password(),
                    new_password,
                )
            account_message.set(t("account_changed"))
        except (PermissionError, ValueError) as exc:
            account_message.set(str(exc))
            return
        # The password change closed every OTHER session of this account; keep this one.
        _reissue_session()
        for field in ("current_password", "new_own_password", "new_own_password_confirm"):
            ui.update_text(field, value="")

    def _toast(message: str, kind: str = "message") -> None:
        ui.notification_show(message, type=kind, duration=6)

    def _create_form() -> dict:
        """Read the create-user form (raises ValueError on invalid input)."""
        new_password = input.new_password()
        if new_password != input.new_password_confirm():
            raise ValueError(t("users_create_mismatch"))
        role = input.new_role()
        expire_date = None
        if role != "superadmin":
            try:
                if input.new_expire_enabled():
                    expire_date = input.new_expire_date()
            except (AttributeError, TypeError):
                expire_date = None
        return {
            "username": validate_username(input.new_username()),
            "password": validate_password(new_password, strict=False),
            "role": role,
            "expire_date": str(expire_date) if expire_date else None,
            "id_code": validate_id_code(input.new_id_code()),
            "email": validate_email(input.new_email()),
            "phone": validate_phone(input.new_phone()),
        }

    def _show_create_modal(values: dict | None = None, message: str = "") -> None:
        """Open the "create user" popup (optionally re-filled after a failed save)."""
        create_prefill.set(dict(values or {}))
        create_modal_message.set(message)
        ui.modal_show(tab_users.create_user_modal(values))

    @reactive.effect
    @reactive.event(input.create_user_open)
    def _open_create_modal():
        current = _ensure_valid_session()
        if not current or current["role"] != "superadmin":
            return
        create_message.set("")
        pending.pop("create", None)
        _show_create_modal()

    @reactive.effect
    @reactive.event(input.create_user)
    def _create_user_event():
        # Step 1 (Save in the popup): check the form. Mistakes are shown inside
        # the popup, before any password is asked.
        # Step 2: _run_create_user() -- confirmation dialog + the user's password.
        current = _ensure_valid_session()
        if not current:
            return
        try:
            form = _create_form()
        except ValueError as exc:
            create_modal_message.set(str(exc))
            return
        create_modal_message.set("")
        pending["create"] = form  # the confirmation dialog replaces the popup
        _run_create_user()

    @confirm_with_password(
        input, _ensure_valid_session,
        message=lambda: t("users_confirm_create",
                          username=pending.get("create", {}).get("username", "")),
        required_role="superadmin",
    )
    def _run_create_user():
        # Runs ONLY after the dialog and the correct password (see auth/confirm.py).
        form = pending.pop("create", None)
        if not form:
            return
        try:
            create_user(
                form["username"], form["password"], form["role"], form["expire_date"],
                id_code=form["id_code"], email=form["email"], phone=form["phone"],
            )
        except PermissionError:
            _toast(t("users_denied_create"), "error")
            return
        except (sqlite3.IntegrityError, ValueError) as exc:
            # e.g. username / identification code already taken: reopen the
            # popup with what was typed (passwords must be entered again).
            message = t("users_exists") if isinstance(exc, sqlite3.IntegrityError) else str(exc)
            _show_create_modal({k: v for k, v in form.items() if k != "password"}, message)
            return
        create_message.set(t("users_created"))
        _toast(t("users_created"))
        users_refresh.set(users_refresh() + 1)

    @render.ui
    def create_modal_message_ui():
        message = create_modal_message()
        return ui.div(message, class_="login-error mt-3") if message else ui.div()

    @render.ui
    def user_create_message():
        # Render the latest create-user status message.
        message = create_message()
        if not message:
            return ui.div()
        return ui.div(message, class_="user-create-message")

    @render.ui
    def create_expiry_field():
        # Show an optional expiration date for non-Superadmin accounts only.
        try:
            role = input.new_role()
        except (AttributeError, TypeError, SilentException):
            role = "guest"

        if role == "superadmin":
            return ui.p(
                t("superadmin_no_expiry"),
                class_="form-text text-muted",
            )

        # Depends on create_prefill: every (re)opened popup redraws this field.
        prefill = create_prefill()
        return ui.div(
            ui.input_checkbox(
                "new_expire_enabled",
                t("set_expiry"),
                value=bool(prefill.get("expire_date")),
            ),
            ui.output_ui("create_expiry_date_input"),
        )

    @render.ui
    def create_expiry_date_input():
        # Only show the date picker when the optional expiration checkbox is enabled.
        try:
            enabled = input.new_expire_enabled()
        except (AttributeError, TypeError):
            enabled = False
        if not enabled:
            return ui.div()
        # Depends on create_prefill: every (re)opened popup redraws this field.
        prefill = create_prefill()
        return ui.input_date(
            "new_expire_date",
            t("expiry_date"),
            value=prefill.get("expire_date"),
            width="100%",
        )


    def _load_user_row(user_id: int, current) -> dict | None:
        with user_context(current):
            rows = list_users()
        return next((row for row in rows if int(row["id"]) == int(user_id)), None)

    def _build_edit_modal(selected: dict):
        # Modal body for editing a single account.
        has_expiry = bool(selected.get("expire_date"))
        return ui.modal(
            ui.div(
                ui.div(
                    text_input("edit_username", t("username"), selected["username"]),
                    text_input("edit_id_code", t("id_code"), selected.get("id_code") or "", ltr=True),
                    text_input("edit_email", t("email"), selected.get("email") or "", ltr=True),
                    text_input("edit_phone", t("phone"), selected.get("phone") or "", ltr=True),
                    password_input("edit_password", t("edit_new_password")),
                    password_input("edit_password_confirm", t("confirm_new_password")),
                    ui.input_select(
                        "edit_role",
                        t("access_level"),
                        {r: role_label(r) for r in ("guest", "user", "admin", "superadmin")},
                        selected=selected["role"],
                        width="100%",
                    ),
                    ui.div(
                        ui.output_ui("edit_expiry_field"),
                        ui.input_checkbox(
                            "edit_is_active",
                            t("edit_active"),
                            value=bool(selected["is_active"]),
                        ),
                        class_="form-grid-cell",
                    ),
                    class_="form-grid",
                ),
                ui.output_ui("edit_modal_message_ui"),
                class_="user-edit-modal-body",
            ),
            title=t("edit_title", username=selected["username"]),
            easy_close=True,
            footer=ui.div(
                ui.div(
                    ui.input_action_button(
                        "save_user", t("edit_save"), class_="btn btn-primary"
                    ),
                    ui.modal_button(t("edit_cancel"), class_="btn btn-secondary"),
                    class_="d-flex gap-2",
                ),
                ui.input_action_button(
                    "delete_user", t("edit_delete"), class_="btn btn-outline-danger"
                ),
                class_="d-flex w-100 align-items-center justify-content-between",
            ),
            size="l",
        )

    @render.ui
    def edit_expiry_field():
        # Optional expiration controls inside the edit modal.
        # Re-validate against SQLite instead of trusting the cached session
        # value, so a superadmin who was just demoted/deactivated in another
        # session loses access to this control immediately, not on the next
        # unrelated input event.
        current = _ensure_valid_session()
        if not current or current["role"] != "superadmin":
            return ui.div()

        try:
            role = input.edit_role()
        except (AttributeError, TypeError):
            role = None

        selected_id = editing_user_id()
        selected = None
        if selected_id is not None:
            selected = _load_user_row(selected_id, current)

        if role is None and selected is not None:
            role = selected["role"]
        if role == "superadmin":
            return ui.p(
                t("superadmin_no_expiry"),
                class_="form-text text-muted",
            )

        has_expiry = bool(selected and selected.get("expire_date"))
        return ui.div(
            ui.input_checkbox(
                "edit_expire_enabled",
                t("set_expiry"),
                value=has_expiry,
            ),
            ui.output_ui("edit_expiry_date_input"),
        )

    @render.ui
    def edit_expiry_date_input():
        # See edit_expiry_field() above for why this revalidates via SQLite.
        current = _ensure_valid_session()
        if not current or current["role"] != "superadmin":
            return ui.div()

        try:
            enabled = input.edit_expire_enabled()
        except (AttributeError, TypeError):
            enabled = False
        if not enabled:
            return ui.div()

        selected_id = editing_user_id()
        selected = _load_user_row(selected_id, current) if selected_id is not None else None
        value = selected["expire_date"] if selected and selected.get("expire_date") else None
        return ui.input_date(
            "edit_expire_date",
            t("expiry_date"),
            value=value,
        )

    @render.ui
    def edit_modal_message_ui():
        message = edit_modal_message()
        if not message:
            return ui.div()
        return ui.div(message, class_="user-create-message")

    @reactive.effect
    @reactive.event(input.user_action_edit)
    def _open_edit_modal():
        # Open the edit popup when Change is clicked in the users table.
        current = _ensure_valid_session()
        if not current or current["role"] != "superadmin":
            return
        try:
            selected_id = int(input.user_action_edit())
        except (TypeError, ValueError):
            return
        selected = _load_user_row(selected_id, current)
        if selected is None:
            create_message.set(t("users_not_found"))
            return
        editing_user_id.set(selected_id)
        edit_modal_message.set("")
        pending.pop("edit", None)  # drop a half-finished edit (it may hold a password)
        ui.modal_show(_build_edit_modal(selected))

    def _ask_delete(selected_id: int, current: dict) -> None:
        """Remember who is to be deleted, then open the password-protected flow."""
        try:
            row = _load_user_row(selected_id, current)
        except PermissionError:
            create_message.set(t("users_denied_delete"))
            return
        if row is None:
            create_message.set(t("users_not_found"))
            return
        pending["delete"] = {"id": int(selected_id), "username": row["username"]}
        _run_delete_user()

    @reactive.effect
    @reactive.event(input.user_action_delete)
    def _delete_from_table():
        # Delete button in the users table. (The browser-side confirm() was removed:
        # the dialog of @confirm_with_password is the confirmation now.)
        current = _ensure_valid_session()
        if not current:
            return
        try:
            selected_id = int(input.user_action_delete())
        except (TypeError, ValueError):
            return
        _ask_delete(selected_id, current)

    @reactive.effect
    @reactive.event(input.delete_user)
    def _delete_user_event():
        # Delete button inside the edit modal.
        current = _ensure_valid_session()
        if not current:
            return
        selected_id = editing_user_id()
        if selected_id is None:
            return
        _ask_delete(int(selected_id), current)

    @confirm_with_password(
        input, _ensure_valid_session,
        message=lambda: t("users_confirm_delete", username=pending.get("delete", {}).get("username", "")),
        required_role="superadmin",
    )
    def _run_delete_user():
        target = pending.pop("delete", None)
        if not target:
            return
        try:
            delete_user(target["id"])
        except PermissionError:
            _toast(t("users_denied_delete"), "error")
            return
        except ValueError as exc:
            _toast(str(exc), "error")
            return
        create_message.set(t("users_deleted"))
        _toast(t("users_deleted"))
        users_refresh.set(users_refresh() + 1)
        editing_user_id.set(None)

    def _reopen_edit_modal(form: dict, message: str, current: dict) -> None:
        """Show the edit popup again (with what was typed) after a failed save."""
        selected = _load_user_row(form["id"], current)
        if selected is None:
            _toast(message, "error")
            return
        selected = {
            **selected,
            "username": form["username"],
            "role": form["role"],
            "is_active": int(form["is_active"]),
            "expire_date": form["expire_date"],
            "id_code": form["id_code"],
            "email": form["email"],
            "phone": form["phone"],
        }
        editing_user_id.set(form["id"])
        edit_modal_message.set(message)
        ui.modal_show(_build_edit_modal(selected))

    @reactive.effect
    @reactive.event(input.save_user)
    def _save_user_event():
        # Step 1 (click): read + check the popup and keep a copy of it (the popup
        # is replaced by the confirmation dialog). Format mistakes stay in the popup.
        # Step 2: _run_save_user() -- confirmation dialog + the user's password.
        current = _ensure_valid_session()
        if not current:
            return

        selected_id = editing_user_id()
        if selected_id is None:
            return

        new_password = input.edit_password()
        confirm_password = input.edit_password_confirm()
        if new_password and new_password != confirm_password:
            edit_modal_message.set(t("edit_mismatch"))
            return

        role = input.edit_role()
        expire_date = None
        if role != "superadmin":
            try:
                if input.edit_expire_enabled():
                    expire_date = input.edit_expire_date()
            except (AttributeError, TypeError):
                expire_date = None

        try:
            form = {
                "id": int(selected_id),
                "username": validate_username(input.edit_username()),
                "role": role,
                "is_active": bool(input.edit_is_active()),
                "password": validate_password(new_password, strict=False) if new_password else "",
                "expire_date": str(expire_date) if expire_date else None,
                "id_code": validate_id_code(input.edit_id_code()),
                "email": validate_email(input.edit_email()),
                "phone": validate_phone(input.edit_phone()),
            }
        except ValueError as exc:
            edit_modal_message.set(str(exc))
            return

        edit_modal_message.set("")
        pending["edit"] = form
        _run_save_user()

    @confirm_with_password(
        input, _ensure_valid_session,
        message=lambda: t("users_confirm_update", username=pending.get("edit", {}).get("username", "")),
        required_role="superadmin",
    )
    def _run_save_user():
        form = pending.pop("edit", None)
        if not form:
            return
        current = _ensure_valid_session()
        if not current:
            return
        try:
            update_user(
                form["id"], form["username"], form["role"], form["is_active"],
                form["password"], form["expire_date"],
                id_code=form["id_code"], email=form["email"], phone=form["phone"],
            )
        except PermissionError:
            _toast(t("users_denied_edit"), "error")
            return
        except sqlite3.IntegrityError:
            _reopen_edit_modal(form, t("users_exists"), current)
            return
        except ValueError as exc:
            _reopen_edit_modal(form, str(exc), current)
            return

        create_message.set(t("users_updated"))
        _toast(t("users_updated"))
        users_refresh.set(users_refresh() + 1)
        editing_user_id.set(None)
        if form["id"] == int(current["id"]):
            # The signed-in account was edited: re-read it (disabled / expired /
            # renamed accounts are signed out or refreshed right away). A new
            # password set for one's OWN account keeps this session signed in.
            if form["password"]:
                _reissue_session()
            _ensure_valid_session()

    @render.ui
    def users_table():
        # Account table with per-row Change / Delete actions.
        users_refresh()
        # Revalidate against SQLite rather than the cached reactive value: this
        # table lists every account's username, role, and activity metadata, so
        # a superadmin who was demoted or deactivated in another session must
        # lose the ability to keep viewing it right away.
        current = _ensure_valid_session()
        if not current or current["role"] != "superadmin":
            return ui.div()

        with user_context(current):
            rows = list_users()

        header = ui.tags.tr(
            ui.tags.th(t("users_col_actions")),
            ui.tags.th(t("users_col_id")),
            ui.tags.th(t("users_col_username")),
            ui.tags.th(t("users_col_id_code")),
            ui.tags.th(t("users_col_email")),
            ui.tags.th(t("users_col_phone")),
            ui.tags.th(t("users_col_role")),
            ui.tags.th(t("users_col_active")),
            ui.tags.th(t("users_col_expires")),
            ui.tags.th(t("users_col_created")),
        )

        def _cell(value, ltr=False):
            # LTR cells keep e-mail / phone / codes readable inside an RTL page.
            if not value:
                return ui.tags.td(t("users_missing_info"), class_="text-muted")
            return ui.tags.td(value, dir="ltr", class_="ltr-cell") if ltr else ui.tags.td(value)

        body = []
        for row in rows:
            actions = ui.tags.td(
                ui.tags.button(
                    t("users_change"),
                    type="button",
                    class_="btn btn-sm btn-primary user-action-edit",
                    data_user_id=str(row["id"]),
                ),
                " ",
                ui.tags.button(
                    t("users_delete"),
                    type="button",
                    class_="btn btn-sm btn-danger user-action-delete",
                    data_user_id=str(row["id"]),
                    data_username=row["username"],
                ),
                class_="user-actions-cell",
            )
            body.append(
                ui.tags.tr(
                    actions,
                    ui.tags.td(str(row["id"])),
                    ui.tags.td(row["username"]),
                    _cell(row.get("id_code"), ltr=True),
                    _cell(row.get("email"), ltr=True),
                    _cell(row.get("phone"), ltr=True),
                    ui.tags.td(role_label(row["role"])),
                    ui.tags.td(t("yes") if row["is_active"] else t("no")),
                    ui.tags.td(row["expire_date"] or t("never")),
                    ui.tags.td(row["created_at"]),
                )
            )
        return ui.tags.table(header, *body, class_="users-table")

    # ---------------- accounts database: backup / restore ------------------
    @render.ui
    def backups_table():
        backups_refresh()
        current = _ensure_valid_session()
        if not current or current["role"] != "superadmin":
            return ui.div()
        try:
            with user_context(current):
                items = list_backups()
        except PermissionError:
            return ui.div()
        if not items:
            return ui.p(t("backup_none"), class_="text-muted")

        header = ui.tags.tr(
            ui.tags.th(t("backup_col_actions")),
            ui.tags.th(t("backup_col_name")),
            ui.tags.th(t("backup_col_created")),
            ui.tags.th(t("backup_col_size")),
            ui.tags.th(t("backup_col_type")),
        )

        def action_button(action: str, label_key: str, style: str, name: str):
            return ui.tags.button(
                t(label_key), type="button", data_action=action, data_name=name,
                class_=f"btn btn-sm {style} backup-action me-1",
            )

        body = []
        for item in items:
            name = item["name"]
            body.append(
                ui.tags.tr(
                    ui.tags.td(
                        action_button("restore", "backup_restore", "btn-warning", name),
                        action_button("download", "backup_download", "btn-secondary", name),
                        action_button("delete", "backup_delete", "btn-danger", name),
                        class_="user-actions-cell",
                    ),
                    ui.tags.td(name, dir="ltr", class_="ltr-cell"),
                    ui.tags.td(item["created"], dir="ltr", class_="ltr-cell"),
                    ui.tags.td(backup.format_size(item["size"]), dir="ltr", class_="ltr-cell"),
                    ui.tags.td(t(f"backup_type_{item['kind']}")),
                )
            )
        return ui.tags.table(header, *body, class_="users-table")

    @reactive.effect
    @reactive.event(input.backup_create)
    def _backup_create_event():
        # Creating a copy changes nothing, so it needs no password (it is logged).
        current = _ensure_valid_session()
        if not current:
            return
        try:
            with user_context(current):
                info = create_backup()
        except PermissionError:
            _toast(t("backup_denied"), "error")
            return
        except (ValueError, OSError) as exc:
            _toast(str(exc), "error")
            return
        backups_refresh.set(backups_refresh() + 1)
        _toast(t("backup_created", name=info["name"]))

    @reactive.effect
    @reactive.event(input.backup_action)
    def _backup_action_event():
        # Restore / Download / Delete buttons of the backups table (static/js/custom.js).
        # Every one of them goes through @confirm_with_password.
        current = _ensure_valid_session()
        if not current:
            return
        payload = input.backup_action()
        if not isinstance(payload, dict):
            return
        action, name = payload.get("action"), payload.get("name")
        runners = {
            "restore": _run_restore_backup,
            "download": _run_download_backup,
            "delete": _run_delete_backup,
        }
        if action not in runners or not backup.is_valid_name(name):
            return  # forged input
        pending["backup"] = name
        runners[action]()

    @confirm_with_password(
        input, _ensure_valid_session,
        message=lambda: t("backup_confirm_restore", name=pending.get("backup", "")),
        required_role="superadmin",
    )
    def _run_restore_backup():
        name = pending.pop("backup", None)
        try:
            result = restore_backup(name)
        except PermissionError:
            _toast(t("backup_denied"), "error")
            return
        except (ValueError, OSError) as exc:
            _toast(str(exc), "error")
            return
        users_refresh.set(users_refresh() + 1)
        backups_refresh.set(backups_refresh() + 1)
        editing_user_id.set(None)
        _toast(
            t("backup_restored", name=result["restored"]["name"],
              users=result["users"], safety=result["safety"]["name"])
        )
        # The restored data may have removed / disabled the account in use.
        _reissue_session()
        _ensure_valid_session()

    @confirm_with_password(
        input, _ensure_valid_session,
        message=lambda: t("backup_confirm_delete", name=pending.get("backup", "")),
        required_role="superadmin",
    )
    def _run_delete_backup():
        name = pending.pop("backup", None)
        try:
            delete_backup(name)
        except PermissionError:
            _toast(t("backup_denied"), "error")
            return
        except (ValueError, OSError) as exc:
            _toast(str(exc), "error")
            return
        backups_refresh.set(backups_refresh() + 1)
        _toast(t("backup_deleted"))

    @confirm_with_password(
        input, _ensure_valid_session,
        message=lambda: t("backup_confirm_download", name=pending.get("backup", "")),
        required_role="superadmin",
    )
    def _run_download_backup():
        # The file only reaches the browser AFTER the password was confirmed:
        # it is offered as a download link inside a dialog.
        name = pending.pop("backup", None)
        try:
            data = read_backup(name)
            if len(data) > 20 * 1024 * 1024:
                raise ValueError(t("err_backup_too_large", n=20))
        except PermissionError:
            _toast(t("backup_denied"), "error")
            return
        except (ValueError, OSError) as exc:
            _toast(str(exc), "error")
            return
        href = "data:application/octet-stream;base64," + base64.b64encode(data).decode("ascii")
        ui.modal_show(
            ui.modal(
                ui.p(t("backup_download_text")),
                ui.tags.a(name, href=href, download=name, class_="btn btn-primary"),
                title=t("backup_download_title"),
                easy_close=True,
                footer=ui.modal_button(t("backup_close"), class_="btn btn-secondary"),
            )
        )

    @reactive.effect
    @reactive.event(input.backup_import)
    def _backup_import_event():
        # Step 1: take the chosen file. Step 2: _run_import_backup() asks for the password.
        current = _ensure_valid_session()
        if not current:
            return
        files = input.backup_upload()
        if not files:
            _toast(t("backup_no_file"), "error")
            return
        chosen = files[0]
        if int(chosen.get("size") or 0) > backup.MAX_IMPORT_BYTES:
            _toast(t("err_backup_too_large", n=backup.MAX_IMPORT_BYTES // (1024 * 1024)), "error")
            return
        try:
            pending["upload"] = Path(chosen["datapath"]).read_bytes()
        except (OSError, KeyError):
            _toast(t("err_backup_invalid"), "error")
            return
        _run_import_backup()

    @confirm_with_password(
        input, _ensure_valid_session,
        message=t("backup_confirm_import"),
        required_role="superadmin",
    )
    def _run_import_backup():
        data = pending.pop("upload", None)
        try:
            info = import_backup(data or b"")
        except PermissionError:
            _toast(t("backup_denied"), "error")
            return
        except (ValueError, OSError) as exc:
            _toast(str(exc), "error")
            return
        backups_refresh.set(backups_refresh() + 1)
        _toast(t("backup_imported", name=info["name"]))




shiny_app = App(app_ui, server, static_assets=STATIC_DIR)
app = SecurityMiddleware(shiny_app, max_upload_bytes=backup.MAX_IMPORT_BYTES + 1024 * 1024)
