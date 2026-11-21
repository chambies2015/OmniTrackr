"""Browse pages: /browse, /browse/manga, /browse/podcasts, /browse/audiobooks and their add-to-library API."""
from __future__ import annotations

import os
import threading
import time
from html import escape
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import browse, explore_art, title_pages
from ..auth import AUTH_COOKIE_NAME
from ..browse_catalog import CATALOG
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..progress import lock_progress_owner
from ..site_chrome import apply_site_chrome
from .titles import CSS_VERSION as TITLE_CSS_VERSION
from .titles import _script_json

router = APIRouter()
SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
CSS_VERSION = "20261120-explore-1"
JS_VERSION = "20261120-explore-1"
GUEST_LIST_JS = "/static/guest-list.js?v=20261121-phone-1"
PAGE_CACHE_SECONDS = 600
TRACKER_GUIDES = {"manga": "/manga-tracker", "podcasts": "/podcast-tracker", "audiobooks": "/audiobook-tracker"}
INDEX_DESCRIPTION = ("Hand-picked manga, podcasts and audiobooks to start a library from, with the current charts "
                     "from MyAnimeList, Apple Podcasts and Apple Books. Add any title to OmniTrackr with one tap.")

_page_cache: dict[tuple, tuple[str, float]] = {}
_page_lock = threading.Lock()


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _kind_or_404(kind: str) -> dict:
    if kind not in browse.KINDS:
        raise HTTPException(404, "Nothing to browse here")
    return browse.KINDS[kind]


# ---------------------------------------------------------------- shared markup

def _head(title: str, description: str, canonical_path: str, structured: str, robots: str = "index, follow") -> str:
    canonical = SITE_URL + canonical_path
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_e(title)}</title>
  <meta name="description" content="{_e(description[:158])}">
  <meta name="robots" content="{robots}, max-image-preview:large">
  <link rel="canonical" href="{_e(canonical)}">
  <meta property="og:title" content="{_e(title)}">
  <meta property="og:description" content="{_e(description[:200])}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{_e(canonical)}">
  <meta property="og:site_name" content="OmniTrackr">
  <meta property="og:image" content="{SITE_URL}/omnitrackr_vortex.png">
  <meta name="twitter:card" content="summary">
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/static/fonts/poppins-800-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/static/fonts/source-serif-4-latin-var-normal.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261009-fonts-1">
  <link rel="stylesheet" href="/static/title-page.css?v={TITLE_CSS_VERSION}">
  <link rel="stylesheet" href="/static/browse.css?v={CSS_VERSION}">
  {explore_art.STYLESHEET}
  {structured}
</head>"""


def _art(image: Optional[str], title: str, kind: str, label: bool = True, width: Optional[int] = None) -> str:
    """The cover, or the title drawn as one in the format's colour (explore.css)."""
    return explore_art.cover(title, browse.KINDS[kind]["title_kind"], image, square=kind == "podcasts", label=label, width=width)


def _save_button(kind: str, item_key: str, item: dict, signed_in: bool) -> str:
    """Members add in one tap; everyone else saves to the list that moves into a new account."""
    config = browse.KINDS[kind]
    if signed_in:
        return (f'<button type="button" class="site-btn site-btn--primary site-btn--sm browse-add" data-browse-add '
                f'data-browse-kind="{_e(kind)}" data-browse-key="{_e(item_key)}">{_e(config["add_label"])}</button>')
    return (f'<button type="button" class="x-save" data-guest-save aria-pressed="false" '
            f'data-guest-kind="{_e(config["title_kind"])}" data-guest-slug="{_e(browse.guest_slug(item))}" '
            f'data-guest-title="{_e(item["title"])}">Save to my list</button>')


