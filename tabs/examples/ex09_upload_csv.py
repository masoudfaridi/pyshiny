"""
Example 09 -- Uploading a CSV file

Concepts
--------
* ``ui.input_file`` gives the server a list of dicts with ``name``, ``size``,
  ``type`` and ``datapath`` (a temporary file on the server).
* Parsing with the standard ``csv`` module, so no extra dependency.
* Always guard uploads: size limit, encoding errors, malformed rows. Show a
  friendly message instead of letting the exception reach the user.
"""

from __future__ import annotations

import csv

from shiny import module, reactive, render, ui

NAV_ID = "tab_ex09"
NAV_LABEL = "Ex 09 Upload CSV"
NAV_ICON = "bi-upload"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"

MODULE_ID = "tab_ex09"

MAX_BYTES = 2 * 1024 * 1024  # 2 MB
PREVIEW_ROWS = 10


@module.ui
def _ui():
    return ui.div(
        ui.h3("Upload a CSV file"),
        ui.div(
            ui.input_file("csv_file", "Choose a .csv file", accept=[".csv"], multiple=False),
            class_="user-form-card",
        ),
        ui.output_ui("preview"),
        class_="tab-pane-content",
    )


@module.server
def _server(input, output, session):
    @reactive.calc
    def parsed() -> dict:
        files = input.csv_file()
        if not files:
            return {"error": None, "empty": True}
        info = files[0]
        if info["size"] > MAX_BYTES:
            return {"error": f"File is too large (limit {MAX_BYTES // 1024} KB)."}
        try:
            with open(info["datapath"], newline="", encoding="utf-8-sig") as handle:
                reader = csv.reader(handle)
                header = next(reader, None)
                rows = list(reader)
        except (UnicodeDecodeError, csv.Error):
            return {"error": "Could not read the file. Is it a UTF-8 CSV?"}
        if not header:
            return {"error": "The file is empty."}
        return {"error": None, "name": info["name"], "header": header, "rows": rows}

    @render.ui
    def preview():
        result = parsed()
        if result.get("empty"):
            return ui.p("No file selected yet.", class_="text-muted mt-3")
        if result["error"]:
            return ui.div(result["error"], class_="login-error mt-3")

        header, rows = result["header"], result["rows"]
        head = ui.tags.tr(*[ui.tags.th(col) for col in header])
        body = [ui.tags.tr(*[ui.tags.td(cell) for cell in row]) for row in rows[:PREVIEW_ROWS]]
        return ui.div(
            ui.p(
                f"{result['name']}: {len(rows)} rows, {len(header)} columns "
                f"(showing the first {min(PREVIEW_ROWS, len(rows))})",
                class_="mt-3",
            ),
            ui.div(ui.tags.table(head, *body, class_="users-table"), style="overflow-x:auto"),
        )


def panel():
    return _ui(MODULE_ID)


def server():
    _server(MODULE_ID)
