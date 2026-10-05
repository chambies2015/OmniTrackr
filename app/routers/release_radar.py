"""Public Release Radar pages and the authenticated "track this" endpoints."""
from __future__ import annotations

import asyncio
import json
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import affiliate, models
from .. import release_radar as radar
from ..csp import strict_html_response
from ..site_chrome import apply_site_chrome
from ..dependencies import get_current_user, get_db

router = APIRouter()

CATEGORY_MODELS = {
    "movies": models.Movie,
    "tv": models.TVShow,
    "anime": models.Anime,
    "games": models.VideoGame,
}
# The collections feature stores categories with these keys.
COLLECTION_CATEGORY = {"movies": "movies", "tv": "tv-shows", "anime": "anime", "games": "video-games"}
COLLECTION_NAME = "Release Radar"
COLLECTION_DESCRIPTION = "Titles saved from OmniTrackr's Release Radar. Mark them finished, rate them, or remove them any time."
SUMMARY_LABELS = {"movies": "movies", "tv": "TV premieres", "anime": "anime", "games": "video games"}
MIN_INDEXABLE_ITEMS = radar.MIN_INDEXABLE_ITEMS
AD_ELIGIBLE_MIN_ITEMS = 12
PAGE_INTROS = {
    "movies": "Films with a release date this month, drawn from Wikidata and ranked by how widely each one is documented. US dates are preferred; festival premieres elsewhere are left out.",
    "tv": "Series premieres and new seasons starting this month on US broadcast channels and on streaming services worldwide, from TVmaze's schedule.",
    "anime": "Everything premiering this broadcast season, from AniList, with what is new and what continues a story you may already follow.",
    "games": "Games with a firm release date this month, ordered by how many RAWG players are already following them.",
}
SEO_TITLES = {
    "movies": "New movie releases in {label}",
    "tv": "TV premieres and new seasons in {label}",
    "anime": "{label} anime season: every new show",
    "games": "Video game releases in {label}",
}


def _client(request: Request):
    return request.app.state.external_api_client


def _today() -> date:
    return radar.today_utc()


def _format_day(iso: str) -> str:
    day = date.fromisoformat(iso)
    return f"{day.strftime('%a')}, {day.strftime('%b')} {day.day}"


def _category_path(category: str, window: Optional[radar.Window] = None) -> str:
    if window is None or window == radar.featured_window(category, _today()):
        return f"/release-radar/{category}"
    return f"/release-radar/{category}/{window.slug}"


