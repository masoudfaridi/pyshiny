"""
Example 08 -- Dependent dropdowns (ui.update_select)

Concepts
--------
* ``ui.update_select`` changes an existing input from the server, so the user
  keeps their place instead of the whole control being redrawn.
* Inside a module, ``ui.update_select("item", ...)`` automatically targets
  ``tab_ex08-item`` -- no manual prefix.
* Other update helpers follow the same pattern: ``update_slider``,
  ``update_text``, ``update_numeric``, ``update_checkbox`` ...
"""

from __future__ import annotations

from shiny import module, reactive, render, ui

NAV_ID = "tab_ex08"
NAV_LABEL = "Ex 08 Update inputs"
NAV_ICON = "bi-arrow-repeat"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"

MODULE_ID = "tab_ex08"

CATALOG = {
    "Fruit": ["Apple", "Banana", "Cherry"],
    "Vegetable": ["Carrot", "Leek", "Spinach", "Turnip"],
    "Dairy": ["Butter", "Cheese", "Yoghurt"],
}
FIRST_GROUP = next(iter(CATALOG))


@module.ui
def _ui():
    return ui.div(
        ui.h3("Dependent dropdowns"),
        ui.div(
            ui.input_select("group", "Group", list(CATALOG), selected=FIRST_GROUP),
            ui.input_select("item", "Item", CATALOG[FIRST_GROUP]),
            ui.h5("Selection", class_="mt-3"),
            ui.output_text("selection"),
            class_="user-form-card",
        ),
        class_="tab-pane-content",
    )


@module.server
def _server(input, output, session):
    @reactive.effect
    @reactive.event(input.group)
    def _sync_items():
        ui.update_select("item", choices=CATALOG[input.group()])

    @render.text
    def selection():
        return f"{input.group()} / {input.item()}"


def panel():
    return _ui(MODULE_ID)


def server():
    _server(MODULE_ID)
