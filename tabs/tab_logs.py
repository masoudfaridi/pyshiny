"""
Logs tab -- audit log viewer (superadmin only, last tab in the sidebar).

Protection uses BOTH layers:

1. UI: ``NAV_MIN_ROLE = "superadmin"`` hides the link and makes
   ``active_panel`` refuse the page for every other role.
2. Server: every read goes through ``auth.list_audit_events``, which is
   decorated with ``@superadmin``. The module server runs for every session
   (even before login), so a forged ``tab_logs-...`` input from a lower role
   reaches the decorator and gets ``PermissionError`` (and the attempt is
   written to the Security log by the decorator itself).

The user is passed in as a function (``_ensure_valid_session`` from app.py) that
re-checks the account in SQLite on every render / download.

Cell values are plain strings, so htmltools escapes them (attacker-controlled
text such as a typed login name cannot inject HTML). The CSV export prefixes
cells that start with ``= + - @`` so spreadsheets do not run them as formulas.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

from shiny import module, reactive, render, ui

from auth import list_audit_events, user_context
from i18n import APP_LANG

NAV_ID = "tab_logs"
NAV_ICON = "bi-journal-text"
NAV_GROUP = None
NAV_MIN_ROLE = "superadmin"

MODULE_ID = "tab_logs"

_TEXTS = {
    "en": {
        "label": "Logs",
        "title": "Audit logs",
        "intro": (
            "Events of all accounts, superadmin included. "
            "Times are UTC, newest first."
        ),
        "cat_auth": "Authentication",
        "cat_navigation": "Navigation",
        "cat_security": "Security",
        "severity": "Severity",
        "all": "All",
        "info": "Info",
        "warning": "Warning",
        "critical": "Critical",
        "username": "Username",
        "limit": "Rows",
        "refresh": "Refresh",
        "download": "Download CSV",
        "col_time": "Time (UTC)",
        "col_event": "Event",
        "col_severity": "Severity",
        "col_user": "Username",
        "col_role": "Role",
        "col_ip": "IP",
        "col_session": "Session",
        "col_detail": "Details",
        "empty": "No events match the filters.",
        "denied": "You do not have access to this section.",
        "signin": "Your session is no longer valid. Please sign in again.",
    },
    "fa": {
        "label": "لاگ‌ها",
        "title": "لاگ رویدادها",
        "intro": (
            "رویدادهای همه حساب‌ها، از جمله سوپر ادمین. "
            "زمان‌ها به وقت UTC و جدیدترین‌ها در بالا هستند."
        ),
        "cat_auth": "احراز هویت",
        "cat_navigation": "ناوبری",
        "cat_security": "امنیتی",
        "severity": "شدت",
        "all": "همه",
        "info": "اطلاعات",
        "warning": "هشدار",
        "critical": "بحرانی",
        "username": "نام کاربری",
        "limit": "تعداد ردیف",
        "refresh": "تازه‌سازی",
        "download": "دانلود CSV",
        "col_time": "زمان (UTC)",
        "col_event": "رویداد",
        "col_severity": "شدت",
        "col_user": "نام کاربری",
        "col_role": "نقش",
        "col_ip": "IP",
        "col_session": "نشست",
        "col_detail": "جزئیات",
        "empty": "رویدادی با این فیلترها پیدا نشد.",
        "denied": "دسترسی به این بخش برای شما مقدور نیست.",
        "signin": "نشست شما دیگر معتبر نیست. لطفاً دوباره وارد شوید.",
    },
}


def _tx(key: str) -> str:
    return _TEXTS.get(APP_LANG, _TEXTS["en"]).get(key, _TEXTS["en"][key])


NAV_LABEL = _tx("label")

_COLUMNS = ("time", "event", "severity", "user", "role", "ip", "session", "detail")
_BADGE = {
    "info": "badge bg-secondary",
    "warning": "badge bg-warning text-dark",
    "critical": "badge bg-danger",
}


# --------------------------- plain helpers (unit-testable) -------------------
def _detail_text(raw: str | None) -> str:
    """Turn the stored JSON into a compact ``key=value; key=value`` string."""
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except ValueError:
        return str(raw)
    if not isinstance(data, dict):
        return str(data)
    parts = []
    for key, value in data.items():
        if isinstance(value, dict):
            value = ", ".join(f"{k}: {v[0]} -> {v[1]}" if isinstance(v, list) and len(v) == 2
                              else f"{k}: {v}" for k, v in value.items())
        parts.append(f"{key}={value}")
    return "; ".join(parts)


def _csv_safe(value) -> str:
    """Neutralise spreadsheet formulas (CSV injection)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _rows_to_csv(rows: list[dict]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        ["id", "time_utc", "category", "event", "severity", "username",
         "role", "ip", "session_id", "user_agent", "detail"]
    )
    for r in rows:
        writer.writerow(
            [_csv_safe(r.get(k)) for k in
             ("id", "ts", "category", "event", "severity", "username",
              "role", "ip", "session_id", "user_agent")]
            + [_csv_safe(_detail_text(r.get("detail")))]
        )
    return out.getvalue()


