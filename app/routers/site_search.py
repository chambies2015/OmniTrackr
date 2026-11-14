"""Site search: GET /api/search (the header box and Ctrl+K), the /search page and /opensearch.xml.

/search is the page the header search falls back to without JavaScript, the
"See all results" link in the search box, and what a browser's address bar
opens through /opensearch.xml. It is noindex: a results page has nothing of
its own for Google to keep.
"""
from __future__ import annotations

from html import escape
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from .. import site_search, title_pages, title_search
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_db
from ..site_chrome import apply_site_chrome
from .titles import CSS_VERSION, KIND_PLURALS, SITE_URL

router = APIRouter(tags=["search"])
SEARCH_CSS_VERSION = "20261114-search-1"
GUEST_LIST_JS = "/static/guest-list.js?v=20261031-browse-1"
PAGE_RESULTS = 36
API_LIMIT_MAX = 24
POPULAR_ON_PAGE = 12


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _signed_in(request: Request) -> bool:
    return bool(request.cookies.get(AUTH_COOKIE_NAME))


def _kind(value: str) -> Optional[str]:
    return value if value in title_pages.KINDS else None


@router.get("/api/search")
def search_api(request: Request, response: Response, q: str = Query("", max_length=200),
               kind: str = Query("", max_length=20), limit: int = Query(8, ge=1, le=API_LIMIT_MAX),
               db: Session = Depends(get_db)):
    """Titles, guides, pages and people for one search; popular titles for an empty one. No account needed."""
    response.headers["Cache-Control"] = "public, max-age=300"
    return site_search.search(db, q, _kind(kind), limit=limit)


@router.get("/opensearch.xml", include_in_schema=False)
def opensearch() -> Response:
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/" xmlns:moz="http://www.mozilla.org/2006/browser/search/">'
        '<ShortName>OmniTrackr</ShortName>'
        '<Description>Search movies, shows, anime, games, music, books, manga, podcasts and audiobooks on OmniTrackr</Description>'
        '<InputEncoding>UTF-8</InputEncoding>'
        f'<Image width="16" height="16" type="image/x-icon">{SITE_URL}/omnitrackr_favicon.ico</Image>'
        f'<Url type="text/html" method="get" template="{SITE_URL}/search?q={{searchTerms}}"/>'
        f'<moz:SearchForm>{SITE_URL}/search</moz:SearchForm>'
        '</OpenSearchDescription>'
    )
    return Response(body, media_type="application/opensearchdescription+xml",
                    headers={"Cache-Control": "public, max-age=86400"})


# ---------------------------------------------------------------- page

def _search_url(q: str = "", kind: Optional[str] = None) -> str:
    params = {key: value for key, value in (("q", q), ("kind", kind or "")) if value}
    return "/search" + (f"?{urlencode(params)}" if params else "")


def _save_button(item: dict, signed_in: bool) -> str:
    label = _e(f"{item['title']} ({item['label']}{', ' + str(item['year']) if item.get('year') else ''})")
    if signed_in:
        return (f'<button type="button" class="search-card__save" data-site-add data-kind="{_e(item["kind"])}" '
                f'data-slug="{_e(item["slug"])}" aria-label="Add {label} to your library">'
                '<span class="search-card__save-idle">＋ Add</span><span class="search-card__save-done">✓ Added</span></button>')
    # guest-list.js toggles these and keeps aria-pressed in step with the saved list.
    return (f'<button type="button" class="search-card__save" data-guest-kind="{_e(item["kind"])}" '
            f'data-guest-slug="{_e(item["slug"])}" data-guest-title="{_e(item["title"])}" aria-pressed="false" '
            f'aria-label="Save {label} to your list">'
            '<span class="search-card__save-idle">＋ Save</span><span class="search-card__save-done">✓ Saved</span></button>')


def _card(item: dict, signed_in: bool) -> str:
    art = (f'<img src="{_e(item["image"])}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" width="200" height="300">'
           if item.get("image") else f'<span aria-hidden="true">{_e(item["title"][:1].upper())}</span>')
    meta = " · ".join(str(part) for part in (item["label"], item.get("year")) if part)
    members = (f'<span class="search-card__members">{_e(item["members"])} members track it</span>'
               if item.get("members") else "")
    return (f'<li class="search-card"><a class="search-card__link" href="{_e(item["url"])}">'
            f'<span class="search-card__art">{art}</span>'
            f'<strong>{_e(item["title"])}</strong><span class="search-card__meta">{_e(meta)}</span>{members}</a>'
            f'{_save_button(item, signed_in)}</li>')


