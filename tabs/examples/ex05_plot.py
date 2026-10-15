"""
Example 05 -- A matplotlib plot

Concepts
--------
* ``ui.output_plot("wave")`` in the UI  <->  ``@render.plot def wave()`` in the
  server. Return a matplotlib Figure.
* Create the figure with ``plt.subplots`` inside the function (as tab_01 does)
  so every redraw starts clean.
"""

from __future__ import annotations

import numpy as np
from matplotlib import pyplot as plt
from shiny import module, render, ui

NAV_ID = "tab_ex05"
NAV_LABEL = "Ex 05 Plot"
NAV_ICON = "bi-graph-up"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"

MODULE_ID = "tab_ex05"


@module.ui
def _ui():
    return ui.div(
        ui.h3("Sine wave"),
        ui.row(
            ui.column(
                4,
                ui.div(
                    ui.input_slider("freq", "Frequency", min=1, max=10, value=2, step=0.5),
                    ui.input_slider("amp", "Amplitude", min=0.5, max=5, value=1, step=0.5),
                    ui.input_checkbox("grid", "Show grid", value=True),
                    class_="user-form-card",
                ),
            ),
            ui.column(8, ui.output_plot("wave", height="360px")),
        ),
        class_="tab-pane-content",
    )


@module.server
def _server(input, output, session):
    @render.plot
    def wave():
        x = np.linspace(0, 2 * np.pi, 400)
        y = input.amp() * np.sin(input.freq() * x)

        fig, ax = plt.subplots(figsize=(7.2, 3.6))
        ax.plot(x, y, color="#2563eb", linewidth=2)
        ax.set_ylim(-5.5, 5.5)
        ax.set_title("y = amplitude * sin(frequency * x)")
        ax.grid(bool(input.grid()), alpha=0.3)
        fig.tight_layout()
        return fig


def panel():
    return _ui(MODULE_ID)


def server():
    _server(MODULE_ID)
