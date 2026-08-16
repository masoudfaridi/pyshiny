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

from datetime import date
from pathlib import Path

from shiny import App, reactive, render, ui
import sqlite3

from auth import (
    authenticate,
    change_own_password,
    clear_login_failures,
    create_user,
    current_role,
    current_user,
    delete_user,
    generate_captcha,
    is_login_locked,
    list_users,
    refresh_session_user,
    register_login_failure,
    update_user,
    user_context,
    verify_captcha,
)

from tabs import tab_01, tab_02, tab_03, tab_04, tab_05, tab_06, tab_account, tab_users

APP_DIR = Path(__file__).parent
STATIC_DIR = APP_DIR / "static"

# Order here = order shown in the sidebar, top to bottom.
TABS = [tab_01, tab_02, tab_03, tab_04, tab_05, tab_06, tab_account, tab_users]
TAB_LOOKUP = {tab.NAV_ID: tab for tab in TABS}
DEFAULT_TAB_ID = "tab_04"  # guest-accessible default so lower roles land on a valid page

# A "group" is not a tab by itself -- it's just a collapsible header in the
# sidebar for every tab whose NAV_GROUP matches its key.
GROUPS = {
    "dashboard": {"label": "Dashboard", "icon": "bi-speedometer2"},
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
                ui.h2("Secure Dashboard"),
                ui.p("Please sign in to continue.", class_="login-subtitle"),
                ui.input_text("login_username", "Username", placeholder="Username"),
                ui.input_password("login_password", "Password", placeholder="Password"),
                ui.div(
                    ui.tags.label("Security check", class_="form-label"),
                    ui.output_ui("login_captcha_ui"),
                    ui.input_text(
                        "login_captcha",
                        None,
                        placeholder="Type the characters you see",
                    ),
                    class_="login-captcha-block",
                ),
                ui.input_action_button("login_button", "Sign in", class_="btn btn-primary w-100"),
                ui.output_ui("login_message"),
                ui.p(
                    "Default accounts are documented in README.md. "
                    "Change default passwords after first login.",
                    class_="login-hint",
                ),
                class_="login-card",
            ),
            class_="login-page",
        )
    )


def dashboard_ui(role: str) -> ui.Tag:
    return ui.div(
        ui.tags.header(
            ui.tags.div(
                ui.tags.i(class_="bi bi-hexagon-fill"),
                ui.tags.span("Python Shiny Dashboard", class_="brand-text"),
                class_="brand",
            ),
            ui.tags.div(
                ui.tags.i(class_="bi bi-hexagon-fill"),
                ui.tags.a(
                    ui.tags.span("github: https://github.com/masoudfaridi/pyshiny", class_="brand-text"),
                    href="https://github.com/masoudfaridi/pyshiny",
                    target="_blank",
                ),
                class_="brand",
            ),
            ui.tags.div(
                ui.tags.span(f"{current_role().title()}", class_="role-badge"),
                ui.tags.span(current_user()["username"], class_="username-badge"),
                ui.input_action_button(
                    "logout_button",
                    ui.tags.span(
                        ui.tags.i(class_="bi bi-box-arrow-right"),
                        " Logout",
                    ),
                    class_="logout-button",
                ),
                ui.tags.div(
                    ui.tags.button(
                        ui.tags.span("", id="theme-current-swatch", class_="theme-swatch"),
                        ui.tags.span("Ocean Blue", id="theme-current-label"),
                        ui.tags.i(class_="bi bi-chevron-down"),
                        class_="theme-button", type="button", aria_label="Choose theme",
                    ),
                    ui.tags.div(
                        ui.tags.div("Light themes", class_="theme-section-title"),
                        ui.tags.div(class_="theme-options-light"),
                        ui.tags.div("Dark themes", class_="theme-section-title"),
                        ui.tags.div(class_="theme-options-dark"),
                        class_="theme-menu",
                    ), class_="theme-picker",
                ),
            ), class_="topbar",
        ),
        ui.layout_sidebar(
            ui.sidebar(build_sidebar(role), width="260px", open="desktop", title=None),
            ui.output_ui("active_panel"), class_="app-body",
        ), class_="app-shell",
    )


