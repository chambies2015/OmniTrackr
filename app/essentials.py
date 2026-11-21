"""The Essential 100 (/essentials): one hand-written canon page per format, 100 titles each.

The writing lives in essentials_<format>.py (one LIST per format); this module loads
it, gives every title an id, and answers the questions the pages ask: which titles a
member already has, which they have finished, and how to add one. Nothing about a
member is stored here. Their progress is read from their own library on every look,
the same way the best-of scorecard and the "In order" guides do it.

Saving copies only the title, year and creator (plus volumes for manga and narrator
and length for audiobooks). A title the member already has is left exactly as it is;
"Seen it" only marks a title finished when this page creates it.
"""
from __future__ import annotations

import importlib
import re
from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import title_pages

BASE_PATH = "/essentials"
FORMATS = ("movies", "tv", "anime", "games", "books", "music", "manga", "podcasts", "audiobooks")
SIZE = 100
FORMAT_LABELS = {"movies": "Films", "tv": "TV shows", "anime": "Anime", "games": "Games", "books": "Books",
                 "music": "Albums", "manga": "Manga", "podcasts": "Podcasts", "audiobooks": "Audiobooks"}
# Saved through browse.add_to_library (it fills volumes, narrator and length); the others through pick.add_to_library.
BROWSE_KINDS = {"manga": "manga", "podcast": "podcasts", "audiobook": "audiobooks"}
# Formats whose titles are matched on name and year. Remakes and re-releases share names
# (The Thing 1951 and 1982), so a year both sides know must agree within a year.
YEAR_CHECKED = {"movie", "tv", "anime", "game"}
UNDO_MINUTES = 30

_lists: Optional[dict] = None
_by_id: dict[str, dict] = {}


def _load() -> dict:
    """{format: list} for every format whose writing loads, in FORMATS order, with ids filled in."""
    global _lists, _by_id
    if _lists is not None:
        return _lists
    found, by_id = {}, {}
    for fmt in FORMATS:
        try:
            data = importlib.import_module(f".essentials_{fmt}", __package__).LIST
        except Exception:  # A list still being written must not take the others down.
            continue
        found[fmt] = _prepare(fmt, data)
        for item in found[fmt]["items"]:
            by_id[item["id"]] = item
    _lists, _by_id = found, by_id
    return found


def _prepare(fmt: str, data: dict) -> dict:
    kind = data["kind"]
    items = []
    for section in data["sections"]:
        for item in section["items"]:
            slug = title_pages.title_slug(item["title"], item.get("year"))
            item.update({
                "kind": kind, "format": fmt, "slug": slug, "id": f"{kind}/{slug}",
                "anchor": f"e-{slug}", "number": len(items) + 1, "section": section["key"],
            })
            items.append(item)
    data["items"] = items
    data["format"] = fmt
    return data


def lists() -> dict:
    return _load()


def get(fmt: str) -> Optional[dict]:
    return _load().get(fmt)


def available() -> list[str]:
    return list(_load())


def path(fmt: Optional[str] = None) -> str:
    return f"{BASE_PATH}/{fmt}" if fmt else BASE_PATH


def item_by_id(item_id: str) -> Optional[dict]:
    _load()
    return _by_id.get(item_id or "")


def all_items() -> Iterable[dict]:
    for data in _load().values():
        yield from data["items"]


def starters(fmt: str) -> list[dict]:
    return [item for item in get(fmt)["items"] if item.get("starter")]


def total_hours(fmt: str) -> float:
    return sum(item.get("hours") or 0 for item in get(fmt)["items"])


def done_label(fmt: str) -> str:
    """The button that marks a title finished: "Seen it", "Played it", "Read it"..."""
    return f'{get(fmt)["done_word"].capitalize()} it'


def anchor_url(item: dict) -> str:
    return f'{path(item["format"])}#{item["anchor"]}'


# Words that end in a full stop without ending a sentence ("Dr. Strangelove", "Mr. Darcy", "St. Petersburg").
_NOT_AN_END = {"mr", "mrs", "ms", "dr", "st", "jr", "sr", "vs", "no", "vol", "bros", "co", "mt", "ft", "prof", "rev",
               "gen", "lt", "col", "capt", "sgt", "inc", "ltd", "ave", "approx", "etc"}
_SENTENCE_END = re.compile(r'[.!?]["\u201d\u2019)]?(?=\s+["\u201c\u2018(]?[A-Z0-9])')


