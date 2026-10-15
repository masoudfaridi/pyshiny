"""
Example 11 -- Notifications and a confirmation popup

Concepts
--------
* ``ui.notification_show`` -- a short toast message (types: "default",
  "message", "warning", "error").
* ``ui.modal_show`` / ``ui.modal_remove`` -- a popup. Buttons created inside
  the popup get namespaced ids like everything else in the module, so
  ``input.confirm`` just works.
* This is the same technique app.py uses for the "Edit user" popup.
"""

from __future__ import annotations

from shiny import module, reactive, render, ui

NAV_ID = "tab_ex11"
NAV_LABEL = "Ex 11 Notify / Modal"
NAV_ICON = "bi-bell"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"

MODULE_ID = "tab_ex11"


@module.ui
def _ui():
    return ui.div(
        ui.h3("Notifications and popups"),
        ui.div(
            ui.input_action_button("save", "Save (toast)", class_="btn btn-primary"),
            " ",
            ui.input_action_button("delete", "Delete... (asks first)", class_="btn btn-danger"),
            ui.h5("Last action", class_="mt-3"),
            ui.output_text("status"),
            class_="user-form-card",
        ),
        class_="tab-pane-content",
    )


@module.server
def _server(input, output, session):
    status_text = reactive.Value("Nothing yet.")

    @reactive.effect
    @reactive.event(input.save)
    def _save():
        ui.notification_show("Saved successfully.", type="message", duration=3)
        status_text.set("Saved.")

    @reactive.effect
    @reactive.event(input.delete)
    def _ask():
        ui.modal_show(
            ui.modal(
                "This cannot be undone. Do you want to continue?",
                title="Please confirm",
                easy_close=True,
                footer=ui.TagList(
                    ui.input_action_button("confirm", "Yes, delete", class_="btn btn-danger"),
                    ui.modal_button("Cancel"),
                ),
            )
        )

    @reactive.effect
    @reactive.event(input.confirm)
    def _confirmed():
        ui.modal_remove()
        ui.notification_show("Item deleted.", type="warning", duration=4)
        status_text.set("Deleted.")

    @render.text
    def status():
        return status_text()


def panel():
    return _ui(MODULE_ID)


def server():
    _server(MODULE_ID)