def _render(title: str, description: str, canonical: str, content: str, *, indexable: bool,
            structured: Optional[dict] = None, ads: bool = False, refresh: bool = False) -> Response:
    html = apply_site_chrome((Path(__file__).parents[1] / "templates" / "release_radar.html").read_text(encoding="utf-8"))
    extra_head = '<meta name="google-adsense-account" content="ca-pub-7271682066779719">'
    if refresh:
        extra_head += '<meta http-equiv="refresh" content="45">'
    structured_html = ""
    if structured:
        payload = json.dumps(structured, ensure_ascii=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
        structured_html = f'<script type="application/ld+json">{payload}</script>'
    replacements = {
        "TITLE": escape(title),
        "DESCRIPTION": escape(description, quote=True),
        "ROBOTS": "index, follow, max-image-preview:large" if indexable else "noindex, follow",
        "CANONICAL": escape(canonical, quote=True),
        "EXTRA_HEAD": extra_head,
        "AD_LOADER": '<script src="/static/ad-loader.js" defer></script>' if ads and indexable else "",
        "STRUCTURED_DATA": structured_html,
        "CONTENT": content,
    }
    for key, value in replacements.items():
        html = html.replace("{{" + key + "}}", value)
    response = strict_html_response(html)
    if not indexable:
        response.headers["X-Robots-Tag"] = "noindex, follow"
    response.headers["Cache-Control"] = "public, max-age=300" if not refresh else "no-cache"
    return response


# ---------------------------------------------------------------------------
# Community signal: how many OmniTrackr libraries already hold each title.
# Only an aggregate count is shown, never who saved it.
# ---------------------------------------------------------------------------

def library_counts(db: Session, category: str, items: list[dict]) -> dict[str, int]:
    model = CATEGORY_MODELS[category]
    titles = {(i["save"].get("title") or "").strip().lower() for i in items} - {""}
    if not titles:
        return {}
    normalized = func.lower(func.trim(model.title))
    active_users = db.query(models.User.id).filter(models.User.is_active == True)  # noqa: E712
    try:
        rows = (
            db.query(normalized, func.count(func.distinct(model.user_id)))
            .filter(normalized.in_(sorted(titles)), model.user_id.in_(active_users))
            .group_by(normalized)
            .all()
        )
    except Exception:
        db.rollback()
        return {}
    by_title = {title: count for title, count in rows}
    return {i["key"]: by_title[(i["save"].get("title") or "").strip().lower()]
            for i in items if (i["save"].get("title") or "").strip().lower() in by_title}


# ---------------------------------------------------------------------------
# HTML fragments
# ---------------------------------------------------------------------------

def _signin_href(path: str) -> str:
    return f"/?next={path}#landing-auth"


def render_card(item: dict, count: int, return_path: str, *, compact: bool = False) -> str:
    category = item["category"]
    key = escape(item["key"], quote=True)
    title = escape(item["title"])
    art = (
        f'<img src="{escape(item["image"], quote=True)}" alt="" width="200" height="300" loading="lazy" decoding="async" referrerpolicy="no-referrer">'
        if item.get("image") else f'<span class="radar-card__initial" aria-hidden="true">{escape(item["title"][:1].upper())}</span>'
    )
    when = (
        f'<time datetime="{item["date"]}">{_format_day(item["date"])}</time>' if item.get("date") else "Date to be announced"
    )
    note = f' · {escape(item["date_note"])}' if item.get("date_note") and item.get("date") else ""
    chips = "".join(f'<li class="radar-chip radar-chip--badge">{escape(b)}</li>' for b in item["badges"])
    chips += "".join(f'<li class="radar-chip">{escape(g)}</li>' for g in item["genres"][:4])
    platforms = f'<p class="radar-card__meta">{escape(" · ".join(item["platforms"][:5]))}</p>' if item["platforms"] else ""
    details = f'<p class="radar-card__meta">{escape(" · ".join(item["details"]))}</p>' if item["details"] else ""
    alt = f'<p class="radar-card__alt" lang="ja-Latn">{escape(item["alt_title"])}</p>' if item.get("alt_title") else ""
    community = (
        f'<p class="radar-card__community">In {count} OmniTrackr {"library" if count == 1 else "libraries"}</p>' if count else ""
    )
    source_name = radar.SOURCES[category][0]
    source = (
        f'<a class="radar-source" href="{escape(item["source_url"], quote=True)}" target="_blank" rel="noopener nofollow">{escape(source_name)} ↗</a>'
        if item.get("source_url") else ""
    )
    creator = (item["save"].get("director") or "") if category == "movies" else ""
    buy = affiliate.links_html(category, item["title"], creator)
    search = " ".join([item["title"], item.get("alt_title", ""), *item["genres"], *item["platforms"], *item["details"]])
    add = (
        f'<a class="radar-add" data-radar-add="{key}" href="{escape(_signin_href(return_path), quote=True)}">'
        f'<span aria-hidden="true">+</span> Track this<span class="visually-hidden"> {title}</span></a>'
    )
    return (
        f'<article class="radar-card{" radar-card--compact" if compact else ""}" id="item-{key}" data-key="{key}" '
        f'data-category="{category}" data-window="{escape(item.get("window", ""), quote=True)}" data-genres="{escape("|".join(item["genres"]), quote=True)}" '
        f'data-platforms="{escape("|".join(item["platforms"]), quote=True)}" data-search="{escape(search.lower(), quote=True)}">'
        f'<div class="radar-card__art">{art}</div><div class="radar-card__body">'
        f'<p class="radar-card__date">{when}{note}</p><h3 class="radar-card__title">{title}</h3>{alt}{details}{platforms}'
        f'<ul class="radar-chips" aria-label="Tags">{chips}</ul>{community}'
        f'<div class="radar-card__actions">{add}{source}{buy}</div></div></article>'
    )


def _status_message(entry: Optional[dict], category: str) -> str:
    label = radar.CATEGORY_LABELS[category].lower()
    if entry is None:
        return (f'<div class="radar-status" role="status"><strong>Gathering {escape(label)} right now.</strong> '
                'This page refreshes itself in under a minute, or reload whenever you like.</div>')
    if entry.get("error") == "unavailable":
        return f'<div class="radar-status" role="status">{escape(radar.CATEGORY_LABELS[category])} listings are not available right now.</div>'
    if entry.get("error") and not entry.get("items"):
        return (f'<div class="radar-status" role="status">We could not reach the {escape(radar.SOURCES[category][0])} schedule just now. '
                'Please try again in a few minutes.</div>')
    return ""


def _structured(title: str, canonical: str, items: list[dict]) -> dict:
    types = {"movies": "Movie", "tv": "TVSeries", "anime": "TVSeries", "games": "VideoGame"}
    elements = []
    for position, item in enumerate(items[:30], start=1):
        thing = {"@type": types[item["category"]], "name": item["title"],
                 "url": f"https://omnitrackr.xyz{canonical}#item-{item['key']}"}
        if item.get("date"):
            thing["datePublished" if item["category"] in ("movies", "games") else "startDate"] = item["date"]
        if item.get("image"):
            thing["image"] = item["image"]
        elements.append({"@type": "ListItem", "position": position, "item": thing})
    return {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "CollectionPage", "name": title, "url": f"https://omnitrackr.xyz{canonical}",
             "isPartOf": {"@type": "WebSite", "name": "OmniTrackr", "url": "https://omnitrackr.xyz/"}},
            {"@type": "ItemList", "name": title, "numberOfItems": len(items), "itemListElement": elements},
        ],
    }


