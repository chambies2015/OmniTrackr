"""Site search: one box for titles, guides, pages and people.

The header search, the /search page and the dashboard's Ctrl+K box all read
from here. Titles come from title_search (titles members track, each with a
public /titles page); guides are the hand-written pages (franchise orders,
"If you liked", binge lengths, best-of lists, release guides, switch guides,
Discover); pages are the hubs in the site menu; people are the /people and
/studios pages that have enough titles to be worth a visit.

Nothing here reads a member's library or says who tracks what. Titles carry
the same member count their /titles page already shows.

Adding a family of guides is one entry in _guide_sources().
"""
from __future__ import annotations

import difflib
import os
import threading
import time
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from . import image_sizes, title_pages, title_search

QUERY_MAX = title_search.QUERY_MAX
KIND_ORDER = tuple(title_pages.KINDS)
# Short names for the format filter.
KIND_FILTERS = {"movie": "Movies", "tv": "TV", "anime": "Anime", "game": "Games", "album": "Music",
                "book": "Books", "manga": "Manga", "podcast": "Podcasts", "audiobook": "Audiobooks"}
GUIDE_LIMIT = 4
PEOPLE_LIMIT = 3
POPULAR_LIMIT = 8
PEOPLE_CACHE_SECONDS = 30 * 60
SUGGEST_CUTOFF = 0.78


def _words(text: str) -> list[str]:
    slug = title_pages.slugify(text or "")
    return [] if slug == "title" and "title" not in (text or "").lower() else [w for w in slug.split("-") if w]


def _query(text: str) -> tuple[str, list[str]]:
    """(slug, tokens) for a search box value; tokens are empty when there's nothing to search."""
    text = (text or "")[:QUERY_MAX]
    tokens = _words(text)
    if len("".join(tokens)) < 2:
        return "", []
    return "-".join(tokens), tokens


def _excerpt(text: str, limit: int = 150) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:.")
    return cut + "…"


# ---------------------------------------------------------------- guides and pages

def _entry(title: str, url: str, section: str, detail: str = "", also=()) -> dict:
    primary = set(_words(title))
    secondary = set()
    for text in also:
        if text:
            secondary.update(_words(str(text)))
    return {"title": title, "url": url, "section": section, "detail": _excerpt(detail),
            "base": title_pages.slugify(title), "primary": primary, "secondary": secondary - primary}


def _guide_sources(today: date) -> list[dict]:
    from . import best_of, binge_calculator, if_you_liked, in_order, new_releases, switch_guides
    from .best_of_guides import GUIDES as BEST_OF
    from .binge_guides import GUIDES as BINGE
    from .discover_catalog import TRAILS
    from .discover_guides import GUIDES as DISCOVER
    from .if_you_liked_guides import GUIDES as LIKED
    from .in_order_guides import GUIDES as ORDERS

    entries = []
    for slug, guide in ORDERS.items():
        also = [guide.get("search_title")]
        for item in guide.get("entries", []):
            also.append(item.get("title"))
            also.extend(item.get("aka") or [])
        entries.append(_entry(f"{guide['name']} in order", in_order.path(slug), "In order", guide.get("summary", ""), also))
    for slug, guide in BINGE.items():
        also = [guide["name"], binge_calculator.card_name(guide), "how long binge"]
        also.extend(item.get("title") for item in guide.get("titles") or [])
        entries.append(_entry(binge_calculator.heading(guide), binge_calculator.path(slug), "How long it takes",
                              guide.get("summary", ""), also))
    for slug, guide in LIKED.items():
        anchor = guide.get("anchor") or {}
        also = [guide.get("search_title"), anchor.get("creator")]
        also.extend(item.get("title") for item in guide.get("picks") or [])
        entries.append(_entry(f"If you liked {anchor.get('title', slug)}", if_you_liked.path(slug), "If you liked",
                              guide.get("summary", ""), also))
    for slug, guide in BEST_OF.items():
        also = [guide.get("search_title")]
        also.extend(item.get("title") for item in guide.get("picks") or [])
        entries.append(_entry(guide["name"], best_of.path(slug), "Best of", guide.get("summary", ""), also))
    for slug, guide in new_releases.published(today).items():
        entries.append(_entry(guide["name"], new_releases.path(slug), "Release guide", guide.get("summary", ""),
                              [guide.get("search_title")]))
    for slug, guide in switch_guides.GUIDES.items():
        entries.append(_entry(f"Switch from {guide['name']}", switch_guides.path(slug), "Switch trackers",
                              guide.get("description", ""), [guide.get("h1"), "import"]))
    for slug, guide in DISCOVER.items():
        name = TRAILS[slug]["name"] if slug in TRAILS else guide.get("search_title", slug).split(":")[0]
        entries.append(_entry(name, f"/discover/{slug}", "Discover", guide.get("summary", ""), [guide.get("search_title")]))
    return entries


