"""Public trending pages: /trending, /trending/month, /trending/<kind> and /trending/<kind>/month.

The numbers and the write-up come from app/trending.py. Pages read completely
without scripts or an account, and link back to the all-time views (most tracked
and member charts) through the same switch those pages show.
"""
from __future__ import annotations

import os
from datetime import datetime
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import title_pages
from .. import trending
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_db
from ..site_chrome import apply_site_chrome, view_switch
from .titles import CSS_VERSION as TITLE_CSS_VERSION
from .titles import KIND_PLURALS

router = APIRouter(tags=["trending"])
SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
CSS_VERSION = "20261030-trending-1"
SINGULAR = {kind: noun for kind, (noun, _) in trending.NOUNS.items()}
PLURAL = {kind: plural for kind, (_, plural) in trending.NOUNS.items()}


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _art(entry: dict, width: int = 64) -> str:
    if entry.get("image"):
        return f'<img src="{_e(entry["image"])}" alt="" loading="lazy" width="{width}" height="{width * 3 // 2}">'
    return f'<span>{_e(entry["title"][:1].upper())}</span>'


def _movement(entry: dict, window: str) -> str:
    before = trending.WINDOW_WORDS[window][1]
    if entry["movement"] == "new":
        return '<span class="trend-move trend-move--new">New</span>'
    if entry["movement"] == "up":
        return (f'<span class="trend-move trend-move--up" title="Up {entry["change"]} from {_e(before)}">'
                f'<span aria-hidden="true">▲</span> {entry["change"]}<span class="sr-only"> up from {_e(before)}</span></span>')
    if entry["movement"] == "down":
        return (f'<span class="trend-move trend-move--down" title="Down {entry["change"]} from {_e(before)}">'
                f'<span aria-hidden="true">▼</span> {entry["change"]}<span class="sr-only"> down from {_e(before)}</span></span>')
    return f'<span class="trend-move" title="Same place as {_e(before)}"><span aria-hidden="true">=</span><span class="sr-only">Same place as {_e(before)}</span></span>'


def _counts(entry: dict) -> str:
    parts = [f'{entry["members"]} members']
    if entry["added"]:
        parts.append(f'{entry["added"]} added')
    if entry["active"]:
        parts.append(f'{entry["active"]} in progress')
    if entry["finished"]:
        parts.append(f'{entry["finished"]} finished')
    return " · ".join(parts)


def _entry_html(entry: dict, window: str, show_kind: bool) -> str:
    meta = " · ".join(filter(None, [title_pages.KINDS[entry["kind"]][3] if show_kind else None,
                                    str(entry["year"]) if entry.get("year") else None, entry.get("creator")]))
    score = (f'<span class="title-chart__score"><strong>{_e(entry["average"])}</strong><small>/10 from {entry["rated"]}</small></span>'
             if entry["average"] is not None else
             f'<span class="title-chart__score trend-score"><strong>{entry["members"]}</strong><small>members</small></span>')
    return (f'<li class="title-chart__entry trend-entry" id="rank-{entry["rank"]}">'
            f'<span class="title-chart__rank trend-rank"><span aria-label="Rank {entry["rank"]}">{entry["rank"]}</span>{_movement(entry, window)}</span>'
            f'<a class="title-chart__art" href="{_e(entry["url"])}" tabindex="-1" aria-hidden="true">{_art(entry, 72)}</a>'
            f'<div class="title-chart__body"><h3><a href="{_e(entry["url"])}">{_e(entry["title"])}</a></h3>'
            f'{f"<p class=title-chart__meta>{_e(meta)}</p>" if meta else ""}'
            f'<p class="title-chart__counts">{_e(_counts(entry))}</p></div>{score}</li>')


def _mini_list(heading: str, anchor: str, intro: str, entries: list[dict], value) -> str:
    if not entries:
        return ""
    items = "".join(
        f'<li><a href="{_e(e["url"])}"><span class="trend-mini__art">{_art(e, 40)}</span>'
        f'<span class="trend-mini__text"><strong>{_e(e["title"])}</strong><small>{_e(value(e))}</small></span></a></li>'
        for e in entries)
    return (f'<section class="title-section trend-panel" aria-labelledby="{anchor}"><h2 id="{anchor}">{_e(heading)}</h2>'
            f'<p class="trend-panel__intro">{_e(intro)}</p><ol class="trend-mini">{items}</ol></section>')


