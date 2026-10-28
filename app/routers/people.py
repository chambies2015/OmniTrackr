"""People and studio pages (/people/<slug>, /studios/<slug>) and their directories."""
from __future__ import annotations

import os
import threading
import time
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import people_pages, review_spoilers, title_pages
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_db
from ..people_pages import PERSON, STUDIO
from ..site_chrome import apply_site_chrome
from .titles import CSS_VERSION, KIND_PLURALS, SITE_URL, _excerpt, _plural, _script_json

router = APIRouter(tags=["people"])
PEOPLE_CSS_VERSION = "20261028-people-1"
DIRECTORY_CACHE_SECONDS = 900
RANKED_SHOWN = 25
REVIEWS_SHOWN = 6
# "titles directed by X", "anime from Madhouse"
BY_PHRASE = {"Director": "directed by", "Creator": "created by", "Writer": "written by", "Cast": "starring",
             "Author": "by", "Mangaka": "by", "Host": "hosted by", "Artist": "by", "Studio": "from",
             "Developer": "developed by", "Publisher": "published by", "Network": "that aired on"}
ROLE_NOUNS = {"Director": "director", "Creator": "creator", "Writer": "writer", "Cast": "actor", "Author": "author",
              "Mangaka": "mangaka", "Host": "host", "Artist": "artist", "Studio": "studio", "Developer": "developer",
              "Publisher": "publisher", "Network": "network"}
ENTITY_LABEL = {PERSON: "People", STUDIO: "Studios"}


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _signed_in(request: Request) -> bool:
    return bool(request.cookies.get(AUTH_COOKIE_NAME))


def _ordered_roles(page) -> list[str]:
    return sorted(page.roles, key=lambda role: (-page.roles[role], people_pages.ROLE_ORDER.index(role)))


def _titles_word(numbers: dict, count: int) -> str:
    kinds = numbers["kinds"]
    if len(kinds) == 1:
        kind = next(iter(kinds))
        if count == 1:
            return {"tv": "TV show", "anime": "anime", "manga": "manga"}.get(kind, title_pages.KINDS[kind][3].lower())
        return _plural(kind)
    return "title" if count == 1 else "titles"


def _summary_text(page, numbers: dict) -> str:
    """A few plain sentences built from the member numbers on the page."""
    roles = _ordered_roles(page)
    count = numbers["titles"]
    titles = _titles_word(numbers, count)
    if len(roles) == 1:
        first = f"OmniTrackr members track {count} {titles} {BY_PHRASE[roles[0]]} {page.name}."
    else:
        nouns = [ROLE_NOUNS[role] for role in roles[:3]]
        joined = nouns[0] if len(nouns) == 1 else ", ".join(nouns[:-1]) + " and " + nouns[-1]
        first = f"OmniTrackr members track {count} {titles} {page.name} worked on, as {joined}."
    sentences = [first]
    if numbers["members"] >= 2:
        sentences.append(f"{numbers['members']} members have at least one of them in their library.")
    best, lowest = numbers["best"], numbers["lowest"]
    if best is not None:
        sentences.append(f"Members rate {best.title} highest, at {best.average} out of 10 from {best.rated} ratings.")
        if lowest is not None:
            sentences.append(f"{lowest.title} is lowest, at {lowest.average}.")
    if numbers["average"] is not None and len(numbers["rated_works"]) >= 2:
        sentences.append(f"Across all {numbers['ratings']} member ratings of these {titles}, the average is "
                         f"{numbers['average']} out of 10.")
    elif best is None:
        sentences.append(f"None of them has enough member ratings for an average yet. A {_titles_word(numbers, 1)} "
                         f"needs {title_pages.MIN_RATINGS_SHOWN} before one shows.")
    return " ".join(sentences)


def _work_meta(work) -> str:
    roles = sorted(work.roles, key=people_pages.ROLE_ORDER.index)
    bits = [title_pages.KINDS[work.kind][3], str(work.year) if work.year else None, " and ".join(roles) if roles else None]
    return " · ".join(filter(None, bits))


def _art(work, width: int = 72, height: int = 108) -> str:
    if work.image:
        return f'<img src="{_e(work.image)}" alt="" loading="lazy" width="{width}" height="{height}">'
    return f'<span>{_e(work.title[:1].upper())}</span>'


