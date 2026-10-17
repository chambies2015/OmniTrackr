"""Badges: the member's trophy case on the dashboard."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from .. import badges, models
from ..dependencies import get_current_user, get_db

router = APIRouter(tags=["badges"])


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.get("/api/badges")
def list_badges(request: Request, response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Every badge with progress toward its next tier. New tiers are recorded and announced once."""
    _no_store(response)
    return badges.payload(db, user)


@router.post("/api/badges/seen")
def badges_seen(request: Request, response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The member dismissed the dashboard celebration."""
    _no_store(response)
    return {"seen": badges.mark_seen(db, user.id)}
