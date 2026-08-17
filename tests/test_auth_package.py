"""Cross-cutting auth package smoke tests."""
from __future__ import annotations

import auth.core as core


def test_login_constants_sane():
    assert core.LOGIN_MAX_FAILURES >= 3
    assert core.LOGIN_LOCKOUT_SECONDS >= 60
    assert core.PASSWORD_MIN_LEN >= 6
    assert core.PASSWORD_MAX_LEN >= core.PASSWORD_MIN_LEN


def test_user_context_resets(isolated_db):
    user = core.authenticate("admin", "Admin123!")
    assert core.current_user() is None
    with core.user_context(user):
        assert core.current_user()["username"] == "admin"
    assert core.current_user() is None


def test_nested_user_context(isolated_db):
    admin = core.authenticate("admin", "Admin123!")
    guest = core.authenticate("guest", "Guest123!")
    with core.user_context(admin):
        assert core.current_role() == "admin"
        with core.user_context(guest):
            assert core.current_role() == "guest"
        assert core.current_role() == "admin"
