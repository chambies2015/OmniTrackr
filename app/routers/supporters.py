"""Ko-fi supporter tier: the Ko-fi webhook, the member's supporter settings, and admin linking."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models, public_profiles, supporters
from ..admin_access import is_site_admin
from ..dependencies import get_current_user, get_db

router = APIRouter(tags=["supporters"])


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"


@router.post("/api/kofi/webhook", include_in_schema=False)
async def kofi_webhook(request: Request, db: Session = Depends(get_db)):
    """Ko-fi posts form data with one field, ``data``, holding the payment as JSON."""
    try:
        form = await request.form()
        raw = form.get("data")
    except Exception:
        raw = None
    try:
        result = supporters.handle_webhook(db, supporters.parse_payload(raw if isinstance(raw, str) else None))
    except supporters.WebhookError as error:
        raise HTTPException(status_code=error.status, detail=error.detail)
    return result


class SupporterSettingsUpdate(BaseModel):
    show_badge: Optional[bool] = None
    accent: Optional[str] = Field(None, max_length=16)


@router.get("/api/supporter")
def supporter_status(response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    supporters.link_pending_by_email(db, user)
    return supporters.status_payload(db, user)


@router.put("/api/supporter")
def update_supporter(
    payload: SupporterSettingsUpdate,
    response: Response,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _no_store(response)
    try:
        supporters.save_settings(db, user, payload.model_dump(exclude_unset=True))
    except PermissionError as error:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error))
    return supporters.status_payload(db, user)


# ---------------------------------------------------------------- site owner

def _require_admin(user: models.User) -> None:
    if not is_site_admin(user):
        raise HTTPException(status_code=403, detail="Only the site owner can manage Ko-fi payments")


class LinkPayment(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=80)
    username: str = Field(..., min_length=1, max_length=80)


@router.get("/api/supporters/unmatched")
def unmatched(response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ko-fi payments that could not be tied to a member automatically."""
    _no_store(response)
    _require_admin(user)
    return {"payments": supporters.unmatched_payments(db)}


@router.post("/api/supporters/link")
def link(payload: LinkPayment, response: Response, user: models.User = Depends(get_current_user),
         db: Session = Depends(get_db)):
    _no_store(response)
    _require_admin(user)
    member = db.query(models.User).filter(models.User.username == payload.username).first()
    if member is None:
        raise HTTPException(status_code=404, detail="No member with that username")
    try:
        supporters.link_payment(db, payload.message_id, member)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    return {"linked": True, "username": member.username, "profile": public_profiles.profile_path(member)}
