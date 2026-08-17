"""Offline CAPTCHA generation and verification."""
from __future__ import annotations

import base64
import time

import pytest

import auth.captcha as captcha


class TestGenerateCaptcha:
    def test_returns_triple(self):
        data_url, answer_hash, expires_at = captcha.generate_captcha()
        assert isinstance(data_url, str)
        assert isinstance(answer_hash, str)
        assert isinstance(expires_at, float)

    def test_data_url_png(self):
        data_url, _, _ = captcha.generate_captcha()
        assert data_url.startswith("data:image/png;base64,")
        b64 = data_url.split(",", 1)[1]
        raw = base64.b64decode(b64)
        assert raw[:8] == b"\x89PNG\r\n\x1a\n"

    def test_hash_is_sha256_hex(self):
        _, answer_hash, _ = captcha.generate_captcha()
        assert len(answer_hash) == 64
        int(answer_hash, 16)  # valid hex

    def test_expiry_in_future(self):
        _, _, expires_at = captcha.generate_captcha()
        assert expires_at > time.time()
        assert expires_at <= time.time() + captcha.CAPTCHA_TTL_SECONDS + 1

    def test_unique_challenges(self):
        hashes = {captcha.generate_captcha()[1] for _ in range(5)}
        assert len(hashes) >= 2  # extremely unlikely to collide


class TestVerifyCaptcha:
    def test_roundtrip_with_known_answer(self, monkeypatch):
        # Force a known alphabet sequence via secrets.choice
        fixed = iter("ABCDE")
        monkeypatch.setattr(captcha.secrets, "choice", lambda seq: next(fixed))
        data_url, answer_hash, expires_at = captcha.generate_captcha()
        assert captcha.verify_captcha("ABCDE", answer_hash, expires_at) is True

    def test_case_insensitive(self, monkeypatch):
        fixed = iter("AB12C")
        monkeypatch.setattr(captcha.secrets, "choice", lambda seq: next(fixed))
        _, answer_hash, expires_at = captcha.generate_captcha()
        assert captcha.verify_captcha("ab12c", answer_hash, expires_at) is True
        assert captcha.verify_captcha("Ab12C", answer_hash, expires_at) is True

    def test_wrong_answer(self, monkeypatch):
        fixed = iter("ABCDE")
        monkeypatch.setattr(captcha.secrets, "choice", lambda seq: next(fixed))
        _, answer_hash, expires_at = captcha.generate_captcha()
        assert captcha.verify_captcha("ZZZZZ", answer_hash, expires_at) is False

    def test_expired(self, monkeypatch):
        fixed = iter("ABCDE")
        monkeypatch.setattr(captcha.secrets, "choice", lambda seq: next(fixed))
        _, answer_hash, expires_at = captcha.generate_captcha()
        past = time.time() - 10
        assert captcha.verify_captcha("ABCDE", answer_hash, past) is False

    def test_missing_hash_or_expiry(self):
        assert captcha.verify_captcha("ABCDE", None, time.time() + 100) is False
        assert captcha.verify_captcha("ABCDE", "abc", None) is False
        assert captcha.verify_captcha("ABCDE", None, None) is False

    def test_strips_whitespace(self, monkeypatch):
        fixed = iter("ABCDE")
        monkeypatch.setattr(captcha.secrets, "choice", lambda seq: next(fixed))
        _, answer_hash, expires_at = captcha.generate_captcha()
        assert captcha.verify_captcha("  ABCDE  ", answer_hash, expires_at) is True


class TestCaptchaConstants:
    def test_alphabet_has_no_ambiguous_chars(self):
        bad = set("0O1Il")
        assert not (set(captcha.CAPTCHA_ALPHABET) & bad)

    def test_length_positive(self):
        assert captcha.CAPTCHA_LENGTH >= 4
