"""Public "New this week" roundups (/new-this-week, /new-this-week/<monday>, /new-this-week/archive).

The data and the write-up live in app/weekly_roundup.py. Pages read completely
without scripts or an account; release cards reuse Release Radar's cards and
script, so members can still track a title while its period is on the radar.
"""
from __future__ import annotations

import threading
import time
from datetime import date, timedelta
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import affiliate, best_of, seasonal, title_pages
from .. import release_radar as radar
from .. import weekly_roundup as roundup
from ..dependencies import get_db
from ..seasonal_guides import SEASONS
from . import release_radar as radar_pages

router = APIRouter(tags=["new-this-week"])
CSS_VERSION = "20261027-roundup-1"
HEAD = f'<link rel="stylesheet" href="/static/weekly-roundup.css?v={CSS_VERSION}">'
SITE = "https://omnitrackr.xyz"
PAGE_CACHE_SECONDS = 600
TEASER_LIMIT = 6

_cache_lock = threading.Lock()
_page_cache: dict = {}


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _paragraphs(values) -> str:
    return "".join(f"<p>{_e(value)}</p>" for value in values)


def clear_cache() -> None:
    with _cache_lock:
        _page_cache.clear()


# ---------------------------------------------------------------- links to title pages

def _release_slug(item: dict) -> tuple[str, str]:
    kind = roundup.RADAR_KIND[item["category"]]
    save = item.get("save") or {}
    title = (save.get("title") or item["title"]).strip()
    year = save.get("year")
    if kind == "game":
        released = save.get("release_date") or item.get("date") or ""
        year = int(released[:4]) if released[:4].isdigit() else None
    return kind, title_pages.title_slug(title, year)


def title_links(db: Session, payload: dict) -> tuple[dict, dict]:
    """Title page paths that exist right now: {release key: path} and {(kind, title): path} for member rows."""
    wanted: dict[str, set[str]] = {}
    for category in radar.CATEGORY_ORDER:
        for item in roundup.releases(payload, category):
            kind, slug = _release_slug(item)
            wanted.setdefault(kind, set()).add(slug)
    members = payload.get("members") or {}
    for row in (members.get("finished") or []) + (members.get("added") or []):
        wanted.setdefault(row["kind"], set()).add(title_pages.title_slug(row["title"], row.get("year")))
    found: dict[str, dict] = {}
    for kind, slugs in wanted.items():
        try:
            found[kind] = title_pages.find_many(db, kind, sorted(slugs))
        except Exception:
            db.rollback()
            found[kind] = {}
    releases = {}
    for category in radar.CATEGORY_ORDER:
        for item in roundup.releases(payload, category):
            kind, slug = _release_slug(item)
            group = found.get(kind, {}).get(slug)
            if group is not None:
                releases[item["key"]] = group.path
    member_paths = {}
    for row in (members.get("finished") or []) + (members.get("added") or []):
        group = found.get(row["kind"], {}).get(title_pages.title_slug(row["title"], row.get("year")))
        if group is not None:
            member_paths[(row["kind"], row["title"])] = group.path
    return releases, member_paths


# ---------------------------------------------------------------- page pieces

def _trackable(item: dict, today: date) -> bool:
    return bool(item.get("window")) and radar.parse_window(item["category"], item["window"], today) is not None


def _radar_link(category: str, monday: date, today: date) -> str:
    windows = roundup.windows_for_week(category, monday, today)
    if not windows:
        return ""
    window = windows[0]
    href = radar_pages._category_path(category, window)
    return (f'<a class="nw-more" href="{_e(href)}">Everything on Release Radar for {_e(window.label)} '
            '<span aria-hidden="true">→</span></a>')


def _best_of_link(category: str, year: int) -> str:
    slug = best_of.find(year, category)
    if not slug:
        return ""
    from ..best_of_guides import GUIDES
    return f'<a class="nw-more" href="{_e(best_of.path(slug))}">{_e(GUIDES[slug]["name"])} <span aria-hidden="true">→</span></a>'


