"""Helpers for the "In order" guides (/in-order/<slug>): which order to watch, read and play a franchise in.

The writing lives in in_order_guides.py. Members see how far through a franchise
they are, worked out from their own library on request (nothing new is stored),
and can add the entries they are missing. Visitors keep entries in the browser-only
guest list, which POST /api/guest-list/import moves into their new library through
find() below. Only the title, year and creator are ever copied into a library.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import pick, title_pages
from .in_order_guides import GUIDES

BASE_PATH = "/in-order"
KIND_ORDER = ("movie", "tv", "anime", "game", "book", "album")


def path(slug: str) -> str:
    return f"{BASE_PATH}/{slug}"


def guide(slug: str) -> Optional[dict]:
    return GUIDES.get(slug)


def entries(entry: dict) -> dict[str, dict]:
    """{entry id: entry} for one guide."""
    return {item["id"]: item for item in entry["entries"]}


def recommended(entry: dict) -> list[dict]:
    """The guide's entries in its recommended (first) order, then any it leaves out, in catalog order."""
    by_id = entries(entry)
    ordered = [by_id[item_id] for item_id in entry["orders"][0]["ids"]]
    listed = {item["id"] for item in ordered}
    return ordered + [item for item in entry["entries"] if item["id"] not in listed]


def core(entry: dict) -> list[dict]:
    """The entries that count toward finishing the franchise (everything not marked optional)."""
    return [item for item in recommended(entry) if not item.get("optional")]


def formats(entry: dict) -> list[str]:
    kinds = {item["kind"] for item in entry["entries"]}
    return [kind for kind in KIND_ORDER if kind in kinds]


def positions(entry: dict, item_id: str) -> list[tuple[str, int]]:
    """(order name, 1-based position) for every order that includes this entry."""
    return [(order["name"], order["ids"].index(item_id) + 1) for order in entry["orders"] if item_id in order["ids"]]


def related(slug: str, limit: int = 3) -> list[str]:
    """Other guides, those sharing a format with this one first, in catalog order."""
    kinds = set(formats(GUIDES[slug]))
    others = [other for other in GUIDES if other != slug]
    others.sort(key=lambda other: not kinds & set(formats(GUIDES[other])))
    return others[:limit]


def anchor_id(item: dict) -> str:
    return "entry-" + item["id"]


# ---------------------------------------------------------------- saving and matching

def saveable(item: dict) -> dict:
    """The fields saving needs (shaped like a Pick for me entry): kind, slug, title, year, creator."""
    slug = title_pages.title_slug(item["title"], item["year"])
    return {"id": f"{item['kind']}/{slug}", "kind": item["kind"], "slug": slug, "category": title_pages.KINDS[item["kind"]][2],
            "title": item["title"], "year": item["year"], "creator": item.get("creator") or None}


def find(kind: str, slug: str) -> Optional[dict]:
    """The saveable entry for a guest-list item saved from a guide (any guide)."""
    for entry in GUIDES.values():
        for item in entry["entries"]:
            if item["kind"] == kind and title_pages.title_slug(item["title"], item["year"]) == slug:
                return saveable(item)
    return None


def names(item: dict) -> set[str]:
    """Every normalized title a member may have saved this entry under."""
    return {title_pages.normalize(name) for name in [item["title"], *item.get("aka", ())]}


def _same_year(item: dict, year) -> bool:
    # Remakes and re-releases share titles (Dune 1984 and Dune 2021), so a known year must agree.
    return year is None or item["year"] is None or abs(int(year) - item["year"]) <= 1


def _rows(db: Session, user_id: int, kind: str, wanted: set[str]):
    model = title_pages.KINDS[kind][0]
    year_column = model.release_date if kind == "game" else model.year
    complete = getattr(model, title_pages.COMPLETE_FIELD[kind])
    rows = (db.query(model.id, model.title, year_column, complete)
            .filter(model.user_id == user_id, func.lower(func.trim(model.title)).in_(sorted(wanted)))
            .order_by(model.id).all())
    for row_id, title, year, done in rows:
        if kind == "game" and year is not None:
            year = year.year
        yield row_id, title_pages.normalize(title), year, bool(done)


