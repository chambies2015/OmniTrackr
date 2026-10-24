"""Helpers for the "Best of the year" guides (/best-of/<year>/<format>).

The writing lives in best_of_guides.py. Every pick also joins the Pick for me pool
(pick.py), so saving reuses the same paths as the "If you liked" guides: members
add a pick through POST /api/pick/add, and visitors keep it in their browser-only
guest list until they sign up.
"""
from __future__ import annotations

from typing import Optional

from . import title_pages
from .best_of_guides import GUIDES

BASE_PATH = "/best-of"
FORMAT_ORDER = ("movies", "tv", "anime", "games", "books")


def path(slug: str) -> str:
    entry = GUIDES[slug]
    return f"{BASE_PATH}/{entry['year']}/{entry['format']}"


def find(year: int, fmt: str) -> Optional[str]:
    """The slug of the guide for this year and format, if there is one."""
    for slug, entry in GUIDES.items():
        if entry["year"] == year and entry["format"] == fmt:
            return slug
    return None


def years() -> list[int]:
    return sorted({entry["year"] for entry in GUIDES.values()}, reverse=True)


def for_year(year: int) -> list[str]:
    """That year's guides in display order."""
    slugs = [slug for slug, entry in GUIDES.items() if entry["year"] == year]
    return sorted(slugs, key=lambda slug: FORMAT_ORDER.index(GUIDES[slug]["format"]))


def source_label(slug: str) -> str:
    return GUIDES[slug]["name"]


def pool_sources():
    """(pick, source label, link to the pick) for every pick, in guide order (used to build the Pick for me pool)."""
    for slug, entry in GUIDES.items():
        for item in entry["picks"]:
            yield item, source_label(slug), f"{path(slug)}#pick-{title_pages.slugify(item['title'])}"


def pool_entry(item: dict) -> Optional[dict]:
    """The Pick for me entry for a guide pick (same kind and title), whose id saving uses."""
    from . import pick

    wanted = (item["kind"], title_pages.slugify(item["title"]))
    for entry in pick.pool():
        if (entry["kind"], title_pages.slugify(entry["title"])) == wanted:
            return entry
    return None
