"""Self-service account page (change own password)."""

from shiny import ui

from auth import current_user
from i18n import role_label, t
from tabs._forms import password_input, with_input_attrs

NAV_ID = "tab_account"
NAV_LABEL = t("nav_account")
NAV_ICON = "bi-person-circle"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"


def _profile_card():
    """Own details: e-mail / phone editable, identification code read-only.

    ``panel()`` runs inside ``user_context`` (see app.py ``active_panel``), so
    ``current_user()`` is the re-validated session user with its stored values.
    """
    person = current_user() or {}
    return ui.div(
        ui.h4(t("account_profile_heading")),
        ui.p(t("account_profile_intro"), class_="text-muted small"),
        ui.tags.dl(
            ui.tags.dt(t("username")),
            ui.tags.dd(person.get("username") or ""),
            ui.tags.dt(t("access_level")),
            ui.tags.dd(role_label(person.get("role") or "guest")),
            ui.tags.dt(t("id_code")),
            ui.tags.dd(person.get("id_code") or t("account_not_set")),
            class_="profile-details",
        ),
        ui.p(t("account_id_code_note"), class_="form-text text-muted"),
        ui.input_text("profile_email", t("email"), value=person.get("email") or ""),
        ui.input_text("profile_phone", t("phone"), value=person.get("phone") or ""),
        ui.input_action_button(
            "profile_save_button", t("account_profile_save"), class_="btn btn-primary mt-2"
        ),
        ui.output_ui("profile_message_ui"),
        class_="user-form-card mb-3",
    )


def panel():
    """Own details + change-password form laid out with Bootstrap columns."""
    return ui.div(
        ui.h3(t("account_title")),
        ui.p(t("account_intro")),
        ui.row(
            ui.column(6, _profile_card()),
        ),
        ui.row(
            ui.column(
                6,
                ui.div(
                    ui.h4(t("account_change_heading")),
                    with_input_attrs(
                        ui.input_password("current_password", t("account_current_password")),
                        autocomplete="current-password",
                    ),
                    password_input("new_own_password", t("account_new_password")),
                    password_input("new_own_password_confirm", t("confirm_new_password")),
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