def _page_sources() -> list[dict]:
    from .page_breadcrumbs import HUBS
    from .site_chrome import NAV_MENUS

    entries, seen = [], set()
    for _, _, items in NAV_MENUS:
        for _, label, href, blurb in items:
            if href not in seen:
                seen.add(href)
                entries.append(_entry(label, href, "Page", blurb, [HUBS.get(href)]))
    for href, name in HUBS.items():
        live = HUB_GATES.get(href)
        if href not in seen and href not in UNLISTED_HUBS and (live is None or live()):
            seen.add(href)
            entries.append(_entry(name, href, "Page"))
    entries.append(_entry("Binge calculator", "/binge-calculator", "Page",
                          "How long a show, anime, film series or book series takes to finish", ["how long"]))
    return entries


# Hubs from page_breadcrumbs that are seasonal or not pages a visitor would look for.
UNLISTED_HUBS = {"/halloween", "/new-this-week/archive"}


def _advent_is_open() -> bool:
    from . import advent_calendar
    return advent_calendar.current_year() is not None


# Hubs that only exist part of the year: listed once they open (the index is rebuilt daily).
HUB_GATES = {"/holidays/advent-calendar": _advent_is_open}

_guides_cache: dict = {"day": None, "entries": []}
_guides_lock = threading.Lock()


def guide_entries(today: Optional[date] = None) -> list[dict]:
    """Every guide and hub page, rebuilt once a day (release guides go live on their date)."""
    today = today or date.today()
    with _guides_lock:
        if _guides_cache["day"] == today:
            return _guides_cache["entries"]
    entries = _guide_sources(today) + _page_sources()
    with _guides_lock:
        _guides_cache["day"], _guides_cache["entries"] = today, entries
    return entries


def _guide_rank(entry: dict, query: str, tokens: list[str]) -> Optional[int]:
    primary, secondary = entry["primary"], entry["secondary"]
    in_primary = [any(word.startswith(token) for word in primary) for token in tokens]
    if all(in_primary):
        return 0 if entry["base"].startswith(query) else 1
    if all(hit or any(word.startswith(token) for word in secondary) for hit, token in zip(in_primary, tokens)):
        # A guide that only mentions the title among its picks comes after one about it.
        return 2 if any(in_primary) else 3
    return None


def search_guides(text: str, limit: int = GUIDE_LIMIT, entries: Optional[list[dict]] = None) -> list[dict]:
    query, tokens = _query(text)
    if not tokens:
        return []
    scored = []
    for entry in guide_entries() if entries is None else entries:
        rank = _guide_rank(entry, query, tokens)
        if rank is not None:
            scored.append((rank, entry["section"] == "Page", len(entry["title"]), entry["title"].casefold(), entry))
    scored.sort(key=lambda row: row[:4])
    return [{"title": e["title"], "url": e["url"], "section": e["section"], "detail": e["detail"]}
            for *_, e in scored[:limit]]


# ---------------------------------------------------------------- people and studios

_people_cache: dict = {"at": 0.0, "entries": None, "building": False}
_people_lock = threading.Lock()


def _build_people(db: Session) -> list[dict]:
    from . import people_pages

    entries, seen = [], set()
    for entity, noun in ((people_pages.PERSON, "Person"), (people_pages.STUDIO, "Studio")):
        for role, rows in people_pages.directory_with_pages(db, entity, per_role=40).items():
            for row in rows:
                if row["url"] in seen:
                    continue
                seen.add(row["url"])
                entries.append({"name": row["name"], "url": row["url"], "role": role, "kind": noun,
                                "titles": row["titles"], "words": set(_words(row["name"]))})
    return entries


def _refresh_people() -> None:
    from .database import SessionLocal

    db = SessionLocal()
    try:
        entries = _build_people(db)
    except Exception:
        db.rollback()
        entries = None
    finally:
        db.close()
    with _people_lock:
        if entries is not None:
            _people_cache["entries"] = entries
        _people_cache["at"] = time.monotonic()
        _people_cache["building"] = False


def people_entries(db: Session) -> list[dict]:
    """People and studio pages. Built in the background; empty until the first build finishes.

    Building checks that each name has a real page, which takes a few seconds on a
    big library, so no search waits for it. Tests build it in the request instead.
    """
    if os.getenv("TESTING", "").lower() == "true":
        try:
            return _build_people(db)
        except Exception:
            db.rollback()
            return []
    with _people_lock:
        entries = _people_cache["entries"]
        fresh = entries is not None and time.monotonic() - _people_cache["at"] < PEOPLE_CACHE_SECONDS
        if fresh or _people_cache["building"]:
            return entries or []
        _people_cache["building"] = True
    threading.Thread(target=_refresh_people, name="site-search-people", daemon=True).start()
    return entries or []


