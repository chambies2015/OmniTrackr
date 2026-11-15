"""Homepage hero search: find a title members track and save it before signing up.

Searches only titles already in members' shareable libraries (the same titles
that have a public /titles page), so every result can go on a guest's list and
later move into their new library through POST /api/guest-list/import. Nothing
about who tracks a title is returned, and no external API is called.

The index is a small in-memory list rebuilt at most every 10 minutes.
"""
from __future__ import annotations

import threading
import time
from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from . import image_sizes, title_pages

CACHE_SECONDS = 600
FAILURE_RETRY_SECONDS = 60
ROWS_PER_KIND = 50000
RESULT_LIMIT = 8
QUERY_MAX = 80
# Indexes this big get a two-letter lookup so a search only ranks titles that can match.
PREFIX_MIN_ENTRIES = 2000
_cache: dict = {"at": 0.0, "entries": None}
_lock = threading.Lock()
_build_lock = threading.Lock()  # one rebuild at a time; other requests keep using the old index


def build_index(db: Session) -> list[dict]:
    """One entry per title page: kind, display title, year, slug, image and member count."""
    editors = {uid for uid, in title_pages._editor_ids(db).all()}
    entries = []
    for kind, (model, _, _, label, _) in title_pages.KINDS.items():
        image_field = getattr(model, title_pages.IMAGE_FIELD[kind])
        year_field = model.release_date if kind == "game" else model.year
        rows = (db.query(model.title, year_field, image_field, model.user_id)
                .filter(model.user_id.in_(title_pages._shareable_ids(db, kind)))
                .limit(ROWS_PER_KIND).all())
        groups: dict = defaultdict(lambda: {"names": Counter(), "images": Counter(), "members": set()})
        for title, year_value, image, user_id in rows:
            title = (title or "").strip()
            base = title_pages.slugify(title)
            if not title or base == "title":
                continue
            year = year_value.year if kind == "game" and year_value else (year_value or None)
            group = groups[(base, year)]
            group["names"][title] += 1
            safe = title_pages._safe_image(image)
            if safe:
                group["images"][safe] += 1
            if user_id not in editors:
                group["members"].add(user_id)
        for (base, year), group in groups.items():
            display = group["names"].most_common(1)[0][0]
            entries.append({
                "kind": kind, "label": label, "title": display, "year": year,
                "slug": f"{base}-{year}" if year else base,
                "image": group["images"].most_common(1)[0][0] if group["images"] else None,
                "members": len(group["members"]),
                "words": base.split("-"),
                "base": base,
            })
    return entries


def index(db: Session) -> list[dict]:
    """The cached index; an empty list if the database can't be read."""
    now = time.monotonic()
    with _lock:
        stale = _cache["entries"]
        if stale is not None and now - _cache["at"] < CACHE_SECONDS:
            return stale
    # Several pages read the index at once when it expires; only one of them rebuilds it.
    if not _build_lock.acquire(blocking=stale is None):
        return stale
    try:
        with _lock:
            if _cache["entries"] is not None and time.monotonic() - _cache["at"] < CACHE_SECONDS:
                return _cache["entries"]
        try:
            entries = build_index(db)
        except Exception:
            # The homepage search never breaks the page. Leave the session usable for the rest
            # of the request, keep the last good index, and try again in a minute.
            db.rollback()
            entries = stale if stale is not None else []
            with _lock:
                _cache["at"], _cache["entries"] = time.monotonic() - CACHE_SECONDS + FAILURE_RETRY_SECONDS, entries
            return entries
        if len(entries) >= PREFIX_MIN_ENTRIES:
            _prefix_positions(entries)  # ready before any search sees the new index
        with _lock:
            _cache["at"], _cache["entries"] = time.monotonic(), entries
        return entries
    finally:
        _build_lock.release()


def clear_cache() -> None:
    with _lock:
        _cache["at"], _cache["entries"] = 0.0, None
    with _prefix_lock:
        _prefix_cache.update(entries=None, size=0, positions=None)


_prefix_cache: dict = {"entries": None, "size": 0, "positions": None}
_prefix_lock = threading.Lock()


def _prefix_positions(entries: list[dict]) -> dict[str, list[int]]:
    """{first two letters of a title word: positions in `entries`}, worked out once per index."""
    with _prefix_lock:
        if _prefix_cache["entries"] is entries and _prefix_cache["size"] == len(entries):
            return _prefix_cache["positions"]
    positions: dict[str, list[int]] = {}
    for position, entry in enumerate(entries):
        for prefix in {word[:2] for word in entry["words"] if len(word) >= 2}:
            positions.setdefault(prefix, []).append(position)
    with _prefix_lock:
        _prefix_cache.update(entries=entries, size=len(entries), positions=positions)
    return positions


def _candidates(entries: list[dict], tokens: list[str]) -> list[dict]:
    """The entries that can match: every query word must start a title word, so a title without a
    word starting with the rarest query word's first two letters is skipped. Index order is kept."""
    keys = [token[:2] for token in tokens if len(token) >= 2]
    if len(entries) < PREFIX_MIN_ENTRIES or not keys:
        return entries
    positions = _prefix_positions(entries)
    narrowest = min((positions.get(key, ()) for key in keys), key=len)
    return [entries[position] for position in narrowest]


def _rank(entry: dict, query: str, tokens: list[str]) -> int | None:
    """Lower is better; None means no match. Every query word must start a title word."""
    words = entry["words"]
    if not all(any(word.startswith(token) for word in words) for token in tokens):
        return None
    if entry["base"] == query:
        return 0
    if entry["base"].startswith(query):
        return 1
    if words[0].startswith(tokens[0]):
        return 2
    return 3


def ranked(entries: list[dict], text: str, kind: str | None = None) -> list[dict]:
    """Every index entry matching the search, best first; `kind` keeps one format."""
    query = title_pages.slugify((text or "")[:QUERY_MAX])
    if query == "title" and "title" not in (text or "").lower():
        return []  # slugify() returns "title" for input with no letters or digits.
    if len(query.replace("-", "")) < 2:
        return []
    tokens = [token for token in query.split("-") if token]
    scored = []
    for entry in _candidates(entries, tokens):
        if kind is not None and entry["kind"] != kind:
            continue
        rank = _rank(entry, query, tokens)
        if rank is not None:
            scored.append((rank, -entry["members"], len(entry["title"]), entry["title"].casefold(), entry))
    scored.sort(key=lambda row: row[:4])
    return [row[-1] for row in scored]


def search(entries: list[dict], text: str, limit: int = RESULT_LIMIT) -> list[dict]:
    return [
        {"kind": e["kind"], "label": e["label"], "title": e["title"], "year": e["year"], "slug": e["slug"],
         "url": f"/titles/{e['kind']}/{e['slug']}", "image": image_sizes.sized(e["image"], 200)}
        for e in ranked(entries, text)[:limit]
    ]
