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
``auth.core``. Both are additionally wrapped in ``@confirm_with_password``: a
confirmation dialog first, then the signed-in user's own password, and only then
does the action run. The deletion itself is recorded afterwards in the Security
log. The total size of all logs (``db/audit.db``, in MB) is shown next to the
row counters.

User behaviour (third sub-tab, "User behaviour analysis"): how often each account
signed in and for how many minutes it used the application, per user and overall,
with filters for period, user, role, category (authentication / navigation /
security) and severity. The numbers come from ``auth.audit_analytics``
(``@superadmin``). Logs backup / restore (Settings sub-tab) uses
``auth.log_backup``; automatic clean-up first backs the logs up into
``db/log_backups/auto/``.

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

import base64
import csv
import io
import json
from datetime import datetime, timezone
from urllib.parse import quote

from pathlib import Path

from shiny.types import SilentException
from shiny import module, reactive, render, ui

from auth import (
    audit_analytics,
    audit_known_users,
    audit_log_counts,
    audit_log_size_mb,
    clear_audit_logs,
    confirm_with_password,
    create_log_backup,
    delete_log_backup,
    get_audit_settings,
    import_log_backup,
    list_audit_events,
    list_log_backups,
    log_backup,
    log_backup_stats,
    read_log_backup,
    restore_log_backup,
    update_audit_settings,
    user_context,
)
from auth.audit import SETTING_LIMITS
from auth.backup import MAX_IMPORT_BYTES, format_size
from i18n import APP_LANG, role_label, t

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
        "section_analytics": "User behaviour analysis",
        "purge_backup_enabled": "Back up the logs before each automatic purge",
        "purge_backup_keep": "Automatic backups to keep",
        "purge_backup_note": (
            "Automatic backups are saved in db/log_backups/auto/ right before old rows "
            "are deleted. If the backup fails, nothing is deleted."
        ),
        "size_banner": "Total size of all logs",
        "size_banner_rows": "rows",
        # ---- logs database backup / restore ----
        "lb_title": "Logs database backup",
        "lb_intro": (
            "All logs are stored in one database file (db/audit.db). Save copies of it and "
            "load them back later. Restoring replaces ALL current log rows (a safety copy is "
            "made first; the retention settings stay). Files are stored in db/log_backups/; "
            "automatic pre-purge copies are in db/log_backups/auto/."
        ),
        "lb_stats": "Stored log backups",
        "lb_create": "Create backup now",
        "lb_created": "Backup created: ",
        "lb_upload": "Load a backup file (.db)",
        "lb_import": "Load file",
        "lb_imported": "File loaded as backup: ",
        "lb_no_file": "Choose a backup file first.",
        "lb_none": "No log backups yet.",
        "lb_col_file": "File",
        "lb_col_created": "Created (UTC)",
        "lb_col_size": "Size",
        "lb_col_type": "Type",
        "lb_col_actions": "Actions",
        "lb_type_manual": "Manual",
        "lb_type_auto": "Automatic (before purge)",
        "lb_type_prerestore": "Before restore",
        "lb_type_uploaded": "Loaded file",
        "lb_restore": "Restore",
        "lb_download": "Download",
        "lb_delete": "Delete",
        "lb_restored": "Logs restored. Rows: ",
        "lb_deleted": "Backup deleted.",
        "lb_confirm_restore": "Replace ALL current logs with this backup? A safety copy is made first.",
        "lb_confirm_delete": "Delete this backup file? This cannot be undone.",
        "lb_confirm_download": "Download this backup?",
        "lb_confirm_import": "Load the selected file as a new log backup?",
        "lb_download_title": "Download ready",
        "lb_download_text": "Your backup file is ready:",
        "lb_close": "Close",
        "lb_too_big": "The backup is too large to download here (max 20 MB).",
        # ---- analytics ----
        "an_title": "User behaviour analysis",
        "an_intro": (
            "How often each account signed in and for how many minutes it used the "
            "application. Minutes are counted when a session ends (sign-out, closed "
            "browser or revoked session)."
        ),
        "an_period": "Period",
        "an_p_24h": "Last 24 hours",
        "an_p_7d": "Last 7 days",
        "an_p_30d": "Last 30 days",
        "an_p_90d": "Last 90 days",
        "an_p_all": "All stored logs",
        "an_p_custom": "Custom dates",
        "an_dates": "Custom dates (used with \"Custom dates\")",
        "an_user": "User",
        "an_all_users": "All users (overall)",
        "an_role": "Role",
        "an_all_roles": "All roles",
        "an_categories": "Log types",
        "an_severity": "Severity",
        "an_apply": "Show",
        "an_none": "No activity found for these filters.",
        "an_no_category": "Select at least one log type.",
        "an_range": "Time zone used for dates and hours",
        "an_summary": "Overall summary",
        "an_users": "Per user",
        "an_c_users": "Active users",
        "an_c_logins": "Logins",
        "an_c_failed": "Failed logins",
        "an_c_minutes": "Total usage (min)",
        "an_c_avg": "Avg. session (min)",
        "an_c_longest": "Longest session (min)",
        "an_c_avg_user": "Avg. usage per user (min)",
        "an_c_sessions": "Measured sessions",
        "an_c_tabs": "Page views",
        "an_c_events": "Events",
        "an_c_alerts": "Warnings / critical",
        "an_failed_unknown": "of which unknown names",
        "an_col_user": "User",
        "an_col_role": "Role",
        "an_col_logins": "Logins",
        "an_col_failed": "Failed",
        "an_col_minutes": "Total (min)",
        "an_col_avg": "Avg session (min)",
        "an_col_longest": "Longest (min)",
        "an_col_tabs": "Page views",
        "an_col_top_tab": "Most used page",
        "an_col_days": "Active days",
        "an_col_alerts": "Alerts",
        "an_col_last_login": "Last login",
        "an_col_last_seen": "Last activity",
        "an_ch_category": "Events by log type",
        "an_ch_hour": "Activity by hour of day",
        "an_ch_weekday": "Activity by weekday",
        "an_ch_day": "Activity per day",
        "an_ch_tabs": "Most visited pages",
        "an_ch_events": "Most frequent events",
        "an_ch_failed": "Failed-login reasons",
        "an_export": "Download per-user table (CSV)",
        "an_note_sessions": "Sessions that are still open are counted once they end.",
        "weekdays": "Sun,Mon,Tue,Wed,Thu,Fri,Sat",
        "weekday_order": "1,2,3,4,5,6,0",
        "stored_rows": "Stored rows",
        "log_size": "Total size of all logs",
        "mb": "MB",
        "confirm_settings": "Save the new log retention settings?",
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
        "section_analytics": "تحلیل رفتار کاربران",
        "purge_backup_enabled": "پیش از هر پاکسازی خودکار از لاگ‌ها بکاپ گرفته شود",
        "purge_backup_keep": "تعداد بکاپ‌های خودکار نگهداری‌شده",
        "purge_backup_note": (
            "بکاپ‌های خودکار دقیقاً پیش از حذف ردیف‌های قدیمی در پوشه‌ی "
            "db/log_backups/auto/ ذخیره می‌شوند. اگر بکاپ ناموفق باشد، چیزی حذف نمی‌شود."
        ),
        "size_banner": "حجم کل لاگ‌ها",
        "size_banner_rows": "ردیف",
        # ---- پشتیبان‌گیری و بارگذاری دیتابیس لاگ‌ها ----
        "lb_title": "پشتیبان‌گیری از دیتابیس لاگ‌ها",
        "lb_intro": (
            "همه‌ی لاگ‌ها در یک فایل دیتابیس (db/audit.db) ذخیره می‌شوند. از آن نسخه‌ی "
            "پشتیبان بگیرید و بعداً دوباره بارگذاری کنید. بازنشانی «همه» ردیف‌های فعلی لاگ را "
            "جایگزین می‌کند (پیش از آن نسخه‌ی ایمنی ساخته می‌شود و تنظیمات نگهداری تغییر نمی‌کند). "
            "فایل‌ها در db/log_backups/ و نسخه‌های خودکارِ پیش از پاکسازی در "
            "db/log_backups/auto/ ذخیره می‌شوند."
        ),
        "lb_stats": "بکاپ‌های ذخیره‌شده‌ی لاگ",
        "lb_create": "ساخت بکاپ",
        "lb_created": "بکاپ ساخته شد: ",
        "lb_upload": "بارگذاری فایل بکاپ (.db)",
        "lb_import": "بارگذاری فایل",
        "lb_imported": "فایل به‌عنوان بکاپ بارگذاری شد: ",
        "lb_no_file": "ابتدا یک فایل بکاپ انتخاب کنید.",
        "lb_none": "هنوز بکاپی از لاگ‌ها وجود ندارد.",
        "lb_col_file": "فایل",
        "lb_col_created": "زمان ساخت (UTC)",
        "lb_col_size": "حجم",
        "lb_col_type": "نوع",
        "lb_col_actions": "عملیات",
        "lb_type_manual": "دستی",
        "lb_type_auto": "خودکار (پیش از پاکسازی)",
        "lb_type_prerestore": "پیش از بازنشانی",
        "lb_type_uploaded": "فایل بارگذاری‌شده",
        "lb_restore": "بازنشانی",
        "lb_download": "دانلود",
        "lb_delete": "حذف",
        "lb_restored": "لاگ‌ها بازنشانی شدند. تعداد ردیف‌ها: ",
        "lb_deleted": "بکاپ حذف شد.",
        "lb_confirm_restore": "همه‌ی لاگ‌های فعلی با این بکاپ جایگزین شوند؟ پیش از آن نسخه‌ی ایمنی ساخته می‌شود.",
        "lb_confirm_delete": "این فایل بکاپ حذف شود؟ این کار قابل بازگشت نیست.",
        "lb_confirm_download": "این بکاپ دانلود شود؟",
        "lb_confirm_import": "فایل انتخاب‌شده به‌عنوان بکاپ جدید بارگذاری شود؟",
        "lb_download_title": "دانلود آماده است",
        "lb_download_text": "فایل بکاپ شما آماده است:",
        "lb_close": "بستن",
        "lb_too_big": "حجم این بکاپ برای دانلود از اینجا زیاد است (حداکثر ۲۰ مگابایت).",
        # ---- تحلیل رفتار ----
        "an_title": "تحلیل رفتار کاربران",
        "an_intro": (
            "هر حساب چند بار وارد شده و در مجموع چند دقیقه از برنامه استفاده کرده است. "
            "دقایق استفاده هنگام پایان نشست (خروج، بستن مرورگر یا ابطال نشست) محاسبه می‌شود."
        ),
        "an_period": "بازه‌ی زمانی",
        "an_p_24h": "۲۴ ساعت گذشته",
        "an_p_7d": "۷ روز گذشته",
        "an_p_30d": "۳۰ روز گذشته",
        "an_p_90d": "۹۰ روز گذشته",
        "an_p_all": "همه‌ی لاگ‌های ذخیره‌شده",
        "an_p_custom": "تاریخ دلخواه",
        "an_dates": "تاریخ دلخواه (همراه با گزینه‌ی «تاریخ دلخواه»)",
        "an_user": "کاربر",
        "an_all_users": "همه‌ی کاربران (کلی)",
        "an_role": "نقش",
        "an_all_roles": "همه‌ی نقش‌ها",
        "an_categories": "نوع لاگ",
        "an_severity": "شدت",
        "an_apply": "نمایش",
        "an_none": "برای این فیلترها فعالیتی پیدا نشد.",
        "an_no_category": "دست‌کم یک نوع لاگ را انتخاب کنید.",
        "an_range": "منطقه‌ی زمانی تاریخ‌ها و ساعت‌ها",
        "an_summary": "خلاصه‌ی کلی",
        "an_users": "به تفکیک کاربر",
        "an_c_users": "کاربران فعال",
        "an_c_logins": "تعداد ورود",
        "an_c_failed": "ورود ناموفق",
        "an_c_minutes": "کل استفاده (دقیقه)",
        "an_c_avg": "میانگین هر نشست (دقیقه)",
        "an_c_longest": "طولانی‌ترین نشست (دقیقه)",
        "an_c_avg_user": "میانگین استفاده‌ی هر کاربر (دقیقه)",
        "an_c_sessions": "نشست‌های اندازه‌گیری‌شده",
        "an_c_tabs": "بازدید صفحه",
        "an_c_events": "رویدادها",
        "an_c_alerts": "هشدار / بحرانی",
        "an_failed_unknown": "از این میان نام‌های ناشناس",
        "an_col_user": "کاربر",
        "an_col_role": "نقش",
        "an_col_logins": "ورود",
        "an_col_failed": "ناموفق",
        "an_col_minutes": "مجموع (دقیقه)",
        "an_col_avg": "میانگین نشست (دقیقه)",
        "an_col_longest": "طولانی‌ترین (دقیقه)",
        "an_col_tabs": "بازدید صفحه",
        "an_col_top_tab": "پربازدیدترین صفحه",
        "an_col_days": "روزهای فعال",
        "an_col_alerts": "هشدارها",
        "an_col_last_login": "آخرین ورود",
        "an_col_last_seen": "آخرین فعالیت",
        "an_ch_category": "رویدادها به تفکیک نوع لاگ",
        "an_ch_hour": "فعالیت بر حسب ساعت روز",
        "an_ch_weekday": "فعالیت بر حسب روز هفته",
        "an_ch_day": "فعالیت در هر روز",
        "an_ch_tabs": "پربازدیدترین صفحه‌ها",
        "an_ch_events": "پرتکرارترین رویدادها",
        "an_ch_failed": "دلایل ورود ناموفق",
        "an_export": "دانلود جدول کاربران (CSV)",
        "an_note_sessions": "نشست‌هایی که هنوز باز هستند پس از پایان محاسبه می‌شوند.",
        "weekdays": "یکشنبه,دوشنبه,سه‌شنبه,چهارشنبه,پنجشنبه,جمعه,شنبه",
        "weekday_order": "6,0,1,2,3,4,5",
        "stored_rows": "ردیف‌های ذخیره‌شده",
        "log_size": "حجم کل لاگ‌ها",
        "mb": "مگابایت",
        "confirm_settings": "تنظیمات جدید نگهداری لاگ‌ها ذخیره شود؟",
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


