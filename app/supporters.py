"""Ko-fi supporters: webhook handling, linking payments to members, and perks.

Ko-fi calls the webhook once per payment. Each payment is recorded once (by its
``message_id``, so retries are harmless) and, when it can be tied to a member,
extends that member's supporter perks:

* a monthly Ko-fi membership payment adds ``MONTHLY_DAYS`` days,
* a one-time donation adds ``DONATION_DAYS`` days.

A payment is tied to a member by the supporter code from Account → Supporter
written in the Ko-fi message (``OT-<id>-<check>``), or by the payer's Ko-fi email
matching a verified OmniTrackr email (ignoring case, Gmail dots and "+tags").
Payments that match nobody wait, keyed by hashes of the payer's email and of
Ko-fi's transaction id, and are linked:

* when a member with that email verifies it or opens their supporter settings,
* when a member proves the Ko-fi email is theirs from a confirmation email
  ("I donated but don't see my badge" in Account → Supporter),
* when the site owner links it from Site stats, in one click when a member's
  email or a transaction-id claim points at it.

Perks for a payment linked late count from the day it's linked, so nobody loses
days to the wait, while the supporter date (and founding status) goes back to the
payment. Ko-fi's "Send a test" pings are recorded but never linked or counted.

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

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func, or_
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
# Hyphens, spaces or dashes between the parts: people retype the code as often as they paste it.
CODE_RE = re.compile(r"\bOT[\s\-\u2010-\u2015_]*(\d{1,10})[\s\-\u2010-\u2015_]+([0-9a-f]{6})\b", re.IGNORECASE)
# Ko-fi's "Send a test" button posts this sample payment.
TEST_TRANSACTION_ID = "00000000-1111-2222-3333-444444444444"
TEST_NAMES = {"ko-fi team"}
EXAMPLE_DOMAINS = {"example.com", "example.org", "example.net"}
GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}
CLAIM_MAX_AGE = 3 * 24 * 3600
LATE_LINK = timedelta(hours=12)


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


def canonical_email(email: Optional[str]) -> Optional[str]:
    """The address mail actually reaches: lower case, no "+tag", and for Gmail no dots."""
    email = (email or "").strip().lower()
    local, at, domain = email.rpartition("@")
    if not at or not local or not domain:
        return None
    local = local.split("+", 1)[0]
    if domain in GMAIL_DOMAINS:
        local, domain = local.replace(".", ""), "gmail.com"
    return f"{local}@{domain}" if local else None


def email_key(email: Optional[str]) -> Optional[str]:
    canonical = canonical_email(email)
    if not canonical:
        return None
    return hmac.new(SECRET_KEY.encode(), f"kofi-email-key:{canonical}".encode(), hashlib.sha256).hexdigest()


def transaction_hash(transaction_id: Optional[str]) -> Optional[str]:
    value = (transaction_id or "").strip().lower()
    if not value or len(value) > 120:
        return None
    return hmac.new(SECRET_KEY.encode(), f"kofi-tx:{value}".encode(), hashlib.sha256).hexdigest()


def _email_matches(payment: models.KofiPayment, email: Optional[str]) -> bool:
    exact, key = email_hash(email), email_key(email)
    return bool((exact and payment.email_hash == exact) or (key and payment.email_key == key))


def is_test_payload(data: dict) -> bool:
    """Ko-fi's "Send a test" ping: its sample transaction id, or the sample sender at an example.com address."""
    txid = data.get("kofi_transaction_id")
    if isinstance(txid, str) and txid.strip() == TEST_TRANSACTION_ID:
        return True
    email = data.get("email") if isinstance(data.get("email"), str) else ""
    name = data.get("from_name") if isinstance(data.get("from_name"), str) else ""
    return email.strip().lower().rpartition("@")[2] in EXAMPLE_DOMAINS and name.strip().lower() in TEST_NAMES


