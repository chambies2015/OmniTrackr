"""Seasonal hubs (/halloween), plus each member's progress and the dashboard card.

The hub reads completely without scripts or an account. Members add one pick or
a whole shelf to their library (title, year and creator only) and see which picks
they already have; visitors keep picks in their browser-only guest list until
they sign up. The dashboard card appears only while the season is running.
"""
from __future__ import annotations

from datetime import date
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import challenges, funnel, pick, seasonal, title_pages, title_search
from ..auth import AUTH_COOKIE_NAME
from ..dependencies import get_current_user, get_db
from ..progress import lock_progress_owner
from ..seasonal_guides import SEASONS
from .discover import page

router = APIRouter(tags=["seasonal"])
CSS_VERSION = "20261019-halloween-1"
JS_VERSION = "20261019-halloween-1"
GUEST_LIST_JS = "/static/guest-list.js?v=20261012-hero-search-1"
SITE = "https://omnitrackr.xyz"
MAX_ADD = 30
FORMAT_PLURALS = {"movie": "movies", "tv": "TV shows", "anime": "anime", "game": "games", "book": "books", "album": "music"}


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _paragraphs(values) -> str:
    return "".join(f"<p>{_e(value)}</p>" for value in values)


def _long_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%B %d, %Y").replace(" 0", " ")


def _details(db: Session) -> dict:
    """{pool id: {"url", "image"}} for picks with a public title page (never raises)."""
    try:
        return pick.title_details(title_search.index(db))
    except Exception:
        return {}


def _meta_line(item: dict) -> str:
    parts = [title_pages.KINDS[item["kind"]][3], str(item["year"])]
    if item["creator"]:
        parts.append(item["creator"])
    return " · ".join(parts)


def _fright(entry: dict, level: int) -> str:
    label = seasonal.fright_label(entry, level)
    marks = "".join(f'<span class="sn-fright__mark{" sn-fright__mark--on" if index <= level else ""}"></span>'
                    for index in range(1, 6))
    return (f'<p class="sn-fright sn-fright--{level}"><span class="sn-fright__marks" aria-hidden="true">{marks}</span>'
            f'<span>Fright {level} of 5 · {_e(label)}</span></p>')


def _save_button(entry: dict, signed_in: bool) -> str:
    if signed_in:
        return (f'<button type="button" class="button sn-save" data-season-add="{_e(entry["id"])}">'
                'Add to my library</button>')
    return (f'<button type="button" class="button sn-save" aria-pressed="false" data-guest-kind="{_e(entry["kind"])}" '
            f'data-guest-slug="{_e(entry["slug"])}" data-guest-title="{_e(entry["title"])}">'
            '<span class="sn-when-off">Save to my list</span><span class="sn-when-on">Saved to your list ✓</span></button>')


def _pick_html(entry: dict, item: dict, details: dict, signed_in: bool) -> str:
    pooled = seasonal.pool_entry(item)
    detail = details.get(pooled["id"], {}) if pooled else {}
    image = title_pages._safe_image(detail.get("image"))
    art = (f'<img class="sn-pick__art" src="{_e(image)}" alt="" width="96" height="144" loading="lazy" '
           'decoding="async" referrerpolicy="no-referrer">' if image
           else f'<span class="sn-pick__art sn-pick__art--letter" aria-hidden="true">{_e(item["title"][:1])}</span>')
    title_link = (f'<a class="sn-pick__link" href="{_e(detail["url"])}">See the title page</a>'
                  if detail.get("url") else "")
    save = _save_button(pooled, signed_in) if pooled else ""
    pick_id = _e(pooled["id"]) if pooled else ""
    return (
        f'<article class="pick sn-pick" id="{_e(seasonal.anchor_id(item))}" data-season-pick="{pick_id}">'
        f'<div class="sn-pick__head">{art}<div><p class="eyebrow">{_e(_meta_line(item))}</p>'
        f'<h3>{_e(item["title"])}</h3>{_fright(entry, item["fright"])}'
        f'<p class="sn-pick__time">{_e(item["time"])}</p></div></div>'
        f'<p class="sn-pick__why">{_e(item["why"])}</p><p>{_e(item["note"])}</p>'
        f'<p class="caveat"><strong>Before you start:</strong> {_e(item["caveat"])}</p>'
        f'<div class="sn-pick__actions">{save}{title_link}'
        '<span class="sn-pick__owned" data-season-owned hidden></span></div>'
        '<p class="sn-pick__status" data-season-status role="status" aria-live="polite"></p></article>'
    )


