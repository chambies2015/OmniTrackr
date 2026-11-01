"""Follow endpoints: following public profiles, the Following feed, and follower settings.

* ``POST /api/follows/{user_id}`` and ``DELETE /api/follows/{user_id}`` follow and unfollow.
* ``GET /api/follows/feed`` lists public reviews, collections and diary entries from people you follow.
* ``GET /api/follows/suggestions`` suggests people from reviews you found helpful and collections you saved.
* ``GET``/``PUT /api/follows/settings`` and the follower list endpoints manage who follows you.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import follows, models, public_profiles
from ..dependencies import get_current_user, get_db
from ..integer_bounds import PositiveDatabaseId
from ..visitor_identity import VISITOR_COOKIE, visitor_identity

router = APIRouter(tags=["follows"])


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


class FollowSettingsBody(BaseModel):
    allow_followers: Optional[bool] = None
    email_following: Optional[bool] = None


@router.post("/api/follows/{user_id:database_id}")
def follow(user_id: PositiveDatabaseId, request: Request, response: Response,
           user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    target = public_profiles.find_user_by_id(db, user_id)
    try:
        created = follows.follow(db, user, target)
    except follows.FollowError as error:
        db.rollback()
        raise HTTPException(error.status, error.detail)
    return {"following": True, "created": created, "followers": follows.counts(db, user_id)["followers"]}


@router.delete("/api/follows/{user_id:database_id}")
def unfollow(user_id: PositiveDatabaseId, request: Request, response: Response,
             user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    removed = follows.unfollow(db, user.id, user_id)
    return {"following": False, "removed": removed, "followers": follows.counts(db, user_id)["followers"]}


@router.get("/api/follows/feed")
def following_feed(response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    items = [follows.serialize(item) for item in follows.feed(db, user.id)]
    return {"items": items, "following": follows.counts(db, user.id)["following"]}


@router.get("/api/follows/suggestions")
def suggestions(request: Request, response: Response, user: models.User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    _private(response)
    # Only an existing browser cookie counts: a new visitor id has marked nothing helpful.
    visitor_hash = visitor_identity(request)[0] if request.cookies.get(VISITOR_COOKIE) else None
    return {"people": follows.suggestions(db, user, visitor_hash)}


@router.get("/api/follows/settings")
def settings(response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    return {**follows.settings_payload(db, user.id), "followers": follows.followers_list(db, user.id),
            "following": follows.following_list(db, user.id), "removed": follows.barred_list(db, user.id)}


@router.put("/api/follows/settings")
def update_settings(body: FollowSettingsBody, response: Response, user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    _private(response)
    follows.save_settings(db, user.id, body.allow_followers, body.email_following)
    return settings(response, user, db)


@router.delete("/api/follows/followers/{user_id:database_id}")
def remove_follower(user_id: PositiveDatabaseId, request: Request, response: Response,
                    user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    follows.remove_follower(db, user.id, user_id)
    return settings(response, user, db)


@router.delete("/api/follows/removed/{user_id:database_id}")
def allow_again(user_id: PositiveDatabaseId, response: Response, user: models.User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    _private(response)
    follows.allow_again(db, user.id, user_id)
    return settings(response, user, db)
