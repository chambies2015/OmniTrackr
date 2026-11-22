"""Homepage "Start your list": popular titles a visitor can save before signing up.

The saved list lives only in the visitor's browser (guest-list.js). When they
create an account and log in, it is moved into their library through
POST /api/guest-list/import. Nothing is stored on the server for guests.
"""
from __future__ import annotations

import re
import threading
import time
from html import escape

from . import title_pages

PICKS_LIMIT = 12
CACHE_SECONDS = 600
KIND_ORDER = ("movie", "tv", "anime", "game", "book", "album")
_cache = {"at": 0.0, "html": "", "quick": "", "stage": ""}
_lock = threading.Lock()

# "Start your list" shows the mixed picks first; format chips then show up to SHELF_PER_KIND
# of one kind. A kind gets a chip once it has CHIP_MIN titles members track.
SECTION_SHOWN = 10
SHELF_PER_KIND = 10
CHIP_MIN = 5
KIND_CHIPS = {"movie": "Movies", "tv": "TV shows", "anime": "Anime", "game": "Games", "book": "Books", "album": "Albums"}


def _per_kind(db, limit: int) -> dict:
    per_kind = {kind: [item for item in title_pages.popular(db, kind, limit=limit, min_members=2)] for kind in KIND_ORDER}
    for items in per_kind.values():
        items.sort(key=lambda item: (not item.get("image"), -item["members"]))
    return per_kind


def mix(per_kind: dict, limit: int = PICKS_LIMIT) -> list[dict]:
    """Take one title per kind in turn, most tracked first, so every kind shows."""
    queues = {kind: list(items) for kind, items in per_kind.items()}
    chosen = []
    while len(chosen) < limit and any(queues.values()):
        for kind in KIND_ORDER:
            if queues.get(kind) and len(chosen) < limit:
                chosen.append(queues[kind].pop(0))
    return chosen


def picks(db, limit: int = PICKS_LIMIT) -> list[dict]:
    """Most-tracked titles across kinds (2+ members, private shelves excluded), mixed so every kind shows."""
    return mix(_per_kind(db, 8), limit)


def _tile(item: dict, top: bool) -> str:
    slug = item["url"].rsplit("/", 1)[1]
    art = (f'<img src="{escape(item["image"], quote=True)}" alt="" width="200" height="300" loading="lazy" decoding="async" referrerpolicy="no-referrer">'
           if item.get("image") else f'<span class="lp-pick__initial" aria-hidden="true">{escape(item["title"][:1].upper())}</span>')
    year = f' · {item["year"]}' if item.get("year") else ""
    # Tiles outside the mixed set wait for their format chip (home-shelf.js shows them).
    flags = (' data-picks-top' if top else '') + ('' if top else ' hidden')
    return (
        f'<li data-picks-kind="{escape(item["kind"], quote=True)}"{flags}><button type="button" class="lp-pick" aria-pressed="false" '
        f'data-guest-kind="{escape(item["kind"], quote=True)}" data-guest-slug="{escape(slug, quote=True)}" '
        f'data-guest-title="{escape(item["title"], quote=True)}">'
        f'<span class="lp-pick__art">{art}<span class="lp-pick__check" aria-hidden="true">✓</span></span>'
        f'<span class="lp-pick__title">{escape(item["title"])}</span>'
        f'<span class="lp-pick__meta">{escape(item["label"])}{escape(year)}</span></button></li>'
    )


SHELF_SLOTS = 8


def shelf_html() -> str:
    """The "Your library" panel beside the picks. home-shelf.js fills it from the visitor's saved list;
    <!--SHELF_SIGNUP--> becomes the sign-up buttons (main.shelf_signup_html)."""
    slots = '<li class="lp-shelf__slot" aria-hidden="true"></li>' * SHELF_SLOTS
    return (
        '<aside class="lp-shelf is-empty" id="your-library" data-guest-shelf aria-labelledby="lp-shelf-title">'
        '<div class="lp-shelf__head"><h3 id="lp-shelf-title">Your library</h3>'
        '<p class="lp-shelf__count" data-shelf-count>Nothing on it yet</p></div>'
        f'<ol class="lp-shelf__slots" data-shelf-slots aria-label="Titles on your list">{slots}</ol>'
        '<p class="lp-shelf__empty" data-shelf-empty>Tap a cover to put it here. Your list stays in this browser until you make a free account.</p>'
        '<div class="lp-shelf__also" data-shelf-also hidden><p class="lp-shelf__label" data-shelf-because></p>'
        '<ul class="lp-shelf__also-list" data-shelf-also-list></ul></div>'
        '<div class="lp-shelf__keep" data-shelf-keep hidden><p class="lp-shelf__keep-title">Keep it, free</p>'
        '<ul class="lp-shelf__perks" data-shelf-perks></ul>'
        '<div class="lp-shelf__actions"><!--SHELF_SIGNUP--></div>'
        '<p class="lp-shelf__note">No card needed. Your titles move into your account when you sign up.</p></div>'
        '</aside>'
    )


