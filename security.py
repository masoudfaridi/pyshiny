"""ASGI wrapper around the Shiny app: HTTP security headers + upload size cap.

``app.py`` exposes ``app = SecurityMiddleware(shiny_app)``; ``shiny run app.py``
(and uvicorn / gunicorn) serve it like the plain Shiny app.

* Security headers on every HTTP response (page, static files, uploads):
  no framing (clickjacking of the password dialogs), no MIME sniffing, no
  referrer leaks, no camera / microphone / location, isolated browsing context.
  ``Strict-Transport-Security`` is added only when ``HSTS=1`` (serve over HTTPS
  first, otherwise browsers would refuse plain-HTTP access for a year).
* File uploads: Shiny accepts an upload from ANY connected browser, signed in or
  not, and streams it to a temp file. Without a cap that is a free disk-filling
  attack. Upload requests larger than ``max_upload_bytes`` are refused with 413.

WebSocket traffic is passed through untouched.
"""
from __future__ import annotations

import os

_BASE_HEADERS = [
    (b"x-frame-options", b"DENY"),
    (
        b"content-security-policy",
        b"frame-ancestors 'none'; base-uri 'self'; object-src 'none'; form-action 'self'",
    ),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
    (b"cross-origin-opener-policy", b"same-origin"),
]
_HSTS = (b"strict-transport-security", b"max-age=31536000; includeSubDomains")


class SecurityMiddleware:
    def __init__(self, app, *, max_upload_bytes: int = 51 * 1024 * 1024):
        self.app = app
        self.max_upload_bytes = int(max_upload_bytes)
        self.headers = list(_BASE_HEADERS)
        if os.environ.get("HSTS", "").strip() == "1":
            self.headers.append(_HSTS)

    def __getattr__(self, name):
        # Keep attributes of the wrapped Shiny App reachable (app.ui, app.server ...).
        return getattr(self.app, name)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope.get("method") == "POST" and "/upload/" in scope.get("path", ""):
            length = None
            for key, value in scope.get("headers", []):
                if key == b"content-length":
                    try:
                        length = int(value)
                    except ValueError:
                        length = -1
            if length is not None and (length < 0 or length > self.max_upload_bytes):
                await self._reject(send, 413, b"Upload too large")
                return
            receive = self._limited(receive)

        extra = self.headers

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                present = {k.lower() for k, _ in message.get("headers", [])}
                message = dict(message)
                message["headers"] = list(message.get("headers", [])) + [
                    (k, v) for k, v in extra if k not in present
                ]
            await send(message)

        await self.app(scope, receive, send_with_headers)

    def _limited(self, receive):
        """Stop a body that grows past the cap even without (or lying in) Content-Length."""
        limit = self.max_upload_bytes
        received = 0

        async def wrapped():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise ValueError("upload exceeds the configured size limit")
            return message

        return wrapped

    async def _reject(self, send, status: int, body: bytes) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"text/plain"), *self.headers],
            }
        )
        await send({"type": "http.response.body", "body": body})
