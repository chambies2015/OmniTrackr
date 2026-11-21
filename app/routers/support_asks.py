"""The dashboard's occasional "support OmniTrackr" note, its settings switch, and /supporters page counters."""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, support_asks
from ..dependencies import get_current_user, get_db, get_optional_current_user
from ..site_traffic import BOT_PATTERN, RECORDER

router = APIRouter(tags=["supporters"])


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"


class AskKey(BaseModel):
    key: str = Field(..., min_length=3, max_length=48)


class AskAnswer(AskKey):
    answer: str = Field(..., min_length=3, max_length=8)


class AskSettings(BaseModel):
    on: bool


@router.get("/api/support-ask")
def support_ask(response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The note to show on the dashboard now, if any. Looking doesn't count as shown."""
    _no_store(response)
    try:
        ask = support_asks.current(db, user)
    except Exception:
        db.rollback()
        ask = None  # The note is optional; the dashboard never waits on it.
    return {"ask": ask, "asks_off": support_asks.is_stopped(db, user.id)}


@router.post("/api/support-ask/seen")
def support_ask_seen(payload: AskKey, request: Request, response: Response, user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    _no_store(response)
    try:
        return {"shown": support_asks.mark_shown(db, user, payload.key)}
    except IntegrityError:
        db.rollback()  # two tabs reported the same note at once; the other one counted it
        return {"shown": True}


@router.post("/api/support-ask/answer")
def support_ask_answer(payload: AskAnswer, request: Request, response: Response, user: models.User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    _no_store(response)
    try:
        saved = support_asks.answer(db, user, payload.key, payload.answer)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    return {"saved": saved, "asks_off": support_asks.is_stopped(db, user.id)}


@router.put("/api/support-ask/settings")
def support_ask_settings(payload: AskSettings, request: Request, response: Response, user: models.User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    _no_store(response)
    on = support_asks.set_on(db, user, payload.on)
    return {"asks_off": not on}


@router.get("/api/support/me")
def support_me(response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The signed-in member's own numbers, for the line at the top of /supporters."""
    _no_store(response)
    return support_asks.member_summary(db, user)


class PageEvent(BaseModel):
    event: str = Field(..., max_length=16)
    place: str = Field(..., max_length=16)


@router.post("/api/support/event", status_code=204, include_in_schema=False)
def support_page_event(payload: PageEvent, request: Request, user: Optional[models.User] = Depends(get_optional_current_user),
                       db: Session = Depends(get_db)):
    """/supporters reporting a visit (with where it came from) or a Ko-fi button press. Names outside the
    lists are ignored, and nothing about the visitor is stored with the count."""
    places = {"page_seen": support_asks.PAGE_SOURCES, "page_kofi": support_asks.PAGE_PLACES}.get(payload.event)
    if places is None or payload.place not in places:
        return Response(status_code=204)
    if BOT_PATTERN.search(request.headers.get("user-agent", "") or "x"):
        return Response(status_code=204)
    if support_asks.count(f"{payload.event}_{payload.place}"):
        try:
            if RECORDER.flush_due():
                asyncio.get_running_loop().create_task(asyncio.to_thread(RECORDER.flush))
        except RuntimeError:
            pass
    if payload.event == "page_kofi" and user is not None:
        try:
            support_asks.note_kofi_press(db, user, payload.place)
        except Exception:
            db.rollback()
    return Response(status_code=204)
