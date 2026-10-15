"""
Example 10 -- Downloading generated data as CSV

Concepts
--------
* ``ui.download_button("download", ...)`` in the UI  <->
  ``@render.download(...) def download()`` in the server.
* The download function ``yield``s the file content (str or bytes).
* The same id rule applies: both sides use the local id ``download``.
"""

from __future__ import annotations

import csv
import io
import random

from shiny import module, render, ui

NAV_ID = "tab_ex10"
NAV_LABEL = "Ex 10 Download CSV"
NAV_ICON = "bi-download"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"

MODULE_ID = "tab_ex10"


@module.ui
def _ui():
    return ui.div(
        ui.h3("Download a CSV file"),
        ui.div(
            ui.input_numeric("rows", "Number of rows", value=20, min=1, max=1000, step=1),
            ui.download_button("download", "Download CSV", class_="btn btn-primary mt-2"),
            class_="user-form-card",
        ),
        class_="tab-pane-content",
    )


@module.server
def _server(input, output, session):
    @render.download(filename="sample.csv", media_type="text/csv")
    def download():
        try:
            count = max(1, min(1000, int(input.rows() or 1)))
        except (TypeError, ValueError):
            count = 1

        rng = random.Random(42)  # fixed seed: the same file every time
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["id", "value", "flag"])
        for i in range(1, count + 1):
            writer.writerow([i, round(rng.gauss(100, 15), 2), rng.choice(["A", "B", "C"])])
        yield buffer.getvalue()


def panel():
    return _ui(MODULE_ID)


def server():
    _server(MODULE_ID)
