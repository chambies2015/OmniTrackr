"""Ko-fi supporters: webhook handling, linking payments to members, and perks.

Ko-fi calls the webhook once per payment. Each payment is recorded once (by its
``message_id``, so retries are harmless) and, when it can be tied to a member,
extends that member's supporter perks:

* a monthly Ko-fi membership payment adds ``MONTHLY_DAYS`` days,
* a one-time donation adds ``DONATION_DAYS`` days.

A payment is tied to a member by the supporter code from Account → Supporter
written in the Ko-fi message (``OT-<id>-<check>``), or by the payer's Ko-fi email
matching a verified OmniTrackr email. Payments that match nobody wait, keyed by a
hash of the payer's email, and are linked when a member with that email opens
their supporter settings, or by an admin by hand.

Perks are cosmetic only (badge, profile accent, a profile banner, six showcase
spots instead of three, a place on the supporter wall).

Monthly members (Oct 28) get a few extras on top, by Ko-fi tier: a tier tag on
the profile and three member banners for every tier, moving banners from
Season Pass up, and gold plus the "Director's Cut" credits on the supporter
wall at the top tier. Membership lasts ``MONTHLY_DAYS`` past each membership
payment (``member_until``), so a cancelled membership winds down on its own. A
member's tier comes from Ko-fi's ``tier_name``, or from the amount when the
name is one we don't know.
``is_ad_free`` is the hook for an ad-free experience once ads run for signed-in
members.

Supporter levels are counted, never stored: anyone whose support started
before ``FOUNDING_BEFORE`` is a founding supporter, and "months supported" is
the number of perk payments linked to the member. Founding supporters and
anyone past ``GOLD_MONTHS`` unlock the gold accent.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models
from .auth import SECRET_KEY

KOFI_URL = os.getenv("KOFI_URL", "https://ko-fi.com/omnitrackr")
MONTHLY_DAYS = 31
DONATION_DAYS = 30
# Ko-fi payment types that grant perks. Shop orders and commissions are recorded only.
PERK_TYPES = {"donation", "subscription"}
BASE_ACCENTS = ("violet", "teal", "amber", "rose", "sky", "emerald", "coral")
ACCENTS = BASE_ACCENTS + ("gold",)
# Banner art drawn in CSS across the top of the public profile, tinted by the accent.
BANNERS = ("aurora", "filmstrip", "pixels", "pages", "vinyl", "stars")
# Extra banners for monthly members of any tier.
MEMBER_BANNERS = ("neon", "marquee", "comic")
ALL_BANNERS = BANNERS + MEMBER_BANNERS
# Ko-fi membership tiers, lowest first. Keep names and prices in step with ko-fi.com/omnitrackr/tiers;
# a payment whose tier name isn't listed here is placed by its amount.
TIERS = (
    {"slug": "popcorn", "name": "Popcorn", "price": 3, "rank": 1},
    {"slug": "season_pass", "name": "Season Pass", "price": 5, "rank": 2},
    {"slug": "directors_cut", "name": "Director's Cut", "price": 10, "rank": 3},
)
TIERS_BY_SLUG = {tier["slug"]: tier for tier in TIERS}
MOTION_RANK = 2  # moving banners
CREDITS_RANK = 3  # gold right away and the credits on the wall
GOLD_MONTHS = 6
FOUNDING_BEFORE = datetime(2027, 1, 1)
WALL_LIMIT = 150
CODE_RE = re.compile(r"\bOT-(\d{1,10})-([0-9a-f]{6})\b", re.IGNORECASE)


class WebhookError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def verification_token() -> str:
    return (os.getenv("KOFI_VERIFICATION_TOKEN") or "").strip()


def _now() -> datetime:
    return datetime.utcnow()


def _check(user_id: int) -> str:
    return hmac.new(SECRET_KEY.encode(), f"kofi-code:{user_id}".encode(), hashlib.sha256).hexdigest()[:6]


def supporter_code(user_id: int) -> str:
    return f"OT-{user_id}-{_check(user_id)}"


def user_id_from_text(text: Optional[str]) -> Optional[int]:
    """The member id from a supporter code inside free text (a Ko-fi message), if valid."""
    for match in CODE_RE.finditer(text or ""):
        user_id = int(match.group(1))
        if hmac.compare_digest(match.group(2).lower(), _check(user_id)):
            return user_id
    return None


def email_hash(email: Optional[str]) -> Optional[str]:
    email = (email or "").strip().lower()
    if not email:
        return None
    return hmac.new(SECRET_KEY.encode(), f"kofi-email:{email}".encode(), hashlib.sha256).hexdigest()


def _clip(value, limit: int) -> Optional[str]:
    text = " ".join(str(value).split()) if value is not None else ""
    return text[:limit] or None


# ---------------------------------------------------------------- status

def get_supporter(db: Session, user_id: int) -> Optional[models.Supporter]:
    return db.query(models.Supporter).filter(models.Supporter.user_id == user_id).first()


def is_active(supporter: Optional[models.Supporter], now: Optional[datetime] = None) -> bool:
    return bool(supporter and supporter.active_until and supporter.active_until > (now or _now()))


def _tier_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def resolve_tier(tier_name: Optional[str], amount: Optional[str]) -> str:
    """The tier slug for a membership payment: by Ko-fi tier name, else by amount."""
    if tier_name:
        key = _tier_key(tier_name)
        for tier in TIERS:
            if key in (_tier_key(tier["name"]), _tier_key(tier["slug"])):
                return tier["slug"]
    paid = _amount(amount)
    best = TIERS[0]
    for tier in TIERS:
        if paid >= tier["price"]:
            best = tier
    return best["slug"]


def is_member(supporter: Optional[models.Supporter], now: Optional[datetime] = None) -> bool:
    """A monthly Ko-fi member right now (on top of being a supporter)."""
    return bool(is_active(supporter, now) and supporter.member_until and supporter.member_until > (now or _now()))


def member_tier(supporter: Optional[models.Supporter], now: Optional[datetime] = None) -> Optional[dict]:
    """The member's tier, or None. Memberships from before tiers were tracked count as the first tier."""
    if not is_member(supporter, now):
        return None
    return TIERS_BY_SLUG.get(supporter.tier or "", TIERS[0])


