"""Tier list maker (/tier-list): rank movies, shows, anime, games, books or albums from S to D."""
from __future__ import annotations

from html import escape
from urllib.parse import urljoin

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from .. import tier_list, title_pages
from ..auth import AUTH_COOKIE_NAME
from ..dependencies import get_current_user, get_db
from .discover import page

router = APIRouter(tags=["tier-list"])
CSS_VERSION = "20261015-tier-1"
JS_VERSION = "20261015-tier-1"
GUEST_LIST_JS = "/static/guest-list.js?v=20261012-hero-search-1"
DESCRIPTION = ("Free tier list maker for movies, TV shows, anime, video games, books and albums. Start from a ready-made "
               "set or search any title, drag it from S to D, and save the finished list as an image. No account needed.")
MAX_REDIRECTS = 3


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _template_links(templates: list[dict]) -> str:
    if not templates:
        return ''
    links = "".join(
        f'<li><a class="tl-start__link" href="/tier-list?template={_e(t["key"])}" data-tier-template="{_e(t["key"])}">'
        f'<strong>{_e(t["name"])}</strong><span>{_e(len(t["items"]))} titles · {_e(t["blurb"])}</span></a></li>'
        for t in templates)
    return f'<ul class="tl-start__list">{links}</ul>'


GUIDE = (
    '<section class="editorial tl-guide"><h2>How to make a tier list that says something</h2>'
    '<p>A tier list is a ranking with room to breathe. Instead of forcing every title into an exact order, you sort them '
    'into a handful of shelves and let titles share a shelf when they really are about as good as each other. That makes '
    'it quicker than a numbered top 20, and far more honest than a single score.</p>'
    '<p>Start with the obvious ones. Put your clear favourites in S and the ones you would not revisit in D, then work '
    'inward. The middle tiers are where the interesting arguments happen, so spend your time there. If a title keeps '
    'bouncing between two shelves, leave it in the lower one: a tier list reads best when the top is hard to reach.</p>'
    '<p>Rename the tiers when the letters do not fit. "Rewatch every year", "Glad I saw it once" and "Not for me" can say '
    'more than S, B and D, and tiers like "Comfort shows" or "Still thinking about it" turn a ranking into a recommendation.</p>'
    '</section>'
    '<section class="editorial tl-guide"><h2>What the tiers usually mean</h2>'
    '<dl class="tl-legend">'
    '<div><dt>S</dt><dd>All-time favourites. You would recommend them to anyone and return to them yourself.</dd></div>'
    '<div><dt>A</dt><dd>Excellent, with a small reservation that keeps them out of S.</dd></div>'
    '<div><dt>B</dt><dd>Good and worth the time, but not one you think about afterwards.</dd></div>'
    '<div><dt>C</dt><dd>Mixed. Some parts worked, others did not, and you would not go back.</dd></div>'
    '<div><dt>D</dt><dd>Not for you. A tier list is about your taste, so this is a statement about fit, not quality.</dd></div>'
    '</dl></section>'
    '<section class="editorial tl-guide"><h2>Tier list ideas to try</h2>'
    '<ul><li>Every anime you watched this season, before the next one starts.</li>'
    '<li>A director\'s or author\'s whole body of work, oldest to newest.</li>'
    '<li>The games in your backlog, ranked by how much you want to play them next.</li>'
    '<li>Every film in a franchise, then compare with a friend\'s list of the same set.</li>'
    '<li>Albums you played most this year, as a warm-up for your Year in Review.</li></ul>'
    '<p>Your board is saved in this browser as you go, and nothing is sent to OmniTrackr. With a free account you can turn '
    'your own ratings into a tier list in one click, keep your rankings next to the reviews that explain them, and see '
    'which titles you have not rated yet. <a href="/guides">More guides</a> · <a href="/pick">Pick for me</a></p></section>'
)


