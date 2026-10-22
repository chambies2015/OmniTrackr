"""Public "Best of the year" guides (/best-of and /best-of/<year>/<format>).

One hand-written list per format and year, updated as the year goes on. Pages
read completely without scripts or an account. Saving a pick works exactly as on
the "If you liked" guides (and reuses their script): members add it through
POST /api/pick/add, visitors keep it in their browser-only guest list.
"""
from __future__ import annotations

from datetime import date
from html import escape
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import best_of, title_pages
from ..auth import AUTH_COOKIE_NAME
from ..best_of_guides import GUIDES
from ..dependencies import get_db
from .discover import page
from .if_you_liked import CSS_VERSION as LIKED_CSS_VERSION, GUEST_LIST_JS, JS_VERSION as LIKED_JS_VERSION, _details, _save_button

router = APIRouter(tags=["best-of"])
CSS_VERSION = "20261022-best-of-1"
SITE = "https://omnitrackr.xyz"
FIRST_PUBLISHED = "2026-10-22"
HUB_TITLE = "The best movies, TV, anime, games and books of the year"
HUB_DESCRIPTION = ("Hand-picked lists of the best new movies, TV shows, anime, video games and books of 2026, "
                   "with where each came out, why it made the list and what to know first.")
FORMAT_LABELS = {"movies": "Movies", "tv": "TV shows", "anime": "Anime", "games": "Games", "books": "Books"}


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _paragraphs(values) -> str:
    return "".join(f"<p>{_e(value)}</p>" for value in values)


def _long_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%B %d, %Y").replace(" 0", " ")


def _meta_line(item: dict) -> str:
    parts = [title_pages.KINDS[item["kind"]][3]]
    if item["creator"]:
        parts.append(item["creator"])
    return " · ".join(parts)


def _pick_html(index: int, item: dict, details: dict, signed_in: bool) -> str:
    entry = best_of.pool_entry(item)
    detail = details.get(entry["id"], {}) if entry else {}
    image = title_pages._safe_image(detail.get("image"))
    art = (f'<img class="yl-pick__art" src="{_e(image)}" alt="" width="96" height="144" loading="lazy" '
           'decoding="async" referrerpolicy="no-referrer">' if image else "")
    title_link = (f'<a class="yl-pick__link" href="{_e(detail["url"])}">See the title page</a>'
                  if detail.get("url") else "")
    save = _save_button(entry, signed_in) if entry else ""
    anchor_id = "pick-" + title_pages.slugify(item["title"])
    return (
        f'<article class="pick yl-pick bo-pick" id="{_e(anchor_id)}">'
        f'<div class="yl-pick__head">{art}<div><p class="eyebrow">{index:02d} / {_e(_meta_line(item))}</p>'
        f'<h3>{_e(item["title"])}</h3><p class="bo-pick__released">{_e(item["released"])}</p></div></div>'
        f'<p class="yl-pick__why">{_e(item["why"])}</p><p>{_e(item["note"])}</p>'
        f'<p class="caveat">{_e(item["caveat"])}</p>'
        f'<div class="yl-pick__actions">{save}{title_link}</div>'
        '<p class="yl-pick__status" data-liked-status role="status" aria-live="polite"></p></article>'
    )


def _guest_bar(signed_in: bool) -> str:
    if signed_in:
        return ""
    return ('<div class="yl-bar" data-guest-bar hidden><p class="yl-bar__count" data-guest-count role="status" aria-live="polite"></p>'
            '<a class="button" href="/#signup" data-liked-signup>Save my list, free →</a></div>')


def _head(signed_in: bool) -> str:
    head = (f'<link rel="stylesheet" href="/static/if-you-liked.css?v={LIKED_CSS_VERSION}">'
            f'<link rel="stylesheet" href="/static/best-of.css?v={CSS_VERSION}">')
    if not signed_in:
        head += f'<script src="{GUEST_LIST_JS}" defer></script>'
    head += f'<script src="/static/if-you-liked.js?v={LIKED_JS_VERSION}" defer></script>'
    if not signed_in:
        head += '<script src="/static/ad-loader.js" defer></script>'
    return head


def _format_nav(slug: str) -> str:
    entry = GUIDES[slug]
    links = []
    for other in best_of.for_year(entry["year"]):
        label = _e(FORMAT_LABELS[GUIDES[other]["format"]])
        if other == slug:
            links.append(f'<span aria-current="page">{label}</span>')
        else:
            links.append(f'<a href="{_e(best_of.path(other))}">{label}</a>')
    return (f'<nav class="bo-formats" aria-label="Best of {entry["year"]} by format">'
            f'<span class="bo-formats__label">Best of {entry["year"]}:</span>{"".join(links)}</nav>')


def _source_link(label: str, url: str) -> str:
    host = urlsplit(url).hostname or ""
    return (f'<li><a href="{_e(url)}" rel="noopener" target="_blank">{_e(label)}</a>'
            f' <span class="muted">({_e(host.removeprefix("www."))})</span></li>')


