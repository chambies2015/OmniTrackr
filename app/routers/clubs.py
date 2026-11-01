"""Watch clubs on shared lists (/api/lists/<id>/club): one pick, a finish-by date, progress and a discussion."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import clubs, funnel, shared_lists
from ..dependencies import get_current_user, get_db
from ..integer_bounds import PositiveDatabaseId
from .shared_lists import _fail, _member_list, _private

router = APIRouter(tags=["clubs"])


class ClubStart(BaseModel):
    item_id: PositiveDatabaseId
    ends_on: date


class ClubDate(BaseModel):
    ends_on: date


class ClubProgress(BaseModel):
    status: Optional[Literal["started", "finished"]] = None
    score: Optional[int] = Field(None, ge=1, le=10)


class ClubPost(BaseModel):
    body: str = Field(..., max_length=1000)
    spoiler: bool = False


@router.get("/clubs", include_in_schema=False)
def clubs_page():
    """A short address for sharing; clubs live on shared lists."""
    return RedirectResponse("/lists", status_code=302)


def _member_round(db, list_id, round_id, user):
    shared, member = _member_list(db, list_id, user)
    try:
        return shared, clubs.get_round(db, shared, round_id)
    except shared_lists.ListError as error:
        _fail(error)


@router.post("/api/lists/{list_id}/club", status_code=201)
def start_pick(list_id: PositiveDatabaseId, payload: ClubStart, request: Request, response: Response,
               user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    shared, _ = _member_list(db, list_id, user)
    try:
        picked = clubs.start(db, shared, user, payload.item_id, payload.ends_on)
    except shared_lists.ListError as error:
        _fail(error)
    funnel.record("club_pick_started", request)
    return {"id": picked.id, "title": picked.title, "ends_on": picked.ends_on.isoformat()}


@router.patch("/api/lists/{list_id}/club/{round_id}")
def move_date(list_id: PositiveDatabaseId, round_id: PositiveDatabaseId, payload: ClubDate, response: Response,
              user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    shared, picked = _member_round(db, list_id, round_id, user)
    try:
        clubs.change_date(db, shared, picked, user, payload.ends_on)
    except shared_lists.ListError as error:
        _fail(error)
    return {"ends_on": picked.ends_on.isoformat()}


@router.post("/api/lists/{list_id}/club/{round_id}/finish")
def wrap_up(list_id: PositiveDatabaseId, round_id: PositiveDatabaseId, response: Response,
            user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    shared, picked = _member_round(db, list_id, round_id, user)
    try:
        clubs.finish(db, shared, picked, user)
    except shared_lists.ListError as error:
        _fail(error)
    return {"ended": True}


@router.delete("/api/lists/{list_id}/club/{round_id}", status_code=204)
def drop_pick(list_id: PositiveDatabaseId, round_id: PositiveDatabaseId,
              user=Depends(get_current_user), db: Session = Depends(get_db)):
    shared, picked = _member_round(db, list_id, round_id, user)
    try:
        clubs.cancel(db, shared, picked, user)
    except shared_lists.ListError as error:
        _fail(error)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@router.put("/api/lists/{list_id}/club/{round_id}/progress")
def my_progress(list_id: PositiveDatabaseId, round_id: PositiveDatabaseId, payload: ClubProgress, response: Response,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    _, picked = _member_round(db, list_id, round_id, user)
    try:
        clubs.set_progress(db, picked, user, payload.status, payload.score)
    except shared_lists.ListError as error:
        _fail(error)
    return {"status": payload.status, "score": payload.score}


@router.get("/api/lists/{list_id}/club/{round_id}/posts")
def round_posts(list_id: PositiveDatabaseId, round_id: PositiveDatabaseId, response: Response,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    """A wrapped-up pick's discussion, for the club's history."""
    _private(response)
    shared, picked = _member_round(db, list_id, round_id, user)
    return {"posts": clubs.past_posts(db, shared, picked, user)}


@router.post("/api/lists/{list_id}/club/{round_id}/posts", status_code=201)
def add_post(list_id: PositiveDatabaseId, round_id: PositiveDatabaseId, payload: ClubPost, request: Request,
             response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    shared, picked = _member_round(db, list_id, round_id, user)
    try:
        post = clubs.add_post(db, shared, picked, user, payload.body, payload.spoiler)
    except shared_lists.ListError as error:
        _fail(error)
    funnel.record("club_post", request)
    return {"id": post.id}


@router.delete("/api/lists/{list_id}/club/{round_id}/posts/{post_id}", status_code=204)
def delete_post(list_id: PositiveDatabaseId, round_id: PositiveDatabaseId, post_id: PositiveDatabaseId,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    shared, picked = _member_round(db, list_id, round_id, user)
    try:
        clubs.delete_post(db, shared, picked, user, post_id)
    except shared_lists.ListError as error:
        _fail(error)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})
