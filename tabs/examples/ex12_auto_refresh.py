"""
Example 12 -- Auto-refreshing content (reactive.invalidate_later)

Concepts
--------
* ``reactive.invalidate_later(seconds)`` asks Shiny to run the current effect
  again after a delay -- a simple "live" tab without JavaScript.
* ``reactive.isolate()`` reads a value WITHOUT making the effect depend on it
  (otherwise updating the counter would re-trigger the effect immediately).
* Keep intervals long enough (a few seconds): every refresh is a server round
  trip for every open browser session.
"""

from __future__ import annotations

from datetime import datetime

from shiny import module, reactive, render, ui

NAV_ID = "tab_ex12"
NAV_LABEL = "Ex 12 Live"
NAV_ICON = "bi-broadcast"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"

MODULE_ID = "tab_ex12"


@module.ui
def _ui():
    return ui.div(
        ui.h3("Live updates"),
        ui.div(
            ui.input_switch("live", "Live updates", value=False),
            ui.input_slider("interval", "Interval (seconds)", min=1, max=10, value=2),
            ui.h5("Updates received", class_="mt-3"),
            ui.output_text("ticks_text"),
            ui.h5("Last update", class_="mt-3"),
            ui.output_text("last_text"),
            class_="user-form-card",
        ),
        class_="tab-pane-content",
    )


@module.server
def _server(input, output, session):
    ticks = reactive.Value(0)
    last = reactive.Value("-")

    @reactive.effect
    def _tick():
        if not input.live():
            return
        reactive.invalidate_later(input.interval())  # run this effect again later
        with reactive.isolate():  # read without creating a dependency
            ticks.set(ticks() + 1)
        last.set(datetime.now().strftime("%H:%M:%S"))

    @render.text
    def ticks_text():
        return str(ticks())

    @render.text
    def last_text():
        return last()


def panel():
    return _ui(MODULE_ID)


def server():
    _server(MODULE_ID)