def looks_like_test(payment: models.KofiPayment) -> bool:
    """For the owner's list: flagged on arrival, or an older row from Ko-fi's sample sender."""
    return bool(payment.test or (payment.from_name or "").strip().lower() in TEST_NAMES)


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
    # A payment linked late (unmatched email, claimed later) still gets its full days, counted from
    # now, while the supporter date goes back to when they paid.
    now = _now()
    start_at = now if now - paid_at > LATE_LINK else paid_at
    days = MONTHLY_DAYS if payment.monthly else DONATION_DAYS
    if supporter is None:
        supporter = models.Supporter(user_id=user_id, since=paid_at, active_until=start_at, show_badge=True)
        db.add(supporter)
    start = max(supporter.active_until or start_at, start_at)
    supporter.active_until = start + timedelta(days=days)
    supporter.since = min(supporter.since or paid_at, paid_at)
    if payment.monthly:
        supporter.member_until = max(supporter.member_until or start_at, start_at) + timedelta(days=MONTHLY_DAYS)
        supporter.tier = resolve_tier(payment.tier_name, payment.amount)
    # A one-time tip from a current member leaves the membership as it is.
    supporter.monthly = bool(supporter.member_until and supporter.member_until > start_at)
    return supporter


def _link(db: Session, payment: models.KofiPayment, user_id: int) -> None:
    payment.user_id = user_id
    payment.linked_at = _now()
    if payment.kind in PERK_TYPES:
        _grant(db, user_id, payment)


def _waiting():
    """Payments still waiting for a member: not linked, not a Ko-fi test, not set aside by the owner."""
    return (models.KofiPayment.user_id.is_(None), models.KofiPayment.test.is_(False),
            models.KofiPayment.dismissed_at.is_(None))


def _waiting_for_email(db: Session, email: Optional[str]) -> list[models.KofiPayment]:
    exact, key = email_hash(email), email_key(email)
    matches = [models.KofiPayment.email_hash == exact] if exact else []
    if key:
        matches.append(models.KofiPayment.email_key == key)
    if not matches:
        return []
    return (db.query(models.KofiPayment).filter(*_waiting(), or_(*matches))
            .order_by(models.KofiPayment.received_at, models.KofiPayment.id).all())


def _thank(db: Session, user_id: int, linked: int) -> None:
    """An in-app note when payments are linked after the fact, so the member knows where the perks came from."""
    if not linked:
        return
    from .crud.friends import create_notification  # avoids a circular import

    what = "Your Ko-fi support is" if linked == 1 else f"Your {linked} Ko-fi payments are"
    create_notification(db, user_id, "supporter_linked",
                        f"{what} now linked to your account. Thank you! Your supporter perks are on.",
                        link="/#supporter")


def link_pending_by_email(db: Session, user, notify: bool = False) -> int:
    """Link waiting payments made with this member's (verified) email. Returns how many."""
    if user is None or not user.is_verified:
        return 0
    pending = _waiting_for_email(db, user.email)
    for payment in pending:
        _link(db, payment, user.id)
    if pending:
        db.commit()
        if notify:
            _thank(db, user.id, len(pending))
    return len(pending)


def link_after_verification(db: Session, user) -> None:
    """Hook for email verification and Google sign-in. Never lets a Ko-fi hiccup break signing in."""
    try:
        link_pending_by_email(db, user, notify=True)
    except Exception as error:  # pragma: no cover - defensive
        db.rollback()
        print(f"Ko-fi linking after verification failed: {error}")


def link_payment(db: Session, message_id: str, user) -> models.KofiPayment:
    """Admin fix-up: tie an unmatched payment to a member."""
    payment = db.query(models.KofiPayment).filter(models.KofiPayment.message_id == message_id).first()
    if payment is None:
        raise LookupError("Payment not found")
    if payment.user_id is not None:
        raise ValueError("That payment is already linked")
    _link(db, payment, user.id)
    db.commit()
    _thank(db, user.id, 1)
    return payment


def set_aside(db: Session, message_id: str, dismissed: bool) -> models.KofiPayment:
    """Admin: take a waiting payment off the "to link" list (a refund, a duplicate), or put it back."""
    payment = db.query(models.KofiPayment).filter(models.KofiPayment.message_id == message_id).first()
    if payment is None:
        raise LookupError("Payment not found")
    if payment.user_id is not None:
        raise ValueError("That payment is already linked")
    payment.dismissed_at = _now() if dismissed else None
    db.commit()
    return payment


