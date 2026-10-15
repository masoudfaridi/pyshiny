"""
Example 06 -- A filterable, sortable table (no pandas needed)

Concepts
--------
* ``@reactive.calc`` produces the filtered/sorted rows once; ``@render.ui``
  turns them into an HTML table (the same technique app.py uses for the users
  table, with the ``users-table`` CSS class).
* Plain Python data (a list of dicts) is enough for small tables. For big
  data frames see MODULES.md ("Tables with pandas").
"""

from __future__ import annotations

from shiny import module, reactive, render, ui

NAV_ID = "tab_ex06"
NAV_LABEL = "Ex 06 Table"
NAV_ICON = "bi-table"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"

MODULE_ID = "tab_ex06"

# Sample data -- replace with a database query or a file in a real tab.
PRODUCTS = [
    {"name": "Notebook", "category": "Paper", "price": 3.5, "stock": 120},
    {"name": "Sketchbook", "category": "Paper", "price": 8.0, "stock": 35},
    {"name": "Ballpoint pen", "category": "Writing", "price": 1.2, "stock": 400},
    {"name": "Fountain pen", "category": "Writing", "price": 24.0, "stock": 12},
    {"name": "Marker set", "category": "Writing", "price": 9.5, "stock": 60},
    {"name": "Stapler", "category": "Office", "price": 6.0, "stock": 45},
    {"name": "Desk lamp", "category": "Office", "price": 32.0, "stock": 8},
]
CATEGORIES = ["All"] + sorted({row["category"] for row in PRODUCTS})
SORT_FIELDS = {"name": "Name", "price": "Price", "stock": "Stock"}


@module.ui
def _ui():
    return ui.div(
        ui.h3("Products"),
        ui.row(
            ui.column(
                4,
                ui.div(
                    ui.input_text("query", "Name contains", placeholder="e.g. pen"),
                    ui.input_select("category", "Category", CATEGORIES),
                    ui.input_radio_buttons("sort_by", "Sort by", SORT_FIELDS, selected="name"),
                    ui.input_checkbox("descending", "Descending", value=False),
                    class_="user-form-card",
                ),
            ),
            ui.column(8, ui.output_ui("table")),
        ),
        class_="tab-pane-content",
    )


@module.server
def _server(input, output, session):
    @reactive.calc
    def rows() -> list[dict]:
        query = (input.query() or "").strip().lower()
        category = input.category()
        data = [
            row
            for row in PRODUCTS
            if (not query or query in row["name"].lower())
            and (category == "All" or row["category"] == category)
        ]
        return sorted(data, key=lambda r: r[input.sort_by()], reverse=bool(input.descending()))

    @render.ui
    def table():
        data = rows()
        if not data:
            return ui.p("No products match the filter.", class_="text-muted")
        header = ui.tags.tr(*[ui.tags.th(label) for label in ("Name", "Category", "Price", "Stock")])
        body = [
            ui.tags.tr(
                ui.tags.td(row["name"]),
                ui.tags.td(row["category"]),
                ui.tags.td(f"{row['price']:.2f}"),
                ui.tags.td(str(row["stock"])),
            )
            for row in data
        ]
        return ui.div(
            ui.tags.table(header, *body, class_="users-table"),
            ui.p(f"{len(data)} of {len(PRODUCTS)} rows", class_="text-muted small mt-2"),
        )


def panel():
    return _ui(MODULE_ID)


def server():
    _server(MODULE_ID)
