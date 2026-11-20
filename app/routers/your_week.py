"""Your week: the home-screen card's endpoints (see app/your_week.py)."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, your_week
from ..dependencies import get_current_user, get_db

router = APIRouter(tags=["your week"])


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"


class Local(BaseModel):
    tz: int = Field(default=0, ge=-14 * 60, le=14 * 60)  # minutes east of UTC, from the browser


class Goal(Local):
    goal: Optional[Literal["once", "three", "most", "finish"]] = None


class Remind(Local):
    email: Optional[bool] = None
    push: Optional[bool] = None


class Rest(Local):
    undo: bool = False


def _card(db: Session, user: models.User, tz: int, show: bool = False) -> dict:
    try:
        return {"card": your_week.build(db, user, tz, show=show)}
    except Exception:
        db.rollback()
        return {"card": None}  # optional card; the home screen never waits on it


@router.get("/api/your-week")
def your_week_card(request: Request, response: Response, tz: int = Query(0, ge=-14 * 60, le=14 * 60), show: bool = False,
                   user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    return _card(db, user, tz, show)


@router.post("/api/your-week/goal")
def your_week_goal(payload: Goal, request: Request, response: Response, user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    _no_store(response)
    try:
        your_week.set_goal(db, user, payload.goal, payload.tz)
    except ValueError as error:
        db.rollback()
        raise HTTPException(422, str(error))
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That didn't save. Please try again.")
    return _card(db, user, payload.tz)


@router.post("/api/your-week/remind")
def your_week_remind(payload: Remind, request: Request, response: Response, user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    _no_store(response)
    try:
        your_week.set_reminder(db, user, payload.email, payload.push, payload.tz)
    except ValueError as error:
        db.rollback()
        raise HTTPException(422, str(error))
    return _card(db, user, payload.tz)


@router.post("/api/your-week/rest")
def your_week_rest(payload: Rest, request: Request, response: Response, user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    _no_store(response)
    try:
        your_week.take_rest(db, user, payload.tz, undo=payload.undo)
    except ValueError as error:
        db.rollback()
        raise HTTPException(422, str(error))
    return _card(db, user, payload.tz)


@router.post("/api/your-week/recap")
def your_week_recap(payload: Local, request: Request, response: Response, user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """Last week's recap was read: the card goes back to this week."""
    _no_store(response)
    your_week.recap_seen(db, user, payload.tz)
    return _card(db, user, payload.tz)


@router.post("/api/your-week/seen")
def your_week_seen(payload: Local, request: Request, response: Response, user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    _no_store(response)
    try:
        your_week.mark_seen(db, user, payload.tz)
    except IntegrityError:
        db.rollback()
    return {"ok": True}


@router.post("/api/your-week/hide")
def your_week_hide(request: Request, response: Response, user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    _no_store(response)
    your_week.hide(db, user)
    return {"hidden": True}


@router.post("/api/your-week/show")
def your_week_show(payload: Local, request: Request, response: Response, user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """Opened from a link to the card (/#your-week, the Steady badge): bring a hidden card back."""
    _no_store(response)
    your_week.unhide(db, user)
    return _card(db, user, payload.tz, show=True)