def _leaders_html(found: dict) -> str:
    cards = ""
    for kind in title_pages.KINDS:
        leaders = found["leaders"].get(kind)
        if not leaders:
            continue
        rows = "".join(f'<li><a href="{_e(e["url"])}">{_e(e["title"])}</a> <small>{e["members"]} members</small></li>'
                       for e in leaders)
        cards += (f'<div class="trend-leader"><h3><a href="{_e(trending.path(kind, found["window"]))}">{_e(KIND_PLURALS[kind])}</a></h3>'
                  f'<ol>{rows}</ol><a class="trend-leader__more" href="{_e(trending.path(kind, found["window"]))}">'
                  f'Full {_e(SINGULAR[kind])} chart <span aria-hidden="true">→</span></a></div>')
    if not cards:
        return ""
    return ('<section class="title-section" aria-labelledby="leaders-heading"><h2 id="leaders-heading">Leading each format</h2>'
            f'<div class="trend-leaders">{cards}</div></section>')


def _pills(kind: Optional[str], window: str) -> str:
    windows = "".join(
        f'<a class="site-chip{" title-chart__pill--on" if other == window else ""}" href="{_e(trending.path(kind, other))}"'
        f'{" aria-current=page" if other == window else ""}>{"Last 7 days" if other == "week" else "Last 30 days"}</a>'
        for other in trending.WINDOWS)
    kinds = [(None, "Everything")] + [(other, KIND_PLURALS[other]) for other in title_pages.KINDS]
    formats = "".join(
        f'<a class="site-chip{" title-chart__pill--on" if other == kind else ""}" href="{_e(trending.path(other, window))}"'
        f'{" aria-current=page" if other == kind else ""}>{_e(label)}</a>' for other, label in kinds)
    return (f'<nav class="title-chart__pills trend-windows" aria-label="Time period">{windows}</nav>'
            f'<nav class="title-chart__pills" aria-label="Trending by type">{formats}</nav>')


def _related_html(kind: Optional[str]) -> str:
    chart_kind = kind or "movie"
    links = [
        (f"/titles/{chart_kind}", f"Highest-rated {PLURAL[chart_kind]} of all time",
         "The all-time chart, ranked by member ratings."),
        ("/titles", "Most tracked titles", "What sits on the most member lists, old and new."),
        ("/new-this-week", "New this week", "This week's releases, with what members finished."),
        ("/release-radar", "Release Radar", "Release dates for the next few months."),
        ("/best-of", "Best of 2026", "Our editors' picks for the year so far."),
    ]
    cards = "".join(f'<a class="trend-link" href="{href}"><strong>{_e(label)}</strong><span>{_e(text)}</span></a>'
                    for href, label, text in links)
    return ('<section class="title-section" aria-labelledby="related-heading"><h2 id="related-heading">More charts and lists</h2>'
            f'<div class="trend-links">{cards}</div></section>')


def _method_html(window: str) -> str:
    days = trending.WINDOWS[window]
    return (
        '<section class="title-section title-chart__method" aria-labelledby="method-heading"><h2 id="method-heading">How trending works</h2>'
        f'<p>This chart only looks at the last {days} days. A title gets a point from each member who added it to their library, '
        'a point from each member who logged a start or progress in their journal, and two points from each member who '
        f'finished it. The arrows compare each title with where it stood in the {days} days before that.</p>'
        f'<p>A title needs activity from at least {trending.MIN_MEMBERS} different members before it is named, and an '
        f'average rating appears only once {trending.RATING_MIN} members have rated it in the same period. When someone '
        f'imports a big list or adds dozens of titles in one go, their batch counts about as much as '
        f'{trending.FULL_WEIGHT_TITLES} titles would, so one import cannot fill the chart. Journal entries that came in '
        'through an import are left out.</p>'
        '<p>Members who keep a category private are never counted, our editors\' account is left out, and nothing here '
        'shows who did what. The chart refreshes every few minutes.</p></section>')


