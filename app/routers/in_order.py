"""Public "In order" guides (/in-order and /in-order/<slug>), plus member progress.

Hand-written guides to the order a franchise is best watched, read and played in.
Pages read completely without scripts or an account. Members see which entries their
library already has and finishes, and can add the rest in one go; visitors keep
entries in their browser-only guest list until they sign up.
"""
from __future__ import annotations

from datetime import date
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import funnel, in_order, title_pages, title_search
from ..auth import AUTH_COOKIE_NAME
from ..dependencies import get_current_user, get_db
from ..in_order_guides import GUIDES
from ..progress import lock_progress_owner
from .discover import page

router = APIRouter(tags=["in-order"])
CSS_VERSION = "20261017-order-2"
JS_VERSION = "20261017-order-2"
GUEST_LIST_JS = "/static/guest-list.js?v=20261012-hero-search-1"
SITE = "https://omnitrackr.xyz"
FIRST_PUBLISHED = "2026-10-17"
HUB_TITLE = "Franchises in order: what to watch, read and play first"
HUB_DESCRIPTION = ("Guides to the best order for Star Wars, The Witcher, The Lord of the Rings, Harry Potter, "
                   "Dune, Alien, Monogatari, Fate, Zelda and more, across films, series, books and games.")
FORMAT_PLURALS = {"movie": "films", "tv": "series", "anime": "anime", "game": "games", "book": "books", "album": "albums"}
MAX_ADD = 40


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _paragraphs(values) -> str:
    return "".join(f"<p>{_e(value)}</p>" for value in values)


def _long_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%B %d, %Y").replace(" 0", " ")


def _details(db: Session) -> dict:
    """{saveable id: {"url", "image"}} for entries with a public title page (never raises)."""
    try:
        return in_order.title_details(title_search.index(db))
    except Exception:
        return {}


def _meta_line(item: dict) -> str:
    parts = [title_pages.KINDS[item["kind"]][3]]
    if item["year"]:
        parts.append(str(item["year"]))
    if item.get("creator"):
        parts.append(item["creator"])
    return " · ".join(parts)


def _formats_text(entry: dict) -> str:
    names = [FORMAT_PLURALS[kind] for kind in in_order.formats(entry)]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _save_button(item: dict, signed_in: bool) -> str:
    if signed_in:
        return (f'<button type="button" class="button io-save" data-io-add="{_e(item["id"])}">'
                'Add to my library</button>')
    fields = in_order.saveable(item)
    return (f'<button type="button" class="button io-save" aria-pressed="false" data-guest-kind="{_e(fields["kind"])}" '
            f'data-guest-slug="{_e(fields["slug"])}" data-guest-title="{_e(fields["title"])}">'
            '<span class="io-when-off">Save to my list</span><span class="io-when-on">Saved to your list ✓</span></button>')


def _progress_panel(slug: str, entry: dict, signed_in: bool) -> str:
    total = len(in_order.core(entry))
    if signed_in:
        # Filled in from the member's own library by in-order.js.
        return (f'<section class="io-progress" data-io-progress="{_e(slug)}" aria-labelledby="progress-heading" hidden>'
                '<p class="eyebrow">YOUR PROGRESS</p><h2 id="progress-heading" data-io-progress-title>Your progress</h2>'
                f'<div class="io-meter" role="progressbar" aria-valuemin="0" aria-valuemax="{total}" aria-valuenow="0" '
                'aria-labelledby="progress-heading" data-io-meter><span data-io-meter-fill></span></div>'
                '<p class="io-progress__next" data-io-next></p>'
                '<div class="io-progress__actions"><button type="button" class="button" data-io-add-all hidden></button></div>'
                '<p class="io-progress__status" data-io-status role="status" aria-live="polite"></p></section>')
    return (f'<section class="io-progress io-progress--guest" aria-labelledby="progress-heading">'
            '<p class="eyebrow">TRACK IT</p>'
            f'<h2 id="progress-heading">Keep your place in {_e(entry["name"])}</h2>'
            f'<p>Save the {total} main entries to a list now, no account needed. Create a free OmniTrackr account and they move '
            'into your library, where this page shows how far through you are and what comes next.</p>'
            f'<div class="io-progress__actions"><button type="button" class="button" data-io-guest-all>Save all {total} to my list</button>'
            '<a href="/#signup" class="io-progress__link">Create a free account</a></div>'
            '<p class="io-progress__status" data-io-status role="status" aria-live="polite"></p></section>')