def _grid(items: list[dict], signed_in: bool) -> str:
    return f'<ul class="search-grid">{"".join(_card(item, signed_in) for item in items)}</ul>'


def _chips(q: str, kind: Optional[str], counts: dict) -> str:
    links = []
    options = [(None, "All")] + list(site_search.KIND_FILTERS.items())
    for value, label in options:
        count = counts.get(value) if q else None
        if q and value is not None and not count and value != kind:
            continue  # Hide formats with nothing to show for this search.
        current = ' aria-current="page"' if value == kind else ""
        number = f' <span>{_e(count)}</span>' if count else ""
        links.append(f'<a class="search-chip" href="{_e(_search_url(q, value))}"{current}>{_e(label)}{number}</a>')
    return f'<nav class="search-chips" aria-label="Filter by format">{"".join(links)}</nav>'


def _detail(guide: dict) -> str:
    return f'<span>{_e(guide["detail"])}</span>' if guide.get("detail") else ""


def _guides_html(guides: list[dict]) -> str:
    if not guides:
        return ""
    cards = "".join(
        f'<li><a href="{_e(g["url"])}"><span class="search-guide__section">{_e(g["section"])}</span>'
        f'<strong>{_e(g["title"])}</strong>{_detail(g)}</a></li>'
        for g in guides)
    return ('<section class="search-section" aria-labelledby="search-guides"><h2 id="search-guides">Guides and pages</h2>'
            f'<ul class="search-guides">{cards}</ul></section>')


def _people_html(people: list[dict]) -> str:
    if not people:
        return ""
    links = "".join(
        f'<li><a href="{_e(p["url"])}"><span class="search-person__mono" aria-hidden="true">{_e(p["name"][:1].upper())}</span>'
        f'<span><strong>{_e(p["name"])}</strong><small>{_e(p["role"])} · {_e(p["titles"])} titles</small></span></a></li>'
        for p in people)
    return ('<section class="search-section" aria-labelledby="search-people"><h2 id="search-people">People and studios</h2>'
            f'<ul class="search-people">{links}</ul></section>')


def _empty_html(q: str, kind: Optional[str], signed_in: bool) -> str:
    where = f" among {KIND_PLURALS[kind].lower()}" if kind else ""
    lines = [f'<h2>Nothing called “{_e(q)}”{_e(where)} yet</h2>']
    if kind:
        lines.append(f'<p><a href="{_e(_search_url(q))}">Search every format instead</a>.</p>')
    if signed_in:
        lines.append('<p>This page only knows titles other members track. Add anything in your library looks it up '
                     'across millions of movies, shows, games, books and more.</p>'
                     f'<a class="site-btn site-btn--primary" href="/?{_e(urlencode({"find": q}))}">Look it up in Add anything</a>')
    else:
        lines.append('<p>This page only knows titles other members track. Once you have a free library, Add anything '
                     'looks a title up across millions of movies, shows, games, books and more, and adds it in one tap.</p>'
                     '<a class="site-btn site-btn--primary" href="/#signup" data-guest-only>Start your free library</a>')
    return f'<div class="search-empty">{"".join(lines)}</div>'


def _guest_bar(signed_in: bool) -> str:
    if signed_in:
        return ""
    return ('<div class="search-guestbar" data-guest-bar hidden><p data-guest-count role="status"></p>'
            '<a class="site-btn site-btn--primary site-btn--sm" href="/#signup">Sign up free</a></div>')