def _glance(payload: dict) -> str:
    tiles = []
    for category in radar.CATEGORY_ORDER:
        n = len(roundup.releases(payload, category))
        if n:
            tiles.append(f'<li><a href="#{category}"><strong>{n}</strong><span>{_e(roundup.HEADINGS[category].lower())}</span></a></li>')
    finishers = (payload.get("members") or {}).get("finishers") or 0
    if finishers:
        tiles.append(f'<li><a href="#members"><strong>{finishers}</strong><span>members finished something</span></a></li>')
    return f'<ul class="nw-glance" aria-label="This week at a glance">{"".join(tiles)}</ul>' if tiles else ""


def _week_nav(monday: date, saved: set[date], today: date) -> str:
    prev_week, next_week = monday - timedelta(days=7), monday + timedelta(days=7)
    this_week = roundup.current_monday(today)
    prev_link = (f'<a href="{roundup.path(prev_week)}" rel="prev">← Week of {_e(roundup._day(prev_week))}</a>'
                 if prev_week in saved else "<span></span>")
    next_link = (f'<a class="nw-weeknav__next" href="{roundup.path(next_week)}" rel="next">Week of {_e(roundup._day(next_week))} →</a>'
                 if next_week <= this_week and (next_week in saved or next_week == this_week) else "<span></span>")
    return (f'<nav class="nw-weeknav" aria-label="Other weeks">{prev_link}'
            f'<a class="nw-weeknav__archive" href="{roundup.ARCHIVE_PATH}">Every week</a>{next_link}</nav>')


def _category_section(category: str, payload: dict, when: str, monday: date, today: date, links: dict) -> str:
    items = roundup.releases(payload, category)
    if not items:
        return ""
    counts = roundup.counts_of(payload, category)
    text = roundup.category_paragraphs(category, items, counts, when)
    return_path = roundup.path(monday)
    cards = "".join(
        radar_pages.render_card(item, counts.get(item["key"], 0), return_path, compact=True,
                                trackable=_trackable(item, today), title_path=links.get(item["key"], ""))
        for item in items
    )
    more = "".join(filter(None, [_radar_link(category, monday, today), _best_of_link(category, monday.year)]))
    return (
        f'<section class="nw-section" id="{category}" aria-labelledby="{category}-heading">'
        f'<h2 id="{category}-heading">{_e(roundup.HEADINGS[category])} <span class="nw-count">{len(items)}</span></h2>'
        f'<div class="nw-prose">{_paragraphs(text)}</div>'
        f'<div class="radar-grid">{cards}</div>'
        + (f'<p class="nw-links">{more}</p>' if more else "")
        + '</section>'
    )


def _member_list(rows: list[dict], paths: dict, show_rating: bool) -> str:
    items = []
    for row in rows:
        href = paths.get((row["kind"], row["title"]))
        name = f'<a href="{_e(href)}">{_e(row["title"])}</a>' if href else _e(row["title"])
        detail = f'{_e(roundup.KIND_LABELS[row["kind"]])} · {row["members"]} members'
        if show_rating and row.get("average") is not None:
            detail += f' · {row["average"]:g}/10 average'
        items.append(f'<li>{name} <span class="muted">{detail}</span></li>')
    return f'<ol class="nw-members__list">{"".join(items)}</ol>'


def _members_section(payload: dict, when: str, paths: dict) -> str:
    members = payload.get("members") or {}
    text = roundup.member_paragraphs(members, when)
    finished, added = members.get("finished") or [], members.get("added") or []
    if not text and not finished and not added:
        return ""
    lists = ""
    if finished:
        lists += f'<div><h3>Most finished</h3>{_member_list(finished, paths, True)}</div>'
    if added:
        lists += f'<div><h3>Most added to libraries</h3>{_member_list(added, paths, False)}</div>'
    return (
        '<section class="nw-section nw-members" id="members" aria-labelledby="members-heading">'
        f'<h2 id="members-heading">What OmniTrackr members {"finished that" if when == "past" else "are finishing this"} week</h2>'
        f'<div class="nw-prose">{_paragraphs(text)}</div>'
        + (f'<div class="nw-members__grid">{lists}</div>' if lists else "")
        + '<p class="muted nw-small">Counted from members who keep that part of their library shareable. Only titles at least '
          'two members finished or added are named, and member names are never shown.</p></section>'
    )


