"""tab_07: the four decorated actions follow the role hierarchy (fail-closed)."""
from __future__ import annotations

import pytest

import auth.core as core
from tabs import tab_07

ACTIONS = {
    "superadmin": tab_07._superadmin_action,
    "admin": tab_07._admin_action,
    "user": tab_07._user_action,
    "guest": tab_07._guest_action,
}

# role of the logged-in account -> actions it may run
ALLOWED = {
    "superadmin": {"superadmin", "admin", "user", "guest"},
    "admin": {"admin", "user", "guest"},
    "user": {"user", "guest"},
    "guest": {"guest"},
}

CREDENTIALS = {
    "superadmin": "ChangeMe123!",
    "admin": "Admin123!",
    "user": "User123!",
    "guest": "Guest123!",
}


def test_tab_is_visible_to_everyone():
    assert tab_07.NAV_MIN_ROLE == "guest"


@pytest.mark.parametrize("role", list(ALLOWED))
@pytest.mark.parametrize("action_role", list(ACTIONS))
def test_role_matrix(isolated_db, role, action_role):
    account = core.authenticate(role, CREDENTIALS[role])
    with core.user_context(account):
        if action_role in ALLOWED[role]:
            assert ACTIONS[action_role]()
        else:
            with pytest.raises(PermissionError):
                ACTIONS[action_role]()


@pytest.mark.parametrize("action_role", list(ACTIONS))
def test_no_session_is_denied(isolated_db, action_role):
    with core.user_context(None):
        with pytest.raises(PermissionError):
            ACTIONS[action_role]()


def test_attempt_notifies_denied_and_skips_action(isolated_db, monkeypatch):
    shown = []
    monkeypatch.setattr(
        tab_07.ui, "notification_show", lambda msg, **kw: shown.append((msg, kw["type"]))
    )
    ran = []

    @core.superadmin
    def protected():
        ran.append(True)
        return "done"

    guest_user = core.authenticate("guest", "Guest123!")
    tab_07._attempt(protected, lambda: guest_user)
    assert ran == []
    assert shown == [(tab_07._tx("denied"), "error")]


def test_attempt_without_session_asks_to_sign_in(isolated_db, monkeypatch):
    shown = []
    monkeypatch.setattr(
        tab_07.ui, "notification_show", lambda msg, **kw: shown.append((msg, kw["type"]))
    )
    tab_07._attempt(tab_07._guest_action, lambda: None)
    assert shown == [(tab_07._tx("signin"), "error")]
