"""Find people endpoints (see app/people_to_follow.py).

* ``GET /api/people/suggestions`` is the Find people view on the friends feed tab.
* ``GET /api/people/rail`` is the short "People you might follow" card in its rail.
* ``POST``/``DELETE /api/people/dismiss/{user_id}`` hide and bring back one suggestion.
* ``POST /api/people/event`` counts a browser-only press for Site stats (names listed in the module).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models, people_to_follow
from ..dependencies import get_current_user, get_db
from ..integer_bounds import PositiveDatabaseId
from ..visitor_identity import VISITOR_COOKIE, visitor_identity

router = APIRouter(tags=["find people"])


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"


def _visitor(request: Request):
    # Only an existing browser cookie counts: a new visitor id has marked nothing helpful.
    return visitor_identity(request)[0] if request.cookies.get(VISITOR_COOKIE) else None


class PeopleEvent(BaseModel):
    name: str = Field(..., max_length=40)


@router.get("/api/people/suggestions")
def people_suggestions(request: Request, response: Response, user: models.User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    _private(response)
    data = people_to_follow.suggestions(db, user, _visitor(request))
    found = bool(data["follow_back"]) or any(group["people"] for group in data["groups"])
    people_to_follow.count("page_shown" if found else "page_empty")
    return data


@router.get("/api/people/rail")
def people_rail(request: Request, response: Response, user: models.User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    _private(response)
    data = people_to_follow.rail(db, user, _visitor(request))
    if data["people"]:
        people_to_follow.count("rail_shown")
    return data


@router.post("/api/people/dismiss/{user_id:database_id}")
def dismiss(user_id: PositiveDatabaseId, request: Request, response: Response,
            user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    if user_id == user.id:
        raise HTTPException(422, "That's you.")
    created = people_to_follow.dismiss(db, user, user_id)
    if created:
        people_to_follow.count("dismissed")
    return {"dismissed": True, "created": created}


@router.delete("/api/people/dismiss/{user_id:database_id}")
def undismiss(user_id: PositiveDatabaseId, request: Request, response: Response,
              user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    removed = people_to_follow.undismiss(db, user, user_id)
    if removed:
        people_to_follow.count("undismissed")
    return {"dismissed": False, "removed": removed}


@router.post("/api/people/event")
def people_event(body: PeopleEvent, request: Request, response: Response,
                 user: models.User = Depends(get_current_user)):
    _private(response)
    name = body.name.strip().lower()
    if name not in people_to_follow.CLIENT_COUNTERS:
        raise HTTPException(422, "Unknown event")
    people_to_follow.count(name)
    return {"ok": True}