def _review_section(review: Optional[dict]) -> str:
    if not review:
        return ""
    text = " ".join((review.get("review") or "").split())
    excerpt = text if len(text) <= 320 else text[:320].rsplit(" ", 1)[0] + "…"
    url = f"/reviews/{int(review['id'])}?category={_e(review.get('category'))}"
    return (
        '<section class="nw-section nw-review" aria-labelledby="review-heading">'
        '<h2 id="review-heading">Review of the week</h2><blockquote>'
        f'<p class="nw-review__title"><a href="{url}">{_e(review.get("title"))}</a></p><p>{_e(excerpt)}</p>'
        f'<footer>by {_e(review.get("username") or "a member")} · <a href="{url}">Read the full review</a></footer>'
        '</blockquote></section>'
    )


def _teaser_section(monday: date, today: date) -> str:
    """What is already dated for next week, from whatever Release Radar has cached (never waits)."""
    next_monday = monday + timedelta(days=7)
    picked = []
    for category in radar.CATEGORY_ORDER:
        windows = roundup.windows_for_week(category, next_monday, today) or []
        entries = [radar.CACHE.peek(window) for window in windows]
        picked += roundup._top(roundup.week_items(category, entries, next_monday), 2)
    if len(picked) < 3:
        return ""
    picked = sorted(picked, key=lambda i: (i["date"], -i["popularity"]))[:TEASER_LIMIT]
    rows = "".join(
        f'<li><a href="{_e(radar.item_path(i, today))}#item-{_e(i["key"])}">{_e(i["title"])}</a> '
        f'<span class="muted">{_e(radar.CATEGORY_SINGULAR[i["category"]])} · {_e(roundup._weekday(i["date"]))}</span></li>'
        for i in picked
    )
    return ('<section class="nw-section nw-next" aria-labelledby="next-heading">'
            f'<h2 id="next-heading">Already dated for next week</h2><ul>{rows}</ul>'
            '<p class="muted nw-small">The full roundup for next week appears here on Monday.</p></section>')


def _seasonal_links(monday: date) -> str:
    links = []
    for slug, entry in SEASONS.items():
        if any(seasonal.in_window(entry, monday + timedelta(days=offset)) for offset in range(7)):
            links.append(f'<a class="nw-more" href="{_e(entry["path"])}">{_e(entry["name"])} picks for every kind of night '
                         '<span aria-hidden="true">→</span></a>')
    return "".join(links)


def _method_section() -> str:
    return (
        '<section class="editorial nw-method" id="method" aria-labelledby="method-heading">'
        '<h2 id="method-heading">How this roundup is made</h2>'
        '<p>Every Monday a new page starts for the week ahead. Releases come from OmniTrackr\'s '
        '<a href="/release-radar">Release Radar</a>: films from Wikidata, TV premieres from TVmaze, the anime season from AniList '
        'and games from RAWG. A roundup lists the releases dated inside its week, Monday to Sunday (UTC), with the most followed '
        'titles in each format. The write-up is calculated from that data, so nobody paid to be included and nothing is ranked '
        'by hand.</p>'
        '<p>The member section counts what OmniTrackr members logged as finished and added that week. It only names a title '
        'when at least two members finished or added it, and members who keep a category private are never counted.</p>'
        '<p>The page updates while its week is running. A couple of days after the week ends it is saved as it stands, so the '
        '<a href="' + roundup.ARCHIVE_PATH + '">archive</a> shows what actually came out each week. Dates move, and some films '
        'open in limited release first, so each card links to its source. '
        '<a href="/contact">Send a correction</a> · <a href="/content-quality">Editorial standards</a></p>'
        f'{affiliate.disclosure_html()}</section>'
    )