@router.get("/tier-list", include_in_schema=False)
def tier_list_page(request: Request, template: str = Query("", max_length=40), db: Session = Depends(get_db)):
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    templates = tier_list.templates(db)
    kinds = "".join(f'<option value="{kind}">{_e(tier_list.KIND_PLURALS[kind].capitalize())}</option>'
                    for kind in tier_list.KIND_ORDER)
    library = (
        '<form class="tl-library" data-tier-library><label for="tlLibraryKind">Rank my library by my ratings</label>'
        f'<div class="tl-row"><select id="tlLibraryKind" name="kind">{kinds}</select>'
        '<button type="submit" class="button">Use my ratings</button></div>'
        '<p class="muted">Titles rated 9 or more start in S, 8 in A, 7 in B, 5.5 in C and lower in D. Unrated titles wait '
        'below the board. Your library is not changed.</p></form>'
        if signed_in else
        '<p class="tl-library tl-library--guest">Have a library on OmniTrackr? <a href="/?login=1">Log in</a> to turn your own '
        'ratings into a tier list in one click.</p>'
    )
    tiers = "".join(
        f'<div class="tl-tier" data-tier-row="{tier}"><div class="tl-tier__label tl-tier__label--{tier.lower()}">{tier}</div>'
        '<div class="tl-tier__items"></div></div>' for tier in tier_list.TIERS)
    content = (
        '<header class="hero tl-hero"><p class="eyebrow">TIER LIST MAKER</p>'
        '<h1>Rank anything from S to D</h1>'
        '<p>Movies, TV shows, anime, games, books or albums. Start from a ready-made set or search for titles, drag them into '
        'tiers, and save the result as an image to share. Free, and no account needed.</p></header>'
        f'<section class="tl-tool" id="tierTool" data-signed-in="{"true" if signed_in else "false"}" '
        f'data-template="{_e(template)}" aria-label="Tier list maker">'
        '<div class="tl-start"><h2>1. Choose what to rank</h2>'
        f'{_template_links(templates)}'
        '<form class="tl-search" role="search" data-tier-search><label for="tlSearch">Or search titles members track</label>'
        '<input id="tlSearch" type="search" autocomplete="off" maxlength="80" placeholder="Try Frieren, Hades or Dune">'
        '<div class="tl-search__results" data-tier-results hidden></div></form>'
        '<form class="tl-custom" data-tier-custom><label for="tlCustom">Or add any title by name</label>'
        '<div class="tl-row"><input id="tlCustom" type="text" maxlength="120" autocomplete="off" placeholder="Any title">'
        '<button type="submit" class="button button--ghost">Add</button></div></form>'
        f'{library}</div>'
        '<div class="tl-board-wrap"><h2>2. Rank them</h2>'
        '<p class="tl-hint muted">Drag a title into a tier, or tap it and choose a tier. Tap a tier letter to rename it.</p>'
        '<label class="tl-name"><span class="sr-only">Tier list name</span>'
        '<input id="tlName" type="text" maxlength="80" value="My tier list" data-tier-name></label>'
        f'<div class="tl-board" id="tierBoard">{tiers}</div>'
        '<div class="tl-pool"><h3>Not ranked yet <span data-tier-pool-count></span></h3>'
        '<div class="tl-pool__items" data-tier-pool><p class="tl-empty">Choose a set above or search for titles to begin.</p></div></div>'
        '<div class="tl-move" data-tier-move hidden role="group" aria-label="Move the selected title">'
        '<p class="tl-move__title" data-tier-move-title></p><div class="tl-move__buttons"></div></div>'
        '<noscript><p>The tier list maker needs JavaScript. The guide below works without it.</p></noscript></div>'
        '<div class="tl-actions"><h2>3. Save and share</h2><div class="tl-row">'
        '<button type="button" class="button" data-tier-export>Save as image</button>'
        '<button type="button" class="button button--ghost" data-tier-share hidden>Share image</button>'
        '<button type="button" class="button button--ghost" data-tier-clear>Start over</button></div>'
        '<p class="tl-status" data-tier-status role="status" aria-live="polite"></p>'
        '<img class="tl-preview" data-tier-preview alt="Preview of your tier list image" hidden>'
        + ('' if signed_in else
           '<div class="tl-cta" data-tier-cta hidden><p><strong>Keep these rankings.</strong> Save the titles you ranked to a '
           'list, then create a free library to rate and review them.</p>'
           '<button type="button" class="button" data-tier-save-guest>Save ranked titles to my list</button> '
           '<a class="button button--ghost" href="/#signup">Create a free library</a></div>')
        + '</div></section>'
        + GUIDE
    )
    head = f'<link rel="stylesheet" href="/static/tier-list.css?v={CSS_VERSION}">'
    if not signed_in:
        head += f'<script src="{GUEST_LIST_JS}" defer></script>'
    head += f'<script src="/static/tier-list.js?v={JS_VERSION}" defer></script>'
    response = page("Tier list maker for movies, TV, anime, games and books", DESCRIPTION, "/tier-list", content,
                    indexable=not template, head=head,
                    structured_data={
                        "@context": "https://schema.org", "@type": "WebApplication",
                        "name": "OmniTrackr tier list maker", "description": DESCRIPTION,
                        "url": "https://omnitrackr.xyz/tier-list", "applicationCategory": "EntertainmentApplication",
                        "operatingSystem": "Any", "inLanguage": "en-US", "isAccessibleForFree": True,
                        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
                        "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": "https://omnitrackr.xyz/"},
                    })
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


