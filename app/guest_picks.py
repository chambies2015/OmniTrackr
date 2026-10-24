"""Homepage "Start your list": popular titles a visitor can save before signing up.

The saved list lives only in the visitor's browser (guest-list.js). When they
create an account and log in, it is moved into their library through
POST /api/guest-list/import. Nothing is stored on the server for guests.
"""
from __future__ import annotations

import threading
import time
from html import escape

from . import title_pages

PICKS_LIMIT = 12
CACHE_SECONDS = 600
KIND_ORDER = ("movie", "tv", "anime", "game", "book", "album")
_cache = {"at": 0.0, "html": ""}
_lock = threading.Lock()


def picks(db, limit: int = PICKS_LIMIT) -> list[dict]:
    """Most-tracked titles across kinds (2+ members, private shelves excluded), mixed so every kind shows."""
    per_kind = {kind: [item for item in title_pages.popular(db, kind, limit=8, min_members=2)] for kind in KIND_ORDER}
    for items in per_kind.values():
        items.sort(key=lambda item: (not item.get("image"), -item["members"]))
    chosen = []
    while len(chosen) < limit and any(per_kind.values()):
        for kind in KIND_ORDER:
            if per_kind[kind] and len(chosen) < limit:
                chosen.append(per_kind[kind].pop(0))
    return chosen


def section_html(items: list[dict]) -> str:
    if len(items) < 6:
        return ""
    tiles = []
    for item in items:
        slug = item["url"].rsplit("/", 1)[1]
        art = (f'<img src="{escape(item["image"], quote=True)}" alt="" width="200" height="300" loading="lazy" decoding="async" referrerpolicy="no-referrer">'
               if item.get("image") else f'<span class="lp-pick__initial" aria-hidden="true">{escape(item["title"][:1].upper())}</span>')
        year = f' · {item["year"]}' if item.get("year") else ""
        tiles.append(
            f'<li><button type="button" class="lp-pick" aria-pressed="false" data-guest-kind="{escape(item["kind"], quote=True)}" '
            f'data-guest-slug="{escape(slug, quote=True)}" data-guest-title="{escape(item["title"], quote=True)}">'
            f'<span class="lp-pick__art">{art}<span class="lp-pick__check" aria-hidden="true">✓</span></span>'
            f'<span class="lp-pick__title">{escape(item["title"])}</span>'
            f'<span class="lp-pick__meta">{escape(item["label"])}{escape(year)}</span></button></li>'
        )
    return (
        '<section class="lp-section lp-picks" id="start-your-list" aria-labelledby="lp-picks-title"><div class="lp-wrap">'
        '<div class="lp-section-head lp-section-head--row"><div><p class="lp-eyebrow">Try it now · no account needed</p>'
        '<h2 id="lp-picks-title">Start your list in ten seconds</h2>'
        '<p class="lp-picks__lead">Tap anything you’ve seen, played or read, or want to. Popular with OmniTrackr members.</p></div></div>'
        f'<ul class="lp-picks__grid">{"".join(tiles)}</ul>'
        '<div class="lp-picks__bar" data-guest-bar hidden><p class="lp-picks__count" data-guest-count role="status" aria-live="polite"></p>'
        '<button type="button" class="lp-btn lp-btn--primary" data-action="show-register-form">Save my list, free '
        '<svg class="lp-icon" aria-hidden="true"><use href="#i-arrow"/></svg></button></div>'
        '</div></section>'
    )


def homepage_section(session_factory=None) -> str:
    """Cached HTML for the homepage (refreshed every 10 minutes; never raises)."""
    now = time.monotonic()
    with _lock:
        if _cache["html"] is not None and now - _cache["at"] < CACHE_SECONDS and _cache["at"]:
            return _cache["html"]
    html = ""
    try:
        if session_factory is None:
            from .database import SessionLocal as session_factory
        db = session_factory()
        try:
            html = section_html(picks(db))
        finally:
            db.close()
    except Exception:
        html = ""
    with _lock:
        _cache["at"], _cache["html"] = now, html
    return html


def clear_cache() -> None:
    with _lock:
        _cache["at"], _cache["html"] = 0.0, ""
