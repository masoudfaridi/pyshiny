"""
Tab 01 — Normal distribution sampler + histogram.

---------------------------------------------------------------------------
Shiny Modules and @module.ui  (same idea as R Shiny's ns())
---------------------------------------------------------------------------
In R you write ns("mean") so the real DOM id becomes something like
"tab_01-mean". Two tabs can both use the local name "mean" without clashing.

In Shiny for Python:

  * @module.ui marks a UI factory. Inside it you use *short local ids*
    ("mean", "var", "n"). You never write the prefix yourself.
  * Calling _ui("tab_01") makes Shiny rewrite every id to tab_01-mean,
    tab_01-var, tab_01-n, ...
  * @module.server is started with the *same* module id: _server("tab_01").
    Inside that server, input.mean() already refers to the namespaced value.
  * panel() only returns the namespaced UI for the shell to display.
  * server() must be registered *once* from app.py's server() — not on
    every tab switch and not inside the login handler.

MODULE_ID is the namespace prefix for this tab.
---------------------------------------------------------------------------
"""

from __future__ import annotations

import numpy as np
from matplotlib import pyplot as plt
from shiny import module, reactive, render, ui

NAV_ID = "tab_01"
NAV_LABEL = "Normal"
NAV_ICON = None
NAV_GROUP = "dashboard"
NAV_MIN_ROLE = "superadmin"

# Prefix applied to every input/output id inside this module.
MODULE_ID = "tab_01"


@module.ui
def _ui():
    """
    Module UI — local ids only.

    After ``_ui("tab_01")`` the browser sees ``tab_01-mean``, ``tab_01-var``,
    ``tab_01-n``, ``tab_01-generate``, ``tab_01-summary``, ``tab_01-hist``.
    That is the Python equivalent of R's ``ns("mean")``.
    """
    return ui.div(
        ui.h3("Normal distribution"),
        ui.p(
            "Choose the population mean (μ) and variance (σ²), set the sample size, "
            "then generate random draws and view the histogram."
        ),
        ui.row(
            ui.column(
                4,
                ui.div(
                    ui.input_numeric("mean", "Mean (μ)", value=0.0, step=0.1),
                    ui.input_numeric(
                        "var", "Variance (σ²)", value=1.0, min=1e-6, step=0.1
                    ),
                    ui.input_numeric(
                        "n",
                        "Sample size (n)",
                        value=500,
                        min=2,
                        max=50_000,
                        step=10,
                    ),
                    ui.input_action_button(
                        "generate",
                        "Generate sample",
                        class_="btn btn-primary mt-2 w-100",
                    ),
                    class_="user-form-card",
                ),
                ui.output_ui("summary"),
            ),
            ui.column(
                8,
                ui.output_plot("hist", height="360px"),
            ),
        ),
        class_="tab-pane-content",
    )


@module.server
def _server(input, output, session):
    """
    Module server — already scoped to MODULE_ID.

    ``input.mean()`` means the namespaced control ``tab_01-mean``.
    No manual prefix is required here.
    """
    sample = reactive.Value(None)

    @reactive.effect
    @reactive.event(input.generate)
    def _generate():
        mean = float(input.mean())
        var = float(input.var())
        n = int(input.n())

        if var <= 0:
            sample.set({"error": "Variance must be positive."})
            return
        if n < 2 or n > 50_000:
            sample.set({"error": "Sample size must be between 2 and 50,000."})
            return

        data = np.random.default_rng().normal(loc=mean, scale=np.sqrt(var), size=n)
        sample.set({"data": data, "mean": mean, "var": var, "n": n, "error": None})

    @render.ui
    def summary():
        state = sample()
        if state is None:
            return ui.p("Press Generate sample to draw data.", class_="text-muted")
        if state.get("error"):
            return ui.div(state["error"], class_="login-error")

        data = state["data"]
        return ui.div(
            ui.tags.ul(
                ui.tags.li(
                    "Population μ = {0:.4g}, σ² = {1:.4g}".format(
                        state["mean"], state["var"]
                    )
                ),
                ui.tags.li("Sample size n = {0}".format(state["n"])),
                ui.tags.li("Sample mean = {0:.4g}".format(float(np.mean(data)))),
                ui.tags.li(
                    "Sample variance = {0:.4g}".format(float(np.var(data, ddof=1)))
                ),
            ),
            class_="user-form-card mt-3",
        )

    @render.plot
    def hist():
        state = sample()
        fig, ax = plt.subplots(figsize=(7.2, 3.6))
        if state is None or state.get("error"):
            ax.text(0.5, 0.5, "No sample yet", ha="center", va="center", fontsize=12)
            ax.set_axis_off()
            return fig

        data = state["data"]
        ax.hist(data, bins="auto", color="#2563eb", edgecolor="white", alpha=0.9)
        ax.axvline(
            state["mean"], color="#dc2626", linestyle="--", linewidth=1.5, label="μ"
        )
        ax.axvline(
            float(np.mean(data)),
            color="#16a34a",
            linestyle="-",
            linewidth=1.5,
            label="Sample mean",
        )
        ax.set_title("Normal sample histogram")
        ax.set_xlabel("Value")
        ax.set_ylabel("Frequency")
        ax.legend(frameon=False)
        fig.tight_layout()
        return fig


def panel():
    """Return namespaced UI for the shell (``tab_01-...`` ids in the DOM)."""
    return _ui(MODULE_ID)


def server():
    """
    Register the module server once from app.py::

        tab_01.server()

    Do not call this inside login or on every sidebar navigation.
    """
    _server(MODULE_ID)