def _facts(kind: str, item: dict) -> str:
    extra = item.get("extra") or {}
    parts: list[str] = []
    if item.get("format"):
        parts.append(item["format"])
    if item.get("genre"):
        parts.append(item["genre"])
    if item.get("year"):
        parts.append(str(item["year"]))
    if kind == "manga":
        if extra.get("volumes"):
            parts.append(f"{extra['volumes']} volumes")
        if item.get("status"):
            parts.append(item["status"])
    elif kind == "audiobooks" and extra.get("length_hours"):
        hours = extra["length_hours"]
        parts.append(f"{hours:g} h" if hours < 10 else f"{round(hours)} h")
    elif kind == "podcasts" and item.get("status"):
        parts.append(item["status"])
    return " · ".join(_e(part) for part in parts)


def _creator_line(kind: str, item: dict) -> str:
    creator = item.get("creator")
    narrator = (item.get("extra") or {}).get("narrator")
    if kind == "audiobooks" and creator:
        line = f"by {creator}" + (f", read by {narrator}" if narrator else "")
    elif kind == "podcasts" and creator:
        line = f"with {creator}"
    elif creator:
        line = f"by {creator}"
    else:
        return ""
    return f'<p class="browse-card__creator">{_e(line)}</p>'


def _shelf_card(kind: str, item: dict, cover: Optional[str], page_link: Optional[str], signed_in: bool) -> str:
    title = item["title"]
    heading = f'<a href="{_e(page_link)}">{_e(title)}</a>' if page_link else _e(title)
    search = " ".join(filter(None, [title, item.get("creator"), item.get("genre"), item.get("format"),
                                     (item.get("extra") or {}).get("narrator")]))
    return (f'<article class="browse-card" id="{_e(item["key"])}" data-browse-item data-search="{_e(search.lower())}">'
            f'<div class="browse-card__art">{_art(cover, title, kind)}</div>'
            f'<div class="browse-card__head"><p class="browse-card__facts">{_facts(kind, item)}</p>'
            f'<h3 class="browse-card__title">{heading}</h3>{_creator_line(kind, item)}</div>'
            f'<p class="browse-card__why">{_e(item["why"])}</p><p class="browse-card__fit">{_e(item["fit"])}</p>'
            f'<div class="browse-card__actions">{_save_button(kind, item["key"], item, signed_in)}'
            f'<span class="browse-card__status" role="status" aria-live="polite"></span></div></article>')


def _chart_entry(kind: str, position: int, item: dict, signed_in: bool) -> str:
    facts = " · ".join(_e(part) for part in filter(None, [item.get("creator"), item.get("genre"), str(item["year"]) if item.get("year") else None]))
    link = (f'<a class="browse-chart__source" href="{_e(item["url"])}" rel="noopener noreferrer nofollow" target="_blank">View on {_e(browse.KINDS[kind]["source"][0])} ↗</a>'
            if item.get("url") else "")
    return (f'<li class="browse-chart__entry" data-browse-item data-search="{_e(" ".join(filter(None, [item["title"], item.get("creator"), item.get("genre")])).lower())}">'
            f'<span class="browse-chart__rank" aria-hidden="true">{position}</span>'
            f'<span class="browse-chart__art">{_art(item.get("image"), item["title"], kind, label=False, width=56)}</span>'
            f'<span class="browse-chart__body"><strong>{_e(item["title"])}</strong><small>{facts}</small>{link}</span>'
            f'<span class="browse-chart__actions">{_save_button(kind, item["id"], item, signed_in)}'
            f'<span class="browse-card__status" role="status" aria-live="polite"></span></span></li>')


