"""The first-week home card for new members (see app/week_one.py)."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import episode_calendar, models, week_one
from ..dependencies import get_current_user, get_db

router = APIRouter(tags=["first week"])

TODAY = Query(None, max_length=10)


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"


class Today(BaseModel):
    today: Optional[str] = Field(default=None, max_length=10)


class Remind(Today):
    day: date
    tz: int = Field(default=0, ge=-14 * 60, le=14 * 60)  # minutes east of UTC, from the browser
    place: Literal["card", "start"] = "card"


class SaveRelease(Today):
    category: str = Field(..., max_length=10)
    window: str = Field(..., max_length=20)
    key: str = Field(..., min_length=1, max_length=80)


class Save(Today):
    key: str = Field(..., min_length=8, max_length=300)


@router.get("/api/week-one")
def week_one_card(request: Request, response: Response, today: Optional[str] = TODAY,
                  user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    local = week_one.local_today(week_one._now(), today)
    try:
        card = week_one.build(db, user, local)
    except Exception:
        db.rollback()
        return {"card": None}  # optional card; the home screen never waits on it
    if card is not None and episode_calendar._stale_shows(db, [user.id]):
        # A show saved a minute ago has no air dates yet; fetch them so the next look has them.
        episode_calendar.queue_member(request.app, user.id)
        card["pending"] = True
    return {"card": card}


@router.post("/api/week-one/seen")
def week_one_seen(payload: Today, request: Request, response: Response, user: models.User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    _no_store(response)
    try:
        return {"seen": week_one.mark_seen(db, user, week_one.local_today(week_one._now(), payload.today))}
    except IntegrityError:
        db.rollback()  # two tabs reported it at once
        return {"seen": True}


@router.post("/api/week-one/save")
def week_one_save(payload: Save, request: Request, response: Response, user: models.User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    _no_store(response)
    local = week_one.local_today(week_one._now(), payload.today)
    if week_one.day_number(user, local) is None:
        raise HTTPException(403, "This list is for an account's first week.")
    try:
        saved = week_one.save_suggestion(db, user, payload.key, local)
    except LookupError as error:
        raise HTTPException(404, str(error))
    episode_calendar.queue_member(request.app, user.id)
    return saved


@router.post("/api/week-one/save-release")
def week_one_save_release(payload: SaveRelease, request: Request, response: Response,
                          user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    if week_one.day_number(user, week_one.local_today(week_one._now(), payload.today)) is None:
        raise HTTPException(403, "This list is for an account's first week.")
    return week_one.save_release(db, user, payload.category, payload.window, payload.key)


@router.post("/api/week-one/start-seen")
def week_one_start_seen(payload: Today, request: Request, response: Response,
                        user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    try:
        return {"seen": week_one.note_start_seen(db, user, week_one.local_today(week_one._now(), payload.today))}
    except IntegrityError:
        db.rollback()
        return {"seen": True}


@router.put("/api/week-one/reminder")
def week_one_remind(payload: Remind, request: Request, response: Response, user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    _no_store(response)
    local = week_one.local_today(week_one._now(), payload.today)
    try:
        return {"reminder": week_one.set_reminder(db, user, payload.day, local, payload.tz, place=payload.place)}
    except ValueError as error:
        raise HTTPException(422, str(error))
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That didn't save. Please try again.")


@router.delete("/api/week-one/reminder")
def week_one_cancel(request: Request, response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    return {"cancelled": week_one.cancel_reminder(db, user)}


@router.post("/api/week-one/push")
def week_one_push(request: Request, response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    try:
        return {"counted": week_one.note_push(db, user)}
    except IntegrityError:
        db.rollback()
        return {"counted": False}


@router.post("/api/week-one/hide")
def week_one_hide(request: Request, response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    try:
        return {"hidden": week_one.hide(db, user)}
    except IntegrityError:
        db.rollback()
        return {"hidden": week_one.hide(db, user)}
