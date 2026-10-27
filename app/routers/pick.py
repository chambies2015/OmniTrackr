"""Pick for me (/pick): one curated suggestion at a time, for visitors and members."""
from __future__ import annotations

from html import escape
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import funnel, pick, title_pages, title_search
from ..auth import AUTH_COOKIE_NAME
from ..dependencies import get_current_user, get_db
from ..progress import lock_progress_owner
from . import next_up
from .discover import page

router = APIRouter(tags=["pick"])
CSS_VERSION = "20261022-next-up-1"
JS_VERSION = "20261022-next-up-1"
GUEST_LIST_JS = "/static/guest-list.js?v=20261012-hero-search-1"
DESCRIPTION = ("Can't decide what to watch, play or read? Pick for me suggests one movie, TV show, anime, game, "
               "book or album at a time, with a reason to try it and a caveat to consider first.")


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _meta_line(entry: dict) -> str:
    parts = [entry["label"]]
    if entry["year"]:
        parts.append(str(entry["year"]))
    if entry["creator"]:
        parts.append(entry["creator"])
    return " · ".join(parts)


def _source_url(entry: dict, collection_links: dict) -> Optional[str]:
    return entry["source_url"] or collection_links.get(entry["source_label"])


def card(entry: dict, details: dict, collection_links: dict, signed_in: bool) -> str:
    """The suggestion card. pick-for-me.js builds the same markup for later picks."""
    detail = details.get(entry["id"], {})
    image = detail.get("image")
    art = (f'<img class="pf-card__art" src="{_e(image)}" alt="" width="120" height="180" loading="lazy" referrerpolicy="no-referrer">'
           if image else '')
    source_url = _source_url(entry, collection_links)
    source = (f'<a href="{_e(source_url)}">{_e(entry["source_label"])}</a>' if source_url else _e(entry["source_label"]))
    caveat = f'<p class="caveat pf-card__caveat">{_e(entry["caveat"])}</p>' if entry["caveat"] else ''
    if signed_in:
        save = f'<button type="button" class="button pf-card__save" data-pick-add="{_e(entry["id"])}">Add to my library</button>'
    else:
        save = (f'<button type="button" class="button pf-card__save" data-guest-kind="{_e(entry["kind"])}" '
                f'data-guest-slug="{_e(entry["slug"])}" data-guest-title="{_e(entry["title"])}" aria-pressed="false">'
                '<span class="pf-when-off">Save to my list</span><span class="pf-when-on">Saved to your list ✓</span></button>')
    title_link = (f'<a class="pf-card__link" href="{_e(detail["url"])}">See the title page</a>' if detail.get("url") else '')
    return (
        f'<div class="pf-card__body">{art}<div class="pf-card__text">'
        f'<p class="eyebrow pf-card__meta">{_e(_meta_line(entry))}</p>'
        f'<h2 class="pf-card__title" id="pfCardTitle">{_e(entry["title"])}</h2>'
        f'<p class="pf-card__why">{_e(entry["why"])}</p>{caveat}'
        f'<p class="pf-card__source muted">From {source}</p></div></div>'
        f'<div class="pf-card__actions">{save}'
        '<button type="button" class="pf-card__again" data-pick-again hidden>Pick again</button>'
        '<button type="button" class="pf-card__share" data-pick-share hidden>Share this pick</button>'
        f'{title_link}</div>'
        '<p class="pf-card__status" data-pick-status role="status" aria-live="polite"></p>'
    )


def _format_chips(selected: Optional[str]) -> str:
    chips = []
    for value, label in [("", "Anything")] + [(kind, pick.FORMAT_LABELS[kind]) for kind in pick.KIND_ORDER]:
        checked = " checked" if (selected or "") == value else ""
        chips.append(f'<label class="pf-chip"><input type="radio" name="format" value="{value}"{checked}><span>{label}</span></label>')
    return "".join(chips)


