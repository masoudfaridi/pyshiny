"""Username and password validation rules."""
from __future__ import annotations

import pytest

import auth.core as core


class TestValidateUsername:
    @pytest.mark.parametrize(
        "username",
        ["abc", "user_1", "Admin-01", "a" * 32, "Z_9-x"],
    )
    def test_valid(self, username):
        assert core.validate_username(username) == username

    def test_strips_whitespace(self):
        assert core.validate_username("  alice  ") == "alice"

    @pytest.mark.parametrize(
        "username",
        [
            "",
            "ab",  # too short
            "a" * 33,  # too long
            "has space",
            "bad@name",
            "name!",
            "فارسی",
            "user.name",
        ],
    )
    def test_invalid(self, username):
        with pytest.raises(ValueError, match="Username"):
            core.validate_username(username)

    def test_none_raises(self):
        with pytest.raises(ValueError):
            core.validate_username(None)  # type: ignore[arg-type]


class TestValidatePassword:
    def test_length_only_non_strict(self):
        assert core.validate_password("abcdefgh", strict=False) == "abcdefgh"
        assert core.validate_password("12345678", strict=False) == "12345678"

    def test_too_short(self):
        with pytest.raises(ValueError, match="at least"):
            core.validate_password("short", strict=False)

    def test_too_long(self):
        with pytest.raises(ValueError, match="at most"):
            core.validate_password("x" * (core.PASSWORD_MAX_LEN + 1), strict=False)

    def test_empty_required(self):
        with pytest.raises(ValueError, match="required"):
            core.validate_password("", strict=False)

    def test_strict_requires_letter_and_digit(self):
        assert core.validate_password("abcde123", strict=True) == "abcde123"
        with pytest.raises(ValueError, match="letter and one number"):
            core.validate_password("onlyletters", strict=True)
        with pytest.raises(ValueError, match="letter and one number"):
            core.validate_password("12345678", strict=True)

    def test_custom_field_name_in_error(self):
        with pytest.raises(ValueError, match="New password"):
            core.validate_password("short", field_name="New password")


class TestNormalizeExpiry:
    def test_superadmin_always_none(self):
        assert core._normalize_expiry("2099-01-01", "superadmin") is None
        assert core._normalize_expiry(None, "superadmin") is None

    def test_empty_becomes_none(self):
        assert core._normalize_expiry("", "user") is None
        assert core._normalize_expiry(None, "admin") is None

    def test_valid_iso_date(self):
        assert core._normalize_expiry("2030-12-31", "user") == "2030-12-31"

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            core._normalize_expiry("31/12/2030", "user")
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            core._normalize_expiry("not-a-date", "user")


class TestIsExpired:
    def test_none_not_expired(self):
        assert core._is_expired(None) is False

    def test_past_date_expired(self):
        assert core._is_expired("2000-01-01") is True

    def test_future_date_not_expired(self):
        assert core._is_expired("2099-12-31") is False
