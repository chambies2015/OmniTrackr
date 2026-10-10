"""Yearly goals: the member's private targets and their progress."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import goals, models
from ..dependencies import get_current_user, get_db

router = APIRouter(tags=["goals"])


class GoalTarget(BaseModel):
    target: int


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.get("/api/goals")
def list_goals(response: Response, year: Optional[int] = None,
               user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    year = year or datetime.utcnow().year
    if not 2000 <= year <= max(goals.allowed_years()):
        raise HTTPException(status_code=422, detail="Goals can be set for this year or next year.")
    return goals.payload(db, user, year)


@router.put("/api/goals/{year}/{category}")
def save_goal(year: int, category: str, body: GoalTarget, request: Request, response: Response,
              user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    try:
        goals.save(db, user.id, year, category, body.target)
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error))
    return goals.payload(db, user, year)


@router.delete("/api/goals/{year}/{category}")
def delete_goal(year: int, category: str, request: Request, response: Response,
                user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    if not goals.remove(db, user.id, year, category):
        raise HTTPException(status_code=404, detail="No goal to remove.")
    return goals.payload(db, user, year)
