"""The page and pictures behind a shared "On your services" list, /on-my-services/<token> (see app/service_shares.py)."""
from __future__ import annotations

import asyncio
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import explore_art, funnel, service_shares, streaming_services
from ..dependencies import get_db, get_optional_current_user

router = APIRouter(tags=["streaming services"])
CSS_VERSION = "20261122-svc-share-1"
JS_VERSION = "20261122-svc-share-1"
GUEST_LIST_JS = "/static/guest-list.js?v=20261122-shelf-1"
SITE = "https://omnitrackr.xyz"
CARD_POSTER_SECONDS = 8.0
FIRST_EAGER = 6


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
        "List not found", "This list isn't shared anymore",
        "Whoever shared it may have turned the link off or changed their services. "
        "Pick the services you have and OmniTrackr shows what on your own list you can stream on them.",
        actions=(("Create a free account", "/#signup"), ("See what OmniTrackr does", "/about"))),
        status_code=404)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _save_html(item: dict, signed_in: bool, owner: bool) -> str:
    if owner:
        return ""
    label = f'Save {item["title"]} to my list'
    if signed_in:
        return (f'<button type="button" class="svc-save" data-svc-add data-kind="{_e(item["kind"])}" '
                f'data-slug="{_e(item["slug"])}" aria-label="{_e(label)}">'
                '<span class="svc-save__idle">+ Add to my list</span><span class="svc-save__done">✓ In your library</span></button>')
    image = f' data-guest-image="{_e(item["image"])}"' if item.get("image") else ""
    return (f'<button type="button" class="svc-save" data-guest-kind="{_e(item["kind"])}" '
            f'data-guest-slug="{_e(item["slug"])}" data-guest-title="{_e(item["title"])}"{image} '
            f'aria-pressed="false" aria-label="{_e(label)}">'
            '<span class="svc-save__idle">+ Save to my list</span><span class="svc-save__done">✓ Saved</span></button>')


def _item_html(item: dict, place: int, signed_in: bool, owner: bool) -> str:
    lazy = "" if place <= FIRST_EAGER else ' loading="lazy"'
    if item.get("image"):
        art = (f'<img src="{_e(item["image"])}" alt="" width="160" height="240" decoding="async" '
               f'referrerpolicy="no-referrer"{lazy}>')
    else:
        art = f'<span class="svc-tile__letter">{_e(item["title"][:1].upper())}</span>'
    new = '<span class="svc-tile__new">New</span>' if item["new"] else ""
    services = "".join(
        f'<span class="svc-pill{" svc-pill--new" if service["new"] else ""}" data-service="{_e(service["id"])}">'
        f'{"New on " if service["new"] else ""}{_e(service["name"])}</span>'
        for service in item["services"])
    names = streaming_services._and([service["name"] for service in item["services"]])
    meta = " · ".join(str(part) for part in (item["label"], item.get("year")) if part)
    return (
        f'<li class="svc-tile{" is-new" if item["new"] else ""}" data-svc-item data-format="{_e(item["category"])}"'
        f' data-mine="{_e(" ".join(service["id"] for service in item["services"]))}" data-all="{_e(" ".join(item["all"]))}">'
        f'<a class="svc-tile__art" href="{_e(item["url"])}" tabindex="-1" aria-hidden="true">{art}{new}</a>'
        '<div class="svc-tile__copy">'
        f'<h3 class="svc-tile__name"><a href="{_e(item["url"])}">{_e(item["title"])}</a></h3>'
        f'<p class="svc-tile__meta">{_e(meta)}</p>'
        f'<p class="svc-tile__where"><span class="sr-only">{"New on" if item["new"] else "On"} {_e(names)}: </span>{services}</p>'
        '<p class="svc-tile__you" data-svc-you hidden></p>'
        f'{_save_html(item, signed_in, owner)}</div></li>')