def _shelf_html(entry: dict, shelf: dict, details: dict, signed_in: bool) -> str:
    ids = [pooled["id"] for pooled in (seasonal.pool_entry(item) for item in shelf["picks"]) if pooled]
    shelf_action = (f'<button type="button" class="button button--ghost sn-shelf__all" data-season-add-shelf="{_e(" ".join(ids))}">'
                    f'Add all {len(ids)} to my library</button>' if signed_in else "")
    levels = [item["fright"] for item in shelf["picks"]]
    parts = [
        f'<section class="sn-shelf sn-shelf--{_e(shelf["key"])}" id="{_e(shelf["key"])}" aria-labelledby="shelf-{_e(shelf["key"])}">',
        f'<header class="sn-shelf__head"><p class="eyebrow">FRIGHT {min(levels)} TO {max(levels)}</p>',
        f'<h2 id="shelf-{_e(shelf["key"])}">{_e(shelf["name"])}</h2><p class="sn-shelf__tagline">{_e(shelf["tagline"])}</p>',
        f'<div class="sn-shelf__intro">{_paragraphs(shelf["intro"])}</div>{shelf_action}',
        '<p class="sn-shelf__status" data-season-shelf-status role="status" aria-live="polite"></p></header>',
        '<div class="sn-picks">',
    ]
    parts.extend(_pick_html(entry, item, details, signed_in) for item in shelf["picks"])
    parts.append('</div></section>')
    return "".join(parts)


def _guest_bar(signed_in: bool) -> str:
    if signed_in:
        return ""
    return ('<div class="yl-bar sn-bar" data-guest-bar hidden><p class="yl-bar__count" data-guest-count role="status" aria-live="polite"></p>'
            '<a class="button" href="/#signup" data-season-signup>Save my list, free →</a></div>')


def _head(signed_in: bool) -> str:
    head = (f'<link rel="stylesheet" href="/static/if-you-liked.css?v={CSS_VERSION}">'
            f'<link rel="stylesheet" href="/static/seasonal.css?v={CSS_VERSION}">')
    if not signed_in:
        head += f'<script src="{GUEST_LIST_JS}" defer></script>'
        head += '<script src="/static/ad-loader.js" defer></script>'
    head += f'<script src="/static/seasonal.js?v={JS_VERSION}" defer></script>'
    return head


def _related(today: date) -> str:
    from ..discover_catalog import MONTHLY_EDITIONS
    links = []
    edition = f"october-{today.year}"
    if edition in MONTHLY_EDITIONS:
        links.append((f"/discover/monthly/{edition}", MONTHLY_EDITIONS[edition]["name"],
                      "The quieter side of October: six unsettling works that skip the jump scares."))
    month = f"{today.year}-10"
    if month in challenges.public_months(today):
        links.append((f"/challenges/{challenges.slug_for(month)}", f"The {challenges.month_label(month)} challenge",
                      challenges.CHALLENGES[month]["tagline"]))
    links.extend([
        ("/if-you-liked", "If you liked…", "What to watch, play and read after a title you loved, across every format."),
        ("/pick", "Pick for me", "Still undecided? Get one suggestion at a time, including these Halloween picks."),
    ])
    cards = "".join(f'<article><h3><a href="{_e(href)}">{_e(name)}</a></h3><p>{_e(text)}</p></article>'
                    for href, name, text in links)
    return ('<section class="guide-related" aria-labelledby="related-heading"><p class="eyebrow">MORE TO READ</p>'
            f'<h2 id="related-heading">More for October</h2><div class="guide-related-grid">{cards}</div></section>')


