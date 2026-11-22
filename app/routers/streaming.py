"""The "On your services" home card: pick streaming services, see what on your list streams there (app/streaming_services.py)."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, streaming_services
from ..dependencies import get_current_user, get_db

router = APIRouter(tags=["streaming services"])


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"


class Choice(BaseModel):
    services: Optional[list[str]] = Field(default=None, max_length=40)
    alerts: Optional[bool] = None


class Answer(BaseModel):
    answer: Literal["later", "stop", "hide", "show"]


class Event(BaseModel):
    event: Literal["where", "queued", "opened", "filter", "from_alert", "seen_choose", "seen_list"]


def _card(db: Session, user: models.User) -> Optional[dict]:
    try:
        return streaming_services.card(db, user)
    except Exception:
        db.rollback()
        return None  # optional card; the home screen never waits on it


@router.get("/api/streaming")
def streaming_card(request: Request, response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    return {"card": _card(db, user), "chosen": streaming_services.picked_names(db, user.id)}


@router.put("/api/streaming")
def streaming_save(payload: Choice, request: Request, response: Response, background: BackgroundTasks,
                   user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    for service in payload.services or []:
        if not isinstance(service, str) or len(service) > 24:
            raise HTTPException(status_code=422, detail="Unknown streaming service")
    try:
        streaming_services.save(db, user, payload.services, payload.alerts)
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error))
    except IntegrityError:
        db.rollback()  # two tabs saved at once; the other one won
    if payload.services:
        # What's already cached shows straight away; the rest is looked up after this response.
        streaming_services.sync_member(db, user.id)
        background.add_task(streaming_services.after_save, request.app, user.id)
    return {"card": _card(db, user), "chosen": streaming_services.picked_names(db, user.id)}


@router.post("/api/streaming/answer")
def streaming_answer(payload: Answer, request: Request, response: Response, user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    _no_store(response)
    try:
        streaming_services.answer(db, user, payload.answer)
    except IntegrityError:
        db.rollback()
    return {"card": _card(db, user) if payload.answer == "show" else None}


@router.post("/api/streaming/event")
def streaming_event(payload: Event, request: Request, response: Response, user: models.User = Depends(get_current_user)):
    _no_store(response)
    return {"counted": streaming_services.count(payload.event)}