def section_html(items: list[dict], shelves: dict | None = None) -> str:
    """The "Start your list" section: mixed picks, a chip per well-tracked format, and the library panel.

    ``items`` is the mixed set shown first; ``shelves`` maps a kind to more of its titles for its chip.
    """
    if len(items) < 6:
        return ""
    top = items[:SECTION_SHOWN]
    seen = {(item["kind"], item["url"]) for item in top}
    tiles = [_tile(item, True) for item in top]
    chips = []
    for kind in KIND_ORDER:
        mine = [item for item in (shelves or {}).get(kind, [])][:SHELF_PER_KIND]
        if len(mine) < CHIP_MIN:
            continue
        chips.append(f'<button type="button" class="lp-chip" aria-pressed="false" data-picks-filter="{kind}">{KIND_CHIPS[kind]}</button>')
        for item in mine:
            if (item["kind"], item["url"]) not in seen:
                seen.add((item["kind"], item["url"]))
                tiles.append(_tile(item, False))
    chip_row = ('<div class="lp-picks__chips" role="group" aria-label="Show picks">'
                '<button type="button" class="lp-chip" aria-pressed="true" data-picks-filter="top">Most tracked</button>'
                f'{"".join(chips)}</div>') if chips else ""
    return (
        '<section class="lp-section lp-picks" id="start-your-list" aria-labelledby="lp-picks-title"><div class="lp-wrap">'
        '<div class="lp-section-head lp-section-head--row"><div><p class="lp-eyebrow">Try it now · no account needed</p>'
        '<h2 id="lp-picks-title">Start your library before you sign up</h2>'
        '<p class="lp-picks__lead">Tap anything you’ve seen, played or read, or want to. It goes on your shelf straight away.</p></div></div>'
        '<div class="lp-picks__layout"><div class="lp-picks__main">'
        f'{chip_row}<ul class="lp-picks__grid">{"".join(tiles)}</ul>'
        '<p class="lp-picks__more">Not here? <a class="lp-linkbtn" href="#hero-title" data-picks-search>Search for any title</a></p>'
        f'</div>{shelf_html()}</div>'
        '</div></section>'  # The page's save bar (public_landing.html) offers sign-up once something is saved.
    )


# The library panel's "Members who track X also track" row (GET /api/guest-list/suggest).
SUGGEST_LIMIT = 8
SUGGEST_SLUG = re.compile(r"^[a-z0-9-]{1,130}$")


def suggestions(db, kind: str, slug: str, limit: int = SUGGEST_LIMIT) -> list[dict]:
    """Titles most often tracked by the members who track this one: the title page's "Members also
    track" list, shared with its cache. Only shareable shelves count, and only titles two or more of
    those members track, so a single library is never shown."""
    if kind not in title_pages.KINDS or not SUGGEST_SLUG.match(slug or ""):
        return []
    group = title_pages.find(db, kind, slug)
    if group is None:
        return []
    related = title_pages._cached_section(("related", group.path), lambda: title_pages._related(db, kind, group))
    results = []
    for item in related:
        other = (item.get("url") or "").rsplit("/", 1)[-1]
        if item.get("kind") not in title_pages.KINDS or not SUGGEST_SLUG.match(other):
            continue
        results.append({"kind": item["kind"], "slug": other, "title": item["title"], "label": item["label"],
                        "year": item.get("year"), "image": item.get("image")})
        if len(results) >= limit:
            break
    return results


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
    section = quick = stage = ""
    try:
        if session_factory is None:
            from .database import SessionLocal as session_factory
        db = session_factory()
        try:
            per_kind = _per_kind(db, SHELF_PER_KIND)
            items = mix({kind: entries[:8] for kind, entries in per_kind.items()})
            section, quick = section_html(items, per_kind), quick_picks_html(items)
            try:
                stage = stage_html(stage_items(db))
            except Exception:
                stage = ""  # The hero falls back to the vortex.
        finally:
            db.close()
    except Exception:
        section = quick = stage = ""
    with _lock:
        _cache["at"], _cache["html"], _cache["quick"], _cache["stage"] = now, section, quick, stage
        return dict(_cache)


