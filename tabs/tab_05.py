"""Widgets tab module."""

from shiny import ui

# Unique identifier used to map sidebar navigation to this module.
NAV_ID = "tab_05"
# Human-readable label displayed in the sidebar.
NAV_LABEL = "Widgets"
# Icon shown for this top-level sidebar item.
NAV_ICON = "bi-boxes"
# None means this item is displayed outside a collapsible group.
NAV_GROUP = None
# This page is available to every authenticated role.
NAV_MIN_ROLE = "guest"

def panel():
    """Return the user interface for the Widgets page."""
    # This page is intended for dashboard cards, charts, and small widgets.
    return ui.div(
        ui.h3("Widgets"),
        ui.p(
            "This is a placeholder for dashboard widgets. "
            "Add KPI cards, charts, status indicators, and other reusable widgets here."
        ),
        class_="tab-pane-content",
    )