def member_rank(supporter: Optional[models.Supporter], now: Optional[datetime] = None) -> int:
    tier = member_tier(supporter, now)
    return tier["rank"] if tier else 0


def unlocked_banners(supporter: Optional[models.Supporter], now: Optional[datetime] = None) -> tuple:
    if not is_active(supporter, now):
        return ()
    return ALL_BANNERS if is_member(supporter, now) else BANNERS


def shown_banner(supporter: Optional[models.Supporter]) -> Optional[str]:
    """The saved banner, if the member can still use it. A lapsed membership hides a member banner but keeps the choice."""
    banner = supporter.banner if supporter else None
    return banner if banner in unlocked_banners(supporter) else None


def is_ad_free(db: Session, user) -> bool:
    """Whether this member should see no ads. Supporters get it while their perks are active."""
    return user is not None and is_active(get_supporter(db, user.id))


def is_founding(supporter: Optional[models.Supporter]) -> bool:
    return bool(supporter and supporter.since and supporter.since < FOUNDING_BEFORE)


def months_supported(db: Session, user_id: int) -> int:
    """How many perk payments (a month of membership or a one-time tip each) this member has made."""
    return int(db.query(func.count(models.KofiPayment.id))
               .filter(models.KofiPayment.user_id == user_id, models.KofiPayment.kind.in_(PERK_TYPES))
               .scalar() or 0)


def unlocked_accents(supporter: Optional[models.Supporter], months: int) -> tuple:
    if is_founding(supporter) or months >= GOLD_MONTHS or member_rank(supporter) >= CREDITS_RANK:
        return ACCENTS
    return BASE_ACCENTS


def level_label(founding: bool, months: int) -> str:
    """The badge text: "Founding supporter", or "Supporter" with the months once there are a few."""
    label = "Founding supporter" if founding else "Supporter"
    return f"{label} · {months} months" if months >= 2 else label


def public_badge(db: Session, user_id: int) -> Optional[dict]:
    """What a public page may show about this member's support, or None."""
    supporter = get_supporter(db, user_id)
    if not is_active(supporter) or not supporter.show_badge:
        return None
    tier = member_tier(supporter)
    banner = shown_banner(supporter)
    return {"since": supporter.since, "accent": supporter.accent if supporter.accent in ACCENTS else None,
            "banner": banner, "founding": is_founding(supporter), "months": months_supported(db, user_id),
            "tier": tier["name"] if tier else None,
            "motion": bool(banner and supporter.banner_motion and tier and tier["rank"] >= MOTION_RANK)}