def _category_tabs(active: Optional[str]) -> str:
    links = ['<a href="/release-radar"' + (' aria-current="page"' if active is None else "") + '>Overview</a>']
    for category in radar.CATEGORY_ORDER:
        current = ' aria-current="page"' if category == active else ""
        links.append(f'<a href="/release-radar/{category}"{current}>{escape(radar.CATEGORY_LABELS[category])}</a>')
    return f'<nav class="radar-tabs" aria-label="Release Radar sections">{"".join(links)}</nav>'


def _window_nav(category: str, window: radar.Window) -> str:
    windows = radar.allowed_windows(category, _today())
    index = windows.index(window)
    prev_link = (f'<a class="radar-window__prev" href="{_category_path(category, windows[index - 1])}" rel="prev">← {escape(windows[index - 1].label)}</a>'
                 if index > 0 else '<span></span>')
    next_link = (f'<a class="radar-window__next" href="{_category_path(category, windows[index + 1])}" rel="next">{escape(windows[index + 1].label)} →</a>'
                 if index + 1 < len(windows) else '<span></span>')
    options = "".join(
        f'<option value="{_category_path(category, w)}"{" selected" if w == window else ""}>{escape(w.label)}</option>' for w in windows
    )
    return (f'<div class="radar-window">{prev_link}<form class="radar-window__jump" method="get" action="/release-radar/jump">'
            f'<label class="visually-hidden" for="radar-window-select">Choose a period</label>'
            f'<select id="radar-window-select" name="to" data-radar-jump>{options}</select>'
            f'<noscript><button type="submit">Go</button></noscript></form>{next_link}</div>')


