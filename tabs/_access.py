"""Server-side access gate for content-tab modules.

Hiding a sidebar link is NOT access control: every module server is registered
for every browser session (signed in or not), and a crafted page can still bind
a hidden output id (e.g. ``tab_01-hist``) or fire an input (``tab_01-generate``).
Each content tab therefore re-checks the role on the server, in every output
and effect, using the re-validated session user from app.py.
"""
from __future__ import annotations

from typing import Callable

from auth import ROLE_LEVELS


def gate(get_session_user: Callable[[], dict | None] | None, min_role: str) -> Callable[[], bool]:
    """Return ``allowed()``: True only for a valid session with role >= ``min_role``.

    Fail-closed: without a ``get_session_user`` function nothing is allowed.
    """
    required = ROLE_LEVELS[min_role]

    def allowed() -> bool:
        if get_session_user is None:
            return False
        person = get_session_user()
        return bool(person) and ROLE_LEVELS.get(person.get("role"), -1) >= required

    return allowed


def finite(value) -> float:
    """``float(value)`` that rejects None, NaN and +/-inf (raises ValueError/TypeError)."""
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError("not a finite number")
    return number
