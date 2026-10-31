"""Browse pages for manga, podcasts and audiobooks (/browse/<kind>, Oct 2026).

The three newest trackers launched with empty libraries, so the public pages that
depend on members (title pages, charts, trending) had nothing to show for them. A
browse page gives each one a stock to start from:

* a live chart from the same source the tracker's search already uses (MyAnimeList
  via Jikan for manga, Apple's charts for podcasts and audiobooks), cached in memory
  and refreshed in the background the way Release Radar does it;
* the written shelves in browse_catalog, with a cover for each entry looked up
  through the title_metadata cache that title pages share;
* one-tap "add to my library" for members, and the save-before-sign-up list for
  everyone else.

Nothing here changes the database schema or touches a member's existing titles.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models, title_metadata, title_pages
from .browse_catalog import CATALOG, entries as shelf_entries, find as find_entry

# URL kind -> how the tracker stores it and where its chart comes from.
KINDS = {
    "manga": {
        "title_kind": "manga", "library": "manga", "model": models.Manga, "creator_field": "author",
        "chart_name": "Most popular on MyAnimeList", "chart_blurb": "The manga with the most MyAnimeList members, refreshed a few times a day.",
        "source": ("MyAnimeList", "https://myanimelist.net/topmanga.php?type=bypopularity"),
        "add_label": "Add to my manga",
    },
    "podcasts": {
        "title_kind": "podcast", "library": "podcasts", "model": models.Podcast, "creator_field": "host",
        "chart_name": "Top shows on Apple Podcasts", "chart_blurb": "Apple's current top podcasts in the United States, refreshed a few times a day.",
        "source": ("Apple Podcasts", "https://podcasts.apple.com/us/charts"),
        "add_label": "Add to my podcasts",
    },
    "audiobooks": {
        "title_kind": "audiobook", "library": "audiobooks", "model": models.Audiobook, "creator_field": "author",
        "chart_name": "Top audiobooks on Apple Books", "chart_blurb": "Apple's current top audiobooks in the United States, refreshed a few times a day.",
        "source": ("Apple Books", "https://books.apple.com/us/audiobooks"),
        "add_label": "Add to my audiobooks",
    },
}
TITLE_KIND_TO_KIND = {config["title_kind"]: kind for kind, config in KINDS.items()}

CHART_LIMIT = 24
USER_AGENT = "OmniTrackr/1.0 (https://omnitrackr.xyz; omnitrackr@gmail.com) Browse"
FRESH_SECONDS = int(os.getenv("BROWSE_CHART_FRESH_SECONDS", str(6 * 3600)))
STALE_MAX_SECONDS = int(os.getenv("BROWSE_CHART_STALE_SECONDS", str(14 * 24 * 3600)))
FIRST_LOAD_WAIT_SECONDS = float(os.getenv("BROWSE_CHART_FIRST_WAIT", "5"))
RETRY_FAILED_SECONDS = 300
ALLOWED_IMAGE_HOSTS = ("cdn.myanimelist.net",)
ALLOWED_IMAGE_SUFFIXES = (".mzstatic.com",)
EDITION_SUFFIX = re.compile(r"\s*[\(\[](?:unabridged|abridged|dramati[sz]ed)[^\)\]]*[\)\]]\s*$", re.IGNORECASE)
# Covers are looked up one at a time in the background, spaced out for the sources' rate limits; a page view never waits on them.
COVER_WARM_BATCH = int(os.getenv("BROWSE_COVER_BATCH", "48"))
COVER_WARM_SPACING = float(os.getenv("BROWSE_COVER_SPACING", "1.5"))


def path(kind: Optional[str] = None) -> str:
    return "/browse" + (f"/{kind}" if kind else "")


class SourceUnavailable(RuntimeError):
    """The chart source is down or rate limiting; keep the last copy and try again later."""


# ---------------------------------------------------------------- normalization

def _clean(value: Any, limit: int = 200) -> str:
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    return "".join(ch for ch in text if ch.isprintable())[:limit]


def _safe_image(url: Any) -> Optional[str]:
    if not isinstance(url, str) or not url.startswith("https://") or any(ch in url for ch in "\"'<> \\"):
        return None
    host = url[8:].split("/", 1)[0].lower()
    if host in ALLOWED_IMAGE_HOSTS or host.endswith(ALLOWED_IMAGE_SUFFIXES):
        return url[:500]
    return None


def _safe_link(url: Any, prefixes: tuple[str, ...]) -> Optional[str]:
    if isinstance(url, str) and url.startswith(prefixes) and not any(ch in url for ch in "\"'<> \\"):
        return url[:500]
    return None


def _year(value: Any) -> Optional[int]:
    text = str(value or "")[:4]
    return int(text) if text.isdigit() and 1800 < int(text) < 2200 else None


def _chart_item(source_id: str, title: str, creator: Optional[str], year: Optional[int], genre: Optional[str],
                image: Optional[str], url: Optional[str], extra: Optional[dict] = None) -> Optional[dict]:
    title = _clean(title)
    if not title or not source_id:
        return None
    return {"id": source_id, "title": title, "creator": _clean(creator) or None, "year": year,
            "genre": _clean(genre, 80) or None, "image": image, "url": url, "extra": extra or {}}


def normalize_manga_chart(data: dict) -> list[dict]:
    from .routers.proxy import normalize_jikan_manga
    items = []
    for entry in (data.get("data") or [])[:CHART_LIMIT]:
        if not isinstance(entry, dict) or not entry.get("mal_id"):
            continue
        shaped = normalize_jikan_manga(entry)
        item = _chart_item(f"mal-{int(entry['mal_id'])}", shaped["title"], shaped["author"], shaped["year"], shaped["genre"],
                           _safe_image(shaped["cover_art_url"]), _safe_link(entry.get("url"), ("https://myanimelist.net/",)),
                           {"volumes": shaped["volumes"] if isinstance(shaped["volumes"], int) else None,
                            "chapters": shaped["chapters"] if isinstance(shaped["chapters"], int) else None})
        if item:
            items.append(item)
    return items


def normalize_podcast_chart(data: dict) -> list[dict]:
    items = []
    for entry in ((data.get("feed") or {}).get("results") or [])[:CHART_LIMIT]:
        if not isinstance(entry, dict) or not str(entry.get("id") or "").isdigit():
            continue
        art = entry.get("artworkUrl100")
        image = _safe_image(re.sub(r"/\d+x\d+bb\.", "/600x600bb.", art)) if isinstance(art, str) else None
        genres = [g.get("name") for g in entry.get("genres") or [] if isinstance(g, dict) and g.get("name") and g.get("name") != "Podcasts"]
        item = _chart_item(f"apple-{entry['id']}", entry.get("name"), entry.get("artistName"), None, ", ".join(genres[:2]) or None,
                           image, _safe_link(entry.get("url"), ("https://podcasts.apple.com/",)))
        if item:
            items.append(item)
    return items


def _label(value: Any) -> str:
    return value.get("label", "") if isinstance(value, dict) else ""


def normalize_audiobook_chart(data: dict) -> list[dict]:
    items = []
    feed_entries = (data.get("feed") or {}).get("entry") or []
    if isinstance(feed_entries, dict):
        feed_entries = [feed_entries]
    for entry in feed_entries[:CHART_LIMIT]:
        if not isinstance(entry, dict):
            continue
        source_id = ((entry.get("id") or {}).get("attributes") or {}).get("im:id") if isinstance(entry.get("id"), dict) else None
        if not str(source_id or "").isdigit():
            continue
        title = _label(entry.get("im:name"))
        title = EDITION_SUFFIX.sub("", title) or title
        images = entry.get("im:image") or []
        art = _label(images[-1]) if isinstance(images, list) and images else ""
        image = _safe_image(re.sub(r"/\d+x\d+bb\.", "/600x600bb.", art)) if art else None
        links = entry.get("link") or []
        if isinstance(links, dict):
            links = [links]
        url = next((_safe_link((link.get("attributes") or {}).get("href"), ("https://books.apple.com/",))
                    for link in links if isinstance(link, dict) and (link.get("attributes") or {}).get("rel") == "alternate"), None)
        genre = ((entry.get("category") or {}).get("attributes") or {}).get("label") if isinstance(entry.get("category"), dict) else None
        item = _chart_item(f"apple-{source_id}", title, _label(entry.get("im:artist")), _year(_label(entry.get("im:releaseDate"))),
                           genre, image, url)
        if item:
            items.append(item)
    return items


# ---------------------------------------------------------------- sources

async def _get_json(client: httpx.AsyncClient, url: str, params: Optional[dict] = None) -> dict:
    try:
        response = await client.get(url, params=params, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=12.0)
    except (httpx.TimeoutException, httpx.TransportError) as error:
        raise SourceUnavailable(str(error)) from error
    if response.status_code == 429 or response.status_code >= 500:
        raise SourceUnavailable(f"{url} answered {response.status_code}")
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


async def fetch_manga_chart(client: httpx.AsyncClient) -> list[dict]:
    data = await _get_json(client, "https://api.jikan.moe/v4/top/manga",
                           {"type": "manga", "filter": "bypopularity", "limit": 25, "sfw": "true"})
    return normalize_manga_chart(data)


async def fetch_podcast_chart(client: httpx.AsyncClient) -> list[dict]:
    data = await _get_json(client, f"https://rss.marketingtools.apple.com/api/v2/us/podcasts/top/{CHART_LIMIT}/podcasts.json")
    return normalize_podcast_chart(data)


async def fetch_audiobook_chart(client: httpx.AsyncClient) -> list[dict]:
    data = await _get_json(client, f"https://itunes.apple.com/us/rss/topaudiobooks/limit={CHART_LIMIT}/json")
    return normalize_audiobook_chart(data)


Provider = Callable[[httpx.AsyncClient], Awaitable[list[dict]]]
PROVIDERS: dict[str, Provider] = {"manga": fetch_manga_chart, "podcasts": fetch_podcast_chart, "audiobooks": fetch_audiobook_chart}


# ---------------------------------------------------------------- cache

def _default_cache_dir() -> Optional[Path]:
    configured = os.getenv("BROWSE_CACHE_DIR")
    if configured == "":
        return None
    return Path(configured or os.path.join(tempfile.gettempdir(), "omnitrackr-browse"))


_event_loop: Optional[asyncio.AbstractEventLoop] = None


def bind_event_loop(loop: Optional[asyncio.AbstractEventLoop]) -> None:
    """Remember the server's event loop so threadpool requests can start background work on it."""
    global _event_loop
    _event_loop = loop


