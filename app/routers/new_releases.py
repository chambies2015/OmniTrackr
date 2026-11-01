"""Public release guides (/new-releases and /new-releases/<slug>).

Release Radar lists every date; these pages say which releases we think are
worth planning around, format by format, and what to catch up on first. Pages
read completely without scripts or an account. Saving a pick works exactly as on
the "If you liked" and best-of guides (and reuses their script): members add it
through POST /api/pick/add, visitors keep it in their browser-only guest list.
"""
from __future__ import annotations

from datetime import date, datetime
from html import escape
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import new_releases, title_pages
from ..auth import AUTH_COOKIE_NAME
from ..dependencies import get_db
from ..release_guides import GUIDES
from .best_of import CSS_VERSION as BEST_OF_CSS_VERSION
from .discover import page
from .if_you_liked import CSS_VERSION as LIKED_CSS_VERSION, GUEST_LIST_JS, JS_VERSION as LIKED_JS_VERSION, _details, _save_button

router = APIRouter(tags=["new-releases"])
CSS_VERSION = "20261101-releases-1"
SITE = "https://omnitrackr.xyz"
HUB_TITLE = "Release guides: the new movies, shows, games, anime and books worth your time"
HUB_DESCRIPTION = ("Month-by-month guides to new releases across movies, TV, games, anime and books, "
                   "with what we'd plan around, who should wait for reviews and what to catch up on first.")


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _paragraphs(values) -> str:
    return "".join(f"<p>{_e(value)}</p>" for value in values)


def _long_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%B %d, %Y").replace(" 0", " ")


def _today() -> date:
    return datetime.utcnow().date()


def _meta_line(item: dict) -> str:
    parts = [title_pages.KINDS[item["kind"]][3]]
    if item["creator"]:
        parts.append(item["creator"])
    return " · ".join(parts)


def _when(item: dict, today: date) -> str:
    if new_releases.is_out(item, today):
        return '<span class="nr-when nr-when--out">Out now</span>'
    return f'<span class="nr-when">Out {_e(new_releases.date_label(item))}</span>'


def _pick_html(item: dict, details: dict, signed_in: bool, today: date) -> str:
    entry = new_releases.pool_entry(item)
    detail = details.get(entry["id"], {}) if entry else {}
    image = title_pages._safe_image(detail.get("image"))
    art = (f'<img class="yl-pick__art" src="{_e(image)}" alt="" width="96" height="144" loading="lazy" '
           'decoding="async" referrerpolicy="no-referrer">' if image else "")
    title_link = (f'<a class="yl-pick__link" href="{_e(detail["url"])}">See the title page</a>'
                  if detail.get("url") else "")
    save = _save_button(entry, signed_in) if entry else ""
    first = (f'<p class="nr-first"><strong>Before it arrives:</strong> {_e(item["first"])}'
             + (f' <a href="{_e(item["first_link"])}">{_e(item["first_label"])}</a>' if item.get("first_link") else "")
             + '</p>') if item.get("first") else ""
    return (
        f'<article class="pick yl-pick bo-pick nr-pick" id="{_e(new_releases.anchor_id(item))}">'
        f'<div class="yl-pick__head">{art}<div><p class="eyebrow">{_e(_meta_line(item))}</p>'
        f'<h3>{_e(item["title"])}</h3><p class="bo-pick__released">{_when(item, today)} {_e(item["released"])}</p></div></div>'
        f'<p class="yl-pick__why">{_e(item["why"])}</p><p>{_e(item["note"])}</p>{first}'
        f'<p class="caveat">{_e(item["caveat"])}</p>'
        f'<div class="yl-pick__actions">{save}{title_link}</div>'
        '<p class="yl-pick__status" data-liked-status role="status" aria-live="polite"></p></article>'
    )


def _guest_bar(signed_in: bool) -> str:
    if signed_in:
        return ""
    return ('<div class="yl-bar" data-guest-bar hidden><p class="yl-bar__count" data-guest-count role="status" aria-live="polite"></p>'
            '<a class="button" href="/#signup" data-liked-signup>Save my list, free →</a></div>')


def _styles() -> str:
    return (f'<link rel="stylesheet" href="/static/if-you-liked.css?v={LIKED_CSS_VERSION}">'
            f'<link rel="stylesheet" href="/static/best-of.css?v={BEST_OF_CSS_VERSION}">'
            f'<link rel="stylesheet" href="/static/new-releases.css?v={CSS_VERSION}">')


def _head(signed_in: bool) -> str:
    head = _styles()
    if not signed_in:
        head += f'<script src="{GUEST_LIST_JS}" defer></script>'
    head += f'<script src="/static/if-you-liked.js?v={LIKED_JS_VERSION}" defer></script>'
    if not signed_in:
        head += '<script src="/static/ad-loader.js" defer></script>'
    return head