def _minutes(seconds) -> str:
    """Seconds -> minutes for display: ``0``, ``3.5``, ``42``."""
    minutes = (seconds or 0) / 60
    if minutes == 0:
        return "0"
    return f"{minutes:.1f}" if minutes < 10 else f"{minutes:.0f}"


def _tz_label(offset_minutes: int) -> str:
    sign = "+" if offset_minutes >= 0 else "-"
    hours, minutes = divmod(abs(int(offset_minutes)), 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def _hbars(items) -> "ui.Tag":
    """Horizontal bar list from ``[(label, value), ...]`` (plain CSS, theme aware)."""
    top = max((value for _, value in items), default=0) or 1
    return ui.div(
        *[
            ui.div(
                ui.tags.span(str(label), class_="hbar-label", title=str(label)),
                ui.div(
                    ui.div(class_="hbar-fill", style=f"width:{max(2, round(value * 100 / top))}%"),
                    class_="hbar-track",
                ),
                ui.tags.span(str(value), class_="hbar-value"),
                class_="hbar-row",
            )
            for label, value in items
        ]
    )


def _vchart(values, labels, titles=None) -> "ui.Tag":
    """Vertical column chart; ``labels`` may contain empty strings."""
    top = max(values, default=0) or 1
    titles = titles or labels
    return ui.div(
        ui.div(
            *[
                ui.div(
                    class_="vbar",
                    style=f"height:{round(v * 100 / top)}%",
                    title=f"{t}: {v}",
                )
                for v, t in zip(values, titles)
            ],
            class_="vchart",
            dir="ltr",
        ),
        ui.div(*[ui.tags.span(label) for label in labels], class_="vchart-labels", dir="ltr"),
    )


def _users_csv(rows: list[dict]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        ["username", "role", "logins", "failed_logins", "sessions", "total_minutes",
         "avg_session_minutes", "longest_session_minutes", "page_views", "top_page",
         "active_days", "alerts", "events", "last_login_local", "last_activity_local"]
    )
    for r in rows:
        avg = (r["total_seconds"] / r["sessions"]) if r["sessions"] else 0
        writer.writerow(
            [_csv_safe(r["username"]), r["role"] or "", r["logins"], r["failed_logins"],
             r["sessions"], round(r["total_seconds"] / 60, 1), round(avg / 60, 1),
             round(r["max_seconds"] / 60, 1), r["tab_views"], _csv_safe(r["top_tab"]),
             r["active_days"], r["alerts"], r["events"], r["last_login"] or "",
             r["last_seen"] or ""]
        )
    return out.getvalue()


# --------------------------------- UI ---------------------------------------
def _analytics_panel():
    """Filters + summary cards + per-user table + charts (all server rendered)."""
    from datetime import date, timedelta

    today = date.today()
    return ui.div(
        ui.h5(_tx("an_title")),
        ui.p(_tx("an_intro"), class_="text-muted"),
        ui.div(ui.div(
            ui.div(
                ui.input_select(
                    "a_period", _tx("an_period"),
                    {k: _tx(f"an_p_{k}") for k in ("24h", "7d", "30d", "90d", "all", "custom")},
                    selected="30d", width="100%",
                ),
                class_="log-field",
            ),
            ui.div(
                ui.input_date_range(
                    "a_dates", _tx("an_dates"),
                    start=today - timedelta(days=30), end=today,
                    separator=t("date_separator"), width="100%",
                ),
                class_="log-field log-field-wide",
            ),
            ui.div(ui.output_ui("analytics_user_field"), class_="log-field"),
            ui.div(
                ui.input_select(
                    "a_role", _tx("an_role"),
                    {"": _tx("an_all_roles"), **{r: role_label(r) for r in
                                                 ("superadmin", "admin", "user", "guest")}},
                    width="100%",
                ),
                class_="log-field",
            ),
            ui.div(
                ui.input_select(
                    "a_severity", _tx("an_severity"),
                    {"": _tx("all"), "info": _tx("info"), "warning": _tx("warning"),
                     "critical": _tx("critical")},
                    width="100%",
                ),
                class_="log-field",
            ),
            ui.div(
                ui.input_checkbox_group(
                    "a_categories", _tx("an_categories"),
                    {c: _tx(f"cat_{c}") for c in ("auth", "navigation", "security")},
                    selected=["auth", "navigation", "security"], inline=True,
                ),
                class_="log-field log-checks",
            ),
            ui.div(
                ui.input_action_button("a_apply", _tx("an_apply"), class_="btn btn-primary"),
                ui.output_ui("analytics_download", inline=True),
                class_="log-actions",
            ),
            class_="log-filters log-grid-analytics",
        ), class_="user-form-card wide mb-3"),
        ui.output_ui("analytics_summary"),
        ui.output_ui("analytics_users"),
        ui.output_ui("analytics_charts"),
        ui.p(_tx("an_note_sessions"), class_="analytics-note mt-3"),
    )


def _log_backup_card():
    """Logs database backup / restore (Settings sub-tab)."""
    return ui.div(
        ui.h5(_tx("lb_title")),
        ui.p(_tx("lb_intro"), class_="text-muted"),
        ui.output_ui("lb_stats"),
        ui.div(
            ui.input_action_button("lb_create", _tx("lb_create"), class_="btn btn-primary"),
            class_="backup-toolbar",
        ),
        ui.div(
            ui.div(
                ui.input_file(
                    "logbackup_upload", _tx("lb_upload"),
                    accept=[".db", ".sqlite", ".sqlite3"], multiple=False,
                    button_label=t("file_browse"), placeholder=t("file_none"), width="100%",
                ),
                class_="backup-file",
            ),
            ui.input_action_button("lb_import", _tx("lb_import"), class_="btn btn-secondary"),
            class_="backup-toolbar",
        ),
        ui.div(ui.output_ui("lb_table"), class_="table-scroll mt-3"),
        class_="user-form-card wide mb-3",
    )


def _events_panel():
    """Filter bar + the three category tables."""
    return ui.div(
        # One flex row: equal-height fields, labels on one line, buttons aligned
        # with the bottom of the inputs. Styles: ".log-filters" in styles.css.
        ui.div(ui.div(
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
                # update_on="blur": filter when the field is left / Enter is
                # pressed, not one database query set per keystroke.
                ui.input_text("username", _tx("username"), width="100%", update_on="blur"),
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
            class_="log-filters log-grid-events",
        ), class_="user-form-card wide mb-3"),
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
            ui.p(_tx("purge_backup_note"), class_="analytics-note mt-2"),
            ui.div(
                ui.input_action_button(
                    "save_settings", _tx("save_settings"), class_="btn btn-primary"
                ),
                class_="log-actions mt-3",
            ),
            class_="user-form-card wide mb-3",
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
            class_="user-form-card wide mb-3",
        ),
        _log_backup_card(),
    )


