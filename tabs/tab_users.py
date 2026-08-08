"""Superadmin-only user management page."""

from shiny import ui

# Unique identifier used to map sidebar navigation to this module.
NAV_ID = "tab_users"
# Human-readable label displayed in the sidebar.
NAV_LABEL = "User Management"
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
        ui.h3("User Management"),
        ui.p("Only Superadmin users can create, edit, and delete accounts."),
        ui.div(
            ui.h4("Create user"),
            ui.input_text("new_username", "Username"),
            ui.input_password("new_password", "Password"),
            ui.input_password("new_password_confirm", "Confirm password"),
            ui.input_select(
                "new_role",
                "Access level",
                {
                    "guest": "Guest",
                    "user": "User",
                    "admin": "Admin",
                    "superadmin": "Superadmin",
                },
            ),
            ui.output_ui("create_expiry_field"),
            ui.input_action_button(
                "create_user", "Create user", class_="btn btn-primary"
            ),
            ui.output_ui("user_create_message"),
            class_="user-form-card",
        ),
        ui.h4("Existing users", class_="mt-4"),
        ui.p(
            "Use Change to edit an account in a popup, or Delete to remove it.",
            class_="text-muted small",
        ),
        ui.output_ui("users_table"),
        class_="tab-pane-content",
    )
