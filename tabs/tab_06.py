"""
Tab 06 — Tables placeholder (module-based layout demo).

Uses ``@module.ui`` so any control id is automatically prefixed with ``tab_06-``
(same role as R Shiny ``ns()``). See ``tab_01.py`` for the full explanation.
"""

from __future__ import annotations

from shiny import module, ui

NAV_ID = "tab_06"
NAV_LABEL = "Tables"
NAV_ICON = "bi-table"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"

MODULE_ID = "tab_06"


@module.ui
def _ui():
    """
    Placeholder UI with a Bootstrap grid.

    Future inputs such as ``ui.input_text("filter", ...)`` become ``tab_06-filter``
    in the DOM and cannot clash with ``tab_05-filter`` or ``tab_01-n``.
    """
    return ui.div(
        ui.h3("Tables"),
        ui.p("Example layout using Bootstrap rows and columns (12-column grid)."),
        ui.row(
            ui.column(
                12,
                ui.div(
                    ui.h5("Full-width row (column 12)"),
                    ui.p(
                        "Use this for wide data tables that need the full content width."
                    ),
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


@module.server
def _server(input, output, session):
    """No reactive logic yet; registered so the module namespace stays active."""
    return


def panel():
    return _ui(MODULE_ID)


def server(get_session_user=None):
    """Register once from app.py: ``tab_06.server(_ensure_valid_session)``.

    No outputs yet. When you add some, gate them like tabs/tab_01.py does
    (``allowed = gate(get_session_user, NAV_MIN_ROLE)`` + ``req(allowed())``).
    """
    _server(MODULE_ID)
