"""
Example 14 -- A module that knows who is logged in (RBAC inside a module)

Concepts
--------
* Hiding a sidebar link (NAV_MIN_ROLE) is not security. Server-side code must
  be protected too: the ``@admin`` decorator from the ``auth`` package raises
  ``PermissionError`` unless the current user is Admin or Superadmin.
* Module servers start once when the page opens -- before anyone logs in --
  so they cannot use ``current_user()`` directly. Instead app.py PASSES the
  session's user (a ``reactive.Value``) into the module as an argument.

!! This example needs ONE extra change in app.py: pass the user in:

        tab_ex14.server(logged_in_user)      # instead of tab_ex14.server()

   (``logged_in_user`` is the reactive.Value defined at the top of app.py's
   ``server()`` function.)
"""

from __future__ import annotations

from shiny import module, reactive, render, ui

from auth import admin, user_context
from i18n import role_label

NAV_ID = "tab_ex14"
NAV_LABEL = "Ex 14 Role-aware"
NAV_ICON = "bi-shield-check"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"  # visible to everyone on purpose: the SERVER decides

MODULE_ID = "tab_ex14"


@admin
def _export_report() -> str:
    """Only Admin and Superadmin may run this; others get PermissionError."""
    return "Report exported."


@module.ui
def _ui():
    return ui.div(
        ui.h3("Role-aware actions"),
        ui.div(
            ui.p("Your role:", ui.output_text("who", inline=True)),
            ui.input_action_button("export", "Export report (Admin+)", class_="btn btn-primary"),
            ui.output_ui("message"),
            class_="user-form-card",
        ),
        class_="tab-pane-content",
    )


@module.server
def _server(input, output, session, session_user):
    """``session_user`` is the reactive.Value passed in by app.py."""
    status = reactive.Value("")

    @render.text
    def who():
        person = session_user()
        return f" {role_label(person['role'])}" if person else " -"

    @reactive.effect
    @reactive.event(input.export)
    def _export():
        person = session_user()
        if person is None:
            status.set("Please sign in again.")
            return
        try:
            with user_context(person):  # makes the decorator see this user
                status.set(_export_report())
        except PermissionError:
            status.set("Access denied: Admin role required.")

    @render.ui
    def message():
        text = status()
        return ui.div(text, class_="user-create-message mt-3") if text else ui.div()


def panel():
    return _ui(MODULE_ID)


def server(session_user):
    _server(MODULE_ID, session_user=session_user)
