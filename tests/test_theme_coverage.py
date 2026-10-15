"""Theme coverage: every widget class must follow the selected theme (see styles.css "THEME BRIDGE")."""
from __future__ import annotations

import base64
import io
import re
from pathlib import Path

import pytest
from PIL import Image, ImageFont

PROJECT = Path(__file__).resolve().parent.parent
CSS = (PROJECT / "static/css/styles.css").read_text(encoding="utf-8")
JS = (PROJECT / "static/js/custom.js").read_text(encoding="utf-8")
APP = (PROJECT / "app.py").read_text(encoding="utf-8")

THEMES = [
    "light-blue", "light-green", "light-purple", "light-orange", "light-teal", "light-rose",
    "dark-slate", "dark-ocean", "dark-emerald", "dark-purple", "dark-amber", "dark-rose",
]
REQUIRED_VARS = [
    "--border", "--accent", "--accent-hover", "--text", "--text-muted", "--sidebar-bg",
    "--page-bg", "--surface", "--surface-hover", "--sidebar-text", "--active-text",
]

# Widget classes that must have an explicit rule in the stylesheet.
REQUIRED_SELECTORS = [
    ".form-control", ".shiny-input-number", ".shiny-input-text", ".shiny-input-password",
    ".shiny-input-textarea", ".form-select", ".form-check-input", ".form-check-label",
    ".selectize-input", ".selectize-dropdown", ".irs--shiny .irs-bar", ".irs--shiny .irs-handle",
    ".irs--shiny .irs-single", ".datepicker", ".btn-default", ".btn-secondary", ".btn-primary",
    ".action-label", ".shiny-download-link", ".input-group-text", ".progress-bar", ".card",
    ".accordion", ".nav-tabs", ".nav-pills", ".table", ".modal-content", ".shiny-notification",
    ".dropdown-menu", ".popover", ".list-group", ".sidebar-toggle-btn", ".app-sidebar", ".app-main",
    ".sidebar-collapsed", ".sidebar-link.active",
    "input:-webkit-autofill", "color-scheme",
]


def _theme_block(name: str) -> str:
    match = re.search(r'html\[data-theme="%s"\]\s*\{(.*?)\}' % re.escape(name), CSS, re.S)
    assert match, f"theme block for {name} not found"
    return match.group(1)


@pytest.mark.parametrize("theme", THEMES)
def test_theme_defines_all_base_variables(theme):
    block = _theme_block(theme)
    for var in REQUIRED_VARS:
        assert f"{var}:" in block, f"{theme} is missing {var}"


@pytest.mark.parametrize("theme", [t for t in THEMES if t.startswith("dark")])
def test_dark_themes_define_input_background(theme):
    assert "--input-bg:" in _theme_block(theme)


@pytest.mark.parametrize("selector", REQUIRED_SELECTORS)
def test_widget_selector_is_styled(selector):
    assert selector in CSS, f"no rule for {selector}"


def test_dark_themes_switch_native_color_scheme():
    assert re.search(r'html\[data-theme\^="dark"\]\s*\{\s*color-scheme:\s*dark', CSS)


def test_css_braces_are_balanced():
    stripped = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    assert stripped.count("{") == stripped.count("}")


def test_theme_switch_also_sets_bootstrap_theme():
    assert 'setAttribute("data-bs-theme"' in JS


def test_sidebar_toggle_is_wired_end_to_end():
    assert 'id="sidebar-toggle-btn"' in APP
    assert 'id="app-sidebar"' in APP and "app-main" in APP
    assert 'getElementById("sidebar-toggle-btn")' in JS
    assert "sidebar-collapsed" in JS and ".app-shell.sidebar-collapsed" in CSS


def test_sidebar_does_not_depend_on_bslib_layout():
    """bslib's collapsible layout left the menu hidden after a toggle; we use our own."""
    assert "ui.layout_sidebar(" not in APP
    assert ".bslib-sidebar-layout" not in CSS


def test_menu_links_cannot_be_recoloured_by_widget_rules():
    # The whole dashboard lives inside a .shiny-html-output; a link rule on it
    # recoloured the menu (active item became unreadable).
    assert not re.search(r"\.shiny-html-output\s+a\b", CSS)
    assert re.search(r"html \.sidebar-link\.active[^{]*\{[^}]*color:var\(--active-text\)", CSS)


def test_tab_content_fills_the_page():
    block = re.search(r"\.tab-pane-content\s*\{(.*?)\}", CSS, re.S).group(1)
    assert "max-width:none" in block.replace(" ", "")
    assert "720px" not in block


class TestCaptcha:
    def test_font_ships_with_the_project(self):
        assert (PROJECT / "auth/fonts/DejaVuSans-Bold.ttf").is_file()
        assert (PROJECT / "auth/fonts/DejaVu-LICENSE.txt").is_file()

    def test_font_is_scalable_not_tiny_default(self):
        from auth.captcha import _load_font

        assert isinstance(_load_font(88), ImageFont.FreeTypeFont)

    def test_image_is_large_and_hi_res(self):
        from auth.captcha import CAPTCHA_HEIGHT, CAPTCHA_WIDTH, generate_captcha

        url, _, _ = generate_captcha()
        image = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
        assert image.size == (CAPTCHA_WIDTH * 2, CAPTCHA_HEIGHT * 2)
        assert f"{CAPTCHA_WIDTH}px" in CSS and f"{CAPTCHA_WIDTH} / {CAPTCHA_HEIGHT}" in CSS
