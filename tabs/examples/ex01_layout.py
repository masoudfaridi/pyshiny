"""
Example 01 -- Static layout (no server logic)

Concepts
--------
* The minimum a tab needs: NAV_* metadata, a ``@module.ui`` function, a
  ``@module.server`` function, ``panel()`` and ``server()``.
* Bootstrap grid (``ui.row`` / ``ui.column``, 12 columns), ``ui.navset_tab``
  (tabs inside a tab) and ``ui.accordion`` (collapsible sections).
* An empty server is fine: it keeps the module registered and gives you a
  place to add logic later.

Try it: see tabs/examples/README.md ("Try an example").
"""

from __future__ import annotations

from shiny import module, ui

NAV_ID = "tab_ex01"          # must be unique in the whole app
NAV_LABEL = "Ex 01 Layout"   # text shown in the sidebar
NAV_ICON = "bi-layout-three-columns"
NAV_GROUP = None             # None = top-level sidebar item
NAV_MIN_ROLE = "guest"       # guest | user | admin | superadmin

MODULE_ID = "tab_ex01"       # prefix for every id inside this module


def _card(title: str, text: str, extra_class: str = "") -> ui.Tag:
    """A plain helper (NOT a module) that returns a styled box."""
    return ui.div(ui.h5(title), ui.p(text), class_=f"user-form-card {extra_class}".strip())


@module.ui
def _ui():
    return ui.div(
        ui.h3("Layout example"),
        ui.p("Rows are split into 12 columns; the numbers below add up to 12."),
        ui.row(
            ui.column(4, _card("Column 4", "One third.")),
            ui.column(4, _card("Column 4", "One third.")),
            ui.column(4, _card("Column 4", "One third.")),
        ),
        ui.row(
            ui.column(8, _card("Column 8", "Two thirds: main content.", "mt-3")),
            ui.column(4, _card("Column 4", "One third: side panel.", "mt-3")),
        ),
        ui.h4("Tabs inside a tab", class_="mt-4"),
        ui.navset_tab(
            ui.nav_panel("Overview", ui.p("Content of the first inner tab.")),
            ui.nav_panel("Details", ui.p("Content of the second inner tab.")),
            id="inner_tabs",  # becomes tab_ex01-inner_tabs in the browser
        ),
        ui.h4("Accordion", class_="mt-4"),
        ui.accordion(
            ui.accordion_panel("What is this?", "Collapsible sections save space."),
            ui.accordion_panel("When should I use it?", "FAQs, long forms, filters."),
            id="faq",
        ),
        class_="tab-pane-content",
    )


@module.server
def _server(input, output, session):
    return  # nothing to compute yet


def panel():
    return _ui(MODULE_ID)


def server():
    _server(MODULE_ID)
