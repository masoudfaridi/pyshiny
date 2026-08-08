"""Dashboard v1 tab module."""

from shiny import ui

# Unique identifier used to map sidebar navigation to this module.
NAV_ID = "tab_01"
# Human-readable label displayed in the sidebar.
NAV_LABEL = "Dashboard v1"
# Child items inherit the icon from their parent group.
NAV_ICON = None
# Place this tab inside the Dashboard collapsible group.
NAV_GROUP = "dashboard"
# Only Superadmin users can access this page.
NAV_MIN_ROLE = "superadmin"

def panel():
    """Return the user interface for Dashboard v1."""
    # Keep the starter page simple so it can be replaced by real dashboard content.
    return ui.div(
        ui.h3("Dashboard v1"),
        ui.p("Required role: Superadmin only."),
        ui.p(
            "This is a placeholder page for Dashboard v1. "
            "Replace this content with KPI cards, charts, project activity, or other widgets."
        ),
        class_="tab-pane-content",
    )