def _ranked_html(page, numbers: dict) -> str:
    ranked = sorted(numbers["rated_works"], key=lambda w: (-w.average, -w.rated, w.title.casefold()))[:RANKED_SHOWN]
    if not ranked:
        return ""
    entries = ""
    for rank, work in enumerate(ranked, start=1):
        counts = f"{work.rated} member ratings · {work.members} tracking"
        entries += (f'<li class="title-chart__entry"><span class="title-chart__rank" aria-label="Rank {rank}">{rank}</span>'
                    f'<a class="title-chart__art" href="{_e(work.url)}" tabindex="-1" aria-hidden="true">{_art(work)}</a>'
                    f'<div class="title-chart__body"><h3><a href="{_e(work.url)}">{_e(work.title)}</a></h3>'
                    f'<p class="title-chart__meta">{_e(_work_meta(work))}</p><p class="title-chart__counts">{_e(counts)}</p></div>'
                    f'<span class="title-chart__score"><strong>{_e(work.average)}</strong><small>/10</small></span></li>')
    unranked = len(page.works) - len(ranked)
    note = (f'<p class="people-note">{unranked} more {"needs" if unranked == 1 else "need"} '
            f'{title_pages.MIN_RATINGS_SHOWN} member ratings to be ranked. They are listed below.</p>' if unranked > 0 else "")
    return (f'<section class="title-section" aria-labelledby="ranked-title"><h2 id="ranked-title">Ranked by member rating</h2>'
            f'<ol class="title-chart">{entries}</ol>{note}</section>')


def _review_html(review: dict) -> str:
    work = review["work"]
    author = (f'<a class="title-review__author" href="{_e(review["profile_url"])}">{_e(review["username"])}</a>'
              if review.get("profile_url") else _e(review["username"]))
    rating = f'<span class="title-review__rating">{_e(review["rating"])}/10</span>' if review["rating"] is not None else ""
    body = review_spoilers.wrap(review, f'<p>{_e(_excerpt(review["review"], 360))}</p>')
    return (f'<article class="title-review"><header><strong>{author}</strong>{rating}</header>'
            f'<p class="people-review__on">On <a href="{_e(work.url)}">{_e(work.title)}</a></p>{body}'
            f'<a class="title-review__more" href="{_e(review["url"])}">Read the full review <span aria-hidden="true">→</span></a></article>')


def _reviews_html(page, numbers: dict) -> str:
    reviews = numbers["reviews"]
    if not reviews:
        return ""
    picked, seen = [], set()
    for review in reviews:  # Spread the picks across titles before doubling up on one.
        if review["work"].url not in seen:
            picked.append(review)
            seen.add(review["work"].url)
    picked += [r for r in reviews if r not in picked]
    cards = "".join(_review_html(review) for review in picked[:REVIEWS_SHOWN])
    return (f'<section class="title-section" aria-labelledby="reviews-title"><h2 id="reviews-title">What members wrote</h2>'
            f'<div class="title-reviews">{cards}</div></section>')


def _all_works_html(page) -> str:
    cards = ""
    for work in page.works:
        detail = f'{work.members} member{"s" if work.members != 1 else ""}'
        if work.year:
            detail += f" · {work.year}"
        cards += (f'<a class="title-related" href="{_e(work.url)}"><span class="title-related__art">{_art(work, 140, 210)}</span>'
                  f'<strong>{_e(work.title)}</strong><small>{_e(detail)}</small></a>')
    return (f'<section class="title-section" aria-labelledby="works-title"><h2 id="works-title">Everything members track</h2>'
            f'<div class="title-related-grid">{cards}</div></section>')


def _collaborators_html(page) -> str:
    if not page.collaborators:
        return ""
    chips = "".join(
        f'<li><a href="{_e(c["url"])}"><strong>{_e(c["name"])}</strong>'
        f'<small>{_e(c["shared"])} shared title{"s" if c["shared"] != 1 else ""}</small></a></li>'
        for c in page.collaborators)
    heading = "Often credited with" if page.entity == PERSON else "People and companies on these titles"
    return (f'<section class="title-section" aria-labelledby="with-title"><h2 id="with-title">{_e(heading)}</h2>'
            f'<ul class="people-chips">{chips}</ul></section>')


