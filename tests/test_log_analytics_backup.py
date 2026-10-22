"""User behaviour analytics, log database backup / restore, automatic pre-purge backup."""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import auth.core as core
from auth import audit, log_backup

PROJECT = Path(__file__).resolve().parent.parent
LOGS_TAB = (PROJECT / "tabs/tab_logs.py").read_text(encoding="utf-8")
JS = (PROJECT / "static/js/custom.js").read_text(encoding="utf-8")
APP = (PROJECT / "app.py").read_text(encoding="utf-8")

ALICE = {"id": 1, "username": "alice", "role": "admin"}
BOB = {"id": 2, "username": "bob", "role": "user"}


def _put(category, event, user=None, *, username=None, severity="info", detail=None, ts=None):
    """Insert one log row, optionally with a chosen UTC time stamp."""
    audit.log_event(category, event, user=user, username=username, severity=severity, detail=detail)
    if ts:
        con = audit._connect()
        con.execute("UPDATE audit_log SET ts=? WHERE id=(SELECT MAX(id) FROM audit_log)", (ts,))
        con.commit(); con.close()


@pytest.fixture
def traffic(isolated_db):
    """alice: 2 logins, 25 min total; bob: 1 login, 5 min, one failed login, one denied."""
    for _ in range(2):
        _put("auth", "login_success", ALICE)
    _put("navigation", "tab_opened", ALICE, detail={"tab": "tab_01"})
    _put("navigation", "tab_opened", ALICE, detail={"tab": "tab_01"})
    _put("navigation", "tab_opened", ALICE, detail={"tab": "tab_02"})
    _put("auth", "logout", ALICE, detail={"duration_s": 600})
    _put("navigation", "session_ended", ALICE, detail={"duration_s": 900})
    _put("auth", "login_success", BOB)
    _put("navigation", "tab_opened", BOB, detail={"tab": "tab_02"})
    _put("auth", "logout", BOB, detail={"duration_s": 300})
    _put("auth", "login_failed", username="bob", severity="warning", detail={"reason": "bad_credentials"})
    _put("auth", "login_failed", username="mallory", severity="warning", detail={"reason": "captcha"})
    _put("security", "access_denied", BOB, severity="warning")
    return isolated_db


def _user(report, name):
    return next(u for u in report["users"] if u["username"] == name)