def _filters(category: str, items: list[dict]) -> str:
    genres = sorted({g for i in items for g in i["genres"]})
    platforms = sorted({p for i in items for p in i["platforms"]})
    genre_options = "".join(f'<option value="{escape(g, quote=True)}">{escape(g)}</option>' for g in genres)
    platform_select = ""
    if platforms:
        platform_options = "".join(f'<option value="{escape(p, quote=True)}">{escape(p)}</option>' for p in platforms)
        platform_select = (f'<div><label for="radar-platform">Platform</label><select id="radar-platform" data-radar-filter="platform">'
                           f'<option value="">Any platform</option>{platform_options}</select></div>')
    return (
        '<section class="trail-filters radar-filters" id="radar-filters" aria-label="Filter releases" hidden>'
        '<div class="trail-filter-fields">'
        '<div><label for="radar-search">Search this list</label><input id="radar-search" type="search" maxlength="80" '
        'placeholder="Title, studio, network, genre" data-radar-filter="search"></div>'
        f'<div><label for="radar-genre">Genre</label><select id="radar-genre" data-radar-filter="genre"><option value="">Any genre</option>{genre_options}</select></div>'
        f'{platform_select}'
        '<div class="radar-toggle" hidden data-radar-mine-wrap><label><input type="checkbox" data-radar-filter="hide-mine"> Hide titles already in my library</label></div>'
        '<button type="button" class="filter-reset" data-radar-reset>Clear</button></div>'
        f'<p class="muted" id="radar-results" role="status" aria-live="polite">{len(items)} titles</p></section>'
    )


def _group_by_week(items: list[dict]) -> list[tuple[str, list[dict]]]:
    groups: dict[str, list[dict]] = {}
    for item in items:
        if item.get("date"):
            monday = radar._week_of(item["date"])
            label = f"Week of {monday.strftime('%B')} {monday.day}"
        else:
            label = "Date to be announced"
        groups.setdefault(label, []).append(item)
    return list(groups.items())


def _about_section(category: Optional[str]) -> str:
    source_list = "".join(
        f'<li><strong>{escape(radar.CATEGORY_LABELS[c])}:</strong> <a href="{radar.SOURCES[c][1]}" rel="noopener">{radar.SOURCES[c][0]}</a></li>'
        for c in ((category,) if category else radar.CATEGORY_ORDER)
    )
    return (
        '<section class="editorial radar-about"><h2>How the radar works</h2>'
        '<p>Release Radar collects dates from public databases once every few hours and keeps the most useful slice: '
        'widely followed films, premieres rather than every weekly episode, the whole anime season, and games with a firm date. '
        'The notes above each list are calculated from that data, so they change as schedules change.</p>'
        '<p><strong>Tracking</strong> adds a title to your private library as unfinished and places it in a private '
        '<em>Release Radar</em> collection. Nothing is shared, rated, or reviewed until you choose to. If you already have the title, '
        'we reuse your entry instead of creating a duplicate.</p>'
        '<p><strong>Dates move.</strong> Games slip, streaming drops change, and some films open in limited release first. '
        'Each card links to its source so you can double-check before you plan a night around it.</p>'
        f'<ul class="radar-sources">{source_list}</ul>'
        f'{affiliate.disclosure_html()}</section>'
    )


def _notes_html(notes: list[str]) -> str:
    if not notes:
        return ""
    return ('<section class="radar-notes" aria-labelledby="radar-notes-title"><h2 id="radar-notes-title">Radar notes</h2><ul>'
            + "".join(f"<li>{escape(n)}</li>" for n in notes) + "</ul></section>")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@router.get("/release-radar")