def _order_html(order: dict, by_id: dict, recommended: bool) -> str:
    rows = []
    for position, item_id in enumerate(order["ids"], 1):
        item = by_id[item_id]
        optional = '<span class="io-tag">Optional</span>' if item.get("optional") else ""
        rows.append(
            f'<li data-io-entry="{_e(item_id)}"><span class="io-row__num">{position}</span>'
            f'<span class="io-row__text"><a href="#{_e(in_order.anchor_id(item))}">{_e(item["title"])}</a>'
            f'<small>{_e(title_pages.KINDS[item["kind"]][3])}{" · " + str(item["year"]) if item["year"] else ""}</small></span>'
            f'{optional}<span class="io-row__state" data-io-state></span></li>'
        )
    badge = '<span class="io-tag io-tag--pick">Our pick</span>' if recommended else ""
    return (f'<section class="io-order" id="order-{_e(order["key"])}" data-io-order="{_e(order["key"])}" '
            f'aria-labelledby="order-{_e(order["key"])}-heading">'
            f'<h3 id="order-{_e(order["key"])}-heading">{_e(order["name"])}{badge}</h3>'
            f'<p class="io-order__pitch">{_e(order["pitch"])}</p><ol class="io-rows">{"".join(rows)}</ol></section>')


def _entry_html(entry: dict, item: dict, details: dict, signed_in: bool) -> str:
    fields = in_order.saveable(item)
    detail = details.get(fields["id"], {})
    image = title_pages._safe_image(detail.get("image"))
    art = (f'<img class="io-entry__art" src="{_e(image)}" alt="" width="96" height="144" loading="lazy" '
           'decoding="async" referrerpolicy="no-referrer">' if image
           else f'<span class="io-entry__art io-entry__initial" aria-hidden="true">{_e(item["title"][:1])}</span>')
    title_link = (f'<a class="io-entry__link" href="{_e(detail["url"])}">See the title page</a>' if detail.get("url") else "")
    where = " · ".join(f"{name}: #{position}" for name, position in in_order.positions(entry, item["id"]))
    optional = '<span class="io-tag">Optional</span>' if item.get("optional") else ""
    return (
        f'<article class="pick io-entry{" is-optional" if item.get("optional") else ""}" id="{_e(in_order.anchor_id(item))}" '
        f'data-io-entry="{_e(item["id"])}">'
        f'<div class="io-entry__head">{art}<div><p class="eyebrow">{_e(_meta_line(item))}</p>'
        f'<h3>{_e(item["title"])}{optional}</h3>'
        + (f'<p class="io-entry__where">{_e(where)}</p>' if where else "")
        + f'</div></div><p>{_e(item["note"])}</p>'
        f'<div class="io-entry__actions">{_save_button(item, signed_in)}{title_link}'
        '<span class="io-entry__state" data-io-state></span></div>'
        '<p class="io-entry__status" data-io-entry-status role="status" aria-live="polite"></p></article>'
    )


def _head(signed_in: bool, ads: bool) -> str:
    head = f'<link rel="stylesheet" href="/static/in-order.css?v={CSS_VERSION}">'
    if not signed_in:
        head += f'<script src="{GUEST_LIST_JS}" defer></script>'
    head += f'<script src="/static/in-order.js?v={JS_VERSION}" defer></script>'
    if ads and not signed_in:
        head += '<script src="/static/ad-loader.js" defer></script>'
    return head


