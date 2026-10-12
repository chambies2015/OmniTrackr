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

from . import title_pages

CACHE_SECONDS = 600
ROWS_PER_KIND = 50000
RESULT_LIMIT = 8
QUERY_MAX = 80
_cache: dict = {"at": 0.0, "entries": None}
_lock = threading.Lock()


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
        if _cache["entries"] is not None and now - _cache["at"] < CACHE_SECONDS:
            return _cache["entries"]
    try:
        entries = build_index(db)
    except Exception:
        entries = []  # The homepage search never breaks the page; retry after the cache window.
    with _lock:
        _cache["at"], _cache["entries"] = now, entries
    return entries


def clear_cache() -> None:
    with _lock:
        _cache["at"], _cache["entries"] = 0.0, None


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


def search(entries: list[dict], text: str, limit: int = RESULT_LIMIT) -> list[dict]:
    query = title_pages.slugify((text or "")[:QUERY_MAX])
    if query == "title" and "title" not in (text or "").lower():
        return []  # slugify() returns "title" for input with no letters or digits.
    if len(query.replace("-", "")) < 2:
        return []
    tokens = [token for token in query.split("-") if token]
    scored = []
    for entry in entries:
        rank = _rank(entry, query, tokens)
        if rank is not None:
            scored.append((rank, -entry["members"], len(entry["title"]), entry["title"].casefold(), entry))
    scored.sort(key=lambda row: row[:4])
    return [
        {"kind": e["kind"], "label": e["label"], "title": e["title"], "year": e["year"], "slug": e["slug"],
         "url": f"/titles/{e['kind']}/{e['slug']}", "image": e["image"]}
        for *_, e in scored[:limit]
    ]
