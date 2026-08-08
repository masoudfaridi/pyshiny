"""Dashboard v2 tab module."""

from shiny import ui

# Unique identifier used to map sidebar navigation to this module.
NAV_ID = "tab_02"
# Human-readable label displayed in the sidebar.
NAV_LABEL = "Dashboard v2"
# Child items do not display an individual icon.
NAV_ICON = None
# Place this tab inside the Dashboard collapsible group.
NAV_GROUP = "dashboard"
# Admin and Superadmin users can access this page.
NAV_MIN_ROLE = "admin"

def panel():
    """Return the user interface for Dashboard v2."""
    # Keep this page as a clean starting point for an alternative dashboard layout.
    return ui.div(
        ui.h3("Dashboard v2"),
        ui.p("Required role: Admin (and Superadmin)."),
        ui.p(
            "This is a placeholder page for Dashboard v2. "
            "Use it for an alternative layout, visualization set, or KPI design."
        ),
        class_="tab-pane-content",
    )