def _cta_html(signed_in: bool, kind: Optional[str]) -> str:
    plural = PLURAL[kind] if kind else "movies, shows, games and books"
    if signed_in:
        return ('<section class="title-section title-write"><h2>Add what you are into right now</h2>'
                '<p class="title-write__lead">Log a start or a finish in your library and it counts toward next week\'s chart.</p>'
                '<div class="title-write__actions"><a class="site-btn site-btn--primary" href="/">Open my library</a></div></section>')
    return ('<section class="title-section title-write"><h2>Keep track of what you pick up</h2>'
            f'<p class="title-write__lead">OmniTrackr is a free tracker for the {_e(plural)} you get through. Add a title, '
            'mark it finished, rate it, and it counts toward these charts. Your library stays private unless you share it.</p>'
            '<div class="title-write__actions"><a class="site-btn site-btn--primary" href="/#signup">Create a free account</a>'
            '<a class="site-btn site-btn--ghost" href="/titles">Browse popular titles</a></div></section>')


def _empty_html(kind: Optional[str], window: str) -> str:
    now_words = trending.WINDOW_WORDS[window][0]
    noun = PLURAL[kind] if kind else "titles"
    other = ("" if window == "month" else
             f' The <a href="{_e(trending.path(kind, "month"))}">last 30 days</a> may have more to show.')
    chart_kind = kind or "movie"
    return (f'<section class="title-section"><h2>Nothing is trending {_e(now_words)} yet</h2>'
            f'<p class="title-empty">A title shows up here once at least {trending.MIN_MEMBERS} members have added, started '
            f'or finished it in the same stretch. Not enough {_e(noun)} have reached that yet.{other} Meanwhile, the '
            f'<a href="/titles/{chart_kind}">all-time member chart</a> and the <a href="/titles">most tracked titles</a> '
            'have plenty to browse.</p></section>')


def render(found: dict, kind: Optional[str], signed_in: bool) -> tuple[str, bool]:
    window = found["window"]
    now_words = trending.WINDOW_WORDS[window][0]
    if kind:
        chart = found["kinds"][kind]["chart"]
        finished, rated = found["kinds"][kind]["finished"], found["kinds"][kind]["rated"]
        indexable = found["kinds"][kind]["indexable"]
        heading = f"Trending {PLURAL[kind]} {now_words}"
        page_title = f"Trending {PLURAL[kind]} on OmniTrackr {now_words}"
        lead = chart[0]["title"] if chart else None
        description = (f"The {PLURAL[kind]} OmniTrackr members added, started and finished most in the last "
                       f"{trending.WINDOWS[window]} days" + (f", led by {lead}." if lead else "."))
        crumb = KIND_PLURALS[kind]
    else:
        chart, finished, rated = found["overall"], found["finished"], found["rated"]
        indexable = found["indexable"]
        heading = f"Trending on OmniTrackr {now_words}"
        page_title = f"Trending movies, shows, games and books {now_words} | OmniTrackr"
        names = [entry["title"] for entry in chart[:3]]
        description = ("The movies, TV shows, anime, games, books and more that OmniTrackr members picked up most in the "
                       f"last {trending.WINDOWS[window]} days" + (f", led by {trending._join(names)}." if names else "."))
        crumb = None
    word_count = trending.word_count(found, kind)
    indexable = indexable and word_count >= 40
    canonical = SITE_URL + trending.path(kind, window)
    built = datetime.fromisoformat(found["built_at"].rstrip("Z"))
    updated = f'Updated <time datetime="{_e(found["built_at"])}">{built.strftime("%B")} {built.day}, {built.year}</time>'
    writeup = "".join(f"<p>{_e(text)}</p>" for text in trending.paragraphs(found, kind))
    show_kind = kind is None
    if chart:
        chart_html = (f'<section class="title-section" aria-labelledby="chart-heading"><h2 id="chart-heading">'
                      f'Top {len(chart)} {_e(now_words)}</h2>'
                      f'<ol class="title-chart">{"".join(_entry_html(entry, window, show_kind) for entry in chart)}</ol></section>')
    else:
        chart_html = _empty_html(kind, window)
    finish_word = trending.FINISH_VERBS
    panels = (
        _mini_list("Finished most", "finished-heading",
                   f"Counted from members' journals {now_words}.", finished,
                   lambda e: f'{e["finished"]} members {finish_word[e["kind"]]} it'
                             + (f' · {e["average"]}/10' if e["average"] is not None else ""))
        + _mini_list("Rated highest by new finishers", "rated-heading",
                     f"Ratings members gave when they finished something {now_words}, {trending.RATING_MIN} or more each.",
                     rated, lambda e: f'{e["average"]}/10 from {e["rated"]} members'))
    panels_html = f'<div class="trend-panels">{panels}</div>' if panels else ""
    leaders = _leaders_html(found) if not kind else ""
    crumbs = (f'<nav class="title-crumbs" aria-label="Breadcrumb"><a href="/titles">Titles</a> <span aria-hidden="true">/</span> '
              f'<a href="{_e(trending.path(None, window))}">Trending</a> <span aria-hidden="true">/</span> {_e(crumb)}</nav>'
              if crumb else
              '<nav class="title-crumbs" aria-label="Breadcrumb"><a href="/titles">Titles</a> <span aria-hidden="true">/</span> Trending</nav>')
    structured = ""
    if chart:
        item_list = {"@context": "https://schema.org", "@type": "ItemList", "name": heading, "url": canonical,
                     "numberOfItems": len(chart), "itemListOrder": "https://schema.org/ItemListOrderDescending",
                     "itemListElement": [{"@type": "ListItem", "position": entry["rank"], "name": entry["title"],
                                          "url": SITE_URL + entry["url"]} for entry in chart]}
        structured += f'<script type="application/ld+json">{_json(item_list)}</script>'
    trail = [{"@type": "ListItem", "position": 1, "name": "Titles", "item": f"{SITE_URL}/titles"},
             {"@type": "ListItem", "position": 2, "name": "Trending", "item": SITE_URL + trending.path(None, window)}]
    if crumb:
        trail.append({"@type": "ListItem", "position": 3, "name": crumb, "item": canonical})
    structured += f'<script type="application/ld+json">{_json({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": trail})}</script>'
    robots = "index, follow" if indexable else "noindex, follow"
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_e(page_title)}</title>
  <meta name="description" content="{_e(description[:158])}">
  <meta name="robots" content="{robots}">
  <link rel="canonical" href="{_e(canonical)}">
  <meta property="og:title" content="{_e(heading)}">
  <meta property="og:description" content="{_e(description[:200])}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{_e(canonical)}">
  <meta property="og:site_name" content="OmniTrackr">
  <meta property="og:image" content="{SITE_URL}/omnitrackr_vortex.png">
  <meta name="twitter:card" content="summary">
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/static/fonts/poppins-800-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261009-fonts-1">
  <link rel="stylesheet" href="/static/title-page.css?v={TITLE_CSS_VERSION}">
  <link rel="stylesheet" href="/static/trending.css?v={CSS_VERSION}">
  {structured}