def _chart_section(kind: str, chart: Optional[dict], signed_in: bool) -> str:
    config = browse.KINDS[kind]
    items = browse.chart_items(chart)
    source_name, source_url = config["source"]
    if not items:
        note = ("The chart is being fetched; it appears on the next visit." if chart is None or not chart.get("error")
                else f"{source_name} did not answer just now, so the chart is resting. The shelves below do not depend on it.")
        return (f'<section class="title-section browse-chart" id="popular" aria-labelledby="popular-heading">'
                f'<h2 id="popular-heading">{_e(config["chart_name"])}</h2><p class="title-section__lead">{_e(note)}</p></section>')
    updated = browse.chart_updated(chart)
    when = (f'<p class="browse-chart__updated">Updated <time datetime="{updated.isoformat()}Z">{updated.strftime("%B")} {updated.day}, {updated.year}</time>'
            f' · Source: <a href="{_e(source_url)}" rel="noopener noreferrer" target="_blank">{_e(source_name)}</a></p>' if updated else "")
    entries = "".join(_chart_entry(kind, position, item, signed_in) for position, item in enumerate(items, start=1))
    return (f'<section class="title-section browse-chart" id="popular" aria-labelledby="popular-heading">'
            f'<div class="title-section__head"><h2 id="popular-heading">{_e(config["chart_name"])}</h2></div>'
            f'<p class="title-section__lead">{_e(config["chart_blurb"])}</p>'
            f'<ol class="browse-chart__list">{entries}</ol>{when}</section>')


def _cta(kind: str, signed_in: bool) -> str:
    plural = CATALOG[kind]["plural"]
    if signed_in:
        return ('<section class="title-section title-write"><h2>Everything you add lands in your library</h2>'
                f'<p class="title-write__lead">New {_e(plural)} start unfinished and unrated. Open the tab to log progress, rate them and write a review once you are done.</p>'
                '<div class="title-write__actions"><a class="site-btn site-btn--primary" href="/">Open my library</a></div></section>')
    return ('<section class="title-section title-write"><h2>Keep the ones you pick</h2>'
            f'<p class="title-write__lead">OmniTrackr is a free tracker for the {_e(plural)} you get through, alongside your movies, shows, games, books and albums. '
            'Save a few from this page now; they move into your library the moment you create an account.</p>'
            '<div class="title-write__actions"><a class="site-btn site-btn--primary" href="/#signup">Create a free account</a>'
            f'<a class="site-btn site-btn--ghost" href="{TRACKER_GUIDES[kind]}">How the {_e(CATALOG[kind]["label"].lower())} tracker works</a></div></section>')


def _related(kind: str) -> str:
    others = "".join(f'<li><a href="{browse.path(other)}">{_e(CATALOG[other]["heading"])}</a><span>{_e(CATALOG[other]["lead"])}</span></li>'
                     for other in CATALOG if other != kind)
    return (f'<section class="title-section browse-related" aria-labelledby="related-heading"><h2 id="related-heading">More shelves</h2>'
            f'<ul class="browse-related__list">{others}'
            '<li><a href="/titles">Popular titles across every format</a><span>The movies, shows, anime, games, books and albums members track most.</span></li>'
            '<li><a href="/discover">Discover trails</a><span>Editorial trails that connect four formats through one idea.</span></li></ul></section>')


def _method(kind: str) -> str:
    paragraphs = "".join(f"<p>{_e(text)}</p>" for text in CATALOG[kind]["method"])
    return (f'<section class="title-section browse-method" id="method" aria-labelledby="method-heading"><h2 id="method-heading">How this page is put together</h2>'
            f'{paragraphs}<p class="muted">Spotted a wrong fact? <a href="/contact">Send a correction</a> · <a href="/content-quality">Editorial standards</a></p></section>')


def _jump_links(kind: str, has_chart: bool) -> str:
    """The shelves as chips in a bar that sticks under the header (browse.js marks the one in view)."""
    links = [f'<a href="#popular">{_e(browse.KINDS[kind]["chart_name"])}</a>'] if has_chart else []
    links += [f'<a href="#{_e(shelf["slug"])}">{_e(shelf["name"])}</a>' for shelf in CATALOG[kind]["shelves"]]
    return f'<nav class="x-jump browse-jump" aria-label="On this page"><div class="x-jump__inner">{"".join(links)}</div></nav>'


