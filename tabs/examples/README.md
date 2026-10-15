# Module examples

Fifteen small, self-contained tabs. Each file is a complete module that follows
the contract used by `tab_01` ... `tab_06`, so you can **copy it into `tabs/`
and rename it** -- or just read it. Start with the guides:

* [`../HOW_TO_ADD_A_TAB.md`](../HOW_TO_ADD_A_TAB.md) -- what to change in the project
* [`../MODULES.md`](../MODULES.md) -- how modules work

The examples are *not* loaded by the app by default.

## The examples

| # | File | What it shows |
|---|------|---------------|
| 01 | `ex01_layout.py` | Minimal tab, Bootstrap grid, inner tabs, accordion; empty server |
| 02 | `ex02_text_io.py` | Text inputs -> `@render.text`; how `input.x()` maps to ids |
| 03 | `ex03_counter.py` | Buttons, `reactive.Value`, `@reactive.event` |
| 04 | `ex04_reactive_calc.py` | `@reactive.calc` shared by two outputs; sliders |
| 05 | `ex05_plot.py` | matplotlib figure with `@render.plot` |
| 06 | `ex06_html_table.py` | Filter + sort a table without pandas |
| 07 | `ex07_dynamic_ui.py` | `@render.ui` returning different inputs |
| 08 | `ex08_update_inputs.py` | Dependent dropdowns with `ui.update_select` |
| 09 | `ex09_upload_csv.py` | `ui.input_file`, safe CSV parsing, preview |
| 10 | `ex10_download_csv.py` | `ui.download_button` + `@render.download` |
| 11 | `ex11_notify_modal.py` | Toast notifications and a confirmation popup |
| 12 | `ex12_auto_refresh.py` | `invalidate_later` + `isolate` for live content |
| 13 | `ex13_nested_modules.py` | One module used three times; returning values from a sub-module |
| 14 | `ex14_role_aware.py` | Passing the logged-in user into a module; `@admin` inside a module (needs one extra change in `app.py`) |
| 15 | `ex15_bilingual.py` | English/Persian tab using `APP_LANG` |

Suggested reading order: 01 -> 02 -> 03 -> 04 -> 05, then pick what you need.

## Use an example as the base of a real tab

1. Copy the file: `cp tabs/examples/ex03_counter.py tabs/tab_07.py`
2. In the new file change `NAV_ID`, `MODULE_ID` (keep them equal), `NAV_LABEL`,
   `NAV_ICON`, and `NAV_MIN_ROLE`.
3. Follow steps 2-4 of [`HOW_TO_ADD_A_TAB.md`](../HOW_TO_ADD_A_TAB.md)
   (import, `TABS`, `server()` call).

## Try an example without copying it

In `app.py`:

```python
# 1. import
from tabs.examples import ex03_counter

# 2. add to TABS
TABS = [tab_01, ..., tab_users, ex03_counter]

# 3. inside server(), next to the other tab.server() calls
ex03_counter.server()
```

Restart the app and the example appears in the sidebar (all examples use
top-level links with unique ids `tab_ex01` ... `tab_ex15`, so you can add as
many as you like at once). Remove the three lines again when you are done.

`ex14_role_aware` takes the session's user: use
`ex14_role_aware.server(logged_in_user)`.

## Notes

* The examples need only the packages already in `requirements.txt`
  (shiny, numpy, matplotlib). None of them needs pandas.
* `tests/test_examples.py` checks that all examples keep the tab contract.
* Sample data in the examples is invented; replace it with your own source.