def public_badges(db: Session, user_ids) -> dict:
    """Badges for many members at once (review lists), keyed by user id. Only shown badges are returned."""
    ids = {int(i) for i in user_ids if i}
    if not ids:
        return {}
    rows = (db.query(models.Supporter)
            .filter(models.Supporter.user_id.in_(ids), models.Supporter.active_until > _now(),
                    models.Supporter.show_badge.is_(True)).all())
    return {row.user_id: {"accent": row.accent if row.accent in ACCENTS else None,
                          "since": f"{row.since:%B} {row.since.year}" if row.since else None,
                          "founding": is_founding(row)} for row in rows}


def chip_html(badge: Optional[dict]) -> str:
    """The small ♥ Supporter chip shown beside a member's name on reviews."""
    if not badge:
        return ""
    since = badge.get("since")
    who = "Founding supporter of OmniTrackr" if badge.get("founding") else "Supporting OmniTrackr"
    title = f"{who} on Ko-fi since {since}" if since else "Supports OmniTrackr on Ko-fi"
    accent = badge.get("accent")
    accent_class = f" supporter-chip--{accent}" if accent in ACCENTS else ""
    return (f'<a class="supporter-chip{accent_class}" href="/supporters" title="{html.escape(title)}">'
            '<span aria-hidden="true">♥</span> Supporter</a>')


def _grant(db: Session, user_id: int, payment: models.KofiPayment) -> models.Supporter:
    supporter = get_supporter(db, user_id)
    paid_at = payment.received_at or _now()
    days = MONTHLY_DAYS if payment.monthly else DONATION_DAYS
    if supporter is None:
        supporter = models.Supporter(user_id=user_id, since=paid_at, active_until=paid_at, show_badge=True)
        db.add(supporter)
    start = max(supporter.active_until or paid_at, paid_at)
    supporter.active_until = start + timedelta(days=days)
    supporter.since = min(supporter.since or paid_at, paid_at)
    if payment.monthly:
        supporter.member_until = max(supporter.member_until or paid_at, paid_at) + timedelta(days=MONTHLY_DAYS)
        supporter.tier = resolve_tier(payment.tier_name, payment.amount)
    # A one-time tip from a current member leaves the membership as it is.
    supporter.monthly = bool(supporter.member_until and supporter.member_until > paid_at)
    return supporter


def _link(db: Session, payment: models.KofiPayment, user_id: int) -> None:
    payment.user_id = user_id
    payment.linked_at = _now()
    if payment.kind in PERK_TYPES:
        _grant(db, user_id, payment)


def link_pending_by_email(db: Session, user) -> int:
    """Link waiting payments made with this member's (verified) email. Returns how many."""
    if user is None or not user.is_verified:
        return 0
    key = email_hash(user.email)
    if not key:
        return 0
    pending = (db.query(models.KofiPayment)
               .filter(models.KofiPayment.user_id.is_(None), models.KofiPayment.email_hash == key)
               .order_by(models.KofiPayment.received_at, models.KofiPayment.id).all())
    for payment in pending:
        _link(db, payment, user.id)
    if pending:
        db.commit()
    return len(pending)


def link_payment(db: Session, message_id: str, user) -> models.KofiPayment:
    """Admin fix-up: tie an unmatched payment to a member."""
    payment = db.query(models.KofiPayment).filter(models.KofiPayment.message_id == message_id).first()
    if payment is None:
        raise LookupError("Payment not found")
    if payment.user_id is not None:
        raise ValueError("That payment is already linked")
    _link(db, payment, user.id)
    db.commit()
    return payment


def tiers_url() -> str:
    return f"{KOFI_URL.rstrip('/')}/tiers"


