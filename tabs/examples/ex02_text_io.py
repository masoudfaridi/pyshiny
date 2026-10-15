"""
Example 02 -- Inputs and outputs

Concepts
--------
* Local ids: ``input.person()`` here is really ``tab_ex02-person`` in the browser.
* ``@render.text`` re-runs automatically whenever an input it reads changes.
* ``ui.output_text("greeting")`` (in the UI) is connected to
  ``def greeting()`` (in the server) by having the SAME local id.
"""

from __future__ import annotations

from shiny import module, render, ui

NAV_ID = "tab_ex02"
NAV_LABEL = "Ex 02 Text I/O"
NAV_ICON = "bi-input-cursor-text"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"

MODULE_ID = "tab_ex02"


@module.ui
def _ui():
    return ui.div(
        ui.h3("Inputs and outputs"),
        ui.row(
            ui.column(
                5,
                ui.div(
                    ui.input_text("person", "Your name", placeholder="Type a name"),
                    ui.input_text_area("note", "A short note", rows=3),
                    ui.input_checkbox("shout", "SHOUT", value=False),
                    class_="user-form-card",
                ),
            ),
            ui.column(
                7,
                ui.div(
                    ui.h5("Greeting"),
                    ui.output_text("greeting"),
                    ui.h5("Note length", class_="mt-3"),
                    ui.output_text("note_info"),
                    class_="user-form-card",
                ),
            ),
        ),
        class_="tab-pane-content",
    )


@module.server
def _server(input, output, session):
    @render.text
    def greeting():
        name = (input.person() or "").strip()
        if not name:
            return "Type your name on the left."
        text = f"Hello, {name}!"
        return text.upper() if input.shout() else text

    @render.text
    def note_info():
        note = input.note() or ""
        words = len(note.split())
        return f"{len(note)} characters, {words} words"


def panel():
    return _ui(MODULE_ID)


def server():
    _server(MODULE_ID)