def _structured(monday: date, payload: dict, title: str, description: str) -> dict:
    url = SITE + roundup.path(monday)
    elements = []
    position = 0
    for category in radar.CATEGORY_ORDER:
        for item in roundup.releases(payload, category)[:10]:
            position += 1
            elements.append({"@type": "ListItem", "position": position, "name": item["title"], "url": f"{url}#item-{item['key']}"})
    modified = (payload.get("built_at") or monday.isoformat())[:10]
    return {
        "@context": "https://schema.org", "@type": "Article",
        "headline": title, "description": description,
        "datePublished": monday.isoformat(), "dateModified": max(modified, monday.isoformat()),
        "mainEntityOfPage": url, "url": url, "inLanguage": "en-US",
        "author": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/about"},
        "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/"},
        "isPartOf": {"@type": "CollectionPage", "name": "New this week", "url": SITE + roundup.ARCHIVE_PATH},
        "mainEntity": {"@type": "ItemList", "numberOfItems": roundup.total_releases(payload), "itemListElement": elements},
    }


def page_texts(monday: date, payload: dict, when: str) -> tuple[str, str]:
    """(title, meta description) for one week."""
    highlights = roundup.headline_titles(payload, 3)
    including = f", including {roundup._join(highlights)}" if highlights else ""
    if when == "current":
        title = f"New this week: movies, TV, anime and games for {roundup.label(monday)}"
    else:
        title = f"New releases for the week of {roundup.label(monday)}"
    description = (f"{roundup.total_releases(payload)} new movies, TV premieres, anime and games for {roundup.label(monday)}"
                   f"{including}, plus what OmniTrackr members finished that week.")
    return title, description[:300]


def week_content(monday: date, payload: dict, previous: Optional[dict], when: str, today: date,
                 saved: set[date], links: tuple[dict, dict], review: Optional[dict]) -> str:
    title, _ = page_texts(monday, payload, when)
    release_links, member_paths = links
    lead = roundup.lead_paragraphs(payload, previous, when)
    built = (payload.get("built_at") or "")[:10]
    updated = ""
    if built:
        built_day = date.fromisoformat(built)
        updated = f' · Updated <time datetime="{built}">{_e(roundup._day(built_day))}, {built_day.year}</time>'
    jump = [f'<a href="#{c}">{_e(roundup.HEADINGS[c])}</a>' for c in radar.CATEGORY_ORDER if roundup.releases(payload, c)]
    if (payload.get("members") or {}).get("finished") or (payload.get("members") or {}).get("added"):
        jump.append('<a href="#members">Members</a>')
    jump.append('<a href="#method">How it is made</a>')
    sections = "".join(_category_section(c, payload, when, monday, today, release_links) for c in radar.CATEGORY_ORDER)
    empty = ""
    if not roundup.total_releases(payload):
        empty = ('<div class="radar-status" role="status">Nothing on Release Radar is dated for this week yet. '
                 'Check back soon, or browse <a href="/release-radar">everything coming up</a>.</div>')
    related = "".join(filter(None, [
        _seasonal_links(monday),
        '<a class="nw-more" href="/release-radar">Release Radar: the next few months <span aria-hidden="true">→</span></a>',
        '<a class="nw-more" href="/best-of">The best of the year so far <span aria-hidden="true">→</span></a>',
        '<a class="nw-more" href="/pick">Not sure what to start? Pick for me <span aria-hidden="true">→</span></a>',
    ]))
    return (
        '<article class="nw-page">'
        f'<header class="hero radar-hero nw-hero"><p class="eyebrow">New this week · {_e(roundup.short_label(monday))}, {monday.year}</p>'
        f'<h1>{_e(title)}</h1>'
        f'<p class="guide-byline">By <a href="/about">OmniTrackr</a> · Week of <time datetime="{monday.isoformat()}">'
        f'{_e(roundup._day(monday))}, {monday.year}</time>{updated}</p>'
        f'{_glance(payload)}</header>'
        + _week_nav(monday, saved, today)
        + f'<div class="nw-prose nw-lead">{_paragraphs(lead)}</div>'
        + (f'<nav class="radar-tabs nw-jump" aria-label="On this page">{"".join(jump)}</nav>' if len(jump) > 2 else "")
        + empty + sections
        + _members_section(payload, when, member_paths)
        + (_review_section(review) if when == "current" else "")
        + (_teaser_section(monday, today) if when == "current" else "")
        + radar_pages._calendar_box(None)
        + f'<section class="nw-section nw-related" aria-labelledby="related-heading"><h2 id="related-heading">Keep exploring</h2><p class="nw-links">{related}</p></section>'
        + _method_section()
        + _week_nav(monday, saved, today)
        + '</article>'
    )


