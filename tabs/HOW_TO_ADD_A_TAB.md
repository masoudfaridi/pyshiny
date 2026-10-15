# How to add a new tab

This guide walks through adding a tab (for example `tab_07`, "Reports") to the
dashboard and lists **every place that has to change**. For the theory behind
`@module.ui` / `@module.server` read [`MODULES.md`](MODULES.md); for ready-made
code to copy see [`examples/`](examples/README.md).

---

## 1. The short version (checklist)

| # | Where | What | Required? |
|---|-------|------|-----------|
| 1 | `tabs/tab_07.py` (new file) | Write the tab: `NAV_*` metadata, `_ui`, `_server`, `panel()`, `server()` | yes |
| 2 | `app.py` -> `from tabs import ...` | Import the new module | yes |
| 3 | `app.py` -> `TABS = [...]` | Add the module to the list (list order = sidebar order) | yes |
| 4 | `app.py` -> `def server(...)` | Call `tab_07.server()` once | yes (if the tab has any logic) |
| 5 | `app.py` -> `GROUPS = {...}` | Add a group, only if you use a brand-new `NAV_GROUP` | only for new groups |
| 6 | `app.py` -> `DEFAULT_TAB_ID` | Change the landing page | optional |
| 7 | `tests/test_tabs.py`, `tests/test_sidebar.py` -> `TAB_MODULES` | Add `"tabs.tab_07"` so the tests cover it | recommended |
| 8 | `i18n.py` | Add keys (or use a tab-local dictionary) | only if the tab must be bilingual |

Nothing else changes: not `static/`, not `auth/`, not the Dockerfile.

> The most common mistake is forgetting step 4. The tab then shows up in the
> sidebar and its layout appears, but buttons and outputs do nothing.

---

## 2. Step by step

### Step 1 -- create `tabs/tab_07.py`

Copy this minimal file (or any file from `tabs/examples/`) and change the
names:

```python
"""Tab 07 -- Reports."""

from __future__ import annotations

from shiny import module, reactive, render, ui

NAV_ID = "tab_07"            # unique in the whole app
NAV_LABEL = "Reports"        # text in the sidebar
NAV_ICON = "bi-file-earmark-text"
NAV_GROUP = None             # None = top level, "dashboard" = inside the Dashboard group
NAV_MIN_ROLE = "user"        # guest | user | admin | superadmin

MODULE_ID = "tab_07"         # prefix for all input/output ids of this tab


@module.ui
def _ui():
    # Use SHORT local ids ("name", "go", "result"). Never type "tab_07-" yourself.
    return ui.div(
        ui.h3("Reports"),
        ui.input_text("name", "Report name"),
        ui.input_action_button("go", "Create", class_="btn btn-primary"),
        ui.output_text("result"),
        class_="tab-pane-content",   # the CSS class every tab uses for padding
    )


@module.server
def _server(input, output, session):
    created = reactive.Value("")

    @reactive.effect
    @reactive.event(input.go)
    def _go():
        created.set(f"Created: {input.name()}")

    @render.text
    def result():
        return created()


def panel():
    """Called by app.py every time the tab is shown."""
    return _ui(MODULE_ID)


def server():
    """Called by app.py ONCE when a browser session starts."""
    _server(MODULE_ID)
```

#### The `NAV_*` constants

