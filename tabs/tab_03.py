"""
Tab 03 — Binomial distribution sampler + histogram.

``@module.ui`` namespaces all local ids under ``tab_03-`` (like R's ``ns()``).
See ``tab_01.py`` for the full module explanation.
"""

from __future__ import annotations

import numpy as np
from matplotlib import pyplot as plt
from shiny import module, reactive, render, ui

NAV_ID = "tab_03"
NAV_LABEL = "Binomial"
NAV_ICON = None
NAV_GROUP = "dashboard"
NAV_MIN_ROLE = "user"

MODULE_ID = "tab_03"


@module.ui
def _ui():
    """Local ids (``m``, ``p``, ``n``, ...) — prefixed automatically with MODULE_ID."""
    return ui.div(
        ui.h3("Binomial distribution"),
        ui.p(
            "Choose the number of trials (m) and success probability (p), set the "
            "sample size, then generate random draws and view the histogram."
        ),
        ui.row(
            ui.column(
                4,
                ui.div(
                    ui.input_numeric(
                        "m", "Trials (m)", value=20, min=1, max=10_000, step=1
                    ),
                    ui.input_numeric(
                        "p",
                        "Success probability (p)",
                        value=0.3,
                        min=0.0,
                        max=1.0,
                        step=0.01,
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
    """Server logic scoped to ``tab_03-...``."""
    sample = reactive.Value(None)

    @reactive.effect
    @reactive.event(input.generate)
    def _generate():
        m = int(input.m())
        p = float(input.p())
        n = int(input.n())

        if m < 1:
            sample.set({"error": "Number of trials must be at least 1."})
            return
        if not 0.0 <= p <= 1.0:
            sample.set({"error": "Probability p must be between 0 and 1."})
            return
        if n < 2 or n > 50_000:
            sample.set({"error": "Sample size must be between 2 and 50,000."})
            return

        data = np.random.default_rng().binomial(n=m, p=p, size=n)
        sample.set({"data": data, "m": m, "p": p, "n": n, "error": None})

    @render.ui
    def summary():
        state = sample()
        if state is None:
            return ui.p("Press Generate sample to draw data.", class_="text-muted")
        if state.get("error"):
            return ui.div(state["error"], class_="login-error")

        data = state["data"]
        pop_mean = state["m"] * state["p"]
        pop_var = state["m"] * state["p"] * (1.0 - state["p"])
        return ui.div(
            ui.tags.ul(
                ui.tags.li(
                    "Trials m = {0}, p = {1:.4g}".format(state["m"], state["p"])
                ),
                ui.tags.li(
                    "Population mean = {0:.4g}, variance = {1:.4g}".format(
                        pop_mean, pop_var
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
        lo, hi = int(data.min()), int(data.max())
        bins = np.arange(lo, hi + 2) - 0.5
        ax.hist(data, bins=bins, color="#0f766e", edgecolor="white", alpha=0.9)
        pop_mean = state["m"] * state["p"]
        ax.axvline(
            pop_mean, color="#dc2626", linestyle="--", linewidth=1.5, label="Mean mp"
        )
        ax.axvline(
            float(np.mean(data)),
            color="#16a34a",
            linestyle="-",
            linewidth=1.5,
            label="Sample mean",
        )
        ax.set_title("Binomial sample histogram")
        ax.set_xlabel("Number of successes")
        ax.set_ylabel("Frequency")
        ax.legend(frameon=False)
        fig.tight_layout()
        return fig


def panel():
    return _ui(MODULE_ID)


def server():
    """Register once from app.py: ``tab_03.server()``."""
    _server(MODULE_ID)
