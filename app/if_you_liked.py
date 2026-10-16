"""Helpers for the "If you liked..." guides (/if-you-liked/<slug>).

The writing lives in if_you_liked_guides.py. Every pick also joins the Pick for me
pool (pick.py), so saving reuses the same paths: members add a pick through
POST /api/pick/add, and visitors keep it in their browser-only guest list, which
POST /api/guest-list/import moves into their new library. Only the title, year
and creator are ever copied into a library.
"""
from __future__ import annotations

from typing import Optional

from . import title_pages
from .if_you_liked_guides import GUIDES

BASE_PATH = "/if-you-liked"
KIND_ORDER = ("movie", "tv", "anime", "game", "book", "album")


def path(slug: str) -> str:
    return f"{BASE_PATH}/{slug}"


def guide(slug: str) -> Optional[dict]:
    return GUIDES.get(slug)


def source_label(slug: str) -> str:
    return f"If you liked {GUIDES[slug]['anchor']['title']}"


def pool_sources():
    """(pick, source label, source path) for every pick, in guide order (used to build the Pick for me pool)."""
    for slug, entry in GUIDES.items():
        for item in entry["picks"]:
            yield item, source_label(slug), path(slug)


def pool_entry(item: dict) -> Optional[dict]:
    """The Pick for me entry for a guide pick (same kind and title), whose id saving uses."""
    from . import pick

    wanted = (item["kind"], title_pages.slugify(item["title"]))
    for entry in pick.pool():
        if (entry["kind"], title_pages.slugify(entry["title"])) == wanted:
            return entry
    return None


def for_title(kind: str, title: str) -> Optional[str]:
    """The slug of the guide written about this title, if there is one."""
    wanted = (kind, title_pages.slugify(title))
    for slug, entry in GUIDES.items():
        anchor = entry["anchor"]
        if (anchor["kind"], title_pages.slugify(anchor["title"])) == wanted:
            return slug
    return None


def related(slug: str, limit: int = 3) -> list[str]:
    """Other guides, those about the same format first, in catalog order."""
    kind = GUIDES[slug]["anchor"]["kind"]
    others = [other for other in GUIDES if other != slug]
    others.sort(key=lambda other: GUIDES[other]["anchor"]["kind"] != kind)
    return others[:limit]


def formats(entry: dict) -> list[str]:
    """The kinds a guide's picks cover, in display order."""
    kinds = {item["kind"] for item in entry["picks"]}
    return [kind for kind in KIND_ORDER if kind in kinds]