def guide_content(slug: str, entry: dict, details: dict, signed_in: bool) -> str:
    reviewed = entry["reviewed"]
    year = entry["year"]
    jump = ['<a href="#picks">The list</a>']
    if entry["also"]:
        jump.append('<a href="#also">Also worth a look</a>')
    if entry["coming"]:
        jump.append('<a href="#coming">Still to come</a>')
    jump += ['<a href="#where-to-start">Where to start</a>', '<a href="#method">How we chose</a>']
    parts = [
        '<article class="trail-guide yl-guide bo-guide">',
        f'<header class="hero hero--guide"><a href="{best_of.BASE_PATH}">← Every best-of list</a>',
        f'<p class="eyebrow">BEST OF {year} · {_e(FORMAT_LABELS[entry["format"]].upper())}</p>',
        f'<h1>{_e(entry["name"])}</h1><p class="guide-deck">{_e(entry["summary"])}</p>',
        '<p class="guide-byline">By <a href="/about">OmniTrackr</a> · Updated ',
        f'<time datetime="{_e(reviewed)}">{_e(_long_date(reviewed))}</time></p>',
        f'<nav class="guide-jump" aria-label="On this page">{"".join(jump)}</nav></header>',
        _format_nav(slug),
        f'<div class="guide-intro">{_paragraphs(entry["lead"])}</div>',
        '<section id="picks" aria-labelledby="picks-heading"><p class="eyebrow">THE LIST</p>',
        f'<h2 id="picks-heading">{len(entry["picks"])} picks from {year}</h2>',
        '<p class="yl-section-intro">Each pick says where and when it came out, why it made the list, and one thing to know '
        'before you start.' + ('' if signed_in else ' Save any of them to a list, no account needed.') + '</p>',
        '<div class="picks yl-picks">',
    ]
    for index, item in enumerate(entry["picks"], 1):
        parts.append(_pick_html(index, item, details, signed_in))
    parts.append('</div></section>')
    parts.append(_guest_bar(signed_in))
    if entry["also"]:
        parts.append('<section id="also" class="editorial bo-also" aria-labelledby="also-heading">'
                     '<h2 id="also-heading">Also worth a look</h2><ul>')
        for title, text in entry["also"]:
            parts.append(f'<li><strong>{_e(title)}</strong> {_e(text)}</li>')
        parts.append('</ul></section>')
    if entry["coming"]:
        parts.append(f'<section id="coming" class="editorial bo-coming" aria-labelledby="coming-heading">'
                     f'<h2 id="coming-heading">Still to come in {year}</h2>{_paragraphs(entry["coming"])}'
                     '<p>Want to know what is out this week? <a href="/release-radar">Release Radar</a> lists new movies, '
                     'TV premieres, the anime season and upcoming games.</p></section>')
    parts.extend([
        '<section id="where-to-start" class="editorial yl-start"><h2>Where to start</h2>', _paragraphs(entry["start"]),
        f'<p>Members who track what they finish get their own year in review each December, with the titles they rated '
        f'highest in {year}. <a href="/#signup">Start a free library</a> if you would like one.</p></section>',
        '<section class="guide-related" aria-labelledby="related-heading"><p class="eyebrow">MORE GUIDES</p>',
        '<h2 id="related-heading">Keep reading</h2><div class="guide-related-grid">',
    ])
    for other in best_of.for_year(year):
        if other != slug:
            target = GUIDES[other]
            parts.append(f'<article><h3><a href="{_e(best_of.path(other))}">{_e(target["name"])}</a></h3>'
                         f'<p>{_e(target["summary"])}</p></article>')
    for label, href in entry["related"]:
        parts.append(f'<article><h3><a href="{_e(href)}">{_e(label)}</a></h3></article>')
    parts.extend([
        '</div></section>',
        '<section id="method" class="guide-sources yl-method" aria-labelledby="method-heading">',
        '<h2 id="method-heading">How we chose</h2>',
        f'<p>Prepared by OmniTrackr and reviewed by the site owner before publishing. We started from the {_e(FORMAT_LABELS[entry["format"]].lower())} '
        f'released in {year} that critics and audiences kept coming back to, then chose the ones we would recommend to a friend, '
        'across genres, with a fair caveat for each. Release dates, platforms and scores were checked against the public sources '
        'below; the opinions are our own.</p>',
        '<p>These picks are not sponsored, and nobody paid to be included. Scores change as more reviews come in, and release '
        'dates and availability vary by region. Links in the list go to OmniTrackr title pages, not shops.</p>',
        f'<h3>Sources we checked</h3><ul class="bo-sources">{"".join(_source_link(label, url) for label, url in entry["sources"])}</ul>',
        f'<p class="muted">First published {_e(_long_date(FIRST_PUBLISHED))}. Checked {_e(_long_date(reviewed))}. '
        '<a href="/contact">Suggest a pick or send a correction</a> · <a href="/content-quality">Editorial standards</a> · '
        '<a href="/pick">Pick for me</a></p></section></article>',
    ])
    return "".join(parts)