def _pool_section(details: dict, collection_links: dict) -> str:
    groups = []
    for kind in pick.KIND_ORDER:
        entries = pick.candidates(kind)
        if not entries:
            continue
        items = []
        for entry in entries:
            detail = details.get(entry["id"], {})
            name = (f'<a href="{_e(detail["url"])}">{_e(entry["title"])}</a>' if detail.get("url") else _e(entry["title"]))
            source_url = _source_url(entry, collection_links)
            source = (f'<a href="{_e(source_url)}">{_e(entry["source_label"])}</a>' if source_url else _e(entry["source_label"]))
            facts = " · ".join(str(part) for part in (entry["year"], entry["creator"]) if part)
            facts = f'<span class="pf-pool__facts">{_e(facts)}</span>' if facts else ''
            items.append(
                f'<li><span class="pf-pool__name">{name}</span>'
                f'{facts}'
                f'<span class="pf-pool__from">From {source}</span>'
                f'<button type="button" class="pf-pool__show" data-pick-show="{_e(entry["id"])}" aria-label="Show {_e(entry["title"])}" hidden>Show</button></li>'
            )
        groups.append(f'<section class="pf-pool__group"><h3>{_e(pick.FORMAT_LABELS[kind])} <span>({len(entries)})</span></h3>'
                      f'<ul>{"".join(items)}</ul></section>')
    total = len(pick.pool())
    return (f'<section id="pick-pool" class="pf-pool" aria-labelledby="pfPoolHeading"><p class="eyebrow">THE WHOLE POOL</p>'
            f'<h2 id="pfPoolHeading">Every title we might pick ({total})</h2>'
            '<p>Prefer to browse? These are all the titles Pick for me draws from, grouped by format. Each one comes from a '
            'Discover trail, a monthly edition, an editors\' collection or an "If you liked" guide, where you can read it next to the picks it was chosen with.</p>'
            f'<div class="pf-pool__groups">{"".join(groups)}</div></section>')


def _pool_rows(details: dict, collection_links: dict) -> list[dict]:
    rows = []
    for entry in pick.pool():
        detail = details.get(entry["id"], {})
        rows.append({
            "id": entry["id"], "kind": entry["kind"], "slug": entry["slug"], "label": entry["label"],
            "title": entry["title"], "year": entry["year"], "creator": entry["creator"],
            "why": entry["why"], "caveat": entry["caveat"], "source": entry["source_label"],
            "sourceUrl": _source_url(entry, collection_links), "url": detail.get("url"), "image": detail.get("image"),
        })
    return rows


GUIDANCE = (
    '<section class="editorial pf-guide"><h2>How to choose when everything sounds good</h2>'
    '<p>Decision fatigue is real: when a streaming row, a game backlog and a stack of books all compete for one free evening, '
    'it is easy to spend the evening choosing. Narrowing the choice to a single suggestion takes that weight away. You are '
    'only deciding yes or no, and "no" just means another pick.</p>'
    '<p>Start with the time you actually have. A movie or an album fits one evening; a book, a season of TV or an anime '
    'series asks for a few sittings; a game can be either, depending on how you play it. Then read the caveat before the '
    'reason. If the caveat describes something you are not in the mood for tonight, skip it.</p>'
    '<p>Finally, give your pick a fair start: twenty minutes of a film, one episode of a show, the first chapter of a book '
    'or the first hour of a game. Saving it to a list also helps, because a pick you are not ready for tonight can still '
    'be the right one next weekend.</p></section>'
    '<section class="editorial pf-method"><h2>Where these picks come from</h2>'
    '<p>Every suggestion comes from OmniTrackr\'s own editorial writing: the Discover trails, the monthly editions, the "If you liked" guides and the '
    'starter collections written by the OmniTrackr editors. They are not rankings, sponsored placements or anyone\'s '
    'private ratings. Picks are random within the format you choose, and the page avoids repeating a recent pick until it '
    'runs out of others.</p>'
    '<p class="muted">Availability varies by region. Source links are informational, not affiliate links. '
    '<a href="/content-quality">Editorial standards</a> · <a href="/discover">Browse every Discover trail</a></p></section>'
)