def _method_html(page) -> str:
    return (
        '<section class="title-section title-chart__method" aria-labelledby="method-title"><h2 id="method-title">How this page works</h2>'
        f'<p>Credits come from what members enter when they add a title (a film\'s director, a book\'s author) and from '
        'public facts we keep for each title page, which come from Wikidata, MyAnimeList, RAWG and TVmaze. A name '
        'spelled the same way counts as the same person or company, so two people who share a name can end up together here.</p>'
        f'<p>Ratings are out of 10 and come from members rating titles in their own libraries. Each member counts once per '
        f'title, and a title needs {title_pages.MIN_RATINGS_SHOWN} member ratings before its average shows or it joins the '
        'ranking. Members who keep a category private are left out, and the page never shows who tracks what.</p></section>')


def _cta_html(signed_in: bool, page) -> str:
    if signed_in:
        return ('<section class="title-section title-write"><h2>Rate what you have finished</h2>'
                f'<p class="title-write__lead">Your ratings change the order on this page. Open a title above to add it or rate it.</p>'
                '<div class="title-write__actions"><a class="site-btn site-btn--primary" href="/">Open my library</a></div></section>')
    return ('<section class="title-section title-write"><h2>Keep track of what you finish</h2>'
            f'<p class="title-write__lead">Make a free OmniTrackr library for movies, shows, anime, games, books, manga, '
            f'podcasts and albums. Rate what you finish and your ratings count on pages like this one.</p>'
            '<div class="title-write__actions"><a class="site-btn site-btn--primary" href="/#signup">Create a free account</a>'
            f'<a class="site-btn site-btn--ghost" href="{PEOPLE_PATHS[page.entity]}">Browse more {ENTITY_LABEL[page.entity].lower()}</a></div></section>')


PEOPLE_PATHS = {PERSON: "/people", STUDIO: "/studios"}


def _json_ld(page, numbers: dict, canonical: str, description: str) -> str:
    about = {"@type": "Person" if page.entity == PERSON else "Organization", "name": page.name}
    if set(page.roles) == {"Artist"}:
        about["@type"] = "MusicGroup"  # schema.org uses it for bands and solo musicians alike.
    item = {"@context": "https://schema.org", "@type": "CollectionPage", "name": f"{page.name} on OmniTrackr",
            "url": canonical, "description": description, "about": about,
            "mainEntity": {"@type": "ItemList", "numberOfItems": len(page.works), "itemListElement": [
                {"@type": "ListItem", "position": position, "name": work.title, "url": SITE_URL + work.url}
                for position, work in enumerate(page.works[:50], start=1)]}}
    breadcrumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_URL}/"},
        {"@type": "ListItem", "position": 2, "name": ENTITY_LABEL[page.entity], "item": SITE_URL + PEOPLE_PATHS[page.entity]},
        {"@type": "ListItem", "position": 3, "name": page.name, "item": canonical}]}
    return (f'<script type="application/ld+json">{_script_json(item)}</script>'
            f'<script type="application/ld+json">{_script_json(breadcrumbs)}</script>')


def _head(title: str, description: str, canonical: str, robots: str, extra: str = "", image: str = "") -> str:
    og_image = image or f"{SITE_URL}/omnitrackr_vortex.png"
    return f"""<meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_e(title)}</title>
  <meta name="description" content="{_e(_excerpt(description, 158))}">
  <meta name="robots" content="{robots}">
  <link rel="canonical" href="{_e(canonical)}">
  <meta property="og:title" content="{_e(title)}">
  <meta property="og:description" content="{_e(_excerpt(description, 200))}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{_e(canonical)}">
  <meta property="og:site_name" content="OmniTrackr">
  <meta property="og:image" content="{_e(og_image)}">
  <meta name="twitter:card" content="summary">
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/static/fonts/poppins-800-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261009-fonts-1">
  <link rel="stylesheet" href="/static/title-page.css?v={CSS_VERSION}">
  <link rel="stylesheet" href="/static/people-page.css?v={PEOPLE_CSS_VERSION}">
  {extra}"""


