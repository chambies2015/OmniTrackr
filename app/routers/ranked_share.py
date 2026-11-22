"""The page and pictures behind a shared Rankings top ten, /ranked/<token> (see app/ranking_shares.py)."""
from __future__ import annotations

import asyncio
from html import escape
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import funnel, ranking_shares, rankings
from ..dependencies import get_db, get_optional_current_user

router = APIRouter(tags=["rankings"])
CSS_VERSION = "20261122-ranked-share-1"
JS_VERSION = "20261122-ranked-share-1"
SITE = "https://omnitrackr.xyz"
CARD_POSTER_SECONDS = 8.0


def _e(value) -> str:
    return escape(str(value), quote=True)


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Vary"] = "Cookie"


def _person(request: Request) -> bool:
    from .tier_list import _person as person
    return person(request)


def _not_found():
    from ..csp import strict_html_response
    from ..site_chrome import message_page
    response = strict_html_response(message_page(
        "Ranking not found", "This top ten isn't shared anymore",
        "Whoever shared it may have turned the link off or made that shelf private. "
        "You can rank what you've finished yourself, two titles at a time.",
        actions=(("Create a free account", "/#signup"), ("See what OmniTrackr does", "/about"))),
        status_code=404)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _item_html(item: dict) -> str:
    place = item["position"]
    medal = f" rk-item--{place}" if place <= 3 else ""
    lazy = "" if place <= 4 else ' loading="lazy"'
    if item.get("image"):
        art = (f'<img src="{_e(item["image"])}" alt="" width="64" height="96" decoding="async" '
               f'referrerpolicy="no-referrer"{lazy}>')
    else:
        art = f'<span>{_e(item["title"][:1].upper())}</span>'
    title = (f'<a class="rk-item__title" href="{_e(item["url"])}">{_e(item["title"])}</a>' if item.get("url")
             else f'<span class="rk-item__title">{_e(item["title"])}</span>')
    meta = " · ".join(str(part) for part in (item.get("creator"), item.get("year")) if part)
    attributes = f'data-rk-item data-title="{_e(item["title"])}" data-position="{place}"'
    if item.get("image"):
        attributes += f' data-image="{_e(item["image"])}"'
    if meta:
        attributes += f' data-meta="{_e(meta)}"'
    small = f"<small>{_e(meta)}</small>" if meta else ""
    return (f'<li class="rk-item{medal}" {attributes}>'
            f'<span class="rk-item__place" aria-hidden="true">{place}</span>'
            f'<span class="rk-item__art" aria-hidden="true">{art}</span>'
            f'<span class="rk-item__copy">{title}{small}</span></li>')


def _description(data: dict) -> str:
    names = [item["title"] for item in data["items"][:3]]
    lead = f'{ranking_shares.heading(data)}, picked two at a time on OmniTrackr'
    return (f'{lead}. Number one: {names[0]}, then {names[1]} and {names[2]}. '
            f'Rank the same {data["nouns"]} yourself and see how much you agree.')


