"""Tier list maker (/tier-list): rank titles into S to D tiers and save the board as an image.

Boards live only in the visitor's browser (tier-list.js); nothing about a board is
stored on the server. This module supplies the starting sets ("templates"), a
member's own rated titles for "rank my library", and the host allowlist for the
image proxy that lets the browser draw posters onto the exported picture.
"""
from __future__ import annotations

import threading
import time
from typing import Optional
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from . import pick, title_pages, title_search
from . import release_radar as radar

TIERS = ("S", "A", "B", "C", "D")
# Lowest rating (out of 10) that lands a title in each tier when ranking a library.
RATING_TIERS = ((9.0, "S"), (8.0, "A"), (7.0, "B"), (5.5, "C"), (0.0, "D"))
TEMPLATE_MIN_ITEMS = 6
TEMPLATE_MAX_ITEMS = 30
LIBRARY_MAX_ITEMS = 120
CACHE_SECONDS = 600
KIND_PLURALS = {"movie": "movies", "tv": "TV shows", "anime": "anime", "game": "video games",
                "album": "albums", "book": "books", "manga": "manga", "podcast": "podcasts", "audiobook": "audiobooks"}
KIND_ORDER = ("movie", "tv", "anime", "game", "book", "manga", "album", "podcast", "audiobook")

# Poster and cover hosts the image proxy may fetch from (the host itself or a subdomain).
IMAGE_HOSTS = (
    "m.media-amazon.com",
    "images-na.ssl-images-amazon.com",
    "media.rawg.io",
    "cdn.myanimelist.net",
    "s4.anilist.co",
    "static.tvmaze.com",
    "covers.openlibrary.org",
    "archive.org",
    "mzstatic.com",
    "upload.wikimedia.org",
    "commons.wikimedia.org",
    "books.google.com",
    "books.googleusercontent.com",
)
IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif", "image/avif")
IMAGE_MAX_BYTES = 4 * 1024 * 1024

_cache: dict = {"at": 0.0, "templates": None}
_lock = threading.Lock()


def tier_for_rating(rating) -> Optional[str]:
    """The tier a member's rating (0 to 10) suggests; None leaves the title unranked."""
    if rating is None:
        return None
    try:
        value = float(rating)
    except (TypeError, ValueError):
        return None
    for floor, tier in RATING_TIERS:
        if value >= floor:
            return tier
    return None


def image_allowed(url) -> bool:
    """True for an http(s) URL on an allowlisted poster host, without credentials or odd ports."""
    if not isinstance(url, str) or len(url) > 1000:
        return False
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or parts.username or parts.password or port not in (None, 80, 443):
        return False
    host = (parts.hostname or "").lower().rstrip(".")
    return any(host == allowed or host.endswith("." + allowed) for allowed in IMAGE_HOSTS)


def _entry(kind: str, title: str, year, image=None, slug: Optional[str] = None) -> dict:
    return {"kind": kind, "title": (title or "").strip()[:200], "year": year if isinstance(year, int) else None,
            "image": title_pages._safe_image(image), "slug": slug}


def _popular_templates(db: Session) -> list[dict]:
    result = []
    for kind in KIND_ORDER:
        items = title_pages.popular(db, kind, limit=TEMPLATE_MAX_ITEMS, min_members=2)
        if len(items) < TEMPLATE_MIN_ITEMS:
            continue
        result.append({
            "key": f"popular-{kind}", "kind": kind,
            "name": f"Most tracked {KIND_PLURALS[kind]} on OmniTrackr",
            "blurb": f"The {KIND_PLURALS[kind]} members save most often.",
            "items": [_entry(kind, item["title"], item["year"], item.get("image"), item["url"].rsplit("/", 1)[1])
                      for item in items],
        })
    return result


def _editor_templates(db: Session) -> list[dict]:
    details = pick.title_details(title_search.index(db))
    result = []
    for kind in KIND_ORDER:
        entries = pick.candidates(kind)[:TEMPLATE_MAX_ITEMS]
        if len(entries) < TEMPLATE_MIN_ITEMS:
            continue
        result.append({
            "key": f"editors-{kind}", "kind": kind,
            "name": f"Editors' {KIND_PLURALS[kind]}",
            "blurb": "Picks from OmniTrackr's Discover trails and editors' collections.",
            "items": [_entry(kind, entry["title"], entry["year"], details.get(entry["id"], {}).get("image"), entry["slug"])
                      for entry in entries],
        })
    return result


def _season_template() -> Optional[dict]:
    """This anime season from Release Radar, when the radar already has it cached (never fetches)."""
    try:
        window = radar.current_window("anime")
        entry = radar.CACHE.peek(window)
    except Exception:
        return None
    items = [item for item in (entry or {}).get("items", []) if item.get("title")]
    items.sort(key=lambda item: -float(item.get("popularity") or 0))
    items = items[:TEMPLATE_MAX_ITEMS]
    if len(items) < TEMPLATE_MIN_ITEMS:
        return None
    label = getattr(window, "label", None) or "This season"
    return {
        "key": "anime-season", "kind": "anime",
        "name": f"{label} anime season",
        "blurb": "The most-followed new anime this season, from Release Radar.",
        "items": [_entry("anime", item["title"], None, item.get("image")) for item in items],
    }


def build_templates(db: Session) -> list[dict]:
    templates = []
    season = _season_template()
    if season:
        templates.append(season)
    templates.extend(_popular_templates(db))
    templates.extend(_editor_templates(db))
    return templates


def templates(db: Session) -> list[dict]:
    """Starting sets, rebuilt at most every 10 minutes."""
    now = time.monotonic()
    with _lock:
        if _cache["templates"] is not None and now - _cache["at"] < CACHE_SECONDS:
            return _cache["templates"]
    built = build_templates(db)
    with _lock:
        _cache.update(at=now, templates=built)
    return built


def clear_cache() -> None:
    with _lock:
        _cache.update(at=0.0, templates=None)


def find_template(db: Session, key: str) -> Optional[dict]:
    return next((template for template in templates(db) if template["key"] == key), None)


def library_items(db: Session, user, kind: str) -> list[dict]:
    """One member's titles of a kind with the tier their own rating suggests (rated first)."""
    model = title_pages.KINDS[kind][0]
    image_field = title_pages.IMAGE_FIELD[kind]
    rows = (db.query(model).filter(model.user_id == user.id)
            .order_by(model.rating.is_(None), model.rating.desc(), model.id).limit(LIBRARY_MAX_ITEMS).all())
    items = []
    seen = set()
    for row in rows:
        title = (row.title or "").strip()
        year = title_pages.item_year(kind, row)
        key = (title.casefold(), year)
        if not title or key in seen:
            continue
        seen.add(key)
        item = _entry(kind, title, year, getattr(row, image_field, None))
        item["tier"] = tier_for_rating(row.rating)
        item["rating"] = row.rating
        items.append(item)
    return items