# ---------------------------------------------------------------- routes

def _client(request: Request):
    return getattr(request.app.state, "external_api_client", None)


@router.get(roundup.BASE_PATH, include_in_schema=False)
def this_week():
    # A fixed target built from today's date: nothing from the request goes into the Location header.
    response = RedirectResponse(roundup.path(roundup.current_monday()), status_code=302)
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


def _saved_weeks(db: Session) -> set[date]:
    return {row[0] for row in db.query(roundup.models.WeeklyRoundup.week_start).all()}


def _review_of_the_week() -> Optional[dict]:
    try:
        from ..review_spotlight import review_of_the_week
        return review_of_the_week()
    except Exception:
        return None


@router.get(roundup.ARCHIVE_PATH, include_in_schema=False)
async def roundup_archive(request: Request, db: Session = Depends(get_db)):
    today = radar.today_utc()
    # Make sure this week is saved, so the newest entry is never missing.
    await roundup.ensure(_client(request), db, roundup.current_monday(today), today=today, run=run_in_threadpool)
    saved = await run_in_threadpool(roundup.weeks, db)
    by_month: dict[str, list] = {}
    indexable_weeks = 0
    for monday, payload, _ in saved:
        if roundup.status(monday, today) == "future":
            continue
        good = roundup.is_indexable(payload, monday, today)
        indexable_weeks += good
        by_month.setdefault(f"{monday.strftime('%B')} {monday.year}", []).append((monday, payload))
    groups = []
    for month, rows in by_month.items():
        items = []
        for monday, payload in rows:
            counts = [roundup._plural(len(roundup.releases(payload, c)), *roundup.NOUNS[c])
                      for c in radar.CATEGORY_ORDER if roundup.releases(payload, c)]
            highlights = roundup.headline_titles(payload, 3)
            items.append(
                f'<li><a class="nw-archive__week" href="{roundup.path(monday)}"><strong>Week of {_e(roundup.label(monday))}</strong>'
                f'<span>{_e(", ".join(counts) or "No dated releases")}</span>'
                + (f'<span class="muted">Including {_e(roundup._join(highlights))}</span>' if highlights else "")
                + '</a></li>'
            )
        groups.append(f'<section class="nw-archive__month"><h2>{_e(month)}</h2><ul class="nw-archive">{"".join(items)}</ul></section>')
    if not groups:
        groups.append('<div class="radar-status" role="status">The first roundup is being put together. '
                      'Check back in a few minutes.</div>')
    title = "New this week: every weekly release roundup"
    description = ("Every week's new movies, TV premieres, anime and games in one place, with what OmniTrackr members "
                   "finished that week. A new roundup starts each Monday.")
    content = (
        '<header class="hero radar-hero nw-hero"><p class="eyebrow">New this week · the archive</p>'
        f'<h1>{_e(title)}</h1><p>One page per week, Monday to Sunday: the new movies, TV premieres, anime and games dated that '
        'week, a short write-up of what stands out, and what OmniTrackr members finished. Past weeks are kept as they were, '
        'so you can look back at what came out when.</p>'
        f'<p><a class="button" href="{roundup.path(roundup.current_monday(today))}">Read this week\'s roundup →</a></p></header>'
        + "".join(groups) + _method_section()
    )
    structured = {
        "@context": "https://schema.org", "@type": "CollectionPage", "name": title, "description": description,
        "url": SITE + roundup.ARCHIVE_PATH, "inLanguage": "en-US",
        "isPartOf": {"@type": "WebSite", "name": "OmniTrackr", "url": SITE + "/"},
        "mainEntity": {"@type": "ItemList", "itemListElement": [
            {"@type": "ListItem", "position": index, "name": f"Week of {roundup.label(monday)}", "url": SITE + roundup.path(monday)}
            for index, (monday, _, _) in enumerate((w for w in saved if roundup.status(w[0], today) != "future"), 1)
        ][:60]},
    }
    response = radar_pages._render(title, description, roundup.ARCHIVE_PATH, content, indexable=indexable_weeks > 0,
                                   structured=structured, head=HEAD)
    response.headers["Cache-Control"] = "public, max-age=600"
    return response


