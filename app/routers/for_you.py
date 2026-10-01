"""Starter picks, "Coming up for you", and the opt-in weekly email."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import digest, for_you, models
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..site_chrome import message_page

router = APIRouter(tags=["for-you"])


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _client(request: Request):
    return getattr(request.app.state, "external_api_client", None)


@router.get("/api/for-you/starter-picks")
async def get_starter_picks(request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    return for_you.starter_picks(db, user.id, client=_client(request))


class StarterAdd(BaseModel):
    category: Literal["movies", "tv-shows", "anime", "video-games", "music", "books"]
    title: str = Field(min_length=1, max_length=200)


@router.post("/api/for-you/starter-picks/add")
def add_starter_pick(selection: StarterAdd, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Copy a popular title's public details (never ratings or notes) into the member's library."""
    _private(response)
    model = for_you.LIBRARY[selection.category][0]
    normalized = func.lower(func.trim(model.title))
    title_key = selection.title.strip().lower()
    existing = db.query(model).filter(model.user_id == user.id, normalized == title_key).first()
    if existing:
        return {"state": "existing", "category": selection.category, "item_id": existing.id, "title": existing.title}
    payload = for_you.popular_entry_payload(db, selection.category, selection.title)
    if payload is None:
        raise HTTPException(404, "That pick is no longer available. Reload the suggestions and try again.")
    # Only public details are copied; everything the member adds later is their own.
    record = model(user_id=user.id, **payload)
    for flag in ("watched", "played", "listened", "read"):
        if hasattr(model, flag):
            setattr(record, flag, False)
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"state": "created", "category": selection.category, "item_id": record.id, "title": record.title}


@router.get("/api/for-you/coming-up")
async def get_coming_up(request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    report = for_you.coming_up(db, user.id, client=_client(request))
    report["email"] = _email_state(db, user.id)
    return report


def _email_state(db: Session, user_id: int) -> dict:
    subscription = digest.subscription_for(db, user_id)
    return {
        "enabled": subscription is not None,
        "available": digest.mail_configured(),
        "last_sent_at": subscription.last_sent_at.isoformat() + "Z" if subscription and subscription.last_sent_at else None,
    }


class EmailPreference(BaseModel):
    enabled: bool


@router.get("/api/for-you/email")
def get_email_preference(response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    return _email_state(db, user.id)


@router.put("/api/for-you/email")
def set_email_preference(preference: EmailPreference, response: Response,
                         user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    if preference.enabled:
        if not user.is_verified:
            raise HTTPException(400, "Verify your email address first, then turn on the weekly email.")
        digest.subscribe(db, user.id)
    else:
        digest.unsubscribe_user(db, user.id)
    return _email_state(db, user.id)


def _unsubscribe_page(title: str, heading: str, message: str, token: str = "", confirm: bool = False):
    page = message_page(title, heading, message, eyebrow="Weekly email",
                        actions=(("Go to OmniTrackr", "/"), ("Open Release Radar", "/release-radar")))
    if confirm:
        # A real button, so link scanners in mail apps can't unsubscribe anyone by prefetching.
        form = (f'<form method="post" action="/email/unsubscribe?token={token}" class="site-message__actions">'
                '<button class="site-btn site-btn--primary" type="submit">Unsubscribe</button></form>')
        page = page.replace('<div class="site-message__actions">', form + '<div class="site-message__actions">', 1)
    response = strict_html_response(page)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@router.get("/email/unsubscribe", include_in_schema=False)
def unsubscribe_confirm(token: str = Query("", max_length=64), db: Session = Depends(get_db)):
    safe = "".join(ch for ch in token if ch.isalnum() or ch in "-_")
    if not safe or not db.query(models.EmailDigestSubscription).filter_by(token=safe).first():
        return _unsubscribe_page("Unsubscribed", "You're not subscribed",
                                 "This link is no longer active, so no weekly email will be sent to you. "
                                 "You can turn it on again any time from your library.")
    return _unsubscribe_page("Unsubscribe", "Stop the weekly email?",
                             "Press the button to stop the weekly \"Coming up for you\" email. Nothing else about your account changes.",
                             token=safe, confirm=True)


@router.post("/email/unsubscribe", include_in_schema=False)
def unsubscribe(token: str = Query("", max_length=64), db: Session = Depends(get_db)):
    digest.unsubscribe_token(db, token)
    return _unsubscribe_page("Unsubscribed", "You're unsubscribed",
                             "You won't get the weekly email any more. You can turn it back on from your library whenever you like.")
