# Shiny modules, explained

Every tab in this project is a **Shiny module**. This document explains what
that means, why it is used here, and how to work with it. Practical,
copy-ready code is in [`examples/`](examples/README.md); the list of places to
edit when you add a tab is in [`HOW_TO_ADD_A_TAB.md`](HOW_TO_ADD_A_TAB.md).

If you know R Shiny: `@module.ui` is `NS()` + a UI function, `@module.server`
is `moduleServer()`.

---

## 1. The problem modules solve

In Shiny, every input and output has an **id** and the whole page shares one id
space. Imagine two tabs that both have a "Generate" button:

```python
ui.input_action_button("generate", "Generate")   # tab 1
ui.input_action_button("generate", "Generate")   # tab 2  -> same id!
```

The browser now has two elements with the id `generate`; Shiny can only see one
of them and the other tab silently breaks. In a dashboard with many tabs you
would have to invent unique names by hand (`generate_tab1`, `generate_tab2` ...).

A **module** does that automatically: it puts a prefix (the *namespace*) in
front of every id inside it.

```
local id (what you write)   id in the browser (what Shiny sees)
generate                    tab_01-generate     <- in tab_01
generate                    tab_04-generate     <- in tab_04
```

So `tab_01.py` and `tab_04.py` can both use `"n"`, `"generate"`, `"summary"`
and `"hist"` without a clash. That is exactly what `tab_01` and `tab_04` do.

---

## 2. Anatomy of a module (the pattern used in every tab)

```python
from shiny import module, reactive, render, ui

MODULE_ID = "tab_01"

@module.ui                         # (A) the UI half
def _ui():
    return ui.div(
        ui.input_numeric("n", "Sample size", value=500),   # local id "n"
        ui.input_action_button("generate", "Generate"),    # local id "generate"
        ui.output_plot("hist"),                            # local id "hist"
    )

@module.server                     # (B) the server half
def _server(input, output, session):
    @reactive.effect
    @reactive.event(input.generate)    # really input["tab_01-generate"]
    def _go(): ...

    @render.plot
    def hist(): ...                    # really output "tab_01-hist"

def panel():                       # (C) used by app.py to DISPLAY the tab
    return _ui(MODULE_ID)

def server():                      # (D) used by app.py to START the logic
    _server(MODULE_ID)
```

| Part | What it is | Who calls it | When |
|------|-----------|--------------|------|
| `_ui` | UI factory with **local ids** | `panel()` | each time the tab is displayed |
| `_server` | logic for that UI; `input`, `output`, `session` are already **scoped** to the module | `server()` | once per browser session |
| `panel()` | tiny wrapper: `_ui(MODULE_ID)` | `app.py` -> `active_panel` | on every navigation |
| `server()` | tiny wrapper: `_server(MODULE_ID)` | `app.py` -> `server()` | once |

Two details that surprise newcomers:

1. **You pass the id when you *call* the function, not when you define it.**
   You write `def _ui():` but call `_ui("tab_01")`. The decorator adds the
   first argument for you. Any further arguments of your function follow the
   id: `_counter_ui("a", "Apples")` for `def _counter_ui(title)`.
2. **The same id must be used for `_ui` and `_server`.** `_ui("tab_01")` +
   `_server("tab_02")` produce ids that never meet, so the tab looks fine but
   does nothing.

---

## 3. How the ids are linked together

```
 _ui("tab_01")                              _server("tab_01")
 ------------------------------             ------------------------------
 ui.input_numeric("n", ...)    -> tab_01-n  <-  input.n()
 ui.input_action_button("generate") -> tab_01-generate <- input.generate
 ui.output_plot("hist")        -> tab_01-hist <-  @render.plot  def hist()
```

* **Inputs:** you create them in the UI with a local id and read them in the
  server with `input.<id>()`.
* **Outputs:** `ui.output_xxx("name")` in the UI is filled by
  `@render.xxx def name()` in the server. The function name *is* the id.
* **Ids created in the server** (inside `@render.ui`, `ui.modal_show(...)`,
  `ui.update_select(...)`) are namespaced automatically too.
* Ids may contain letters, digits and underscores. Avoid names that clash with
  Python/Shiny attributes of `input` (`input.name`, `input.value`) -- pick
  descriptive ones such as `person` or `entry`.

---

## 4. Lifecycle -- what runs when

```
browser opens page
  -> app.py server() runs
       -> tab_01.server() ... tab_06.server()     (every module server starts NOW, once)
user logs in
  -> active_panel runs -> tab.panel()             (UI of the chosen tab is drawn)
user clicks another sidebar link
  -> active_panel re-runs -> new tab.panel()      (server of that tab is already running)
```

Consequences:

* A module's **state** (`reactive.Value`) survives switching tabs. Go to
  another tab and back: the counter still has its value (the UI is redrawn
  from the current inputs).
* State is **per browser session**. Two users never share a `reactive.Value`.
  For data shared by everybody use a database or a module-level object.
* Module servers start **before login**. They cannot call `current_user()`;
  see section 7.
* Because `server()` runs once, never call it from `panel()` or from a handler.

---

## 5. The reactive building blocks you will use most