@router.get(roundup.BASE_PATH + "/{slug}", include_in_schema=False)
async def roundup_week(slug: str, request: Request, db: Session = Depends(get_db)):
    monday = roundup.parse_slug(slug)
    today = radar.today_utc()
    if monday is None or roundup.status(monday, today) == "future":
        raise HTTPException(404, "No roundup for that week")
    when = roundup.status(monday, today)
    payload = await roundup.ensure(_client(request), db, monday, today=today, run=run_in_threadpool)
    if payload is None:
        if when != "current":
            raise HTTPException(404, "No roundup for that week")
        content = ('<header class="hero radar-hero nw-hero"><p class="eyebrow">New this week</p>'
                   f'<h1>New this week: {_e(roundup.label(monday))}</h1></header>'
                   '<div class="radar-status" role="status"><strong>Gathering this week\'s releases right now.</strong> '
                   'This page refreshes itself in under a minute, or reload whenever you like.</div>' + _method_section())
        return radar_pages._render(f"New this week: {roundup.label(monday)}", "This week's new movies, TV, anime and games.",
                                   roundup.path(monday), content, indexable=False, refresh=True, head=HEAD)

    key = (monday, payload.get("built_at"), when)
    now = time.monotonic()
    with _cache_lock:
        cached = _page_cache.get(key)
    if cached and now - cached[0] < PAGE_CACHE_SECONDS:
        _, title, description, content, indexable, structured = cached
    else:
        def gather():
            previous = roundup.payload_of(roundup.load(db, monday - timedelta(days=7)))
            return previous, _saved_weeks(db), title_links(db, payload)
        previous, saved, links = await run_in_threadpool(gather)
        review = await run_in_threadpool(_review_of_the_week) if when == "current" else None
        title, description = page_texts(monday, payload, when)
        content = week_content(monday, payload, previous, when, today, saved | {monday}, links, review)
        indexable = roundup.is_indexable(payload, monday, today, previous)
        structured = _structured(monday, payload, title, description)
        with _cache_lock:
            if len(_page_cache) > 200:
                _page_cache.clear()
            _page_cache[key] = (now, title, description, content, indexable, structured)
    response = radar_pages._render(title, description, roundup.path(monday), content, indexable=indexable,
                                   structured=structured, head=HEAD,
                                   ads=roundup.ROUNDUP_ADS and indexable)
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


# ---------------------------------------------------------------- background saving

async def roundup_loop(app) -> None:
    """Keep this week's and last week's roundups saved even when nobody opens them."""
    import asyncio

    from ..database import SessionLocal
    await asyncio.sleep(300)
    while True:
        try:
            await save_recent_weeks(getattr(app.state, "external_api_client", None), SessionLocal)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"Weekly roundup refresh failed: {error}")
        await asyncio.sleep(3 * 3600)


async def save_recent_weeks(client, session_factory, today: Optional[date] = None) -> int:
    """Build every week Release Radar still covers, back to the start of its earliest period. Returns weeks saved."""
    today = today or radar.today_utc()
    this_week = roundup.current_monday(today)
    earliest = min(radar.allowed_windows(c, today)[0].start for c in radar.CATEGORY_ORDER)
    monday = roundup.monday_of(earliest)
    saved = 0
    while monday <= this_week:
        db = session_factory()
        try:
            if await roundup.ensure(client, db, monday, today=today, wait=30, run=run_in_threadpool) is not None:
                saved += 1
        finally:
            db.close()
        monday += timedelta(days=7)
    return saved
