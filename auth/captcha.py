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

from PIL import Image, ImageDraw, ImageFont

# Unambiguous alphabet (no 0/O, 1/I/l).
CAPTCHA_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CAPTCHA_LENGTH = 5
CAPTCHA_TTL_SECONDS = 300  # 5 minutes

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

    width, height = 180, 56
    image = Image.new("RGB", (width, height), (248, 250, 252))
    draw = ImageDraw.Draw(image)

    # Light background noise dots.
    for _ in range(40):
        x, y = random.randint(0, width - 1), random.randint(0, height - 1)
        draw.point((x, y), fill=(random.randint(160, 200),) * 3)

    # A few interference lines.
    for _ in range(3):
        draw.line(
            (
                random.randint(0, width // 3),
                random.randint(0, height - 1),
                random.randint(width // 2, width - 1),
                random.randint(0, height - 1),
            ),
            fill=(random.randint(140, 180),) * 3,
            width=1,
        )

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 28)
    except OSError:
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 28)
        except OSError:
            font = ImageFont.load_default()

    # Draw each character with slight position jitter.
    x = 14
    for ch in text:
        y = random.randint(8, 16)
        # Pillow >=10 removed ImageDraw.textsize; use textbbox / default font metrics.
        draw.text((x, y), ch, font=font, fill=(30, 41, 59))
        x += 30 + random.randint(-2, 4)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(
        "ascii"
    )
    return data_url, answer_hash, expires_at
