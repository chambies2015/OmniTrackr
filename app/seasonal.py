"""Helpers for the seasonal hubs (/halloween, /holidays), whose writing lives in seasonal_guides.py,
and the guides beside the holiday hub (holiday_guides.py: /holidays/thanksgiving and
/holidays/reading-and-listening), which share the hub's page parts and member API.

Every pick joins the Pick for me pool (pick.py), so saving reuses the same paths:
members add a pick through POST /api/pick/add, and visitors keep it in their
browser-only guest list. A member's progress through a hub is counted from their
own library each time it is asked for; nothing about it is stored.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from . import in_order, title_pages
from .holiday_guides import GUIDES as COMPANIONS
from .seasonal_guides import SEASONS

# Formats Pick for me doesn't suggest; picks in these are saved straight to their tracker.
EXTRA_KINDS = {"manga": "manga", "podcast": "podcasts", "audiobook": "audiobooks"}  # title kind -> browse kind


def season(slug: str) -> Optional[dict]:
    """A seasonal hub or one of the guides beside it (both have shelves of picks)."""
    return SEASONS.get(slug) or COMPANIONS.get(slug)


def companion(slug: str) -> Optional[dict]:
    return COMPANIONS.get(slug)


def companions_of(slug: str) -> list[tuple[str, dict]]:
    """The guides that sit beside a hub, in catalog order."""
    return [(key, entry) for key, entry in COMPANIONS.items() if entry["parent"] == slug]


def path(slug: str) -> str:
    return season(slug)["path"]


def picks(entry: dict) -> list[dict]:
    """Every pick across the season's shelves, in page order."""
    return [item for shelf in entry["shelves"] for item in shelf["picks"]]


def anchor_id(item: dict) -> str:
    return "pick-" + title_pages.slugify(item["title"])


def level_label(entry: dict, level: int) -> str:
    return next(name for value, name, _ in entry["scale"] if value == level)


def pool_sources():
    """(pick, source label, source path) for every pick (used to build the Pick for me pool)."""
    for slug, entry in SEASONS.items():
        label = f"{entry['name']} picks"
        for shelf in entry["shelves"]:
            for item in shelf["picks"]:
                yield item, label, f"{entry['path']}#{shelf['key']}"
    for slug, entry in COMPANIONS.items():
        for shelf in entry["shelves"]:
            for item in shelf["picks"]:
                if item["kind"] not in EXTRA_KINDS:
                    yield item, entry["name"], f"{entry['path']}#{shelf['key']}"


def extra_entry(item: dict) -> dict:
    """A manga, podcast or audiobook pick in the shape saving uses (Pick for me has no entry for it)."""
    slug = title_pages.title_slug(item["title"], item.get("year"))
    return {"id": f"{item['kind']}/{slug}", "kind": item["kind"], "slug": slug, "title": item["title"],
            "year": item.get("year"), "creator": item.get("creator"), "extra": item.get("extra") or {},
            "browse_kind": EXTRA_KINDS[item["kind"]]}


def find_extra(kind: str, slug: str) -> Optional[tuple[str, dict]]:
    """For the saved-before-sign-up import: (browse kind, entry) for a manga, podcast or audiobook pick."""
    if kind not in EXTRA_KINDS:
        return None
    for entry in COMPANIONS.values():
        for item in picks(entry):
            if item["kind"] == kind:
                found = extra_entry(item)
                if found["slug"] == slug:
                    return found["browse_kind"], found
    return None


def pool_entry(item: dict) -> Optional[dict]:
    """The entry saving uses for a pick: Pick for me's (same kind and title), or extra_entry for the other formats."""
    if item["kind"] in EXTRA_KINDS:
        return extra_entry(item)
    from . import if_you_liked
    return if_you_liked.pool_entry(item)


# ---------------------------------------------------------------- the season's window

def _bounds(entry: dict, year: int) -> tuple[date, date]:
    start, end = (date(year, *map(int, value.split("-"))) for value in entry["window"])
    return start, end


def in_window(entry: dict, today: Optional[date] = None) -> bool:
    today = today or datetime.utcnow().date()
    start, end = _bounds(entry, today.year)
    return start <= today <= end


def days_left(entry: dict, today: Optional[date] = None) -> int:
    today = today or datetime.utcnow().date()
    return max(0, (_bounds(entry, today.year)[1] - today).days)


def current(today: Optional[date] = None) -> Optional[str]:
    """The slug of the season running today, if any."""
    return next((slug for slug, entry in SEASONS.items() if in_window(entry, today)), None)


# ---------------------------------------------------------------- a member's progress

def _matchable(entry: dict) -> dict:
    """The season's picks in the shape in_order.library_matches reads."""
    items = []
    for item in picks(entry):
        pooled = pool_entry(item)
        items.append({"id": pooled["id"] if pooled else anchor_id(item), "kind": item["kind"],
                      "title": item["title"], "year": item["year"]})
    return {"entries": items}


def _extra_matches(db: Session, user_id: int, matchable: dict) -> dict[str, dict]:
    """library_matches for the formats it doesn't read (manga, podcasts, audiobooks), matched the same way."""
    found: dict[str, dict] = {}
    for kind in EXTRA_KINDS:
        items = [item for item in matchable["entries"] if item["kind"] == kind]
        if not items:
            continue
        wanted = set().union(*(in_order.names(item) for item in items))
        category = title_pages.KINDS[kind][2]
        for row_id, title, year, done in in_order._rows(db, user_id, kind, wanted):
            for item in items:
                if title not in in_order.names(item) or not in_order._same_year(item, year):
                    continue
                current = found.get(item["id"])
                if current is None or (done and current["state"] != "done"):
                    found[item["id"]] = {"state": "done" if done else "tracked",
                                         "library_url": f"/?library_category={category}&library_item={row_id}"}
    return found


def progress(db: Session, user_id: int, slug: str) -> dict:
    """Which of the season's picks are in this member's library, and which they have finished."""
    entry = season(slug)
    matchable = _matchable(entry)
    matches = in_order.library_matches(db, user_id, matchable)
    matches.update(_extra_matches(db, user_id, matchable))
    return {
        "entries": matches,
        "total": len(matchable["entries"]),
        "tracked": len(matches),
        "done": sum(1 for match in matches.values() if match["state"] == "done"),
    }
