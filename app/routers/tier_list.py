"""Tier list maker (/tier-list): rank movies, shows, anime, games, books or albums from S to D."""
from __future__ import annotations

import asyncio
import os
from collections import OrderedDict
from html import escape
from typing import Optional
from urllib.parse import urljoin

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import funnel, tier_list, tier_list_shares, title_pages
from ..auth import AUTH_COOKIE_NAME
from ..dependencies import get_current_user, get_db, get_optional_current_user
from ..visitor_identity import set_visitor_cookie, visitor_identity
from .discover import page

router = APIRouter(tags=["tier-list"])
CSS_VERSION = "20261117-tier-share-1"
JS_VERSION = "20261117-tier-share-1"
GUEST_LIST_JS = "/static/guest-list.js?v=20261031-browse-1"
DESCRIPTION = ("Free tier list maker for movies, TV, anime, games, books and albums. Start from a ready-made set or "
               "search any title, rank it S to D, save it as an image.")
MAX_REDIRECTS = 3
# The image proxy shares the outgoing connection pool with Google sign-in, Release Radar and
# the metadata lookups. Capping it keeps a burst of poster requests (one export asks for up to
# 30 at once) from taking every connection and stalling those.
IMAGE_CONCURRENCY = 6
IMAGE_QUEUE_SECONDS = 10.0
IMAGE_FETCH_SECONDS = 20.0
_image_slots: asyncio.Semaphore | None = None
# One visitor may hold only this many of the shared slots, so a single client firing
# requests can't keep everyone else's exports waiting.
IMAGE_SLOTS_PER_CLIENT = 2
_client_slots: dict[str, list] = {}  # client -> [semaphore, requests using it]
# Recently fetched posters, kept in memory: templates and popular titles reuse the same
# images, so most exports need no outgoing fetch at all.
IMAGE_CACHE_BYTES = 16 * 1024 * 1024
_image_cache: "OrderedDict[str, tuple[str, bytes]]" = OrderedDict()
_image_cache_size = 0


def _slots() -> asyncio.Semaphore:
    global _image_slots
    if _image_slots is None:
        _image_slots = asyncio.Semaphore(IMAGE_CONCURRENCY)
    return _image_slots


def _client_key(request) -> str:
    try:
        from ..main import client_address
        return client_address(request)
    except Exception:
        client = getattr(request, "client", None)
        return getattr(client, "host", None) or "unknown"


def _image_cache_enabled() -> bool:
    # Tests reuse poster URLs with different upstream answers.
    return os.getenv("TESTING", "").lower() != "true"


def _cached_image(url: str):
    entry = _image_cache.get(url) if _image_cache_enabled() else None
    if entry is not None:
        _image_cache.move_to_end(url)
    return entry


def _remember_image(url: str, media_type: str, body: bytes) -> None:
    global _image_cache_size
    if not _image_cache_enabled() or len(body) > IMAGE_CACHE_BYTES // 8:
        return
    previous = _image_cache.pop(url, None)
    if previous is not None:
        _image_cache_size -= len(previous[1])
    _image_cache[url] = (media_type, body)
    _image_cache_size += len(body)
    while _image_cache_size > IMAGE_CACHE_BYTES and _image_cache:
        _, (_, dropped) = _image_cache.popitem(last=False)
        _image_cache_size -= len(dropped)


def _image_response(media_type: str, body: bytes) -> Response:
    return Response(content=body, media_type=media_type, headers={
        "Cache-Control": "public, max-age=86400",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'",
    })


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _set_card(template: dict) -> str:
    posters = [item["image"] for item in template["items"] if item.get("image")][:3]
    art = "".join(f'<img src="{_e(url)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" '
                  'width="54" height="80">' for url in posters)
    if not art:
        art = f'<span class="tl-set__letter" aria-hidden="true">{_e(template["name"][:1].upper())}</span>'
    count = len(template["items"])
    return (f'<li><a class="tl-set" href="/tier-list?template={_e(template["key"])}" data-tier-template="{_e(template["key"])}" '
            f'data-tier-set-name="{_e(template["name"].casefold())}">'
            f'<span class="tl-set__art">{art}</span><span class="tl-set__text"><strong>{_e(template["name"])}</strong>'
            f'<span>{_e(count)} titles · {_e(template["blurb"])}</span></span></a></li>')