def render(db: Session, q: str, kind: Optional[str], signed_in: bool) -> str:
    q = " ".join((q or "").split())[:site_search.QUERY_MAX]
    result = site_search.search(db, q, kind, limit=PAGE_RESULTS)
    searching = bool(q) and "popular" not in result
    if searching:
        heading = f"Results for “{q}”"
        everything = title_search.ranked(title_search.index(db), q)
        counts = {None: len(everything)}
        for entry in everything:
            counts[entry["kind"]] = counts.get(entry["kind"], 0) + 1
    else:
        heading = "Find something to watch, play, read or hear"
        counts = {}
    page_title = f"{q} - Search OmniTrackr" if searching else "Search OmniTrackr"

    body = []
    if searching:
        if result.get("suggestion"):
            body.append(f'<p class="search-suggest">Did you mean <a href="{_e(_search_url(result["suggestion"], kind))}">'
                        f'{_e(result["suggestion"])}</a>?</p>')
        if result["titles"]:
            total = result.get("total", len(result["titles"]))
            label = KIND_PLURALS[kind] if kind else "Titles"
            body.append(f'<section class="search-section" aria-labelledby="search-titles"><h2 id="search-titles">{_e(label)} '
                        f'<span>{_e(total)}</span></h2>{_grid(result["titles"], signed_in)}')
            if result.get("more"):
                body.append(f'<p class="search-more">Showing the closest {PAGE_RESULTS}. Add another word or pick a format to narrow it down.</p>')
            body.append('</section>')
        if not result["titles"]:
            body.append(_empty_html(q, kind, signed_in))
        body.append(_guides_html(result["guides"]))
        body.append(_people_html(result["people"]))
    else:
        popular = site_search.popular(title_search.index(db), kind, limit=POPULAR_ON_PAGE)
        if popular:
            label = f"Popular {KIND_PLURALS[kind].lower()}" if kind else "Popular with members"
            body.append(f'<section class="search-section" aria-labelledby="search-popular"><h2 id="search-popular">{_e(label)}</h2>'
                        f'{_grid(popular, signed_in)}</section>')
        starts = site_search.search_guides("in order", limit=2) + site_search.search_guides("how long", limit=1) \
            + site_search.search_guides("best", limit=1)
        body.append(_guides_html(starts).replace(">Guides and pages<", ">Good places to start<", 1))
    hint = "" if signed_in else (
        '<p class="search-hero__hint" data-guest-only>Tap <strong>Save</strong> on anything you like. '
        'Your list moves into a free library when you sign up.</p>')
    extra = "" if signed_in else f'<script src="{GUEST_LIST_JS}" defer></script>'
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_e(page_title)}</title>
  <meta name="description" content="Search the movies, shows, anime, games, music, books, manga, podcasts and audiobooks OmniTrackr members track, plus every guide on the site.">
  <meta name="robots" content="noindex, follow">
  <link rel="canonical" href="{SITE_URL}/search">
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/static/fonts/poppins-800-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261009-fonts-1">
  <link rel="stylesheet" href="/static/search-page.css?v={SEARCH_CSS_VERSION}">
  {extra}
</head>
<body class="site search-page">
  <!--SITE_NAV:-->
  <main id="main">
    <section class="search-hero"><div class="site-wrap">
      <p class="site-eyebrow">Search</p>
      <h1>{_e(heading)}</h1>
      <form class="search-hero__form" action="/search" method="get" role="search" data-search-page>
        <label class="sr-only" for="search-page-q">Search titles, guides and people</label>
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
        <input id="search-page-q" type="search" name="q" value="{_e(q)}" maxlength="200" autocomplete="off" placeholder="Try Dune, Frieren, Hollow Knight, Taylor Swift…"{"" if q else " autofocus"}>
        {f'<input type="hidden" name="kind" value="{_e(kind)}">' if kind else ""}
        <button class="site-btn site-btn--primary site-btn--md" type="submit">Search</button>
      </form>
      {_chips(q if searching else "", kind, counts)}
      {hint}
    </div></section>
    <div class="site-wrap search-body">{"".join(body)}</div>
    {_guest_bar(signed_in)}
  </main>
  <!--SITE_FOOTER-->
</body>
</html>"""
    return apply_site_chrome(html, member=signed_in)


@router.get("/search", include_in_schema=False)
def search_page(request: Request, q: str = Query("", max_length=200), kind: str = Query("", max_length=20),
                db: Session = Depends(get_db)):
    signed_in = _signed_in(request)
    response = strict_html_response(render(db, q, _kind(kind), signed_in))
    response.headers["Cache-Control"] = "private, no-store" if signed_in else "public, max-age=300"
    response.headers["Vary"] = "Cookie"
    response.headers["X-Robots-Tag"] = "noindex, follow"
    return response
