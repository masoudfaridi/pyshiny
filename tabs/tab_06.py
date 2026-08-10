"""Tables placeholder page."""

from shiny import ui

NAV_ID = "tab_06"
NAV_LABEL = "Tables"
NAV_ICON = "bi-table"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"


def panel():
    """Simple Bootstrap grid demo for tables."""
    return ui.div(
        ui.h3("Tables"),
        ui.p("Example layout using Bootstrap rows and columns (12-column grid)."),
        ui.row(
            ui.column(
                12,
                ui.div(
                    ui.h5("Full-width row (column 12)"),
                    ui.p("Use this for wide data tables that need the full content width."),
                    class_="user-form-card",
                ),
            ),
        ),
        ui.row(
            ui.column(
                6,
                ui.div(
                    ui.h5("Column 6"),
                    ui.p("Half-width table or summary on the left."),
                    class_="user-form-card mt-3",
                ),
            ),
            ui.column(
                6,
                ui.div(
                    ui.h5("Column 6"),
                    ui.p("Half-width table or summary on the right."),
                    class_="user-form-card mt-3",
                ),
            ),
        ),
        class_="tab-pane-content",
    )
