"""Make trailing-slash redirects permanent.

FastAPI answers /about/ with a 307 to /about. A 307 tells Google the move is
temporary, so it keeps the slash URL as its own page and splits links between
the two. For a GET or HEAD whose only change is the trailing slash, this sends
301 instead. Every other redirect, and every other method, is left alone.
"""
from __future__ import annotations

from urllib.parse import urlsplit


class PermanentSlashRedirectMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") not in ("GET", "HEAD"):
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")

        async def wrapped_send(message):
            if message["type"] == "http.response.start" and message.get("status") == 307:
                location = next((value for key, value in message.get("headers", []) if key.lower() == b"location"), b"")
                target = urlsplit(location.decode("latin-1")).path
                if target and target != path and target.rstrip("/") == path.rstrip("/"):
                    message = {**message, "status": 301}
            await send(message)

        await self.app(scope, receive, wrapped_send)
