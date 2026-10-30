"""Superadmin-only user management page."""

from shiny import ui

from i18n import role_label, t
from tabs._forms import file_input, password_input, text_input

# Unique identifier used to map sidebar navigation to this module.
NAV_ID = "tab_users"
# Human-readable label displayed in the sidebar.
NAV_LABEL = t("nav_users")
# Icon shown for this top-level sidebar item.
NAV_ICON = "bi-people"
# None means this item is displayed outside a collapsible group.
NAV_GROUP = None
# Only Superadmin users can see this page.
NAV_MIN_ROLE = "superadmin"


def _roles() -> dict:
    return {r: role_label(r) for r in ("guest", "user", "admin", "superadmin")}


def create_user_form(values: dict | None = None):
    """Fields of the "create user" popup (two columns on wide screens).

    ``values`` pre-fills the text fields and the role after a failed save, so
    nothing typed is lost (passwords are never sent back to the browser).
    """
    values = values or {}
    return ui.div(
        ui.div(
            text_input("new_username", t("username"), values.get("username", "")),
            text_input("new_id_code", t("id_code"), values.get("id_code", ""), ltr=True),
            text_input("new_email", t("email"), values.get("email", ""), ltr=True),
            text_input("new_phone", t("phone"), values.get("phone", ""), ltr=True),
            password_input("new_password", t("password")),
            password_input("new_password_confirm", t("confirm_password")),
            ui.input_select(
                "new_role", t("access_level"), _roles(),
                selected=values.get("role", "guest"), width="100%",
            ),
            ui.div(ui.output_ui("create_expiry_field"), class_="form-grid-cell"),
            class_="form-grid",
        ),
        ui.output_ui("create_modal_message_ui"),
        class_="user-create-form",
    )


def create_user_modal(values: dict | None = None):
    """The popup opened by the "New user" button (see app.py)."""
    return ui.modal(
        create_user_form(values),
        title=t("users_create_heading"),
        easy_close=False,
        size="l",
        footer=ui.div(
            ui.input_action_button(
                "create_user", t("users_create_button"), class_="btn btn-primary"
            ),
            ui.modal_button(t("edit_cancel"), class_="btn btn-secondary"),
            class_="d-flex gap-2",
        ),
    )


def panel():
    """Return the user management interface."""
    # Create = popup (button below); edit/delete = Change buttons in the table.
    return ui.div(
        ui.div(
            ui.div(
                ui.h3(t("users_title"), class_="mb-1"),
                ui.p(t("users_intro"), class_="text-muted mb-0"),
            ),
            ui.input_action_button(
                "create_user_open",
                ui.tags.span(ui.tags.i(class_="bi bi-person-plus"), " " + t("users_new_button")),
                class_="btn btn-primary",
            ),
            class_="page-header-row",
        ),
        ui.output_ui("user_create_message"),
        ui.p(t("users_existing_hint"), class_="text-muted small mt-3"),
        ui.div(ui.output_ui("users_table"), class_="table-scroll"),
        # ---- accounts database backup / restore (all actions password-protected) ----
        ui.h4(t("backup_title"), class_="mt-4"),
        ui.p(t("backup_intro"), class_="text-muted small"),
        ui.div(
            ui.div(
                ui.input_action_button(
                    "backup_create", t("backup_create"), class_="btn btn-primary"
                ),
                ui.div(
                    file_input(
                        "backup_upload",
                        t("backup_upload_label"),
                        accept=[".db", ".sqlite", ".sqlite3"],
                        multiple=False,
                        button_label=t("file_browse"),
                        placeholder=t("file_none"),
                        width="100%",
                    ),
                    class_="backup-file",
                ),
                ui.input_action_button(
                    "backup_import", t("backup_import"), class_="btn btn-secondary"
                ),
                class_="backup-toolbar",
            ),
            class_="user-form-card wide",
        ),
        ui.div(ui.output_ui("backups_table"), class_="table-scroll mt-3"),
        class_="tab-pane-content",
    )