def _template_links(templates: list[dict]) -> str:
    if not templates:
        return ''
    featured = tier_list.featured(templates) or templates[:tier_list.FEATURED_SHOWN]
    shown = {template["key"] for template in featured}
    html = f'<h3 class="tl-sets__title">Popular starting sets</h3><ul class="tl-sets">{"".join(map(_set_card, featured))}</ul>'
    rest = [template for template in templates if template["key"] not in shown]
    if rest:
        groups = []
        for group, label in tier_list.GROUPS:
            members = [template for template in rest if template.get("group") == group]
            if members:
                groups.append(f'<div class="tl-sets__group" data-tier-set-group><h4>{_e(label)}</h4>'
                              f'<ul class="tl-sets tl-sets--compact">{"".join(map(_set_card, members))}</ul></div>')
        html += (f'<details class="tl-sets-all"><summary>Browse all {_e(len(templates))} starting sets</summary>'
                 '<label class="tl-sets-all__filter"><span class="sr-only">Filter starting sets</span>'
                 '<input type="search" maxlength="60" autocomplete="off" placeholder="Filter: Zelda, Bond, anime…" '
                 'data-tier-set-filter></label>'
                 f'{"".join(groups)}<p class="tl-empty" data-tier-set-none hidden>No starting set matches that. '
                 'Search for titles below instead.</p></details>')
    return html


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
def tier_list_page(request: Request, template: str = Query("", max_length=40), remix: str = Query("", max_length=40),
                   edit: str = Query("", max_length=40), db: Session = Depends(get_db)):
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    remix = remix if tier_list_shares.valid_token(remix) else ""
    edit = edit if tier_list_shares.valid_token(edit) else ""
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
        '<p>Movies, TV shows, anime, games, books or albums. Start from a whole franchise or search for titles, drag them into '
        'tiers, then share a link your friends can rank too. Free, and no account needed.</p></header>'
        f'<section class="tl-tool" id="tierTool" data-signed-in="{"true" if signed_in else "false"}" '
        f'data-template="{_e(template)}" data-remix="{_e(remix)}" data-edit="{_e(edit)}" aria-label="Tier list maker">'
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
        '<div class="tl-compare" data-tier-compare hidden aria-live="polite"></div>'
        '<div class="tl-move" data-tier-move hidden role="group" aria-label="Move the selected title">'
        '<p class="tl-move__title" data-tier-move-title></p><div class="tl-move__buttons"></div></div>'
        '<noscript><p>The tier list maker needs JavaScript. The guide below works without it.</p></noscript></div>'
        '<div class="tl-actions"><h2>3. Save and share</h2>'
        '<div class="tl-linkbox" data-tier-linkbox><p class="tl-linkbox__lead"><strong>Share it as a link.</strong> Friends see '
        'your board with every poster, and can rank the same titles themselves to see how much you agree.</p>'
        '<div class="tl-row"><button type="button" class="button" data-tier-link>Get a share link</button></div>'
        '<div class="tl-link" data-tier-link-ready hidden><label class="sr-only" for="tlLink">Your tier list link</label>'
        '<div class="tl-row"><input id="tlLink" type="text" readonly data-tier-link-url>'
        '<button type="button" class="button" data-tier-link-copy>Copy link</button>'
        '<button type="button" class="button button--ghost" data-tier-link-share hidden>Share</button>'
        '<a class="button button--ghost" data-tier-link-open href="/tier-list" target="_blank" rel="noopener">Open</a></div>'
        '<p class="tl-link__note muted" data-tier-link-note></p></div></div>'
        '<div class="tl-row tl-row--export">'
        '<button type="button" class="button button--ghost" data-tier-export>Save as image</button>'
        '<button type="button" class="button button--ghost" data-tier-share hidden>Share image</button>'
        '<button type="button" class="button button--ghost" data-tier-clear>Start over</button></div>'
        '<p class="tl-status" data-tier-status role="status" aria-live="polite"></p>'
        '<img class="tl-preview" data-tier-preview alt="Preview of your tier list image" hidden>'
        + ('' if signed_in else
           '<div class="tl-cta" data-tier-cta hidden><p><strong>Keep these rankings.</strong> Links made without an account '
           f'stay up for {tier_list_shares.GUEST_DAYS} days. A free account keeps every tier list you share, shows how many '
           'people opened each one, and turns your own ratings into a tier list in one click.</p>'
           '<a class="button" href="/?next=%2Ftier-list#signup" data-tier-signup>Create a free account</a> '
           '<button type="button" class="button button--ghost" data-tier-save-guest>Save ranked titles to my list</button></div>')
        + '</div></section>'
        + ('<section class="tl-mine" data-tier-mine hidden aria-labelledby="tlMineTitle"><h2 id="tlMineTitle">Your shared tier lists</h2>'
           '<ul class="tl-mine__list" data-tier-mine-list></ul></section>' if signed_in else '')
        + GUIDE
    )
    head = f'<link rel="stylesheet" href="/static/tier-list.css?v={CSS_VERSION}">'
    if not signed_in:
        head += f'<script src="{GUEST_LIST_JS}" defer></script>'
    head += f'<script src="/static/tier-list.js?v={JS_VERSION}" defer></script>'
    response = page("Tier list maker for movies, TV, anime, games and books", DESCRIPTION, "/tier-list", content,
                    indexable=not (template or remix or edit), head=head,
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
def tier_list_templates(request: Request, response: Response, key: str = Query("", max_length=60),
                        db: Session = Depends(get_db)):
    """Ready-made starting sets with titles, years and artwork (no member data); ?key= returns just one."""
    response.headers["Cache-Control"] = "public, max-age=600"
    if key:
        found = tier_list.find_template(db, key)
        return {"templates": [found] if found else []}
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
    cached = _cached_image(url)
    if cached is not None:
        return _image_response(*cached)
    client = getattr(request.app.state, "external_api_client", None)
    if client is None:
        raise HTTPException(503, "Images unavailable")
    key = _client_key(request)
    mine = _client_slots.setdefault(key, [asyncio.Semaphore(IMAGE_SLOTS_PER_CLIENT), 0])
    mine[1] += 1
    try:
        deadline = asyncio.get_running_loop().time() + IMAGE_QUEUE_SECONDS
        try:
            await asyncio.wait_for(mine[0].acquire(), timeout=IMAGE_QUEUE_SECONDS)
        except asyncio.TimeoutError:
            raise HTTPException(503, "Images are busy, try again in a moment")
        try:
            slots = _slots()
            try:
                remaining = max(0.0, deadline - asyncio.get_running_loop().time())
                await asyncio.wait_for(slots.acquire(), timeout=remaining)
            except asyncio.TimeoutError:
                raise HTTPException(503, "Images are busy, try again in a moment")
            try:
                # A whole fetch, redirects included, gets a hard deadline so a trickling host can't hold a slot.
                media_type, body = await asyncio.wait_for(_fetch_image(client, url), timeout=IMAGE_FETCH_SECONDS)
            except asyncio.TimeoutError:
                raise HTTPException(504, "Image took too long")
            finally:
                slots.release()
        finally:
            mine[0].release()
    finally:
        mine[1] -= 1
        if mine[1] == 0 and _client_slots.get(key) is mine:
            del _client_slots[key]
    _remember_image(url, media_type, body)
    return _image_response(media_type, body)


async def _fetch_image(client, url: str) -> tuple[str, bytes]:
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
                return media_type, bytes(body)
        raise HTTPException(404, "Too many redirects")
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, "Image unavailable")


