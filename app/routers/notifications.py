"""
Notifications endpoints for the OmniTrackr API.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..integer_bounds import PositiveDatabaseId
from .. import crud, schemas, models, web_push
from ..dependencies import get_db, get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])
NOTIFICATION_LIST_LIMIT = 200
NOTIFICATION_UNREAD_LIMIT = 300


@router.get("", response_model=List[schemas.NotificationResponse])
async def get_notifications(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """The current user's notifications, newest first.

    The bell lists the newest NOTIFICATION_LIST_LIMIT, plus older ones still unread,
    instead of every notification ever received.
    """
    notifications = crud.get_notifications(db, current_user.id, limit=NOTIFICATION_LIST_LIMIT,
                                           unread_limit=NOTIFICATION_UNREAD_LIMIT)
    return [schemas.NotificationResponse.model_validate(notif) for notif in notifications]


@router.get("/count", response_model=schemas.NotificationCount)
async def get_notification_count(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get unread notification count."""
    count = crud.get_unread_notification_count(db, current_user.id)
    return schemas.NotificationCount(count=count)


class PushKeys(BaseModel):
    p256dh: str = Field(max_length=128)
    auth: str = Field(max_length=64)


class PushSubscriptionIn(BaseModel):
    endpoint: str = Field(max_length=1024)
    keys: PushKeys


class PushEndpoint(BaseModel):
    endpoint: str = Field(max_length=1024)


@router.get("/push/key")
async def push_public_key(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The key this device subscribes with, and whether this member has any device turned on."""
    devices = db.query(models.PushSubscription).filter(models.PushSubscription.user_id == current_user.id).count()
    return {"public_key": web_push.public_key(db), "devices": devices}


@router.post("/push/subscription")
async def save_push_subscription(body: PushSubscriptionIn, current_user: models.User = Depends(get_current_user),
                                 db: Session = Depends(get_db)):
    """Turn on phone/desktop notifications for the device that sent this subscription."""
    if not web_push.valid_endpoint(body.endpoint):
        raise HTTPException(status_code=422, detail="This browser's push service isn't supported.")
    if not web_push.valid_keys(body.keys.p256dh, body.keys.auth):
        raise HTTPException(status_code=422, detail="This browser sent an invalid subscription.")
    fresh = web_push.save_subscription(db, current_user.id, body.endpoint, body.keys.p256dh, body.keys.auth)
    if fresh:
        # A confirmation in the bell, which is also pushed so the member sees it work right away.
        db.add(models.Notification(user_id=current_user.id, type="push_enabled", link="/",
                                   message="Notifications are on for this device. You can turn them off from the bell."))
        db.commit()
    return {"enabled": True, "new": fresh}


@router.post("/push/subscription/remove")
async def remove_push_subscription(body: PushEndpoint, current_user: models.User = Depends(get_current_user),
                                   db: Session = Depends(get_db)):
    """Turn off notifications for one device (also called when signing out)."""
    removed = web_push.remove_subscription(db, current_user.id, body.endpoint)
    return {"enabled": False, "removed": removed}


@router.delete("/{notification_id}", response_model=dict)
async def dismiss_notification(
    notification_id: PositiveDatabaseId,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dismiss/delete a notification."""
    success = crud.delete_notification(db, notification_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification dismissed"}