def _structured(kind: str, items: list[dict], links: dict[str, str]) -> str:
    page = CATALOG[kind]
    canonical = SITE_URL + browse.path(kind)
    elements = []
    for position, item in enumerate(items, start=1):
        element = {"@type": "ListItem", "position": position, "name": item["title"]}
        if item["key"] in links:
            element["url"] = SITE_URL + links[item["key"]]
        elements.append(element)
    collection = {"@context": "https://schema.org", "@type": "CollectionPage", "name": page["heading"], "url": canonical,
                  "description": page["description"], "inLanguage": "en-US",
                  "isPartOf": {"@type": "WebSite", "name": "OmniTrackr", "url": SITE_URL + "/"},
                  "mainEntity": {"@type": "ItemList", "numberOfItems": len(elements), "itemListElement": elements}}
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL + "/"},
        {"@type": "ListItem", "position": 2, "name": "Browse", "item": SITE_URL + browse.path()},
        {"@type": "ListItem", "position": 3, "name": page["label"], "item": canonical}]}
    return (f'<script type="application/ld+json">{_script_json(collection)}</script>'
            f'<script type="application/ld+json">{_script_json(crumbs)}</script>')


# ---------------------------------------------------------------- pages

def render_kind(db: Session, kind: str, chart: Optional[dict], signed_in: bool) -> tuple[str, list[dict]]:
    """The page and the shelf entries whose covers still need a lookup."""
    page = CATALOG[kind]
    items = browse.shelf_items(kind)
    covers, pending = browse.cached_covers(db, kind, items)
    # Entries members already track link to their title page, which has reviews and facts.
    groups = title_pages.find_many(db, browse.KINDS[kind]["title_kind"], {browse.guest_slug(item) for item in items})
    links = {item["key"]: groups[browse.guest_slug(item)].path for item in items if browse.guest_slug(item) in groups}
    shelves = ""
    for shelf in page["shelves"]:
        cards = "".join(_shelf_card(kind, item, covers.get(item["key"]), links.get(item["key"]), signed_in) for item in shelf["items"])
        shelves += (f'<section class="title-section browse-shelf" id="{_e(shelf["slug"])}" aria-labelledby="{_e(shelf["slug"])}-heading">'
                    f'<div class="title-section__head"><h2 id="{_e(shelf["slug"])}-heading">{_e(shelf["name"])}</h2>'
                    f'<span class="browse-shelf__count">{len(shelf["items"])} {_e(page["noun"])}</span></div>'
                    f'<p class="title-section__lead">{_e(shelf["lead"])}</p><div class="browse-grid">{cards}</div></section>')
    intro = "".join(f"<p>{_e(text)}</p>" for text in page["intro"])
    chart_html = _chart_section(kind, chart, signed_in)
    crumbs = (f'<nav class="title-crumbs" aria-label="Breadcrumb"><a href="{browse.path()}">Browse</a> '
              f'<span aria-hidden="true">/</span> {_e(page["label"])}</nav>')
    filter_html = ('<section class="browse-filter" aria-label="Find a title on this page" hidden>'
                   '<label for="browse-search">Looking for something in particular?</label>'
                   '<input id="browse-search" type="search" class="site-field" maxlength="100" placeholder="Title, creator or genre" autocomplete="off">'
                   '<p id="browse-filter-status" class="muted" role="status" aria-live="polite"></p></section>')
    # The hero's cover stack: the first covers the shelves have found, drawn ones if none yet.
    stack_items = sorted(items, key=lambda item: item["key"] not in covers)[:5]
    stack = "".join(_art(covers.get(item["key"]), item["title"], kind) for item in stack_items)
    title_kind = browse.KINDS[kind]["title_kind"]
    body = f"""
<body class="site title-page browse-page explore" data-browse-kind="{_e(kind)}" data-kind="{_e(title_kind)}">
  <!--SITE_NAV:browse-->
  <main>
    <section class="site-hero browse-hero"><div class="site-wrap browse-hero__wrap">
      <div class="browse-hero__copy">
      {crumbs}
      <p class="site-eyebrow">Browse · {_e(page["label"])} · {len(items)} picks</p>
      <h1>{_e(page["heading"])}</h1>
      <p class="browse-deck">{_e(page["lead"])}</p>
      <p class="browse-byline">By <a href="/about">OmniTrackr</a> · <a href="#method">How this page is put together</a></p>
      <p class="title-hero__status browse-hero__status" role="status" aria-live="polite"></p>
      </div>
      <div class="browse-hero__stack" aria-hidden="true">{stack}</div>
    </div></section>
    {_jump_links(kind, bool(browse.chart_items(chart)))}
    <div class="site-wrap title-body browse-body">
      <section class="title-section browse-intro" aria-label="About these shelves">{intro}</section>
      {chart_html}
      {filter_html}
      {shelves}
      {_cta(kind, signed_in)}
      {_related(kind)}
      {_method(kind)}
    </div>
  </main>
  {"" if signed_in else explore_art.dock()}
  <!--SITE_FOOTER-->
  <script src="/static/browse.js?v={JS_VERSION}" defer></script>
  {'' if signed_in else f'<script src="{GUEST_LIST_JS}" defer></script>'}
</body>
</html>"""
    html = _head(page["page_title"], page["description"], browse.path(kind), _structured(kind, items, links)) + body
    return apply_site_chrome(html, member=signed_in), pending