def guide_content(slug: str, entry: dict, details: dict, signed_in: bool) -> str:
    by_id = in_order.entries(entry)
    reviewed = entry["reviewed"]
    total = len(entry["entries"])
    parts = [
        '<article class="trail-guide io-guide">',
        f'<header class="hero hero--guide"><a href="{in_order.BASE_PATH}">← Every franchise in order</a>',
        f'<p class="eyebrow">IN ORDER · {_e(_formats_text(entry).upper())}</p>',
        f'<h1>{_e(entry["name"])} in order</h1><p class="guide-deck">{_e(entry["summary"])}</p>',
        '<p class="guide-byline">By <a href="/about">OmniTrackr</a> · Updated ',
        f'<time datetime="{_e(reviewed)}">{_e(_long_date(reviewed))}</time></p>',
        '<nav class="guide-jump" aria-label="On this page"><a href="#orders">The orders</a>',
        '<a href="#entries">Every entry</a><a href="#where-to-start">Where to start</a><a href="#questions">Questions</a>',
        '<a href="#method">How we chose</a></nav></header>',
        f'<div class="guide-intro">{_paragraphs(entry["lead"])}</div>',
        _progress_panel(slug, entry, signed_in),
        '<section id="orders" class="io-orders" aria-labelledby="orders-heading"><p class="eyebrow">THE ORDERS</p>',
        f'<h2 id="orders-heading">{len(entry["orders"])} ways through {_e(entry["name"])}</h2>' if len(entry["orders"]) > 1
        else f'<h2 id="orders-heading">The order to follow</h2>',
        '<p class="io-section-intro">The first order is the one we recommend for most people. Entries marked optional are side '
        'stories you can skip without missing the main story.</p>',
    ]
    if len(entry["orders"]) > 1:
        tabs = "".join(
            f'<button type="button" role="tab" id="tab-{_e(order["key"])}" aria-controls="order-{_e(order["key"])}" '
            f'aria-selected="{"true" if index == 0 else "false"}" data-io-tab="{_e(order["key"])}">{_e(order["name"])}</button>'
            for index, order in enumerate(entry["orders"]))
        parts.append(f'<div class="io-tabs" role="tablist" aria-label="Choose an order" data-io-tabs hidden>{tabs}</div>')
    parts.append('<div class="io-order-list">')
    for index, order in enumerate(entry["orders"]):
        parts.append(_order_html(order, by_id, index == 0))
    parts.extend([
        '</div></section>',
        '<section id="entries" aria-labelledby="entries-heading"><p class="eyebrow">EVERY ENTRY</p>',
        f'<h2 id="entries-heading">All {total} entries, in our recommended order</h2>',
        '<p class="io-section-intro">What each one is, why it sits where it does, and where it falls in each order.'
        + ('' if signed_in else ' Save any of them to a list, no account needed.') + '</p>',
        '<div class="picks io-entries">',
    ])
    for item in in_order.recommended(entry):
        parts.append(_entry_html(entry, item, details, signed_in))
    parts.append('</div></section>')
    if not signed_in:
        parts.append('<div class="io-bar" data-guest-bar hidden><p class="io-bar__count" data-guest-count role="status" aria-live="polite"></p>'
                     '<a class="button" href="/#signup" data-io-signup>Save my list, free →</a></div>')
    parts.extend([
        '<section id="where-to-start" class="editorial io-start"><h2>Where to start</h2>', _paragraphs(entry["start"]), '</section>',
        '<section id="questions" class="io-faq" aria-labelledby="questions-heading"><h2 id="questions-heading">Questions</h2>',
    ])
    for question, answer in entry["faq"]:
        parts.append(f'<h3>{_e(question)}</h3><p>{_e(answer)}</p>')
    parts.extend([
        '</section>',
        '<section class="guide-related" aria-labelledby="related-heading"><p class="eyebrow">MORE ORDERS</p>',
        '<h2 id="related-heading">Another franchise?</h2><div class="guide-related-grid">',
    ])
    for other in in_order.related(slug):
        target = GUIDES[other]
        parts.append(f'<article><h3><a href="{in_order.path(other)}">{_e(target["name"])} in order</a></h3>'
                     f'<p>{_e(target["summary"])}</p></article>')
    parts.extend([
        '</div></section>',
        '<section id="method" class="guide-sources io-method" aria-labelledby="method-heading">',
        '<h2 id="method-heading">How we chose</h2>',
        f'<p>Prepared by OmniTrackr and reviewed by the site owner before publishing. We listed the entries most people mean by '
        f'"{_e(entry["name"])}", checked release years and story placement against public sources, and marked as optional the '
        'side stories that are not needed to follow the main story. The recommended order is editorial opinion: it is the order '
        'we would hand a friend starting from nothing.</p>',
        '<p>Release years are for the first release in the original language. Running times, editions and availability vary by '
        'region. Links go to OmniTrackr title pages, not shops. Your progress is worked out from your own library each time you '
        'open the page; nothing about it is shared.</p>',
        f'<p class="muted">First published {_e(_long_date(FIRST_PUBLISHED))}. Checked {_e(_long_date(reviewed))}. '
        '<a href="/contact">Suggest a franchise or send a correction</a> · <a href="/content-quality">Editorial standards</a> · '
        '<a href="/if-you-liked">If you liked guides</a></p></section></article>',
    ])
    return "".join(parts)


def _structured(slug: str, entry: dict) -> dict:
    url = SITE + in_order.path(slug)
    order = entry["orders"][0]
    by_id = in_order.entries(entry)
    return {
        "@context": "https://schema.org", "@type": "Article",
        "headline": f"{entry['name']} in order", "description": entry["summary"],
        "datePublished": FIRST_PUBLISHED, "dateModified": entry["reviewed"],
        "mainEntityOfPage": url, "url": url, "inLanguage": "en-US",
        "author": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/about"},
        "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/"},
        "about": {"@type": "CreativeWorkSeries", "name": entry["name"]},
        "mainEntity": {"@type": "ItemList", "name": order["name"], "itemListOrder": "https://schema.org/ItemListOrderAscending",
                       "numberOfItems": len(order["ids"]), "itemListElement": [
                           {"@type": "ListItem", "position": index, "name": by_id[item_id]["title"],
                            "url": f"{url}#{in_order.anchor_id(by_id[item_id])}"}
                           for index, item_id in enumerate(order["ids"], 1)
                       ]},
    }


