"""Password hashing and verification."""
from __future__ import annotations

import pytest

import auth.core as core


class TestHashPassword:
    def test_format_scheme(self):
        encoded = core._hash_password("Secret123!")
        parts = encoded.split("$")
        assert len(parts) == 4
        assert parts[0] == "pbkdf2_sha256"
        assert parts[1].isdigit()
        assert int(parts[1]) >= 100_000
        assert len(parts[2]) == 32  # 16-byte salt hex
        assert len(parts[3]) == 64  # sha256 hex

    def test_unique_salt_each_call(self):
        a = core._hash_password("SamePassword1")
        b = core._hash_password("SamePassword1")
        assert a != b

    def test_deterministic_with_fixed_salt(self):
        salt = b"\x00" * 16
        a = core._hash_password("FixedSaltPwd1", salt=salt)
        b = core._hash_password("FixedSaltPwd1", salt=salt)
        assert a == b


class TestVerifyPassword:
    def test_correct_password(self):
        encoded = core._hash_password("CorrectHorse1")
        assert core._verify_password("CorrectHorse1", encoded) is True

    def test_wrong_password(self):
        encoded = core._hash_password("CorrectHorse1")
        assert core._verify_password("wrong-password", encoded) is False

    def test_empty_password_against_hash(self):
        encoded = core._hash_password("NotEmpty12")
        assert core._verify_password("", encoded) is False

    def test_malformed_hash_returns_false(self):
        assert core._verify_password("anything", "not-a-valid-hash") is False
        assert core._verify_password("anything", "only$two") is False
        assert core._verify_password("anything", "") is False

    def test_wrong_scheme_returns_false(self):
        encoded = core._hash_password("Abcdef12")
        tampered = encoded.replace("pbkdf2_sha256", "bcrypt")
        assert core._verify_password("Abcdef12", tampered) is False

    def test_dummy_hash_is_valid_encoding(self):
        assert core._DUMMY_PASSWORD_HASH.startswith("pbkdf2_sha256$")
        assert core._verify_password("timing-protection-dummy-value", core._DUMMY_PASSWORD_HASH)


class TestChangeOwnPassword:
    def test_success(self, user_ctx):
        core.change_own_password("User123!", "NewPass99")
        assert core.authenticate("user", "NewPass99") is not None
        assert core.authenticate("user", "User123!") is None

    def test_wrong_current_password(self, user_ctx):
        with pytest.raises(ValueError, match="[Cc]urrent password"):
            core.change_own_password("WrongOld99", "NewPass99")

    def test_strict_complexity_required(self, user_ctx):
        with pytest.raises(ValueError, match="letter and one number"):
            core.change_own_password("User123!", "allletters")
        with pytest.raises(ValueError, match="letter and one number"):
            core.change_own_password("User123!", "12345678")

    def test_requires_authentication(self, anonymous_ctx):
        with pytest.raises(PermissionError):
            core.change_own_password("User123!", "NewPass99")
