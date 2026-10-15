"""
Example 15 -- A bilingual (English / Persian) tab

Concepts
--------
* Reuse the project's language switch: ``APP_LANG`` from i18n.py ("en" or
  "fa"). Direction (RTL) is already handled by app.py -- you only translate
  the words.
* Keep the texts of a hand-made tab in a small dictionary INSIDE the tab file
  so you do not have to edit i18n.py. (Shared words such as "Username" can
  still come from ``i18n.t(...)``.)
* NAV_LABEL is evaluated once at import time, which is fine because the
  language is fixed when the server starts.
"""

from __future__ import annotations

from shiny import module, reactive, render, ui

from i18n import APP_LANG

NAV_ID = "tab_ex15"
NAV_LABEL = "Ex 15 Bilingual"  # replaced below by the translated label
NAV_ICON = "bi-translate"
NAV_GROUP = None
NAV_MIN_ROLE = "guest"

MODULE_ID = "tab_ex15"

_TEXT = {
    "en": {
        "nav": "Ex 15 Bilingual",
        "title": "Greeting card",
        "intro": "Everything on this page follows the language chosen in i18n.py.",
        "name": "Your name",
        "button": "Greet me",
        "hello": "Welcome, {name}!",
        "empty": "Please type a name first.",
    },
    "fa": {
        "nav": "مثال ۱۵ دو زبانه",
        "title": "کارت خوشامدگویی",
        "intro": "همه‌ی متن‌های این صفحه از زبانی که در i18n.py انتخاب شده پیروی می‌کنند.",
        "name": "نام شما",
        "button": "به من خوشامد بگو",
        "hello": "{name} عزیز، خوش آمدید!",
        "empty": "لطفاً ابتدا یک نام وارد کنید.",
    },
}


def _t(key: str, **kwargs) -> str:
    """Active language first, English as the fallback."""
    table = _TEXT.get(APP_LANG, _TEXT["en"])
    text = table.get(key) or _TEXT["en"][key]
    return text.format(**kwargs) if kwargs else text


NAV_LABEL = _t("nav")


@module.ui
def _ui():
    return ui.div(
        ui.h3(_t("title")),
        ui.p(_t("intro")),
        ui.div(
            ui.input_text("person", _t("name")),
            ui.input_action_button("greet", _t("button"), class_="btn btn-primary"),
            ui.output_ui("answer"),
            class_="user-form-card",
        ),
        class_="tab-pane-content",
    )


@module.server
def _server(input, output, session):
    greeting = reactive.Value("")

    @reactive.effect
    @reactive.event(input.greet)
    def _greet():
        person = (input.person() or "").strip()
        greeting.set(_t("hello", name=person) if person else _t("empty"))

    @render.ui
    def answer():
        text = greeting()
        return ui.p(text, class_="mt-3") if text else ui.div()


def panel():
    return _ui(MODULE_ID)


def server():
    _server(MODULE_ID)
