"""Taste quiz (/taste-quiz): a one-minute start for new members and visitors.

The page is a deck of well-known titles. Members' answers go straight into their
library (POST /api/taste-quiz/save); visitors' answers stay in their browser and
move into their library at first log-in through the same endpoint. Suggestions
come from the editors' "If you liked" guides and the Pick for me pool, and are
saved through POST /api/pick/add or the guest list like every other pick.
"""
from __future__ import annotations

import json
from html import escape
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import funnel, pick, taste_quiz, title_metadata, title_pages, title_search
from ..auth import AUTH_COOKIE_NAME
from ..dependencies import get_current_user, get_db
from ..progress import lock_progress_owner
from .discover import page

router = APIRouter(tags=["taste-quiz"])
CSS_VERSION = "20261027-taste-quiz-1"
JS_VERSION = "20261030-audiobooks-1"
GUEST_LIST_JS = "/static/guest-list.js?v=20261031-browse-1"
DESCRIPTION = ("Tap through 24 well-known movies, shows, anime and games, mark what you've seen and loved, "
               "and start OmniTrackr with a filled-in library and picks chosen for you.")

Answer = Literal["loved", "liked", "meh", "want"]


class QuizAnswer(BaseModel):
    id: str = Field(..., min_length=3, max_length=160)
    answer: Answer


class QuizAnswers(BaseModel):
    answers: list[QuizAnswer] = Field(default_factory=list, max_length=len(taste_quiz.DECK))
    kinds: list[Literal["movie", "tv", "anime", "game"]] = Field(default_factory=list, max_length=4)
    # "quiz" when the member just finished it; "guest" when answers saved before sign-up are moved in.
    source: Literal["quiz", "guest"] = "quiz"


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _pairs(payload: QuizAnswers) -> list[tuple[str, str]]:
    return [(item.id, item.answer) for item in payload.answers if taste_quiz.find(item.id) is not None]


def _with_details(rows: list[dict], details: dict) -> list[dict]:
    for row in rows:
        detail = details.get(row["id"], {})
        row["image"] = detail.get("image")
        row["url"] = detail.get("url")
    return rows


def _json_block(data) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return f'<script type="application/json" id="tasteQuizDeck">{payload}</script>'


def _fallback_list(cards: list[dict]) -> str:
    items = "".join(f'<li>{_e(card["title"])} <span class="muted">· {_e(card["label"])} · {_e(card["year"])}</span></li>'
                    for card in cards)
    return (f'<noscript><p>The quiz needs JavaScript. These are the titles it asks about; you can add any of them '
            f'from your library with Add Anything.</p><ul class="tq-fallback">{items}</ul></noscript>')