def _structured(slug: str, entry: dict) -> dict:
    url = SITE + best_of.path(slug)
    return {
        "@context": "https://schema.org", "@type": "Article",
        "headline": entry["name"], "description": entry["summary"],
        "datePublished": FIRST_PUBLISHED, "dateModified": entry["reviewed"],
        "mainEntityOfPage": url, "url": url, "inLanguage": "en-US",
        "author": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/about"},
        "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/"},
        "mainEntity": {"@type": "ItemList", "numberOfItems": len(entry["picks"]), "itemListElement": [
            {"@type": "ListItem", "position": index, "name": item["title"],
             "url": f"{url}#pick-{title_pages.slugify(item['title'])}"}
            for index, item in enumerate(entry["picks"], 1)
        ]},
    }


@router.get(best_of.BASE_PATH, include_in_schema=False)
def best_of_index():
    sections = []
    for year in best_of.years():
        cards = []
        for slug in best_of.for_year(year):
            entry = GUIDES[slug]
            titles = " · ".join(item["title"] for item in entry["picks"][:4])
            cards.append(
                f'<li><a class="yl-card bo-card" href="{_e(best_of.path(slug))}">'
                f'<span class="yl-card__art"><span class="yl-card__initial" aria-hidden="true">{_e(FORMAT_LABELS[entry["format"]][:1])}</span></span>'
                f'<span class="yl-card__text"><strong>{_e(entry["name"])}</strong>'
                f'<span>{len(entry["picks"])} picks, including {_e(titles)}</span></span></a></li>'
            )
        sections.append(f'<section class="yl-group" aria-labelledby="bo-{year}"><h2 id="bo-{year}">Best of {year}</h2>'
                        f'<ul class="yl-cards">{"".join(cards)}</ul></section>')
    content = (
        '<header class="hero"><p class="eyebrow">BEST OF THE YEAR</p><h1>The best of the year, one format at a time</h1>'
        '<p>Short, opinionated lists of the year\'s best new movies, TV shows, anime, games and books. Each pick says where '
        'and when it came out, why it made the list and what might put you off, and every list names the reviews and '
        'listings we checked.</p></header>'
        + "".join(sections)
        + '<section class="editorial yl-why"><h2>How these lists work</h2><p>We publish each year\'s lists in the autumn and '
          'keep updating them until the year is over, so a late release can still make the cut. The date at the top of '
          'each list says when it was last checked. Nothing on these lists is sponsored.</p><p>Looking for something older? '
          'The <a href="/if-you-liked">If you liked</a> guides start from a favourite and suggest what to try next, and '
          '<a href="/pick">Pick for me</a> suggests one title at a time from every guide on the site.</p></section>'
    )
    structured = {
        "@context": "https://schema.org", "@type": "CollectionPage", "name": HUB_TITLE, "description": HUB_DESCRIPTION,
        "url": SITE + best_of.BASE_PATH, "inLanguage": "en-US",
        "isPartOf": {"@type": "WebSite", "name": "OmniTrackr", "url": SITE + "/"},
        "mainEntity": {"@type": "ItemList", "itemListElement": [
            {"@type": "ListItem", "position": index, "name": GUIDES[slug]["name"], "url": SITE + best_of.path(slug)}
            for index, slug in enumerate((slug for year in best_of.years() for slug in best_of.for_year(year)), 1)
        ]},
    }
    response = page(HUB_TITLE, HUB_DESCRIPTION, best_of.BASE_PATH, content, structured_data=structured,
                    head=(f'<link rel="stylesheet" href="/static/if-you-liked.css?v={LIKED_CSS_VERSION}">'
                          f'<link rel="stylesheet" href="/static/best-of.css?v={CSS_VERSION}">'))
    response.headers["Cache-Control"] = "public, max-age=600"
    return response


@router.get(best_of.BASE_PATH + "/{year}", include_in_schema=False)
def best_of_year(year: int):
    if year not in best_of.years():
        raise HTTPException(404, "No best-of lists for that year")
    return RedirectResponse(f"{best_of.BASE_PATH}#bo-{year}", status_code=301)


@router.get(best_of.BASE_PATH + "/{year}/{fmt}", include_in_schema=False)
def best_of_guide(year: int, fmt: str, request: Request, db: Session = Depends(get_db)):
    slug = best_of.find(year, fmt)
    if slug is None:
        raise HTTPException(404, "Guide not found")
    entry = GUIDES[slug]
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    content = guide_content(slug, entry, _details(db), signed_in)
    response = page(entry["search_title"], entry["summary"], best_of.path(slug), content,
                    structured_data=_structured(slug, entry), head=_head(signed_in))
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response
