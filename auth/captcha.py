"""Offline image CAPTCHA generator (no external network services)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import os
import random
import secrets
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Unambiguous alphabet (no 0/O, 1/I/l).
CAPTCHA_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CAPTCHA_LENGTH = 5
CAPTCHA_TTL_SECONDS = 300  # 5 minutes

# Size of the image as it is SHOWN in the browser (CSS pixels). Keep in sync
# with .login-captcha-image in static/css/styles.css.
CAPTCHA_WIDTH, CAPTCHA_HEIGHT = 300, 72  # wide: fills the login card's row

# A font file ships with the project so the letters are large and identical on
# every OS. (Docker "slim" images and Windows have no DejaVu; without a font
# Pillow would fall back to a tiny 10px bitmap font -- the old "too small" bug.)
_BUNDLED_FONT = Path(__file__).resolve().parent / "fonts" / "DejaVuSans-Bold.ttf"
_FONT_CANDIDATES = (
    str(_BUNDLED_FONT),
    "DejaVuSans-Bold.ttf",
    "arialbd.ttf",
    "Arial Bold.ttf",
    "LiberationSans-Bold.ttf",
    "Helvetica.ttc",
)


def _load_font(size: int) -> ImageFont.ImageFont:
    """Return a scalable bold font of ``size`` pixels (never the tiny default)."""
    for candidate in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    try:  # Pillow >= 10.1 can scale its built-in font.
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow: last resort
        return ImageFont.load_default()

# Server-side secret for hashing answers (rotated each process start is fine).
_CAPTCHA_SECRET = os.urandom(32)


def _hash_answer(answer: str) -> str:
    normalized = (answer or "").strip().upper()
    return hmac.new(
        _CAPTCHA_SECRET, normalized.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def verify_captcha(answer: str, expected_hash: str | None, expires_at: float | None) -> bool:
    """Return True when the answer matches and the challenge is still valid."""
    if not expected_hash or not expires_at:
        return False
    if time.time() > float(expires_at):
        return False
    candidate = _hash_answer(answer)
    return hmac.compare_digest(candidate, expected_hash)


def generate_captcha() -> tuple[str, str, float]:
    """Create a new CAPTCHA challenge.

    Returns:
        image_data_url: PNG as a data URL for <img src="...">
        answer_hash: HMAC hash of the correct answer (store in session only)
        expires_at: unix timestamp when the challenge becomes invalid
    """
    text = "".join(secrets.choice(CAPTCHA_ALPHABET) for _ in range(CAPTCHA_LENGTH))
    answer_hash = _hash_answer(text)
    expires_at = time.time() + CAPTCHA_TTL_SECONDS

    # Draw at 2x and let the browser scale it down: crisp on high-DPI screens.
    scale = 2
    width, height = CAPTCHA_WIDTH * scale, CAPTCHA_HEIGHT * scale
    image = Image.new("RGB", (width, height), (248, 250, 252))
    draw = ImageDraw.Draw(image)

    # Light background noise dots (kept pale so the letters stay readable).
    for _ in range(60):
        x, y = random.randint(0, width - 1), random.randint(0, height - 1)
        draw.point((x, y), fill=(random.randint(170, 210),) * 3)

    font = _load_font(44 * scale)

    # Interference lines are drawn BEFORE the letters so they never cover them.
    for _ in range(3):
        draw.line(
            (
                random.randint(0, width // 4),
                random.randint(0, height - 1),
                random.randint(width // 2, width - 1),
                random.randint(0, height - 1),
            ),
            fill=(random.randint(170, 200),) * 3,
            width=2,
        )

    # Spread the characters evenly over the image, with a little jitter.
    slot = width / (len(text) + 0.4)
    for index, ch in enumerate(text):
        left, top, right, bottom = draw.textbbox((0, 0), ch, font=font)
        char_w, char_h = right - left, bottom - top
        x = slot * (index + 0.35) + (slot - char_w) / 2 - left + random.randint(-3, 3)
        y = (height - char_h) / 2 - top + random.randint(-6 * scale, 6 * scale)
        draw.text((x, y), ch, font=font, fill=(30, 41, 59))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(
        "ascii"
    )
    return data_url, answer_hash, expires_at
