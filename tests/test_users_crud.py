"""User create / list / update / delete (Superadmin-only)."""
from __future__ import annotations

import sqlite3

import pytest

import auth.core as core
from tests.conftest import contact


class TestCreateUser:
    def test_create_success(self, superadmin_ctx):
        core.create_user("newbie", "Passw0rd!", "user", expire_date="2099-01-01", **contact("newbie"))
        session = core.authenticate("newbie", "Passw0rd!")
        assert session is not None
        assert session["role"] == "user"
        assert session["expire_date"] == "2099-01-01"

    def test_duplicate_username(self, superadmin_ctx):
        core.create_user("dupuser", "Passw0rd1", "user", **contact("dupuser"))
        with pytest.raises(Exception):
            core.create_user("dupuser", "Passw0rd2", "user", **contact("dupuser_2"))

    def test_invalid_role(self, superadmin_ctx):
        with pytest.raises(ValueError, match="[Ii]nvalid role"):
            core.create_user("xuser", "Passw0rd1", "root", **contact("xuser"))

    def test_invalid_username(self, superadmin_ctx):
        with pytest.raises(ValueError, match="Username"):
            core.create_user("x", "Passw0rd1", "user", **contact("x"))

    def test_short_password(self, superadmin_ctx):
        with pytest.raises(ValueError, match="at least"):
            core.create_user("shortpwd", "123", "user", **contact("shortpwd"))

    def test_non_superadmin_forbidden(self, admin_ctx):
        with pytest.raises(PermissionError):
            core.create_user("blocked", "Passw0rd1", "user", **contact("blocked"))

    def test_superadmin_created_without_expiry(self, superadmin_ctx):
        core.create_user("sa2", "Passw0rd1", "superadmin", expire_date="2099-01-01", **contact("sa2"))
        # normalize forces None for superadmin
        with sqlite3.connect(core.DB_PATH) as con:
            row = con.execute(
                "SELECT expire_date FROM users WHERE username='sa2'"
            ).fetchone()
        assert row[0] is None


class TestListUsers:
    def test_lists_defaults(self, superadmin_ctx):
        users = core.list_users()
        names = {u["username"] for u in users}
        assert {"superadmin", "admin", "user", "guest"}.issubset(names)

    def test_no_password_hash_exposed(self, superadmin_ctx):
        for u in core.list_users():
            assert "password_hash" not in u

    def test_forbidden_for_admin(self, admin_ctx):
        with pytest.raises(PermissionError):
            core.list_users()


class TestUpdateUser:
    def test_rename_and_role(self, superadmin_ctx):
        core.create_user("toupdate", "Passw0rd1", "user", **contact("toupdate"))
        uid = core.authenticate("toupdate", "Passw0rd1")["id"]
        core.update_user(uid, "renamed", "admin", True, new_password="", expire_date=None)
        assert core.authenticate("toupdate", "Passw0rd1") is None
        session = core.authenticate("renamed", "Passw0rd1")
        assert session is not None
        assert session["role"] == "admin"

    def test_password_change_by_admin(self, superadmin_ctx):
        core.create_user("pwchange", "OldPass12", "user", **contact("pwchange"))
        uid = core.authenticate("pwchange", "OldPass12")["id"]
        core.update_user(uid, "pwchange", "user", True, new_password="NewPass99", expire_date=None)
        assert core.authenticate("pwchange", "OldPass12") is None
        assert core.authenticate("pwchange", "NewPass99") is not None

    def test_deactivate(self, superadmin_ctx):
        core.create_user("todeact", "Passw0rd1", "user", **contact("todeact"))
        uid = core.authenticate("todeact", "Passw0rd1")["id"]
        core.update_user(uid, "todeact", "user", False, new_password="", expire_date=None)
        assert core.authenticate("todeact", "Passw0rd1") is None

    def test_missing_user(self, superadmin_ctx):
        with pytest.raises(ValueError, match="not found"):
            core.update_user(999999, "ghost", "user", True, new_password="", expire_date=None)

    def test_cannot_demote_last_superadmin(self, superadmin_ctx):
        me = core.current_user()
        with pytest.raises(ValueError, match="Superadmin"):
            core.update_user(me["id"], "superadmin", "admin", True, new_password="", expire_date=None)

    def test_cannot_deactivate_last_superadmin(self, superadmin_ctx):
        me = core.current_user()
        with pytest.raises(ValueError, match="Superadmin"):
            core.update_user(me["id"], "superadmin", "superadmin", False, new_password="", expire_date=None)


class TestDeleteUser:
    def test_delete_success(self, superadmin_ctx):
        core.create_user("todelete", "Passw0rd1", "user", **contact("todelete"))
        uid = core.authenticate("todelete", "Passw0rd1")["id"]
        core.delete_user(uid)
        assert core.authenticate("todelete", "Passw0rd1") is None

    def test_cannot_delete_self(self, superadmin_ctx):
        me = core.current_user()
        with pytest.raises(ValueError, match="cannot delete"):
            core.delete_user(me["id"])

    def test_cannot_delete_last_active_superadmin_other(self, superadmin_ctx):
        """Deleting the only other active superadmin is allowed only if >1 exist.

        When a second superadmin exists, deletion succeeds. After that, the
        remaining one cannot be deleted by another session – simulate by
        switching context to a non-self superadmin attempting to delete the last.
        """
        core.create_user("sa_other", "Passw0rd1", "superadmin", **contact("sa_other"))
        other = core.authenticate("sa_other", "Passw0rd1")
        assert other is not None
        # Two active superadmins: deleting the other is OK
        core.delete_user(other["id"])
        # Recreate as the sole extra, then remove until one remains and protect it
        core.create_user("sa_other2", "Passw0rd1", "superadmin", **contact("sa_other2"))
        other2 = core.authenticate("sa_other2", "Passw0rd1")
        # Switch to other2 and try to delete original superadmin while both active – OK
        with core.user_context(other2):
            me = core.authenticate("superadmin", "ChangeMe123!")
            core.delete_user(me["id"])
        # Now only sa_other2 is active superadmin – cannot delete self
        with core.user_context(other2):
            with pytest.raises(ValueError, match="cannot delete"):
                core.delete_user(other2["id"])

    def test_missing_user(self, superadmin_ctx):
        with pytest.raises(ValueError, match="not found"):
            core.delete_user(999999)

    def test_forbidden_for_non_superadmin(self, admin_ctx):
        with pytest.raises(PermissionError):
            core.delete_user(1)