def _source_link(label: str, url: str) -> str:
    host = urlsplit(url).hostname or ""
    return (f'<li><a href="{_e(url)}" rel="noopener" target="_blank">{_e(label)}</a>'
            f' <span class="muted">({_e(host.removeprefix("www."))})</span></li>')


def _section_id(section: dict) -> str:
    return "section-" + section["format"]


def guide_content(slug: str, entry: dict, details: dict, signed_in: bool, today: date) -> str:
    reviewed = entry["reviewed"]
    jump = [f'<a href="#{_section_id(section)}">{_e(new_releases.FORMAT_LABELS[section["format"]])}</a>'
            for section in entry["sections"]]
    if entry["also"]:
        jump.append('<a href="#also">Also on the calendar</a>')
    jump += ['<a href="#plan">Plan it</a>', '<a href="#method">How we chose</a>']
    total = len(new_releases.picks(entry))
    parts = [
        '<article class="trail-guide yl-guide bo-guide nr-guide">',
        f'<header class="hero hero--guide"><a href="{new_releases.BASE_PATH}">← Every release guide</a>',
        f'<p class="eyebrow">RELEASE GUIDE · {_e(entry["period"].upper())}</p>',
        f'<h1>{_e(entry["name"])}</h1><p class="guide-deck">{_e(entry["summary"])}</p>',
        '<p class="guide-byline">By <a href="/about">OmniTrackr</a> · Checked ',
        f'<time datetime="{_e(reviewed)}">{_e(_long_date(reviewed))}</time></p>',
        f'<nav class="guide-jump" aria-label="On this page">{"".join(jump)}</nav></header>',
        f'<div class="guide-intro">{_paragraphs(entry["lead"])}</div>',
        f'<p class="nr-count">{total} releases across {len(entry["sections"])} formats. Each one says when and where it '
        'comes out, why it is on our list, what to catch up on first, and one thing to know before you commit.'
        + ('' if signed_in else ' Save any of them to a list, no account needed, and we will keep it for you if you sign up.') + '</p>',
    ]
    for section in entry["sections"]:
        label = new_releases.FORMAT_LABELS[section["format"]]
        parts.append(f'<section id="{_section_id(section)}" class="nr-section" aria-labelledby="{_section_id(section)}-heading">'
                     f'<p class="eyebrow">{_e(label.upper())}</p><h2 id="{_section_id(section)}-heading">{_e(section["heading"])}</h2>'
                     f'<div class="yl-section-intro">{_paragraphs(section["intro"])}</div><div class="picks yl-picks">')
        for item in section["picks"]:
            parts.append(_pick_html(item, details, signed_in, today))
        parts.append('</div></section>')
    parts.append(_guest_bar(signed_in))
    if entry["also"]:
        parts.append('<section id="also" class="editorial bo-also" aria-labelledby="also-heading">'
                     '<h2 id="also-heading">Also on the calendar</h2><ul>')
        for title, text in entry["also"]:
            parts.append(f'<li><strong>{_e(title)}</strong> {_e(text)}</li>')
        parts.append('</ul></section>')
    parts.extend([
        f'<section id="plan" class="editorial yl-start"><h2>{_e(entry["plan_heading"])}</h2>', _paragraphs(entry["plan"]),
        '<p>Release dates still move, sometimes by a week and sometimes by a year. <a href="/release-radar">Release Radar</a> '
        'keeps every date current, and members who track an upcoming title get a note the day it comes out. '
        '<a href="/#signup">Start a free library</a> if you would like that.</p></section>',
        '<section class="guide-related" aria-labelledby="related-heading"><p class="eyebrow">MORE GUIDES</p>',
        '<h2 id="related-heading">Keep reading</h2><div class="guide-related-grid">',
    ])
    for other, target in new_releases.published(today).items():
        if other != slug:
            parts.append(f'<article><h3><a href="{_e(new_releases.path(other))}">{_e(target["name"])}</a></h3>'
                         f'<p>{_e(target["summary"])}</p></article>')
    for label, href in entry["related"]:
        parts.append(f'<article><h3><a href="{_e(href)}">{_e(label)}</a></h3></article>')
    parts.extend([
        '</div></section>',
        '<section id="method" class="guide-sources yl-method" aria-labelledby="method-heading">',
        '<h2 id="method-heading">How we chose</h2>',
        '<p>Prepared by OmniTrackr with AI assistance and reviewed by the site owner before publishing. Most of these '
        'releases were not out when we wrote about them, so read this as a guide to what is worth '
        'planning around. We picked from the dated releases on the calendars and studio announcements listed below, left out '
        'anything without a firm date, and chose the ones we would point a friend towards, with an honest note on who '
        'should wait for reviews. The opinions are ours.</p>',
        '<p>Nothing here is sponsored, and nobody paid to be included. Dates are for the US unless we say otherwise, and '
        'they can change; when one moves, we update the page and the date at the top. Links in the list go to OmniTrackr '
        'title pages, not shops.</p>',
        f'<h3>Sources we checked</h3><ul class="bo-sources">{"".join(_source_link(label, url) for label, url in entry["sources"])}</ul>',
        f'<p class="muted">First published {_e(_long_date(entry["published"]))}. Checked {_e(_long_date(reviewed))}. '
        '<a href="/contact">Suggest a release or send a correction</a> · <a href="/content-quality">Editorial standards</a> · '
        '<a href="/release-radar">Release Radar</a></p></section></article>',
    ])
    return "".join(parts)