def status_payload(db: Session, user) -> dict:
    supporter = get_supporter(db, user.id)
    active = is_active(supporter)
    tier = member_tier(supporter)
    months = months_supported(db, user.id) if supporter else 0
    founding = is_founding(supporter)
    return {
        "active": active,
        "founding": founding,
        "months": months,
        "level": level_label(founding, months) if supporter else None,
        "on_wall": bool(supporter and supporter.on_wall),
        "unlocked_accents": list(unlocked_accents(supporter, months)) if active else [],
        "gold_months": GOLD_MONTHS,
        "since": supporter.since.isoformat() if supporter and supporter.since else None,
        "active_until": supporter.active_until.isoformat() if supporter and supporter.active_until else None,
        "monthly": bool(supporter and supporter.monthly),
        "show_badge": supporter.show_badge if supporter else True,
        "accent": (supporter.accent if supporter and supporter.accent in ACCENTS else None),
        "accents": list(ACCENTS),
        "banner": (supporter.banner if supporter and supporter.banner in ALL_BANNERS else None),
        "banners": list(BANNERS),
        "member_banners": list(MEMBER_BANNERS),
        "unlocked_banners": list(unlocked_banners(supporter)) if supporter else [],
        "member": tier is not None,
        "tier": tier["slug"] if tier else None,
        "tier_name": tier["name"] if tier else None,
        "member_until": supporter.member_until.isoformat() if tier and supporter.member_until else None,
        "banner_motion": bool(supporter and supporter.banner_motion),
        "can_animate": bool(tier and tier["rank"] >= MOTION_RANK),
        "tiers": [dict(item) for item in TIERS],
        "tiers_url": tiers_url(),
        "ad_free": active,
        "code": supporter_code(user.id),
        "kofi_url": KOFI_URL,
    }


def save_settings(db: Session, user, changes: dict) -> models.Supporter:
    supporter = get_supporter(db, user.id)
    if supporter is None:
        raise PermissionError("Supporter settings unlock after your first Ko-fi support.")
    if "show_badge" in changes and changes["show_badge"] is not None:
        supporter.show_badge = bool(changes["show_badge"])
    if "on_wall" in changes and changes["on_wall"] is not None:
        supporter.on_wall = bool(changes["on_wall"])
    if "accent" in changes:
        accent = changes["accent"] or None
        if accent is not None and accent not in ACCENTS:
            raise ValueError("Pick one of the listed accent colors.")
        if accent is not None and not is_active(supporter):
            raise PermissionError("Accent colors are a perk for current supporters.")
        if accent is not None and accent not in unlocked_accents(supporter, months_supported(db, user.id)):
            raise PermissionError(f"Gold unlocks for founding supporters and after {GOLD_MONTHS} months of support.")
        supporter.accent = accent
    if "banner" in changes:
        banner = changes["banner"] or None
        if banner is not None and banner not in ALL_BANNERS:
            raise ValueError("Pick one of the listed banners.")
        if banner is not None and not is_active(supporter):
            raise PermissionError("Profile banners are a perk for current supporters.")
        if banner in MEMBER_BANNERS and not is_member(supporter):
            raise PermissionError("Neon, marquee and comic come with a monthly Ko-fi membership.")
        supporter.banner = banner
    if "banner_motion" in changes and changes["banner_motion"] is not None:
        motion = bool(changes["banner_motion"])
        if motion and member_rank(supporter) < MOTION_RANK:
            raise PermissionError("Moving banners come with the Season Pass and Director's Cut memberships.")
        supporter.banner_motion = motion
    db.commit()
    db.refresh(supporter)
    return supporter


# ---------------------------------------------------------------- supporters page

def wall(db: Session, limit: int = WALL_LIMIT) -> list[dict]:
    """Members who chose to be thanked by name on /supporters: current supporters first, longest first."""
    from .public_profiles import enabled_profile_paths, profile_path  # avoids a circular import

    now = _now()
    rows = (db.query(models.Supporter, models.User)
            .join(models.User, models.User.id == models.Supporter.user_id)
            .filter(models.Supporter.on_wall.is_(True), models.User.is_active == True)
            .order_by(models.Supporter.since, models.Supporter.id).limit(limit).all())
    paths = enabled_profile_paths(db, [user.id for _, user in rows])
    entries = []
    for supporter, user in rows:
        active = is_active(supporter, now)
        tier = member_tier(supporter, now)
        entries.append({
            "name": user.username, "path": paths.get(user.id), "active": active,
            "founding": is_founding(supporter), "since": supporter.since,
            "accent": supporter.accent if active and supporter.accent in ACCENTS else None,
            "tier": tier["name"] if tier else None, "credits": bool(tier and tier["rank"] >= CREDITS_RANK),
        })
    entries.sort(key=lambda entry: not entry["active"])
    return entries


