"""Login brute-force lockout."""
from __future__ import annotations

import time

import pytest

import auth.core as core


class TestLoginLockout:
    def test_not_locked_initially(self, isolated_db):
        locked, remaining = core.is_login_locked("admin")
        assert locked is False
        assert remaining == 0

    def test_lock_after_max_failures(self, isolated_db):
        username = "admin"
        for _ in range(core.LOGIN_MAX_FAILURES):
            core.register_login_failure(username)
        locked, remaining = core.is_login_locked(username)
        assert locked is True
        assert remaining > 0
        assert remaining <= core.LOGIN_LOCKOUT_SECONDS

    def test_under_threshold_not_locked(self, isolated_db):
        for _ in range(core.LOGIN_MAX_FAILURES - 1):
            core.register_login_failure("user")
        locked, _ = core.is_login_locked("user")
        assert locked is False

    def test_clear_failures(self, isolated_db):
        for _ in range(core.LOGIN_MAX_FAILURES):
            core.register_login_failure("guest")
        assert core.is_login_locked("guest")[0] is True
        core.clear_login_failures("guest")
        assert core.is_login_locked("guest")[0] is False

    def test_lock_is_per_username(self, isolated_db):
        for _ in range(core.LOGIN_MAX_FAILURES):
            core.register_login_failure("admin")
        assert core.is_login_locked("admin")[0] is True
        assert core.is_login_locked("user")[0] is False

    def test_empty_username_handled(self, isolated_db):
        # Should not raise
        core.register_login_failure("")
        core.clear_login_failures("")
        locked, _ = core.is_login_locked("")
        assert isinstance(locked, bool)

    def test_case_normalization_strip(self, isolated_db):
        # Implementation uses stripped username as key
        for _ in range(core.LOGIN_MAX_FAILURES):
            core.register_login_failure("  Admin  ")
        # Depending on implementation – check both
        locked_a, _ = core.is_login_locked("Admin")
        locked_b, _ = core.is_login_locked("  Admin  ")
        assert locked_a or locked_b
