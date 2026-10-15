"""Bilingual UI strings (i18n.py): both languages stay in sync."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from string import Formatter

import pytest

import i18n

PROJECT = Path(__file__).resolve().parent.parent


def _placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(text) if name}


class TestDictionaryParity:
    def test_same_keys_in_every_language(self):
        reference = set(i18n.STRINGS["en"])
        for lang, table in i18n.STRINGS.items():
            assert set(table) == reference, f"{lang}: keys differ from 'en'"

    def test_no_empty_values(self):
        for lang, table in i18n.STRINGS.items():
            for key, value in table.items():
                assert value.strip(), f"{lang}.{key} is empty"

    def test_placeholders_match_english(self):
        for lang, table in i18n.STRINGS.items():
            for key, value in table.items():
                assert _placeholders(value) == _placeholders(i18n.STRINGS["en"][key]), (
                    f"{lang}.{key}: placeholders differ from 'en'"
                )

    def test_persian_is_actually_translated(self):
        fa = i18n.STRINGS["fa"]
        arabic_script = re.compile("[\u0600-\u06FF]")
        for key, value in fa.items():
            assert arabic_script.search(value), f"fa.{key} has no Persian text"


class TestTranslateHelper:
    def test_default_is_english(self):
        assert i18n.STRINGS["en"]["login_title"] == "Secure Dashboard"

    def test_switches_with_app_lang(self, monkeypatch):
        monkeypatch.setattr(i18n, "APP_LANG", "fa")
        assert i18n.t("login_title") == i18n.STRINGS["fa"]["login_title"]
        monkeypatch.setattr(i18n, "APP_LANG", "en")
        assert i18n.t("login_title") == "Secure Dashboard"

    def test_format_placeholders(self, monkeypatch):
        monkeypatch.setattr(i18n, "APP_LANG", "en")
        assert "30" in i18n.t("login_locked", remaining=30)
        monkeypatch.setattr(i18n, "APP_LANG", "fa")
        assert "30" in i18n.t("login_locked", remaining=30)

    def test_missing_key_returns_key(self):
        assert i18n.t("no_such_key_anywhere") == "no_such_key_anywhere"

    def test_missing_key_in_language_falls_back_to_english(self, monkeypatch):
        monkeypatch.setitem(i18n.STRINGS, "xx", {})
        monkeypatch.setattr(i18n, "APP_LANG", "xx")
        assert i18n.t("login_title") == "Secure Dashboard"

    def test_role_label(self, monkeypatch):
        monkeypatch.setattr(i18n, "APP_LANG", "en")
        assert i18n.role_label("superadmin") == "Superadmin"
        assert i18n.role_label("unknown-role") == "unknown-role"


class TestLanguageSelection:
    def _lang_for(self, value: str | None) -> str:
        env = {k: v for k, v in os.environ.items() if k != "APP_LANG"}
        if value is not None:
            env["APP_LANG"] = value
        code = "import i18n; print(i18n.APP_LANG, i18n.DIRECTION, i18n.IS_RTL)"
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT, env=env, capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()

    def test_default_is_english_ltr(self):
        assert self._lang_for(None) == "en ltr False"

    def test_env_var_selects_persian_rtl(self):
        assert self._lang_for("fa") == "fa rtl True"

    def test_env_var_is_case_insensitive(self):
        assert self._lang_for(" FA ") == "fa rtl True"

    def test_unknown_language_falls_back_to_english(self):
        assert self._lang_for("xx") == "en ltr False"


class TestBrowserBundle:
    def test_theme_names_cover_every_theme_in_custom_js(self):
        js = (PROJECT / "static/js/custom.js").read_text(encoding="utf-8")
        js_ids = set(re.findall(r'"((?:light|dark)-[a-z]+)":\s*\{', js))
        assert len(js_ids) == 12
        assert set(i18n.js_bundle()["themes"]) == js_ids

    def test_confirm_text_keeps_username_placeholder(self):
        assert "{username}" in i18n.js_bundle()["users_confirm_delete"]


class TestNoHardcodedUiText:
    """The four translated areas must not slip back to literal English."""

    @pytest.mark.parametrize("rel", ["tabs/tab_account.py", "tabs/tab_users.py"])
    def test_tab_modules_use_t(self, rel):
        text = (PROJECT / rel).read_text(encoding="utf-8")
        assert "from i18n import" in text
        assert 't("' in text