@module.ui
def _ui():
    return ui.div(
        ui.h3(_tx("title")),
        ui.p(_tx("intro")),
        ui.output_ui("size_banner"),
        ui.navset_pill(
            ui.nav_panel(_tx("section_events"), _events_panel(), value="events"),
            ui.nav_panel(_tx("section_analytics"), _analytics_panel(), value="analytics"),
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

    # One cached query per category, shared by its table AND the CSV link
    # (they used to query the database separately on every refresh).
    def _events_calc(category: str):
        @reactive.calc
        def rows():
            return _fetch(category)

        return rows

    events = {c: _events_calc(c) for c in ("auth", "navigation", "security")}

    def _table(category: str):
        rows, error = events[category]()
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
            number("purge_backup_keep", "purge_backup_keep", "purge_backup_keep"),
            ui.div(
                ui.input_checkbox(
                    "purge_backup_on", _tx("purge_backup_enabled"),
                    bool(settings["purge_backup_enabled"]),
                ),
                class_="log-field log-checks log-check-inline",
            ),
            class_="log-filters log-settings-grid",
        )

    # Order matters: effect -> event -> @confirm_with_password -> callback.
    # The callback runs only after the confirmation dialog AND the correct password.
    @reactive.effect
    @reactive.event(input.save_settings)
    @confirm_with_password(
        input, get_session_user,
        message=_tx("confirm_settings"),
        required_role="superadmin",
    )
    def _on_save_settings():
        values = {
            "retention_days_navigation": input.ret_navigation(),
            "retention_days_auth": input.ret_auth(),
            "retention_days_security": input.ret_security(),
            "purge_interval_hours": input.purge_interval(),
            "purge_backup_enabled": 1 if input.purge_backup_on() else 0,
            "purge_backup_keep": input.purge_backup_keep(),
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
        size_mb, size_error = _guarded(audit_log_size_mb)
        chips = [
            ui.tags.span(_tx(f"cat_{c}"), " ", ui.tags.bdi(str(counts[c])), class_="log-chip")
            for c in ("navigation", "auth", "security")
        ]
        size_cell = [] if size_error else [
            ui.tags.bdi(f"{size_mb:.2f}", class_="log-size-value"), f" {_tx('mb')}",
        ]
        return ui.div(
            ui.div(ui.tags.strong(f"{_tx('stored_rows')}:"), *chips, class_="log-chip-row"),
            ui.p(ui.tags.strong(f"{_tx('log_size')}: "), *size_cell, class_="mb-1 mt-2"),
        )

    def _clear(category: str | None):
        """Delete one log (``None`` = all) as the re-validated user, then refresh."""
        deleted, error = _guarded(clear_audit_logs, category)
        if error:
            _toast(error, "error")
            return
        refresh.set(refresh() + 1)  # tables, counters and the size re-read the database
        _toast("cleared", "message", str(deleted))

    # Every clean-up button: confirmation dialog + the user's own password.
    # (The decorated name only opens the dialog; the body runs after the password.)
    @reactive.effect
    @reactive.event(input.clear_navigation)
    @confirm_with_password(
        input, get_session_user,
        message=_tx("confirm_navigation"), required_role="superadmin",
    )
    def _clear_navigation():
        _clear("navigation")

    @reactive.effect
    @reactive.event(input.clear_auth)
    @confirm_with_password(
        input, get_session_user,
        message=_tx("confirm_auth"), required_role="superadmin",
    )
    def _clear_auth():
        _clear("auth")

    @reactive.effect
    @reactive.event(input.clear_security)
    @confirm_with_password(
        input, get_session_user,
        message=_tx("confirm_security"), required_role="superadmin",
    )
    def _clear_security():
        _clear("security")

    @reactive.effect
    @reactive.event(input.clear_all)
    @confirm_with_password(
        input, get_session_user,
        message=_tx("confirm_all"), required_role="superadmin",
    )
    def _clear_all():
        _clear(None)

    # ---------------------- size banner (always visible) --------------------
    @render.ui
    def size_banner():
        refresh()
        size_mb, size_error = _guarded(audit_log_size_mb)
        counts, count_error = _guarded(audit_log_counts)
        if size_error or count_error:
            return ui.div()
        return ui.div(
            ui.tags.strong(f"{_tx('size_banner')}: "),
            # <bdi> keeps each number in place inside RTL text ("0.03 MB · 20 rows").
            ui.tags.bdi(f"{size_mb:.2f}", class_="log-size-value"),
            f" {_tx('mb')}",
            ui.tags.span("|", class_="mx-2 text-muted"),
            ui.tags.bdi(str(sum(counts.values()))),
            f" {_tx('size_banner_rows')}",
            class_="log-size-banner",
        )

    # ---------------------- user behaviour analysis -------------------------
    @render.ui
    def analytics_user_field():
        refresh()
        names, error = _guarded(audit_known_users)
        names = names or []
        try:
            with reactive.isolate():
                chosen = input.a_user() or ""
        except Exception:
            chosen = ""
        return ui.input_select(
            "a_user", _tx("an_user"),
            {"": _tx("an_all_users"), **{n: n for n in names}},
            selected=chosen if chosen in names else "", width="100%",
        )

    def _client_offset() -> int:
        try:
            return int(input.client_tz())
        except Exception:
            return 0  # not reported (yet): UTC

    @reactive.calc
    @reactive.event(input.a_apply, refresh, ignore_none=False)
    def analytics_data():
        """``(report, error_key)`` for the current filters.

        Recomputed when Apply (or Refresh) is pressed -- not on every filter
        change: each run scans the whole log with about a dozen queries.
        """
        try:
            # The user list is a dynamic output that may not exist yet on the
            # first run: treat "not there yet" as "all users".
            try:
                chosen_user = input.a_user() or None
            except SilentException:
                chosen_user = None
            categories = list(input.a_categories() or [])
            filters = {
                "period": input.a_period() or "30d",
                "username": chosen_user,
                "role": input.a_role() or None,
                "severity": input.a_severity() or None,
                "categories": categories,
                "tz_offset_minutes": _client_offset(),
            }
            dates = input.a_dates()
            if dates and len(dates) == 2:
                filters["date_from"], filters["date_to"] = str(dates[0]), str(dates[1])
        except Exception:
            return None, "wait"
        if not categories:
            return None, "an_no_category"
        report, error = _guarded(lambda: audit_analytics(**filters))
        return report, error

    def _analytics_error(error):
        if error == "wait":
            return ui.div()
        key = error if error in ("denied", "signin", "an_no_category") else "an_none"
        return ui.p(_tx(key), class_="text-muted mt-3")

    @render.ui
    def analytics_summary():
        report, error = analytics_data()
        if error:
            return _analytics_error(error)
        sm = report["summary"]
        if not sm["events"]:
            return ui.p(_tx("an_none"), class_="text-muted mt-3")
        cards = [
            (sm["users"], "an_c_users"),
            (sm["logins"], "an_c_logins"),
            (f"{sm['failed_logins']}", "an_c_failed"),
            (_minutes(sm["total_seconds"]), "an_c_minutes"),
            (_minutes(sm["avg_session_seconds"]), "an_c_avg"),
            (_minutes(sm["longest_session_seconds"]), "an_c_longest"),
            (_minutes(sm["avg_seconds_per_user"]), "an_c_avg_user"),
            (sm["sessions"], "an_c_sessions"),
            (sm["tab_views"], "an_c_tabs"),
            (sm["events"], "an_c_events"),
            (sm["alerts"], "an_c_alerts"),
        ]
        return ui.div(
            ui.h6(_tx("an_summary")),
            ui.div(
                *[
                    ui.div(
                        ui.div(str(value), class_="stat-value", dir="ltr"),
                        ui.div(_tx(label), class_="stat-label"),
                        class_="stat-card",
                    )
                    for value, label in cards
                ],
                class_="stat-grid",
            ),
            ui.p(
                f"{_tx('an_range')}: {_tz_label(report['range']['tz_offset_minutes'])}"
                + (f" \u00b7 {_tx('an_failed_unknown')}: {sm['failed_unknown']}"
                   if sm["failed_unknown"] else ""),
                class_="analytics-note",
            ),
        )

    @render.ui
    def analytics_users():
        report, error = analytics_data()
        if error or not report["summary"]["events"]:
            return ui.div()
        header = ui.tags.tr(
            *[ui.tags.th(_tx(f"an_col_{c}")) for c in (
                "user", "role", "logins", "failed", "minutes", "avg", "longest",
                "tabs", "top_tab", "days", "alerts", "last_login", "last_seen")]
        )
        body = []
        for r in report["users"]:
            avg = (r["total_seconds"] / r["sessions"]) if r["sessions"] else 0
            body.append(
                ui.tags.tr(
                    ui.tags.td(r["username"]),
                    ui.tags.td(role_label(r["role"]) if r["role"] else ""),
                    ui.tags.td(str(r["logins"])),
                    ui.tags.td(str(r["failed_logins"])),
                    ui.tags.td(_minutes(r["total_seconds"])),
                    ui.tags.td(_minutes(avg)),
                    ui.tags.td(_minutes(r["max_seconds"])),
                    ui.tags.td(str(r["tab_views"])),
                    ui.tags.td(r["top_tab"] or "-"),
                    ui.tags.td(str(r["active_days"])),
                    ui.tags.td(str(r["alerts"])),
                    ui.tags.td(r["last_login"] or "-", dir="ltr", class_="ltr-cell"),
                    ui.tags.td(r["last_seen"] or "-", dir="ltr", class_="ltr-cell"),
                )
            )
        return ui.div(
            ui.h6(_tx("an_users")),
            ui.div(ui.tags.table(header, *body, class_="users-table"), class_="table-scroll"),
        )

    @render.ui
    def analytics_charts():
        report, error = analytics_data()
        if error or not report["summary"]["events"]:
            return ui.div()
        names = _tx("weekdays").split(",")
        order = [int(i) for i in _tx("weekday_order").split(",")]
        hours = report["by_hour"]
        days = report["by_day"]
        day_labels = [""] * len(days)
        if days:
            for i in {0, len(days) // 2, len(days) - 1}:
                day_labels[i] = days[i]["day"][5:]
        cards = [
            (_tx("an_ch_category"), _hbars(
                [(_tx(f"cat_{c}"), n) for c, n in report["by_category"].items()])),
            (_tx("an_ch_hour"), _vchart(
                hours, [str(h) if h % 3 == 0 else "" for h in range(24)],
                [f"{h:02d}:00" for h in range(24)])),
            (_tx("an_ch_weekday"), _vchart(
                [report["by_weekday"][i] for i in order],
                [names[i][:3] for i in order], [names[i] for i in order])),
        ]
        if days:
            cards.append((_tx("an_ch_day"), _vchart(
                [d["events"] for d in days], day_labels, [d["day"] for d in days])))
        if report["top_tabs"]:
            cards.append((_tx("an_ch_tabs"), _hbars(report["top_tabs"])))
        if report["top_events"]:
            cards.append((_tx("an_ch_events"), _hbars(report["top_events"])))
        if report["failed_reasons"]:
            cards.append((_tx("an_ch_failed"), _hbars(report["failed_reasons"])))
        return ui.div(
            *[ui.div(ui.h6(title), chart, class_="chart-card") for title, chart in cards],
            class_="chart-grid",
        )

    @render.ui
    def analytics_download():
        report, error = analytics_data()
        if error or not report["users"]:
            return ui.tags.span()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        return ui.tags.a(
            _tx("an_export"), href=_csv_href(_users_csv(report["users"])),
            download=f"user-behaviour-{stamp}.csv", class_="btn btn-secondary",
        )

    # ---------------------- logs database backup / restore ------------------
    lb_rev = reactive.Value(0)
    pending: dict = {}

    def _attempt(function, *args):
        """Run a ``@superadmin`` function as the re-validated user.

        Returns ``(result, None)`` or ``(None, message)`` (message is shown as is).
        """
        person = get_session_user()
        if person is None:
            return None, _tx("signin")
        try:
            with user_context(person):
                return function(*args), None
        except PermissionError:
            return None, _tx("denied")
        except (ValueError, OSError) as exc:
            return None, str(exc)

    def _say(text: str, kind: str = "message"):
        ui.notification_show(text, type=kind, duration=6)

    @render.ui
    def lb_stats():
        lb_rev()
        refresh()
        stats, error = _attempt(log_backup_stats)
        if error:
            return ui.div()
        return ui.p(
            ui.tags.strong(f"{_tx('lb_stats')}: "),
            ui.tags.bdi(str(stats["count"])),
            ui.tags.span("|", class_="mx-2 text-muted"),
            ui.tags.bdi(format_size(stats["bytes"]), dir="ltr"),
            class_="mb-2",
        )

    @render.ui
    def lb_table():
        lb_rev()
        items, error = _attempt(list_log_backups)
        if error:
            return ui.div(error, class_="login-error")
        if not items:
            return ui.p(_tx("lb_none"), class_="text-muted")
        header = ui.tags.tr(
            *[ui.tags.th(_tx(f"lb_col_{c}")) for c in ("actions", "file", "created", "size", "type")]
        )
        target = f"{MODULE_ID}-logbackup_action"

        def button(action, label, style, name):
            return ui.tags.button(
                _tx(label), type="button", data_action=action, data_name=name,
                data_input=target, class_=f"btn btn-sm {style} backup-action me-1",
            )

        body = []
        for item in items:
            name = item["name"]
            where = f"/{item['location']}" if item["location"] else ""
            body.append(
                ui.tags.tr(
                    ui.tags.td(
                        button("restore", "lb_restore", "btn-warning", name),
                        button("download", "lb_download", "btn-secondary", name),
                        button("delete", "lb_delete", "btn-danger", name),
                        class_="user-actions-cell",
                    ),
                    ui.tags.td(f"{where.lstrip('/')}{'/' if where else ''}{name}",
                               dir="ltr", class_="ltr-cell"),
                    ui.tags.td(item["created"], dir="ltr", class_="ltr-cell"),
                    ui.tags.td(format_size(item["size"]), dir="ltr", class_="ltr-cell"),
                    ui.tags.td(_tx(f"lb_type_{item['kind']}")),
                )
            )
        return ui.tags.table(header, *body, class_="users-table")

    @reactive.effect
    @reactive.event(input.lb_create)
    def _lb_create():
        info, error = _attempt(create_log_backup)  # a copy changes nothing: no password
        if error:
            _say(error, "error")
            return
        lb_rev.set(lb_rev() + 1)
        _say(_tx("lb_created") + info["name"])

    @reactive.effect
    @reactive.event(input.logbackup_action)
    def _lb_action():
        # Restore / Download / Delete buttons of the table (static/js/custom.js).
        if get_session_user() is None:
            return
        payload = input.logbackup_action()
        if not isinstance(payload, dict):
            return
        action, name = payload.get("action"), payload.get("name")
        runners = {"restore": _lb_restore, "download": _lb_download, "delete": _lb_delete}
        if action not in runners or not log_backup.is_valid_name(name):
            return  # forged input
        pending["lb"] = name
        runners[action]()

    @confirm_with_password(
        input, get_session_user, message=_tx("lb_confirm_restore"), required_role="superadmin",
    )
    def _lb_restore():
        result, error = _attempt(restore_log_backup, pending.pop("lb", None))
        if error:
            _say(error, "error")
            return
        refresh.set(refresh() + 1)
        lb_rev.set(lb_rev() + 1)
        _say(_tx("lb_restored") + str(result["rows"]))

    @confirm_with_password(
        input, get_session_user, message=_tx("lb_confirm_delete"), required_role="superadmin",
    )
    def _lb_delete():
        _, error = _attempt(delete_log_backup, pending.pop("lb", None))
        if error:
            _say(error, "error")
            return
        lb_rev.set(lb_rev() + 1)
        _say(_tx("lb_deleted"))

    @confirm_with_password(
        input, get_session_user, message=_tx("lb_confirm_download"), required_role="superadmin",
    )
    def _lb_download():
        # The file reaches the browser only AFTER the password was confirmed.
        name = pending.pop("lb", None)
        data, error = _attempt(read_log_backup, name)
        if not error and len(data) > 20 * 1024 * 1024:
            error = _tx("lb_too_big")
        if error:
            _say(error, "error")
            return
        href = "data:application/octet-stream;base64," + base64.b64encode(data).decode("ascii")
        ui.modal_show(
            ui.modal(
                ui.p(_tx("lb_download_text")),
                ui.tags.a(name, href=href, download=name, class_="btn btn-primary"),
                title=_tx("lb_download_title"), easy_close=True,
                footer=ui.modal_button(_tx("lb_close"), class_="btn btn-secondary"),
            )
        )

    @reactive.effect
    @reactive.event(input.lb_import)
    def _lb_import():
        if get_session_user() is None:
            return
        files = input.logbackup_upload()
        if not files:
            _say(_tx("lb_no_file"), "error")
            return
        chosen = files[0]
        if int(chosen.get("size") or 0) > MAX_IMPORT_BYTES:
            _say(f"> {MAX_IMPORT_BYTES // (1024 * 1024)} MB", "error")
            return
        try:
            pending["lb_upload"] = Path(chosen["datapath"]).read_bytes()
        except (OSError, KeyError):
            _say(_tx("denied"), "error")
            return
        _lb_load()

    @confirm_with_password(
        input, get_session_user, message=_tx("lb_confirm_import"), required_role="superadmin",
    )
    def _lb_load():
        info, error = _attempt(import_log_backup, pending.pop("lb_upload", b""))
        if error:
            _say(error, "error")
            return
        lb_rev.set(lb_rev() + 1)
        _say(_tx("lb_imported") + info["name"])

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
        if category not in events:
            return ui.tags.span()
        rows, error = events[category]()
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
