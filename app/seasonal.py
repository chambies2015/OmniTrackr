"""Helpers for the seasonal hubs (/halloween, /holidays), whose writing lives in seasonal_guides.py.

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
from .seasonal_guides import SEASONS


def season(slug: str) -> Optional[dict]:
    return SEASONS.get(slug)


def path(slug: str) -> str:
    return SEASONS[slug]["path"]


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


def pool_entry(item: dict) -> Optional[dict]:
    """The Pick for me entry for a pick (same kind and title), whose id saving uses."""
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


def progress(db: Session, user_id: int, slug: str) -> dict:
    """Which of the season's picks are in this member's library, and which they have finished."""
    entry = SEASONS[slug]
    matchable = _matchable(entry)
    matches = in_order.library_matches(db, user_id, matchable)
    return {
        "entries": matches,
        "total": len(matchable["entries"]),
        "tracked": len(matches),
        "done": sum(1 for match in matches.values() if match["state"] == "done"),
    }