| Constant | Meaning | Notes |
|----------|---------|-------|
| `NAV_ID` | Unique id of the tab | Used by the sidebar (`data-nav-id`) and `TAB_LOOKUP`. Two tabs with the same id break navigation (a test checks this). |
| `NAV_LABEL` | Text in the sidebar | Plain string, or `t("key")` for a translated one. |
| `NAV_ICON` | A [Bootstrap Icons](https://icons.getbootstrap.com/) class such as `"bi-table"` | **Required for top-level tabs** (`NAV_GROUP = None`); optional (`None`) for tabs inside a group. |
| `NAV_GROUP` | `None` or a key of `GROUPS` in `app.py` | `None` = its own sidebar link. `"dashboard"` = inside the collapsible Dashboard group. An unknown key raises `KeyError` when the sidebar is built. |
| `NAV_MIN_ROLE` | Lowest role that can open the tab | `guest` < `user` < `admin` < `superadmin`. Hides the link **and** makes `active_panel` refuse the page. |
| `MODULE_ID` | Namespace prefix for ids | Keep it equal to `NAV_ID`; the module must be started with the same id it was drawn with. |

### Step 2 -- import the module in `app.py`

```python
# before
from tabs import tab_01, tab_02, tab_03, tab_04, tab_05, tab_06, tab_account, tab_users
# after
from tabs import tab_01, tab_02, tab_03, tab_04, tab_05, tab_06, tab_07, tab_account, tab_users
```

### Step 3 -- add it to `TABS`

```python
TABS = [tab_01, tab_02, tab_03, tab_04, tab_05, tab_06, tab_07, tab_account, tab_users]
```

The order of this list is the order of the sidebar. Put `tab_account` and
`tab_users` last to keep "My Account" and "User Management" at the bottom.

### Step 4 -- register the server part once

Inside `def server(input, output, session):` next to the other tabs:

```python
    tab_01.server()
    ...
    tab_06.server()
    tab_07.server()      # <-- add this line
```

Rules:

* Call it **once**, directly in `server()`.
* **Never** call it inside `active_panel`, a login handler, or a
  `@reactive.effect` -- it would be registered again on every click.
* If the tab needs to know who is logged in, pass the reactive:
  `tab_07.server(logged_in_user)` and declare `def server(session_user):` in the
  tab (see [`examples/ex14_role_aware.py`](examples/ex14_role_aware.py)).

### Step 5 -- (only for a new group) add it to `GROUPS`

```python
GROUPS = {
    "dashboard": {"label": t("nav_dashboard"), "icon": "bi-speedometer2"},
    "reports":   {"label": "Reports",          "icon": "bi-folder"},   # new
}
```

and set `NAV_GROUP = "reports"` in every tab that belongs to it. A group is
only a collapsible header; it is shown when at least one of its tabs is
visible to the current role. For a bilingual header add a key to `i18n.py` and
write `t("nav_reports")`.

### Step 6 -- (optional) change the landing page

```python
DEFAULT_TAB_ID = "tab_04"
```

The default tab must have `NAV_MIN_ROLE = "guest"`, otherwise lower roles land
on a page they cannot open (a test checks this for the current default).

### Step 7 -- add it to the tests

In both `tests/test_tabs.py` and `tests/test_sidebar.py`:

```python
TAB_MODULES = [
    "tabs.tab_01",
    ...
    "tabs.tab_07",      # <-- add
    "tabs.tab_account",
    "tabs.tab_users",
]
```

Then run `pytest`. The tests check unique ids, valid roles, and that
`panel()` builds.

### Step 8 -- (optional) make it bilingual

Two options, both shown in [`examples/ex15_bilingual.py`](examples/ex15_bilingual.py):

* **Tab-local dictionary** (simplest; nothing else to edit): keep a small
  `{"en": {...}, "fa": {...}}` in the tab file and pick with `APP_LANG`.
* **Shared dictionary**: add keys to *both* `"en"` and `"fa"` in `i18n.py`
  and use `t("key")`. `tests/test_i18n.py` will fail if one language is
  missing a key.

You never handle right-to-left yourself: `app.py` already sets `dir="rtl"` and
loads the RTL stylesheet when `APP_LANG = "fa"`.

---

## 3. Removing or hiding a tab

* **Hide it for some roles:** raise `NAV_MIN_ROLE`.
* **Remove it:** delete its import, its entry in `TABS`, its `server()` call and
  its entry in the tests' `TAB_MODULES`, then delete the file.

---

## 4. Two kinds of tabs in this project

| Kind | Files | Where is the server logic? |
|------|-------|----------------------------|
| **Module tabs** (`tab_01` ... `tab_06`, your new tabs) | one file each | inside the tab file, in `_server` |
| **Shell tabs** (`tab_account`, `tab_users`) | UI in the tab file | in `app.py`'s `server()`, because they change the session itself (passwords, users, logout) and use global ids such as `new_username` |

Build **your** tabs as module tabs. Only touch the shell tabs when you change
authentication or user management.

---

## 5. Common mistakes

| Symptom | Likely cause |
|---------|--------------|
| Tab is in the sidebar but buttons do nothing | Step 4 forgotten, or `server()` called with a different id than `panel()` |
| Everything works but runs twice per click | `server()` called more than once (e.g. inside `active_panel`) |
| `KeyError` when the sidebar loads | `NAV_GROUP` is not a key of `GROUPS` |
| Sidebar link shows no icon (or "bi None") | top-level tab without `NAV_ICON` |
| Two tabs open at once / wrong tab opens | duplicate `NAV_ID` |
| Output stays empty, no error | `ui.output_xxx("a")` and `def b()` do not share the same local id |
| `ValueError`/`NameError` from a reactive | a `@render` function reads an input id that is not in `_ui` |
| Guest can still trigger an action | the UI was hidden but the server code is not protected, see "RBAC inside modules" in [`MODULES.md`](MODULES.md) |
