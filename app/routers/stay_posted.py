"""The home-screen "stay posted" card and the note after saving a show (see app/stay_posted.py)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, stay_posted
from ..dependencies import get_current_user, get_db

router = APIRouter(tags=["stay posted"])


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"


class Seen(BaseModel):
    moment: str = Field(..., min_length=3, max_length=16)


class Answer(BaseModel):
    answer: str = Field(..., min_length=3, max_length=12)
    place: Literal["card", "after"] = "card"


class AfterSave(BaseModel):
    category: str = Field(..., min_length=2, max_length=16)
    title: str = Field(default="", max_length=300)
    push: bool = False  # this browser can turn notifications on (supported, not blocked, not on yet)


@router.get("/api/stay-posted")
def stay_posted_card(response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    try:
        card = stay_posted.current(db, user)
    except Exception:
        db.rollback()
        card = None  # optional card; the home screen never waits on it
    return {"ask": card}


@router.post("/api/stay-posted/seen")
def stay_posted_seen(payload: Seen, request: Request, response: Response, user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    _no_store(response)
    try:
        return {"shown": stay_posted.mark_shown(db, user, payload.moment)}
    except IntegrityError:
        db.rollback()  # two tabs reported it at once
        return {"shown": True}


@router.post("/api/stay-posted/answer")
def stay_posted_answer(payload: Answer, request: Request, response: Response, user: models.User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    _no_store(response)
    try:
        return {"saved": stay_posted.answer(db, user, payload.answer, payload.place)}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.post("/api/stay-posted/after-save")
def stay_posted_after_save(payload: AfterSave, request: Request, response: Response, user: models.User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    _no_store(response)
    try:
        offer = stay_posted.after_save(db, user, payload.category, payload.title, payload.push)
    except IntegrityError:
        db.rollback()
        offer = None
    return {"offer": offer}
