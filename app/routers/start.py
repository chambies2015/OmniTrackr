"""The start page (/start) and its API. See app/start_flow.py."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from html import escape
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import auth, for_you, start_flow, title_metadata, title_pages, title_search
from ..dependencies import get_current_user, get_db, get_optional_current_user
from ..library_lifecycle import delete_owned_media
from ..progress import lock_progress_owner
from ..taste_quiz import cached_art
from .discover import page
from .titles import add_group_to_library

router = APIRouter(tags=["start"])
CSS_VERSION = "20261030-start-1"
JS_VERSION = "20261030-start-1"
# The same scripts the dashboard uses to move titles saved before sign-up into the library.
IMPORT_SCRIPTS = ("/static/guest-list.js?v=20261030-start-1", "/static/taste-quiz.js?v=20261030-start-1",
                  "/static/taste-compare.js?v=20261030-start-1")
UNDO_WINDOW = timedelta(minutes=30)
SECURE_COOKIE = auth.ENVIRONMENT == "production"


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _json_block(element_id: str, data) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return f'<script type="application/json" id="{element_id}">{payload}</script>'


def _state(db: Session, user) -> dict:
    total = start_flow.library_total(db, user.id)
    return {
        "total": total,
        "goal": start_flow.GOAL,
        "shelf": start_flow.recent_titles(db, user.id),
        "first_week": for_you.first_week(db, user),
    }


def _content(state: dict) -> str:
    chips = "".join(
        f'<label class="st-chip"><input type="checkbox" name="kind" value="{kind}"'
        f'{" checked" if kind in start_flow.DEFAULT_KINDS else ""}><span>{_e(chip)}</span></label>'
        for kind, (chip, _) in start_flow.FORMATS.items())
    slots = "".join('<li class="st-slot"></li>' for _ in range(start_flow.GOAL))
    return (
        '<section class="st" id="startFlow" aria-labelledby="stTitle">'
        '<header class="st-head">'
        '<p class="eyebrow">YOUR FIRST FIVE</p>'
        '<h1 id="stTitle">Let\'s get five titles into your library</h1>'
        '<p class="st-lead">Five is where OmniTrackr starts paying off: release alerts, picks and stats all work from '
        'what you save. Most people get there in a couple of minutes.</p>'
        f'<div class="st-goal"><ol class="st-slots" data-st-slots aria-hidden="true">{slots}</ol>'
        '<p class="st-count" data-st-count role="status" aria-live="polite"></p></div>'
        '</header>'

        '<div class="st-screen" data-st-screen="choose">'
        '<h2 class="st-subhead">How do you want to start?</h2>'
        '<div class="st-paths">'
        '<button type="button" class="st-path st-path--primary" data-st-go="quick">'
        '<span class="st-path__tag">Fastest</span><strong>Quick add</strong>'
        '<span>Tap through popular titles: seen it, want to, or skip. About a minute.</span></button>'
        '<button type="button" class="st-path" data-st-go="search"><strong>Search by name</strong>'
        '<span>Already know what you want to save? Find it and add it.</span></button>'
        '<a class="st-path" href="/?start=import" data-st-step="import"><strong>Import a list</strong>'
        '<span>Bring a Letterboxd, IMDb, Goodreads, StoryGraph, MyAnimeList, AniList, Kitsu or Trakt export. '
        'You see a preview before anything is added.</span></a>'
        '</div>'
        '<p class="st-quiz">Rather answer a few questions? <a href="/taste-quiz" data-st-step="quiz">Take the '
        'one-minute taste quiz</a> and get picks chosen from your answers.</p>'
        '</div>'

        '<div class="st-screen st-quick" data-st-screen="quick" hidden>'
        f'<fieldset class="st-formats"><legend>What are you into?</legend><div class="st-chips">{chips}</div></fieldset>'
        '<article class="st-card" data-st-card aria-live="polite" aria-atomic="true"></article>'
        '<div class="st-answers" role="group" aria-label="Your answer">'
        '<button type="button" class="st-answer st-answer--skip" data-st-answer="skip">Skip</button>'
        '<button type="button" class="st-answer st-answer--want" data-st-answer="want"><span aria-hidden="true">＋</span> Want to</button>'
        '<button type="button" class="st-answer st-answer--seen" data-st-answer="seen"><span aria-hidden="true">✓</span> Seen it</button>'
        '</div>'
        '<p class="st-keys">On a keyboard: ← skip, ↑ want to, → seen it.</p>'
        '<p class="st-status" data-st-status role="status" aria-live="polite"></p>'
        '<p class="st-switch"><button type="button" class="st-link" data-st-go="search">Search instead</button>'
        '<button type="button" class="st-link" data-st-go="choose">Other ways to start</button></p>'
        '</div>'

        '<div class="st-screen st-search" data-st-screen="search" hidden>'
        '<form class="st-search__form" role="search" data-st-search-form>'
        '<label for="stSearch">Search for a movie, show, anime, game, book or album</label>'
        '<input id="stSearch" type="search" maxlength="80" autocomplete="off" spellcheck="false" '
        'placeholder="Try Dune, Frieren or Hades" aria-describedby="stSearchHint">'
        '</form>'
        '<ul class="st-results" data-st-results aria-live="polite"></ul>'
        '<p class="st-hint" id="stSearchHint">This searches titles other members already track. Can\'t find it? '
        '<a href="/">Add anything</a> in your library looks it up everywhere.</p>'
        '<p class="st-switch"><button type="button" class="st-link" data-st-go="quick">Quick add instead</button>'
        '<button type="button" class="st-link" data-st-go="choose">Other ways to start</button></p>'
        '</div>'

        '<div class="st-screen st-done" data-st-screen="done" hidden tabindex="-1">'
        '<p class="eyebrow">FIVE SAVED</p>'
        '<h2 data-st-done-title>Your library is off the ground</h2>'
        '<p class="st-lead">From here, a few small things make OmniTrackr feel like yours. None of them take long.</p>'
        '<ol class="st-next" data-st-next></ol>'
        '<div class="st-done__actions"><a class="button" href="/" data-st-library>Open my library</a>'
        '<button type="button" class="st-link" data-st-go="quick">Keep adding titles</button></div>'
        '</div>'

        '<footer class="st-foot"><button type="button" class="st-link" data-st-skip>Skip for now and open my library</button></footer>'
        '<noscript><p>This page needs JavaScript. You can add titles from <a href="/">your library</a> with Add anything.</p></noscript>'
        f'{_json_block("startState", state)}'
        '</section>'
    )


@router.get("/start", include_in_schema=False)
def start_page(request: Request, db: Session = Depends(get_db), user=Depends(get_optional_current_user)):
    if user is None:
        response = RedirectResponse("/?next=/start#landing-auth", status_code=303)
        start_flow.clear_cookie(response, SECURE_COOKIE)
        return response
    start_flow.row_for(db, user.id)
    state = _state(db, user)
    db.commit()
    head = (f'<link rel="stylesheet" href="/static/start.css?v={CSS_VERSION}">'
            + "".join(f'<script src="{src}" defer></script>' for src in IMPORT_SCRIPTS)
            + f'<script src="/static/start.js?v={JS_VERSION}" defer></script>')
    response = page("Your first five titles", "Fill your OmniTrackr library with five titles in a couple of minutes.",
                    "/start", _content(state), indexable=False, head=head, member=True)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Cookie"
    # Seen once: the dashboard stops sending this member here.
    start_flow.clear_cookie(response, SECURE_COOKIE)
    return response


@router.get("/api/start/state")
def start_state(response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    state = _state(db, user)
    if state["total"] >= start_flow.GOAL and start_flow.row_for(db, user.id, create=False) is not None:
        # Titles can arrive from the import studio, the quiz or a guest list too.
        start_flow.mark(db, user.id, "reached_five")
        db.commit()
    return state


@router.get("/api/start/deck")
def start_deck(response: Response, kinds: str = Query("", max_length=120),
               user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    wanted = [kind for kind in kinds.split(",") if kind in start_flow.FORMATS]
    cards = start_flow.deck(title_search.index(db), start_flow.owned_slugs(db, user.id), wanted)
    return {"cards": cards}


@router.get("/api/start/art/{kind}/{slug}")
async def start_art(kind: str, slug: str, request: Request, response: Response,
                    user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Artwork for a well-known card nobody has saved with a cover yet, looked up once and cached."""
    entry = start_flow.well_known(kind, slug)
    if entry is None:
        raise HTTPException(404, "Not a start page title")
    image = await run_in_threadpool(lambda: cached_art(db, entry))
    if image:
        response.headers["Cache-Control"] = "private, max-age=86400"
        return {"image": image}
    client = getattr(request.app.state, "external_api_client", None)
    data = await title_metadata.get_or_fetch(db, client, kind, title_pages.normalize(entry["title"]),
                                             entry["title"], entry["year"], entry.get("creator"), wait=6)
    image = title_pages._safe_image((data or {}).get("poster"))
    response.headers["Cache-Control"] = "private, max-age=86400" if image else "no-store"
    return {"image": image}