# Written for the hub: how to choose a first manga, podcast or audiobook, and where to get them
# without paying full price. Shelf pages carry the picks; this is the advice that applies to all of them.
INDEX_NOTES = """
      <section class="title-section browse-notes" id="choosing-a-manga" aria-labelledby="browse-manga-heading">
        <h2 id="browse-manga-heading">Choosing a first manga</h2>
        <p><strong>Check the length before the premise.</strong> A finished series under fifteen volumes is a few weekends. A long-running one can be a hundred volumes and counting, which is wonderful if you love it and a poor first test if you are not sure you like manga at all. That is why the first shelf is finished series under fifteen volumes.</p>
        <p><strong>Read the first volume, not the first chapter.</strong> Series are planned and paced for the collected volume, and many take most of one to find their footing. If volume one has not caught you, volume two rarely will.</p>
        <p><strong>Treat the magazine label as a hint, not a rule.</strong> Shōnen, shōjo, seinen and josei name the readers a magazine was aimed at (teenage boys, teenage girls, adult men and adult women), not the quality or even the genre. Some of the most loved series sit outside the label you would expect.</p>
        <p><strong>Know which way it reads.</strong> Most English editions of Japanese manga keep the original right-to-left order, so you start at what looks like the back. Korean webtoons are made to scroll top to bottom on a phone, one long strip per chapter.</p>
        <p><strong>Read it legally for little or nothing.</strong> Shueisha's Manga Plus and Viz's Shonen Jump app carry current chapters of many Jump series. Many public libraries lend manga, on the shelf and through apps such as Libby and Hoopla, and Webtoon and Tapas have large free catalogues of webtoons.</p>
      </section>
      <section class="title-section browse-notes" id="choosing-a-podcast" aria-labelledby="browse-podcast-heading">
        <h2 id="browse-podcast-heading">Choosing a podcast</h2>
        <p><strong>Know which kind of show it is.</strong> A narrative series tells one story over a season and should be heard from episode one. A conversation or interview show can be started anywhere, so try the newest episode, or one with a guest or topic you already care about.</p>
        <p><strong>Give it two episodes.</strong> First episodes carry the most setup, and hosts often take a few to settle. If the second still feels like work, move on: there are more good shows than anyone has time for.</p>
        <p><strong>Pick the speed by the show.</strong> Most apps play at 1.25 or 1.5 times speed, which suits a chat show. Fiction and sound-designed documentaries are usually better at normal speed, because their pauses and music were timed for it.</p>
        <p><strong>Check where it lives.</strong> Most podcasts come from an open feed that any podcast app can play for free. Some are exclusive to one service, and some also sell a paid feed with no ads or with extra episodes.</p>
      </section>
      <section class="title-section browse-notes" id="choosing-an-audiobook" aria-labelledby="browse-audiobook-heading">
        <h2 id="browse-audiobook-heading">Choosing an audiobook</h2>
        <p><strong>Play the sample first.</strong> Most stores and library apps let you hear a few minutes from the start. If the narrator's voice bothers you in five minutes, it will bother you more in fifteen hours, and the same book read by someone else can be a different experience.</p>
        <p><strong>Start with something that suits the ear.</strong> Dialogue-heavy fiction, memoirs read by the people who lived them and full-cast productions tend to make the easiest listens. Dense nonfiction built on tables, maps or footnotes is harder, though some publishers include a PDF of the figures.</p>
        <p><strong>Borrow before you buy.</strong> If your library offers them, Libby and Hoopla lend audiobooks free with a library card. Popular new titles can have long waiting lists, so place holds early. If you buy, Libro.fm shares the money with an independent bookshop you choose.</p>
        <p><strong>Use the hours.</strong> Every shelf pick lists its length. A commute of forty minutes each way gets through a ten-hour novel in about a week and a half of working days.</p>
      </section>"""


