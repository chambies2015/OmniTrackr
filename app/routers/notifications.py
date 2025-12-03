"""
Notifications endpoints for the OmniTrackr API.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas, models
from ..dependencies import get_db, get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=List[schemas.NotificationResponse])
async def get_notifications(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all notifications for the current user (newest first)."""
    notifications = crud.get_notifications(db, current_user.id)
    return [schemas.NotificationResponse.model_validate(notif) for notif in notifications]


@router.get("/count", response_model=schemas.NotificationCount)
async def get_notification_count(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get unread notification count."""
    count = crud.get_unread_notification_count(db, current_user.id)
    return schemas.NotificationCount(count=count)


@router.delete("/{notification_id}", response_model=dict)
async def dismiss_notification(
    notification_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dismiss/delete a notification."""
    success = crud.delete_notification(db, notification_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification dismissed"}

