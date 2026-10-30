"""Privacy-light traffic counting for the owner's Site stats page.

Each counted page view adds to a handful of daily counters (total views, page,
referring site, device type, guest vs member). Unique visitors are estimated
with a salted hash of IP + user agent that exists only in memory for the
current day; the salt is random per process and never written anywhere, so the
stored numbers cannot be linked back to anyone.

Counters are buffered in memory and written in one small batch about once a
minute, so page loads never wait on the database. A restart loses at most that
minute of counts (and restarts the day's visitor de-duplication).

Two sets of counters are kept side by side:

- "All requests" (kinds total/page/source/device/audience): every HTML page the
  server sends to something that doesn't call itself a bot. Scanners and
  scripts that pretend to be browsers land here too.
- "Likely people" (kinds human_total/human_page/...): counted only when the page
  itself reports in from a real, visible browser tab (POST /api/visit, sent by
  static/visit.js). On top of needing JavaScript, a report is dropped when it
  comes from a known crawler network, from another site, from a browser driven
  by automation, or repeats the same page within a few seconds, and each
  visitor's daily count is capped.
"""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
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
# A campaign tag is a short plain word; anything else (scanners put script tags in
# utm_source) is counted under one label instead of being stored as written.
SAFE_TAG = re.compile(r"[a-z0-9][a-z0-9 ._+-]{0,59}")
BAD_TAG = "(unreadable tag)"
# "Likely people" limits: the same page again within this many seconds is a reload
# or a script, and nobody reads more than this many pages in a day.
HUMAN_REPEAT_SECONDS = 10
HUMAN_MAX_VIEWS_PER_DAY = 300
# Crawlers that run JavaScript and so could report in like a browser: Googlebot,
# Bingbot and Meta's link preview fetcher. More can be added with
# SITE_TRAFFIC_BOT_NETWORKS (comma-separated, e.g. "192.0.2.0/24,2001:db8::/32").
CRAWLER_NETWORKS = (
    "66.249.64.0/19", "2001:4860:4801::/48",
    "40.77.167.0/24", "157.55.39.0/24", "207.46.13.0/24", "52.167.144.0/24", "13.66.139.0/24",
    "31.13.24.0/21", "66.220.144.0/20", "69.63.176.0/20", "69.171.224.0/19", "173.252.64.0/18",
    "2a03:2880::/32",
)


def _networks(values) -> tuple:
    networks = []
    for value in values:
        try:
            networks.append(ipaddress.ip_network(value.strip(), strict=False))
        except ValueError:
            continue
    return tuple(networks)


_CRAWLERS = _networks(CRAWLER_NETWORKS + tuple(
    item for item in os.getenv("SITE_TRAFFIC_BOT_NETWORKS", "").split(",") if item.strip()))


def crawler_address(ip: str) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(address.version == network.version and address in network for network in _CRAWLERS)


def client_ip(request: Request) -> str:
    # Render (behind Cloudflare) passes the visitor's address in True-Client-IP.
    forwarded = request.headers.get("true-client-ip") or request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "")


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


def clean_path(path: str) -> str:
    if len(path) > 1:
        path = path.rstrip("/") or "/"
    return _clean(path)


def source_for(utm: str | None, referer: str | None) -> str | None:
    """Where a visit came from: its utm_source tag, else the referring site.

    None means navigation inside the site; "(direct)" means no referrer at all.
    """
    tag = (utm or "").strip().lower()
    if tag:
        return tag if SAFE_TAG.fullmatch(tag) else BAD_TAG
    referer = (referer or "").strip()
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


def traffic_source(request: Request) -> str | None:
    """Where the visit came from, or None for navigation inside the site."""
    utm = parse_qs(request.url.query).get("utm_source")
    return source_for(utm[0] if utm else "", request.headers.get("referer", ""))


def human_problem(request: Request) -> str | None:
    """Why a page's "I was opened" report can't count as a person, or None if it can."""
    user_agent = request.headers.get("user-agent", "")
    if not user_agent or BOT_PATTERN.search(user_agent):
        return "bot"
    site = request.headers.get("sec-fetch-site", "")
    if site and site != "same-origin":
        return "other site"
    if crawler_address(client_ip(request)):
        return "crawler network"
    return None


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
        # Likely-people visitors today: digest -> [views, last page, when, homepage counted].
        self._people: dict[bytes, list] = {}

    # -- recording ---------------------------------------------------------
    def _roll_day(self, day) -> None:
        if day != self._visitor_day:
            self._visitor_day = day
            self._visitor_salt = secrets.token_bytes(16)
            self._seen = set()
            self._people = {}

    def _digest(self, request: Request, user_agent: str, scope: bytes = b"") -> bytes:
        ip = client_ip(request)
        return hashlib.sha256(self._visitor_salt + scope + ip.encode() + b"|" + user_agent.encode()).digest()[:12]

    def _visitor_is_new(self, day, request: Request, user_agent: str) -> bool:
        self._roll_day(day)
        digest = self._digest(request, user_agent)
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

    def record_person(self, request: Request, path: str, referrer: str = "", utm: str = "") -> bool:
        """Count a page view reported by the page itself (see the module docstring)."""
        if not self.enabled or human_problem(request):
            return False
        path = (path or "").split("?", 1)[0].split("#", 1)[0]
        if not path.startswith("/") or path.startswith("//") or path.startswith(EXCLUDED_PREFIXES):
            return False
        path = clean_path(path)
        user_agent = request.headers.get("user-agent", "")
        member = AUTH_COOKIE_NAME in request.cookies
        source = source_for(utm, referrer)
        day = _utc_today()
        now = time.monotonic()
        with self._lock:
            if len(self._pending) >= MAX_PENDING_KEYS:
                return False
            self._roll_day(day)
            digest = self._digest(request, user_agent, b"person|")
            state = self._people.get(digest)
            pending = self._pending
            if state is None:
                state = [0, "", 0.0, False]
                if len(self._people) < MAX_SEEN_VISITORS:
                    self._people[digest] = state
                pending[(day, "human_total", "visitors")] += 1
            elif state[0] >= HUMAN_MAX_VIEWS_PER_DAY or (state[1] == path and now - state[2] < HUMAN_REPEAT_SECONDS):
                return False
            state[0], state[1], state[2] = state[0] + 1, path, now
            pending[(day, "human_total", "views")] += 1
            pending[(day, "human_page", path)] += 1
            pending[(day, "human_device", classify_device(user_agent))] += 1
            pending[(day, "human_audience", "member" if member else "guest")] += 1
            if source:
                pending[(day, "human_source", source)] += 1
            if path == "/" and not member and not state[3]:
                state[3] = True
                pending[(day, "funnel", "landing_seen")] += 1  # one per person per day
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