def render_index(signed_in: bool, db: Optional[Session] = None) -> str:
    cards = ""
    for kind, page in CATALOG.items():
        items = browse.shelf_items(kind)
        covers: dict[str, str] = {}
        if db is not None:
            try:
                covers, _ = browse.cached_covers(db, kind, items)
            except Exception:  # Covers are decoration; the hub reads fine without them.
                covers = {}
        fan_items = sorted(items, key=lambda item: item["key"] not in covers)[:4]
        fan = "".join(_art(covers.get(item["key"]), item["title"], kind, width=76) for item in fan_items)
        shelves = "".join(f'<li>{_e(shelf["name"])}</li>' for shelf in page["shelves"])
        cards += (f'<a class="browse-hub__card" href="{browse.path(kind)}" data-kind="{_e(browse.KINDS[kind]["title_kind"])}">'
                  f'<span class="browse-hub__fan" aria-hidden="true">{fan}</span><div class="browse-hub__text">'
                  f'<p class="site-eyebrow">{_e(page["label"])} · {len(items)} picks</p>'
                  f'<h2>{_e(page["heading"])}</h2><p>{_e(page["lead"])}</p><ul class="browse-hub__shelves">{shelves}</ul>'
                  f'<span class="browse-hub__go">Open the shelves <span aria-hidden="true">→</span></span></div></a>')
    structured = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Browse: manga, podcasts and audiobooks to start with",
                  "url": SITE_URL + browse.path(), "description": INDEX_DESCRIPTION, "inLanguage": "en-US",
                  "isPartOf": {"@type": "WebSite", "name": "OmniTrackr", "url": SITE_URL + "/"},
                  "mainEntity": {"@type": "ItemList", "itemListElement": [
                      {"@type": "ListItem", "position": position, "name": page["heading"], "url": SITE_URL + browse.path(kind)}
                      for position, (kind, page) in enumerate(CATALOG.items(), start=1)]}}
    body = f"""
<body class="site title-page browse-page browse-hub explore">
  <!--SITE_NAV:browse-->
  <main>
    <section class="site-hero"><div class="site-wrap">
      <p class="site-eyebrow">Browse · Three shelves, picked by hand</p>
      <h1>Something to start with</h1>
      <p>Manga, podcasts and audiobooks are the newest things OmniTrackr tracks, and the newest libraries are the emptiest. These pages are the starting stock: a live chart from the source each tracker already searches, and shelves of titles we would hand you, each with a line on why and who it suits.</p>
    </div></section>
    <div class="site-wrap title-body browse-body">
      <div class="browse-hub__grid">{cards}</div>{INDEX_NOTES}
      <section class="title-section"><h2>Already track movies, shows or games?</h2>
      <p class="title-section__lead">The six older formats have enough members that their pages build themselves. <a href="/titles">Popular titles</a> shows what members track most, <a href="/trending">Trending</a> shows what they picked up this week, and <a href="/discover">Discover</a> has editorial trails across all of them.</p></section>
    </div>
  </main>
  <!--SITE_FOOTER-->
</body>
</html>"""
    html = _head("Browse manga, podcasts and audiobooks worth starting | OmniTrackr", INDEX_DESCRIPTION, browse.path(),
                 f'<script type="application/ld+json">{_script_json(structured)}</script>') + body
    return apply_site_chrome(html, member=signed_in)


