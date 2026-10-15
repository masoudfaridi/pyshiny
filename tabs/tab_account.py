"""Self-service account page (change own password)."""

from shiny import ui

from i18n import t

NAV_ID = "tab_account"
NAV_LABEL = t("nav_account")
NAV_ICON = "bi-person-circle"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"


def panel():
    """Change-password form laid out with Bootstrap columns."""
    return ui.div(
        ui.h3(t("account_title")),
        ui.p(t("account_intro")),
        ui.row(
            ui.column(
                6,
                ui.div(
                    ui.h4(t("account_change_heading")),
                    ui.input_password("current_password", t("account_current_password")),
                    ui.input_password("new_own_password", t("account_new_password")),
                    ui.input_password("new_own_password_confirm", t("confirm_new_password")),
                    ui.input_action_button(
                        "change_password_button",
                        t("account_change_button"),
                        class_="btn btn-primary mt-2",
                    ),
                    ui.output_ui("account_message_ui"),
                    class_="user-form-card",
                ),
            ),
            ui.column(
                6,
                ui.div(
                    ui.h5(t("account_tips_heading")),
                    ui.tags.ul(
                        ui.tags.li(t("account_tip_length")),
                        ui.tags.li(t("account_tip_mix")),
                        ui.tags.li(t("account_tip_reuse")),
                    ),
                    class_="user-form-card",
                ),
            ),
        ),
        class_="tab-pane-content",
    )
