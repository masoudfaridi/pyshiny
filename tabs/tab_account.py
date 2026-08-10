"""Self-service account page (change own password)."""

from shiny import ui

NAV_ID = "tab_account"
NAV_LABEL = "My Account"
NAV_ICON = "bi-person-circle"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"


def panel():
    """Change-password form laid out with Bootstrap columns."""
    return ui.div(
        ui.h3("My Account"),
        ui.p("Change your own password. This is available to every authenticated user."),
        ui.row(
            ui.column(
                6,
                ui.div(
                    ui.h4("Change password"),
                    ui.input_password("current_password", "Current password"),
                    ui.input_password("new_own_password", "New password"),
                    ui.input_password("new_own_password_confirm", "Confirm new password"),
                    ui.input_action_button(
                        "change_password_button",
                        "Change password",
                        class_="btn btn-primary mt-2",
                    ),
                    ui.output_ui("account_message_ui"),
                    class_="user-form-card",
                ),
            ),
            ui.column(
                6,
                ui.div(
                    ui.h5("Password tips"),
                    ui.tags.ul(
                        ui.tags.li("Use at least 8 characters."),
                        ui.tags.li("Mix letters, numbers, and symbols."),
                        ui.tags.li("Avoid reusing passwords from other sites."),
                    ),
                    class_="user-form-card",
                ),
            ),
        ),
        class_="tab-pane-content",
    )