def build_app_shell() -> ui.Tag:
    return ui.div(ui.output_ui("root_ui"), id="root-container")


# =============================================================================
# DIRECTION / LAYOUT MODE  (LTR ↔ RTL)
# =============================================================================
# The dashboard ships in LTR (left-to-right) by default.
#
# To switch to RTL (right-to-left, suitable for Persian / Arabic):
#   1. Comment out the entire "LTR mode" block below.
#   2. Uncomment the entire "RTL mode" block below.
#
# Only ONE of the two blocks must be active at a time.
# Both blocks load the shared styles.css + custom.js; the difference is
# which Bootstrap CSS is used and whether html[dir="rtl"] is set.
# Bootstrap files live in static/css/ (bootstrap.css / bootstrap.rtl.css).
# =============================================================================

# --- LTR mode (default, ACTIVE) ---
app_ui = ui.page_fillable(
    # Override Shiny's default Bootstrap with the local LTR build
    ui.tags.link(rel="stylesheet", href="css/bootstrap.css"),
    ui.tags.style(read_asset("css", "styles.css")),
    ui.tags.script(read_asset("js", "custom.js")),
    # Ensure document direction is left-to-right
    ui.tags.script("document.documentElement.setAttribute('dir','ltr');"),
    build_app_shell(),
    class_="app-shell-root",
)