async def radar_hub(request: Request, db: Session = Depends(get_db)):
    today = _today()
    windows = {c: radar.featured_window(c, today) for c in radar.CATEGORY_ORDER}
    entries = dict(zip(windows, await asyncio.gather(*(radar.CACHE.get(_client(request), w) for w in windows.values()))))
    items_by_category = {c: (entries[c] or {}).get("items", []) for c in radar.CATEGORY_ORDER}
    counts = {c: library_counts(db, c, items) for c, items in items_by_category.items()}
    total = sum(len(items) for items in items_by_category.values())

    # The two-week strip can straddle a month or season boundary: add the
    # neighbouring period when it is already cached (never wait on it here).
    strip_pool = {c: list(items) for c, items in items_by_category.items()}
    for category, window in windows.items():
        current = radar.current_window(category, today)
        neighbours = radar.allowed_windows(category, today)
        other = current if window != current else neighbours[neighbours.index(current) + 1]
        cached = radar.CACHE.peek(other)
        if cached:
            known = {i["key"] for i in strip_pool[category]}
            strip_pool[category] += [i for i in cached.get("items", []) if i["key"] not in known]
        elif window == current:
            # Warm the next period in the background so the strip fills in.
            radar.CACHE.warm(_client(request), other)
    soon = [i for items in strip_pool.values() for i in radar.upcoming_within(items, today, 14)]
    extra_counts = {c: library_counts(db, c, [i for i in soon if i["category"] == c and i["key"] not in counts[c]])
                    for c in radar.CATEGORY_ORDER}
    for c in radar.CATEGORY_ORDER:
        counts[c].update(extra_counts[c])
    # Keep the two-week strip varied: at most five per category.
    per_category: dict[str, int] = {}
    strip = []
    for item in sorted(soon, key=lambda i: -i["popularity"]):
        if per_category.get(item["category"], 0) < 5:
            per_category[item["category"]] = per_category.get(item["category"], 0) + 1
            strip.append(item)
    strip.sort(key=lambda i: (i["date"], -i["popularity"]))

    sections = []
    for category in radar.CATEGORY_ORDER:
        items = items_by_category[category]
        window = windows[category]
        path = f"/release-radar/{category}"
        upcoming = [i for i in items if not i["date"] or i["date"] >= today.isoformat()] or items
        top = sorted(upcoming, key=lambda i: -i["popularity"])[:6]
        top.sort(key=lambda i: (i["date"] or "9999", -i["popularity"]))
        cards = "".join(render_card(i, counts[category].get(i["key"], 0), "/release-radar", compact=True) for i in top)
        status = _status_message(entries[category], category) if not items else ""
        sections.append(
            f'<section class="radar-section" aria-labelledby="radar-{category}"><div class="radar-section__head">'
            f'<h2 id="radar-{category}">{escape(radar.CATEGORY_LABELS[category])} <span class="radar-section__period">· {escape(window.label)}</span></h2>'
            f'<a class="button" href="{path}">See all {len(items) or ""} →</a></div>{status}'
            f'<div class="radar-grid">{cards}</div></section>'
        )

    most_tracked = sorted(
        ((counts[c][i["key"]], i) for c in radar.CATEGORY_ORDER for i in items_by_category[c] if counts[c].get(i["key"])),
        key=lambda pair: (-pair[0], pair[1]["title"].lower()),
    )[:5]
    tracked_html = ""
    if most_tracked:
        rows = "".join(
            f'<li><a href="/release-radar/{i["category"]}#item-{escape(i["key"], quote=True)}">{escape(i["title"])}</a>'
            f' <span class="muted">{escape(radar.CATEGORY_SINGULAR[i["category"]])} · {count} {"library" if count == 1 else "libraries"}</span></li>'
            for count, i in most_tracked
        )
        tracked_html = f'<section class="radar-notes"><h2>Already on OmniTrackr shelves</h2><ol class="radar-tracked">{rows}</ol></section>'

    strip_html = ""
    if strip:
        strip_cards = "".join(render_card(i, counts[i["category"]].get(i["key"], 0), "/release-radar", compact=True) for i in strip)
        strip_html = (f'<section class="radar-section radar-section--soon" aria-labelledby="radar-soon"><div class="radar-section__head">'
                      f'<h2 id="radar-soon">Out in the next two weeks</h2></div><div class="radar-grid">{strip_cards}</div></section>')

    summary = " · ".join(f"{len(items_by_category[c])} {SUMMARY_LABELS[c]}" for c in radar.CATEGORY_ORDER if items_by_category[c])
    content = (
        '<header class="hero radar-hero"><p class="eyebrow">Release Radar · updated every few hours</p>'
        '<h1>What is coming out, all in one place.</h1>'
        '<p>New movies, TV premieres, the current anime season and upcoming games, side by side. '
        'Spot something you want to see, play or finish, and track it in one click.</p>'
        + (f'<p class="radar-hero__summary">{escape(summary)}</p>' if summary else "")
        + '</header>' + _category_tabs(None) + strip_html + tracked_html + "".join(sections) + _about_section(None)
    )
    indexable = total >= MIN_INDEXABLE_ITEMS
    title = f"Release Radar: new movies, TV, anime and games for {windows['movies'].label}"
    description = "Upcoming movie releases, TV premieres, this season's anime and new video games in one calendar, with one-click tracking."
    structured = _structured(title, "/release-radar", strip or [i for c in radar.CATEGORY_ORDER for i in items_by_category[c][:6]])
    warming = any(entries[c] is None for c in radar.CATEGORY_ORDER)
    return _render(title, description, "/release-radar", content, indexable=indexable, structured=structured,
                   ads=radar.RADAR_ADS and total >= AD_ELIGIBLE_MIN_ITEMS, refresh=warming)


