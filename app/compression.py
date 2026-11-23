"""Gzip for every response, with the compressed copy of each script and stylesheet kept.

Render's edge in front of the app does not cache /static/ (every request reaches
uvicorn), so before this the server gzipped the same files again for every new
visitor. That ran at level 9 on the event loop: about 20 ms each for the
dashboard's bundled stylesheet and script and a few ms for each of its ~50 other
scripts, so a phone opening the dashboard on a cold cache cost the server well
over 100 ms of compression while its data requests waited behind it.

Scripts, stylesheets, SVGs, icons and the web manifest are now compressed once
per distinct body and served from memory after that. The cache is keyed by a hash
of the uncompressed body, so it can never hand out stale bytes: an edited file
or a new bundle is a new key. Everything else (pages, JSON) still goes through
Starlette's GZipMiddleware, at level 6 instead of 9; pages are built per request,
so their compressed form can't be reused, and level 9 took about 40% more time
for about 1% fewer bytes.

Since Nov 23 2026 scripts and stylesheets are minified before they are compressed
(app/minify.py), and browsers that accept Brotli get a Brotli copy of each asset
at level 11: 14% smaller than gzip for the signed-in app's scripts, 24% for its
stylesheet. Level 11 is slow (about a second for that stylesheet), so the first
request for a new body gets gzip while one background thread makes the Brotli
copy, and every request after that gets Brotli. BROTLI_ASSETS=off goes back to
gzip only.
"""
from __future__ import annotations

import hashlib
import os
import threading
import zlib
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

import anyio.to_thread
from starlette.datastructures import Headers, MutableHeaders
from starlette.middleware.gzip import GZipMiddleware

from . import minify

try:
    import brotli
except ImportError:  # Gzip only.
    brotli = None

DYNAMIC_LEVEL = 6
ASSET_LEVEL = 9
BROTLI_LEVEL = 11
MINIMUM_SIZE = 500
# Bodies at least this big are compressed off the event loop (Starlette's own threshold).
THREAD_MINIMUM_SIZE = 128 * 1024
# The biggest asset is the dashboard stylesheet bundle (about 630 KB); anything larger
# is sent as it comes instead of being held in memory.
MAX_ASSET_BYTES = 2 * 1024 * 1024
# Compressed copies kept in memory. Every script and stylesheet the site serves comes
# to about 1.5 MB compressed, so a deploy's worth of old versions fits several times over.
CACHE_BYTES = 12 * 1024 * 1024

ASSET_SUFFIXES = (".js", ".css", ".svg", ".ico", ".webmanifest", ".map", ".txt", ".xml", ".json")
COMPRESSIBLE_TYPES = {
    "application/javascript",
    "text/javascript",
    "text/css",
    "image/svg+xml",
    "image/x-icon",
    "image/vnd.microsoft.icon",
    "application/manifest+json",
    "application/json",
    "text/plain",
    "application/xml",
    "text/xml",
}


def is_asset_path(path: str) -> bool:
    """Files served as they are: everything under /static/ and root files like /app.js."""
    if path.startswith("/static/profile_pictures/"):
        return False
    if path.startswith("/static/"):
        return True
    return path.count("/") == 1 and path.endswith(ASSET_SUFFIXES)


class CompressedCopies:
    """A size-bounded, least-recently-used map from body hash to gzipped body."""

    def __init__(self, max_bytes: int = CACHE_BYTES):
        self.max_bytes = max_bytes
        self.size = 0
        self.entries: OrderedDict[bytes, bytes] = OrderedDict()
        self.lock = threading.Lock()

    @staticmethod
    def key(body: bytes) -> bytes:
        return hashlib.blake2b(body, digest_size=20).digest()

    def get(self, key: bytes) -> bytes | None:
        with self.lock:
            found = self.entries.get(key)
            if found is not None:
                self.entries.move_to_end(key)
            return found

    def put(self, key: bytes, compressed: bytes) -> None:
        if len(compressed) > self.max_bytes:
            return
        with self.lock:
            if key in self.entries:
                return
            self.entries[key] = compressed
            self.size += len(compressed)
            while self.size > self.max_bytes and self.entries:
                _, dropped = self.entries.popitem(last=False)
                self.size -= len(dropped)

    def clear(self) -> None:
        with self.lock:
            self.entries.clear()
            self.size = 0