def _structured(slug: str, entry: dict) -> dict:
    url = SITE + new_releases.path(slug)
    items = new_releases.picks(entry)
    return {
        "@context": "https://schema.org", "@type": "Article",
        "headline": entry["name"], "description": entry["summary"],
        "datePublished": entry["published"], "dateModified": entry["reviewed"],
        "mainEntityOfPage": url, "url": url, "inLanguage": "en-US",
        "author": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/about"},
        "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/"},
        "mainEntity": {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": [
            {"@type": "ListItem", "position": index, "name": item["title"], "url": f"{url}#{new_releases.anchor_id(item)}"}
            for index, item in enumerate(items, 1)
        ]},
    }


@router.get(new_releases.BASE_PATH, include_in_schema=False)
def release_guides_index():
    today = _today()
    live = new_releases.published(today)
    current = new_releases.current(today)
    cards = []
    for slug, entry in live.items():
        titles = " · ".join(item["title"] for item in new_releases.picks(entry)[:4])
        label = "This month" if slug == current else entry["period"]
        cards.append(
            f'<li><a class="yl-card bo-card" href="{_e(new_releases.path(slug))}">'
            f'<span class="yl-card__art"><span class="yl-card__initial" aria-hidden="true">{_e(entry["period"][:1])}</span></span>'
            f'<span class="yl-card__text"><span class="nr-card__label">{_e(label)}</span><strong>{_e(entry["name"])}</strong>'
            f'<span>{len(new_releases.picks(entry))} releases, including {_e(titles)}</span></span></a></li>'
        )
    content = (
        '<header class="hero"><p class="eyebrow">RELEASE GUIDES</p><h1>What is coming out, and what is worth it</h1>'
        '<p>Release calendars tell you everything that comes out. These guides tell you which releases we would plan an '
        'evening or a weekend around, format by format, and what to watch, play or read first so you arrive ready. '
        'Each one is dated, names its sources and says honestly who should wait for the reviews.</p></header>'
        f'<section class="yl-group" aria-labelledby="nr-guides"><h2 id="nr-guides">The guides</h2>'
        f'<ul class="yl-cards">{"".join(cards)}</ul></section>'
        '<section class="editorial yl-why"><h2>How these guides work</h2><p>We write each guide just before its stretch of '
        'the calendar begins, from release dates the studios, publishers and networks have announced. Most of the picks '
        'are not out yet when we write about them, so these are not reviews. They are the releases we think deserve a '
        'place in your plans, with a fair warning for each one.</p><p>Dates move, so we check them again during the month '
        'and the date at the top of each guide says when. For the full calendar, day by day, see '
        '<a href="/release-radar">Release Radar</a>. For the year\'s releases that have already proved themselves, see '
        '<a href="/best-of">the best of 2026</a>, and for older picks to fill the gaps, '
        '<a href="/discover">Discover</a> and the <a href="/if-you-liked">If you liked</a> guides.</p></section>'
    )
    structured = {
        "@context": "https://schema.org", "@type": "CollectionPage", "name": HUB_TITLE, "description": HUB_DESCRIPTION,
        "url": SITE + new_releases.BASE_PATH, "inLanguage": "en-US",
        "isPartOf": {"@type": "WebSite", "name": "OmniTrackr", "url": SITE + "/"},
        "mainEntity": {"@type": "ItemList", "itemListElement": [
            {"@type": "ListItem", "position": index, "name": entry["name"], "url": SITE + new_releases.path(slug)}
            for index, (slug, entry) in enumerate(live.items(), 1)
        ]},
    }
    response = page(HUB_TITLE, HUB_DESCRIPTION, new_releases.BASE_PATH, content, structured_data=structured, head=_styles())
    response.headers["Cache-Control"] = "public, max-age=600"
    return response


@router.get(new_releases.BASE_PATH + "/{slug}", include_in_schema=False)
def release_guide(slug: str, request: Request, db: Session = Depends(get_db)):
    today = _today()
    if slug not in new_releases.published(today):
        raise HTTPException(404, "Guide not found")
    entry = GUIDES[slug]
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    content = guide_content(slug, entry, _details(db), signed_in, today)
    response = page(entry["search_title"], entry["summary"], new_releases.path(slug), content,
                    structured_data=_structured(slug, entry), head=_head(signed_in))
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response