def _picker_html(data: dict) -> str:
    """Chips for every service any of these titles streams on, so a visitor can tick theirs."""
    found = {service for item in data["items"] for service in item["all"]}
    chips = "".join(
        f'<label class="svc-chip"><input type="checkbox" name="svcMine" value="{_e(service_id)}">'
        f'<span>{_e(name)}</span></label>'
        for service_id, name, _free, _aliases in streaming_services.SERVICES if service_id in found)
    return (
        '<section class="svc-match" id="svcMatch" aria-labelledby="svcMatchTitle">'
        '<div class="svc-match__head"><h2 id="svcMatchTitle">Which of these can you watch?</h2>'
        '<p class="svc-match__lead">Tick the services you have. Nothing you tick leaves this browser.</p></div>'
        f'<fieldset class="svc-match__chips"><legend class="sr-only">Your streaming services</legend>{chips}</fieldset>'
        '<p class="svc-match__result" data-svc-result role="status" aria-live="polite"></p></section>')


def _description(data: dict) -> str:
    names = [item["title"] for item in data["items"][:3]]
    return (f'{service_shares.heading(data)}: {data["total"]} {service_shares.kind_words(data)} on '
            f'{service_shares.service_names(data)}, including {streaming_services._and(names)}. '
            'See which of them you can watch on the services you have.')