@router.get("/taste-quiz", include_in_schema=False)
def taste_quiz_page(request: Request, db: Session = Depends(get_db)):
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    cards = taste_quiz.deck()
    formats = "".join(
        f'<label class="tq-chip"><input type="checkbox" name="kind" value="{kind}" checked><span>{_e(label)}</span></label>'
        for kind, label in taste_quiz.FORMAT_LABELS.items())
    lead = ("Mark what you've seen and how you felt about it. Everything goes straight into your library, and "
            "you'll get a few picks chosen from your answers." if signed_in else
            "Mark what you've seen and how you felt about it, then get a few picks chosen from your answers. "
            "No account needed: your answers stay in this browser and move into your library when you sign up.")
    content = (
        '<section class="tq" id="tasteQuiz" aria-labelledby="tqTitle" '
        f'data-signed-in="{"true" if signed_in else "false"}">'
        '<div class="tq-screen tq-intro" data-tq-screen="intro">'
        '<p class="eyebrow">TASTE QUIZ · ABOUT A MINUTE</p>'
        '<h1 id="tqTitle">What have you loved lately?</h1>'
        f'<p class="tq-lead">{_e(lead)}</p>'
        f'<fieldset class="tq-formats"><legend>What are you into?</legend>{formats}</fieldset>'
        '<button type="button" class="button tq-start" data-tq-action="start">Start the quiz</button>'
        '<p class="tq-note muted">Skip anything you haven\'t seen. You can stop after a few titles.</p>'
        '<p class="tq-resume" data-tq-resume hidden></p>'
        '</div>'
        '<div class="tq-screen tq-play" data-tq-screen="play" hidden>'
        '<div class="tq-progress"><div class="tq-progress__bar"><span data-tq-bar></span></div>'
        '<p class="tq-progress__text" data-tq-count aria-live="polite"></p></div>'
        '<article class="tq-card" data-tq-card aria-live="polite"></article>'
        '<div class="tq-answers" role="group" aria-label="Your answer">'
        '<div class="tq-answers__seen">'
        '<button type="button" class="tq-answer tq-answer--loved" data-tq-answer="loved"><span aria-hidden="true">♥</span> Loved it</button>'
        '<button type="button" class="tq-answer tq-answer--liked" data-tq-answer="liked"><span aria-hidden="true">👍</span> Liked it</button>'
        '<button type="button" class="tq-answer tq-answer--meh" data-tq-answer="meh"><span aria-hidden="true">👎</span> Not for me</button>'
        '</div><div class="tq-answers__other">'
        '<button type="button" class="tq-answer tq-answer--want" data-tq-answer="want"><span aria-hidden="true">＋</span> Want to</button>'
        '<button type="button" class="tq-answer tq-answer--skip" data-tq-answer="skip">Haven\'t seen</button>'
        '</div></div>'
        '<div class="tq-controls"><button type="button" class="tq-link" data-tq-action="back" disabled>Back</button>'
        '<button type="button" class="tq-link tq-finish" data-tq-action="finish" hidden>Show my picks</button></div>'
        '</div>'
        '<div class="tq-screen tq-result" data-tq-screen="result" hidden tabindex="-1">'
        '<p class="eyebrow">YOUR PICKS</p><h2 data-tq-result-title>Here\'s where to go next</h2>'
        '<p class="tq-summary" data-tq-summary role="status"></p>'
        '<div class="tq-shelf" data-tq-shelf></div>'
        '<h3 class="tq-subhead" data-tq-picks-title>Picked for you</h3>'
        '<ul class="tq-picks" data-tq-picks></ul>'
        '<div class="tq-result__actions" data-tq-actions></div>'
        '<button type="button" class="tq-link" data-tq-action="restart">Take the quiz again</button>'
        '</div>'
        f'{_fallback_list(cards)}{_json_block(cards)}'
        '</section>'
    )
    head = f'<link rel="stylesheet" href="/static/taste-quiz.css?v={CSS_VERSION}">'
    if not signed_in:
        head += f'<script src="{GUEST_LIST_JS}" defer></script>'
    head += f'<script src="/static/taste-quiz.js?v={JS_VERSION}" defer></script>'
    # An interactive tool, not an article: kept out of search results.
    response = page("Taste quiz: start your library in a minute", DESCRIPTION, "/taste-quiz", content,
                    indexable=False, head=head, member=signed_in)
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


@router.get("/api/taste-quiz/art/{kind}/{slug}")
async def taste_quiz_art(kind: str, slug: str, request: Request, response: Response, db: Session = Depends(get_db)):
    """Artwork for one deck card, looked up once and cached like a title page's details."""
    card = taste_quiz.find(f"{kind}/{slug}")
    if card is None:
        raise HTTPException(404, "Not a quiz title")
    # A member's cover or cached metadata first; an outside lookup only when neither exists.
    image = await run_in_threadpool(lambda: taste_quiz.cached_art(db, card, taste_quiz._art_index(title_search.index(db))))
    if image:
        response.headers["Cache-Control"] = "public, max-age=86400"
        return {"image": image}
    client = getattr(request.app.state, "external_api_client", None)
    data = await title_metadata.get_or_fetch(db, client, card["kind"], title_pages.normalize(card["title"]),
                                             card["title"], card["year"], card.get("creator"), wait=6)
    image = title_pages._safe_image((data or {}).get("poster"))
    response.headers["Cache-Control"] = "public, max-age=86400" if image else "no-store"
    return {"image": image}


@router.post("/api/taste-quiz/suggestions")
def taste_quiz_suggestions(payload: QuizAnswers, request: Request, response: Response, db: Session = Depends(get_db)):
    """Picks for a visitor's answers. Nothing is stored."""
    response.headers["Cache-Control"] = "no-store"
    pairs = _pairs(payload)
    rows = taste_quiz.suggestions(pairs, kinds=payload.kinds or None)
    if pairs:
        funnel.record("quiz_finished", request)
    return {"suggestions": _with_details(rows, pick.title_details(title_search.index(db)))}


@router.post("/api/taste-quiz/save")
def taste_quiz_save(payload: QuizAnswers, request: Request, response: Response,
                    user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a member's answers to their library and return picks for them. Existing titles are left untouched."""
    response.headers["Cache-Control"] = "private, no-store"
    pairs = _pairs(payload)
    lock_progress_owner(db, user.id)
    index = title_search.index(db)
    result = taste_quiz.save_answers(db, user, pairs, taste_quiz._art_index(index))
    db.commit()
    rows = taste_quiz.suggestions(pairs, owned=taste_quiz.owned_identities(db, user.id), kinds=payload.kinds or None)
    if pairs:
        funnel.record("quiz_finished" if payload.source == "quiz" else "quiz_imported", request)
    return {**result, "suggestions": _with_details(rows, pick.title_details(index))}