def homepage_section(session_factory=None) -> str:
    """Cached HTML for the homepage's "Start your list" section."""
    return _cached(session_factory)["html"]


def hero_quick_picks(session_factory=None) -> str:
    """Cached HTML for the popular titles under the hero search."""
    return _cached(session_factory)["quick"]


def hero_stage(session_factory=None) -> str:
    """Cached HTML for the poster wall beside the hero copy ("" until there are enough covers)."""
    return _cached(session_factory)["stage"]


def clear_cache() -> None:
    with _lock:
        _cache["at"], _cache["html"], _cache["quick"], _cache["stage"] = 0.0, "", "", ""


# The hero's poster wall: three columns of covers members track, drifting slowly
# (public-landing.css). Real covers tell a visitor what the site is for faster than
# the abstract vortex did; the vortex stays as the fallback for a thin database.
STAGE_COLUMNS = 3
STAGE_PER_COLUMN = 5
STAGE_MIN = 9
STAGE_KINDS = ("movie", "anime", "game", "tv", "book", "album", "manga")


def stage_items(db, limit: int = STAGE_COLUMNS * STAGE_PER_COLUMN) -> list[dict]:
    """Popular titles that have cover art, mixed across kinds so no column is all one format."""
    per_kind = {kind: [item for item in title_pages.popular(db, kind, limit=10, min_members=2) if item.get("image")]
                for kind in STAGE_KINDS}
    chosen = []
    while len(chosen) < limit and any(per_kind.values()):
        for kind in STAGE_KINDS:
            if per_kind[kind] and len(chosen) < limit:
                chosen.append(per_kind[kind].pop(0))
    return chosen


def _stage_poster(item: dict) -> str:
    return (f'<li class="lp-stage__poster"><img src="{escape(item["image"], quote=True)}" alt="" width="200" height="300" '
            f'decoding="async" fetchpriority="low" referrerpolicy="no-referrer">'
            f'<span class="lp-stage__kind">{escape(item["label"])}</span></li>')


def _stage_loop(items: list[dict], css_class: str) -> str:
    # Listed twice so the drift can loop without a jump; the copies reuse the same image requests.
    posters = "".join(_stage_poster(item) for item in items)
    return f'<ul class="{css_class}">{posters}{posters}</ul>'


def stage_html(items: list[dict]) -> str:
    if len(items) < STAGE_MIN:
        return ""
    # Desktop: three vertical columns. Phones and tablets: two rows that each carry every cover,
    # so a row is always wider than the screen it drifts across.
    cols = "".join(_stage_loop(items[start::STAGE_COLUMNS], "lp-stage__col") for start in range(STAGE_COLUMNS))
    middle = len(items) // 2
    rows = _stage_loop(items, "lp-stage__row") + _stage_loop(items[middle:] + items[:middle], "lp-stage__row")
    saved = items[0]
    return (
        '<div class="lp-hero__visual lp-stage" aria-hidden="true">'
        f'<div class="lp-stage__wall">{cols}</div><div class="lp-stage__rows">{rows}</div>'
        '<div class="lp-stage__card lp-stage__card--saved"><span class="lp-stage__badge is-teal">✓</span>'
        f'<span><small>Saved to your list</small><strong>{escape(saved["title"])}</strong></span></div>'
        '<div class="lp-stage__card lp-stage__card--rating"><span class="lp-stage__badge is-amber">★</span>'
        '<span><small>Your rating</small><strong>9.2 / 10</strong></span></div>'
        '<div class="lp-stage__card lp-stage__card--streak"><span class="lp-stage__badge is-violet">7</span>'
        '<span><small>This week</small><strong>Finished, rated, logged</strong></span></div>'
        '</div>'
    )
