"""Authenticated user account page."""

from shiny import ui

# Unique identifier used to map sidebar navigation to this module.
NAV_ID = "tab_account"
# Human-readable label displayed in the sidebar.
NAV_LABEL = "My Account"
# Icon shown for this top-level sidebar item.
NAV_ICON = "bi-person-gear"
# None means this item is displayed outside a collapsible group.
NAV_GROUP = None
# Every authenticated role can access this page.
NAV_MIN_ROLE = "guest"


def panel():
    """Return the authenticated user's account and password interface."""
    # The server-side handler verifies the current password before changing it.
    return ui.div(
        ui.h3("My Account"),
        ui.p("Change your own password. This is available to every authenticated user."),
        ui.div(
            ui.h4("Change password"),
            ui.input_password("current_password", "Current password"),
            ui.input_password("new_own_password", "New password"),
            ui.input_password("new_own_password_confirm", "Confirm new password"),
            ui.input_action_button(
                "change_password_button",
                "Change password",
                class_="btn btn-primary",
            ),
            ui.output_ui("account_message_ui"),
            class_="user-form-card",
        ),
        class_="tab-pane-content",
    )
