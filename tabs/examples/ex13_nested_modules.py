"""
Example 13 -- One module used many times (nested / reusable modules)

Concepts
--------
* THIS is why modules exist: write ``_counter_ui`` / ``_counter_server`` once,
  then use them as often as you like. Each copy has its own ids
  (``tab_ex13-a-inc``, ``tab_ex13-b-inc`` ...) and its own state.
* A module can call another module: ``_ui`` calls ``_counter_ui("a", ...)``.
  Ids are nested: tab id -> sub-module id -> local id.
* A module server can RETURN something (here a reactive value); the parent
  uses it to compute a total.
* Extra arguments are allowed: ``_counter_server("b", step=5)``.
"""

from __future__ import annotations

from shiny import module, reactive, render, ui

NAV_ID = "tab_ex13"
NAV_LABEL = "Ex 13 Nested modules"
NAV_ICON = "bi-diagram-3"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"

MODULE_ID = "tab_ex13"


# ---- The reusable piece: a counter card ------------------------------------
@module.ui
def _counter_ui(title: str):
    return ui.div(
        ui.h5(title),
        ui.h2(ui.output_text("value")),
        ui.input_action_button("inc", "Add", class_="btn btn-primary"),
        class_="user-form-card",
    )


@module.server
def _counter_server(input, output, session, step: int = 1):
    count = reactive.Value(0)

    @reactive.effect
    @reactive.event(input.inc)
    def _inc():
        count.set(count() + step)

    @render.text
    def value():
        return str(count())

    return count  # hand the reactive value back to the parent


# ---- The tab that uses it three times --------------------------------------
@module.ui
def _ui():
    return ui.div(
        ui.h3("Reusable counters"),
        ui.p("Same module, three independent copies. The last one adds 5 per click."),
        ui.row(
            ui.column(4, _counter_ui("a", "Apples (+1)")),
            ui.column(4, _counter_ui("b", "Oranges (+1)")),
            ui.column(4, _counter_ui("c", "Boxes (+5)")),
        ),
        ui.div(ui.h5("Total"), ui.output_text("total"), class_="user-form-card mt-3"),
        class_="tab-pane-content",
    )


@module.server
def _server(input, output, session):
    a = _counter_server("a", step=1)
    b = _counter_server("b", step=1)
    c = _counter_server("c", step=5)

    @render.text
    def total():
        return str(a() + b() + c())


def panel():
    return _ui(MODULE_ID)


def server():
    _server(MODULE_ID)