@router.get(service_shares.BASE_PATH + "/{token}", include_in_schema=False)
def shared_services_page(token: str, request: Request, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    share = service_shares.by_token(db, token)
    data = service_shares.view(db, share) if share is not None else None
    if data is None:
        return _not_found()
    owner = user is not None and user.id == data["owner_id"]
    signed_in = user is not None
    # Chat apps fetch the page to show a preview and browsers prefetch it; neither is someone opening the link.
    if not owner and _person(request):
        service_shares.count_open(db, share)
        streaming_services.count("link_opened")
        if user is None:
            funnel.record("svc_link_opened", request)
    heading = service_shares.heading(data)
    total = data["total"]
    who = (f'<a href="{_e(data["profile"])}">{_e(data["by"])}</a>' if data.get("by") and data.get("profile") else "they")
    lead = (f'{total:,} {_e(service_shares.kind_words(data))} {who} want{"s" if data.get("by") else ""} to watch, '
            f'all streaming on {_e(streaming_services._and([service["name"] for service in data["services"]]))} right now.')
    if data["new"]:
        lead += f' {data["new"]} arrived in the last two weeks.'
    shown = len(data["items"])
    more = (f'<p class="svc-more">{total - shown:,} more on the list. These are the newest.</p>' if total > shown else "")
    filters = ""
    if len(data["services"]) > 1:
        chips = [f'<button type="button" class="svc-filter" data-svc-filter="" aria-pressed="true">All '
                 f'<span>{total:,}</span></button>']
        chips += [f'<button type="button" class="svc-filter" data-svc-filter="{_e(service["id"])}" aria-pressed="false">'
                  f'{_e(service["name"])} <span>{service["count"]:,}</span></button>' for service in data["services"]]
        filters = f'<div class="svc-filters" role="group" aria-label="Show titles on">{"".join(chips)}</div>'
    items = "".join(_item_html(item, place, signed_in, owner) for place, item in enumerate(data["items"], start=1))
    credit = streaming_services.credit()
    if streaming_services.where_to_watch.tmdb_enabled():
        credit += " This product uses the TMDB API but is not endorsed or certified by TMDB."
    owner_html = ('<aside class="svc-owner" data-svc-owner>'
                  '<p><strong>This is your link.</strong> It always shows what on your list is streaming on your services '
                  'right now, so it changes as your list does. Nobody sees your scores, notes or the rest of your library.'
                  + (f' Opened {data["opened"]:,} time{"" if data["opened"] == 1 else "s"} so far.' if data["opened"] else '')
                  + '</p><div class="svc-actions">'
                  '<button type="button" class="site-btn site-btn--primary site-btn--sm" data-svc-copy>Copy link</button>'
                  '<button type="button" class="site-btn site-btn--ghost site-btn--sm" data-svc-share hidden>Share</button>'
                  f'<button type="button" class="site-btn site-btn--ghost site-btn--sm" data-svc-story data-src="{_e(data["path"])}/story.png">Save image for stories</button>'
                  '<a class="site-btn site-btn--ghost site-btn--sm" href="/#on-your-services">Open your home card</a></div>'
                  '<p class="svc-status" data-svc-owner-status role="status" aria-live="polite"></p></aside>') if owner else ''
    guest_html = '' if signed_in else (
        '<aside class="svc-cta"><div><p class="svc-cta__title">Know when the rest start streaming</p>'
        '<p>OmniTrackr is a free library for films, TV, anime, games, books and more. Pick the services you have and it '
        'shows what on your list you can watch tonight, then tells you when something else arrives. Your services stay private.</p></div>'
        '<a class="site-btn site-btn--primary" href="/#signup" data-svc-signup>Create a free account</a></aside>')
    content = (
        f'<article class="svc-share" id="servicesShare" data-token="{_e(data["token"])}"'
        f' data-member="{"true" if signed_in else "false"}" data-owner="{"true" if owner else "false"}">'
        '<header class="svc-head">'
        f'<p class="eyebrow svc-eyebrow">Streaming now · {_e(service_shares.service_names(data))}</p>'
        f'<h1>{_e(heading)}</h1><p class="svc-lead">{lead}</p>'
        + ('' if owner else '<a class="svc-jump" href="#svcMatch">Which can you watch? ↓</a>')
        + '</header>'
        + owner_html
        + ('' if owner else _picker_html(data))
        + f'<section class="svc-board" aria-label="{_e(heading)}">{filters}'
        f'<ul class="svc-grid" data-svc-grid>{items}</ul>{more}'
        f'<p class="svc-credit">{_e(credit)} Checked every few days, so a title can leave a service before we notice.</p></section>'
        + guest_html
        + (explore_art.dock("Keep my list") if not signed_in else '')
        + '</article>'
    )
    head = (f'<link rel="stylesheet" href="/static/services-share.css?v={CSS_VERSION}">'
            + ('' if signed_in else f'<script src="{GUEST_LIST_JS}" defer></script>')
            + f'<script src="/static/services-share.js?v={JS_VERSION}" defer></script>')
    card = f'{SITE}{data["path"]}/card.png?v={data["fingerprint"]}'
    from .discover import page
    response = page(heading, _description(data), data["path"], content, indexable=False, head=head,
                    member=signed_in, share_image=card, body_class="svc-page")
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
    """{place: poster bytes} for the first ``limit`` titles, fetched through the image proxy's cache."""
    from .. import tier_list
    from .tier_list import _poster_bytes
    client = getattr(request.app.state, "external_api_client", None)
    # A library poster can be any address the member typed in, so the server only fetches the poster
    # hosts the tier list image proxy allows. Anything else gets the drawn tile.
    wanted = [(place, item["image"]) for place, item in enumerate(data["items"][:limit], start=1)
              if item.get("image") and tier_list.image_allowed(item["image"])]
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
        share = service_shares.by_token(db, token)
        return service_shares.view(db, share) if share is not None else None
    data = await run_in_threadpool(facts)
    if data is None:
        raise HTTPException(404, "This list isn't shared anymore")
    etag = f'"{kind}-{data["fingerprint"]}"'
    # Short-lived, so a link turned off stops showing its picture soon after.
    headers = {"Cache-Control": "public, max-age=600", "ETag": etag, "X-Content-Type-Options": "nosniff",
               "X-Robots-Tag": "noindex"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    key = (data["owner_id"], kind, data["fingerprint"])
    png = _cache().get(key)
    if png is None:
        posters = await _posters(request, data, service_shares.PICTURE_SHOWN)
        render = service_shares.render_story if kind == "story" else service_shares.render_card
        try:
            png = await run_in_threadpool(render, data, posters)
        except Exception:
            raise HTTPException(404, "Card unavailable")
        _cache().put(key, png)
    if kind == "story":
        headers["Content-Disposition"] = 'inline; filename="on-my-services.png"'
    return Response(content=png, media_type="image/png", headers=headers)


@router.get(service_shares.BASE_PATH + "/{token}/card.png", include_in_schema=False)
async def shared_services_card(token: str, request: Request, db: Session = Depends(get_db)):
    """The picture chat apps show for a shared link."""
    return await _picture(token, request, db, "card")


@router.get(service_shares.BASE_PATH + "/{token}/story.png", include_in_schema=False)
async def shared_services_story(token: str, request: Request, db: Session = Depends(get_db)):
    """A 1080x1920 picture of the same list for stories."""
    return await _picture(token, request, db, "story")