@router.get("/release-radar/jump")
def radar_jump(to: str = ""):
    """No-JavaScript fallback for the period picker; only internal radar paths are accepted."""
    from fastapi.responses import RedirectResponse
    parts = to.strip("/").split("/")
    if len(parts) in (2, 3) and parts[0] == "release-radar" and parts[1] in radar.CATEGORY_ORDER:
        if len(parts) == 2 or radar.parse_window(parts[1], parts[2], _today()):
            return RedirectResponse("/" + "/".join(parts), status_code=303)
    return RedirectResponse("/release-radar", status_code=303)


async def _category_page(request: Request, db: Session, category: str, window: radar.Window):
    entry = await radar.CACHE.get(_client(request), window)
    items = (entry or {}).get("items", [])
    counts = library_counts(db, category, items)
    canonical = _category_path(category, window)
    return_path = canonical
    notes = radar.radar_notes(category, items, window)
    groups = "".join(
        f'<section class="radar-week" aria-label="{escape(label, quote=True)}"><h2 class="radar-week__title">{escape(label)}</h2>'
        f'<div class="radar-grid">{"".join(render_card(i, counts.get(i["key"], 0), return_path) for i in group)}</div></section>'
        for label, group in _group_by_week(items)
    )
    title = SEO_TITLES[category].format(label=window.label)
    description = (f"{len(items) or 'Every'} {SUMMARY_LABELS[category]} for {window.label}, "
                   "with dates, details and one-click tracking in OmniTrackr.")
    content = (
        f'<header class="hero radar-hero radar-hero--{category}"><p class="eyebrow">Release Radar · {escape(window.label)}</p>'
        f'<h1>{escape(title)}</h1><p>{escape(PAGE_INTROS[category])}</p></header>'
        + _category_tabs(category) + _window_nav(category, window)
        + _status_message(entry, category)
        + _notes_html(notes)
        + (_filters(category, items) if items else "")
        + f'<div id="radar-list" data-radar-category="{category}" data-radar-window="{window.slug}">{groups}</div>'
        + '<p id="radar-empty" class="trail-empty" hidden>Nothing matches those filters. Try another genre or clear the search.</p>'
        + _about_section(category)
    )
    indexable = radar.INDEX_CATEGORY_PAGES and len(items) >= MIN_INDEXABLE_ITEMS
    return _render(title, description, canonical, content, indexable=indexable,
                   structured=_structured(title, canonical, items) if items else None,
                   ads=radar.RADAR_ADS and len(items) >= AD_ELIGIBLE_MIN_ITEMS, refresh=entry is None)


