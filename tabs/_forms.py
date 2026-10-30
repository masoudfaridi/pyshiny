"""Small helpers for admin forms (no Shiny server logic here)."""
from __future__ import annotations

from htmltools import Tag
from shiny import ui


def with_input_attrs(container: Tag, **attrs) -> Tag:
    """Set attributes on the ``<input>`` inside a Shiny input container.

    Used to stop the browser's password manager from filling the signed-in
    user's own login into forms that create / edit OTHER accounts (it used to
    put "superadmin" into the phone field and the saved password into
    "Password"): ``autocomplete="new-password"`` on password fields and
    ``autocomplete="off"`` on the text fields.
    """
    for child in container.children:
        if isinstance(child, Tag) and child.name == "input":
            child.attrs.update({k.replace("_", "-"): v for k, v in attrs.items()})
    return container


def password_input(input_id: str, label: str):
    return with_input_attrs(
        ui.input_password(input_id, label, width="100%"), autocomplete="new-password"
    )


def text_input(input_id: str, label: str, value: str = "", *, ltr: bool = False):
    tag = ui.input_text(input_id, label, value=value, width="100%", autocomplete="off")
    if ltr:  # e-mail / phone / codes stay readable inside an RTL page
        with_input_attrs(tag, dir="ltr")
    return tag


# Shiny hides the native <input type="file"> at left:-99999px (inline, !important).
# In a right-to-left page that position is SCROLLABLE: when the browser gives
# focus back to the input after the file dialog closes, it scrolls the content
# area ~100 000px sideways to show it -- the page looks blank. The input is
# therefore kept inside its "Browse" button instead (invisible, same size).
_FILE_INPUT_STYLE = (
    "position:absolute; inset:0; width:100%; height:100%; opacity:0; "
    "cursor:pointer; overflow:hidden;"
)


def _fix_file_inputs(node) -> None:
    for child in getattr(node, "children", []):
        if isinstance(child, Tag):
            if child.name == "input" and child.attrs.get("type") == "file":
                child.attrs["style"] = _FILE_INPUT_STYLE
            _fix_file_inputs(child)


def file_input(input_id: str, label: str, **kwargs) -> Tag:
    """``ui.input_file`` that is safe in RTL pages (see ``_FILE_INPUT_STYLE``)."""
    tag = ui.input_file(input_id, label, **kwargs)
    _fix_file_inputs(tag)
    return tag
