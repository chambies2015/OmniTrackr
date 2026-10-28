"""Release calendar feeds (.ics) and the member's private calendar setting."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from .. import episode_calendar
from .. import release_calendar as calendar
from .. import release_radar as radar
from ..dependencies import get_current_user, get_db

router = APIRouter(tags=["calendar"])
FIRST_LOAD_WAIT_SECONDS = 4.0


def _client(request: Request):
    return getattr(request.app.state, "external_api_client", None)


def _ics_response(body: str, filename: str, cache: str, private: bool = False) -> Response:
    response = Response(content=body, media_type="text/calendar; charset=utf-8")
    response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
    response.headers["Cache-Control"] = cache
    response.headers["X-Robots-Tag"] = "noindex"
    if private:
        response.headers["Referrer-Policy"] = "no-referrer"
    return response


async def _pool(request: Request, categories) -> list[dict]:
    """Cached items, waiting briefly for a section's current period on a cold start."""
    today = radar.today_utc()
    client = _client(request)
    if client is not None:
        cold = [window for window in (radar.current_window(category, today) for category in categories)
                if radar.CACHE.peek(window) is None]
        if cold:
            await asyncio.gather(*(radar.CACHE.get(client, window, wait=FIRST_LOAD_WAIT_SECONDS) for window in cold))
    return calendar.pool_for(today, client)


async def _public(request: Request, feed: str) -> Response:
    categories = radar.CATEGORY_ORDER if feed == "all" else (feed,)
    pool = await _pool(request, categories)
    events = calendar.public_events(pool, feed, radar.today_utc())
    body = calendar.build_ics(calendar.FEED_NAMES[feed], calendar.FEED_DESCRIPTIONS[feed], events)
    filename = "omnitrackr-release-radar.ics" if feed == "all" else f"omnitrackr-{feed}.ics"
    # A cold cache gives a short-lived, empty calendar so the next poll fills in.
    cache = "public, max-age=3600" if events else "public, max-age=300"
    return _ics_response(body, filename, cache)


@router.api_route("/calendar/release-radar.ics", methods=["GET", "HEAD"], include_in_schema=False)
async def release_radar_calendar(request: Request):
    return await _public(request, "all")


@router.api_route("/calendar/release-radar/{feed}.ics", methods=["GET", "HEAD"], include_in_schema=False)
async def release_radar_section_calendar(feed: str, request: Request):
    if feed not in radar.CATEGORY_ORDER:
        raise HTTPException(404, "Unknown Release Radar calendar")
    return await _public(request, feed)


@router.api_route("/calendar/u/feed-{token}.ics", methods=["GET", "HEAD"], include_in_schema=False)
async def member_calendar(token: str, request: Request, db: Session = Depends(get_db)):
    user = await run_in_threadpool(calendar.member_for_token, db, token)
    if user is None:
        raise HTTPException(404, "This calendar address is no longer active")
    feed = await run_in_threadpool(calendar.feed_for, db, user.id)
    include_episodes = bool(feed and feed.include_episodes is not False)
    pool = await _pool(request, radar.CATEGORY_ORDER)
    events = await run_in_threadpool(calendar.member_feed_events, db, user, pool, radar.today_utc(), include_episodes)
    description = ("New releases, seasons, sequels and episodes connected to your OmniTrackr library."
                   if include_episodes else "New releases, seasons and sequels connected to your OmniTrackr library.")
    body = calendar.build_ics("OmniTrackr: my releases", description, events)
    return _ics_response(body, "omnitrackr-my-releases.ics", "private, max-age=1800", private=True)


# ---------------------------------------------------------------- member setting

def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.get("/api/calendar")
def get_calendar(response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    return calendar.state(db, user.id)


@router.post("/api/calendar")
def turn_on_calendar(request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    feed = calendar.enable(db, user.id)
    if feed.include_episodes:
        episode_calendar.queue_member(request.app, user.id)
    return calendar.state(db, user.id)


@router.put("/api/calendar/episodes")
def set_calendar_episodes(request: Request, response: Response, enabled: bool = Body(..., embed=True),
                          user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    calendar.set_episodes(db, user.id, enabled)
    if enabled:
        episode_calendar.queue_member(request.app, user.id)
    return calendar.state(db, user.id)


@router.post("/api/calendar/reset")
def reset_calendar(response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    calendar.reset(db, user.id)
    return calendar.state(db, user.id)


@router.delete("/api/calendar")
def turn_off_calendar(response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    calendar.disable(db, user.id)
    return calendar.state(db, user.id)