copies = CompressedCopies()


def gzip_bytes(body: bytes, level: int = ASSET_LEVEL) -> bytes:
    compressor = zlib.compressobj(level, zlib.DEFLATED, 16 + zlib.MAX_WBITS)
    return compressor.compress(body) + compressor.flush()


async def compressed_copy(body: bytes) -> bytes:
    key = CompressedCopies.key(body)
    found = copies.get(key)
    if found is not None:
        return found
    if len(body) >= THREAD_MINIMUM_SIZE:
        compressed = await anyio.to_thread.run_sync(gzip_bytes, body)
    else:
        compressed = gzip_bytes(body)
    copies.put(key, compressed)
    return compressed


brotli_copies = CompressedCopies()
_brotli_pending: set[bytes] = set()
_brotli_lock = threading.Lock()
# One thread, so a deploy's worth of new files is compressed one at a time in the background.
_brotli_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="brotli-assets")


def brotli_enabled() -> bool:
    return brotli is not None and os.getenv("BROTLI_ASSETS", "on").strip().lower() not in {"0", "off", "false", "no"}


def _make_brotli_copy(key: bytes, body: bytes) -> None:
    try:
        brotli_copies.put(key, brotli.compress(body, quality=BROTLI_LEVEL))
    except Exception:  # pragma: no cover - gzip keeps being served.
        pass
    finally:
        with _brotli_lock:
            _brotli_pending.discard(key)


def brotli_copy(body: bytes) -> bytes | None:
    """The kept Brotli copy of body, or None while it is being made (serve gzip meanwhile)."""
    key = CompressedCopies.key(body)
    found = brotli_copies.get(key)
    if found is not None:
        return found
    with _brotli_lock:
        if key in _brotli_pending:
            return None
        _brotli_pending.add(key)
    _brotli_worker.submit(_make_brotli_copy, key, body)
    return None


def wait_for_brotli() -> None:
    """Block until the background Brotli copies asked for so far exist (used by tests)."""
    _brotli_worker.submit(lambda: None).result()


def accepted_encodings(header: str) -> set[str]:
    """Content codings an Accept-Encoding header allows ("br;q=0" doesn't count)."""
    found = set()
    for part in header.lower().split(","):
        name, _, params = part.partition(";")
        name = name.strip()
        weight = 1.0
        for param in params.split(";"):
            key, _, value = param.partition("=")
            if key.strip() == "q":
                try:
                    weight = float(value)
                except ValueError:
                    weight = 0.0
        if name and weight > 0:
            found.add(name)
    return found


async def minified_copy(body: bytes, kind: str) -> bytes:
    found = minify.cached(body, kind)
    if found is not None:
        return found
    if len(body) >= THREAD_MINIMUM_SIZE:
        return await anyio.to_thread.run_sync(minify.minified, body, kind)
    return minify.minified(body, kind)


def _without_range(scope):
    """The request with Range headers dropped, so a minified file is always sent whole."""
    headers = [(name, value) for name, value in scope["headers"] if name not in (b"range", b"if-range")]
    if len(headers) == len(scope["headers"]):
        return scope
    return {**scope, "headers": headers}


