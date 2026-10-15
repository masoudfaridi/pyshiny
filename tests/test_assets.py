"""Static assets, package exports, and project layout (no Shiny required)."""
from __future__ import annotations

from pathlib import Path

import pytest

import auth

PROJECT = Path(__file__).resolve().parent.parent


class TestAuthPackageExports:
    def test_all_exports_importable(self):
        for name in auth.__all__:
            assert hasattr(auth, name), f"auth missing export {name}"

    def test_critical_callables(self):
        for name in (
            "authenticate",
            "create_user",
            "list_users",
            "update_user",
            "delete_user",
            "generate_captcha",
            "verify_captcha",
            "init_db",
            "validate_username",
            "validate_password",
            "has_role",
            "require_role",
        ):
            assert callable(getattr(auth, name))


class TestProjectLayout:
    @pytest.mark.parametrize(
        "rel",
        [
            "auth/core.py",
            "auth/captcha.py",
            "auth/__init__.py",
            "app.py",
            "i18n.py",
            "requirements.txt",
            "static/css/styles.css",
            "static/js/custom.js",
            "tabs/tab_01.py",
            "tabs/tab_users.py",
            "pytest.ini",
            "tests/conftest.py",
        ],
    )
    def test_expected_files_exist(self, rel):
        assert (PROJECT / rel).is_file(), f"missing {rel}"

    def test_gitignore_excludes_db(self):
        gi = (PROJECT / ".gitignore").read_text(encoding="utf-8")
        assert "auth.db" in gi or "db/" in gi


class TestStaticContent:
    def test_styles_css_nonempty(self):
        css = (PROJECT / "static/css/styles.css").read_text(encoding="utf-8")
        assert len(css) > 100
        assert "topbar" in css or "--" in css

    def test_custom_js_has_theme_or_font(self):
        js = (PROJECT / "static/js/custom.js").read_text(encoding="utf-8")
        assert "THEME_KEY" in js or "theme" in js.lower()
        assert "FONT_KEY" in js or "font" in js.lower()

    def test_fonts_css_if_present(self):
        path = PROJECT / "static/css/fonts.css"
        if not path.is_file():
            pytest.skip("fonts.css not packaged")
        text = path.read_text(encoding="utf-8")
        assert "@font-face" in text

    def test_app_py_has_dir_mode(self):
        text = (PROJECT / "app.py").read_text(encoding="utf-8")
        assert "APP_DIR_MODE" in text
        assert 'APP_DIR_MODE = "ltr"' in text or "APP_DIR_MODE = 'ltr'" in text or "APP_DIR_MODE" in text


class TestRequirements:
    def test_lists_shiny_and_pillow(self):
        req = (PROJECT / "requirements.txt").read_text(encoding="utf-8").lower()
        assert "shiny" in req
        assert "pillow" in req
