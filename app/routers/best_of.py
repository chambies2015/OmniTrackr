"""Public "Best of the year" guides (/best-of and /best-of/<year>/<format>).

One hand-written list per format and year, updated as the year goes on. Pages
read completely without scripts or an account. Saving a pick works exactly as on
the "If you liked" guides (and reuses their script): members add it through
POST /api/pick/add, visitors keep it in their browser-only guest list. Manga,
podcast and audiobook picks are not in Pick for me, so members save those through
POST /api/best-of/add instead (the button carries the endpoint).

Signed-in members also see which picks they already have: each pick says so, and
the hub counts how many of the year's picks they have finished. Nothing is stored.
"""
from __future__ import annotations

from datetime import date
from html import escape
from typing import Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import affiliate, best_of, browse, funnel, title_pages, title_search
from ..best_of_guides import GUIDES, YEARS
from ..dependencies import get_current_user, get_db, get_optional_current_user
from ..progress import lock_progress_owner
from .discover import page
from .if_you_liked import CSS_VERSION as LIKED_CSS_VERSION, GUEST_LIST_JS, JS_VERSION as LIKED_JS_VERSION, _details, _save_button

router = APIRouter(tags=["best-of"])
CSS_VERSION = "20261109-best-of-2"
SITE = "https://omnitrackr.xyz"
FIRST_PUBLISHED = "2026-10-22"
HUB_TITLE = "The best of 2026: movies, TV, anime, games, books, music, manga, podcasts and audiobooks"
HUB_DESCRIPTION = ("Hand-picked lists of the best new movies, TV shows, anime, video games, books, albums, manga, podcasts "
                   "and audiobooks of 2026, with where each came out, why it made the list and what to know first.")
FORMAT_LABELS = {"movies": "Movies", "tv": "TV shows", "anime": "Anime", "games": "Games", "books": "Books",
                 "music": "Albums", "manga": "Manga", "podcasts": "Podcasts", "audiobooks": "Audiobooks"}
# Formats that get one Amazon search link per pick. TV and anime picks live on streaming services, and
# podcasts are free, so those link to the title page (and, for podcasts, the show's own page) only.
SHOP_FORMATS = {"movies", "games", "books", "music", "manga", "audiobooks"}
COMPLETE_WORDS = {"movie": "Watched", "tv": "Watched", "anime": "Watched", "game": "Played", "book": "Read",
                  "album": "Listened", "manga": "Read", "podcast": "Listened", "audiobook": "Listened"}


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _paragraphs(values) -> str:
    return "".join(f"<p>{_e(value)}</p>" for value in values)


def _long_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%B %d, %Y").replace(" 0", " ")




def _hours(value) -> str:
    hours, minutes = divmod(round(float(value) * 60), 60)
    return f"{hours} hr {minutes} min" if minutes else f"{hours} hr"


def _meta_line(item: dict) -> str:
    parts = [title_pages.KINDS[item["kind"]][3]]
    if item["creator"]:
        parts.append(item["creator"])
    extra = item.get("extra") or {}
    if extra.get("narrator"):
        parts.append(f"read by {extra['narrator']}")
    if extra.get("length_hours"):
        parts.append(_hours(extra["length_hours"]))
    return " · ".join(parts)


def all_details(db: Session) -> dict:
    """{entry id: {"url", "image"}} for every pick with a public title page, all nine formats (never raises)."""
    details = dict(_details(db))
    try:
        details.update(best_of.extra_details(title_search.index(db)))
    except Exception:
        pass
    return details


def _member_button(entry: dict, state: Optional[str]) -> str:
    if state == "done":
        return f'<span class="bo-owned bo-owned--done">{_e(COMPLETE_WORDS[entry["kind"]])} ✓</span>'
    if state == "tracked":
        return '<span class="bo-owned">In your library ✓</span>'
    endpoint = ' data-liked-endpoint="/api/best-of/add"' if entry["kind"] in best_of.EXTRA_KINDS else ""
    return (f'<button type="button" class="button yl-save" data-liked-add="{_e(entry["id"])}"{endpoint}>'
            'Add to my library</button>')


