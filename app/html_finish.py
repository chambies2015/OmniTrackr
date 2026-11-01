"""Last touches on every HTML page before it is compressed and sent.

Each step is a plain str -> str function that leaves a page it has nothing to
do for unchanged, so pages never depend on these steps to work.
"""
from __future__ import annotations

from .image_sizes import shrink_html
from .page_breadcrumbs import add_breadcrumbs
from .site_chrome import fill_join_prompt

STEPS = (shrink_html, add_breadcrumbs, fill_join_prompt)


def finish(html: str) -> str:
    for step in STEPS:
        try:
            html = step(html)
        except Exception:
            pass  # A page is always sent, with or without the extra markup.
    return html


class HtmlFinishMiddleware:
    """Run finish() on HTML pages on their way out.

    Public pages are built in many routers, and several of them fill in their
    lists, titles and canonical links after the shared header is applied, so the
    response is the one place every finished page passes through. It sits inside
    GZip, so it sees plain HTML, and leaves anything else (JSON, images,
    already-encoded bodies, other methods) alone.
    """

    MAX_BYTES = 4 * 1024 * 1024

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "GET":
            await self.app(scope, receive, send)
            return

        start = None
        chunks: list[bytes] = []
        passthrough = False

        async def wrapped_send(message):
            nonlocal start, passthrough
            if passthrough:
                await send(message)
                return
            if message["type"] == "http.response.start":
                headers = {k.lower(): v for k, v in message.get("headers", [])}
                content_type = headers.get(b"content-type", b"")
                if not content_type.startswith(b"text/html") or b"content-encoding" in headers:
                    passthrough = True
                    await send(message)
                    return
                start = message
                return
            if message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
                if sum(len(c) for c in chunks) > self.MAX_BYTES:
                    passthrough = True
                    await send(start)
                    await send({"type": "http.response.body", "body": b"".join(chunks), "more_body": message.get("more_body", False)})
                    return
                if message.get("more_body", False):
                    return
                body = b"".join(chunks)
                try:
                    text = body.decode("utf-8")
                    new_text = finish(text)
                    if new_text != text:
                        body = new_text.encode("utf-8")
                except UnicodeDecodeError:
                    pass
                headers = [(k, v) for k, v in start.get("headers", []) if k.lower() != b"content-length"]
                headers.append((b"content-length", str(len(body)).encode()))
                await send({**start, "headers": headers})
                await send({"type": "http.response.body", "body": body, "more_body": False})
                return
            await send(message)

        await self.app(scope, receive, wrapped_send)
