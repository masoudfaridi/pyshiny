"""Superadmin-only user management page."""

from shiny import ui

from i18n import role_label, t

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


def panel():
    """Return the user management interface."""
    # Edit/delete happens via Change buttons in the table and a modal dialog.
    return ui.div(
        ui.h3(t("users_title")),
        ui.p(t("users_intro")),
        ui.div(
            ui.h4(t("users_create_heading")),
            ui.input_text("new_username", t("username")),
            ui.input_text("new_id_code", t("id_code")),
            ui.input_text("new_email", t("email")),
            ui.input_text("new_phone", t("phone")),
            ui.input_password("new_password", t("password")),
            ui.input_password("new_password_confirm", t("confirm_password")),
            ui.input_select(
                "new_role",
                t("access_level"),
                {
                    "guest": role_label("guest"),
                    "user": role_label("user"),
                    "admin": role_label("admin"),
                    "superadmin": role_label("superadmin"),
                },
            ),
            ui.output_ui("create_expiry_field"),
            ui.input_action_button(
                "create_user", t("users_create_button"), class_="btn btn-primary"
            ),
            ui.output_ui("user_create_message"),
            class_="user-form-card",
        ),
        ui.h4(t("users_existing_heading"), class_="mt-4"),
        ui.p(
            t("users_existing_hint"),
            class_="text-muted small",
        ),
        ui.div(ui.output_ui("users_table"), class_="table-scroll"),
        # ---- accounts database backup / restore (all actions password-protected) ----
        ui.h4(t("backup_title"), class_="mt-4"),
        ui.p(t("backup_intro"), class_="text-muted small"),
        ui.div(
            ui.div(
                ui.input_action_button(
                    "backup_create", t("backup_create"), class_="btn btn-primary"
                ),
                class_="backup-toolbar",
            ),
            ui.div(
                ui.input_file(
                    "backup_upload",
                    t("backup_upload_label"),
                    accept=[".db", ".sqlite", ".sqlite3"],
                    multiple=False,
                ),
                ui.input_action_button(
                    "backup_import", t("backup_import"), class_="btn btn-secondary"
                ),
                class_="backup-toolbar",
            ),
            class_="user-form-card",
        ),
        ui.div(ui.output_ui("backups_table"), class_="table-scroll mt-3"),
        class_="tab-pane-content",
    )