def _shop_links(fmt: str, item: dict) -> str:
    links = []
    if item.get("link"):
        label, url = item["link"]
        links.append(f'<a class="bo-out" href="{_e(url)}" target="_blank" rel="noopener">{_e(label)} '
                     '<span aria-hidden="true">↗</span></a>')
    if fmt in SHOP_FORMATS:
        for link in affiliate.links_for(item["kind"], item["title"], item["creator"] or ""):
            links.append(f'<a class="bo-out" href="{_e(link["url"])}" target="_blank" rel="sponsored noopener noreferrer">'
                         f'{_e(link["label"])} <span aria-hidden="true">↗</span></a>')
    return "".join(links)


def _pick_html(index: int, fmt: str, item: dict, details: dict, signed_in: bool, states: Optional[dict] = None) -> str:
    entry = best_of.pool_entry(item)
    detail = details.get(entry["id"], {}) if entry else {}
    image = title_pages._safe_image(detail.get("image"))
    art = (f'<img class="yl-pick__art" src="{_e(image)}" alt="" width="96" height="144" loading="lazy" '
           'decoding="async" referrerpolicy="no-referrer">' if image else "")
    title_link = (f'<a class="yl-pick__link" href="{_e(detail["url"])}">See the title page</a>'
                  if detail.get("url") else "")
    if entry and signed_in and states is not None:
        save = _member_button(entry, states.get(entry["id"]))
    else:
        save = _save_button(entry, signed_in) if entry else ""
        if entry and signed_in and entry["kind"] in best_of.EXTRA_KINDS:
            save = save.replace('data-liked-add=', 'data-liked-endpoint="/api/best-of/add" data-liked-add=', 1)
    return (
        f'<article class="pick yl-pick bo-pick" id="{_e(best_of.anchor(item))}">'
        f'<div class="yl-pick__head">{art}<div><p class="eyebrow">{index:02d} / {_e(_meta_line(item))}</p>'
        f'<h3>{_e(item["title"])}</h3><p class="bo-pick__released">{_e(item["released"])}</p></div></div>'
        f'<p class="yl-pick__why">{_e(item["why"])}</p><p>{_e(item["note"])}</p>'
        f'<p class="caveat">{_e(item["caveat"])}</p>'
        f'<div class="yl-pick__actions">{save}{title_link}{_shop_links(fmt, item)}</div>'
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
            f'<a class="bo-formats__label" href="{best_of.BASE_PATH}">Best of {entry["year"]}:</a>'
            f'<div class="bo-formats__list">{"".join(links)}</div></nav>')


def _source_link(label: str, url: str) -> str:
    host = urlsplit(url).hostname or ""
    return (f'<li><a href="{_e(url)}" rel="noopener" target="_blank">{_e(label)}</a>'
            f' <span class="muted">({_e(host.removeprefix("www."))})</span></li>')


def _member_strip(entry: dict, states: Optional[dict]) -> str:
    """For members: how many of this list's picks they already have."""
    if states is None:
        return ""
    ids = [found["id"] for found in (best_of.pool_entry(item) for item in entry["picks"]) if found]
    done = sum(1 for pick_id in ids if states.get(pick_id) == "done")
    tracked = sum(1 for pick_id in ids if states.get(pick_id) == "tracked")
    if done == len(ids):
        text = f"You have finished all {len(ids)}. Not many people can say that."
    elif done or tracked:
        if not done:
            text = f"Of these {len(ids)}, {tracked} {'is' if tracked == 1 else 'are'} in your library, not finished yet."
        else:
            text = f"Of these {len(ids)}, you have finished {done}"
            if tracked:
                text += f", and {tracked} more {'is' if tracked == 1 else 'are'} in your library"
            text += "."
    else:
        text = f"None of these {len(ids)} are in your library yet. Add the ones you want to get to before the year is out."
    width = round(100 * done / len(ids)) if ids else 0
    return (f'<p class="bo-mine"><span class="bo-mine__bar" aria-hidden="true"><span style="width:{width}%"></span></span>'
            f'<span>{_e(text)}</span></p>')