@router.get("/api/tier-list/templates")
def tier_list_templates(request: Request, response: Response, db: Session = Depends(get_db)):
    """Ready-made starting sets with titles, years and artwork (no member data)."""
    response.headers["Cache-Control"] = "public, max-age=600"
    return {"templates": tier_list.templates(db)}


@router.get("/api/tier-list/library")
def tier_list_library(request: Request, response: Response, kind: str = Query(..., max_length=10),
                      user=Depends(get_current_user), db: Session = Depends(get_db)):
    """The signed-in member's own titles of one kind, each with the tier their rating suggests."""
    response.headers["Cache-Control"] = "private, no-store"
    if kind not in title_pages.KINDS:
        raise HTTPException(400, "Unknown kind")
    return {"kind": kind, "items": tier_list.library_items(db, user, kind)}


@router.get("/api/tier-list/image")
async def tier_list_image(request: Request, url: str = Query(..., max_length=1000)):
    """Same-origin copy of a poster so the browser can draw it onto the exported image.

    Only allowlisted poster hosts, at most a few redirects (each re-checked), image
    types only, and a hard size cap. Nothing is stored.
    """
    if not tier_list.image_allowed(url):
        raise HTTPException(400, "Image host not allowed")
    client = getattr(request.app.state, "external_api_client", None)
    if client is None:
        raise HTTPException(503, "Images unavailable")
    current = url
    try:
        for _ in range(MAX_REDIRECTS + 1):
            async with client.stream("GET", current, headers={"Accept": "image/*"}) as upstream:
                if upstream.status_code in (301, 302, 303, 307, 308):
                    current = urljoin(current, upstream.headers.get("location", ""))
                    if not tier_list.image_allowed(current):
                        raise HTTPException(400, "Image host not allowed")
                    continue
                if upstream.status_code != 200:
                    raise HTTPException(404, "Image not found")
                media_type = (upstream.headers.get("content-type") or "").split(";")[0].strip().lower()
                if media_type not in tier_list.IMAGE_TYPES:
                    raise HTTPException(415, "Not an image")
                declared = upstream.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > tier_list.IMAGE_MAX_BYTES:
                    raise HTTPException(413, "Image too large")
                body = bytearray()
                async for chunk in upstream.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > tier_list.IMAGE_MAX_BYTES:
                        raise HTTPException(413, "Image too large")
                return Response(content=bytes(body), media_type=media_type, headers={
                    "Cache-Control": "public, max-age=86400",
                    "X-Content-Type-Options": "nosniff",
                    "Content-Security-Policy": "default-src 'none'",
                })
        raise HTTPException(404, "Too many redirects")
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, "Image unavailable")
