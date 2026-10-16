"""Pick for me: one curated suggestion for visitors who can't decide what to start.

The pool is the editors' own writing that already ships with the site: the
Discover trails, the monthly editions, the starter public collections and the
"If you liked..." guides. Every
pick carries the reason it was chosen, so the page never shows a bare title.
Nothing here reads or reveals anyone's library; the only database reads are the
cached title index (for artwork and title page links) and the editors' public
collection links.

Visitors save a pick to their browser-only guest list (it moves into their new
library at first log-in through POST /api/guest-list/import); members add it to
their library directly. Either way only the title, year and creator are copied.
"""
from __future__ import annotations

import random
import zlib
from datetime import date, datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models, title_pages
from .discover_catalog import MONTHLY_EDITIONS, TRAILS
from .editorial_collections import COLLECTIONS, EDITOR_USERNAME

# Display order of the format chips and the pool list.
KIND_ORDER = ("movie", "tv", "anime", "game", "book", "album")
FORMAT_LABELS = {"movie": "Movies", "tv": "TV shows", "anime": "Anime", "game": "Games", "book": "Books", "album": "Music"}
CREATOR_FIELD = {"movie": "director", "album": "artist", "book": "author"}
CREATOR_META = ("director", "author", "artist")

_pool: Optional[list[dict]] = None


def _entry(kind: str, title: str, year, creator, why: str, caveat, source_label: str, source_url) -> dict:
    year = year if isinstance(year, int) and not isinstance(year, bool) and 1800 <= year <= 2100 else None
    slug = title_pages.title_slug(title, year)
    return {
        "id": f"{kind}/{slug}", "kind": kind, "slug": slug,
        "category": title_pages.KINDS[kind][2], "label": title_pages.KINDS[kind][3],
        "title": title, "year": year, "creator": creator or None,
        "why": why, "caveat": caveat or None,
        "source_label": source_label, "source_url": source_url,
    }


def _build() -> list[dict]:
    found: dict[tuple[str, str], dict] = {}

    def keep(entry: dict) -> None:
        key = (entry["kind"], title_pages.slugify(entry["title"]))
        current = found.get(key)
        # The first writing wins (trails are the most detailed); a later copy only fills a missing year or creator.
        if current is None:
            found[key] = entry
            return
        for field in ("year", "creator"):
            if current[field] is None and entry[field] is not None:
                current[field] = entry[field]
        if current["year"] is not None:
            current["slug"] = title_pages.title_slug(current["title"], current["year"])
            current["id"] = f"{current['kind']}/{current['slug']}"

    for slug, trail in TRAILS.items():
        for item in trail["items"]:
            creator = next((item["meta"][k] for k in CREATOR_META if item["meta"].get(k)), None)
            keep(_entry(title_pages.LIBRARY_TO_KIND[item["category"]], item["title"], item["meta"].get("year"), creator,
                        item["why"], item.get("caveat"), trail["name"], f"/discover/{slug}"))
    for slug, edition in MONTHLY_EDITIONS.items():
        for item in edition["items"]:
            creator = next((item["meta"][k] for k in CREATOR_META if item["meta"].get(k)), None)
            keep(_entry(title_pages.LIBRARY_TO_KIND[item["category"]], item["title"], item["meta"].get("year"), creator,
                        item["why"], item.get("caveat"), edition["name"], f"/discover/monthly/{slug}"))
    for collection in COLLECTIONS:
        for category, title, year, creator, note in collection["items"]:
            keep(_entry(title_pages.LIBRARY_TO_KIND[category], title, year, creator, note, None, collection["name"], None))
    from .if_you_liked import pool_sources
    for item, label, url in pool_sources():
        keep(_entry(item["kind"], item["title"], item["year"], item["creator"], item["why"], item["caveat"], label, url))
    order = {kind: index for index, kind in enumerate(KIND_ORDER)}
    return sorted(found.values(), key=lambda e: (order[e["kind"]], e["title"].casefold()))