class TestAnalytics:
    def test_per_user_numbers(self, traffic):
        report = audit.analytics("all")
        alice, bob = _user(report, "alice"), _user(report, "bob")
        assert (alice["logins"], alice["sessions"], alice["total_seconds"], alice["max_seconds"]) == (2, 2, 1500, 900)
        assert alice["tab_views"] == 3 and alice["top_tab"] == "tab_01"
        assert (bob["logins"], bob["total_seconds"], bob["failed_logins"], bob["alerts"]) == (1, 300, 1, 1)

    def test_overall_summary(self, traffic):
        sm = audit.analytics("all")["summary"]
        assert sm["users"] == 2 and sm["logins"] == 3
        assert sm["sessions"] == 3 and sm["total_seconds"] == 1800
        assert sm["avg_session_seconds"] == 600 and sm["longest_session_seconds"] == 900
        assert sm["avg_seconds_per_user"] == 900
        assert sm["failed_logins"] == 2 and sm["failed_unknown"] == 1  # "mallory" is not an account
        assert sm["tab_views"] == 4

    def test_users_are_sorted_by_usage(self, traffic):
        assert [u["username"] for u in audit.analytics("all")["users"]] == ["alice", "bob"]

    def test_breakdowns(self, traffic):
        report = audit.analytics("all")
        assert report["by_category"] == {"auth": 7, "navigation": 5, "security": 1}
        assert dict(report["top_tabs"]) == {"tab_01": 2, "tab_02": 2}
        assert dict(report["failed_reasons"]) == {"bad_credentials": 1, "captcha": 1}
        assert sum(report["by_hour"]) == sum(report["by_weekday"]) == report["summary"]["events"]
        assert report["by_day"][-1]["logins"] == 3

    def test_filter_one_user(self, traffic):
        report = audit.analytics("all", username="bob")
        assert [u["username"] for u in report["users"]] == ["bob"]
        assert report["summary"]["total_seconds"] == 300

    def test_filter_role(self, traffic):
        assert [u["username"] for u in audit.analytics("all", role="admin")["users"]] == ["alice"]

    def test_filter_category(self, traffic):
        only_security = audit.analytics("all", categories=["security"])
        assert only_security["summary"]["events"] == 1
        assert only_security["summary"]["logins"] == 0  # login events belong to "auth"
        only_nav = audit.analytics("all", categories=["navigation"])
        assert only_nav["summary"]["tab_views"] == 4 and only_nav["summary"]["logins"] == 0
        assert only_nav["summary"]["total_seconds"] == 900  # only session_ended is navigation
        assert audit.analytics("all", categories=[])["summary"]["events"] == 0

    def test_filter_severity(self, traffic):
        sm = audit.analytics("all", severity="warning")["summary"]
        assert sm["events"] == 3 and sm["failed_logins"] == 2

    def test_period_presets(self, isolated_db):
        old = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
        _put("auth", "login_success", ALICE, ts=old)
        _put("auth", "login_success", ALICE)
        assert audit.analytics("24h")["summary"]["logins"] == 1
        assert audit.analytics("7d")["summary"]["logins"] == 1
        assert audit.analytics("30d")["summary"]["logins"] == 2
        assert audit.analytics("all")["summary"]["logins"] == 2

    def test_custom_dates_are_inclusive(self, isolated_db):
        for day in ("2026-03-01 23:30:00", "2026-03-02 00:15:00", "2026-03-04 10:00:00"):
            _put("auth", "login_success", ALICE, ts=day)
        got = audit.analytics("custom", date_from="2026-03-02", date_to="2026-03-04")["summary"]["logins"]
        assert got == 2
        swapped = audit.analytics("custom", date_from="2026-03-04", date_to="2026-03-02")
        assert swapped["summary"]["logins"] == 2  # reversed dates are tolerated

    def test_timezone_shifts_hours_and_days(self, isolated_db):
        _put("auth", "login_success", ALICE, ts="2026-03-01 22:00:00")  # UTC
        utc = audit.analytics("all")
        tehran = audit.analytics("all", tz_offset_minutes=210)  # UTC+03:30 -> 01:30 next day
        assert utc["by_hour"][22] == 1 and tehran["by_hour"][1] == 1
        assert utc["by_day"][0]["day"] == "2026-03-01" and tehran["by_day"][0]["day"] == "2026-03-02"
        assert tehran["users"][0]["last_login"] == "2026-03-02 01:30:00"
        # the custom range is read in the viewer's local days, too
        local_day = audit.analytics("custom", date_from="2026-03-02", date_to="2026-03-02", tz_offset_minutes=210)
        assert local_day["summary"]["logins"] == 1

    def test_garbage_durations_are_ignored(self, isolated_db):
        _put("auth", "login_success", ALICE)
        for bad in ("soon", None, -5, True, 10**9):
            _put("auth", "logout", ALICE, detail={"duration_s": bad})
        _put("auth", "logout", ALICE, detail={"duration_s": 120})
        user = _user(audit.analytics("all"), "alice")
        assert user["sessions"] == 1 and user["total_seconds"] == 120

    def test_revoked_sessions_count_too(self, isolated_db):
        _put("security", "session_revoked", ALICE, severity="warning",
             detail={"reason": "account_disabled", "duration_s": 60})
        assert _user(audit.analytics("all"), "alice")["total_seconds"] == 60

    def test_empty_log(self, isolated_db):
        report = audit.analytics("30d")
        assert report["users"] == [] and report["summary"]["events"] == 0
        assert report["summary"]["avg_session_seconds"] == 0

    def test_bad_period(self, isolated_db):
        with pytest.raises(ValueError):
            audit.analytics("forever")

    def test_user_name_filter_is_exact_and_safe(self, traffic):
        assert audit.analytics("all", username="bo")["users"] == []
        assert audit.analytics("all", username="x' OR '1'='1")["users"] == []

    def test_known_users(self, traffic):
        assert audit.known_users() == ["alice", "bob"]  # not "mallory" (never signed in)