| Tool | Use it for | Example |
|------|-----------|---------|
| `input.x()` | read a control | `n = int(input.n())` |
| `@render.text / ui / plot / download` | produce an output that updates when the inputs it reads change | `ex02`, `ex05` |
| `reactive.Value` | state you set yourself | `count = reactive.Value(0)`; `count.set(count() + 1)` -> `ex03` |
| `@reactive.calc` | a computed value shared by several outputs, cached | `ex04`, `ex06` |
| `@reactive.effect` | run code for its side effect (no return value) | `ex08` |
| `@reactive.event(input.btn)` | make a calc/effect/render run **only** when `btn` is clicked | `ex03`, `ex11` |
| `reactive.isolate()` | read a value without depending on it | `ex12` |
| `reactive.invalidate_later(s)` | re-run after `s` seconds | `ex12` |
| `ui.update_*` | change an existing input from the server | `ex08` |
| `ui.notification_show`, `ui.modal_show` | toasts and popups | `ex11` |

Decorator order matters: `@reactive.effect` goes **above**
`@reactive.event(...)`, as in every tab here.

---

## 6. Modules inside modules (reusable components)

A module can use other modules. This is where modules pay off: write a
component once, use it many times, each copy independent.

```python
@module.ui
def _counter_ui(title): ...

@module.server
def _counter_server(input, output, session, step=1):
    count = reactive.Value(0)
    ...
    return count                      # servers can return values

@module.ui
def _ui():
    return ui.row(_counter_ui("a", "Apples"), _counter_ui("b", "Oranges"))

@module.server
def _server(input, output, session):
    a = _counter_server("a", step=1)
    b = _counter_server("b", step=5)
```

Ids nest: `tab_ex13-a-inc`, `tab_ex13-b-inc`. Full working code:
[`examples/ex13_nested_modules.py`](examples/ex13_nested_modules.py).

When a component is useful in several tabs, move it to its own file (for
example `tabs/components/counter.py`) and import it, instead of copying it.

---

## 7. Modules and security (RBAC)

`NAV_MIN_ROLE` hides the sidebar link and `active_panel` refuses to draw the
page for a lower role. That protects the **UI**. But module servers are
started for every session, before anybody logs in, so the server code itself
is not behind the role check. Therefore:

* Put sensitive actions (deleting data, exporting, changing settings) behind
  the `@admin` / `@superadmin` / `@user` decorators from the `auth` package.
* Those decorators need to know the current user. A module server cannot call
  `current_user()` on its own, so **pass the session's user in**:

```python
# app.py, inside server()
tab_08.server(logged_in_user)

# tabs/tab_08.py
@module.server
def _server(input, output, session, session_user):
    ...
    with user_context(session_user()):
        do_protected_thing()          # raises PermissionError for lower roles

def server(session_user):
    _server(MODULE_ID, session_user=session_user)
```

Working code: [`examples/ex14_role_aware.py`](examples/ex14_role_aware.py).

> **Better for sensitive actions:** `logged_in_user` is a cache of the user as
> it was at login; if an admin demotes or disables the account later, the cached
> role is stale. `tab_07` and `tab_logs` therefore receive a *function*,
> `_ensure_valid_session`, that re-reads the user from SQLite on every call:
> `tab_08.server(_ensure_valid_session)` and `def server(get_session_user): ...`
> with `person = get_session_user()` inside each callback. For a password
> confirmation before the callback, add `@confirm_with_password(input,
> get_session_user, message=...)` (see `tabs/tab_07.py` and
> [`../docs/confirm-with-password.md`](../docs/confirm-with-password.md)).

Other safety habits for every tab: validate numbers and sizes on the server
(never trust the browser), limit upload sizes (`ex09`), and never build SQL by
string concatenation (use `?` placeholders, as `auth/core.py` does).

---

## 8. Using pandas (optional)

`render.table` and `render.data_frame` need **pandas**, which is not in
`requirements.txt` because the stock tabs do not use it. If you want them:

```bash
pip install pandas
```

```python
import pandas as pd
from shiny import module, render, ui

@module.ui
def _ui():
    return ui.output_data_frame("grid")

@module.server
def _server(input, output, session):
    @render.data_frame
    def grid():
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        return render.DataGrid(df, filters=True)   # sortable / filterable grid
```

Add `pandas` to `requirements.txt` (or run
`python 01_requirements/update_requirements.py`). Without pandas, build small
tables by hand as in [`examples/ex06_html_table.py`](examples/ex06_html_table.py).

---

## 9. Testing a module

You can check a module without a browser:

```python
import importlib
mod = importlib.import_module("tabs.tab_08")
assert mod.panel() is not None          # the UI builds
```

`tests/test_tabs.py` and `tests/test_examples.py` do this for every tab.
Reactive logic is easiest to test if you keep the calculations in plain
functions (no Shiny) and call those from `@reactive.calc`:

```python
def bmi(weight_kg: float, height_cm: float) -> float:   # unit-testable
    return weight_kg / (height_cm / 100) ** 2
```

---

## 10. Glossary

| Term | Meaning |
|------|---------|
| Module | a UI function + a server function that share a namespace |
| Namespace / prefix | the `tab_01-` that is put in front of local ids |
| Local id | the short id you type inside a module (`"n"`) |
| Reactive | a value or function that re-runs when what it depends on changes |
| Session | one open browser tab; has its own reactive state |
| `reactive.Value` | a variable that notifies the things that read it |
| Render function | `@render.*` function that fills an `ui.output_*` placeholder |