@router.get("/pick", include_in_schema=False)
def pick_page(request: Request,
              format: str = Query("", max_length=10),
              pick_id: str = Query("", alias="pick", max_length=160),
              db: Session = Depends(get_db)):
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    kind = format if format in pick.KIND_ORDER else None
    chosen = pick.find_id(pick_id) if pick_id else None
    if chosen is None:
        chosen = pick.choose(kind) if kind else pick.of_the_day()
    details = pick.title_details(title_search.index(db))
    collection_links = pick.collection_links(db)
    intro = ('Pick a format, or leave it on Anything, and get one movie, TV show, anime, game, book or album with a reason '
             'to try it. ' + ('Like it? Add it to your library in one tap.' if signed_in else
                              'Like it? Save it to a list, no account needed.'))
    guest_bar = ('' if signed_in else
                 '<div class="pf-bar" data-guest-bar hidden><p class="pf-bar__count" data-guest-count></p>'
                 '<a class="button" href="/#signup" data-pick-signup>Save my list, free →</a></div>')
    content = (
        '<header class="hero pf-hero"><p class="eyebrow">PICK FOR ME</p>'
        '<h1>Can\'t decide what to start?</h1>'
        f'<p>{_e(intro)}</p></header>'
        f'<section class="pf-tool" id="pick-tool" data-signed-in="{"true" if signed_in else "false"}" aria-label="Pick for me">'
        '<form class="pf-form" action="/pick" method="get" data-pick-form>'
        f'<fieldset class="pf-formats"><legend>What are you in the mood for?</legend>{_format_chips(kind)}</fieldset>'
        '<button type="submit" class="button pf-go">Pick for me</button></form>'
        f'<article class="pf-card" id="pickCard" aria-labelledby="pfCardTitle" data-pick-id="{_e(chosen["id"])}">'
        f'{card(chosen, details, collection_links, signed_in)}</article>{guest_bar}</section>'
        + GUIDANCE
        + _pool_section(details, collection_links)
    )
    head = f'<link rel="stylesheet" href="/static/pick-for-me.css?v={CSS_VERSION}">'
    if not signed_in:
        head += f'<script src="{GUEST_LIST_JS}" defer></script>'
    head += f'<script src="/static/pick-for-me.js?v={JS_VERSION}" defer></script>'
    response = page("Pick for me: what to watch, play or read next", DESCRIPTION, "/pick", content,
                    indexable=not (format or pick_id), head=head,
                    structured_data={
                        "@context": "https://schema.org", "@type": "WebPage",
                        "name": "Pick for me", "description": DESCRIPTION,
                        "url": "https://omnitrackr.xyz/pick", "inLanguage": "en-US",
                        "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": "https://omnitrackr.xyz/"},
                    })
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


@router.get("/api/pick/pool")
def pick_pool(request: Request, response: Response, db: Session = Depends(get_db)):
    """Every pick with its public details, for picking in the browser without a request per pick."""
    response.headers["Cache-Control"] = "public, max-age=600"
    details = pick.title_details(title_search.index(db))
    return {"picks": _pool_rows(details, pick.collection_links(db))}


SAVE_EVENTS = {"pick": "pick_saved", "if-you-liked": "liked_saved", "seasonal": "seasonal_saved", "taste-quiz": "quiz_saved"}


class PickAdd(BaseModel):
    id: str = Field(..., min_length=3, max_length=160)
    # Where the button was: Pick for me itself, an "If you liked" guide or a seasonal hub (counted separately on Site stats).
    source: Literal["pick", "if-you-liked", "seasonal", "taste-quiz"] = "pick"
    # Also line it up in the member's Next Up queue (skipped when it is already finished).
    next_up: bool = False


@router.post("/api/pick/add")
def add_pick(payload: PickAdd, request: Request, response: Response,
             user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a Pick for me suggestion to the member's library (title, year and creator only)."""
    response.headers["Cache-Control"] = "private, no-store"
    entry = pick.find_id(payload.id)
    if entry is None:
        raise HTTPException(404, "Pick not found")
    lock_progress_owner(db, user.id)
    image = pick.title_details(title_search.index(db)).get(entry["id"], {}).get("image")
    state, record = pick.add_to_library(db, user, entry, image)
    queued = None
    if payload.next_up:
        if getattr(record, title_pages.COMPLETE_FIELD[entry["kind"]], False):
            queued = "finished"
        else:
            queued = "queued" if next_up.enqueue(db, user.id, entry["category"], record.id) else "already_queued"
    result = {
        "state": state, "title": record.title, "category": entry["category"],
        "library_url": f"/?library_category={entry['category']}&library_item={record.id}",
        "next_up": queued,
    }
    db.commit()
    if state == "created":
        funnel.record(SAVE_EVENTS[payload.source], request)
    return result