@router.get("/release-radar/{category}")
async def radar_category(category: str, request: Request, db: Session = Depends(get_db)):
    if category not in radar.CATEGORY_ORDER:
        raise HTTPException(404, "Unknown Release Radar section")
    return await _category_page(request, db, category, radar.featured_window(category, _today()))


@router.get("/release-radar/{category}/{slug}")
async def radar_category_window(category: str, slug: str, request: Request, db: Session = Depends(get_db)):
    if category not in radar.CATEGORY_ORDER:
        raise HTTPException(404, "Unknown Release Radar section")
    window = radar.parse_window(category, slug, _today())
    if window is None:
        raise HTTPException(404, "That period is outside the Release Radar range")
    return await _category_page(request, db, category, window)


# ---------------------------------------------------------------------------
# Authenticated API
# ---------------------------------------------------------------------------

def _match(db: Session, user_id: int, category: str, title: str):
    model = CATEGORY_MODELS[category]
    return (db.query(model)
            .filter(model.user_id == user_id, func.lower(func.trim(model.title)) == title.strip().lower())
            .order_by(model.id).first())


def _window_items(category: str, slug: str) -> tuple[radar.Window, list[dict]]:
    if category not in radar.CATEGORY_ORDER:
        raise HTTPException(404, "Unknown Release Radar section")
    window = radar.parse_window(category, slug, _today())
    if window is None:
        raise HTTPException(404, "That period is outside the Release Radar range")
    entry = radar.CACHE.peek(window)
    return window, (entry or {}).get("items", [])


@router.get("/api/release-radar/{category}/{slug}/library")
def radar_library_status(category: str, slug: str, response: Response,
                         user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Which radar titles in this list the signed-in member already has."""
    response.headers["Cache-Control"] = "private, no-store"
    _, items = _window_items(category, slug)
    model = CATEGORY_MODELS[category]
    titles = {(i["save"].get("title") or "").strip().lower(): i["key"] for i in items}
    titles.pop("", None)
    if not titles:
        return {"keys": []}
    normalized = func.lower(func.trim(model.title))
    owned = {row[0] for row in db.query(normalized).filter(model.user_id == user.id, normalized.in_(sorted(titles))).all()}
    return {"keys": sorted(titles[t] for t in owned)}


class RadarSave(BaseModel):
    category: str = Field(max_length=10)
    window: str = Field(max_length=20)
    key: str = Field(min_length=1, max_length=80)


def _build_record(category: str, user_id: int, save: dict):
    model = CATEGORY_MODELS[category]
    title = (save.get("title") or "").strip()[:200]
    if category == "movies":
        return model(user_id=user_id, title=title, director=save.get("director"), year=save.get("year"), watched=False)
    if category in ("tv", "anime"):
        record = model(user_id=user_id, title=title, year=save.get("year"), watched=False, poster_url=save.get("poster_url"))
        if category == "anime" and save.get("episodes"):
            record.episodes = save["episodes"]
        return record
    release = None
    if save.get("release_date"):
        try:
            release = datetime.fromisoformat(save["release_date"])
        except ValueError:
            release = None
    return model(user_id=user_id, title=title, release_date=release, genres=save.get("genres"), played=False,
                 cover_art_url=save.get("cover_art_url"), rawg_link=save.get("rawg_link"))


@router.post("/api/release-radar/save")
def radar_save(selection: RadarSave, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Add one radar title to the member's library (reusing an existing entry) and the private Radar collection."""
    response.headers["Cache-Control"] = "private, no-store"
    _, items = _window_items(selection.category, selection.window)
    item = next((i for i in items if i["key"] == selection.key), None)
    if item is None or not (item["save"].get("title") or "").strip():
        raise HTTPException(404, "That release is no longer on the radar. Reload the page and try again.")
    category = selection.category
    # Serialize concurrent saves for this member on PostgreSQL.
    db.query(models.User).filter(models.User.id == user.id).with_for_update().first()
    try:
        record = _match(db, user.id, category, item["save"]["title"])
        state = "existing"
        if record is None:
            record = _build_record(category, user.id, item["save"])
            db.add(record)
            db.flush()
            state = "created"
        collection = (db.query(models.Collection)
                      .filter_by(user_id=user.id, name=COLLECTION_NAME)
                      .order_by(models.Collection.id).first())
        if collection is None:
            collection = models.Collection(user_id=user.id, name=COLLECTION_NAME, description=COLLECTION_DESCRIPTION)
            db.add(collection)
            db.flush()
        collection_category = COLLECTION_CATEGORY[category]
        linked = db.query(models.CollectionItem).filter_by(
            collection_id=collection.id, category=collection_category, item_id=record.id).first()
        if linked is None:
            position = (db.query(func.max(models.CollectionItem.position))
                        .filter(models.CollectionItem.collection_id == collection.id).scalar())
            db.add(models.CollectionItem(collection_id=collection.id, category=collection_category,
                                         item_id=record.id, position=(position if position is not None else -1) + 1))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"state": state, "title": record.title, "collection_id": collection.id}