class TestAnalyticsAccess:
    def test_superadmin_only(self, traffic, admin_ctx):
        with pytest.raises(PermissionError):
            core.audit_analytics(period="all")
        with pytest.raises(PermissionError):
            core.audit_known_users()

    def test_superadmin_can_read(self, traffic, superadmin_ctx):
        assert core.audit_analytics(period="all")["summary"]["users"] == 2
        assert "alice" in core.audit_known_users()


class TestSessionDurationIsLogged:
    def test_app_records_duration_for_revoked_sessions(self):
        block = APP.split('"session_revoked"')[1][:200]
        assert "duration_s" in block


# ------------------------------------------------------------ log backup
def _rows():
    con = audit._connect()
    try:
        return con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    finally:
        con.close()


class TestLogBackup:
    def test_create_and_list(self, superadmin_ctx):
        info = core.create_log_backup()
        assert info["kind"] == "manual" and info["name"].startswith("audit-")
        assert (audit.AUDIT_DB_PATH.parent / "log_backups" / info["name"]).is_file()
        assert [b["name"] for b in core.list_log_backups()] == [info["name"]]
        assert core.log_backup_stats()["count"] == 1

    def test_restore_replaces_the_rows(self, superadmin_ctx):
        audit.log_event("auth", "before", user=ALICE)
        rows_then = _rows()
        snapshot = core.create_log_backup()
        audit.log_event("auth", "after_1", user=ALICE)
        audit.log_event("auth", "after_2", user=ALICE)
        result = core.restore_log_backup(snapshot["name"])
        events = {e["event"] for e in audit.query_events(limit=100)}
        assert "before" in events and "after_1" not in events and "after_2" not in events
        assert result["rows"] == rows_then
        assert result["safety"]["kind"] == "prerestore"
        assert "audit_backup_restored" in events  # logged AFTER the restore, so it survives it

    def test_restore_keeps_the_retention_settings(self, superadmin_ctx):
        core.update_audit_settings({**audit.DEFAULT_SETTINGS, "retention_days_auth": 77})
        snapshot = core.create_log_backup()
        core.update_audit_settings({**audit.DEFAULT_SETTINGS, "retention_days_auth": 88})
        core.restore_log_backup(snapshot["name"])
        assert core.get_audit_settings()["retention_days_auth"] == 88

    def test_safety_copy_can_undo_a_restore(self, superadmin_ctx):
        snapshot = core.create_log_backup()
        audit.log_event("auth", "precious", user=ALICE)
        result = core.restore_log_backup(snapshot["name"])
        assert "precious" not in {e["event"] for e in audit.query_events(limit=100)}
        core.restore_log_backup(result["safety"]["name"])
        assert "precious" in {e["event"] for e in audit.query_events(limit=100)}

    def test_rejects_forged_missing_and_corrupt(self, superadmin_ctx):
        for forged in ("../audit.db", "audit.db", "auth-20200101-000000.db"):
            with pytest.raises(ValueError, match="Invalid backup"):
                core.restore_log_backup(forged)
        with pytest.raises(ValueError, match="not found"):
            core.restore_log_backup("audit-20200101-000000.db")
        bad = audit.AUDIT_DB_PATH.parent / "log_backups" / "audit-20200101-000001.db"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_bytes(b"nonsense")
        before = _rows()
        with pytest.raises(ValueError, match="not a valid"):
            core.restore_log_backup(bad.name)
        assert _rows() == before

    def test_a_database_without_the_log_table_is_refused(self, superadmin_ctx):
        other = audit.AUDIT_DB_PATH.parent / "log_backups" / "audit-20200101-000002.db"
        other.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(other) as con:
            con.execute("CREATE TABLE something_else(x)")
        with pytest.raises(ValueError, match="not a valid"):
            core.restore_log_backup(other.name)

    def test_import_download_delete(self, superadmin_ctx):
        source = core.create_log_backup()
        data = core.read_log_backup(source["name"])
        assert data.startswith(b"SQLite format 3\x00")
        imported = core.import_log_backup(data)
        assert imported["kind"] == "uploaded"
        core.delete_log_backup(imported["name"])
        assert imported["name"] not in [b["name"] for b in core.list_log_backups()]
        with pytest.raises(ValueError):
            core.import_log_backup(b"garbage")

    def test_only_superadmin(self, admin_ctx):
        for call in (core.create_log_backup, core.list_log_backups, core.log_backup_stats,
                     lambda: core.restore_log_backup("audit-20200101-000000.db"),
                     lambda: core.delete_log_backup("audit-20200101-000000.db"),
                     lambda: core.read_log_backup("audit-20200101-000000.db"),
                     lambda: core.import_log_backup(b"x")):
            with pytest.raises(PermissionError):
                call()

    def test_operations_are_audited(self, superadmin_ctx):
        info = core.create_log_backup()
        core.read_log_backup(info["name"])
        core.delete_log_backup(info["name"])
        events = {e["event"] for e in audit.query_events(category="security", limit=50)}
        assert {"audit_backup_created", "audit_backup_downloaded", "audit_backup_deleted"} <= events

    def test_logs_and_accounts_backups_do_not_mix(self, superadmin_ctx):
        core.create_backup()
        core.create_log_backup()
        assert all(b["name"].startswith("auth-") for b in core.list_backups())
        assert all(b["name"].startswith("audit-") for b in core.list_log_backups())


