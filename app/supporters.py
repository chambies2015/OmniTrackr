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

Perks are cosmetic only (badge, profile accent). ``is_ad_free`` is the hook for
an ad-free experience once ads run for signed-in members.
"""
from __future__ import annotations

import hashlib
import hmac
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
ACCENTS = ("violet", "teal", "amber", "rose", "sky")
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


def is_ad_free(db: Session, user) -> bool:
    """Whether this member should see no ads. Supporters get it while their perks are active."""
    return user is not None and is_active(get_supporter(db, user.id))


def public_badge(db: Session, user_id: int) -> Optional[dict]:
    """What a public page may show about this member's support, or None."""
    supporter = get_supporter(db, user_id)
    if not is_active(supporter) or not supporter.show_badge:
        return None
    return {"since": supporter.since, "accent": supporter.accent if supporter.accent in ACCENTS else None}


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
    supporter.monthly = bool(payment.monthly)
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


def status_payload(db: Session, user) -> dict:
    supporter = get_supporter(db, user.id)
    active = is_active(supporter)
    return {
        "active": active,
        "since": supporter.since.isoformat() if supporter and supporter.since else None,
        "active_until": supporter.active_until.isoformat() if supporter and supporter.active_until else None,
        "monthly": bool(supporter and supporter.monthly),
        "show_badge": supporter.show_badge if supporter else True,
        "accent": (supporter.accent if supporter and supporter.accent in ACCENTS else None),
        "accents": list(ACCENTS),
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
    if "accent" in changes:
        accent = changes["accent"] or None
        if accent is not None and accent not in ACCENTS:
            raise ValueError("Pick one of the listed accent colors.")
        if accent is not None and not is_active(supporter):
            raise PermissionError("Accent colors are a perk for current supporters.")
        supporter.accent = accent
    db.commit()
    db.refresh(supporter)
    return supporter


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
        message_id=message_id, kind=kind, monthly=monthly,
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
             "monthly": p.monthly, "from_name": p.from_name, "received_at": p.received_at.isoformat()}
            for p in rows]