# --- RTL mode (INACTIVE – uncomment this block and comment the LTR block above) ---
# app_ui = ui.page_fillable(
#     # Use Bootstrap RTL so components, grids, and utilities flip correctly
#     ui.tags.link(rel="stylesheet", href="css/bootstrap.rtl.css"),
#     ui.tags.style(read_asset("css", "styles.css")),
#     ui.tags.script(read_asset("js", "custom.js")),
#     # Force document direction to right-to-left (Persian / Arabic)
#     ui.tags.script("document.documentElement.setAttribute('dir','rtl');"),
#     build_app_shell(),
#     class_="app-shell-root",
# )


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
                logged_in_user.set(None)
            return None
        if (
            fresh["username"] != user.get("username")
            or fresh["role"] != user.get("role")
            or int(fresh["is_active"]) != int(user.get("is_active") or 0)
            or fresh.get("expire_date") != user.get("expire_date")
        ):
            logged_in_user.set(dict(fresh))
        return fresh

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
                alt="CAPTCHA",
                class_="login-captcha-image",
            ),
            ui.tags.button(
                ui.tags.i(class_="bi bi-arrow-clockwise"),
                " Refresh",
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
            login_error.set("Invalid username or password, inactive account, or expired account.")
            _issue_captcha()
            return

        locked, remaining = is_login_locked(username)
        if locked:
            login_error.set(
                f"Too many failed attempts. Try again in {remaining} seconds."
            )
            _issue_captcha()
            return

        if not verify_captcha(captcha_answer, captcha_hash(), captcha_expires()):
            register_login_failure(username)
            login_error.set("Invalid security check. Please try again.")
            _issue_captcha()
            return

        # Single-use CAPTCHA: invalidate after the first verification attempt.
        captcha_hash.set(None)
        captcha_expires.set(None)

        user = authenticate(username, password)
        if user is None:
            register_login_failure(username)
            login_error.set(
                "Invalid username or password, inactive account, or expired account."
            )
            _issue_captcha()
            return

        clear_login_failures(username)
        login_error.set("")
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
    @reactive.event(input.change_password_button)
    def _change_password_event():
        # Change the password for the currently authenticated account.
        current = _ensure_valid_session()
        if not current:
            return

        new_password = input.new_own_password()
        confirm_password = input.new_own_password_confirm()
        if new_password != confirm_password:
            account_message.set("New password and confirmation do not match.")
            return

        try:
            with user_context(current):
                change_own_password(
                    input.current_password(),
                    new_password,
                )
            account_message.set("Password changed successfully.")
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
            create_message.set("Password and confirmation do not match.")
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
            create_message.set("User created successfully.")
            users_refresh.set(users_refresh() + 1)
        except PermissionError:
            create_message.set("Access denied: only Superadmin can create users.")
        except sqlite3.IntegrityError:
            create_message.set("This username already exists.")
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
                "Superadmin accounts do not expire.",
                class_="form-text text-muted",
            )

        return ui.div(
            ui.input_checkbox(
                "new_expire_enabled",
                "Set an expiration date",
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
            "Expiration date",
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
                    "Username",
                    value=selected["username"],
                ),
                ui.input_select(
                    "edit_role",
                    "Access level",
                    {
                        "guest": "Guest",
                        "user": "User",
                        "admin": "Admin",
                        "superadmin": "Superadmin",
                    },
                    selected=selected["role"],
                ),
                ui.output_ui("edit_expiry_field"),
                ui.input_checkbox(
                    "edit_is_active",
                    "Active account",
                    value=bool(selected["is_active"]),
                ),
                ui.input_password(
                    "edit_password",
                    "New password (leave blank to keep current password)",
                ),
                ui.input_password(
                    "edit_password_confirm",
                    "Confirm new password",
                ),
                ui.output_ui("edit_modal_message_ui"),
                class_="user-edit-modal-body",
            ),
            title=f'Edit user: {selected["username"]}',
            easy_close=True,
            footer=ui.div(
                ui.input_action_button(
                    "save_user", "Save changes", class_="btn btn-primary"
                ),
                ui.input_action_button(
                    "delete_user", "Delete user", class_="btn btn-danger ms-2"
                ),
                ui.modal_button("Cancel", class_="btn btn-secondary ms-2"),
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
                "Superadmin accounts do not expire.",
                class_="form-text text-muted",
            )

        has_expiry = bool(selected and selected.get("expire_date"))
        return ui.div(
            ui.input_checkbox(
                "edit_expire_enabled",
                "Set an expiration date",
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
            "Expiration date",
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
            create_message.set("User not found.")
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
            create_message.set("User deleted successfully.")
            users_refresh.set(users_refresh() + 1)
            editing_user_id.set(None)
            ui.modal_remove()
        except PermissionError:
            create_message.set("Access denied: only Superadmin can delete users.")
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
            edit_modal_message.set("New password and confirmation do not match.")
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

            create_message.set("User updated successfully.")
            edit_modal_message.set("")
            users_refresh.set(users_refresh() + 1)
            ui.modal_remove()
            editing_user_id.set(None)
        except PermissionError:
            edit_modal_message.set("Access denied: only Superadmin can edit users.")
        except sqlite3.IntegrityError:
            edit_modal_message.set("This username already exists.")
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
            create_message.set("User deleted successfully.")
            users_refresh.set(users_refresh() + 1)
            editing_user_id.set(None)
            ui.modal_remove()
        except PermissionError:
            edit_modal_message.set("Access denied: only Superadmin can delete users.")
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
            ui.tags.th("Actions"),
            ui.tags.th("ID"),
            ui.tags.th("Username"),
            ui.tags.th("Role"),
            ui.tags.th("Active"),
            ui.tags.th("Expires"),
            ui.tags.th("Created"),
        )
        body = []
        for row in rows:
            actions = ui.tags.td(
                ui.tags.button(
                    "Change",
                    type="button",
                    class_="btn btn-sm btn-primary user-action-edit",
                    data_user_id=str(row["id"]),
                ),
                " ",
                ui.tags.button(
                    "Delete",
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
                    ui.tags.td(row["role"]),
                    ui.tags.td("Yes" if row["is_active"] else "No"),
                    ui.tags.td(row["expire_date"] or "Never"),
                    ui.tags.td(row["created_at"]),
                )
            )
        return ui.tags.table(header, *body, class_="users-table")




app = App(app_ui, server, static_assets=STATIC_DIR)
