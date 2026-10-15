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

import json
import time
from datetime import date
from pathlib import Path

from shiny import App, reactive, render, ui
import sqlite3

from auth import (
    LOGIN_LOCKOUT_SECONDS,
    ROLE_LEVELS,
    audit,
    authenticate,
    change_own_password,
    clear_login_failures,
    create_user,
    current_role,
    current_user,
    delete_user,
    generate_captcha,
    get_user_by_id,
    is_login_locked,
    list_users,
    refresh_session_user,
    register_login_failure,
    update_user,
    user_context,
    verify_captcha,
)

from i18n import APP_LANG, DIRECTION, IS_RTL, js_bundle, role_label, t
from tabs import tab_01, tab_02, tab_03, tab_04, tab_05, tab_06, tab_07, tab_account, tab_users, tab_logs

APP_DIR = Path(__file__).parent
STATIC_DIR = APP_DIR / "static"

# Order here = order shown in the sidebar, top to bottom.
# tab_logs is deliberately the LAST entry (superadmin only).
TABS = [tab_01, tab_02, tab_03, tab_04, tab_05, tab_06, tab_07, tab_account, tab_users, tab_logs]
TAB_LOOKUP = {tab.NAV_ID: tab for tab in TABS}
DEFAULT_TAB_ID = "tab_04"  # guest-accessible default so lower roles land on a valid page

_last_purge = 0.0  # audit-log retention purge runs at most once an hour

# A "group" is not a tab by itself -- it's just a collapsible header in the
# sidebar for every tab whose NAV_GROUP matches its key.
GROUPS = {
    "dashboard": {"label": t("nav_dashboard"), "icon": "bi-speedometer2"},
}


def read_asset(*parts: str) -> str:
    """Read a text asset from the static/ directory."""
    return (STATIC_DIR.joinpath(*parts)).read_text(encoding="utf-8")


def _flat_link(tab) -> ui.Tag:
    """A single, top-level sidebar link (no children)."""
    return ui.tags.a(
        ui.tags.i(class_=f"bi {tab.NAV_ICON} nav-icon"),
        ui.tags.span(tab.NAV_LABEL),
        href="javascript:void(0)",
        class_="sidebar-link" + (" active" if tab.NAV_ID == DEFAULT_TAB_ID else ""),
        data_nav_id=tab.NAV_ID,
    )


def _group_block(group_key: str, children: list) -> ui.Tag:
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
                + (" active" if child.NAV_ID == DEFAULT_TAB_ID else ""),
                data_nav_id=child.NAV_ID,
            )
            for child in children
        ],
        id=submenu_id,
        class_="collapse show",
    )

    return ui.tags.div(toggle, sub_links, class_="nav-group")