def render(page, indexable: bool, signed_in: bool) -> str:
    numbers = people_pages.stats(page)
    canonical = SITE_URL + page.path
    roles = _ordered_roles(page)
    summary = _summary_text(page, numbers)
    titles = _titles_word(numbers, 2)
    page_title = f"{page.name}: {titles} ranked by OmniTrackr members"
    robots = "index, follow, max-image-preview:large" if indexable else "noindex, follow"
    cover = next((w.image for w in page.works if w.image), None)
    stats_tiles = [f'<div><strong>{_e(numbers["titles"])}</strong><span>{_e(titles if numbers["titles"] != 1 else _titles_word(numbers, 1))} tracked</span></div>',
                   f'<div><strong>{_e(numbers["members"])}</strong><span>member{"s" if numbers["members"] != 1 else ""} tracking</span></div>']
    if numbers["average"] is not None:
        stats_tiles.append(f'<div><strong>{_e(numbers["average"])}/10</strong><span>average member rating</span></div>')
    else:
        stats_tiles.append(f'<div><strong>{_e(numbers["ratings"])}</strong><span>member rating{"s" if numbers["ratings"] != 1 else ""}</span></div>')
    kinds = " · ".join(f'{count} {KIND_PLURALS[kind].lower() if kind != "tv" else "TV shows"}' if count != 1
                       else f'1 {title_pages.KINDS[kind][3].lower() if kind != "tv" else "TV show"}'
                       for kind, count in numbers["kinds"].most_common()) if len(numbers["kinds"]) > 1 else ""
    ad_loader = '<script src="/static/ad-loader.js" defer></script>' if indexable and not signed_in else ""
    extra = f'<script src="/static/share.js?v=20261004-share-1" defer></script>{ad_loader}{_json_ld(page, numbers, canonical, summary)}'
    sections = "".join([_ranked_html(page, numbers), _reviews_html(page, numbers), _all_works_html(page),
                        _collaborators_html(page), _cta_html(signed_in, page), _method_html(page)])
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  {_head(page_title, summary, canonical, robots, extra, cover or "")}
</head>
<body class="site title-page people-page">
  <!--SITE_NAV:-->
  <main>
    <section class="site-hero people-hero"><div class="site-wrap people-hero__inner">
      <span class="people-hero__mono" aria-hidden="true">{_e(page.name[:1].upper())}</span>
      <div class="people-hero__copy">
        <nav class="title-crumbs" aria-label="Breadcrumb"><a href="{PEOPLE_PATHS[page.entity]}">{_e(ENTITY_LABEL[page.entity])}</a> <span aria-hidden="true">/</span> {_e(page.name)}</nav>
        <p class="site-eyebrow">{_e(" · ".join(roles))}</p>
        <h1>{_e(page.name)}</h1>
        <p class="people-hero__lead">{_e(summary)}</p>
        {f'<p class="people-hero__kinds">{_e(kinds)}</p>' if kinds else ''}
        <div class="title-stats people-hero__stats">{"".join(stats_tiles)}</div>
        <div class="title-hero__actions"><button type="button" class="site-btn site-btn--ghost" data-share data-share-title="{_e(page.name)} on OmniTrackr">Share</button></div>
      </div>
    </div></section>
    <div class="site-wrap title-body">{sections}</div>
  </main>
  <!--SITE_FOOTER-->