def first_sentence(text: str) -> str:
    """The first sentence of a blurb, for a one-line answer. Initials ("Monkey D. Luffy", "T. E. Lawrence")
    and abbreviations ("Dr.", "Mr.", "Super Mario Bros.") don't end it."""
    text = " ".join((text or "").split())
    for match in _SENTENCE_END.finditer(text):
        end = match.end()
        word = text[:match.start()].rsplit(" ", 1)[-1].lstrip("\"\u201c\u2018(")
        if len(word) <= 1 or "." in word or word.lower() in _NOT_AN_END:
            continue
        if len(text[:end].split()) < 4:  # "Comedy Bang! Bang!" is a name, not a sentence.
            continue
        return text[:end]
    return text


def for_title(kind: str, title: str, year=None) -> Optional[dict]:
    """The essential title a title page is about, if one of the lists has it (for a link back)."""
    wanted = title_pages.normalize(title)
    for item in all_items():
        film = kind == "movie" and item["kind"] == "anime" and (item.get("extra") or {}).get("film")
        if item["kind"] != kind and not film:
            continue
        if wanted not in names(item):
            continue
        if item["kind"] in YEAR_CHECKED and not _same_year(item.get("year"), year):
            continue
        return item
    return None


# ---------------------------------------------------------------- saving

def entry(item: dict) -> dict:
    """The shape the library helpers save: pick.add_to_library's, plus extra details for browse kinds."""
    kind = item["kind"]
    saved = {"id": item["id"], "kind": kind, "slug": item["slug"], "category": title_pages.KINDS[kind][2],
             "title": item["title"], "year": item.get("year"), "creator": item.get("creator") or None}
    if kind in BROWSE_KINDS:
        extra = {}
        details = item.get("extra") or {}
        if kind == "manga" and isinstance(details.get("volumes"), int):
            extra["volumes"] = details["volumes"]
        if kind == "audiobook":
            extra["narrator"] = details.get("narrator")
            extra["length_hours"] = details.get("length_hours")
        saved["extra"] = extra
        saved["browse_kind"] = BROWSE_KINDS[kind]
    return saved


def find(kind: str, slug: str) -> Optional[dict]:
    """For the saved-before-sign-up import: the saveable entry for a guest-list (kind, slug)."""
    item = item_by_id(f"{kind}/{slug}")
    return entry(item) if item else None


def add(db: Session, user, item: dict, seen: bool, image: Optional[str] = None) -> tuple[str, object]:
    """Add one title to the member's library. Does not commit.

    Returns ("created" | "existing", record). A new record is marked finished when
    ``seen``; a title the member already has (same name, any case) is never changed.
    """
    from . import browse, pick

    saved = entry(item)
    kind = item["kind"]
    # A "seen" title is created already finished: a friend's feed then shows it as added, not as
    # something finished just now (ticking 200 titles would otherwise post 200 finishes), and it
    # costs one write instead of two.
    if kind in BROWSE_KINDS:
        return browse.add_to_library(db, user, saved["browse_kind"], saved, image, finished=seen)
    return pick.add_to_library(db, user, saved, image, finished=seen)


def library_titles(db: Session, user_id: int, items: list[dict]) -> set[tuple[str, str]]:
    """(kind, normalized title) for the titles in ``items`` the member already has, one query per format.

    Matches the way the add helpers look for an existing title, so an import can skip
    those without asking about each one.
    """
    by_kind: dict[str, set[str]] = {}
    for item in items:
        by_kind.setdefault(item["kind"], set()).add(title_pages.normalize(item["title"]))
    found = set()
    for kind, titles in by_kind.items():
        model = title_pages.KINDS[kind][0]
        wanted = sorted(titles)
        for start in range(0, len(wanted), 500):
            for (title,) in db.query(func.lower(func.trim(model.title))).filter(
                    model.user_id == user_id, func.lower(func.trim(model.title)).in_(wanted[start:start + 500])):
                found.add((kind, title))
    return found


# ---------------------------------------------------------------- what a member already has

def names(item: dict) -> set[str]:
    return {title_pages.normalize(name) for name in [item["title"], *(item.get("aka") or ())]}


def _same_year(wanted, year) -> bool:
    return wanted is None or year is None or abs(int(year) - int(wanted)) <= 1


def _creator_matches(item: dict, creator) -> bool:
    mine, theirs = title_pages.normalize(item.get("creator") or ""), title_pages.normalize(creator or "")
    return not mine or not theirs or mine in theirs or theirs in mine


def _rows(db: Session, user_id: int, kind: str, wanted: set[str]):
    model = title_pages.KINDS[kind][0]
    year_column = model.release_date if kind == "game" else model.year
    complete = getattr(model, title_pages.COMPLETE_FIELD[kind])
    creator_field = title_pages.KINDS[kind][4]
    columns = [model.id, model.title, year_column, complete]
    if kind == "album" and creator_field:
        columns.append(getattr(model, creator_field))
    rows = (db.query(*columns)
            .filter(model.user_id == user_id, func.lower(func.trim(model.title)).in_(sorted(wanted)))
            .order_by(model.id).all())
    for row in rows:
        year = row[2]
        if kind == "game" and year is not None:
            year = year.year
        yield row[0], title_pages.normalize(row[1]), year, bool(row[3]), (row[4] if len(row) > 4 else None)