def build_sidebar(role: str = "guest") -> ui.Tag:
    """Walks TABS in order and hides links above the current user role."""
    nodes = []
    rendered_groups = set()

    role_levels = {"guest": 0, "user": 1, "admin": 2, "superadmin": 3}

    def allowed(tab):
        return role_levels.get(role, 0) >= role_levels.get(getattr(tab, "NAV_MIN_ROLE", "guest"), 0)

    visible_tabs = [t for t in TABS if allowed(t)]

    for tab in visible_tabs:
        group_key = getattr(tab, "NAV_GROUP", None)

        if group_key is None:
            nodes.append(_flat_link(tab))
            continue

        if group_key in rendered_groups:
            continue  # this group's children were all added the first time
        rendered_groups.add(group_key)

        children = [t for t in visible_tabs if getattr(t, "NAV_GROUP", None) == group_key]
        nodes.append(_group_block(group_key, children))

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
                ui.input_text("login_username", t("username"), placeholder=t("username")),
                ui.input_password("login_password", t("password"), placeholder=t("password")),
                ui.div(
                    ui.tags.label(t("login_security_check"), class_="form-label"),
                    ui.output_ui("login_captcha_ui"),
                    ui.input_text(
                        "login_captcha",
                        None,
                        placeholder=t("login_captcha_placeholder"),
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


def dashboard_ui(role: str) -> ui.Tag:
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
            ui.tags.aside(build_sidebar(role), id="app-sidebar", class_="app-sidebar"),
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
    ui.tags.link(rel="stylesheet", href="css/fonts.css"),
    ui.tags.style(read_asset("css", "styles.css")),
    ui.tags.script(read_asset("js", "custom.js")),
    ui.tags.script(
        f"document.documentElement.setAttribute('dir','{DIRECTION}');"
        f"document.documentElement.setAttribute('lang','{APP_LANG}');"
        f"window.APP_DIR_MODE='{APP_DIR_MODE}';"
        f"window.APP_I18N={_inline_json(js_bundle())};"
    ),
    build_app_shell(),
    class_="app-shell-root",
)


def server(input, output, session):
    logged_in_user = reactive.Value(None)
    login_error = reactive.Value("")
    create_message = reactive.Value("")
    account_message = reactive.Value("")
    users_refresh = reactive.Value(0)
    editing_user_id = reactive.Value(None)
    edit_modal_message = reactive.Value("")
    captcha_hash = reactive.Value(None)
    captcha_expires = reactive.Value(None)
    captcha_image = reactive.Value("")
    captcha_nonce = reactive.Value(0)

    # --- audit log helpers (see auth/audit.py) -------------------------------
    global _last_purge
    if time.time() - _last_purge > 3600:
        _last_purge = time.time()
        audit.purge_old()

    meta = audit.session_meta(session)  # {"sid", "ip", "ua"}
    state = {"login_at": None, "last_tab": None}  # per-session, not reactive

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
        return "account_expired"

    def _note_login_failure(username, reason):
        just_locked = register_login_failure(username)
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
    tab_01.server()
    tab_02.server()
    tab_03.server()
    tab_04.server()
    tab_05.server()
    tab_06.server()


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
                     detail={"reason": _revoke_reason(user)})
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
        ):
            logged_in_user.set(dict(fresh))
        return fresh

    # tab_07 (role-gated buttons) receives the *validating* getter, not the raw
    # reactive value, so each click re-checks the account in SQLite. It must be
    # registered after _ensure_valid_session is defined, and only once.
    tab_07.server(_ensure_valid_session)
    tab_logs.server(_ensure_valid_session)

    @reactive.effect
    def _ensure_captcha_ready():
        # Issue the first CAPTCHA when the login screen is shown.
        if logged_in_user() is None and not captcha_image():
            _issue_captcha()

    @render.ui
    def root_ui():
        user = _ensure_valid_session()
        if not user:
            return login_ui()
        with user_context(user):
            return dashboard_ui(user["role"])

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
                " " + t("login_refresh"),
                type="button",
                id="captcha_refresh_btn",
                class_="btn btn-sm btn-outline-secondary login-captcha-refresh",
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
        _log("auth", "login_success", user)
        logged_in_user.set(user)
        _issue_captcha()

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
        person = logged_in_user()
        if person:
            _log("auth", "logout", person, detail={"duration_s": _session_seconds()})
        state["login_at"] = None
        state["last_tab"] = None
        logged_in_user.set(None)
        login_error.set("")
        create_message.set("")
        account_message.set("")

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

        role_levels = {"guest": 0, "user": 1, "admin": 2, "superadmin": 3}
        tab = TAB_LOOKUP.get(selected, TAB_LOOKUP.get(DEFAULT_TAB_ID, TABS[0]))
        required = getattr(tab, "NAV_MIN_ROLE", "guest")
        if role_levels[user["role"]] < role_levels.get(required, 0):
            # Fall back to the first tab this role is allowed to see.
            for candidate in TABS:
                min_role = getattr(candidate, "NAV_MIN_ROLE", "guest")
                if role_levels[user["role"]] >= role_levels.get(min_role, 0):
                    tab = candidate
                    break
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

    @reactive.effect
    @reactive.event(input.create_user)
    def _create_user_event():
        # Read the current session before attempting a protected operation.
        current = _ensure_valid_session()
        if not current:
            return

        new_password = input.new_password()
        confirm_password = input.new_password_confirm()
        if new_password != confirm_password:
            create_message.set(t("users_create_mismatch"))
            return

        try:
            # The @superadmin decorator performs the actual authorization check.
            with user_context(current):
                role = input.new_role()
                expire_date = None
                if role != "superadmin":
                    try:
                        if input.new_expire_enabled():
                            expire_date = input.new_expire_date()
                    except (AttributeError, TypeError):
                        expire_date = None
                create_user(
                    input.new_username(),
                    new_password,
                    role,
                    str(expire_date) if expire_date else None,
                )
            create_message.set(t("users_created"))
            users_refresh.set(users_refresh() + 1)
        except PermissionError:
            create_message.set(t("users_denied_create"))
        except sqlite3.IntegrityError:
            create_message.set(t("users_exists"))
        except ValueError as exc:
            create_message.set(str(exc))

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
        except (AttributeError, TypeError):
            role = "guest"

        if role == "superadmin":
            return ui.p(
                t("superadmin_no_expiry"),
                class_="form-text text-muted",
            )

        return ui.div(
            ui.input_checkbox(
                "new_expire_enabled",
                t("set_expiry"),
                value=False,
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
        return ui.input_date(
            "new_expire_date",
            t("expiry_date"),
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
                ui.input_text(
                    "edit_username",
                    t("username"),
                    value=selected["username"],
                ),
                ui.input_select(
                    "edit_role",
                    t("access_level"),
                    {
                        "guest": role_label("guest"),
                        "user": role_label("user"),
                        "admin": role_label("admin"),
                        "superadmin": role_label("superadmin"),
                    },
                    selected=selected["role"],
                ),
                ui.output_ui("edit_expiry_field"),
                ui.input_checkbox(
                    "edit_is_active",
                    t("edit_active"),
                    value=bool(selected["is_active"]),
                ),
                ui.input_password(
                    "edit_password",
                    t("edit_new_password"),
                ),
                ui.input_password(
                    "edit_password_confirm",
                    t("confirm_new_password"),
                ),
                ui.output_ui("edit_modal_message_ui"),
                class_="user-edit-modal-body",
            ),
            title=t("edit_title", username=selected["username"]),
            easy_close=True,
            footer=ui.div(
                ui.input_action_button(
                    "save_user", t("edit_save"), class_="btn btn-primary"
                ),
                ui.input_action_button(
                    "delete_user", t("edit_delete"), class_="btn btn-danger ms-2"
                ),
                ui.modal_button(t("edit_cancel"), class_="btn btn-secondary ms-2"),
            ),
            size="m",
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
        ui.modal_show(_build_edit_modal(selected))

    @reactive.effect
    @reactive.event(input.user_action_delete)
    def _delete_from_table():
        # Delete directly from the table Delete button (after JS confirm).
        current = _ensure_valid_session()
        if not current:
            return
        try:
            selected_id = int(input.user_action_delete())
        except (TypeError, ValueError):
            return
        try:
            with user_context(current):
                delete_user(selected_id)
            create_message.set(t("users_deleted"))
            users_refresh.set(users_refresh() + 1)
            editing_user_id.set(None)
            ui.modal_remove()
        except PermissionError:
            create_message.set(t("users_denied_delete"))
        except ValueError as exc:
            create_message.set(str(exc))

    @reactive.effect
    @reactive.event(input.save_user)
    def _save_user_event():
        # Save the account currently open in the edit modal.
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

        try:
            with user_context(current):
                role = input.edit_role()
                expire_date = None
                if role != "superadmin":
                    try:
                        if input.edit_expire_enabled():
                            expire_date = input.edit_expire_date()
                    except (AttributeError, TypeError):
                        expire_date = None
                update_user(
                    int(selected_id),
                    input.edit_username(),
                    role,
                    input.edit_is_active(),
                    new_password or "",
                    str(expire_date) if expire_date else None,
                )

            # Refresh the session when the currently logged-in account is edited.
            if int(selected_id) == int(current["id"]):
                current["username"] = input.edit_username().strip()
                current["role"] = role
                current["is_active"] = int(input.edit_is_active())
                current["expire_date"] = str(expire_date) if expire_date else None
                expired = (
                    current["role"] != "superadmin"
                    and current["expire_date"]
                    and str(current["expire_date"]) < date.today().isoformat()
                )
                if not current["is_active"] or expired:
                    logged_in_user.set(None)
                    ui.modal_remove()
                    return
                logged_in_user.set(dict(current))

            create_message.set(t("users_updated"))
            edit_modal_message.set("")
            users_refresh.set(users_refresh() + 1)
            ui.modal_remove()
            editing_user_id.set(None)
        except PermissionError:
            edit_modal_message.set(t("users_denied_edit"))
        except sqlite3.IntegrityError:
            edit_modal_message.set(t("users_exists"))
        except ValueError as exc:
            edit_modal_message.set(str(exc))

    @reactive.effect
    @reactive.event(input.delete_user)
    def _delete_user_event():
        # Delete from inside the edit modal.
        current = _ensure_valid_session()
        if not current:
            return
        selected_id = editing_user_id()
        if selected_id is None:
            return
        try:
            with user_context(current):
                delete_user(int(selected_id))
            create_message.set(t("users_deleted"))
            users_refresh.set(users_refresh() + 1)
            editing_user_id.set(None)
            ui.modal_remove()
        except PermissionError:
            edit_modal_message.set(t("users_denied_delete"))
        except ValueError as exc:
            edit_modal_message.set(str(exc))

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
            ui.tags.th(t("users_col_role")),
            ui.tags.th(t("users_col_active")),
            ui.tags.th(t("users_col_expires")),
            ui.tags.th(t("users_col_created")),
        )
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
                    ui.tags.td(role_label(row["role"])),
                    ui.tags.td(t("yes") if row["is_active"] else t("no")),
                    ui.tags.td(row["expire_date"] or t("never")),
                    ui.tags.td(row["created_at"]),
                )
            )
        return ui.tags.table(header, *body, class_="users-table")




app = App(app_ui, server, static_assets=STATIC_DIR)