</body>
</html>"""
    return apply_site_chrome(html)


def _page_response(request: Request, db: Session, entity: str, slug: str):
    page = people_pages.build(db, entity, slug)
    if page is None:
        raise HTTPException(404, "Not found")
    signed_in = _signed_in(request)
    indexable = people_pages.is_indexable(page)
    response = strict_html_response(render(page, indexable, signed_in))
    response.headers["Cache-Control"] = "private, no-store" if signed_in else "public, max-age=600"
    response.headers["Vary"] = "Cookie"
    if not indexable:
        response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


@router.get("/people/{slug}", include_in_schema=False)
def person_page(slug: str, request: Request, db: Session = Depends(get_db)):
    return _page_response(request, db, PERSON, slug)


@router.get("/studios/{slug}", include_in_schema=False)
def studio_page(slug: str, request: Request, db: Session = Depends(get_db)):
    return _page_response(request, db, STUDIO, slug)


# ---------------------------------------------------------------- directories

DIRECTORY_COPY = {
    PERSON: ("People", "Directors, actors, authors and hosts members track",
             "The directors, actors, writers, authors, mangaka, podcast hosts and musicians whose work OmniTrackr "
             "members track most. Each page ranks their work by member rating and collects what members wrote about it."),
    STUDIO: ("Studios", "Studios, game developers and TV networks members track",
             "The film and anime studios, game developers, publishers and TV networks behind the titles OmniTrackr "
             "members track most. Each page ranks their work by member rating and collects what members wrote about it."),
}
_directory_cache: dict = {}
_directory_lock = threading.Lock()


def _directory_page(db: Session, entity: str) -> tuple[str, bool]:
    groups = people_pages.directory(db, entity)
    eyebrow, heading, intro = DIRECTORY_COPY[entity]
    sections, listed = [], []
    for role, entries in groups.items():
        listed += entries
        items = "".join(f'<li><a href="{_e(entry["url"])}"><strong>{_e(entry["name"])}</strong>'
                        f'<small>{_e(entry["titles"])} titles</small></a></li>' for entry in entries)
        sections.append(f'<section class="title-section" aria-labelledby="role-{_e(role.lower())}">'
                        f'<h2 id="role-{_e(role.lower())}">{_e(people_pages.ROLE_PLURALS[role])}</h2>'
                        f'<ul class="people-chips">{items}</ul></section>')
    if not sections:
        sections.append('<section class="title-section"><h2>Nothing here yet</h2><p class="title-empty">Names appear '
                        f'here once members track at least {people_pages.MIN_LINKED_WORKS} titles by the same '
                        'person or company. <a href="/titles">Browse popular titles</a> in the meantime.</p></section>')
    other = STUDIO if entity == PERSON else PERSON
    sections.append(f'<p class="people-note">Looking for {_e(ENTITY_LABEL[other].lower())}? '
                    f'<a href="{PEOPLE_PATHS[other]}">Browse {_e(DIRECTORY_COPY[other][1][0].lower() + DIRECTORY_COPY[other][1][1:])}</a>.</p>')
    # Mostly links, so it waits until enough of the pages it lists have real member data.
    index_directory = sum(1 for entry in listed if entry["titles"] >= people_pages.INDEX_MIN_WORKS) >= 12
    canonical = SITE_URL + PEOPLE_PATHS[entity]
    item_list = {"@context": "https://schema.org", "@type": "CollectionPage", "name": heading, "url": canonical,
                 "description": intro, "mainEntity": {"@type": "ItemList", "itemListElement": [
                     {"@type": "ListItem", "position": position, "name": entry["name"], "url": SITE_URL + entry["url"]}
                     for position, entry in enumerate(listed[:100], start=1)]}}
    structured = f'<script type="application/ld+json">{_script_json(item_list)}</script>' if listed else ""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  {_head(f"{heading} | OmniTrackr", intro, canonical, "index, follow" if index_directory else "noindex, follow", structured)}
</head>
<body class="site title-page people-page">
  <!--SITE_NAV:titles-->
  <main>
    <section class="site-hero"><div class="site-wrap">
      <p class="site-eyebrow">{_e(eyebrow)}</p>
      <h1>{_e(heading)}</h1>
      <p>{_e(intro)}</p>
    </div></section>
    <div class="site-wrap title-body">{"".join(sections)}</div>
  </main>
  <!--SITE_FOOTER-->
</body>
</html>"""
    return apply_site_chrome(html), index_directory


def _directory_response(db: Session, entity: str):
    if os.getenv("TESTING", "").lower() == "true":
        html, index_directory = _directory_page(db, entity)
    else:
        with _directory_lock:
            cached = _directory_cache.get(entity)
            if cached is None or time.monotonic() - cached[0] >= DIRECTORY_CACHE_SECONDS:
                cached = (time.monotonic(), _directory_page(db, entity))
                _directory_cache[entity] = cached
            html, index_directory = cached[1]
    response = strict_html_response(html)
    response.headers["Cache-Control"] = "public, max-age=900"
    if not index_directory:
        response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


@router.get("/people", include_in_schema=False)
def people_index(db: Session = Depends(get_db)):
    return _directory_response(db, PERSON)


@router.get("/studios", include_in_schema=False)
def studios_index(db: Session = Depends(get_db)):
    return _directory_response(db, STUDIO)


def directory_is_indexable(db: Session, entity: str) -> bool:
    return _directory_page(db, entity)[1]