def guide_content(slug: str, entry: dict, details: dict, signed_in: bool, states: Optional[dict] = None) -> str:
    reviewed = entry["reviewed"]
    year = entry["year"]
    fmt = entry["format"]
    jump = ['<a href="#picks">The list</a>']
    if entry["also"]:
        jump.append('<a href="#also">Also worth a look</a>')
    if entry["coming"]:
        jump.append('<a href="#coming">Still to come</a>')
    jump += ['<a href="#where-to-start">Where to start</a>', '<a href="#method">How we chose</a>']
    shop = fmt in SHOP_FORMATS and affiliate.affiliate_enabled()
    parts = [
        f'<article class="trail-guide yl-guide bo-guide" data-bo-format="{_e(fmt)}">',
        f'<header class="hero hero--guide"><a href="{best_of.BASE_PATH}">← Every best-of list</a>',
        f'<p class="eyebrow">BEST OF {year} · {_e(FORMAT_LABELS[fmt].upper())}</p>',
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
        _member_strip(entry, states),
        '<div class="picks yl-picks">',
    ]
    for index, item in enumerate(entry["picks"], 1):
        parts.append(_pick_html(index, fmt, item, details, signed_in, states))
    parts.append('</div></section>')
    parts.append(_guest_bar(signed_in))
    if entry["also"]:
        parts.append('<section id="also" class="editorial bo-also" aria-labelledby="also-heading">'
                     '<h2 id="also-heading">Also worth a look</h2><ul>')
        for title, text in entry["also"]:
            parts.append(f'<li><strong>{_e(title)}</strong> {_e(text)}</li>')
        parts.append('</ul></section>')
    if entry["coming"]:
        radar = ('<p>Want to know what is out this week? <a href="/release-radar">Release Radar</a> lists new movies, '
                 'TV premieres, the anime season and upcoming games, and our <a href="/new-releases">release guides</a> '
                 'pick the ones worth planning around.</p>') if fmt in {"movies", "tv", "anime", "games", "books"} else ""
        parts.append(f'<section id="coming" class="editorial bo-coming" aria-labelledby="coming-heading">'
                     f'<h2 id="coming-heading">Still to come in {year}</h2>{_paragraphs(entry["coming"])}{radar}</section>')
    parts.extend([
        '<section id="where-to-start" class="editorial yl-start"><h2>Where to start</h2>', _paragraphs(entry["start"]),
        f'<p>Members who track what they finish get their own year in review each December, with the titles they rated '
        f'highest in {year}. ' + ('<a href="/year-in-review">See yours</a>.' if signed_in else
                                  '<a href="/#signup">Start a free library</a> if you would like one.') + '</p></section>',
        '<section class="guide-related" aria-labelledby="related-heading"><p class="eyebrow">MORE GUIDES</p>',
        '<h2 id="related-heading">Keep reading</h2><div class="guide-related-grid">',
    ])
    others = [other for other in best_of.for_year(year) if other != slug]
    # The neighbouring formats first, so a long list of nine doesn't bury the related guides.
    position = best_of.for_year(year).index(slug)
    others.sort(key=lambda other: abs(best_of.for_year(year).index(other) - position))
    for other in others[:4]:
        target = GUIDES[other]
        parts.append(f'<article><h3><a href="{_e(best_of.path(other))}">{_e(target["name"])}</a></h3>'
                     f'<p>{_e(target["summary"])}</p></article>')
    for label, href in entry["related"]:
        parts.append(f'<article><h3><a href="{_e(href)}">{_e(label)}</a></h3></article>')
    shop_note = ('Where a pick has a "Find it" link, that link goes to Amazon, and OmniTrackr may earn a small commission '
                 'if you buy something there. It never decides what makes the list.' if shop else
                 'Links in the list go to OmniTrackr title pages' + (' and to each show\'s own page' if fmt == "podcasts" else '') + ', not shops.')
    parts.extend([
        '</div></section>',
        '<section id="method" class="guide-sources yl-method" aria-labelledby="method-heading">',
        '<h2 id="method-heading">How we chose</h2>',
        f'<p>{_e(entry.get("method") or _default_method(entry))}</p>',
        f'<p>These picks are not sponsored, and nobody paid to be included. Scores change as more reviews come in, and release '
        f'dates and availability vary by region. {_e(shop_note)}</p>',
        affiliate.disclosure_html("muted bo-disclosure") if shop else "",
        f'<h3>Sources we checked</h3><ul class="bo-sources">{"".join(_source_link(label, url) for label, url in entry["sources"])}</ul>',
        f'<p class="muted">First published {_e(_long_date(entry.get("published") or FIRST_PUBLISHED))}. Checked {_e(_long_date(reviewed))}. '
        '<a href="/contact">Suggest a pick or send a correction</a> · <a href="/content-quality">Editorial standards</a> · '
        '<a href="/pick">Pick for me</a></p></section></article>',
    ])
    return "".join(parts)