</head>
<body class="site title-page trending-page">
  <!--SITE_NAV:trending-->
  <main>
    <section class="site-hero"><div class="site-wrap">
      {view_switch("titles", "trending")}
      {crumbs}
      <p class="site-eyebrow">Trending · last {trending.WINDOWS[window]} days</p>
      <h1>{_e(heading)}</h1>
      <p>{_e(description)}</p>
      <p class="trend-updated">{updated}</p>
      {_pills(kind, window)}
    </div></section>
    <div class="site-wrap title-body">
      {f'<section class="title-section trend-writeup" aria-label="This period in short">{writeup}</section>' if writeup else ""}
      {chart_html}{panels_html}{leaders}{_cta_html(signed_in, kind)}{_related_html(kind)}{_method_html(window)}
    </div>
  </main>
  <!--SITE_FOOTER-->
</body>
</html>"""
    return apply_site_chrome(page), indexable


def _json(data) -> str:
    from .titles import _script_json
    return _script_json(data)


def _respond(request: Request, db: Session, kind: Optional[str], window: str):
    if kind is not None and kind not in title_pages.KINDS:
        raise HTTPException(404, "Unknown title type")
    found = trending.data(db, window)
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    html, indexable = render(found, kind, signed_in)
    response = strict_html_response(html)
    response.headers["Cache-Control"] = "private, no-store" if signed_in else "public, max-age=600"
    response.headers["Vary"] = "Cookie"
    if not indexable:
        response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


@router.get("/trending", include_in_schema=False)
def trending_week(request: Request, db: Session = Depends(get_db)):
    return _respond(request, db, None, "week")


@router.get("/trending/month", include_in_schema=False)
def trending_month(request: Request, db: Session = Depends(get_db)):
    return _respond(request, db, None, "month")


@router.get("/trending/{kind}", include_in_schema=False)
def trending_kind_week(kind: str, request: Request, db: Session = Depends(get_db)):
    return _respond(request, db, kind, "week")


@router.get("/trending/{kind}/month", include_in_schema=False)
def trending_kind_month(kind: str, request: Request, db: Session = Depends(get_db)):
    return _respond(request, db, kind, "month")
