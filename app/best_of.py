"""Helpers for the "Best of the year" guides (/best-of/<year>/<format>).

The writing lives in best_of_guides.py. Movie, TV, anime, game, book and album
picks join the Pick for me pool (pick.py), so saving reuses the same paths as the
"If you liked" guides: members add a pick through POST /api/pick/add, and visitors
keep it in their browser-only guest list until they sign up. Manga, podcast and
audiobook picks are not in that pool (pick.KIND_ORDER has six formats); they save
through POST /api/best-of/add straight to their tracker, the way the holiday reading
guide's picks do (seasonal.extra_entry).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from . import title_pages
from .best_of_guides import GUIDES

BASE_PATH = "/best-of"
FORMAT_ORDER = ("movies", "tv", "anime", "games", "books", "music", "manga", "podcasts", "audiobooks")
EXTRA_KINDS = ("manga", "podcast", "audiobook")  # saved through extra_entry, never part of Pick for me


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


def picks(year: Optional[int] = None):
    """(guide slug, pick) for every pick, in display order, optionally for one year."""
    for year_value in years():
        if year is not None and year_value != year:
            continue
        for slug in for_year(year_value):
            for item in GUIDES[slug]["picks"]:
                yield slug, item


def anchor(item: dict) -> str:
    return "pick-" + title_pages.slugify(item["title"])


def pool_sources():
    """(pick, source label, link to the pick) for every Pick for me format, in guide order (builds the pool)."""
    for slug, entry in GUIDES.items():
        for item in entry["picks"]:
            if item["kind"] not in EXTRA_KINDS:
                yield item, source_label(slug), f"{path(slug)}#{anchor(item)}"


def pool_entry(item: dict) -> Optional[dict]:
    """The entry saving uses for a pick: Pick for me's (same kind and title), or extra_entry for manga, podcasts, audiobooks."""
    if item["kind"] in EXTRA_KINDS:
        from . import seasonal
        return seasonal.extra_entry(item)
    from . import pick

    wanted = (item["kind"], title_pages.slugify(item["title"]))
    for entry in pick.pool():
        if (entry["kind"], title_pages.slugify(entry["title"])) == wanted:
            return entry
    return None


def find_extra(kind: str, slug: str) -> Optional[tuple[str, dict]]:
    """For POST /api/best-of/add and the saved-before-sign-up import: (browse kind, entry) for a manga,
    podcast or audiobook pick."""
    if kind not in EXTRA_KINDS:
        return None
    for _, item in picks():
        if item["kind"] == kind:
            found = pool_entry(item)
            if found["slug"] == slug:
                return found["browse_kind"], found
    return None


def extra_details(index: list[dict]) -> dict[str, dict]:
    """{entry id: {"url", "image"}} for manga, podcast and audiobook picks members already track.

    pick.title_details only covers the Pick for me pool, so these are matched here the same
    way: the exact slug first, then the most-tracked title with the same base name.
    """
    by_slug = {(entry["kind"], entry["slug"]): entry for entry in index}
    by_base: dict[tuple[str, str], dict] = {}
    for entry in index:
        current = by_base.get((entry["kind"], entry["base"]))
        if current is None or entry["members"] > current["members"]:
            by_base[(entry["kind"], entry["base"])] = entry
    details = {}
    for _, item in picks():
        if item["kind"] not in EXTRA_KINDS:
            continue
        found = pool_entry(item)
        match = by_slug.get((item["kind"], found["slug"])) or by_base.get((item["kind"], title_pages.slugify(item["title"])))
        if match is not None:
            details[found["id"]] = {"url": f"/titles/{match['kind']}/{match['slug']}", "image": match.get("image")}
    return details


def library_states(db: Session, user_id: int, year: int) -> dict[str, str]:
    """{entry id: "done" | "tracked"} for that year's picks already in this member's library."""
    from . import in_order, seasonal

    items = []
    for _, item in picks(year):
        found = pool_entry(item)
        if found:
            items.append({"id": found["id"], "kind": item["kind"], "title": item["title"], "year": item["year"]})
    matchable = {"entries": items}
    matches = in_order.library_matches(db, user_id, matchable)
    matches.update(seasonal._extra_matches(db, user_id, matchable))
    return {pick_id: match["state"] for pick_id, match in matches.items()}
