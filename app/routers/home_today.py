"""GET /api/home/today: what's new for the signed-in member, for the home screen."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from .. import episode_calendar, home_today
from ..dependencies import get_current_user, get_db

router = APIRouter(tags=["home"])


def _since(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@router.get("/api/home/today")
def today(request: Request, response: Response, since: Optional[str] = Query(None, max_length=40),
          user=Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    data = home_today.build(db, user, since=_since(since))
    if data.pop("stale_shows", 0):
        # Fetch this member's air dates soon, so the next visit has them. Queued at most once at a time.
        episode_calendar.queue_member(request.app, user.id)
    return data
