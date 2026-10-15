"""
Example 03 -- Buttons and state (reactive.Value)

Concepts
--------
* ``reactive.Value`` stores state that lives as long as the browser session.
* ``@reactive.effect`` + ``@reactive.event(input.button)`` runs code ONLY when
  that button is clicked (not when other inputs change).
* Each browser session has its own counter: two users never share it.
"""

from __future__ import annotations

from shiny import module, reactive, render, ui

NAV_ID = "tab_ex03"
NAV_LABEL = "Ex 03 Counter"
NAV_ICON = "bi-plus-slash-minus"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"

MODULE_ID = "tab_ex03"


@module.ui
def _ui():
    return ui.div(
        ui.h3("Counter"),
        ui.div(
            ui.input_numeric("step", "Step", value=1, min=1, max=100),
            ui.div(
                ui.input_action_button("dec", "- Step", class_="btn btn-outline-secondary"),
                " ",
                ui.input_action_button("inc", "+ Step", class_="btn btn-primary"),
                " ",
                ui.input_action_button("reset", "Reset", class_="btn btn-outline-danger"),
            ),
            ui.h2(ui.output_text("value"), class_="mt-3"),
            class_="user-form-card",
        ),
        class_="tab-pane-content",
    )


@module.server
def _server(input, output, session):
    count = reactive.Value(0)

    def _step() -> int:
        try:
            return max(1, int(input.step() or 1))
        except (TypeError, ValueError):
            return 1

    @reactive.effect
    @reactive.event(input.inc)
    def _inc():
        count.set(count() + _step())

    @reactive.effect
    @reactive.event(input.dec)
    def _dec():
        count.set(count() - _step())

    @reactive.effect
    @reactive.event(input.reset)
    def _reset():
        count.set(0)

    @render.text
    def value():
        return str(count())


def panel():
    return _ui(MODULE_ID)


def server():
    _server(MODULE_ID)
