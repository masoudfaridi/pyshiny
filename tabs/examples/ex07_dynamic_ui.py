"""
Example 07 -- Dynamic UI (render.ui)

Concepts
--------
* ``@render.ui`` can return DIFFERENT inputs depending on another input.
* Ids created inside the module server are namespaced automatically, exactly
  like the ones in ``@module.ui``.
* Reading an input that has not been drawn yet silently stops the output, so
  ``chosen`` stays blank for a moment after switching type. That is normal.
"""

from __future__ import annotations

from shiny import module, render, ui

NAV_ID = "tab_ex07"
NAV_LABEL = "Ex 07 Dynamic UI"
NAV_ICON = "bi-magic"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"

MODULE_ID = "tab_ex07"

KINDS = {"text": "Text", "number": "Number", "date": "Date", "choice": "Choice"}


@module.ui
def _ui():
    return ui.div(
        ui.h3("Dynamic input"),
        ui.div(
            ui.input_select("kind", "What do you want to enter?", KINDS),
            ui.output_ui("value_input"),
            ui.h5("You entered", class_="mt-3"),
            ui.output_text("chosen"),
            class_="user-form-card",
        ),
        class_="tab-pane-content",
    )


@module.server
def _server(input, output, session):
    @render.ui
    def value_input():
        kind = input.kind()
        if kind == "number":
            return ui.input_numeric("entry", "Number", value=10, min=0, max=100)
        if kind == "date":
            return ui.input_date("entry", "Date")
        if kind == "choice":
            return ui.input_radio_buttons("entry", "Pick one", ["Small", "Medium", "Large"])
        return ui.input_text("entry", "Text", placeholder="Type something")

    @render.text
    def chosen():
        return f"{input.kind()}: {input.entry()}"


def panel():
    return _ui(MODULE_ID)


def server():
    _server(MODULE_ID)
