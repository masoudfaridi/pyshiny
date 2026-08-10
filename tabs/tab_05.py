"""Widgets placeholder page."""

from shiny import ui

NAV_ID = "tab_05"
NAV_LABEL = "Widgets"
NAV_ICON = "bi-sliders"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"


def panel():
    """Simple Bootstrap grid demo for widgets."""
    return ui.div(
        ui.h3("Widgets"),
        ui.p("Example layout using Bootstrap rows and columns (12-column grid)."),
        ui.row(
            ui.column(
                4,
                ui.div(
                    ui.h5("Column 4"),
                    ui.p("One-third width. Place filters or controls here."),
                    class_="user-form-card",
                ),
            ),
            ui.column(
                4,
                ui.div(
                    ui.h5("Column 4"),
                    ui.p("One-third width. Place summary cards here."),
                    class_="user-form-card",
                ),
            ),
            ui.column(
                4,
                ui.div(
                    ui.h5("Column 4"),
                    ui.p("One-third width. Place actions or status here."),
                    class_="user-form-card",
                ),
            ),
        ),
        ui.row(
            ui.column(
                8,
                ui.div(
                    ui.h5("Column 8"),
                    ui.p("Main content area (two-thirds). Charts or tables go here."),
                    class_="user-form-card mt-3",
                ),
            ),
            ui.column(
                4,
                ui.div(
                    ui.h5("Column 4"),
                    ui.p("Side panel (one-third)."),
                    class_="user-form-card mt-3",
                ),
            ),
        ),
        class_="tab-pane-content",
    )
