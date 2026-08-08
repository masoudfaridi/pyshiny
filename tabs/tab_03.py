"""Dashboard v3 tab module."""

from shiny import ui

# Unique identifier used to map sidebar navigation to this module.
NAV_ID = "tab_03"
# Human-readable label displayed in the sidebar.
NAV_LABEL = "Dashboard v3"
# Child items do not display an individual icon.
NAV_ICON = None
# Place this tab inside the Dashboard collapsible group.
NAV_GROUP = "dashboard"
# User, Admin, and Superadmin users can access this page.
NAV_MIN_ROLE = "user"

def panel():
    """Return the user interface for Dashboard v3."""
    # Keep this page available as another independent dashboard composition.
    return ui.div(
        ui.h3("Dashboard v3"),
        ui.p("Required role: User (and Admin, Superadmin)."),
        ui.p(
            "This is a placeholder page for Dashboard v3. "
            "It can demonstrate a different dashboard composition or visualization strategy."
        ),
        class_="tab-pane-content",
    )