def _default_method(entry: dict) -> str:
    return (f'Prepared by OmniTrackr and reviewed by the site owner before publishing. We started from the '
            f'{FORMAT_LABELS[entry["format"]].lower()} released in {entry["year"]} that critics and audiences kept coming back to, '
            'then chose the ones we would recommend to a friend, across genres, with a fair caveat for each. Release dates, '
            'platforms and scores were checked against the public sources below; the opinions are our own.')


def _structured(slug: str, entry: dict) -> dict:
    url = SITE + best_of.path(slug)
    return {
        "@context": "https://schema.org", "@type": "Article",
        "headline": entry["name"], "description": entry["summary"],
        "datePublished": entry.get("published") or FIRST_PUBLISHED, "dateModified": entry["reviewed"],
        "mainEntityOfPage": url, "url": url, "inLanguage": "en-US",
        "author": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/about"},
        "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/"},
        "mainEntity": {"@type": "ItemList", "numberOfItems": len(entry["picks"]), "itemListElement": [
            {"@type": "ListItem", "position": index, "name": item["title"], "url": f"{url}#{best_of.anchor(item)}"}
            for index, item in enumerate(entry["picks"], 1)
        ]},
    }


# ---------------------------------------------------------------- the hub

def _covers(slug: str, details: dict, limit: int = 3) -> list[str]:
    found = []
    for item in GUIDES[slug]["picks"]:
        entry = best_of.pool_entry(item)
        image = title_pages._safe_image((details.get(entry["id"], {}) if entry else {}).get("image"))
        if image:
            found.append(image)
        if len(found) == limit:
            break
    return found


def _format_card(slug: str, details: dict, states: Optional[dict]) -> str:
    entry = GUIDES[slug]
    fmt = entry["format"]
    covers = _covers(slug, details)
    if covers:
        art = "".join(f'<img src="{_e(url)}" alt="" width="64" height="96" loading="lazy" decoding="async" '
                      'referrerpolicy="no-referrer">' for url in covers)
    else:
        art = f'<span class="bo-tile__initial" aria-hidden="true">{_e(FORMAT_LABELS[fmt][:1])}</span>'
    titles = " · ".join(item["title"] for item in entry["picks"][:3])
    mine = ""
    if states is not None:
        ids = [found["id"] for found in (best_of.pool_entry(item) for item in entry["picks"]) if found]
        done = sum(1 for pick_id in ids if states.get(pick_id) == "done")
        mine = f'<span class="bo-tile__mine">{done} of {len(ids)} finished</span>'
    return (f'<li><a class="bo-tile" href="{_e(best_of.path(slug))}" data-bo-format="{_e(fmt)}">'
            f'<span class="bo-tile__art{" bo-tile__art--covers" if covers else ""}">{art}</span>'
            f'<span class="bo-tile__text"><span class="bo-tile__format">{_e(FORMAT_LABELS[fmt])}</span>'
            f'<strong>{_e(entry["name"])}</strong>'
            f'<span class="bo-tile__titles">{len(entry["picks"])} picks: {_e(titles)}…</span>{mine}</span></a></li>')


def _nine_html(year: int, notes: dict, details: dict) -> str:
    rows = []
    for fmt, title, text in notes["nine"]:
        slug = best_of.find(year, fmt)
        item = next(item for item in GUIDES[slug]["picks"] if item["title"] == title)
        entry = best_of.pool_entry(item)
        image = title_pages._safe_image((details.get(entry["id"], {}) if entry else {}).get("image"))
        art = (f'<img class="bo-nine__art" src="{_e(image)}" alt="" width="72" height="108" loading="lazy" decoding="async" '
               'referrerpolicy="no-referrer">' if image else
               f'<span class="bo-nine__art bo-nine__art--empty" aria-hidden="true">{_e(FORMAT_LABELS[fmt][:1])}</span>')
        rows.append(
            f'<li class="bo-nine__item" data-bo-format="{_e(fmt)}">{art}<div>'
            f'<p class="bo-nine__format">{_e(FORMAT_LABELS[fmt])}</p>'
            f'<h3><a href="{_e(best_of.path(slug))}#{_e(best_of.anchor(item))}">{_e(title)}</a></h3>'
            f'<p class="bo-nine__creator">{_e(_meta_line(item).split(" · ", 1)[-1] if item["creator"] else item["released"])}</p>'
            f'<p>{_e(text)}</p></div></li>')
    return (f'<section class="bo-nine" id="the-year-in-nine" aria-labelledby="bo-nine-heading">'
            f'<p class="eyebrow">THE YEAR IN NINE</p><h2 id="bo-nine-heading">{_e(notes["nine_heading"])}</h2>'
            f'<div class="bo-nine__intro">{_paragraphs(notes["nine_intro"])}</div>'
            f'<ol class="bo-nine__list">{"".join(rows)}</ol></section>')