def library_matches(db: Session, user_id: int, entry: dict) -> dict[str, dict]:
    """{entry id: {"state": "done" | "tracked", "library_url"}} for entries this member already has."""
    found: dict[str, dict] = {}
    for kind in formats(entry):
        items = [item for item in entry["entries"] if item["kind"] == kind]
        wanted = set().union(*(names(item) for item in items))
        category = title_pages.KINDS[kind][2]
        for row_id, title, year, done in _rows(db, user_id, kind, wanted):
            for item in items:
                if title not in names(item) or not _same_year(item, year):
                    continue
                current = found.get(item["id"])
                if current is None or (done and current["state"] != "done"):
                    found[item["id"]] = {"state": "done" if done else "tracked",
                                         "library_url": f"/?library_category={category}&library_item={row_id}"}
    return found


def progress(db: Session, user_id: int, entry: dict) -> dict:
    """How far through the franchise a member is, from their own library."""
    matches = library_matches(db, user_id, entry)
    counted = core(entry)
    done = sum(1 for item in counted if matches.get(item["id"], {}).get("state") == "done")
    upcoming = next((item for item in counted if matches.get(item["id"], {}).get("state") != "done"), None)
    missing = [item["id"] for item in recommended(entry) if item["id"] not in matches and not item.get("optional")]
    return {
        "entries": matches,
        "done": done,
        "total": len(counted),
        "tracked": sum(1 for item in counted if item["id"] in matches),
        "next": {"id": upcoming["id"], "title": upcoming["title"]} if upcoming else None,
        "missing": missing,
    }


def add_entries(db: Session, user, entry: dict, item_ids: list[str], image_for=None) -> tuple[list, list]:
    """Add the chosen entries the member does not have yet, as not started. Does not commit.

    Returns (added, existing) as lists of {"id", "title"}. An entry the member already
    has under any of its titles is left exactly as it is.
    """
    by_id = entries(entry)
    chosen = [by_id[item_id] for item_id in dict.fromkeys(item_ids) if item_id in by_id]
    matches = library_matches(db, user.id, entry)
    added, existing = [], []
    for item in chosen:
        if item["id"] in matches:
            existing.append({"id": item["id"], "title": item["title"]})
            continue
        fields = saveable(item)
        image = image_for(fields) if image_for else None
        state, record = pick.add_to_library(db, user, fields, image)
        (added if state == "created" else existing).append({"id": item["id"], "title": record.title})
    return added, existing


# ---------------------------------------------------------------- title pages and artwork

def for_title(kind: str, title: str, year=None) -> list[tuple[str, dict]]:
    """(guide slug, entry) for every guide that includes this title."""
    wanted = title_pages.normalize(title)
    found = []
    for slug, entry in GUIDES.items():
        for item in entry["entries"]:
            if item["kind"] == kind and wanted in names(item) and _same_year(item, year):
                found.append((slug, item))
                break
    return found


_details_cache: dict = {"index": None, "details": None}


def title_details(index: list[dict]) -> dict[str, dict]:
    """{saveable id: {"url", "image"}} for entries that already have a public title page (cached per index)."""
    cached = _details_cache
    if cached["index"] is index and cached["details"] is not None:
        return cached["details"]
    by_slug = {(row["kind"], row["slug"]): row for row in index}
    by_base: dict[tuple[str, str], dict] = {}
    for row in index:
        current = by_base.get((row["kind"], row["base"]))
        if current is None or row["members"] > current["members"]:
            by_base[(row["kind"], row["base"])] = row
    details = {}
    for entry in GUIDES.values():
        for item in entry["entries"]:
            fields = saveable(item)
            match = by_slug.get((fields["kind"], fields["slug"]))
            if match is None and fields["kind"] == "game":
                # Catalog games often carry no year.
                match = by_base.get((fields["kind"], title_pages.slugify(item["title"])))
            if match is not None:
                details[fields["id"]] = {"url": f"/titles/{match['kind']}/{match['slug']}", "image": match.get("image")}
    cached["index"], cached["details"] = index, details
    return details