def _on_loop(callback: Callable, *args) -> None:
    """Run callback on the server loop, from inside it or from a threadpool request. Skipped when there is none."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = _event_loop
        if loop is not None and loop.is_running() and not loop.is_closed():
            loop.call_soon_threadsafe(callback, *args)
        return
    callback(*args)


class ChartCache:
    def __init__(self, cache_dir: Optional[Path] = None):
        self.entries: dict[str, dict] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        self.cache_dir = cache_dir

    def _disk_path(self, kind: str) -> Optional[Path]:
        return self.cache_dir / f"chart-{kind}.json" if self.cache_dir else None

    def _load_disk(self, kind: str) -> Optional[dict]:
        disk = self._disk_path(kind)
        if not disk or not disk.exists():
            return None
        try:
            entry = json.loads(disk.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if isinstance(entry, dict) and isinstance(entry.get("items"), list) and isinstance(entry.get("fetched_at"), (int, float)):
            return entry
        return None

    def _save_disk(self, kind: str, entry: dict) -> None:
        disk = self._disk_path(kind)
        if not disk:
            return
        try:
            disk.parent.mkdir(parents=True, exist_ok=True)
            tmp = disk.with_suffix(".tmp")
            tmp.write_text(json.dumps(entry), encoding="utf-8")
            tmp.replace(disk)
        except OSError:
            pass

    def peek(self, kind: str) -> Optional[dict]:
        entry = self.entries.get(kind)
        if entry is None:
            entry = self._load_disk(kind)
            if entry is not None:
                self.entries[kind] = entry
        if entry and entry.get("fetched_at") and time.time() - entry["fetched_at"] > STALE_MAX_SECONDS:
            return None
        return entry

    async def _refresh(self, client: httpx.AsyncClient, kind: str) -> dict:
        try:
            items = await PROVIDERS[kind](client)
            if not items:
                raise SourceUnavailable("empty chart")
            entry = {"items": items, "fetched_at": time.time(), "error": None}
            self.entries[kind] = entry
            self._save_disk(kind, entry)
            return entry
        except Exception as error:
            previous = self.entries.get(kind)
            reason = "unavailable" if isinstance(error, SourceUnavailable) else "error"
            if previous and previous.get("fetched_at"):
                previous = {**previous, "error": reason, "failed_at": time.time()}
            else:
                previous = {"items": [], "fetched_at": 0, "error": reason, "failed_at": time.time()}
            self.entries[kind] = previous
            return previous

    def _start_refresh(self, client: httpx.AsyncClient, kind: str) -> asyncio.Task:
        task = self.tasks.get(kind)
        if task is None or task.done():
            task = asyncio.create_task(self._refresh(client, kind))
            self.tasks[kind] = task
        return task

    def warm(self, client: Optional[httpx.AsyncClient], kind: str) -> None:
        """Start a background fetch for a missing or stale chart without waiting for it."""
        if client is None:
            return
        entry = self.peek(kind)
        now = time.time()
        if entry and entry.get("fetched_at") and now - entry["fetched_at"] <= FRESH_SECONDS:
            return
        if entry and now - entry.get("failed_at", 0) < RETRY_FAILED_SECONDS:
            return
        _on_loop(self._start_refresh, client, kind)

    async def get(self, client: Optional[httpx.AsyncClient], kind: str, *, wait: Optional[float] = None) -> Optional[dict]:
        """The chart, waiting briefly for a cold fetch; a stale copy is served while a refresh runs."""
        if wait is None:
            wait = FIRST_LOAD_WAIT_SECONDS
        entry = self.peek(kind)
        if client is None:
            return entry
        now = time.time()
        if entry and entry.get("fetched_at"):
            if now - entry["fetched_at"] > FRESH_SECONDS and now - entry.get("failed_at", 0) > RETRY_FAILED_SECONDS:
                self._start_refresh(client, kind)
            return entry
        if entry and now - entry.get("failed_at", 0) < RETRY_FAILED_SECONDS:
            return entry
        task = self._start_refresh(client, kind)
        if wait <= 0:
            return None
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=wait)
        except asyncio.TimeoutError:
            return None


CACHE = ChartCache(_default_cache_dir())


def chart_items(entry: Optional[dict]) -> list[dict]:
    if not entry or not isinstance(entry.get("items"), list):
        return []
    return [item for item in entry["items"] if isinstance(item, dict) and item.get("id") and item.get("title")][:CHART_LIMIT]


def chart_updated(entry: Optional[dict]) -> Optional[datetime]:
    if entry and entry.get("fetched_at"):
        return datetime.utcfromtimestamp(entry["fetched_at"])
    return None


# ---------------------------------------------------------------- covers (title_metadata cache)

def metadata_key(kind: str, item: dict) -> str:
    return title_metadata.cache_key(KINDS[kind]["title_kind"], title_pages.normalize(item["title"]), item.get("year"))


def cached_covers(db: Session, kind: str, items: list[dict]) -> tuple[dict[str, str], list[dict]]:
    """(item key -> cover url) from the facts cache, and the items whose facts are missing or stale.

    One query for the whole shelf; freshness follows title_metadata.cached so a miss is
    retried on the same schedule a title page would use.
    """
    keys = {item["key"]: metadata_key(kind, item) for item in items}
    rows = {row.key: row for row in db.query(models.TitleMetadata).filter(models.TitleMetadata.key.in_(set(keys.values()))).all()}
    covers: dict[str, str] = {}
    pending: list[dict] = []
    now = datetime.utcnow()
    for item in items:
        row = rows.get(keys[item["key"]])
        if row is None:
            pending.append(item)
            continue
        data = None
        if row.status == "ok" and row.data:
            try:
                data = json.loads(row.data)
            except ValueError:
                data = None
        if isinstance(data, dict):
            poster = title_pages._safe_image(data.get("poster"))
            if poster:
                covers[item["key"]] = poster
        limit = title_metadata.FRESH.get(row.status, title_metadata.FRESH["error"])
        if isinstance(data, dict) and data.get("partial"):
            limit = min(limit, title_metadata.PARTIAL_FRESH)
        fresh = now - row.fetched_at < limit
        if row.status == "miss" and row.fetched_at < title_metadata.MATCHER_UPDATED:
            fresh = False
        if not fresh:
            pending.append(item)
    return covers, pending


_warming: set[str] = set()


async def warm_covers(client: httpx.AsyncClient, kind: str, pending: list[dict]) -> int:
    """Look up a few missing covers through the shared facts cache, spaced out for rate limits."""
    if kind in _warming or client is None:
        return 0
    _warming.add(kind)
    done = 0
    try:
        from .database import SessionLocal
        category = KINDS[kind]["title_kind"]
        # Apple lists a podcast under its production company, not its host, so the host would only spoil the match.
        match_creator = kind != "podcasts"
        for item in pending[:COVER_WARM_BATCH]:
            db = SessionLocal()
            try:
                await title_metadata.get_or_fetch(db, client, category, title_pages.normalize(item["title"]), item["title"],
                                                  item.get("year"), item.get("creator") if match_creator else None, wait=12.0)
                done += 1
            except Exception:
                pass
            finally:
                db.close()
            if COVER_WARM_SPACING:
                await asyncio.sleep(COVER_WARM_SPACING)
    finally:
        _warming.discard(kind)
    return done


def schedule_cover_warming(client: Optional[httpx.AsyncClient], kind: str, pending: list[dict]) -> None:
    if client is None or not pending or kind in _warming:
        return
    _on_loop(lambda: asyncio.create_task(warm_covers(client, kind, pending)))


# ---------------------------------------------------------------- library

def shelf_items(kind: str) -> list[dict]:
    return shelf_entries(kind)


def find_key(kind: str, key: str, chart: Optional[dict] = None) -> Optional[dict]:
    """A shelf entry by key, or a chart entry by its source id ("mal-13", "apple-1200361736")."""
    entry = find_entry(kind, key)
    if entry is not None:
        return entry
    for item in chart_items(chart):
        if item["id"] == key:
            return item
    return None


def guest_slug(item: dict) -> str:
    return title_pages.title_slug(item["title"], item.get("year"))


def find(title_kind: str, slug: str) -> Optional[tuple[str, dict]]:
    """For the saved-before-sign-up import: the browse entry a (title kind, slug) names, if any."""
    kind = TITLE_KIND_TO_KIND.get(title_kind)
    if kind is None or not re.fullmatch(r"[a-z0-9-]{1,130}", slug or ""):
        return None
    for item in shelf_entries(kind):
        if item["key"] == slug or guest_slug(item) == slug:
            return kind, item
    for item in chart_items(CACHE.peek(kind)):
        if guest_slug(item) == slug:
            return kind, item
    return None


def member_keys(db: Session, user_id: int, kind: str, chart: Optional[dict] = None) -> list[str]:
    """Keys of the shelf and chart entries this member already has, matched by title."""
    model = KINDS[kind]["model"]
    owned = {title_pages.normalize(title) for title, in db.query(model.title).filter(model.user_id == user_id).all() if title}
    keys = [item["key"] for item in shelf_entries(kind) if title_pages.normalize(item["title"]) in owned]
    keys += [item["id"] for item in chart_items(chart) if title_pages.normalize(item["title"]) in owned]
    return keys


def add_to_library(db: Session, user, kind: str, entry: dict, image: Optional[str] = None) -> tuple[str, object]:
    """Add a shelf or chart entry to the member's library, unfinished and unrated. Does not commit.

    Returns ("existing" | "created", record). A title the member already has (same name,
    any case) is left exactly as it is.
    """
    config = KINDS[kind]
    model = config["model"]
    normalized = title_pages.normalize(entry["title"])
    existing = db.query(model).filter(model.user_id == user.id, func.lower(func.trim(model.title)) == normalized).first()
    if existing is not None:
        return "existing", existing
    extra = entry.get("extra") or {}
    fields = {"user_id": user.id, "title": entry["title"], "year": entry.get("year"), "genre": entry.get("genre"),
              config["creator_field"]: entry.get("creator") or None}
    if kind == "manga":
        fields["volumes"] = extra.get("volumes") if isinstance(extra.get("volumes"), int) else None
        fields["chapters"] = extra.get("chapters") if isinstance(extra.get("chapters"), int) else None
    elif kind == "audiobooks":
        fields["narrator"] = extra.get("narrator") or None
        hours = extra.get("length_hours")
        fields["length_hours"] = float(hours) if isinstance(hours, (int, float)) and hours > 0 else None
    cover = title_pages._safe_image(image) or title_pages._safe_image(entry.get("image"))
    if cover:
        fields["cover_art_url"] = cover
    record = model(**fields)
    db.add(record)
    db.flush()
    return "created", record


def counts() -> dict[str, int]:
    return {kind: len(shelf_entries(kind)) for kind in CATALOG}


def word_count(kind: str) -> int:
    page = CATALOG[kind]
    text = " ".join([page["lead"], *page["intro"], *page["method"]] +
                    [f"{shelf['lead']} " + " ".join(f"{i['why']} {i['fit']}" for i in shelf["items"]) for shelf in page["shelves"]])
    return len(text.split())
