"""Negative binomial distribution sampler and histogram."""

from __future__ import annotations

import numpy as np
from matplotlib import pyplot as plt
from shiny import reactive, render, ui

NAV_ID = "tab_04"
NAV_LABEL = "Negative Binomial"
NAV_ICON = "bi-bar-chart"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"


def panel():
    """UI: successes r, probability p, sample size → generate → histogram (Bootstrap grid).

    Parameterization: number of failures before r successes (NumPy default).
    """
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
                        "nb_r", "Successes (r)", value=5, min=1, max=10_000, step=1
                    ),
                    ui.input_numeric(
                        "nb_p",
                        "Success probability (p)",
                        value=0.4,
                        min=1e-6,
                        max=1.0,
                        step=0.01,
                    ),
                    ui.input_numeric(
                        "nb_n",
                        "Sample size (n)",
                        value=500,
                        min=2,
                        max=50_000,
                        step=10,
                    ),
                    ui.input_action_button(
                        "nb_generate",
                        "Generate sample",
                        class_="btn btn-primary mt-2 w-100",
                    ),
                    class_="user-form-card",
                ),
                ui.output_ui("nb_summary"),
            ),
            ui.column(
                8,
                ui.output_plot("nb_hist", height="360px"),
            ),
        ),
        class_="tab-pane-content",
    )

def server(input, output, session):
    """Wire this from app.py: tab_04.server(input, output, session)."""
    sample = reactive.Value(None)

    @reactive.effect
    @reactive.event(input.nb_generate)
    def _generate():
        r = int(input.nb_r())
        p = float(input.nb_p())
        n = int(input.nb_n())

        if r < 1:
            sample.set({"error": "r must be at least 1."})
            return
        if not 0.0 < p <= 1.0:
            sample.set({"error": "Probability p must be in (0, 1]."})
            return
        if n < 2 or n > 50_000:
            sample.set({"error": "Sample size must be between 2 and 50,000."})
            return

        # NumPy: number of failures before r successes.
        data = np.random.default_rng().negative_binomial(n=r, p=p, size=n)
        sample.set({"data": data, "r": r, "p": p, "n": n, "error": None})

    @render.ui
    def nb_summary():
        state = sample()
        if state is None:
            return ui.p("Press Generate sample to draw data.", class_="text-muted")
        if state.get("error"):
            return ui.div(state["error"], class_="login-error")

        data = state["data"]
        r, p = state["r"], state["p"]
        pop_mean = r * (1.0 - p) / p
        pop_var = r * (1.0 - p) / (p**2)
        return ui.div(
            ui.tags.ul(
                ui.tags.li(f"Successes r = {r}, p = {p:.4g}"),
                ui.tags.li(
                    f"Population mean (failures) = {pop_mean:.4g}, "
                    f"variance = {pop_var:.4g}"
                ),
                ui.tags.li(f"Sample size n = {state['n']}"),
                ui.tags.li(f"Sample mean = {float(np.mean(data)):.4g}"),
                ui.tags.li(f"Sample variance = {float(np.var(data, ddof=1)):.4g}"),
            ),
            class_="user-form-card mt-3",
        )

    @render.plot
    def nb_hist():
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
