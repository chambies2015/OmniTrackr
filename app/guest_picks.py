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
_cache = {"at": 0.0, "html": "", "quick": ""}
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
        '</div></section>'  # The page's save bar (public_landing.html) offers sign-up once something is saved.
    )


QUICK_PICKS = 4


def quick_picks_html(items: list[dict]) -> str:
    """A row of popular titles under the hero search: one tap saves one (guest-list.js)."""
    if len(items) < QUICK_PICKS:
        return ""
    buttons = []
    for item in items[:QUICK_PICKS]:
        slug = item["url"].rsplit("/", 1)[1]
        buttons.append(
            f'<li><button type="button" class="lp-quick__pick" aria-pressed="false" data-guest-kind="{escape(item["kind"], quote=True)}" '
            f'data-guest-slug="{escape(slug, quote=True)}" data-guest-title="{escape(item["title"], quote=True)}" '
            f'aria-label="Save {escape(item["title"], quote=True)} ({escape(item["label"], quote=True)})">'
            f'<span class="lp-quick__title">{escape(item["title"])}</span></button></li>'
        )
    return f'<div class="lp-quick"><p class="lp-quick__label">Or tap one</p><ul class="lp-quick__list">{"".join(buttons)}</ul></div>'



def _cached(session_factory=None) -> dict:
    """Both homepage blocks, rebuilt every 10 minutes from one query; never raises."""
    now = time.monotonic()
    with _lock:
        if _cache["at"] and now - _cache["at"] < CACHE_SECONDS:
            return _cache
    section = quick = ""
    try:
        if session_factory is None:
            from .database import SessionLocal as session_factory
        db = session_factory()
        try:
            items = picks(db)
            section, quick = section_html(items), quick_picks_html(items)
        finally:
            db.close()
    except Exception:
        section = quick = ""
    with _lock:
        _cache["at"], _cache["html"], _cache["quick"] = now, section, quick
        return dict(_cache)


def homepage_section(session_factory=None) -> str:
    """Cached HTML for the homepage's "Start your list" section."""
    return _cached(session_factory)["html"]


def hero_quick_picks(session_factory=None) -> str:
    """Cached HTML for the popular titles under the hero search."""
    return _cached(session_factory)["quick"]


def clear_cache() -> None:
    with _lock:
        _cache["at"], _cache["html"], _cache["quick"] = 0.0, "", ""