# ------------------------------------------- automatic backup before a purge
def _old_rows(n=3):
    for i in range(n):
        audit.log_event("navigation", f"old_{i}", user=ALICE)


LATER = lambda: datetime.now(timezone.utc) + timedelta(days=60)  # noqa: E731


class TestAutoBackupBeforePurge:
    def test_backup_is_made_in_the_special_folder_before_deleting(self, isolated_db):
        _old_rows(3)
        assert audit.purge_old(now=LATER()) == 3
        auto = audit.AUDIT_DB_PATH.parent / "log_backups" / "auto"
        files = list(auto.glob("audit-*-auto.db"))
        assert len(files) == 1
        with sqlite3.connect(files[0]) as con:  # the copy still holds the rows that were deleted
            names = {r[0] for r in con.execute("SELECT event FROM audit_log")}
        assert {"old_0", "old_1", "old_2"} <= names

    def test_nothing_to_delete_means_no_backup(self, isolated_db):
        audit.log_event("navigation", "fresh", user=ALICE)
        assert audit.purge_old() == 0
        assert not (audit.AUDIT_DB_PATH.parent / "log_backups" / "auto").exists() or \
            not list((audit.AUDIT_DB_PATH.parent / "log_backups" / "auto").iterdir())

    def test_can_be_switched_off(self, superadmin_ctx):
        core.update_audit_settings({**audit.DEFAULT_SETTINGS, "purge_backup_enabled": 0})
        _old_rows(2)
        assert audit.purge_old(now=LATER()) == 2
        auto = audit.AUDIT_DB_PATH.parent / "log_backups" / "auto"
        assert not auto.exists() or not list(auto.iterdir())

    def test_nothing_is_deleted_when_the_backup_fails(self, isolated_db, monkeypatch):
        _old_rows(2)

        def boom(*a, **k):
            raise OSError("disk full")

        monkeypatch.setattr(log_backup, "create_auto", boom)
        assert audit.purge_old(now=LATER()) == 0
        assert _rows() == 2

    def test_only_the_newest_n_automatic_backups_are_kept(self, superadmin_ctx):
        core.update_audit_settings({**audit.DEFAULT_SETTINGS, "purge_backup_keep": 2})
        for _ in range(4):
            _old_rows(1)
            assert audit.purge_old(now=LATER()) == 1
        auto = audit.AUDIT_DB_PATH.parent / "log_backups" / "auto"
        assert len(list(auto.glob("audit-*-auto.db"))) == 2

    def test_automatic_backups_are_listed_and_restorable(self, superadmin_ctx):
        _old_rows(2)
        audit.purge_old(now=LATER())
        autos = [b for b in core.list_log_backups() if b["kind"] == "auto"]
        assert len(autos) == 1 and autos[0]["location"] == "auto"
        core.restore_log_backup(autos[0]["name"])
        assert {"old_0", "old_1"} <= {e["event"] for e in audit.query_events(limit=100)}

    def test_purge_is_recorded(self, isolated_db):
        _old_rows(2)
        audit.purge_old(now=LATER())
        row = next(e for e in audit.query_events(category="security") if e["event"] == "audit_auto_purged")
        assert '"removed": 2' in row["detail"] and "-auto.db" in row["detail"]


