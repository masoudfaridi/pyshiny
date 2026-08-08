"""Components tab module."""

from shiny import ui

# Unique identifier used to map sidebar navigation to this module.
NAV_ID = "tab_04"
# Human-readable label displayed in the sidebar.
NAV_LABEL = "Components"
# Icon shown for this top-level sidebar item.
NAV_ICON = "bi-grid"
# None means this item is displayed outside a collapsible group.
NAV_GROUP = None
# Every authenticated role can access this page.
NAV_MIN_ROLE = "guest"

def panel():
    """Return the user interface for the Components page."""
    # This page is intended for reusable UI component examples.
    return ui.div(
        ui.h3("Components"),
        ui.p("Required role: Guest (all authenticated users)."),
        ui.p(
            "This is a placeholder for reusable UI components. "
            "Use this page to document and demonstrate components used by the project."
        ),
        class_="tab-pane-content",
    )