def _scorecard(year: int, states: Optional[dict], signed_in: bool) -> str:
    total = sum(1 for _ in best_of.picks(year))
    if not signed_in:
        return ('<aside class="bo-score bo-score--guest" aria-labelledby="bo-score-heading">'
                f'<div><p class="eyebrow">YOUR {year}</p><h2 id="bo-score-heading">How many of these {total} have you seen?</h2>'
                '<p>Save the picks you have finished and the ones you still mean to get to. A free OmniTrackr library keeps '
                'count across all nine formats and turns it into your own year in review in December.</p></div>'
                '<a class="button" href="/#signup">Start counting, free →</a></aside>')
    if states is None:
        return ""
    done = sum(1 for state in states.values() if state == "done")
    tracked = sum(1 for state in states.values() if state == "tracked")
    per_format = []
    for slug in best_of.for_year(year):
        ids = [found["id"] for found in (best_of.pool_entry(item) for item in GUIDES[slug]["picks"]) if found]
        got = sum(1 for pick_id in ids if states.get(pick_id) == "done")
        width = round(100 * got / len(ids)) if ids else 0
        per_format.append(f'<li data-bo-format="{_e(GUIDES[slug]["format"])}"><a href="{_e(best_of.path(slug))}">'
                          f'{_e(FORMAT_LABELS[GUIDES[slug]["format"]])}</a>'
                          f'<span class="bo-score__bar" aria-hidden="true"><span style="width:{width}%"></span></span>'
                          f'<span class="bo-score__n">{got}/{len(ids)}</span></li>')
    if done == 0 and tracked == 0:
        lead = (f"None of our {total} picks are in your library yet. Every list below has an Add button, "
                "and the year still has a few weeks left.")
    else:
        lead = f"You have finished {done} of our {total} picks"
        lead += f", and {tracked} more {'is' if tracked == 1 else 'are'} waiting in your library." if tracked else "."
    return ('<aside class="bo-score" aria-labelledby="bo-score-heading">'
            f'<div><p class="eyebrow">YOUR {year}</p><h2 id="bo-score-heading">{done} of {total} finished</h2>'
            f'<p>{_e(lead)}</p><p><a href="/year-in-review">Open your year in review →</a></p></div>'
            f'<ul class="bo-score__formats">{"".join(per_format)}</ul></aside>')


def hub_content(details: dict, signed_in: bool, states: Optional[dict] = None) -> str:
    sections = []
    latest = best_of.years()[0]
    for year in best_of.years():
        cards = "".join(_format_card(slug, details, states if year == latest else None) for slug in best_of.for_year(year))
        sections.append(f'<section class="bo-year" aria-labelledby="bo-{year}"><p class="eyebrow">EVERY LIST</p>'
                        f'<h2 id="bo-{year}">Best of {year}, format by format</h2>'
                        f'<ul class="bo-tiles">{cards}</ul></section>')
    notes = YEARS.get(latest)
    total = sum(1 for _ in best_of.picks(latest))
    formats = len(best_of.for_year(latest))
    reviewed = max(GUIDES[slug]["reviewed"] for slug in best_of.for_year(latest))
    hero = (
        '<header class="hero bo-hero">'
        f'<p class="eyebrow">BEST OF {latest} · YEAR-END EDITION</p>'
        f'<h1>{_e(notes["headline"]) if notes else "The best of the year, one format at a time"}</h1>'
        f'<p class="guide-deck">{_e(notes["deck"]) if notes else ""}</p>'
        f'<p class="bo-hero__facts"><span><strong>{total}</strong> picks</span><span><strong>{formats}</strong> formats</span>'
        f'<span>Updated <time datetime="{_e(reviewed)}">{_e(_long_date(reviewed))}</time></span></p>'
        '<nav class="guide-jump" aria-label="On this page"><a href="#the-year-in-nine">The year in nine</a>'
        f'<a href="#bo-{latest}">Every list</a><a href="#how-these-lists-work">How these lists work</a></nav></header>'
    )
    intro = f'<div class="guide-intro bo-hub-intro">{_paragraphs(notes["intro"])}</div>' if notes else ""
    nine = _nine_html(latest, notes, details) if notes else ""
    return (
        '<article class="trail-guide bo-hub">' + hero + intro + _scorecard(latest, states, signed_in) + nine
        + "".join(sections)
        + '<section class="editorial yl-why" id="how-these-lists-work"><h2>How these lists work</h2>'
          '<p>We publish each year\'s lists in the autumn and keep updating them until the year is over, so a late release '
          'can still make the cut. Each list is written by hand, gives every pick a caveat as well as a reason, and ends '
          'with the reviews and listings its facts were checked against. The date at the top of each list says when it was '
          'last checked. Nothing on these lists is sponsored.</p>'
          '<p>Looking for something older? The <a href="/if-you-liked">If you liked</a> guides start from a favourite and '
          'suggest what to try next, <a href="/new-releases">the release guides</a> look ahead to the coming season, and '
          '<a href="/pick">Pick for me</a> suggests one title at a time from every guide on the site.</p></section></article>'
    )


