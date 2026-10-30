"""Ko-fi supporter tier: the Ko-fi webhook, the member's supporter settings, and admin linking."""
from __future__ import annotations

from html import escape
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import email as email_utils, models, public_profiles, supporters
from ..admin_access import is_site_admin
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..site_chrome import message_page

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
    username: str = Field(..., min_length=1, max_length=254)


class SetAsidePayment(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=80)
    set_aside: bool = True


def _member_json(member: models.User) -> dict:
    return {"username": member.username, "verified": bool(member.is_verified)}


@router.get("/api/supporters/unmatched")
def unmatched(response: Response, email: str = Query("", max_length=254), user: models.User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    """Ko-fi payments that could not be tied to a member automatically. ``email`` narrows them to one payer."""
    _no_store(response)
    _require_admin(user)
    email = email.strip()
    if email and not supporters.looks_like_email(email):
        raise HTTPException(status_code=422, detail="Type a whole email address, like name@example.com")
    result = {"payments": supporters.unmatched_payments(db, email=email or None), "waiting": supporters.waiting_count(db),
              "tests": supporters.test_count(db)}
    if email:
        result["members"] = [_member_json(member) for member in supporters.members_with_email(db, email)]
    return result


def _find_member(db: Session, who: str) -> Optional[models.User]:
    """A member by username (an @ in front is fine) or by email."""
    who = who.strip()
    if supporters.looks_like_email(who):
        exact = db.query(models.User).filter(func.lower(models.User.email) == who.lower()).limit(2).all()
        if len(exact) == 1:
            return exact[0]
        same_inbox = supporters.members_with_email(db, who)
        return same_inbox[0] if len(same_inbox) == 1 else None
    return db.query(models.User).filter(models.User.username == who.lstrip("@")).first()


@router.post("/api/supporters/link")
def link(payload: LinkPayment, response: Response, user: models.User = Depends(get_current_user),
         db: Session = Depends(get_db)):
    _no_store(response)
    _require_admin(user)
    member = _find_member(db, payload.username)
    if member is None:
        raise HTTPException(status_code=404, detail="No member with that username or email")
    try:
        supporters.link_payment(db, payload.message_id, member)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    return {"linked": True, "username": member.username, "profile": public_profiles.profile_path(member)}


@router.post("/api/supporters/set-aside")
def set_aside(payload: SetAsidePayment, response: Response, user: models.User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    """Take a payment off the "to link" list (a refund or a duplicate), or put it back."""
    _no_store(response)
    _require_admin(user)
    try:
        supporters.set_aside(db, payload.message_id, payload.set_aside)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    return {"set_aside": payload.set_aside}


# ---------------------------------------------------------------- "I donated but don't see my badge"

class ClaimPayment(BaseModel):
    value: str = Field(..., min_length=3, max_length=254)


CLAIM_EMAIL_SENT = ("If a Ko-fi payment from that address is waiting, we've emailed it a link. Open it to switch your "
                    "perks on. Nothing after a few minutes? Check spam, or try the transaction ID from your Ko-fi receipt.")


async def _send_claim(email: str, username: str, token: str) -> None:
    try:
        await email_utils.send_kofi_claim_email(email, username, f"{email_utils.APP_URL}/supporter/claim?token={token}")
    except Exception as error:  # the member sees the same reply either way
        print(f"Failed to send Ko-fi claim email: {error}")


@router.post("/api/supporter/claim")
def claim(payload: ClaimPayment, request: Request, background: BackgroundTasks, response: Response,
          user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Find a Ko-fi payment that didn't link: by the Ko-fi email (confirmed by email) or by transaction ID."""
    _no_store(response)
    value = payload.value.strip()
    if supporters.looks_like_email(value):
        result = supporters.claim_by_email(db, user, value)
        if "linked" in result:
            if result["linked"]:
                return {"status": "linked", "message": "Found it. Your supporter perks are on. Thank you!",
                        "supporter": supporters.status_payload(db, user)}
            return {"status": "none", "message": "Nothing from your OmniTrackr email is waiting. If you used another "
                    "email on Ko-fi, type that one, or the transaction ID from your Ko-fi receipt."}
        if result["send"]:
            background.add_task(_send_claim, value, user.username, supporters.claim_token(user.id, value))
        return {"status": "email_sent", "message": CLAIM_EMAIL_SENT}
    if not supporters.claim_by_transaction(db, user, value):
        raise HTTPException(status_code=404, detail="We couldn't find a waiting payment with that transaction ID. "
                            "Ko-fi can take a minute to tell us about a new payment, and payments from before Oct 30 "
                            "can only be found by email.")
    return {"status": "claimed", "message": "Found it. The site owner confirms transaction-ID claims by hand, "
            "usually within a day, and your perks switch on then."}


def _claim_page(heading: str, message: str, token: str = "", confirm: bool = False):
    # On the confirm step the button below is the only call to action.
    actions = () if confirm else (("Open my supporter settings", "/#supporter"), ("See supporter perks", "/supporters"))
    page = message_page("Ko-fi support", heading, message, eyebrow="Ko-fi support", actions=actions)
    if confirm:
        # A button, so a mail app scanning the link can't confirm on someone's behalf.
        form = (f'<form method="post" action="/supporter/claim?token={escape(token, quote=True)}" class="site-message__actions">'
                '<button class="site-btn site-btn--primary" type="submit">Yes, link my Ko-fi payment</button></form>')
        page = page.replace('<div class="site-message__actions">', form + '<div class="site-message__actions">', 1)
    response = strict_html_response(page)
    _no_store(response)
    return response


EXPIRED = ("This link has expired", "Links work for 3 days. Ask for a new one from Account → Supporter → "
           "\u201cI donated but don't see my badge\u201d.")


@router.get("/supporter/claim", include_in_schema=False)
def claim_confirm_page(token: str = Query("", max_length=400), db: Session = Depends(get_db)):
    data = supporters.read_claim_token(token)
    member = db.get(models.User, data["u"]) if data else None
    if member is None or not member.is_active:
        return _claim_page(*EXPIRED)
    return _claim_page("Link this Ko-fi payment?",
                       f"Your Ko-fi payment will be linked to the OmniTrackr account @{member.username}, and its "
                       "supporter perks switch on right away.", token=token, confirm=True)


@router.post("/supporter/claim", include_in_schema=False)
def claim_confirm(token: str = Query("", max_length=400), db: Session = Depends(get_db)):
    result = supporters.confirm_claim(db, token)
    if result is None:
        return _claim_page(*EXPIRED)
    member, linked = result
    if not linked:
        return _claim_page("Already linked", f"There's nothing left to link for this email. If @{member.username} "
                           "still doesn't show the supporter badge, write to us from the Contact page.")
    return _claim_page("Thank you!", f"Your Ko-fi support is linked to @{member.username} and the supporter perks are on. "
                       "Pick a profile accent and banner in Account → Supporter.")
