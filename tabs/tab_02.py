"""
Tab 02 — Poisson distribution sampler + histogram.

Uses ``@module.ui`` / ``@module.server`` so local ids are automatically prefixed
with ``tab_02-`` (Python equivalent of R Shiny ``ns()``).
See ``tab_01.py`` for the full module explanation.
"""

from __future__ import annotations

import numpy as np
from shiny import module, reactive, render, req, ui

from tabs._access import finite as _finite
from tabs._access import gate

NAV_ID = "tab_02"
NAV_LABEL = "Poisson"
NAV_ICON = None
NAV_GROUP = "dashboard"
NAV_MIN_ROLE = "admin"

MODULE_ID = "tab_02"


@module.ui
def _ui():
    """Local ids only; Shiny turns ``n`` into ``tab_02-n`` when panel() runs."""
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
                    # ``lambda_`` avoids clashing with the Python keyword ``lambda``.
                    ui.input_numeric(
                        "lambda_", "Rate (λ)", value=4.0, min=1e-6, step=0.1
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
    """Server logic scoped to ``tab_02-...`` inputs/outputs."""
    sample = reactive.Value(None)
    # Server-side role check (see tabs/_access.py): the sidebar only hides links.
    allowed = gate(get_session_user, NAV_MIN_ROLE)

    @reactive.effect
    @reactive.event(input.generate)
    def _generate():
        if not allowed():
            return
        try:
            lam = _finite(input.lambda_())
            n = int(input.n())

            if lam <= 0:
                sample.set({"error": "λ must be positive."})
                return
            if n < 2 or n > 50_000:
                sample.set({"error": "Sample size must be between 2 and 50,000."})
                return

            data = np.random.default_rng().poisson(lam=lam, size=n)
            sample.set({"data": data, "lam": lam, "n": n, "error": None})
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
        return ui.div(
            ui.tags.ul(
                ui.tags.li("Population λ = {0:.4g}".format(state["lam"])),
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


def panel():
    """Namespaced UI: local ``n`` becomes ``tab_02-n`` in the DOM."""
    return _ui(MODULE_ID)


def server(get_session_user=None):
    """Register once from app.py: ``tab_02.server()``."""
    _server(MODULE_ID, get_session_user=get_session_user)