def pool() -> list[dict]:
    """Every curated pick, built once per process from the editorial content in code."""
    global _pool
    if _pool is None:
        _pool = _build()
    return _pool


def find(kind: str, slug: str) -> Optional[dict]:
    for entry in pool():
        if entry["kind"] == kind and entry["slug"] == slug:
            return entry
    return None


def find_id(pick_id: str) -> Optional[dict]:
    kind, _, slug = (pick_id or "").partition("/")
    return find(kind, slug) if kind in title_pages.KINDS else None


def candidates(kind: Optional[str] = None) -> list[dict]:
    return [entry for entry in pool() if kind is None or entry["kind"] == kind]


def choose(kind: Optional[str] = None, exclude=(), rng: Optional[random.Random] = None) -> Optional[dict]:
    """A random pick, avoiding recently shown ones while anything else is left."""
    options = candidates(kind)
    recent = set(exclude)
    fresh = [entry for entry in options if entry["id"] not in recent]
    options = fresh or options
    return (rng or random).choice(options) if options else None


def of_the_day(day: Optional[date] = None) -> dict:
    """The same pick for everyone on a given day (the page's starting suggestion)."""
    entries = pool()
    day = day or date.today()
    return entries[zlib.crc32(day.isoformat().encode("ascii")) % len(entries)]


# ---------------------------------------------------------------- links and artwork

def collection_links(db: Session) -> dict[str, str]:
    """{collection name: public URL} for the editors' collections that are published and public."""
    try:
        rows = (db.query(models.Collection.id, models.Collection.name)
                .join(models.User, models.User.id == models.Collection.user_id)
                .filter(models.User.username == EDITOR_USERNAME, models.Collection.is_public == True)
                .all())
    except Exception:
        return {}
    names = {collection["name"] for collection in COLLECTIONS}
    return {name: f"/collections/public/{collection_id}" for collection_id, name in rows if name in names}


def title_details(index: list[dict]) -> dict[str, dict]:
    """{pick id: {"url", "image"}} for picks that already have a public title page."""
    by_slug = {(entry["kind"], entry["slug"]): entry for entry in index}
    by_base: dict[tuple[str, str], dict] = {}
    for entry in index:
        current = by_base.get((entry["kind"], entry["base"]))
        if current is None or entry["members"] > current["members"]:
            by_base[(entry["kind"], entry["base"])] = entry
    details = {}
    for pick in pool():
        match = by_slug.get((pick["kind"], pick["slug"]))
        if match is None and pick["year"] is None:
            # Catalog games carry no year; members' copies usually do.
            match = by_base.get((pick["kind"], title_pages.slugify(pick["title"])))
        if match is not None:
            details[pick["id"]] = {"url": f"/titles/{match['kind']}/{match['slug']}", "image": match.get("image")}
    return details


# ---------------------------------------------------------------- saving

def add_to_library(db: Session, user, pick: dict, image: Optional[str] = None) -> tuple[str, object]:
    """Add a curated pick to the member's library as not yet started. Does not commit.

    Returns ("existing" | "created", record). A title the member already has (same
    name, any case) is left exactly as it is.
    """
    kind = pick["kind"]
    model, _, category, _, _ = title_pages.KINDS[kind]
    normalized = title_pages.normalize(pick["title"])
    existing = db.query(model).filter(model.user_id == user.id, func.lower(func.trim(model.title)) == normalized).first()
    if existing is not None:
        return "existing", existing
    fields = {"user_id": user.id, "title": pick["title"]}
    if kind == "game":
        fields["release_date"] = datetime(pick["year"], 1, 1) if pick["year"] else None
    else:
        fields["year"] = pick["year"]
    if kind in CREATOR_FIELD:
        fields[CREATOR_FIELD[kind]] = pick["creator"] or ""
    safe = title_pages._safe_image(image)
    if safe:
        fields[title_pages.IMAGE_FIELD[kind]] = safe
    record = model(**fields)
    db.add(record)
    db.flush()
    return "created", record