# ---------------------------------------------------------------- member claims

def looks_like_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value or ""))


def claim_token(user_id: int, email: str) -> str:
    """A signed link for the confirmation email. It carries hashes only, never the address."""
    return _claim_serializer().dumps({"u": user_id, "h": email_hash(email), "k": email_key(email)})


def read_claim_token(token: str) -> Optional[dict]:
    try:
        data = _claim_serializer().loads(token or "", max_age=CLAIM_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("u"), int):
        return None
    return data


def _claim_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(SECRET_KEY, salt="kofi-claim")


def claim_by_email(db: Session, user, email: str) -> dict:
    """Step one of a claim by Ko-fi email. Returns {"linked": n} or {"send": bool}.

    The member's own verified address links at once. Any other address gets a
    confirmation email only when a payment from it is waiting; the reply to the
    member reads the same either way, so nobody can check who has donated.
    """
    if canonical_email(email) and canonical_email(email) == canonical_email(user.email) and user.is_verified:
        return {"linked": link_pending_by_email(db, user, notify=False)}
    return {"send": bool(_waiting_for_email(db, email))}


def confirm_claim(db: Session, token: str) -> Optional[tuple]:
    """Step two: the link in the confirmation email was opened. Returns (member, linked count) or None."""
    data = read_claim_token(token)
    if data is None:
        return None
    user = db.get(models.User, data["u"])
    if user is None or not user.is_active:
        return None
    matches = []
    if data.get("h"):
        matches.append(models.KofiPayment.email_hash == data["h"])
    if data.get("k"):
        matches.append(models.KofiPayment.email_key == data["k"])
    if not matches:
        return None
    pending = (db.query(models.KofiPayment).filter(*_waiting(), or_(*matches))
               .order_by(models.KofiPayment.received_at, models.KofiPayment.id).all())
    for payment in pending:
        _link(db, payment, user.id)
    if pending:
        db.commit()
        _thank(db, user.id, len(pending))
    return user, len(pending)


