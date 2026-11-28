"""The public binge calculator (/binge-calculator) and its "how long" guides.

The calculator works out how long a series takes and when you would finish.
Each guide (/binge-calculator/<slug>) does the same for one series from
hand-checked lengths in binge_guides*.py, broken down by season, arc, book or
film. Reading time starts from word counts turned into pages at
``WORDS_PER_PAGE``; listening time is the unabridged audiobook's length.

A visitor can also look up a title members track, in which case the lengths
come from the shared title cache only (nothing is fetched from outside on a
visitor's request). Members see how far through a guide's series they are and
what they have left across their library, read from their own rows on request;
nothing new is stored.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from . import episodes, in_order, models, time_spent, title_metadata, title_pages
from .binge_guides import GUIDES

BASE_PATH = "/binge-calculator"
WORDS_PER_PAGE = 300
PAGES_PER_HOUR = round(60 / time_spent.MINUTES_PER_PAGE)
WORDS_PER_MINUTE = round(WORDS_PER_PAGE * PAGES_PER_HOUR / 60)
LOOKUP_KINDS = {"tv": "tv-shows", "anime": "anime", "book": "books", "movie": "movies", "game": "video-games"}
PACES = (1, 2, 4)  # hours a day shown in each guide's pace table
KIND_ORDER = ("tv", "anime", "book", "film")
KIND_LABELS = {"tv": "TV series", "anime": "Anime", "book": "Book series", "film": "Film series"}
VERBS = {"tv": "watch", "anime": "watch", "book": "read", "film": "watch"}
LIBRARY_KIND = {"tv": "tv", "anime": "anime", "book": "book", "film": "movie"}
# Minutes the "skip intros" box takes off an episode: a cold open recap and credits
# for live action, the 90-second opening and ending for anime.
SKIP_MINUTES = {"tv": 2, "anime": 3}
# A guide is only offered to search engines with this much hand-written text.
MIN_INDEX_WORDS = 300


def path(slug: str) -> str:
    return f"{BASE_PATH}/{slug}"


def guide(slug: str) -> Optional[dict]:
    return GUIDES.get(slug)


def heading(entry: dict) -> str:
    return entry.get("heading") or f"How long does it take to {VERBS[entry['kind']]} {entry['name']}?"


def card_name(entry: dict) -> str:
    return entry.get("card") or entry["name"]


def by_kind() -> dict[str, list[str]]:
    return {kind: [slug for slug, entry in GUIDES.items() if entry["kind"] == kind] for kind in KIND_ORDER}


_TITLE_INDEX: dict = {}


def _title_index() -> dict:
    """{(library kind, normalized name): [(slug, guide, its titles, the title)]} in guide order.

    The guides never change while the app runs, so this is built once. Without it every
    lookup walked all the guides and normalized each name again, and "what you have left"
    does two lookups for every unfinished title in a library.
    """
    if not _TITLE_INDEX:
        built: dict = {}
        for slug, entry in GUIDES.items():
            items = titles(entry)
            for item in items:
                for name in in_order.names(item):
                    built.setdefault((item["kind"], name), []).append((slug, entry, items, item))
        # Filled in one step, so a request on another thread never reads half an index.
        _TITLE_INDEX.update(built)
    return _TITLE_INDEX


def _title_matches(kind: str, title: str, year=None):
    """Guide titles a library title could be, first match first."""
    for match in _title_index().get((kind, title_pages.normalize(title)), ()):
        if in_order._same_year(match[3], year):
            yield match


def known_length(kind: str, title: str, year=None) -> dict:
    """Checked numbers for one library title, where a guide covers it.

    ``total`` is minutes at the default pace. Shows also get ``episodes`` and books ``pages``.
    """
    for _, entry, items, item in _title_matches(kind, title, year):
        if item["part"] is not None:
            part = entry["parts"][int(item["part"])]
            known = {"total": minutes(entry, part)}
            if entry["kind"] == "book":
                known["pages"] = pages(part)
            return known
        parts = [part for part in core(entry) if unit(entry, part) == "episode"]
        if len(items) > 1:
            # A guide over two shows (Naruto, then Shippuden) names a part after each.
            parts = [part for part in parts if title_pages.normalize(part["name"]) == title_pages.normalize(item["title"])]
        episode_count = sum(count(part) for part in parts)
        if not episode_count:
            return {}
        seasonal = all(part["name"] == f"Season {index}" for index, part in enumerate(parts, 1))
        return {"total": sum(minutes(entry, part) for part in parts), "episodes": episode_count,
                "seasons": [count(part) for part in parts] if seasonal else None}
    return {}


def episodes_seen(known: dict, checkpoint) -> Optional[int]:
    """Episodes watched, from a member's place (season and episode) and a guide's season lengths.

    For a show whose episode list was never looked up, so the library has no running count of its own.
    """
    if not known.get("episodes") or checkpoint is None or checkpoint.unit != "episode" or not checkpoint.position:
        return None
    season = checkpoint.season or 1
    seasons = known.get("seasons") or []
    if season > 1 and season > len(seasons):
        return None
    return min(known["episodes"], sum(seasons[:season - 1]) + checkpoint.position) or None


# ---------------------------------------------------------------- lengths

def unit(entry: dict, part: dict) -> str:
    """What one item of this part is called: episode, film, special or book."""
    return part.get("unit") or {"tv": "episode", "anime": "episode", "book": "book", "film": "film"}[entry["kind"]]


def count(part: dict, alt: bool = False) -> int:
    """Episodes in a part (1 for a book or film). ``alt`` leaves out its filler."""
    episodes_in_part = part.get("episodes", 1)
    return episodes_in_part - (part.get("skip", 0) if alt else 0)


def pages(part: dict) -> int:
    return round(part["words"] / WORDS_PER_PAGE)


def minutes(entry: dict, part: dict, alt: bool = False) -> float:
    """Minutes one part takes at the default pace. ``alt`` is the guide's other version."""
    if entry["kind"] == "book":
        return part["words"] / WORDS_PER_MINUTE
    if alt and part.get("alt"):
        return part["alt"]
    if "total" in part:
        return part["total"]
    if "episodes" in part:
        return count(part, alt) * part["minutes"]
    return part["minutes"]


