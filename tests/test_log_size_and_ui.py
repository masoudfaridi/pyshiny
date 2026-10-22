"""Log size (MB), @confirm_with_password wiring, top bar clock, new UI strings."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import auth.core as core
import i18n
from auth import audit

PROJECT = Path(__file__).resolve().parent.parent
APP = (PROJECT / "app.py").read_text(encoding="utf-8")
LOGS_TAB = (PROJECT / "tabs/tab_logs.py").read_text(encoding="utf-8")
JS = (PROJECT / "static/js/custom.js").read_text(encoding="utf-8")
CSS = (PROJECT / "static/css/styles.css").read_text(encoding="utf-8")


# ----------------------------------------------------------------- log size
class TestLogSize:
    def test_empty_when_the_file_does_not_exist(self, tmp_path, monkeypatch):
        monkeypatch.setattr(audit, "AUDIT_DB_PATH", tmp_path / "missing.db")
        assert audit.db_size_bytes() == 0 and audit.size_mb() == 0.0

    def test_size_is_reported_in_megabytes(self, superadmin_ctx):
        audit.log_event("auth", "login_success", user=superadmin_ctx)
        size = core.audit_log_size_mb()
        assert isinstance(size, float) and size > 0
        assert size == pytest.approx(audit.db_size_bytes() / (1024 * 1024))

    def test_includes_the_wal_side_files(self, superadmin_ctx):
        audit.log_event("auth", "login_success", user=superadmin_ctx)
        main = audit.AUDIT_DB_PATH
        wal = main.with_name(main.name + "-wal")
        wal.write_bytes(b"\0" * 4096)  # pretend a WAL exists (it is part of the footprint)
        try:
            assert audit.db_size_bytes() >= main.stat().st_size + 4096
        finally:
            wal.unlink()

    def test_grows_with_data_and_shrinks_after_clear(self, superadmin_ctx):
        for i in range(600):
            audit.log_event("navigation", "tab_opened", user=superadmin_ctx, detail={"tab": f"tab_{i}" * 5})
        big = audit.db_size_bytes()
        assert big > 40 * 1024
        core.clear_audit_logs()
        assert audit.db_size_bytes() < big  # VACUUM gave the space back

    def test_only_superadmin_can_read_it(self, admin_ctx):
        with pytest.raises(PermissionError):
            core.audit_log_size_mb()


# ---------------------------------------------- @confirm_with_password wiring
def _decorated_functions(source: str) -> set[str]:
    """Names of functions that sit directly under @confirm_with_password(...)."""
    names = set()
    for match in re.finditer(r"@confirm_with_password\((?:.|\n)*?\)\n\s*def (\w+)\(", source):
        names.add(match.group(1))
    return names


class TestPasswordProtection:
    def test_user_management_actions_are_protected(self):
        protected = _decorated_functions(APP)
        assert {
            "_run_create_user", "_run_save_user", "_run_delete_user",
            "_run_restore_backup", "_run_delete_backup", "_run_download_backup",
            "_run_import_backup",
        } <= protected

    def test_every_protected_action_requires_superadmin(self):
        blocks = re.findall(r"@confirm_with_password\(((?:.|\n)*?)\)\n\s*def (\w+)\(", APP)
        assert blocks
        for args, name in blocks:
            assert 'required_role="superadmin"' in args, name

    def test_log_actions_are_protected(self):
        protected = _decorated_functions(LOGS_TAB)
        assert {"_on_save_settings", "_clear_navigation", "_clear_auth",
                "_clear_security", "_clear_all"} <= protected

    def test_no_unprotected_clear_path_is_left_in_logs_tab(self):
        assert "clear_audit_logs" in LOGS_TAB
        assert "confirm_bar" not in LOGS_TAB and "_on_confirm_clear" not in LOGS_TAB

    def test_browser_confirm_was_replaced(self):
        assert "window.confirm" not in JS

    def test_delete_event_goes_through_the_decorated_function(self):
        for handler in ("_delete_from_table", "_delete_user_event"):
            body = APP.split(f"def {handler}(")[1].split("\n    @")[0]
            assert "delete_user(" not in body, f"{handler} must not delete directly"
            assert "_ask_delete(" in body


class TestConfirmDecoratorFlowForLogs:
    """The flow object behind a decorated callback must be a normal _Flow."""

    def test_flow_requires_superadmin(self, isolated_db):
        from auth import confirm

        ran = []
        flow = confirm._Flow(lambda: ran.append(1), "reauth_x", lambda: core.authenticate("admin", "Admin123!"),
                             "msg", None, "superadmin", 120)
        shown, toasts = [], []
        flow.show_modal = shown.append
        flow.notify = lambda text, **kw: toasts.append(text)
        flow.start()
        assert shown == [] and ran == []  # an admin never even gets the dialog


# ------------------------------------------------------------------- clock
class TestTopBarClock:
    def test_element_sits_before_the_logout_button(self):
        clock = APP.index('id="topbar-datetime"')
        logout = APP.index('"logout_button"')
        assert clock < logout

    def test_language_is_exposed_to_javascript(self):
        assert "window.APP_LANG=" in APP

    def test_script_uses_the_persian_calendar_for_fa_and_gregorian_for_en(self):
        assert "fa-IR-u-ca-persian" in JS
        assert '"en-CA"' in JS and '"en-US"' in JS
        assert 'window.APP_LANG || "en"' in JS
        assert "setInterval(updateClock, 1000)" in JS

    def test_weekday_date_and_time_are_all_shown(self):
        assert "weekday" in JS and "hourCycle" in JS and "second:" not in JS  # minutes only

    def test_css_rules_exist(self):
        for selector in (".topbar-datetime", ".table-scroll", ".backup-toolbar", ".profile-details"):
            assert selector in CSS


# -------------------------------------------------------------- UI strings
NEW_KEYS = [
    "id_code", "email", "phone", "users_col_id_code", "users_col_email", "users_col_phone",
    "err_id_code_required", "err_id_code_format", "err_id_code_exists", "err_email_format",
    "err_phone_format", "account_profile_heading", "users_confirm_create", "users_confirm_update",
    "backup_title", "backup_create", "backup_restore", "backup_confirm_restore", "err_backup_invalid",
]


class TestStrings:
    @pytest.mark.parametrize("key", NEW_KEYS)
    def test_key_exists_in_both_languages(self, key):
        assert i18n.STRINGS["en"][key].strip()
        assert i18n.STRINGS["fa"][key].strip()

    def test_languages_stay_in_sync(self):
        assert set(i18n.STRINGS["en"]) == set(i18n.STRINGS["fa"])

    def test_placeholders_match_between_languages(self):
        pattern = re.compile(r"{(\w+)}")
        for key, text in i18n.STRINGS["en"].items():
            assert set(pattern.findall(text)) == set(pattern.findall(i18n.STRINGS["fa"][key])), key

    def test_log_size_texts(self):
        from tabs import tab_logs

        for lang in ("en", "fa"):
            assert tab_logs._TEXTS[lang]["log_size"] and tab_logs._TEXTS[lang]["mb"]
            assert tab_logs._TEXTS[lang]["confirm_settings"]


class TestPanelsRender:
    def test_users_panel_has_the_new_fields_and_backup_card(self):
        from tabs import tab_users

        html = str(tab_users.panel())
        for element in ('id="new_id_code"', 'id="new_email"', 'id="new_phone"',
                        'id="backup_create"', 'id="backup_upload"', 'id="backup_import"',
                        'id="backups_table"'):
            assert element in html, element

    def test_account_panel_shows_own_details(self, isolated_db):
        from tabs import tab_account

        person = core.authenticate("user", "User123!")
        person.update({"id_code": "EMP-9", "email": "me@example.com", "phone": "0912"})
        with core.user_context(person):
            html = str(tab_account.panel())
        assert "EMP-9" in html and 'value="me@example.com"' in html
        assert 'id="profile_email"' in html and 'id="profile_save_button"' in html
