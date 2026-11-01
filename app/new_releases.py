"""Helpers for the release guides (/new-releases and /new-releases/<slug>).

The writing lives in release_guides.py. A guide covers one stretch of the
calendar (a month, or a season) and goes format by format: the films, series,
games, anime and books coming out, which ones we think are worth planning
around, and what to watch, play or read first.

Every pick joins the Pick for me pool (pick.py) so it can be saved the same way
as the other guides' picks, but Pick for me only suggests it once its release
date has passed: nobody wants "start this tonight" for a game that is three
weeks away. A guide goes live on its ``published`` date, like the monthly
editions, so the next one can be written ahead.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from . import title_pages
from .release_guides import GUIDES

BASE_PATH = "/new-releases"
FORMAT_ORDER = ("movies", "tv", "games", "anime", "books")
FORMAT_LABELS = {"movies": "Movies", "tv": "TV", "games": "Games", "anime": "Anime", "books": "Books"}


def _today(today: Optional[date] = None) -> date:
    return today or datetime.utcnow().date()


def path(slug: str) -> str:
    return f"{BASE_PATH}/{slug}"


def published(today: Optional[date] = None) -> dict:
    """Guides whose publish date has come, newest first."""
    day = _today(today).isoformat()
    live = {slug: entry for slug, entry in GUIDES.items() if entry["published"] <= day}
    return dict(sorted(live.items(), key=lambda pair: pair[1]["published"], reverse=True))


def current(today: Optional[date] = None) -> Optional[str]:
    """The newest live guide whose stretch of the calendar includes today, else the newest live guide."""
    day = _today(today).isoformat()
    live = published(today)
    for slug, entry in live.items():
        if entry["starts"] <= day <= entry["ends"]:
            return slug
    return next(iter(live), None)


def picks(entry: dict) -> list[dict]:
    """Every pick across the guide's sections, in page order."""
    return [item for section in entry["sections"] for item in section["picks"]]


def anchor_id(item: dict) -> str:
    return "pick-" + title_pages.slugify(item["title"])


def is_out(item: dict, today: Optional[date] = None) -> bool:
    return item["date"] <= _today(today).isoformat()


def date_label(item: dict) -> str:
    """"November 20" or "February 2027" (for a month with no fixed day)."""
    parsed = date.fromisoformat(item["date"])
    if item.get("month_only"):
        return f"{parsed:%B} {parsed.year}"
    return f"{parsed:%B} {parsed.day}"


def source_label(slug: str) -> str:
    return GUIDES[slug]["name"]


def pool_sources(today: Optional[date] = None):
    """(pick, source label, link to the pick) for every pick in a live guide (used to build the Pick for me pool)."""
    for slug in published(today):
        entry = GUIDES[slug]
        for item in picks(entry):
            yield item, source_label(slug), f"{path(slug)}#{anchor_id(item)}"


def pool_entry(item: dict) -> Optional[dict]:
    """The Pick for me entry for a guide pick (same kind and title), whose id saving uses."""
    from . import pick

    wanted = (item["kind"], title_pages.slugify(item["title"]))
    for entry in pick.pool():
        if (entry["kind"], title_pages.slugify(entry["title"])) == wanted:
            return entry
    return None
