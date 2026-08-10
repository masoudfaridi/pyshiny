"""Poisson distribution sampler and histogram."""

from __future__ import annotations

import numpy as np
from matplotlib import pyplot as plt
from shiny import reactive, render, ui

NAV_ID = "tab_02"
NAV_LABEL = "Poisson"
NAV_ICON = None
NAV_GROUP = "dashboard"
NAV_MIN_ROLE = "admin"


def panel():
    """UI: rate λ, sample size → generate → histogram (Bootstrap grid)."""
    return ui.div(
        ui.h3("Poisson distribution"),
        ui.p(
            "Choose the rate parameter λ (mean number of events), set the sample size, "
            "then generate random draws and view the histogram."
        ),
        ui.row(
            ui.column(
                4,
                ui.div(
                    ui.input_numeric(
                        "pois_lambda", "Rate (λ)", value=4.0, min=1e-6, step=0.1
                    ),
                    ui.input_numeric(
                        "pois_n",
                        "Sample size (n)",
                        value=500,
                        min=2,
                        max=50_000,
                        step=10,
                    ),
                    ui.input_action_button(
                        "pois_generate",
                        "Generate sample",
                        class_="btn btn-primary mt-2 w-100",
                    ),
                    class_="user-form-card",
                ),
                ui.output_ui("pois_summary"),
            ),
            ui.column(
                8,
                ui.output_plot("pois_hist", height="360px"),
            ),
        ),
        class_="tab-pane-content",
    )


def server(input, output, session):
    """Wire this from app.py: tab_02.server(input, output, session)."""
    sample = reactive.Value(None)

    @reactive.effect
    @reactive.event(input.pois_generate)
    def _generate():
        lam = float(input.pois_lambda())
        n = int(input.pois_n())

        if lam <= 0:
            sample.set({"error": "λ must be positive."})
            return
        if n < 2 or n > 50_000:
            sample.set({"error": "Sample size must be between 2 and 50,000."})
            return

        data = np.random.default_rng().poisson(lam=lam, size=n)
        sample.set({"data": data, "lam": lam, "n": n, "error": None})

    @render.ui
    def pois_summary():
        state = sample()
        if state is None:
            return ui.p("Press Generate sample to draw data.", class_="text-muted")
        if state.get("error"):
            return ui.div(state["error"], class_="login-error")

        data = state["data"]
        return ui.div(
            ui.tags.ul(
                ui.tags.li(f"Population λ = {state['lam']:.4g}"),
                ui.tags.li(f"Sample size n = {state['n']}"),
                ui.tags.li(f"Sample mean = {float(np.mean(data)):.4g}"),
                ui.tags.li(f"Sample variance = {float(np.var(data, ddof=1)):.4g}"),
            ),
            class_="user-form-card mt-3",
        )

    @render.plot
    def pois_hist():
        state = sample()
        fig, ax = plt.subplots(figsize=(7.2, 3.6))
        if state is None or state.get("error"):
            ax.text(0.5, 0.5, "No sample yet", ha="center", va="center", fontsize=12)
            ax.set_axis_off()
            return fig

        data = state["data"]
        # Integer support: align bins on counts.
        lo, hi = int(data.min()), int(data.max())
        bins = np.arange(lo, hi + 2) - 0.5
        ax.hist(data, bins=bins, color="#7c3aed", edgecolor="white", alpha=0.9)
        ax.axvline(
            state["lam"], color="#dc2626", linestyle="--", linewidth=1.5, label="λ"
        )
        ax.axvline(
            float(np.mean(data)),
            color="#16a34a",
            linestyle="-",
            linewidth=1.5,
            label="Sample mean",
        )
        ax.set_title("Poisson sample histogram")
        ax.set_xlabel("Count")
        ax.set_ylabel("Frequency")
        ax.legend(frameon=False)
        fig.tight_layout()
        return fig
