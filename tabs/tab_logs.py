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

Settings and clean-up (second sub-tab) follow the same rule: saving the
retention settings and deleting log rows go through ``@superadmin`` functions in
``auth.core``; deleting always asks for a confirmation click first, and the
deletion itself is recorded afterwards in the Security log.

CSV export: ``render.download`` is deprecated in recent Shiny releases and the
replacement API differs between versions, so the export is a plain
``<a download href="data:text/csv...">`` link produced by ``render.ui``. The CSV
text is built on the server through the same ``@superadmin``-guarded read as the
tables, so a denied / signed-out request gets no link at all.

Cell values are plain strings, so htmltools escapes them (attacker-controlled
text such as a typed login name cannot inject HTML). The CSV export prefixes
cells that start with ``= + - @`` so spreadsheets do not run them as formulas.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from urllib.parse import quote

from shiny import module, reactive, render, ui

from auth import (
    audit_log_counts,
    clear_audit_logs,
    get_audit_settings,
    list_audit_events,
    update_audit_settings,
    user_context,
)
from auth.audit import SETTING_LIMITS
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
        "section_events": "Events",
        "section_settings": "Settings",
        "settings_title": "Retention settings",
        "settings_intro": (
            "Old events are deleted automatically. Choose how long each log is "
            "kept and how often the automatic clean-up may run."
        ),
        "ret_navigation": "Navigation log: keep (days)",
        "ret_auth": "Authentication log: keep (days)",
        "ret_security": "Security log: keep (days)",
        "purge_interval": "Automatic clean-up at most once every (hours)",
        "save_settings": "Save settings",
        "settings_saved": "Settings saved.",
        "settings_invalid": "Invalid values. Days: 1-3650, hours: 1-168.",
        "cleanup_title": "Clean up logs",
        "cleanup_intro": (
            "Deleting cannot be undone. The deletion itself is recorded in the "
            "Security log."
        ),
        "stored_rows": "Stored rows",
        "clear_navigation": "Clear navigation log",
        "clear_auth": "Clear authentication log",
        "clear_security": "Clear security log",
        "clear_all": "Clear ALL logs",
        "confirm_navigation": "Delete the whole navigation log?",
        "confirm_auth": "Delete the whole authentication log?",
        "confirm_security": "Delete the whole security log?",
        "confirm_all": "Delete ALL logs (navigation, authentication and security)?",
        "confirm_yes": "Yes, delete",
        "confirm_no": "Cancel",
        "cleared": "Deleted rows: ",
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
        "section_events": "رویدادها",
        "section_settings": "تنظیمات",
        "settings_title": "تنظیمات نگهداری",
        "settings_intro": (
            "رویدادهای قدیمی به‌صورت خودکار پاک می‌شوند. مشخص کنید هر لاگ چند "
            "روز نگهداری شود و پاکسازی خودکار حداکثر هر چند ساعت یک بار اجرا شود."
        ),
        "ret_navigation": "لاگ ناوبری: نگهداری (روز)",
        "ret_auth": "لاگ احراز هویت: نگهداری (روز)",
        "ret_security": "لاگ امنیتی: نگهداری (روز)",
        "purge_interval": "پاکسازی خودکار حداکثر هر (ساعت) یک بار",
        "save_settings": "ذخیره تنظیمات",
        "settings_saved": "تنظیمات ذخیره شد.",
        "settings_invalid": "مقادیر نامعتبر است. روز: ۱ تا ۳۶۵۰، ساعت: ۱ تا ۱۶۸.",
        "cleanup_title": "پاکسازی لاگ‌ها",
        "cleanup_intro": (
            "حذف قابل بازگشت نیست. خود عملیات حذف در لاگ امنیتی ثبت می‌شود."
        ),
        "stored_rows": "ردیف‌های ذخیره‌شده",
        "clear_navigation": "پاک کردن لاگ ناوبری",
        "clear_auth": "پاک کردن لاگ احراز هویت",
        "clear_security": "پاک کردن لاگ امنیتی",
        "clear_all": "پاک کردن همه لاگ‌ها",
        "confirm_navigation": "کل لاگ ناوبری حذف شود؟",
        "confirm_auth": "کل لاگ احراز هویت حذف شود؟",
        "confirm_security": "کل لاگ امنیتی حذف شود؟",
        "confirm_all": "همه لاگ‌ها (ناوبری، احراز هویت و امنیتی) حذف شود؟",
        "confirm_yes": "بله، حذف شود",
        "confirm_no": "انصراف",
        "cleared": "تعداد ردیف‌های حذف‌شده: ",
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