class StartSave(BaseModel):
    id: str = Field(..., min_length=3, max_length=160)
    answer: Literal["seen", "want"]
    via: Literal["quick", "search"] = "quick"


@router.post("/api/start/save")
def start_save(payload: StartSave, request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Save one card or search result. A title already in the library is left exactly as it is."""
    _private(response)
    kind, _, slug = payload.id.partition("/")
    found = start_flow.resolve(db, kind, slug)
    if found is None:
        raise HTTPException(404, "That title isn't available here any more. Try another one.")
    lock_progress_owner(db, user.id)
    source, entry = found
    if source == "group":
        state, record = add_group_to_library(db, user, entry)
    else:
        image = None
        if kind in start_flow.WELL_KNOWN:
            image = cached_art(db, {"kind": kind, "title": entry["title"], "year": entry.get("year")})
        state, record = start_flow.add_known(db, user, kind, entry, image)
    if state == "created" and payload.answer == "seen":
        start_flow.mark_seen(record, kind)
    start_flow.mark(db, user.id, "quick_add" if payload.via == "quick" else "search", request)
    if state == "created":
        start_flow.mark(db, user.id, "first_saved", request)
    db.flush()
    total = start_flow.library_total(db, user.id)
    if total >= start_flow.GOAL:
        start_flow.mark(db, user.id, "reached_five", request)
    category = title_pages.KINDS[kind][2]
    result = {
        "state": state, "title": record.title, "kind": kind, "category": category, "item_id": record.id,
        "seen": bool(getattr(record, title_pages.COMPLETE_FIELD[kind], False)),
        "image": title_pages._safe_image(getattr(record, title_pages.IMAGE_FIELD[kind], None)),
        "total": total,
    }
    db.commit()
    return result


class StartUndo(BaseModel):
    category: Literal["movies", "tv-shows", "anime", "video-games", "music", "books", "manga", "podcasts", "audiobooks"]
    item_id: int = Field(..., ge=1, le=2147483647)


@router.post("/api/start/undo")
def start_undo(payload: StartUndo, request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Take back a title saved on this page a moment ago. Older entries are never removed from here."""
    _private(response)
    model = for_you.LIBRARY[payload.category][0]
    item = db.query(model).filter(model.user_id == user.id, model.id == payload.item_id).first()
    if item is None:
        raise HTTPException(404, "That title is no longer in your library.")
    if item.added_at is None or item.added_at < datetime.utcnow() - UNDO_WINDOW:
        raise HTTPException(409, "That title has been in your library for a while. Remove it from your library instead.")
    db.rollback()
    if delete_owned_media(db, user.id, payload.category, payload.item_id) is None:
        raise HTTPException(404, "That title is no longer in your library.")
    return {"total": start_flow.library_total(db, user.id)}


class StartStep(BaseModel):
    step: Literal["import", "quiz", "next_step", "skipped"]


@router.post("/api/start/step", status_code=204)
def start_step(payload: StartStep, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """A step the page reports itself (opening the importer or the quiz, a first-week step, skipping)."""
    start_flow.mark(db, user.id, payload.step, request)
    db.commit()
    return Response(status_code=204)
