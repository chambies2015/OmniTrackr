"""Privacy-light traffic counting for the owner's Site stats page.

Each counted page view adds to a handful of daily counters (total views, page,
referring site, device type, guest vs member). Unique visitors are estimated
with a salted hash of IP + user agent that exists only in memory for the
current day; the salt is random per process and never written anywhere, so the
stored numbers cannot be linked back to anyone.

Counters are buffered in memory and written in one small batch about once a
minute, so page loads never wait on the database. A restart loses at most that
minute of counts (and restarts the day's visitor de-duplication).
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import secrets
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

EXCLUDED_PREFIXES = (
    "/api/", "/static/", "/auth/", "/docs", "/redoc", "/openapi.json", "/site-stats",
    "/profile-pictures/", "/custom-tab-posters/", "/favicon", "/robots.txt", "/sitemap",
    "/ads.txt", "/sellers.json", "/.well-known/",
)
BOT_PATTERN = re.compile(
    r"bot|crawl|spider|slurp|preview|facebookexternalhit|embedly|monitor|uptime|pingdom|"
    r"lighthouse|headless|curl|wget|python|httpx|aiohttp|go-http|java/|okhttp|axios|node-fetch|"
    r"render/|scanner|validator|feedfetcher|mediapartners|adsbot|bingpreview|semrush|ahrefs",
    re.IGNORECASE,
)
INTERNAL_HOSTS = {"omnitrackr.xyz", "localhost", "127.0.0.1", "testserver"}
MAX_KEY_LENGTH = 200
MAX_SEEN_VISITORS = 250_000
MAX_PENDING_KEYS = 20_000
AUTH_COOKIE_NAME = "omnitrackr_session"


def _utc_today():
    return datetime.now(timezone.utc).date()


def _clean(value: str, limit: int = MAX_KEY_LENGTH) -> str:
    return "".join(ch for ch in value if ch.isprintable())[:limit]


def classify_device(user_agent: str) -> str:
    ua = user_agent.lower()
    if "ipad" in ua or "tablet" in ua:
        return "tablet"
    if "mobi" in ua or "android" in ua or "iphone" in ua:
        return "mobile"
    return "desktop"


def traffic_source(request: Request) -> str | None:
    """Where the visit came from, or None for navigation inside the site."""
    utm = parse_qs(request.url.query).get("utm_source")
    if utm and utm[0].strip():
        return _clean(utm[0].strip().lower(), 60)
    referer = request.headers.get("referer", "").strip()
    if not referer:
        return "(direct)"
    host = (urlsplit(referer).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return "(direct)"
    site_host = (urlsplit(os.getenv("SITE_URL", "")).hostname or "").lower().removeprefix("www.")
    if host in INTERNAL_HOSTS or host == site_host or host.endswith(".omnitrackr.xyz"):
        return None
    return _clean(host, 60)


def should_count(request: Request, status_code: int, content_type: str) -> bool:
    if request.method != "GET" or status_code != 200 or not content_type.startswith("text/html"):
        return False
    path = request.url.path
    if path.startswith(EXCLUDED_PREFIXES):
        return False
    purpose = (request.headers.get("sec-purpose", "") + request.headers.get("purpose", "")).lower()
    if "prefetch" in purpose or "prerender" in purpose:
        return False
    user_agent = request.headers.get("user-agent", "")
    return bool(user_agent) and not BOT_PATTERN.search(user_agent)


class TrafficRecorder:
    def __init__(self, session_factory=None, flush_interval: float = 60.0, flush_threshold: int = 500):
        self.session_factory = session_factory
        self.flush_interval = flush_interval
        self.flush_threshold = flush_threshold
        setting = os.getenv("SITE_TRAFFIC_TRACKING", "").strip().lower()
        if setting in ("off", "0", "false", "no"):
            self.enabled = False
        elif setting in ("on", "1", "true", "yes"):
            self.enabled = True
        else:  # Default: on, except in the test suite.
            self.enabled = os.getenv("TESTING", "").lower() != "true"
        self._lock = threading.Lock()
        self._pending: Counter = Counter()
        self._events = 0
        self._last_flush = time.monotonic()
        self._visitor_day = None
        self._visitor_salt = b""
        self._seen: set[bytes] = set()

    # -- recording ---------------------------------------------------------
    def _visitor_is_new(self, day, request: Request, user_agent: str) -> bool:
        if day != self._visitor_day:
            self._visitor_day = day
            self._visitor_salt = secrets.token_bytes(16)
            self._seen = set()
        # Render (behind Cloudflare) passes the visitor's address in True-Client-IP.
        forwarded = request.headers.get("true-client-ip") or request.headers.get("x-forwarded-for", "")
        ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "")
        digest = hashlib.sha256(self._visitor_salt + ip.encode() + b"|" + user_agent.encode()).digest()[:12]
        if digest in self._seen:
            return False
        if len(self._seen) < MAX_SEEN_VISITORS:
            self._seen.add(digest)
        return True

    def record(self, request: Request, status_code: int, content_type: str) -> bool:
        if not self.enabled or not should_count(request, status_code, content_type):
            return False
        day = _utc_today()
        user_agent = request.headers.get("user-agent", "")
        path = request.url.path
        if len(path) > 1:
            path = path.rstrip("/")
        source = traffic_source(request)
        member = AUTH_COOKIE_NAME in request.cookies
        with self._lock:
            if len(self._pending) >= MAX_PENDING_KEYS:
                return False
            pending = self._pending
            pending[(day, "total", "views")] += 1
            pending[(day, "page", _clean(path))] += 1
            pending[(day, "device", classify_device(user_agent))] += 1
            pending[(day, "audience", "member" if member else "guest")] += 1
            if source:
                pending[(day, "source", source)] += 1
            if self._visitor_is_new(day, request, user_agent):
                pending[(day, "total", "visitors")] += 1
            self._events += 1
        return True

    def flush_due(self) -> bool:
        return self._events >= self.flush_threshold or (
            self._events > 0 and time.monotonic() - self._last_flush >= self.flush_interval
        )

    # -- persistence -------------------------------------------------------
    def flush(self) -> int:
        """Write buffered counters; returns the number of counters written."""
        with self._lock:
            pending, self._pending = self._pending, Counter()
            self._events = 0
            self._last_flush = time.monotonic()
        if not pending:
            return 0
        factory = self.session_factory
        if factory is None:
            from .database import SessionLocal
            factory = SessionLocal
        from . import models

        db = factory()
        try:
            table = models.SiteTrafficDaily
            for (day, kind, key), amount in pending.items():
                updated = db.query(table).filter(
                    table.day == day, table.kind == kind, table.key == key
                ).update({table.count: table.count + amount}, synchronize_session=False)
                if not updated:
                    db.add(table(day=day, kind=kind, key=key, count=amount))
                    db.flush()
            db.commit()
            return len(pending)
        except Exception:
            db.rollback()
            with self._lock:
                if len(self._pending) + len(pending) <= MAX_PENDING_KEYS:
                    self._pending.update(pending)  # Try again on the next flush.
            return 0
        finally:
            db.close()


RECORDER = TrafficRecorder()
_background_flushes: set = set()


class SiteTrafficMiddleware(BaseHTTPMiddleware):
    """Count human page views after the response is ready; never affects the response."""

    def __init__(self, app, recorder: TrafficRecorder | None = None):
        super().__init__(app)
        self.recorder = recorder

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        recorder = self.recorder or RECORDER
        try:
            counted = recorder.record(request, response.status_code, response.headers.get("content-type", ""))
            if counted and recorder.flush_due():
                task = asyncio.create_task(asyncio.to_thread(recorder.flush))
                _background_flushes.add(task)
                task.add_done_callback(_background_flushes.discard)
        except Exception:
            pass  # Analytics must never break a page.
        return response
