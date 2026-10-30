"""
Tab 04 — Negative binomial distribution sampler + histogram.

``@module.ui`` namespaces local ids under ``tab_04-`` (Python counterpart of R ``ns()``).
See ``tab_01.py`` for the full module explanation.

Parameterization (NumPy): number of *failures* before ``r`` successes.
"""

from __future__ import annotations

import numpy as np
from shiny import module, reactive, render, req, ui

from tabs._access import finite as _finite
from tabs._access import gate

NAV_ID = "tab_04"
NAV_LABEL = "Negative Binomial"
NAV_ICON = "bi-bar-chart"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"

MODULE_ID = "tab_04"


@module.ui
def _ui():
    """Local ids only; DOM ids become ``tab_04-r``, ``tab_04-p``, ``tab_04-n``, ..."""
    return ui.div(
        ui.h3("Negative binomial distribution"),
        ui.p(
            "Choose the target number of successes (r) and success probability (p). "
            "Each draw is the number of failures before r successes. "
            "Set the sample size, generate draws, and view the histogram."
        ),
        ui.row(
            ui.column(
                4,
                ui.div(
                    ui.input_numeric(
                        "r", "Successes (r)", value=5, min=1, max=10_000, step=1
                    ),
                    ui.input_numeric(
                        "p",
                        "Success probability (p)",
                        value=0.4,
                        min=1e-6,
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
def _server(input, output, session, get_session_user=None):
    """Server logic scoped to ``tab_04-...``."""
    sample = reactive.Value(None)
    # Server-side role check (see tabs/_access.py): the sidebar only hides links.
    allowed = gate(get_session_user, NAV_MIN_ROLE)

    @reactive.effect
    @reactive.event(input.generate)
    def _generate():
        if not allowed():
            return
        try:
            r = int(input.r())
            p = _finite(input.p())
            n = int(input.n())

            if r < 1:
                sample.set({"error": "r must be at least 1."})
                return
            if not 0.0 < p <= 1.0:
                sample.set({"error": "Probability p must be in (0, 1]."})
                return
            if n < 2 or n > 50_000:
                sample.set({"error": "Sample size must be between 2 and 50,000."})
                return

            data = np.random.default_rng().negative_binomial(n=r, p=p, size=n)
            sample.set({"data": data, "r": r, "p": p, "n": n, "error": None})
        except (TypeError, ValueError, OverflowError):
            # Empty / non-numeric / out-of-range input: show a message instead
            # of letting the exception end the whole browser session.
            sample.set({"error": "Please enter valid numbers."})

    @render.ui
    def summary():
        req(allowed())
        state = sample()
        if state is None:
            return ui.p("Press Generate sample to draw data.", class_="text-muted")
        if state.get("error"):
            return ui.div(state["error"], class_="login-error")

        data = state["data"]
        r, p = state["r"], state["p"]
        pop_mean = r * (1.0 - p) / p
        pop_var = r * (1.0 - p) / (p ** 2)
        return ui.div(
            ui.tags.ul(
                ui.tags.li("Successes r = {0}, p = {1:.4g}".format(r, p)),
                ui.tags.li(
                    "Population mean (failures) = {0:.4g}, variance = {1:.4g}".format(
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
        req(allowed())
        from matplotlib import pyplot as plt  # lazy: keeps app start-up light

        state = sample()
        fig, ax = plt.subplots(figsize=(7.2, 3.6))
        if state is None or state.get("error"):
            ax.text(0.5, 0.5, "No sample yet", ha="center", va="center", fontsize=12)
            ax.set_axis_off()
            return fig

        data = state["data"]
        lo, hi = int(data.min()), int(data.max())
        bins = np.arange(lo, hi + 2) - 0.5
        ax.hist(data, bins=bins, color="#ea580c", edgecolor="white", alpha=0.9)
        r, p = state["r"], state["p"]
        pop_mean = r * (1.0 - p) / p
        ax.axvline(
            pop_mean,
            color="#dc2626",
            linestyle="--",
            linewidth=1.5,
            label="Mean r(1-p)/p",
        )
        ax.axvline(
            float(np.mean(data)),
            color="#16a34a",
            linestyle="-",
            linewidth=1.5,
            label="Sample mean",
        )
        ax.set_title("Negative binomial sample histogram")
        ax.set_xlabel("Number of failures before r successes")
        ax.set_ylabel("Frequency")
        ax.legend(frameon=False)
        fig.tight_layout()
        return fig


def panel():
    return _ui(MODULE_ID)


def server(get_session_user=None):
    """Register once from app.py: ``tab_04.server()``."""
    _server(MODULE_ID, get_session_user=get_session_user)
