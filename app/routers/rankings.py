"""Rankings: the endpoints behind the Rankings tab, the home card and the finish dialog (see app/rankings.py)."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, rankings
from ..dependencies import get_current_user, get_db

router = APIRouter(tags=["rankings"])

Category = Literal["movies", "tv-shows", "anime", "video-games", "music", "books", "manga", "podcasts", "audiobooks"]
ItemId = Field(..., ge=1, le=2147483647)


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"


class Title(BaseModel):
    category: Category
    item_id: int = ItemId


class Placing(Title):
    source: Literal["home", "tab", "finish"] = "tab"


class Answer(BaseModel):
    category: Category
    placing_id: int = ItemId
    against_id: int = ItemId
    choice: Literal["placing", "against", "tie"]
    source: Literal["home", "tab", "finish"] = "tab"


class Skip(Title):
    leave_out: bool = False


class Move(Title):
    position: int = Field(..., ge=1, le=rankings.MAX_RANKED)


class Settings(BaseModel):
    category: Category
    public: bool


class Save(BaseModel):
    category: Category
    top: int = Field(default=10, ge=3, le=50)


class Seen(BaseModel):
    where: Literal["home", "tab"]


def _stale(db: Session, user: models.User, category: str) -> JSONResponse:
    """409 with the question that is current now, so the page can show it instead."""
    db.rollback()
    response = JSONResponse(status_code=409, content={
        "detail": "That question had already moved on. Here's the current one.",
        "question": rankings.question(db, user, category),
    })
    _no_store(response)
    return response


@router.get("/api/rankings")
def rankings_overview(request: Request, response: Response, category: Optional[Category] = Query(None),
                      user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Every format at a glance; with ?category= also that format's whole ranking."""
    _no_store(response)
    result = rankings.overview(db, user)
    if category:
        result["detail"] = rankings.detail(db, user, category)
    return result


@router.get("/api/rankings/card")
def rankings_card(request: Request, response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    try:
        return {"card": rankings.home(db, user)}
    except Exception:
        db.rollback()
        return {"card": None}  # optional card; the home screen never waits on it


@router.post("/api/rankings/answer")
def rankings_answer(payload: Answer, request: Request, response: Response,
                    user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    try:
        return rankings.answer(db, user, payload.category, payload.placing_id, payload.against_id, payload.choice,
                               source=payload.source)
    except rankings.Stale:
        return _stale(db, user, payload.category)
    except IntegrityError:
        return _stale(db, user, payload.category)


@router.post("/api/rankings/place")
def rankings_place(payload: Placing, request: Request, response: Response,
                   user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    try:
        return rankings.place(db, user, payload.category, payload.item_id, source=payload.source)
    except LookupError as error:
        db.rollback()
        raise HTTPException(409, str(error))
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That didn't save. Please try again.")


@router.post("/api/rankings/skip")
def rankings_skip(payload: Skip, request: Request, response: Response,
                  user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    try:
        rankings.skip(db, user, payload.category, payload.item_id, payload.leave_out)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That didn't save. Please try again.")
    return {"question": rankings.question(db, user, payload.category)}


@router.post("/api/rankings/move")
def rankings_move(payload: Move, request: Request, response: Response,
                  user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    try:
        position = rankings.move(db, user, payload.category, payload.item_id, payload.position)
    except LookupError as error:
        db.rollback()
        raise HTTPException(404, str(error))
    return {"position": position}


@router.post("/api/rankings/remove")
def rankings_remove(payload: Title, request: Request, response: Response,
                    user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    try:
        rankings.remove(db, user, payload.category, payload.item_id)
    except LookupError as error:
        db.rollback()
        raise HTTPException(404, str(error))
    return {"removed": True}


@router.post("/api/rankings/restore")
def rankings_restore(payload: Title, request: Request, response: Response,
                     user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    rankings.restore(db, user, payload.category, payload.item_id)
    return {"restored": True}


@router.put("/api/rankings/settings")
def rankings_settings(payload: Settings, request: Request, response: Response,
                      user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    try:
        public = rankings.set_public(db, user, payload.category, payload.public)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That didn't save. Please try again.")
    return {"public": public}


@router.post("/api/rankings/collection")
def rankings_collection(payload: Save, request: Request, response: Response,
                        user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    try:
        return rankings.to_collection(db, user, payload.category, payload.top)
    except LookupError as error:
        db.rollback()
        raise HTTPException(409, str(error))


@router.post("/api/rankings/seen")
def rankings_seen(payload: Seen, request: Request, response: Response, user: models.User = Depends(get_current_user)):
    """Counting only: the home card scrolled into view, or the tab opened."""
    _no_store(response)
    rankings.count(f"seen_{payload.where}")
    return {"ok": True}