def hub_content(slug: str, entry: dict, details: dict, signed_in: bool, today: date) -> str:
    items = seasonal.picks(entry)
    formats = sorted({item["kind"] for item in items}, key=list(title_pages.KINDS).index)
    jump = "".join(f'<a href="#{_e(shelf["key"])}">{_e(shelf["name"])}</a>' for shelf in entry["shelves"])
    progress = ('<section class="sn-progress" data-season-progress="' + _e(slug) + '" aria-labelledby="sn-progress-title" hidden>'
                f'<p class="eyebrow">YOUR {_e(entry["name"].upper())}</p><h2 id="sn-progress-title" data-season-progress-title>Your progress</h2>'
                f'<div class="sn-meter" role="progressbar" aria-valuemin="0" aria-valuemax="{len(items)}" aria-valuenow="0" '
                'aria-labelledby="sn-progress-title" data-season-meter><span class="sn-meter__fill" data-season-meter-fill></span></div>'
                '<p class="sn-progress__text" data-season-progress-text></p></section>') if signed_in else ""
    scale = "".join(f'<li>{_fright(entry, value)}<span class="sn-scale__text">{_e(text)}</span></li>'
                    for value, _, text in entry["scale"])
    nights = "".join(f'<li><h3>{_e(night["name"])}</h3><p>{_e(night["plan"])}</p></li>' for night in entry["nights"])
    faq = "".join(f'<details class="sn-faq__item"><summary>{_e(question)}</summary><p>{_e(answer)}</p></details>'
                  for question, answer in entry["faq"])
    reviewed = entry["reviewed"]
    parts = [
        f'<article class="trail-guide sn-hub" data-season-theme="{_e(entry["theme"])}">',
        '<header class="hero hero--guide sn-hero"><span class="sn-hero__moon" aria-hidden="true"></span>',
        f'<p class="eyebrow">SEASONAL · {_e(entry["name"].upper())} {today.year}</p>',
        f'<h1>{_e(entry["headline"])}</h1><p class="guide-deck">{_e(entry["deck"])}</p>',
        '<p class="guide-byline">By <a href="/about">OmniTrackr</a> · Updated ',
        f'<time datetime="{_e(reviewed)}">{_e(_long_date(reviewed))}</time> · '
        f'{len(items)} picks across {_e(", ".join(FORMAT_PLURALS[kind] for kind in formats))}</p>',
        f'<nav class="guide-jump" aria-label="Shelves">{jump}<a href="#plan">Plan your night</a><a href="#faq">Questions</a></nav></header>',
        progress,
        f'<div class="guide-intro">{_paragraphs(entry["intro"])}</div>',
        '<section class="sn-scale" aria-labelledby="scale-heading"><p class="eyebrow">THE FRIGHT SCALE</p>',
        f'<h2 id="scale-heading">How scary is it?</h2><ol class="sn-scale__list">{scale}</ol></section>',
    ]
    if not signed_in:
        parts.append('<p class="yl-section-intro sn-guest-note">Save any pick to a list as you go, no account needed. '
                     'Your list moves into a free library when you sign up.</p>')
    parts.extend(_shelf_html(entry, shelf, details, signed_in) for shelf in entry["shelves"])
    parts.extend([
        _guest_bar(signed_in),
        f'<section id="plan" class="editorial sn-plan" aria-labelledby="plan-heading"><p class="eyebrow">PLAN YOUR NIGHT</p>'
        f'<h2 id="plan-heading">Five kinds of Halloween night</h2><ul class="sn-nights">{nights}</ul></section>',
        f'<section id="faq" class="editorial sn-faq" aria-labelledby="faq-heading"><h2 id="faq-heading">Questions</h2>{faq}</section>',
        _related(today),
        '<section class="guide-sources yl-method" aria-labelledby="method-heading"><h2 id="method-heading">How we chose</h2>',
        _paragraphs(entry["method"]),
        f'<p class="muted">First published {_e(_long_date(entry["published"]))}. Checked {_e(_long_date(reviewed))}. '
        '<a href="/contact">Suggest a pick or send a correction</a> · <a href="/content-quality">Editorial standards</a></p>'
        '</section></article>',
    ])
    return "".join(parts)


