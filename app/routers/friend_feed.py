"""Friends feed endpoints: the feed itself, the sharing switch, cheers and "save to my library".

* ``GET /api/friend-feed`` lists friends' recent adds, finishes, ratings and reviews.
* ``POST /api/friend-feed/sharing`` turns the member's own updates on or off for friends.
* ``POST /api/friend-feed/cheer`` cheers a friend's title once; the friend gets a notification.
* ``POST /api/friend-feed/save`` copies the title's public facts (never the friend's rating,
  review or progress) into the member's library, optionally onto Next Up.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import friend_feed, models, title_origins
from ..dependencies import get_current_user, get_db
from ..for_you import LIBRARY
from ..integer_bounds import PositiveDatabaseId
from ..progress import lock_progress_owner
from .friend_recs import COMPLETE_FIELD, _details, _new_item, _same_title
from .next_up import enqueue

router = APIRouter(tags=["friend-feed"])
FEED_LINK = "/#friends-feed"
DAILY_CHEER_LIMIT = 200


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


class SharingBody(BaseModel):
    sharing: bool


class FeedTitle(BaseModel):
    friend_id: PositiveDatabaseId
    category: str = Field(..., max_length=20)
    item_id: PositiveDatabaseId


class SaveBody(FeedTitle):
    next_up: bool = False


def _cursor(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, "Invalid cursor")
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


@router.get("/api/friend-feed")
def feed(response: Response, before: Optional[str] = Query(None, max_length=40),
         limit: int = Query(friend_feed.PAGE_SIZE, ge=1, le=50),
         user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    data = friend_feed.page(db, user.id, before=_cursor(before), limit=limit)
    data["sharing"] = friend_feed.sharing(db, user.id)
    return data


@router.post("/api/friend-feed/sharing")
def update_sharing(body: SharingBody, response: Response, user=Depends(get_current_user),
                   db: Session = Depends(get_db)):
    _private(response)
    return {"sharing": friend_feed.set_sharing(db, user.id, body.sharing)}


def _visible(db: Session, user, body: FeedTitle):
    item = friend_feed.visible_item(db, user.id, body.friend_id, body.category, body.item_id)
    if item is None:
        raise HTTPException(404, "That title isn't on your friends feed")
    return item


@router.post("/api/friend-feed/cheer")
def cheer(body: FeedTitle, request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Cheer a friend's title. Cheering twice does nothing; only the first one notifies."""
    _private(response)
    item = _visible(db, user, body)
    count = lambda: db.query(models.FriendFeedCheer).filter_by(
        owner_id=body.friend_id, category=body.category, item_id=item.id).count()
    if db.query(models.FriendFeedCheer.id).filter_by(user_id=user.id, category=body.category,
                                                     item_id=item.id).first():
        return {"cheered": True, "cheers": count(), "created": False}
    today = db.query(models.FriendFeedCheer.id).filter(
        models.FriendFeedCheer.user_id == user.id,
        models.FriendFeedCheer.created_at > datetime.utcnow() - timedelta(days=1)).count()
    if today >= DAILY_CHEER_LIMIT:
        raise HTTPException(429, "That's a lot of cheering for one day. Try again tomorrow.")
    db.add(models.FriendFeedCheer(user_id=user.id, owner_id=body.friend_id, category=body.category, item_id=item.id))
    title = item.title.strip()
    if getattr(item, COMPLETE_FIELD[body.category], False):
        message = f"{user.username} cheered you for finishing {title}."
    elif (item.review or "").strip():
        message = f"{user.username} cheered your review of {title}."
    else:
        message = f"{user.username} cheered you adding {title}."
    db.add(models.Notification(user_id=body.friend_id, type="friend_feed_cheer", message=message[:250],
                               link=FEED_LINK))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"cheered": True, "cheers": count(), "created": False}
    return {"cheered": True, "cheers": count(), "created": True}


@router.post("/api/friend-feed/save")
def save(body: SaveBody, request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Put a friend's title in the member's own library, unfinished and unrated."""
    _private(response)
    lock_progress_owner(db, user.id)
    source = _visible(db, user, body)
    model = LIBRARY[body.category][0]
    title = source.title.strip()
    item = db.query(model).filter(model.user_id == user.id, _same_title(model.title, title)).first()
    created = item is None
    if created:
        item = _new_item(user.id, body.category, _details(body.category, source))
        db.add(item)
        db.flush()
        title_origins.prefill(db, user.id, body.category, item.id, "friend",
                              friend=db.get(models.User, body.friend_id), note="Saved from the friends feed")
    queued = False
    if body.next_up and not getattr(item, COMPLETE_FIELD[body.category], False):
        queued = enqueue(db, user.id, body.category, item.id)
    db.commit()
    return {"created": created, "queued": queued, "category": body.category, "item_id": item.id, "title": title}