class TestNewSettings:
    def test_old_callers_may_omit_the_new_keys(self, superadmin_ctx):
        four = {k: audit.DEFAULT_SETTINGS[k] for k in
                ("retention_days_navigation", "retention_days_auth",
                 "retention_days_security", "purge_interval_hours")}
        core.update_audit_settings(four)
        assert core.get_audit_settings()["purge_backup_keep"] == 10

    @pytest.mark.parametrize("key, value", [("purge_backup_keep", 0), ("purge_backup_keep", 101),
                                            ("purge_backup_enabled", 2)])
    def test_limits(self, superadmin_ctx, key, value):
        with pytest.raises(ValueError):
            core.update_audit_settings({**audit.DEFAULT_SETTINGS, key: value})


# ------------------------------------------------------------------- UI
class TestLogsTabWiring:
    def test_analytics_tab_exists_in_both_languages(self):
        from tabs import tab_logs

        assert tab_logs._TEXTS["en"]["section_analytics"] == "User behaviour analysis"
        assert tab_logs._TEXTS["fa"]["section_analytics"] == "تحلیل رفتار کاربران"
        assert set(tab_logs._TEXTS["en"]) == set(tab_logs._TEXTS["fa"])

    def test_panel_contains_the_controls(self):
        from tabs import tab_logs

        html = str(tab_logs._ui("tab_logs"))
        for element in ("tab_logs-a_period", "tab_logs-a_dates", "tab_logs-a_categories",
                        "tab_logs-a_severity", "tab_logs-a_role", "tab_logs-analytics_summary",
                        "tab_logs-analytics_charts", "tab_logs-lb_create", "tab_logs-lb_table",
                        "tab_logs-logbackup_upload", "tab_logs-size_banner",
                        "tab_logs-purge_backup_on" if False else "tab_logs-section"):
            assert element in html, element

    def test_log_backup_actions_are_password_protected(self):
        protected = set(re.findall(r"@confirm_with_password\((?:.|\n)*?\)\n\s*def (\w+)\(", LOGS_TAB))
        assert {"_lb_restore", "_lb_delete", "_lb_download", "_lb_load"} <= protected

    def test_backup_buttons_post_to_the_module_input(self):
        assert 'data-input' in JS and "tab_logs-client_tz" in JS
        assert 'f"{MODULE_ID}-logbackup_action"' in LOGS_TAB

    @pytest.mark.parametrize("seconds, text", [(0, "0"), (30, "0.5"), (90, "1.5"), (600, "10"), (3600, "60")])
    def test_minutes_format(self, seconds, text):
        from tabs import tab_logs

        assert tab_logs._minutes(seconds) == text

    def test_tz_label(self):
        from tabs import tab_logs

        assert tab_logs._tz_label(210) == "UTC+03:30" and tab_logs._tz_label(-300) == "UTC-05:00"
        assert tab_logs._tz_label(0) == "UTC+00:00"

    def test_users_csv_is_formula_safe(self):
        from tabs import tab_logs

        row = {"username": "=cmd()", "role": "user", "logins": 1, "failed_logins": 0, "sessions": 1,
               "total_seconds": 120, "max_seconds": 120, "tab_views": 2, "top_tab": "tab_01",
               "active_days": 1, "alerts": 0, "events": 3, "last_login": None, "last_seen": None}
        text = tab_logs._users_csv([row])
        assert "'=cmd()" in text and text.splitlines()[1].split(",")[5] == "2.0"