def monthly_goal() -> Optional[float]:
    """The monthly hosting goal in US dollars, from ``KOFI_MONTHLY_GOAL``. Unset hides the meter."""
    try:
        goal = float((os.getenv("KOFI_MONTHLY_GOAL") or "").strip().lstrip("$"))
    except ValueError:
        return None
    return goal if 0 < goal < 1_000_000 else None


def _amount(value: Optional[str]) -> float:
    try:
        amount = float((value or "").replace(",", ""))
    except ValueError:
        return 0.0
    return amount if 0 < amount < 100_000 else 0.0


def goal_progress(db: Session, now: Optional[datetime] = None) -> Optional[dict]:
    """This calendar month's Ko-fi payments (US dollars) against the goal, or None when no goal is set."""
    goal = monthly_goal()
    if goal is None:
        return None
    now = now or _now()
    start = datetime(now.year, now.month, 1)
    amounts = (db.query(models.KofiPayment.amount)
               .filter(models.KofiPayment.received_at >= start,
                       func.coalesce(func.upper(models.KofiPayment.currency), "USD") == "USD").all())
    raised = sum(_amount(amount) for (amount,) in amounts)
    return {"goal": goal, "raised": raised, "percent": min(100, int(raised * 100 / goal)), "month": f"{now:%B}"}


def active_count(db: Session) -> int:
    return int(db.query(func.count(models.Supporter.id)).filter(models.Supporter.active_until > _now()).scalar() or 0)


# ---------------------------------------------------------------- webhook

def parse_payload(raw: Optional[str]) -> dict:
    if not raw or len(raw) > 20000:
        raise WebhookError(400, "Missing data")
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        raise WebhookError(400, "Invalid data")
    if not isinstance(data, dict):
        raise WebhookError(400, "Invalid data")
    return data


def handle_webhook(db: Session, data: dict) -> dict:
    """Record one Ko-fi payment. Returns {"status": ..., "linked": bool}."""
    expected = verification_token()
    if not expected:
        raise WebhookError(503, "Ko-fi webhook is not configured")
    given = data.get("verification_token")
    if not isinstance(given, str) or not hmac.compare_digest(given.encode(), expected.encode()):
        raise WebhookError(403, "Invalid verification token")
    message_id = _clip(data.get("message_id") or data.get("kofi_transaction_id"), 80)
    if not message_id:
        raise WebhookError(400, "Missing message_id")
    if db.query(models.KofiPayment.id).filter(models.KofiPayment.message_id == message_id).first():
        return {"status": "duplicate", "linked": False}

    kind = (_clip(data.get("type"), 24) or "donation").lower()
    monthly = kind == "subscription" or data.get("is_subscription_payment") is True
    if monthly and kind == "donation":
        kind = "subscription"
    payment = models.KofiPayment(
        message_id=message_id, kind=kind, monthly=monthly, tier_name=_clip(data.get("tier_name"), 40) if monthly else None,
        amount=_clip(data.get("amount"), 16), currency=_clip(data.get("currency"), 8),
        email_hash=email_hash(data.get("email") if isinstance(data.get("email"), str) else None),
        from_name=_clip(data.get("from_name"), 80), received_at=_now(),
    )
    db.add(payment)

    user = None
    code_id = user_id_from_text(data.get("message") if isinstance(data.get("message"), str) else None)
    if code_id is not None:
        user = db.get(models.User, code_id)
    if user is None and payment.email_hash:
        email = data["email"].strip().lower()
        candidates = (db.query(models.User)
                      .filter(models.User.is_verified == True, func.lower(models.User.email) == email)
                      .limit(2).all())
        if len(candidates) == 1:
            user = candidates[0]
    if user is not None:
        _link(db, payment, user.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # the same delivery arrived twice at once
        return {"status": "duplicate", "linked": False}
    return {"status": "recorded", "linked": user is not None}


def unmatched_payments(db: Session, limit: int = 50) -> list[dict]:
    rows = (db.query(models.KofiPayment).filter(models.KofiPayment.user_id.is_(None))
            .order_by(models.KofiPayment.received_at.desc()).limit(limit).all())
    return [{"message_id": p.message_id, "kind": p.kind, "amount": p.amount, "currency": p.currency,
             "monthly": p.monthly, "tier_name": p.tier_name, "from_name": p.from_name, "received_at": p.received_at.isoformat()}
            for p in rows]