def _hub_structured() -> dict:
    return {
        "@context": "https://schema.org", "@type": "CollectionPage", "name": HUB_TITLE, "description": HUB_DESCRIPTION,
        "url": SITE + best_of.BASE_PATH, "inLanguage": "en-US",
        "isPartOf": {"@type": "WebSite", "name": "OmniTrackr", "url": SITE + "/"},
        "mainEntity": {"@type": "ItemList", "itemListElement": [
            {"@type": "ListItem", "position": index, "name": GUIDES[slug]["name"], "url": SITE + best_of.path(slug)}
            for index, slug in enumerate((slug for year in best_of.years() for slug in best_of.for_year(year)), 1)
        ]},
    }


def _states(db: Session, user, year: int) -> Optional[dict]:
    if user is None:
        return None
    try:
        return best_of.library_states(db, user.id, year)
    except Exception:
        return None


@router.get(best_of.BASE_PATH, include_in_schema=False)
def best_of_index(user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    signed_in = user is not None
    states = _states(db, user, best_of.years()[0])
    content = hub_content(all_details(db), signed_in, states)
    response = page(HUB_TITLE, HUB_DESCRIPTION, best_of.BASE_PATH, content, structured_data=_hub_structured(),
                    head=(f'<link rel="stylesheet" href="/static/if-you-liked.css?v={LIKED_CSS_VERSION}">'
                          f'<link rel="stylesheet" href="/static/best-of.css?v={CSS_VERSION}">'), member=signed_in)
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


@router.get(best_of.BASE_PATH + "/{year}", include_in_schema=False)
def best_of_year(year: int):
    if year not in best_of.years():
        raise HTTPException(404, "No best-of lists for that year")
    # A fixed target: the hub lists every year, so nothing from the request goes into the Location header.
    return RedirectResponse(best_of.BASE_PATH, status_code=301)


@router.get(best_of.BASE_PATH + "/{year}/{fmt}", include_in_schema=False)
def best_of_guide(year: int, fmt: str, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    slug = best_of.find(year, fmt)
    if slug is None:
        raise HTTPException(404, "Guide not found")
    entry = GUIDES[slug]
    signed_in = user is not None
    content = guide_content(slug, entry, all_details(db), signed_in, _states(db, user, year))
    response = page(entry["search_title"], entry["summary"], best_of.path(slug), content,
                    structured_data=_structured(slug, entry), head=_head(signed_in), member=signed_in)
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


class BestOfAdd(BaseModel):
    id: str = Field(..., min_length=3, max_length=160)


@router.post("/api/best-of/add")
def best_of_add(payload: BestOfAdd, request: Request, response: Response,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a manga, podcast or audiobook pick to the member's library (title, year and creator only).

    The other formats save through POST /api/pick/add, since they are part of Pick for me.
    """
    response.headers["Cache-Control"] = "private, no-store"
    kind, _, slug = payload.id.partition("/")
    found = best_of.find_extra(kind, slug)
    if found is None:
        raise HTTPException(404, "Pick not found")
    browse_kind, entry = found
    lock_progress_owner(db, user.id)
    image = best_of.extra_details(title_search.index(db)).get(entry["id"], {}).get("image")
    state, record = browse.add_to_library(db, user, browse_kind, entry, image)
    db.commit()
    if state == "created":
        funnel.record("liked_saved", request)
    return {"state": state, "title": record.title, "category": title_pages.KINDS[kind][2],
            "library_url": f"/?library_category={title_pages.KINDS[kind][2]}&library_item={record.id}"}
