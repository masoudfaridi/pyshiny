"""Binomial distribution sampler and histogram."""

from __future__ import annotations

import numpy as np
from matplotlib import pyplot as plt
from shiny import reactive, render, ui

NAV_ID = "tab_03"
NAV_LABEL = "Binomial"
NAV_ICON = None
NAV_GROUP = "dashboard"
NAV_MIN_ROLE = "user"


def panel():
    """UI: trials m, success probability p, sample size → generate → histogram."""
    return ui.div(
        ui.h3("Binomial distribution"),
        ui.p(
            "Choose the number of trials (m) and success probability (p), set the "
            "sample size, then generate random draws and view the histogram."
        ),
        ui.div(
            ui.input_numeric(
                "bin_m", "Trials (m)", value=20, min=1, max=10_000, step=1
            ),
            ui.input_numeric(
                "bin_p",
                "Success probability (p)",
                value=0.3,
                min=0.0,
                max=1.0,
                step=0.01,
            ),
            ui.input_numeric(
                "bin_n",
                "Sample size (n)",
                value=500,
                min=2,
                max=50_000,
                step=10,
            ),
            ui.input_action_button(
                "bin_generate", "Generate sample", class_="btn btn-primary mt-2"
            ),
            class_="user-form-card",
        ),
        ui.output_ui("bin_summary"),
        ui.output_plot("bin_hist", height="360px"),
        class_="tab-pane-content",
    )


def server(input, output, session):
    """Wire this from app.py: tab_03.server(input, output, session)."""
    sample = reactive.Value(None)

    @reactive.effect
    @reactive.event(input.bin_generate)
    def _generate():
        m = int(input.bin_m())
        p = float(input.bin_p())
        n = int(input.bin_n())

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
    def bin_summary():
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
                ui.tags.li(f"Trials m = {state['m']}, p = {state['p']:.4g}"),
                ui.tags.li(f"Population mean = {pop_mean:.4g}, variance = {pop_var:.4g}"),
                ui.tags.li(f"Sample size n = {state['n']}"),
                ui.tags.li(f"Sample mean = {float(np.mean(data)):.4g}"),
                ui.tags.li(f"Sample variance = {float(np.var(data, ddof=1)):.4g}"),
            ),
            class_="user-form-card mt-3",
        )

    @render.plot
    def bin_hist():
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