def _csv_href(csv_text: str) -> str:
    """Data URI for a CSV download link (UTF-8 BOM so Excel reads non-ASCII)."""
    return "data:text/csv;charset=utf-8," + quote("\ufeff" + csv_text, safe="")


def _limit_value(raw) -> int:
    try:
        return max(1, min(int(raw), 1000))
    except (TypeError, ValueError):
        return 100


# --------------------------------- UI ---------------------------------------
def _events_panel():
    """Filter bar + the three category tables."""
    return ui.div(
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
                ui.output_ui("download_link", inline=True),
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
    )


def _settings_panel():
    """Retention settings + clean-up buttons (every action is server-guarded)."""
    return ui.div(
        ui.div(
            ui.h5(_tx("settings_title")),
            ui.p(_tx("settings_intro"), class_="text-muted"),
            ui.output_ui("settings_form"),
            ui.div(
                ui.input_action_button(
                    "save_settings", _tx("save_settings"), class_="btn btn-primary"
                ),
                class_="log-actions mt-3",
            ),
            class_="user-form-card mb-3",
        ),
        ui.div(
            ui.h5(_tx("cleanup_title")),
            ui.p(_tx("cleanup_intro"), class_="text-muted"),
            ui.output_ui("log_counts"),
            ui.div(
                ui.input_action_button(
                    "clear_navigation", _tx("clear_navigation"), class_="btn btn-outline-danger"
                ),
                ui.input_action_button(
                    "clear_auth", _tx("clear_auth"), class_="btn btn-outline-danger"
                ),
                ui.input_action_button(
                    "clear_security", _tx("clear_security"), class_="btn btn-outline-danger"
                ),
                ui.input_action_button(
                    "clear_all", _tx("clear_all"), class_="btn btn-danger"
                ),
                class_="log-actions mt-2",
            ),
            ui.output_ui("confirm_bar"),
            class_="user-form-card",
        ),
    )


