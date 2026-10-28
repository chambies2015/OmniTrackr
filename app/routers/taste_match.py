"""Taste Match endpoints: compare libraries with a friend and save their favorites."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import crud, funnel, models, taste_match
from ..dependencies import get_current_user, get_db
from ..integer_bounds import PositiveDatabaseId
from ..progress import lock_progress_owner

router = APIRouter(tags=["friends"])


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _friend(db: Session, user: models.User, friend_id: int) -> models.User:
    if not crud.are_friends(db, user.id, friend_id):
        raise HTTPException(403, "You are not friends with this user")
    friend = crud.get_user_by_id(db, friend_id)
    if friend is None:
        raise HTTPException(404, "Friend not found")
    return friend


@router.get("/api/taste-match/friends")
def friends_overview(request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """A score per friend for the friends list, best match first."""
    _private(response)
    scores = taste_match.friend_scores(db, user, crud.get_friends(db, user.id))
    scores.sort(key=lambda row: (row["score"] is None, -(row["score"] or 0), -row["shared_count"]))
    return {"friends": scores}


@router.get("/api/taste-match/friends/{friend_id}")
def friend_match(friend_id: PositiveDatabaseId, request: Request, response: Response,
                 user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    result = taste_match.match(db, user, _friend(db, user, friend_id))
    funnel.record("taste_match_viewed", request)
    return result


class TasteMatchAdd(BaseModel):
    category: Literal["movies", "tv-shows", "anime", "video-games", "music", "books", "manga", "podcasts"]
    title: str = Field(min_length=1, max_length=200)


@router.post("/api/taste-match/friends/{friend_id}/add")
def add_friend_pick(friend_id: PositiveDatabaseId, selection: TasteMatchAdd, request: Request, response: Response,
                    user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Copy a friend's title (public details only) into the member's library as not started."""
    _private(response)
    friend = _friend(db, user, friend_id)
    source = taste_match.find_friend_entry(db, friend, selection.category, selection.title)
    if source is None:
        raise HTTPException(404, "That title is no longer on your friend's shelves.")
    lock_progress_owner(db, user.id)
    library_url = f"/?library_category={selection.category}&library_item="
    existing = taste_match.find_own_entry(db, user.id, selection.category, source.title)
    if existing is not None:
        db.rollback()
        return {"state": "existing", "title": existing.title, "category": selection.category,
                "library_url": f"{library_url}{existing.id}"}
    model = taste_match.LIBRARY[selection.category][0]
    record = model(user_id=user.id, **taste_match.copy_payload(selection.category, source))
    flag = taste_match.DONE_FIELD[selection.category]
    setattr(record, flag, False)
    db.add(record)
    db.commit()
    db.refresh(record)
    funnel.record("taste_match_saved", request)
    return {"state": "created", "title": record.title, "category": selection.category,
            "library_url": f"{library_url}{record.id}"}