@router.get(ranking_shares.BASE_PATH + "/{token}", include_in_schema=False)
def ranked_page(token: str, request: Request, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    share = ranking_shares.by_token(db, token)
    data = ranking_shares.view(db, share) if share is not None else None
    if data is None:
        return _not_found()
    owner = user is not None and user.id == data["owner_id"]
    # Chat apps fetch the page to show a preview and browsers prefetch it; neither is someone opening the link.
    if not owner and _person(request):
        ranking_shares.count_open(db, share)
        rankings.count("link_opened")
        if user is None:
            funnel.record("rank_link_opened", request)
    signed_in = user is not None
    heading = ranking_shares.heading(data)
    count = len(data["items"])
    nouns, noun = data["nouns"], data["noun"]
    by = (f'<a href="{_e(data["profile"])}">{_e(data["by"])}</a>' if data.get("by") and data.get("profile")
          else "")
    who = f"{by}'s" if by else "their"
    lead = (f'In order, best first, out of {data["total"]:,} {nouns if data["total"] != 1 else noun} in {who} ranking. '
            f'Every place was settled by picking the one they liked more, two at a time.')
    more = data["total"] - count
    more_html = (f'<p class="rk-more">{more:,} more ranked below these.</p>' if more > 0 else '')
    items = "".join(_item_html(item) for item in data["items"])
    next_path = quote(data["path"], safe="")
    signup = f"/?next={next_path}#signup"
    owner_html = ('<aside class="rk-owner" data-rk-owner>'
                  '<p><strong>This is your link.</strong> It always shows your current top ten, '
                  'so it changes as you rank. Nobody sees your scores.'
                  + (f' Opened {data["opened"]:,} time{"" if data["opened"] == 1 else "s"} so far.' if data["opened"] else '')
                  + '</p><div class="rk-actions">'
                  '<button type="button" class="button" data-rk-copy>Copy link</button>'
                  '<button type="button" class="button button--ghost" data-rk-share hidden>Share</button>'
                  f'<button type="button" class="button button--ghost" data-rk-story data-src="{_e(data["path"])}/story.png">Save image for stories</button>'
                  '<a class="button button--ghost" href="/#rankings">Open Rankings</a></div>'
                  '<p class="rk-status" data-rk-owner-status role="status" aria-live="polite"></p></aside>') if owner else ''
    guest_html = '' if signed_in else (
        '<aside class="rk-cta"><div><p class="rk-cta__title">Rank everything you\'ve finished</p>'
        '<p>OmniTrackr is a free library for films, TV, anime, games, books, albums, manga, podcasts and audiobooks. '
        'Mark what you finish, pick between two at a time, and your own top ten builds itself. Your rankings stay private '
        'until you share them.</p></div>'
        f'<a class="button" href="{_e(signup)}" data-rk-signup>Create a free account</a></aside>')
    content = (
        f'<article class="rk-share" id="rankedShare" data-format="{_e(data["category"])}" data-token="{_e(data["token"])}"'
        f' data-nouns="{_e(nouns)}" data-noun="{_e(noun)}" data-verb="{_e(data["verb"])}"'
        f' data-by="{_e(data["by"] or "")}" data-member="{"true" if signed_in else "false"}"'
        f' data-owner="{"true" if owner else "false"}" data-signup="{_e(signup)}">'
        '<header class="rk-head">'
        f'<p class="eyebrow rk-eyebrow">Top {count} {_e(nouns)} · ranked two at a time</p>'
        f'<h1>{_e(heading)}</h1><p class="rk-lead">{lead}</p>'
        '<a class="rk-jump" href="#rankPlay">Rank them yourself ↓</a></header>'
        f'<div class="rk-layout"><section class="rk-board" aria-label="{_e(heading)}">'
        f'<ol class="rk-list">{items}</ol>{more_html}</section>'
        '<section class="rk-play" id="rankPlay" aria-labelledby="rankPlayTitle">'
        '<h2 id="rankPlayTitle">Rank them yourself</h2>'
        f'<p class="rk-play__lead">Tick the ones you\'ve {_e(data["verb"])}, then pick the one you liked more, two at a time. '
        'At the end you see how close your order is to this one.</p>'
        '<div class="rk-stage" data-rk-stage aria-live="polite"></div>'
        '<noscript><p class="rk-play__lead">Ranking them here needs JavaScript.</p></noscript>'
        f'</section></div>{owner_html}{guest_html}</article>'
    )
    head = (f'<link rel="stylesheet" href="/static/ranked-share.css?v={CSS_VERSION}">'
            f'<script src="/static/ranked-share.js?v={JS_VERSION}" defer></script>')
    card = f'{SITE}{data["path"]}/card.png?v={data["fingerprint"]}'
    from .discover import page
    response = page(heading, _description(data), data["path"], content, indexable=False, head=head,
                    member=signed_in, share_image=card)
    _private(response)
    return response


# ---------------------------------------------------------------- the pictures

_CARDS = None


def _cache():
    global _CARDS
    if _CARDS is None:
        from .profiles import _CardCache
        _CARDS = _CardCache(size=64)
    return _CARDS


async def _posters(request: Request, data: dict, limit: int) -> dict:
    """{place: poster bytes} for the first ``limit`` places, fetched through the image proxy's cache."""
    from .tier_list import _poster_bytes
    client = getattr(request.app.state, "external_api_client", None)
    wanted = [(item["position"], item["image"]) for item in data["items"][:limit] if item.get("image")]
    if client is None or not wanted:
        return {}
    urls = list(dict.fromkeys(url for _, url in wanted))
    tasks = {url: asyncio.ensure_future(_poster_bytes(client, url)) for url in urls}
    done, pending = await asyncio.wait(tasks.values(), timeout=CARD_POSTER_SECONDS)
    for task in pending:
        task.cancel()
    bodies = {}
    for url, task in tasks.items():
        if task in done and not task.cancelled() and task.exception() is None:
            bodies[url] = task.result()
    return {place: bodies[url] for place, url in wanted if url in bodies}


async def _picture(token: str, request: Request, db: Session, kind: str) -> Response:
    def facts():
        share = ranking_shares.by_token(db, token)
        return ranking_shares.view(db, share) if share is not None else None
    data = await run_in_threadpool(facts)
    if data is None:
        raise HTTPException(404, "This top ten isn't shared anymore")
    etag = f'"{kind}-{data["fingerprint"]}"'
    # Short-lived, so a link turned off or a shelf made private stops showing its picture soon after.
    headers = {"Cache-Control": "public, max-age=600", "ETag": etag, "X-Content-Type-Options": "nosniff",
               "X-Robots-Tag": "noindex"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    key = (data["owner_id"], data["category"], kind, data["fingerprint"])
    png = _cache().get(key)
    if png is None:
        posters = await _posters(request, data, 10)
        render = ranking_shares.render_story if kind == "story" else ranking_shares.render_card
        try:
            png = await run_in_threadpool(render, data, posters)
        except Exception:
            raise HTTPException(404, "Card unavailable")
        _cache().put(key, png)
    if kind == "story":
        headers["Content-Disposition"] = f'inline; filename="top-{len(data["items"])}-{data["category"]}.png"'
    return Response(content=png, media_type="image/png", headers=headers)


@router.get(ranking_shares.BASE_PATH + "/{token}/card.png", include_in_schema=False)
async def ranked_card(token: str, request: Request, db: Session = Depends(get_db)):
    """The picture chat apps show for a shared link: #1 large, the rest of the top ten beside it."""
    return await _picture(token, request, db, "card")


@router.get(ranking_shares.BASE_PATH + "/{token}/story.png", include_in_schema=False)
async def ranked_story(token: str, request: Request, db: Session = Depends(get_db)):
    """A 1080x1920 picture of the same top ten for stories."""
    return await _picture(token, request, db, "story")
