"""
Example 04 -- Shared computation (reactive.calc)

Concepts
--------
* ``@reactive.calc`` computes a value ONCE and lets several outputs reuse it.
  It re-runs only when the inputs it reads change.
* Without it, ``bmi_value`` and ``bmi_category`` would each repeat the formula.
"""

from __future__ import annotations

from shiny import module, reactive, render, ui

NAV_ID = "tab_ex04"
NAV_LABEL = "Ex 04 Calc"
NAV_ICON = "bi-calculator"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"

MODULE_ID = "tab_ex04"


@module.ui
def _ui():
    return ui.div(
        ui.h3("Body mass index"),
        ui.row(
            ui.column(
                5,
                ui.div(
                    ui.input_slider("weight", "Weight (kg)", min=30, max=200, value=70),
                    ui.input_slider("height", "Height (cm)", min=120, max=220, value=170),
                    class_="user-form-card",
                ),
            ),
            ui.column(
                7,
                ui.div(
                    ui.h5("Result"),
                    ui.output_text("bmi_value"),
                    ui.output_ui("bmi_category"),
                    class_="user-form-card",
                ),
            ),
        ),
        class_="tab-pane-content",
    )


@module.server
def _server(input, output, session):
    @reactive.calc
    def bmi() -> float:
        height_m = input.height() / 100
        return input.weight() / (height_m * height_m)

    @render.text
    def bmi_value():
        return f"BMI = {bmi():.1f}"

    @render.ui
    def bmi_category():
        value = bmi()
        if value < 18.5:
            label, css = "Underweight", "text-muted"
        elif value < 25:
            label, css = "Normal range", ""
        elif value < 30:
            label, css = "Overweight", "text-muted"
        else:
            label, css = "Obese range", "login-error"
        return ui.p(label, class_=css)


def panel():
    return _ui(MODULE_ID)


def server():
    _server(MODULE_ID)