@module.ui
def _ui():
    return ui.div(
        ui.h3(_tx("title")),
        ui.p(_tx("intro")),
        ui.navset_pill(
            ui.nav_panel(_tx("section_events"), _events_panel(), value="events"),
            ui.nav_panel(_tx("section_settings"), _settings_panel(), value="settings"),
            id="section",
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

    settings_rev = reactive.Value(0)  # bump to re-read the saved settings
    pending = reactive.Value(None)  # clear-confirmation: None | category | "all"

    def _guarded(function, *args):
        """Run a ``@superadmin`` function as the re-validated user.

        Returns ``(result, error_key)`` with error_key in
        ``None | "signin" | "denied" | "invalid"``.
        """
        person = get_session_user()
        if person is None:
            return None, "signin"
        try:
            with user_context(person):
                return function(*args), None
        except PermissionError:
            return None, "denied"
        except ValueError:
            return None, "invalid"

    def _toast(message_key: str, kind: str = "message", suffix: str = ""):
        if message_key == "invalid":
            message_key = "settings_invalid"
        ui.notification_show(_tx(message_key) + suffix, type=kind, duration=5)

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

    # ---------------------- settings (retention) ----------------------------
    @render.ui
    def settings_form():
        settings_rev()
        settings, error = _guarded(get_audit_settings)
        if error:
            return ui.div(_tx(error), class_="login-error")

        def number(input_id, label_key, setting):
            low, high = SETTING_LIMITS[setting]
            return ui.div(
                ui.input_numeric(
                    input_id, _tx(label_key), settings[setting],
                    min=low, max=high, step=1, width="100%",
                ),
                class_="log-field",
            )

        return ui.div(
            number("ret_navigation", "ret_navigation", "retention_days_navigation"),
            number("ret_auth", "ret_auth", "retention_days_auth"),
            number("ret_security", "ret_security", "retention_days_security"),
            number("purge_interval", "purge_interval", "purge_interval_hours"),
            class_="log-filters",
        )

    @reactive.effect
    @reactive.event(input.save_settings)
    def _on_save_settings():
        values = {
            "retention_days_navigation": input.ret_navigation(),
            "retention_days_auth": input.ret_auth(),
            "retention_days_security": input.ret_security(),
            "purge_interval_hours": input.purge_interval(),
        }
        _, error = _guarded(update_audit_settings, values)
        if error:
            _toast(error, "error")
            return
        settings_rev.set(settings_rev() + 1)
        _toast("settings_saved")

    # ---------------------- clean-up (always confirmed) ---------------------
    @render.ui
    def log_counts():
        refresh()
        counts, error = _guarded(audit_log_counts)
        if error:
            return ui.div(_tx(error), class_="login-error")
        return ui.p(
            f"{_tx('stored_rows')}: "
            f"{_tx('cat_navigation')} {counts['navigation']} \u00b7 "
            f"{_tx('cat_auth')} {counts['auth']} \u00b7 "
            f"{_tx('cat_security')} {counts['security']}",
            class_="mb-1",
        )

    @reactive.effect
    @reactive.event(input.clear_navigation)
    def _ask_navigation():
        pending.set("navigation")

    @reactive.effect
    @reactive.event(input.clear_auth)
    def _ask_auth():
        pending.set("auth")

    @reactive.effect
    @reactive.event(input.clear_security)
    def _ask_security():
        pending.set("security")

    @reactive.effect
    @reactive.event(input.clear_all)
    def _ask_all():
        pending.set("all")

    @reactive.effect
    @reactive.event(input.cancel_clear)
    def _cancel_clear():
        pending.set(None)

    @render.ui
    def confirm_bar():
        target = pending()
        if target is None:
            return ui.div()
        return ui.div(
            ui.span(_tx(f"confirm_{target}"), class_="me-3 fw-bold"),
            ui.input_action_button(
                "confirm_clear", _tx("confirm_yes"), class_="btn btn-danger me-2"
            ),
            ui.input_action_button(
                "cancel_clear", _tx("confirm_no"), class_="btn btn-secondary"
            ),
            class_="log-actions mt-3",
        )

    @reactive.effect
    @reactive.event(input.confirm_clear)
    def _on_confirm_clear():
        target = pending()
        if target is None:
            return
        pending.set(None)
        deleted, error = _guarded(clear_audit_logs, None if target == "all" else target)
        if error:
            _toast(error, "error")
            return
        refresh.set(refresh() + 1)  # tables and counters re-read the database
        _toast("cleared", "message", str(deleted))

    # ---------------------- event tables ------------------------------------
    @render.ui
    def table_auth():
        return _table("auth")

    @render.ui
    def table_navigation():
        return _table("navigation")

    @render.ui
    def table_security():
        return _table("security")

    @render.ui
    def download_link():
        category = input.cat() or "auth"
        rows, error = _fetch(category)
        if error or not rows:
            return ui.tags.span()  # nothing to export (or not allowed): no link
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        return ui.tags.a(
            _tx("download"),
            href=_csv_href(_rows_to_csv(rows)),
            download=f"audit-{category}-{stamp}.csv",
            class_="btn btn-secondary",
        )


def panel():
    """Called by app.py every time the tab is shown."""
    return _ui(MODULE_ID)


def server(get_session_user):
    """Register once from app.py: ``tab_logs.server(_ensure_valid_session)``."""
    _server(MODULE_ID, get_session_user=get_session_user)