# ---------------------------------------------------------------- shared tier lists

class ShareBody(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    labels: Optional[dict] = None
    tiers: dict = Field(default_factory=dict)
    template: Optional[str] = Field(None, max_length=60)
    source: Optional[str] = Field(None, max_length=40)
    key: Optional[str] = Field(None, max_length=80)


class ShareKey(BaseModel):
    key: Optional[str] = Field(None, max_length=80)


class ClaimLink(BaseModel):
    token: str = Field(..., max_length=40)
    key: str = Field(..., max_length=80)


class ClaimBody(BaseModel):
    links: list[ClaimLink] = Field(default_factory=list, max_length=tier_list_shares.CLAIM_MAX)


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"


def _fail(error: tier_list_shares.ShareError):
    raise HTTPException(error.status, error.message)


def _share_or_404(db: Session, token: str, *, lock: bool = False):
    share = tier_list_shares.by_token(db, token, lock=lock)
    if share is None:
        raise HTTPException(404, "This tier list link isn't here anymore")
    return share


def _link_reply(share, key: Optional[str] = None) -> dict:
    reply = {"token": share.token, "path": tier_list_shares.path_for(share),
             "url": f"https://omnitrackr.xyz{tier_list_shares.path_for(share)}", "count": share.item_count,
             "member": share.owner_id is not None,
             "expires_at": share.expires_at.isoformat() + "Z" if share.expires_at else None}
    if key:
        reply["key"] = key
    return reply


@router.post("/api/tier-list/shares")
def create_share(payload: ShareBody, request: Request, response: Response,
                 user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    """Turn a ranked board into a link. Works without an account (the link then lasts GUEST_DAYS)."""
    _private(response)
    visitor, new_cookie = None, None
    if user is None:
        visitor, new_cookie, _ = visitor_identity(request)
    try:
        share, key = tier_list_shares.create(db, user, visitor, payload.model_dump())
    except tier_list_shares.ShareError as error:
        _fail(error)
    set_visitor_cookie(response, new_cookie)
    funnel.record("tier_list_link_created", request)
    return _link_reply(share, key)


@router.get("/api/tier-list/shares/mine")
def my_shares(request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    return {"links": tier_list_shares.mine(db, user)}


@router.post("/api/tier-list/shares/claim")
def claim_shares(payload: ClaimBody, request: Request, response: Response,
                 user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Links this browser made before signing up move into the account and stop expiring."""
    _private(response)
    claimed = tier_list_shares.claim(db, user, [link.model_dump() for link in payload.links])
    if claimed:
        funnel.record("tier_list_link_claimed", request)
    return {"claimed": claimed}


@router.get("/api/tier-list/shares/{token}")
def get_share(token: str, request: Request, response: Response, db: Session = Depends(get_db)):
    _private(response)
    return tier_list_shares.public_state(db, _share_or_404(db, token))


@router.put("/api/tier-list/shares/{token}")
def update_share(token: str, payload: ShareBody, request: Request, response: Response,
                 user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    _private(response)
    share = _share_or_404(db, token, lock=True)
    try:
        share = tier_list_shares.update(db, share, user, payload.model_dump())
    except tier_list_shares.ShareError as error:
        _fail(error)
    return _link_reply(share)


@router.delete("/api/tier-list/shares/{token}", status_code=204)
def delete_share(token: str, request: Request, payload: Optional[ShareKey] = None,
                 user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    share = _share_or_404(db, token, lock=True)
    try:
        tier_list_shares.delete(db, share, user, payload.key if payload else None)
    except tier_list_shares.ShareError as error:
        _fail(error)
    response = Response(status_code=204)
    _private(response)
    return response


def _shared_not_found():
    from ..csp import strict_html_response
    from ..site_chrome import message_page
    response = strict_html_response(message_page(
        "Tier list not found", "This tier list link isn't here anymore",
        "Whoever made it may have deleted it, or it was made without an account and its 30 days ran out. "
        "You can rank the same kind of titles yourself in a minute.",
        actions=(("Make a tier list", "/tier-list"), ("See what OmniTrackr does", "/about"))), status_code=404)
    _private(response)
    return response


def _person(request: Request) -> bool:
    from ..site_traffic import BOT_PATTERN
    agent = request.headers.get("user-agent", "")
    purpose = (request.headers.get("sec-purpose", "") + request.headers.get("purpose", "")).lower()
    return bool(agent) and not BOT_PATTERN.search(agent) and "prefetch" not in purpose and "prerender" not in purpose


def _shared_tile(item: dict) -> str:
    meta = " · ".join(str(part) for part in (title_pages.KINDS[item["kind"]][3] if item.get("kind") else "", item.get("year") or "") if part)
    label = f'{item["title"]}{f", {meta}" if meta else ""}'
    if item.get("image"):
        inner = (f'<img src="{_e(item["image"])}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" '
                 f'width="72" height="108"><span class="tl-tile__title">{_e(item["title"])}</span>')
        cls = "tl-tile tl-tile--static"
    else:
        inner = f'<span class="tl-tile__title">{_e(item["title"])}</span>'
        cls = "tl-tile tl-tile--static tl-tile--text"
    if item.get("kind") and item.get("slug"):
        return (f'<a class="{cls}" href="/titles/{_e(item["kind"])}/{_e(item["slug"])}" title="{_e(item["title"])}" '
                f'aria-label="{_e(label)}">{inner}</a>')
    return f'<span class="{cls}" title="{_e(item["title"])}" role="img" aria-label="{_e(label)}">{inner}</span>'


def _shared_board(data: dict) -> str:
    rows = []
    for tier in tier_list.TIERS:
        items = data["tiers"][tier]
        tiles = "".join(_shared_tile(item) for item in items) or '<span class="tl-empty tl-empty--row">Nothing here</span>'
        rows.append(f'<div class="tl-tier"><div class="tl-tier__label tl-tier__label--{tier.lower()}">'
                    f'<span class="tl-tier__name">{_e(data["labels"][tier])}</span></div>'
                    f'<div class="tl-tier__items">{tiles}</div></div>')
    return f'<div class="tl-board tl-board--shared">{"".join(rows)}</div>'


def _top_titles(data: dict, limit: int = 3) -> list[str]:
    return [item["title"] for tier in tier_list.TIERS for item in data["tiers"][tier]][:limit]


@router.get("/tier-list/s/{token}", include_in_schema=False)
def shared_tier_list(token: str, request: Request, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    share = tier_list_shares.by_token(db, token)
    if share is None:
        return _shared_not_found()
    visitor, _, retained = visitor_identity(request)
    made_here = retained and share.owner_id is None and share.visitor == visitor
    owner = (user is not None and share.owner_id == user.id) or made_here
    # Chat apps fetch the page to unfurl it, and browsers prefetch it; neither is someone opening the link.
    if not owner and _person(request):
        tier_list_shares.count_view(db, share)
        if user is None:
            funnel.record("tier_list_link_opened", request)
    state = tier_list_shares.public_state(db, share)
    credit = tier_list_shares.credit(db, share)
    by_html = (f'<a href="{_e(credit[1])}">{_e(credit[0])}</a>' if credit else _e(state["by"]))
    top = _top_titles(state)
    s_tier = [item["title"] for item in state["tiers"]["S"]][:3]
    description = (f'{share.name}: a tier list by {state["by"]} with {share.item_count} titles.'
                   + (f' {state["labels"]["S"]} tier: {", ".join(s_tier)}.' if s_tier else '')
                   + ' Rank the same titles yourself and see how much you agree.')
    counts = []
    if state["views"] >= 3:
        counts.append(f'opened {state["views"]:,} times')
    if state["remixes"]:
        counts.append(f'{state["remixes"]:,} {"person has" if state["remixes"] == 1 else "people have"} ranked it themselves')
    source = (f'<p class="tl-shared__source">A take on <a href="{_e(state["source"]["path"])}">{_e(state["source"]["name"])}</a></p>'
              if state["source"] else '')
    signed_in = user is not None
    guest_cta = '' if signed_in else (
        '<aside class="tl-cta tl-cta--shared"><p><strong>Track everything you rank.</strong> OmniTrackr is a free library for '
        'movies, TV, anime, games, books, music and more. Rate what you finish and your tier lists build themselves.</p>'
        '<a class="button" href="/?next=%2Ftier-list#signup" data-tier-signup>Create a free account</a> '
        '<a class="button button--ghost" href="/tier-list">Make a tier list without one</a></aside>')
    templates = tier_list.featured(tier_list.templates(db))[:4]
    more = (f'<section class="tl-shared__more"><h2>More tier lists to make</h2><ul class="tl-sets">'
            f'{"".join(map(_set_card, templates))}</ul></section>' if templates else '')
    content = (
        f'<article class="tl-shared" id="tierShare" data-token="{_e(share.token)}" data-owner="{"true" if owner else "false"}">'
        '<header class="hero tl-hero tl-shared__head"><p class="eyebrow">TIER LIST</p>'
        f'<h1>{_e(share.name)}</h1>'
        f'<p class="tl-shared__by">By {by_html} · {_e(share.item_count)} titles'
        f'{" · " + _e(", ".join(counts)) if counts else ""}</p>{source}</header>'
        f'{_shared_board(state)}'
        '<div class="tl-shared__actions">'
        f'<a class="button" href="/tier-list?remix={_e(share.token)}" data-tier-remix>Rank these yourself</a>'
        '<button type="button" class="button button--ghost" data-tier-shared-copy>Copy link</button>'
        '<button type="button" class="button button--ghost" data-tier-shared-share hidden>Share</button></div>'
        '<p class="tl-shared__hint muted">Same titles, your order. When you finish, you see how many you put in the same tier.'
        + (f' Top of this list: {_e(", ".join(top))}.' if top else '') + '</p>'
        '<p class="tl-status" data-tier-status role="status" aria-live="polite"></p>'
        '<div class="tl-owner" data-tier-owner' + ('' if owner else ' hidden') + '><p><strong>This is your tier list.</strong> '
        'Changes you make on the maker update this link.</p>'
        f'<a class="button button--ghost" href="/tier-list?edit={_e(share.token)}">Edit it</a> '
        '<button type="button" class="button button--ghost" data-tier-shared-delete>Delete this link</button></div>'
        f'{guest_cta}{more}</article>'
    )
    head = (f'<link rel="stylesheet" href="/static/tier-list.css?v={CSS_VERSION}">'
            f'<script src="/static/tier-list.js?v={JS_VERSION}" defer></script>')
    card = f"https://omnitrackr.xyz/tier-list/s/{share.token}/card.png?v={tier_list_shares.fingerprint(share, state['by'])}"
    response = page(f"{share.name} · tier list", description, tier_list_shares.path_for(share), content,
                    indexable=False, head=head, member=signed_in, share_image=card)
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Vary"] = "Cookie"
    return response


_SHARE_CARDS = None
CARD_POSTERS_MAX = 60
CARD_POSTER_SECONDS = 8.0
CARD_FETCH_SLOTS = 3  # of the IMAGE_CONCURRENCY shared slots, at most this many go to share cards
_card_fetch_slots: asyncio.Semaphore | None = None


def _share_cards():
    global _SHARE_CARDS
    if _SHARE_CARDS is None:
        from .profiles import _CardCache
        _SHARE_CARDS = _CardCache(size=64)
    return _SHARE_CARDS


def _card_slots() -> asyncio.Semaphore:
    global _card_fetch_slots
    if _card_fetch_slots is None:
        _card_fetch_slots = asyncio.Semaphore(CARD_FETCH_SLOTS)
    return _card_fetch_slots


async def _poster_bytes(client, url: str):
    cached = _cached_image(url)
    if cached is not None:
        return cached[1]
    # Cards wait for their own few slots first, so one card asking for 60 posters can't take
    # every shared slot and stall people saving their tier list as an image.
    card_slots = _card_slots()
    await card_slots.acquire()
    try:
        slots = _slots()
        await slots.acquire()
        try:
            media_type, body = await asyncio.wait_for(_fetch_image(client, url), timeout=IMAGE_FETCH_SECONDS)
        finally:
            slots.release()
    finally:
        card_slots.release()
    _remember_image(url, media_type, body)
    return body


async def _card_posters(request: Request, data: dict) -> dict:
    client = getattr(request.app.state, "external_api_client", None)
    wanted = [(tier, index, item["image"]) for tier, index, item in tier_list_shares.card_items(data) if item.get("image")]
    wanted = wanted[:CARD_POSTERS_MAX]
    if client is None or not wanted:
        return {}
    urls = list(dict.fromkeys(url for _, _, url in wanted))
    tasks = {url: asyncio.ensure_future(_poster_bytes(client, url)) for url in urls}
    done, pending = await asyncio.wait(tasks.values(), timeout=CARD_POSTER_SECONDS)
    for task in pending:
        task.cancel()
    bodies = {}
    for url, task in tasks.items():
        if task in done and not task.cancelled() and task.exception() is None:
            bodies[url] = task.result()
    return {(tier, index): bodies[url] for tier, index, url in wanted if url in bodies}


@router.get("/tier-list/s/{token}/card.png", include_in_schema=False)
async def shared_tier_list_card(token: str, request: Request, db: Session = Depends(get_db)):
    """The picture chat apps show for a shared link: the five tiers with their posters."""
    def facts():
        share = tier_list_shares.by_token(db, token)
        if share is None:
            return None
        by = tier_list_shares.byline(db, share)
        return share.id, share.name, tier_list_shares.board(share), by, tier_list_shares.fingerprint(share, by)
    found = await run_in_threadpool(facts)
    if found is None:
        raise HTTPException(404, "This tier list link isn't here anymore")
    share_id, name, data, by, fingerprint = found
    etag = f'"{fingerprint}"'
    headers = {"Cache-Control": "public, max-age=3600", "ETag": etag, "X-Content-Type-Options": "nosniff",
               "X-Robots-Tag": "noindex"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    cache = _share_cards()
    png = cache.get((share_id, fingerprint))
    if png is None:
        posters = await _card_posters(request, data)
        try:
            png = await run_in_threadpool(tier_list_shares.render_card, name, data, by, posters)
        except Exception:
            raise HTTPException(404, "Card unavailable")
        cache.put((share_id, fingerprint), png)
    return Response(content=png, media_type="image/png", headers=headers)