def claim_by_transaction(db: Session, user, transaction_id: str) -> bool:
    """A member says a payment is theirs by its Ko-fi transaction id. The owner confirms it in Site stats.

    The id can show up on public Ko-fi pages, so it flags the payment rather than linking it.
    """
    key = transaction_hash(transaction_id)
    if not key:
        return False
    payment = (db.query(models.KofiPayment)
               .filter(*_waiting(), models.KofiPayment.transaction_hash == key).first())
    if payment is None:
        return False
    payment.claimed_by = user.id
    payment.claimed_at = _now()
    db.commit()
    return True


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
               .filter(models.KofiPayment.received_at >= start, models.KofiPayment.test.is_(False),
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
    email = data.get("email").strip() if isinstance(data.get("email"), str) else None
    txid = data.get("kofi_transaction_id")
    payment = models.KofiPayment(
        message_id=message_id, kind=kind, monthly=monthly, tier_name=_clip(data.get("tier_name"), 40) if monthly else None,
        amount=_clip(data.get("amount"), 16), currency=_clip(data.get("currency"), 8),
        email_hash=email_hash(email), email_key=email_key(email),
        transaction_hash=transaction_hash(txid if isinstance(txid, str) else None),
        test=is_test_payload(data), from_name=_clip(data.get("from_name"), 80), received_at=_now(),
    )
    db.add(payment)

    user = None if payment.test else _match(db, data, email)
    if user is not None:
        _link(db, payment, user.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # the same delivery arrived twice at once
        return {"status": "duplicate", "linked": False}
    return {"status": "recorded", "linked": user is not None}


def _match(db: Session, data: dict, email: Optional[str]):
    """The member a new payment belongs to: a supporter code anywhere the payer could type it, else one verified email."""
    for field in ("message", "from_name"):
        code_id = user_id_from_text(data.get(field) if isinstance(data.get(field), str) else None)
        user = db.get(models.User, code_id) if code_id is not None else None
        if user is not None:
            return user
    if not email:
        return None
    candidates = (db.query(models.User)
                  .filter(models.User.is_verified == True, func.lower(models.User.email) == email.lower())
                  .limit(2).all())
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        return None
    candidates = members_with_email(db, email, verified_only=True)
    return candidates[0] if len(candidates) == 1 else None


def members_with_email(db: Session, email: str, verified_only: bool = False, limit: int = 5) -> list:
    """Active members whose email reaches the same inbox (case, Gmail dots and "+tags" aside)."""
    canonical = canonical_email(email)
    if not canonical:
        return []
    domain = canonical.rpartition("@")[2]
    domains = GMAIL_DOMAINS if domain == "gmail.com" else {domain}
    query = db.query(models.User).filter(models.User.is_active == True,
                                         or_(*[func.lower(models.User.email).like(f"%@{d}") for d in domains]))
    if verified_only:
        query = query.filter(models.User.is_verified == True)
    found = [user for user in query.order_by(models.User.id).all() if canonical_email(user.email) == canonical]
    return found[:limit]


def _suggestions(db: Session, payments: list) -> dict:
    """For the owner's list: members who could be each payer, by email (verified or not) or by name. Keyed by payment id."""
    if not payments:
        return {}
    exact = {p.email_hash for p in payments if p.email_hash}
    keys = {p.email_key for p in payments if p.email_key}
    names = {(p.from_name or "").strip().lower() for p in payments if p.from_name}
    claimers = {p.claimed_by for p in payments if p.claimed_by}
    by_hash, by_key, by_name, by_id = {}, {}, {}, {}
    rows = db.query(models.User.id, models.User.username, models.User.email, models.User.is_verified).filter(
        models.User.is_active == True).all()
    for row in rows:
        member = {"username": row.username, "verified": bool(row.is_verified)}
        if row.id in claimers:
            by_id[row.id] = member
        if exact and email_hash(row.email) in exact:
            by_hash.setdefault(email_hash(row.email), []).append(member)
        if keys and email_key(row.email) in keys:
            by_key.setdefault(email_key(row.email), []).append(member)
        if row.username and row.username.lower() in names:
            by_name.setdefault(row.username.lower(), []).append(member)
    result = {}
    for payment in payments:
        seen, picks = set(), []
        candidates = [("claimed it with the transaction id", [by_id[payment.claimed_by]] if payment.claimed_by in by_id else []),
                      ("same email", by_hash.get(payment.email_hash, [])),
                      ("same inbox", by_key.get(payment.email_key, [])),
                      ("same name", by_name.get((payment.from_name or "").strip().lower(), []))]
        for reason, members in candidates:
            for member in members:
                if member["username"] not in seen:
                    seen.add(member["username"])
                    picks.append({**member, "reason": reason if member["verified"] or reason.startswith("claimed")
                                  else f"{reason}, not verified"})
        result[payment.id] = picks[:3]
    return result


def unmatched_payments(db: Session, limit: int = 50, email: Optional[str] = None) -> list[dict]:
    """Waiting payments for the owner, newest first, with likely members. With an email, only that payer's."""
    query = db.query(models.KofiPayment).filter(*_waiting())
    if email:
        exact, key = email_hash(email), email_key(email)
        query = query.filter(or_(models.KofiPayment.email_hash == exact, models.KofiPayment.email_key == key))
    rows = query.order_by(models.KofiPayment.received_at.desc()).limit(limit).all()
    suggestions = _suggestions(db, rows)
    return [{"message_id": p.message_id, "kind": p.kind, "amount": p.amount, "currency": p.currency,
             "monthly": p.monthly, "tier_name": p.tier_name, "from_name": p.from_name, "received_at": p.received_at.isoformat(),
             "looks_like_test": looks_like_test(p), "claimed": p.claimed_by is not None,
             "suggestions": suggestions.get(p.id, [])}
            for p in rows]


def waiting_count(db: Session) -> int:
    """Payments the owner still needs to look at: not linked, not a test, not set aside."""
    return int(db.query(func.count(models.KofiPayment.id)).filter(*_waiting()).scalar() or 0)