def search_people(db: Session, text: str, limit: int = PEOPLE_LIMIT, entries: Optional[list[dict]] = None) -> list[dict]:
    query, tokens = _query(text)
    if not tokens or len(query) < 3:
        return []
    scored = []
    for entry in people_entries(db) if entries is None else entries:
        if all(any(word.startswith(token) for word in entry["words"]) for token in tokens):
            scored.append((-entry["titles"], entry["name"].casefold(), entry))
    scored.sort(key=lambda row: row[:2])
    return [{"name": e["name"], "url": e["url"], "role": e["role"], "kind": e["kind"], "titles": e["titles"]}
            for *_, e in scored[:limit]]


def clear_cache() -> None:
    with _guides_lock:
        _guides_cache["day"], _guides_cache["entries"] = None, []
    with _people_lock:
        _people_cache.update(at=0.0, entries=None, building=False)


# ---------------------------------------------------------------- titles

def title_result(entry: dict, image_width: int = 200) -> dict:
    return {"kind": entry["kind"], "label": entry["label"], "title": entry["title"], "year": entry["year"],
            "slug": entry["slug"], "url": f"/titles/{entry['kind']}/{entry['slug']}",
            "image": image_sizes.sized(entry["image"], image_width),
            # The same count the title page shows; one member is left out so it never points at a person.
            "members": entry["members"] if entry["members"] >= 2 else 0}


def popular(entries: list[dict], kind: Optional[str] = None, limit: int = POPULAR_LIMIT) -> list[dict]:
    """The most-tracked titles, taking turns between formats so one doesn't fill the list."""
    pool = [e for e in entries if e["members"] >= 2 and (kind is None or e["kind"] == kind)]
    pool.sort(key=lambda e: (-e["members"], e["image"] is None, e["title"].casefold()))
    if kind:
        return [title_result(e) for e in pool[:limit]]
    by_kind = {k: [e for e in pool if e["kind"] == k] for k in KIND_ORDER}
    picked = []
    depth = 0
    while len(picked) < limit and any(len(rows) > depth for rows in by_kind.values()):
        layer = [rows[depth] for rows in by_kind.values() if len(rows) > depth]
        layer.sort(key=lambda e: (-e["members"], e["title"].casefold()))
        picked.extend(layer)
        depth += 1
    return [title_result(e) for e in picked[:limit]]


def suggest(text: str, entries: list[dict], guides: list[dict]) -> Optional[str]:
    """A close spelling for a search that found nothing ("interstelar" -> "Interstellar")."""
    query, tokens = _query(text)
    if len(query) < 4:
        return None
    names: dict[str, str] = {}
    for entry in entries:
        names.setdefault(entry["base"], entry["title"])
    for entry in guides:
        if entry["section"] != "Page":
            names.setdefault(entry["base"], entry["title"])
    close = difflib.get_close_matches(query, list(names), n=1, cutoff=SUGGEST_CUTOFF)
    if close:
        return names[close[0]]
    # A long title typed in part: "witchr 3" against "the-witcher-3-wild-hunt".
    prefixes = {}
    for base, title in names.items():
        prefixes.setdefault(base[:len(query)], title)
    close = difflib.get_close_matches(query, list(prefixes), n=1, cutoff=SUGGEST_CUTOFF + 0.06)
    return prefixes[close[0]] if close else None


def search(db: Session, text: str, kind: Optional[str] = None, limit: int = title_search.RESULT_LIMIT) -> dict:
    """Everything for one search box value. An empty value returns popular titles instead."""
    kind = kind if kind in title_pages.KINDS else None
    entries = title_search.index(db)
    query, tokens = _query(text)
    result = {"query": " ".join((text or "").split())[:QUERY_MAX], "kind": kind,
              "titles": [], "guides": [], "people": [], "suggestion": None, "more": False}
    if not tokens:
        result["popular"] = popular(entries, kind)
        return result
    matches = title_search.ranked(entries, text, kind=kind)
    result["titles"] = [title_result(e) for e in matches[:limit]]
    result["more"] = len(matches) > limit
    result["total"] = len(matches)
    if kind is None:
        result["guides"] = search_guides(text)
        result["people"] = search_people(db, text)
    if not (result["titles"] or result["guides"] or result["people"]):
        suggestion = suggest(text, entries if kind is None else [e for e in entries if e["kind"] == kind],
                             guide_entries() if kind is None else [])
        if suggestion and title_pages.slugify(suggestion) != query:
            result["suggestion"] = suggestion
    return result