def _limit_value(raw) -> int:
    try:
        return max(1, min(int(raw), 1000))
    except (TypeError, ValueError):
        return 100


# --------------------------------- UI ---------------------------------------
@module.ui
def _ui():
    return ui.div(
        ui.h3(_tx("title")),
        ui.p(_tx("intro")),
        # One flex row: equal-height fields, labels on one line, buttons aligned
        # with the bottom of the inputs. Styles: ".log-filters" in styles.css.
        ui.div(
            ui.div(
                ui.input_select(
                    "severity",
                    _tx("severity"),
                    {
                        "": _tx("all"),
                        "info": _tx("info"),
                        "warning": _tx("warning"),
                        "critical": _tx("critical"),
                    },
                    width="100%",
                ),
                class_="log-field",
            ),
            ui.div(
                ui.input_text("username", _tx("username"), width="100%"),
                class_="log-field",
            ),
            ui.div(
                ui.input_select(
                    "limit",
                    _tx("limit"),
                    {"100": "100", "250": "250", "500": "500", "1000": "1000"},
                    width="100%",
                ),
                class_="log-field log-field-narrow",
            ),
            ui.div(
                ui.input_action_button(
                    "refresh_btn", _tx("refresh"), class_="btn btn-primary"
                ),
                ui.download_button(
                    "download_csv", _tx("download"), class_="btn btn-secondary"
                ),
                class_="log-actions",
            ),
            class_="user-form-card log-filters mb-3",
        ),
        ui.navset_tab(
            ui.nav_panel(_tx("cat_auth"), ui.output_ui("table_auth"), value="auth"),
            ui.nav_panel(
                _tx("cat_navigation"), ui.output_ui("table_navigation"), value="navigation"
            ),
            ui.nav_panel(_tx("cat_security"), ui.output_ui("table_security"), value="security"),
            id="cat",
        ),
        class_="tab-pane-content",
    )


# ------------------------------- server -------------------------------------
@module.server
def _server(input, output, session, get_session_user):
    """``get_session_user`` returns the re-validated user dict, or None."""
    refresh = reactive.Value(0)

    @reactive.effect
    @reactive.event(input.refresh_btn)
    def _on_refresh():
        refresh.set(refresh() + 1)

    def _fetch(category: str):
        """Return (rows, error_key). The decorator is the real access check."""
        refresh()  # re-run when Refresh is pressed
        person = get_session_user()
        if person is None:
            return None, "signin"
        try:
            with user_context(person):
                rows = list_audit_events(
                    category=category,
                    severity=input.severity() or None,
                    username=input.username() or None,
                    limit=_limit_value(input.limit()),
                )
        except PermissionError:
            return None, "denied"
        return rows, None

    def _table(category: str):
        rows, error = _fetch(category)
        if error:
            return ui.div(_tx(error), class_="login-error")
        if not rows:
            return ui.p(_tx("empty"), class_="text-muted mt-3")

        header = ui.tags.tr(*[ui.tags.th(_tx(f"col_{c}")) for c in _COLUMNS])
        body = []
        for r in rows:
            body.append(
                ui.tags.tr(
                    ui.tags.td(r["ts"]),
                    ui.tags.td(r["event"]),
                    ui.tags.td(
                        ui.tags.span(
                            _tx(r["severity"]), class_=_BADGE.get(r["severity"], "badge")
                        )
                    ),
                    ui.tags.td(r["username"] or ""),
                    ui.tags.td(r["role"] or ""),
                    ui.tags.td(r["ip"] or ""),
                    ui.tags.td((r["session_id"] or "")[:8]),
                    ui.tags.td(_detail_text(r["detail"])),
                )
            )
        return ui.div(
            ui.tags.table(header, *body, class_="users-table"),
            style="overflow-x:auto;",
            class_="mt-3",
        )

    @render.ui
    def table_auth():
        return _table("auth")

    @render.ui
    def table_navigation():
        return _table("navigation")

    @render.ui
    def table_security():
        return _table("security")

    @render.download(
        filename=lambda: f"audit-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.csv"
    )
    def download_csv():
        with reactive.isolate():  # download handlers are not reactive contexts
            rows, error = _fetch(input.cat() or "auth")
        # A denied / signed-out request downloads an empty file, never the log.
        yield _rows_to_csv(rows if not error else [])


def panel():
    """Called by app.py every time the tab is shown."""
    return _ui(MODULE_ID)


def server(get_session_user):
    """Register once from app.py: ``tab_logs.server(_ensure_valid_session)``."""
    _server(MODULE_ID, get_session_user=get_session_user)