@router.get(in_order.BASE_PATH, include_in_schema=False)
def in_order_index(request: Request):
    cards = []
    for slug, entry in GUIDES.items():
        names = " · ".join(order["name"] for order in entry["orders"])
        cards.append(
            f'<li><a class="io-card" href="{in_order.path(slug)}"><span class="io-card__initial" aria-hidden="true">{_e(entry["name"].removeprefix("The ")[:1])}</span>'
            f'<span class="io-card__text"><strong>{_e(entry["name"])} in order</strong>'
            f'<span>{len(entry["entries"])} entries across {_e(_formats_text(entry))}</span>'
            f'<span class="io-card__orders">{_e(names)}</span></span></a></li>'
        )
    content = (
        '<header class="hero"><p class="eyebrow">IN ORDER</p><h1>Every franchise, in the right order.</h1>'
        '<p>Release order, story order, or the order that keeps every twist intact? Guides to the best way through '
        'the biggest franchises, across films, series, anime, books and games, with what you can safely skip.</p></header>'
        f'<ul class="io-cards">{"".join(cards)}</ul>'
        '<section class="editorial io-why"><h2>Why the order matters</h2><p>Stories that grow over decades are rarely told in order. '
        'Prequels arrive after the endings they lead to, books and their adaptations disagree, and a twist that floored the first '
        'audience can be spoiled by watching the "right" way on paper. Each guide gives more than one order, says who each one suits, '
        'and recommends one.</p><p>Members of OmniTrackr see their own progress on every guide: which entries they have finished, '
        'which are on their list, and what to start next. <a href="/if-you-liked">If you liked</a> guides cover what to try after '
        'something you loved.</p></section>'
    )
    structured = {
        "@context": "https://schema.org", "@type": "CollectionPage", "name": HUB_TITLE, "description": HUB_DESCRIPTION,
        "url": SITE + in_order.BASE_PATH, "inLanguage": "en-US",
        "isPartOf": {"@type": "WebSite", "name": "OmniTrackr", "url": SITE + "/"},
        "mainEntity": {"@type": "ItemList", "itemListElement": [
            {"@type": "ListItem", "position": index, "name": f"{entry['name']} in order", "url": SITE + in_order.path(slug)}
            for index, (slug, entry) in enumerate(GUIDES.items(), 1)
        ]},
    }
    response = page(HUB_TITLE, HUB_DESCRIPTION, in_order.BASE_PATH, content, structured_data=structured,
                    head=f'<link rel="stylesheet" href="/static/in-order.css?v={CSS_VERSION}">')
    response.headers["Cache-Control"] = "public, max-age=600"
    return response


@router.get(in_order.BASE_PATH + "/{slug}", include_in_schema=False)
def in_order_guide(slug: str, request: Request, db: Session = Depends(get_db)):
    entry = in_order.guide(slug)
    if entry is None:
        raise HTTPException(404, "Guide not found")
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    content = guide_content(slug, entry, _details(db), signed_in)
    response = page(entry["search_title"], entry["summary"], in_order.path(slug), content,
                    structured_data=_structured(slug, entry), head=_head(signed_in, ads=True))
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


@router.get("/api/in-order/{slug}/progress")
def in_order_progress(slug: str, request: Request, response: Response,
                      user=Depends(get_current_user), db: Session = Depends(get_db)):
    """How far through a franchise the member is, read from their own library."""
    response.headers["Cache-Control"] = "private, no-store"
    entry = in_order.guide(slug)
    if entry is None:
        raise HTTPException(404, "Guide not found")
    return in_order.progress(db, user.id, entry)


class InOrderAdd(BaseModel):
    ids: list[str] = Field(..., min_length=1, max_length=MAX_ADD)


@router.post("/api/in-order/{slug}/add")
def in_order_add(slug: str, payload: InOrderAdd, request: Request, response: Response,
                 user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Add entries from a guide to the member's library as not started (title, year and creator only)."""
    response.headers["Cache-Control"] = "private, no-store"
    entry = in_order.guide(slug)
    if entry is None:
        raise HTTPException(404, "Guide not found")
    known = in_order.entries(entry)
    if any(item_id not in known for item_id in payload.ids):
        raise HTTPException(404, "Entry not found")
    lock_progress_owner(db, user.id)
    details = _details(db)
    added, existing = in_order.add_entries(db, user, entry, payload.ids,
                                           image_for=lambda fields: details.get(fields["id"], {}).get("image"))
    db.commit()
    if added:
        funnel.record("order_saved", request)
    return {"added": added, "existing": existing, "progress": in_order.progress(db, user.id, entry)}
