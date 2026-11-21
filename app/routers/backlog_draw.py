"""Draw from your backlog: the home-screen card's endpoints (see app/backlog_draw.py)."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import backlog_draw, models
from ..dependencies import get_current_user, get_db

router = APIRouter(tags=["backlog draw"])

TODAY = Query(None, max_length=10)


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"


def _today(value: Optional[str]) -> date:
    return backlog_draw.local_today(backlog_draw._now(), value)


class Today(BaseModel):
    today: Optional[str] = Field(default=None, max_length=10)


class Deal(Today):
    deal: int = Field(default=0, ge=0, le=999)


class Pick(Deal):
    category: str = Field(..., max_length=16)
    item_id: int = Field(..., ge=1, le=2147483647)


class Plan(Today):
    night: Optional[date] = None
    email: bool = False
    tz: int = Field(default=0, ge=-14 * 60, le=14 * 60)  # minutes east of UTC, from the browser


class Answer(Today):
    action: Literal["finished", "rate", "later", "not_for_me", "put_back"]
    rating: Optional[int] = Field(default=None, ge=1, le=10)
    draw_id: Optional[int] = Field(default=None, ge=1, le=2147483647)


@router.get("/api/backlog-draw")
def backlog_draw_card(request: Request, response: Response, today: Optional[str] = TODAY, hidden: bool = False,
                      user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    try:
        return {"card": backlog_draw.build(db, user, _today(today), hidden=hidden)}
    except Exception:
        db.rollback()
        return {"card": None}  # optional card; the home screen never waits on it


@router.post("/api/backlog-draw/deal")
def backlog_draw_deal(payload: Deal, request: Request, response: Response, user: models.User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    _no_store(response)
    local = _today(payload.today)
    if backlog_draw.active(db, user.id) is not None:
        raise HTTPException(409, "You've already kept one. Put it back to deal again.")
    cards, total = backlog_draw.deal_hand(db, user, local, payload.deal)
    if not cards:
        raise HTTPException(404, "Nothing is waiting on your list right now.")
    backlog_draw.count("redealt" if payload.deal else "dealt")
    return {"cards": cards, "deal": payload.deal, "total": total}


@router.post("/api/backlog-draw/pick")
def backlog_draw_pick(payload: Pick, request: Request, response: Response, user: models.User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    _no_store(response)
    local = _today(payload.today)
    try:
        backlog_draw.pick(db, user, payload.category, payload.item_id, payload.deal, local)
    except LookupError as error:
        raise HTTPException(404, str(error))
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That didn't save. Please try again.")
    return {"card": backlog_draw.build(db, user, local)}


@router.post("/api/backlog-draw/plan")
def backlog_draw_plan(payload: Plan, request: Request, response: Response, user: models.User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    _no_store(response)
    local = _today(payload.today)
    try:
        backlog_draw.plan(db, user, payload.night, payload.email, payload.tz, local)
    except LookupError as error:
        raise HTTPException(404, str(error))
    except ValueError as error:
        db.rollback()
        raise HTTPException(422, str(error))
    return {"card": backlog_draw.build(db, user, local)}


@router.post("/api/backlog-draw/answer")
def backlog_draw_answer(payload: Answer, request: Request, response: Response, user: models.User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    _no_store(response)
    local = _today(payload.today)
    try:
        result = backlog_draw.answer(db, user, payload.action, payload.rating, payload.draw_id)
    except LookupError as error:
        raise HTTPException(404, str(error))
    except ValueError as error:
        raise HTTPException(422, str(error))
    return {"title": result, "card": backlog_draw.build(db, user, local)}


@router.post("/api/backlog-draw/seen")
def backlog_draw_seen(payload: Today, request: Request, response: Response, user: models.User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    _no_store(response)
    try:
        return backlog_draw.note_seen(db, user, _today(payload.today))
    except IntegrityError:
        db.rollback()
        return {"back": False}


@router.post("/api/backlog-draw/hide")
def backlog_draw_hide(request: Request, response: Response, user: models.User = Depends(get_current_user)):
    """The card is hidden in this browser for a while; this only counts it."""
    _no_store(response)
    backlog_draw.count("hidden")
    return {"hidden": True}


@router.get("/api/backlog-draw/calendar.ics")
def backlog_draw_calendar(request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    body = backlog_draw.calendar_ics(db, user)
    if body is None:
        raise HTTPException(404, "Pick a night first.")
    response = Response(content=body, media_type="text/calendar; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="omnitrackr-night-in.ics"'
    _no_store(response)
    return response