# ---------------------------------------------------------------------------
# Homepage strip: fresh, public release data for the anonymous landing page.
# Reads only what is already cached (never waits); warms missing lists.
# ---------------------------------------------------------------------------

HOME_STRIP_MAX = 10
HOME_STRIP_DAYS = 21


def home_strip_items(client=None, today: Optional[date] = None) -> list[dict]:
    today = today or _today()
    pool: list[dict] = []
    for category in radar.CATEGORY_ORDER:
        current = radar.current_window(category, today)
        windows = radar.allowed_windows(category, today)
        for window in (current, windows[windows.index(current) + 1]):
            entry = radar.CACHE.peek(window)
            if entry is None:
                if client is not None:
                    radar.CACHE.warm(client, window)
                continue
            pool.extend(entry.get("items", []))
    upcoming = {i["key"]: i for i in radar.upcoming_within(pool, today, HOME_STRIP_DAYS)}.values()
    per_category: dict[str, int] = {}
    chosen = []
    for item in sorted(upcoming, key=lambda i: -i["popularity"]):
        if per_category.get(item["category"], 0) < 3:
            per_category[item["category"]] = per_category.get(item["category"], 0) + 1
            chosen.append(item)
        if len(chosen) >= HOME_STRIP_MAX:
            break
    return sorted(chosen, key=lambda i: (i["date"], -i["popularity"]))


def home_strip_html(client=None, today: Optional[date] = None) -> str:
    items = home_strip_items(client, today)
    if len(items) < 4:
        return ""
    labels = {"movies": "Movie", "tv": "TV", "anime": "Anime", "games": "Game"}
    cards = []
    for item in items:
        art = (f'<img src="{escape(item["image"], quote=True)}" alt="" width="200" height="300" loading="lazy" decoding="async" referrerpolicy="no-referrer">'
               if item.get("image") else f'<span class="lp-radar-card__initial" aria-hidden="true">{escape(item["title"][:1].upper())}</span>')
        cards.append(
            f'<li><a class="lp-radar-card" href="/release-radar/{item["category"]}#item-{escape(item["key"], quote=True)}">'
            f'<span class="lp-radar-card__art">{art}<span class="lp-radar-card__type">{labels[item["category"]]}</span></span>'
            f'<span class="lp-radar-card__date"><time datetime="{item["date"]}">{_format_day(item["date"])}</time></span>'
            f'<span class="lp-radar-card__title">{escape(item["title"])}</span></a></li>'
        )
    return (
        '<section class="lp-section lp-radar" aria-labelledby="lp-radar-title"><div class="lp-wrap">'
        '<div class="lp-section-head lp-section-head--row"><div><p class="lp-eyebrow">Release Radar · updated every few hours</p>'
        '<h2 id="lp-radar-title">Coming out soon</h2></div>'
        '<a class="lp-link-arrow" href="/release-radar">See everything coming out <span aria-hidden="true">→</span></a></div>'
        f'<ul class="lp-radar-rail">{"".join(cards)}</ul></div></section>'
    )
