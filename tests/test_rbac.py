"""Role hierarchy, has_role, require_role decorators."""
from __future__ import annotations

import pytest

import auth.core as core


class TestRoleLevels:
    def test_ordering(self):
        assert core.ROLE_LEVELS["guest"] < core.ROLE_LEVELS["user"]
        assert core.ROLE_LEVELS["user"] < core.ROLE_LEVELS["admin"]
        assert core.ROLE_LEVELS["admin"] < core.ROLE_LEVELS["superadmin"]

    def test_known_roles_complete(self):
        assert set(core.ROLE_LEVELS) == {"guest", "user", "admin", "superadmin"}


class TestCurrentUserRole:
    def test_anonymous_is_guest(self, anonymous_ctx):
        assert core.current_user() is None
        assert core.current_role() == "guest"

    def test_authenticated_role(self, admin_ctx):
        assert core.current_role() == "admin"
        assert core.current_user()["username"] == "admin"


class TestHasRole:
    def test_superadmin_has_all(self, superadmin_ctx):
        for role in core.ROLE_LEVELS:
            assert core.has_role(role) is True

    def test_guest_only_guest(self, guest_ctx):
        assert core.has_role("guest") is True
        assert core.has_role("user") is False
        assert core.has_role("admin") is False
        assert core.has_role("superadmin") is False

    def test_user_level(self, user_ctx):
        assert core.has_role("guest") is True
        assert core.has_role("user") is True
        assert core.has_role("admin") is False

    def test_anonymous_has_no_role(self, anonymous_ctx):
        assert core.has_role("guest") is False  # no authenticated user
        assert core.has_role("user") is False

    def test_inactive_session_denied(self, isolated_db):
        user = core.authenticate("user", "User123!")
        user["is_active"] = 0
        with core.user_context(user):
            assert core.has_role("user") is False

    def test_expired_session_denied(self, isolated_db):
        user = core.authenticate("user", "User123!")
        user["expire_date"] = "2000-01-01"
        with core.user_context(user):
            assert core.has_role("user") is False


class TestRequireRoleDecorator:
    def test_superadmin_decorator_blocks_admin(self, admin_ctx):
        @core.superadmin
        def only_super():
            return "ok"

        with pytest.raises(PermissionError, match="superadmin"):
            only_super()

    def test_superadmin_decorator_allows_superadmin(self, superadmin_ctx):
        @core.superadmin
        def only_super():
            return "ok"

        assert only_super() == "ok"

    def test_admin_allows_superadmin(self, superadmin_ctx):
        @core.admin
        def admin_area():
            return "ok"

        assert admin_area() == "ok"

    def test_admin_blocks_user(self, user_ctx):
        @core.admin
        def admin_area():
            return "ok"

        with pytest.raises(PermissionError):
            admin_area()

    def test_user_blocks_guest_account(self, guest_ctx):
        @core.user
        def user_area():
            return "ok"

        with pytest.raises(PermissionError):
            user_area()

    def test_guest_decorator_allows_any_authenticated(self, guest_ctx):
        @core.guest
        def any_auth():
            return "ok"

        assert any_auth() == "ok"

    def test_guest_decorator_blocks_anonymous(self, anonymous_ctx):
        @core.guest
        def any_auth():
            return "ok"

        with pytest.raises(PermissionError):
            any_auth()
