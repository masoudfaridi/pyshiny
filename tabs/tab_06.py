"""Tables tab module."""

from shiny import ui

# Unique identifier used to map sidebar navigation to this module.
NAV_ID = "tab_06"
# Human-readable label displayed in the sidebar.
NAV_LABEL = "Tables"
# Icon shown for this top-level sidebar item.
NAV_ICON = "bi-table"
# None means this item is displayed outside a collapsible group.
NAV_GROUP = None
# This page is available to every authenticated role.
NAV_MIN_ROLE = "guest"

def panel():
    """Return the user interface for the Tables page."""
    # This page is intended for data tables and related controls.
    return ui.div(
        ui.h3("Tables"),
        ui.p(
            "This is a placeholder for data tables. "
            "Add filtering, sorting, pagination, selection, and export features here."
        ),
        class_="tab-pane-content",
    )