def core(entry: dict) -> list[dict]:
    """The parts that count toward the headline total (everything not marked optional)."""
    return [part for part in entry["parts"] if not part.get("optional")]


def totals(entry: dict, alt: bool = False, parts: Optional[list] = None) -> dict:
    parts = core(entry) if parts is None else parts
    result = {
        "minutes": sum(minutes(entry, part, alt) for part in parts),
        "parts": len(parts),
        "episodes": sum(count(part, alt) for part in parts if unit(entry, part) == "episode"),
        "extras": sum(count(part) for part in parts if unit(entry, part) in ("special", "film")),
    }
    if entry["kind"] == "book":
        result["words"] = sum(part["words"] for part in parts)
        result["pages"] = sum(pages(part) for part in parts)
        result["audio"] = sum(part["audio"] for part in parts)
    return result


def days_at(total_minutes: float, hours_per_day: float) -> int:
    return int(-(-total_minutes // (hours_per_day * 60)))


def words(entry: dict) -> int:
    """Hand-written words in a guide (not the numbers the page works out)."""
    texts = [entry["summary"], *entry["lead"]]
    for _, title, paragraphs in entry["sections"]:
        texts += [title, *paragraphs]
    texts += [question + " " + answer for question, answer in entry["faq"]]
    texts += [part["note"] for part in entry["parts"] if part.get("note")]
    if entry.get("alt"):
        texts.append(entry["alt"]["note"])
    return sum(len(text.split()) for text in texts)


def is_indexable(entry: dict) -> bool:
    return words(entry) >= MIN_INDEX_WORDS


def planner(entry: dict) -> dict:
    """What the page's planner script needs, kept small: one row per part."""
    rows = []
    for index, part in enumerate(entry["parts"]):
        row = {"id": str(index), "name": part["name"], "unit": unit(entry, part), "n": count(part),
               "min": round(minutes(entry, part), 1)}
        if part.get("optional"):
            row["optional"] = True
        if entry["kind"] == "book":
            row["pages"], row["audio"] = pages(part), part["audio"]
        elif entry.get("alt"):
            row["altN"], row["altMin"] = count(part, True), round(minutes(entry, part, True), 1)
        rows.append(row)
    return {
        "slug": next(slug for slug, value in GUIDES.items() if value is entry),
        # Names are written to sit mid-sentence ("the Marvel Infinity Saga"); the planner shows them alone.
        "name": entry["name"][:1].upper() + entry["name"][1:], "kind": entry["kind"], "parts": rows,
        "skip": entry.get("skip_minutes", SKIP_MINUTES.get(entry["kind"], 0)),
        "alt": entry["alt"]["label"] if entry.get("alt") else None,
        "pagesPerHour": PAGES_PER_HOUR,
    }


# ---------------------------------------------------------------- saving and matching

def titles(entry: dict) -> list[dict]:
    """The library titles a guide covers, each tied to the part it stands for (books and films)."""
    if entry["kind"] in ("tv", "anime"):
        return [{"id": f"t{index}", "part": None, "optional": False, **item, "creator": item.get("creator")}
                for index, item in enumerate(entry["titles"])]
    kind = LIBRARY_KIND[entry["kind"]]
    return [{"id": str(index), "part": str(index), "kind": kind, "title": part.get("title") or part["name"],
             "year": part.get("year"), "creator": part.get("creator"), "optional": bool(part.get("optional")),
             # The short name on the page is also a name members save it under.
             "aka": [part["name"], *part.get("aka", ())]}
            for index, part in enumerate(entry["parts"]) if unit(entry, part) in ("book", "film")]


def as_order(entry: dict) -> dict:
    """The guide's titles shaped like an "In order" guide, so its library matching can be reused."""
    return {"entries": titles(entry)}


def saveable(item: dict) -> dict:
    return in_order.saveable(item)


def find(kind: str, slug: str) -> Optional[dict]:
    """The saveable title for a guest-list item saved from a guide."""
    for entry in GUIDES.values():
        for item in titles(entry):
            if item["kind"] == kind and title_pages.title_slug(item["title"], item["year"]) == slug:
                return saveable(item)
    return None


def for_title(kind: str, title: str, year=None) -> Optional[str]:
    """The guide whose series is (or includes) this title page's title, if there is one."""
    return next((slug for slug, _, _, _ in _title_matches(kind, title, year)), None)


def _watched(db: Session, user_id: int, kind: str, row_id: int) -> Optional[int]:
    """Episodes the member has ticked off on one show, from their saved checkpoint."""
    model, _, category, _, _ = title_pages.KINDS[kind]
    item = db.query(model).filter(model.id == row_id, model.user_id == user_id).first()
    if item is None:
        return None
    summary = episodes.progress_map(db, user_id, category, [item]).get(item.id) or {}
    return summary.get("watched") or None


def _watched_by_season(db: Session, user_id: int, kind: str, item: dict, row_id: int) -> Optional[int]:
    category = title_pages.KINDS[kind][2]
    checkpoint = db.query(models.ProgressCheckpoint).filter(
        models.ProgressCheckpoint.user_id == user_id, models.ProgressCheckpoint.category == category,
        models.ProgressCheckpoint.item_id == row_id).first()
    return episodes_seen(known_length(kind, item["title"], item["year"]), checkpoint)


def progress(db: Session, user_id: int, entry: dict) -> dict:
    """Where a member is in a guide's series, from their own library."""
    order = as_order(entry)
    matches = in_order.library_matches(db, user_id, order)
    items = titles(entry)
    counted = [item for item in items if not item["optional"]]
    result = {
        "titles": {item["id"]: matches[item["id"]]["state"] for item in items if item["id"] in matches},
        "done_parts": [item["part"] for item in items if item["part"] and matches.get(item["id"], {}).get("state") == "done"],
        "tracked": sum(1 for item in counted if item["id"] in matches),
        "done": sum(1 for item in counted if matches.get(item["id"], {}).get("state") == "done"),
        "total": len(counted),
        "missing": [item["id"] for item in counted if item["id"] not in matches],
        "watched": None,
    }
    if entry["kind"] in ("tv", "anime") and len(items) == 1 and items[0]["id"] in matches:
        match = matches[items[0]["id"]]
        row_id = int(match["library_url"].rsplit("=", 1)[1])
        if match["state"] != "done":
            result["watched"] = (_watched(db, user_id, items[0]["kind"], row_id)
                                 or _watched_by_season(db, user_id, items[0]["kind"], items[0], row_id))
    return result


def add_titles(db: Session, user, entry: dict, image_for=None) -> tuple[list, list]:
    """Add the guide's main titles the member does not have yet, as not started. Does not commit."""
    wanted = [item["id"] for item in titles(entry) if not item["optional"]]
    return in_order.add_entries(db, user, as_order(entry), wanted, image_for=image_for)


# ---------------------------------------------------------------- the member's own list

MINE_CATEGORIES = ("tv-shows", "anime", "books", "movies", "video-games", "manga", "audiobooks")
MINE_LIMIT = 12
MINE_SCAN = 400  # newest rows read per shelf; a huge backlog is summarised from these


def mine(db: Session, user: models.User) -> dict:
    """Unfinished titles in the member's library with the time each has left.

    Uses the same lengths as the Statistics tab's time spent (``time_spent``):
    cached running times and episode lists where a title page has looked them up,
    the member's own counts, and typical lengths otherwise. Steam playtime is
    left out, since hours played say nothing about hours left.
    """
    checkpoints = {(entry.category, entry.item_id): entry for entry in db.query(models.ProgressCheckpoint).filter(
        models.ProgressCheckpoint.user_id == user.id, models.ProgressCheckpoint.unit.is_not(None))}
    rows = []
    for category in MINE_CATEGORIES:
        kind = time_spent.CATEGORIES[category][0]
        model = title_pages.KINDS[kind][0]
        done = getattr(model, title_pages.COMPLETE_FIELD[kind])
        items = (db.query(model).filter(model.user_id == user.id, done.isnot(True))
                 .order_by(model.id.desc()).limit(MINE_SCAN).all())
        if not items:
            continue
        keys = {item.id: title_metadata.cache_key(kind, title_pages.normalize(item.title or ""),
                                                  title_pages.item_year(kind, item)) for item in items}
        facts = time_spent._cached_facts(db, list(keys.values()))
        shows = episodes.progress_map(db, user.id, category, items) if category in episodes.KINDS else {}
        for item in items:
            item_facts = facts.get(keys[item.id], {})
            show = shows.get(item.id) or {}
            full, typical = time_spent.full_minutes(category, item, item_facts, show.get("total"))
            spent, _ = time_spent.partial_minutes(category, item, item_facts, show.get("watched"),
                                                  checkpoints.get((category, item.id)))
            known = known_length(kind, item.title or "", title_pages.item_year(kind, item))
            if known and full:
                # A guide has the checked length, so it replaces the estimate and keeps the share done.
                share = spent / full
                if known.get("episodes"):
                    seen = show.get("watched") or episodes_seen(known, checkpoints.get((category, item.id))) or 0
                    share = seen / known["episodes"]
                full, typical = known["total"], False
                spent = min(1.0, share) * full
            left = max(0.0, full - spent)
            if left < 1:
                continue
            rows.append({
                "kind": kind, "label": title_pages.KINDS[kind][3], "title": item.title or "",
                "minutes": round(left), "started": spent > 0, "typical": bool(typical),
                "percent": round(100 * spent / full) if full and spent else 0,
                "guide": for_title(kind, item.title or "", title_pages.item_year(kind, item)),
            })
    started = [row for row in rows if row["started"]]
    # In-progress titles first (closest to done on top), then the shortest things not yet started.
    started.sort(key=lambda row: row["minutes"])
    waiting = sorted((row for row in rows if not row["started"]), key=lambda row: row["minutes"])
    listed = (started + waiting)[:MINE_LIMIT]
    return {
        "titles": listed,
        "count": len(rows),
        "started": len(started),
        "minutes": sum(row["minutes"] for row in rows),
        "started_minutes": sum(row["minutes"] for row in started),
        "typical": sum(1 for row in rows if row["typical"]),
    }


# ---------------------------------------------------------------- cache-only lookup

def lookup(db: Session, kind: str, title: str, year: Optional[int]) -> dict:
    """Lengths for a title from the shared cache. Missing numbers come back as None."""
    category = LOOKUP_KINDS[kind]
    key = title_metadata.cache_key(kind, title_pages.normalize(title), year)
    data, _ = title_metadata.cached(db, key)
    facts = time_spent._facts(data)
    result = {"kind": kind, "title": title, "year": year, "episodes": None, "minutes": None, "pages": None,
              "hours": None, "guide": for_title(kind, title, year)}
    if kind in ("tv", "anime"):
        layout = episodes.cached_layouts(db, [episodes.layout_key(category, title, year)])
        seasons = next(iter(layout.values()), [])
        result["episodes"] = sum(entry["episodes"] for entry in seasons) or time_spent.parse_count(facts.get("Episodes"))
        per_episode = time_spent.parse_minutes(facts.get("Episode length"))
        result["minutes"] = round(per_episode) if per_episode else None
    elif kind == "movie":
        running = time_spent.parse_minutes(facts.get("Running time"))
        result["minutes"] = round(running) if running else None
    elif kind == "game":
        playtime = time_spent.parse_minutes(facts.get("Average playtime"))
        result["hours"] = round(playtime / 60, 1) if playtime else None
    else:
        result["pages"] = time_spent.parse_count(facts.get("Pages"))
    # Where a guide covers the title, its checked numbers win, so the hub and the guide agree.
    known = known_length(kind, title, year)
    if known.get("episodes"):
        result["episodes"], result["minutes"] = known["episodes"], round(known["total"] / known["episodes"], 1)
    elif kind == "movie" and known:
        result["minutes"] = round(known["total"])
    elif kind == "book" and known:
        result["pages"] = known["pages"]
    return result