def _testing() -> bool:
    return os.getenv("TESTING", "").lower() == "true"


def _cached_page(key: tuple, build):
    if _testing():
        return build()
    with _page_lock:
        cached = _page_cache.get(key)
        if cached and time.monotonic() - cached[1] < PAGE_CACHE_SECONDS:
            return cached[0]
    result = build()
    with _page_lock:
        _page_cache[key] = (result, time.monotonic())
    return result


def clear_page_cache() -> None:
    with _page_lock:
        _page_cache.clear()


def _respond(html: str, signed_in: bool) -> Response:
    response = strict_html_response(html)
    response.headers["Cache-Control"] = "private, no-store" if signed_in else "public, max-age=600"
    response.headers["Vary"] = "Cookie"
    return response


@router.get("/browse", include_in_schema=False)
def browse_index(request: Request, db: Session = Depends(get_db)):
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    return _respond(_cached_page(("index", signed_in), lambda: render_index(signed_in, db)), signed_in)


@router.get("/browse/{kind}", include_in_schema=False)
async def browse_kind(kind: str, request: Request, db: Session = Depends(get_db)):
    _kind_or_404(kind)
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    client = getattr(request.app.state, "external_api_client", None)
    chart = await browse.CACHE.get(client, kind)

    def build():
        html, pending = render_kind(db, kind, chart, signed_in)
        browse.schedule_cover_warming(client, kind, pending)
        return html

    html = await run_in_threadpool(_cached_page, (kind, signed_in, bool(browse.chart_items(chart))), build)
    return _respond(html, signed_in)


# ---------------------------------------------------------------- API

class BrowseAdd(BaseModel):
    key: str = Field(..., min_length=1, max_length=130, pattern=r"^[a-z0-9-]+$")


@router.get("/api/browse/{kind}/mine")
def browse_mine(kind: str, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Keys of the entries on this page the member already tracks, so the buttons can say so."""
    _kind_or_404(kind)
    response.headers["Cache-Control"] = "private, no-store"
    return {"keys": browse.member_keys(db, user.id, kind, browse.CACHE.peek(kind))}


@router.post("/api/browse/{kind}/add")
def browse_add(kind: str, payload: BrowseAdd, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Add one shelf or chart entry to the member's library with public details only."""
    config = _kind_or_404(kind)
    response.headers["Cache-Control"] = "private, no-store"
    entry = browse.find_key(kind, payload.key, browse.CACHE.peek(kind))
    if entry is None:
        raise HTTPException(404, "That title is not on this page any more. Reload and try again.")
    lock_progress_owner(db, user.id)
    cover = None
    if "key" in entry:  # A shelf entry: use the cover the facts cache found, if any.
        covers, _ = browse.cached_covers(db, kind, [entry])
        cover = covers.get(entry["key"])
    state, record = browse.add_to_library(db, user, kind, entry, cover)
    db.commit()
    return {"state": state, "title": record.title, "category": config["library"],
            "url": title_pages.path_for_item(config["title_kind"], record)}
