"""Ko-fi supporter tier: the Ko-fi webhook, the member's supporter settings, and admin linking."""
from __future__ import annotations

from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models, public_profiles, supporters
from ..admin_access import is_site_admin
from ..dependencies import get_current_user, get_db

router = APIRouter(tags=["supporters"])


def _e(value) -> str:
    return escape(str(value), quote=True)


# ---------------------------------------------------------------- /supporters page sections

def _money(value: float) -> str:
    return f"${value:,.0f}" if float(value).is_integer() else f"${value:,.2f}"


def _goal_html(db: Session) -> str:
    progress = supporters.goal_progress(db)
    if progress is None:
        return ""
    percent = progress["percent"]
    return (
        '<section class="support-goal" aria-labelledby="goal-heading">'
        f'<div class="support-goal__head"><h2 id="goal-heading">{_e(progress["month"])}\'s hosting</h2>'
        f'<p><strong>{percent}%</strong> of {_e(_money(progress["goal"]))} covered</p></div>'
        f'<div class="support-goal__bar" role="progressbar" aria-label="Hosting covered this month" aria-valuemin="0" '
        f'aria-valuemax="100" aria-valuenow="{percent}"><span class="support-goal__fill support-goal__fill--{percent // 5 * 5}"></span></div>'
        '<p class="support-goal__note">Servers, the database, email and title data. Anything past the goal goes into new features.</p>'
        '</section>'
    )


# What each Ko-fi tier adds, on top of every supporter perk. Lower tiers' extras carry up.
TIER_EXTRAS = {
    "popcorn": ("A Popcorn member tag beside your badge", "Three member banners: neon, marquee and comic"),
    "season_pass": ("Everything in Popcorn", "Moving banners: a slow sheen across yours, and the marquee bulbs chase"),
    "directors_cut": ("Everything in Season Pass", "Gold for your profile from the first month",
                      "Your name in the Director's Cut credits at the top of the wall"),
}


def _tiers_html() -> str:
    url = supporters.tiers_url()
    cards = []
    for tier in supporters.TIERS:
        extras = "".join(f"<li>{_e(line)}</li>" for line in TIER_EXTRAS.get(tier["slug"], ()))
        cards.append(
            f'<article class="support-tier support-tier--{_e(tier["slug"])}">'
            f'<p class="support-tier__price"><strong>{_e(_money(tier["price"]))}</strong> a month</p>'
            f'<h3>{_e(tier["name"])}</h3>'
            f'<ul>{extras}</ul>'
            f'<a class="site-btn site-btn--{"primary" if tier["rank"] == 2 else "ghost"}" data-kofi href="{_e(url)}" '
            f'target="_blank" rel="noopener noreferrer">Join {_e(tier["name"])} ↗</a>'
            '</article>')
    return f'<div class="support-tiers">{"".join(cards)}</div>'


def _wall_entry(entry: dict) -> str:
    classes = ["support-wall__name"]
    if entry["accent"]:
        classes.append(f"support-wall__name--{entry['accent']}")
    if not entry["active"]:
        classes.append("support-wall__name--past")
    mark = "★" if entry["founding"] else "♥"
    since = entry["since"]
    title = ("Founding supporter" if entry["founding"] else "Supporter") + (f" since {since:%B} {since.year}" if since else "")
    if entry.get("tier"):
        title += f' · {entry["tier"]} member'
    if not entry["active"]:
        title += " (past)"
    name = f'<span class="support-wall__mark" aria-hidden="true">{mark}</span>{_e(entry["name"])}'
    if entry["path"]:
        return f'<li><a class="{" ".join(classes)}" href="{_e(entry["path"])}" title="{_e(title)}">{name}</a></li>'
    return f'<li><span class="{" ".join(classes)}" title="{_e(title)}">{name}</span></li>'


def _wall_html(db: Session) -> str:
    entries = supporters.wall(db)
    if not entries:
        return ('<p class="support-wall__empty">No names here yet. Supporters can add theirs from '
                '<a href="/#supporter">Account → Supporter</a>, and the first few will be founding supporters.</p>')
    credits = [entry for entry in entries if entry.get("credits")]
    rest = [entry for entry in entries if not entry.get("credits")]
    html = ""
    if credits:
        names = "".join(_wall_entry(entry) for entry in credits)
        html += ('<div class="support-credits"><p class="support-credits__title">Director\'s Cut</p>'
                 f'<ul class="support-wall__list support-credits__list">{names}</ul></div>')
    if rest:
        html += f'<ul class="support-wall__list">{"".join(_wall_entry(entry) for entry in rest)}</ul>'
    return html


def _count_html(db: Session) -> str:
    count = supporters.active_count(db)
    if count < 3:  # a tiny number reads as a ghost town; the wall says thanks instead
        return ""
    return f'<p class="support-hero__count"><strong>{count}</strong> members support OmniTrackr right now.</p>'


def page_sections(db: Session) -> dict:
    """Live parts of /supporters: the hosting goal, the supporter count, the membership tiers and the wall. All text is escaped."""
    return {"<!--SUPPORTERS_GOAL-->": _goal_html(db), "<!--SUPPORTERS_COUNT-->": _count_html(db),
            "<!--SUPPORTERS_TIERS-->": _tiers_html(), "<!--SUPPORTERS_WALL-->": _wall_html(db)}


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
    on_wall: Optional[bool] = None
    accent: Optional[str] = Field(None, max_length=16)
    banner: Optional[str] = Field(None, max_length=24)
    banner_motion: Optional[bool] = None


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
