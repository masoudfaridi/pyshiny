"""Normal distribution sampler and histogram."""

from __future__ import annotations

import numpy as np
from matplotlib import pyplot as plt
from shiny import reactive, render, ui

NAV_ID = "tab_01"
NAV_LABEL = "Normal"
NAV_ICON = None
NAV_GROUP = "dashboard"
NAV_MIN_ROLE = "superadmin"


def panel():
    """UI: mean, variance, sample size → generate → histogram (Bootstrap grid)."""
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
                    ui.input_numeric("norm_mean", "Mean (μ)", value=0.0, step=0.1),
                    ui.input_numeric(
                        "norm_var", "Variance (σ²)", value=1.0, min=1e-6, step=0.1
                    ),
                    ui.input_numeric(
                        "norm_n",
                        "Sample size (n)",
                        value=500,
                        min=2,
                        max=50_000,
                        step=10,
                    ),
                    ui.input_action_button(
                        "norm_generate",
                        "Generate sample",
                        class_="btn btn-primary mt-2 w-100",
                    ),
                    class_="user-form-card",
                ),
                ui.output_ui("norm_summary"),
            ),
            ui.column(
                8,
                ui.output_plot("norm_hist", height="360px"),
            ),
        ),
        class_="tab-pane-content",
    )


def server(input, output, session):
    """Wire this from app.py: tab_01.server(input, output, session)."""
    sample = reactive.Value(None)

    @reactive.effect
    @reactive.event(input.norm_generate)
    def _generate():
        mean = float(input.norm_mean())
        var = float(input.norm_var())
        n = int(input.norm_n())

        if var <= 0:
            sample.set({"error": "Variance must be positive."})
            return
        if n < 2 or n > 50_000:
            sample.set({"error": "Sample size must be between 2 and 50,000."})
            return

        data = np.random.default_rng().normal(loc=mean, scale=np.sqrt(var), size=n)
        sample.set({"data": data, "mean": mean, "var": var, "n": n, "error": None})

    @render.ui
    def norm_summary():
        state = sample()
        if state is None:
            return ui.p("Press Generate sample to draw data.", class_="text-muted")
        if state.get("error"):
            return ui.div(state["error"], class_="login-error")

        data = state["data"]
        return ui.div(
            ui.tags.ul(
                ui.tags.li(
                    f"Population μ = {state['mean']:.4g}, σ² = {state['var']:.4g}"
                ),
                ui.tags.li(f"Sample size n = {state['n']}"),
                ui.tags.li(f"Sample mean = {float(np.mean(data)):.4g}"),
                ui.tags.li(f"Sample variance = {float(np.var(data, ddof=1)):.4g}"),
            ),
            class_="user-form-card mt-3",
        )

    @render.plot
    def norm_hist():
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
