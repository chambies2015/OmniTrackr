"""The member's own weekly email, shown in place and sent once on request (see app/weekly_preview.py)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from .. import episode_calendar, models, weekly_preview
from ..dependencies import get_current_user, get_db

router = APIRouter(tags=["weekly email"])


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"


def _client(request: Request):
    return getattr(request.app.state, "external_api_client", None)


@router.get("/api/weekly-email/preview")
def weekly_email_preview(request: Request, response: Response,
                         place: Literal["settings", "for_you", "home_card"] = Query("settings"),
                         user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    try:
        data = weekly_preview.summary(db, user, client=_client(request))
    except Exception as error:
        db.rollback()
        print(f"Weekly email preview for user {user.id} failed: {error}")
        raise HTTPException(503, "Couldn't build your preview just now. Try again in a minute.")
    try:
        # Non-subscribers' shows aren't refreshed by the weekly sweep, so fetch their dates now.
        if episode_calendar._stale_shows(db, [user.id]):
            episode_calendar.queue_member(request.app, user.id)
            data["refreshing"] = True
    except Exception:
        db.rollback()
    weekly_preview.count(f"preview_{place}")
    return data


@router.post("/api/weekly-email/copy")
async def weekly_email_copy(request: Request, response: Response,
                            user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    try:
        return await weekly_preview.send_copy(db, user, client=_client(request))
    except weekly_preview.CopyRefused as refused:
        raise HTTPException(409 if refused.reason in ("recent", "subscribed") else 400,
                            {"reason": refused.reason, "message": refused.message})