def _matches(item: dict, kind: str, title: str, year, creator) -> bool:
    if title not in names(item):
        return False
    if kind == "album":
        # Albums share names across artists ("Blue"); the artist decides when both are known.
        return _creator_matches(item, creator) if creator and item.get("creator") else _same_year(item.get("year"), year)
    if kind in YEAR_CHECKED:
        return _same_year(item.get("year"), year)
    return True


def library_states(db: Session, user_id: int, items: list[dict]) -> dict[str, dict]:
    """{item id: {"state": "done" | "tracked", "library_url"}} for the titles this member already has.

    One query per format. Anime films are also looked for among the member's movies,
    since plenty of people file Spirited Away there.
    """
    by_kind: dict[str, list[dict]] = {}
    for item in items:
        by_kind.setdefault(item["kind"], []).append(item)
        if item["kind"] == "anime" and (item.get("extra") or {}).get("film"):
            by_kind.setdefault("movie", []).append(item)
    found: dict[str, dict] = {}
    for kind, group in by_kind.items():
        wanted = set().union(*(names(item) for item in group))
        category = title_pages.KINDS[kind][2]
        for row_id, title, year, done, creator in _rows(db, user_id, kind, wanted):
            for item in group:
                if not _matches(item, kind, title, year, creator):
                    continue
                current = found.get(item["id"])
                if current is None or (done and current["state"] != "done"):
                    found[item["id"]] = {"state": "done" if done else "tracked",
                                         "library_url": f"/?library_category={category}&library_item={row_id}"}
    return found


def progress(states: dict, fmt: str) -> dict:
    items = get(fmt)["items"]
    done = sum(1 for item in items if states.get(item["id"], {}).get("state") == "done")
    tracked = sum(1 for item in items if states.get(item["id"], {}).get("state") == "tracked")
    return {"done": done, "tracked": tracked, "total": len(items)}


def finished_count(db: Session, user_id: int) -> int:
    """Essential titles this member has finished, across every list (the Essentials badge)."""
    states = library_states(db, user_id, list(all_items()))
    return sum(1 for match in states.values() if match["state"] == "done")


# ---------------------------------------------------------------- title pages and art

_details_cache: dict = {"index": None, "details": None}


def title_details(index: list[dict]) -> dict[str, dict]:
    """{item id: {"url", "image"}} for essential titles members track (they have a public title page).

    Matched the way pick.title_details matches: the exact slug first, then the most
    tracked title with the same base name. Kept until the search index is rebuilt.
    """
    cached = _details_cache
    if cached["index"] is index and cached["details"] is not None:
        return cached["details"]
    by_slug = {(entry["kind"], entry["slug"]): entry for entry in index}
    by_base: dict[tuple[str, str], dict] = {}
    for entry in index:
        current = by_base.get((entry["kind"], entry["base"]))
        if current is None or entry["members"] > current["members"]:
            by_base[(entry["kind"], entry["base"])] = entry
    details = {}
    for item in all_items():
        kinds = [item["kind"]] + (["movie"] if item["kind"] == "anime" and (item.get("extra") or {}).get("film") else [])
        match = None
        for kind in kinds:
            match = by_slug.get((kind, item["slug"]))
            if match is None:
                candidate = by_base.get((kind, title_pages.slugify(item["title"])))
                # Names shared by remakes or by two artists need the year to agree before we link.
                strict = item["kind"] in YEAR_CHECKED or item["kind"] == "album"
                if candidate is not None and (not strict or _same_year(item.get("year"), candidate.get("year"))):
                    match = candidate
            if match is not None:
                break
        if match is not None:
            details[item["id"]] = {"url": f"/titles/{match['kind']}/{match['slug']}", "image": match.get("image")}
    cached["index"], cached["details"] = index, details
    return details


def posters(db: Session, items: list[dict]) -> dict[str, str]:
    """{item id: poster} from the shared title facts cache (never waits on an outside lookup)."""
    from . import explore_art

    wanted = {item["id"]: (item["kind"], item["title"], item.get("year")) for item in items}
    try:
        found = explore_art.cached_posters(db, wanted.values())
    except Exception:
        db.rollback()
        return {}
    return {item_id: found[key] for item_id, key in wanted.items() if key in found}


def undo_allowed(record) -> bool:
    added = getattr(record, "added_at", None)
    return added is not None and (datetime.utcnow() - added).total_seconds() <= UNDO_MINUTES * 60