class CompressionMiddleware:
    def __init__(self, app, minimum_size: int = MINIMUM_SIZE, compresslevel: int = DYNAMIC_LEVEL):
        self.app = app
        self.minimum_size = minimum_size
        self.dynamic = GZipMiddleware(app, minimum_size=minimum_size, compresslevel=compresslevel)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("method") == "GET" and is_asset_path(scope.get("path", "")):
            path = scope["path"]
            encodings = accepted_encodings(Headers(scope=scope).get("accept-encoding", ""))
            minifying = minify.enabled() and path.endswith((".js", ".css")) and path not in minify.SKIP_PATHS
            if minifying:
                scope = _without_range(scope)
            if minifying or "gzip" in encodings:
                await AssetResponder(self.app, self.minimum_size, encodings, minifying)(scope, receive, send)
                return
        await self.dynamic(scope, receive, send)


class AssetResponder:
    """Collect a text asset's body, then send the kept minified and compressed copy of it.

    Images, fonts, partial and conditional responses, bodies that are already
    encoded and anything over MAX_ASSET_BYTES pass through untouched, as they
    would have through GZipMiddleware (which skips the same media types).
    """

    def __init__(self, app, minimum_size: int, encodings: set[str] | None = None, minifying: bool = False):
        self.app = app
        self.minimum_size = minimum_size
        self.encodings = {"gzip"} if encodings is None else encodings
        self.minifying = minifying
        self.kind = None
        self.path = ""
        self.send = None
        self.start = None
        self.chunks: list[bytes] = []
        self.buffered = 0
        self.passthrough = False

    async def __call__(self, scope, receive, send):
        self.send = send
        self.path = scope.get("path", "")
        await self.app(scope, receive, self.wrapped_send)

    async def wrapped_send(self, message):
        if self.passthrough:
            await self.send(message)
            return
        kind = message["type"]
        if kind == "http.response.start":
            headers = Headers(raw=message.get("headers", []))
            media_type = headers.get("content-type", "").partition(";")[0].strip().lower()
            if self.minifying:
                self.kind = minify.kind_for(self.path, media_type)
            if (
                message["status"] != 200
                or "content-encoding" in headers
                or media_type not in COMPRESSIBLE_TYPES
                or (self.kind is None and "gzip" not in self.encodings)
            ):
                self.passthrough = True
                await self.send(message)
                return
            self.start = message
            return
        if kind != "http.response.body":
            # Early hints, trailers or pathsend: hand everything over unchanged.
            await self.flush_uncompressed()
            self.passthrough = True
            await self.send(message)
            return
        body = message.get("body", b"")
        self.chunks.append(body)
        self.buffered += len(body)
        if self.buffered > MAX_ASSET_BYTES:
            await self.flush_uncompressed(more_body=message.get("more_body", False))
            self.passthrough = True
            return
        if message.get("more_body", False):
            return
        await self.send_whole(b"".join(self.chunks))

    async def flush_uncompressed(self, more_body: bool = True):
        if self.start is None:
            return
        start, self.start = self.start, None
        await self.send(start)
        body = b"".join(self.chunks)
        self.chunks = []
        await self.send({"type": "http.response.body", "body": body, "more_body": more_body})

    async def send_whole(self, body: bytes):
        start, self.start = self.start, None
        headers = MutableHeaders(raw=start["headers"])
        if self.kind is not None:
            smaller = await minified_copy(body, self.kind)
            if len(smaller) < len(body):  # A file it couldn't read comes back as it was.
                body = smaller
                headers["Content-Length"] = str(len(body))
                if "accept-ranges" in headers:
                    del headers["accept-ranges"]  # Ranges of the file on disk wouldn't match.
        if len(body) >= self.minimum_size:
            headers.add_vary_header("Accept-Encoding")
            encoded, coding = None, None
            if "br" in self.encodings and brotli_enabled():
                encoded, coding = brotli_copy(body), "br"
            if encoded is None and "gzip" in self.encodings:
                encoded, coding = await compressed_copy(body), "gzip"
            if encoded is not None:
                body = encoded
                headers["Content-Encoding"] = coding
                headers["Content-Length"] = str(len(body))
        await self.send(start)
        await self.send({"type": "http.response.body", "body": body, "more_body": False})
