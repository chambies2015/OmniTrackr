"""Dashboard card: share private reviews on title pages (see app/review_inbox.py)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import review_inbox
from ..dependencies import get_current_user, get_db
from ..integer_bounds import PositiveDatabaseId
from ..progress import lock_progress_owner

router = APIRouter(tags=["review-inbox"])

Category = Literal["movie", "tv_show", "anime", "video_game", "music", "book", "manga", "podcast", "audiobook"]


class ReviewRef(BaseModel):
    category: Category
    item_id: PositiveDatabaseId


class ReviewAnswer(ReviewRef):
    version: str = Field(..., min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class ReviewShare(ReviewAnswer):
    spoilers: bool = False


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _apply(db: Session, action):
    try:
        result = action()
    except review_inbox.ShareError as error:
        db.rollback()
        raise HTTPException(error.status, error.message)
    db.commit()
    return result


@router.get("/api/review-inbox")
def list_reviews(response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    return review_inbox.candidates(db, user)


@router.post("/api/review-inbox/share")
def share_review(payload: ReviewShare, request: Request, response: Response,
                  user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    lock_progress_owner(db, user.id)
    return _apply(db, lambda: review_inbox.share(db, user, payload.category, payload.item_id, payload.version, payload.spoilers))


@router.post("/api/review-inbox/keep")
def keep_review(payload: ReviewAnswer, request: Request, response: Response,
                 user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    lock_progress_owner(db, user.id)
    return _apply(db, lambda: review_inbox.keep_private(db, user, payload.category, payload.item_id, payload.version))


@router.post("/api/review-inbox/undo")
def undo_answer(payload: ReviewRef, request: Request, response: Response,
                 user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    lock_progress_owner(db, user.id)
    return _apply(db, lambda: review_inbox.undo(db, user, payload.category, payload.item_id))