def _structured(entry: dict) -> dict:
    url = SITE + entry["path"]
    return {"@context": "https://schema.org", "@graph": [
        {
            "@type": "Article", "headline": entry["headline"], "description": entry["summary"],
            "datePublished": entry["published"], "dateModified": entry["reviewed"],
            "mainEntityOfPage": url, "url": url, "inLanguage": "en-US",
            "author": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/about"},
            "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/"},
            "mainEntity": {"@type": "ItemList", "numberOfItems": len(seasonal.picks(entry)), "itemListElement": [
                {"@type": "ListItem", "position": index, "name": item["title"], "url": f"{url}#{seasonal.anchor_id(item)}"}
                for index, item in enumerate(seasonal.picks(entry), 1)
            ]},
        },
        {
            "@type": "FAQPage", "url": url + "#faq", "mainEntity": [
                {"@type": "Question", "name": question, "acceptedAnswer": {"@type": "Answer", "text": answer}}
                for question, answer in entry["faq"]
            ],
        },
    ]}


def _hub(slug: str):
    def view(request: Request, db: Session = Depends(get_db)):
        entry = SEASONS[slug]
        signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
        content = hub_content(slug, entry, _details(db), signed_in, date.today())
        response = page(entry["search_title"], entry["summary"], entry["path"], content,
                        structured_data=_structured(entry), head=_head(signed_in))
        response.headers["Cache-Control"] = "private, no-cache"
        response.headers["Vary"] = "Cookie"
        return response
    view.__name__ = f"seasonal_{slug}"
    return view


for _slug, _entry in SEASONS.items():
    router.add_api_route(_entry["path"], _hub(_slug), methods=["GET"], include_in_schema=False)


# ---------------------------------------------------------------- member API

def _season_or_404(slug: str) -> dict:
    entry = seasonal.season(slug)
    if entry is None:
        raise HTTPException(404, "Season not found")
    return entry


@router.get("/api/seasonal/current")
def seasonal_current(request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """The season running today, with the member's progress, for the dashboard card ({"season": null} otherwise)."""
    response.headers["Cache-Control"] = "private, no-store"
    slug = seasonal.current()
    if slug is None:
        return {"season": None}
    entry = SEASONS[slug]
    progress = seasonal.progress(db, user.id, slug)
    return {
        "season": slug, "name": entry["name"], "theme": entry["theme"], "path": entry["path"],
        "year": date.today().year, "card": entry["card"], "days_left": seasonal.days_left(entry),
        "shelves": [{"key": shelf["key"], "name": shelf["name"], "tagline": shelf["tagline"]} for shelf in entry["shelves"]],
        "total": progress["total"], "tracked": progress["tracked"], "done": progress["done"],
    }


@router.get("/api/seasonal/{slug}/progress")
def seasonal_progress(slug: str, request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Which of the season's picks are in the member's library, read from the library itself."""
    response.headers["Cache-Control"] = "private, no-store"
    _season_or_404(slug)
    return seasonal.progress(db, user.id, slug)


class SeasonalAdd(BaseModel):
    ids: list[str] = Field(..., min_length=1, max_length=MAX_ADD)


@router.post("/api/seasonal/{slug}/add")
def seasonal_add(slug: str, payload: SeasonalAdd, request: Request, response: Response,
                 user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Add picks from a season to the member's library as not started (title, year and creator only)."""
    response.headers["Cache-Control"] = "private, no-store"
    entry = _season_or_404(slug)
    known = {pooled["id"]: pooled for pooled in (seasonal.pool_entry(item) for item in seasonal.picks(entry)) if pooled}
    if any(pick_id not in known for pick_id in payload.ids):
        raise HTTPException(404, "Pick not found")
    lock_progress_owner(db, user.id)
    owned = seasonal.progress(db, user.id, slug)["entries"]
    details = _details(db)
    added, existing = [], []
    for pick_id in dict.fromkeys(payload.ids):
        if pick_id in owned:
            existing.append({"id": pick_id, "title": known[pick_id]["title"]})
            continue
        state, record = pick.add_to_library(db, user, known[pick_id], details.get(pick_id, {}).get("image"))
        (added if state == "created" else existing).append({"id": pick_id, "title": record.title})
    db.commit()
    if added:
        funnel.record("seasonal_saved", request)
    return {"added": added, "existing": existing, "progress": seasonal.progress(db, user.id, slug)}
