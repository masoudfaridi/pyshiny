"""
Tab 05 — Widgets placeholder (module-based layout demo).

Uses ``@module.ui`` so any control id is automatically prefixed with ``tab_05-``
(same role as R Shiny ``ns()``). See ``tab_01.py`` for the full explanation.
"""

from __future__ import annotations

from shiny import module, ui

NAV_ID = "tab_05"
NAV_LABEL = "Widgets"
NAV_ICON = "bi-boxes"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"

MODULE_ID = "tab_05"


@module.ui
def _ui():
    """
    Placeholder UI with a Bootstrap grid.

    If you later add ``ui.input_text("title", ...)``, the DOM id becomes
    ``tab_05-title`` — safe even if another tab also uses local id ``title``.
    """
    return ui.div(
        ui.h3("Widgets"),
        ui.p(
            "Placeholder for dashboard widgets (KPI cards, charts, status indicators). "
            "This tab is a Shiny module: new controls can reuse simple local ids "
            "without colliding with other tabs."
        ),
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


@module.server
def _server(input, output, session):
    """No reactive logic yet; registered so the module namespace stays active."""
    return


def panel():
    return _ui(MODULE_ID)


def server(get_session_user=None):
    """Register once from app.py: ``tab_05.server(_ensure_valid_session)``.

    No outputs yet. When you add some, gate them like tabs/tab_01.py does
    (``allowed = gate(get_session_user, NAV_MIN_ROLE)`` + ``req(allowed())``).
    """
    _server(MODULE_ID)
