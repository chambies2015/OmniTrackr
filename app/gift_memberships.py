"""Gift supporter memberships (Nov 23 2026): supporter perks bought on Ko-fi for somebody else.

Buying one: a one-time Ko-fi payment with OT-GIFT in its message. Each $3 coffee buys a month
of perks, up to a year. Signed-in members are shown OT-GIFT-<id>-<check> instead (their own
supporter code joined on), so the gift lands in their account even when they pay with another
email. The payment is recorded like any other and marked ``gift``: it never switches on the
payer's own perks and never sits on the owner's "to link" list.

The payer gets an email at their Ko-fi address with the gift's link, and a private link of their
own for writing the card, printing it and seeing whether it has been opened. A member who gave it
sees the same on /supporters/gift.

Whoever has the code opens the gift with an OmniTrackr account. The perks start that day, after
any perks they already have, and their supporter date (so founding status too) is the day the gift
was paid for. A gift opens once. Its code and the giver's link come from ``salt`` and the secret
key, so neither is stored; the table keeps only a keyed hash of the code for looking it up.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import models, supporters
from .auth import SECRET_KEY

MONTH_PRICE = 3  # a $3 coffee buys a month, the same as a one-time tip does for yourself
MAX_MONTHS = 12
CODE_LENGTH = 12
# No 0/O, 1/I/L or U, so a code read off a printed card can't be typed wrong in those ways.
ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"
_SEP = r"[\s\-‐-―_]"
MARKER_RE = re.compile(rf"\bOT{_SEP}*GIFT\b(?:{_SEP}*(\d{{1,10}}){_SEP}+([0-9a-f]{{6}})\b)?", re.IGNORECASE)
TO_LIMIT = 40
FROM_LIMIT = 40
NOTE_LIMIT = 280
OWNER_LIST_LIMIT = 60
_CONTROL = re.compile(r"[\x00-\x1f\x7f​-‏‪-‮⁦-⁩]")


class GiftError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _now() -> datetime:
    return datetime.utcnow()


def _mac(purpose: str) -> bytes:
    return hmac.new(SECRET_KEY.encode(), purpose.encode(), hashlib.sha256).digest()


# ---------------------------------------------------------------- buying

def marker_for(user_id: int) -> str:
    """What a member writes in the Ko-fi message so the gift is tied to their account."""
    return f"OT-GIFT-{user_id}-{supporters._check(user_id)}"


def find_marker(data: dict) -> Optional[dict]:
    """{"giver_id": int | None} when a payment asks to be a gift, else None.

    The id only counts when its check matches, like a supporter code. Looked for in the message and,
    like supporter codes, in the name (people paste codes into whichever box they see first).
    """
    for field in ("message", "from_name"):
        value = data.get(field)
        if not isinstance(value, str):
            continue
        found = None
        for match in MARKER_RE.finditer(value):
            found = found or {"giver_id": None}
            if match.group(1):
                user_id = int(match.group(1))
                if hmac.compare_digest(match.group(2).lower(), supporters._check(user_id)):
                    return {"giver_id": user_id}
        if found:
            return found
    return None


def months_for(amount: Optional[str]) -> int:
    """Months of perks a gift payment buys: one per $3 coffee, at least one and at most a year."""
    paid = supporters._amount(amount)
    return max(1, min(MAX_MONTHS, int((paid + 0.001) // MONTH_PRICE)))


def days_for(months: int) -> int:
    """30 days for a month, 91 for three, 183 for six and 365 for a year."""
    return round(months * 365.25 / 12)


def months_label(months: int) -> str:
    if months == MAX_MONTHS:
        return "a year"
    return "1 month" if months == 1 else f"{months} months"


# ---------------------------------------------------------------- codes and links

def _code(salt: str) -> str:
    number = int.from_bytes(_mac(f"gift-code:{salt}"), "big")
    chars = []
    for _ in range(CODE_LENGTH):
        number, index = divmod(number, len(ALPHABET))
        chars.append(ALPHABET[index])
    return "".join(chars)


def code_hash(code: str) -> str:
    return hmac.new(SECRET_KEY.encode(), f"gift-hash:{code}".encode(), hashlib.sha256).hexdigest()


def normalize(raw: Optional[str]) -> Optional[str]:
    """A typed or pasted code in its plain form, or None if it can't be one."""
    text = re.sub(r"[\s\-‐-―_.]", "", (raw or "")[:60]).upper()
    if len(text) != CODE_LENGTH or any(ch not in ALPHABET for ch in text):
        return None
    return text


def pretty(code: str) -> str:
    return "-".join(code[i:i + 4] for i in range(0, len(code), 4))


def code_of(gift: models.GiftMembership) -> str:
    return pretty(_code(gift.salt))


def path_of(gift: models.GiftMembership) -> str:
    return f"/gift/{code_of(gift)}"


def manage_token(gift: models.GiftMembership) -> str:
    check = hmac.new(SECRET_KEY.encode(), f"gift-manage:{gift.id}:{gift.salt}".encode(), hashlib.sha256).hexdigest()
    return f"{gift.id}-{check[:32]}"


def manage_path(gift: models.GiftMembership) -> str:
    return f"/supporters/gift/manage/{manage_token(gift)}"


def by_code(db: Session, raw: Optional[str]) -> Optional[models.GiftMembership]:
    code = normalize(raw)
    if code is None:
        return None
    return db.query(models.GiftMembership).filter(models.GiftMembership.code_hash == code_hash(code)).first()


def by_manage_token(db: Session, token: Optional[str]) -> Optional[models.GiftMembership]:
    match = re.fullmatch(r"([1-9]\d{0,9})-([0-9a-f]{32})", token or "")
    if not match or int(match.group(1)) > 2147483647:
        return None
    gift = db.get(models.GiftMembership, int(match.group(1)))
    if gift is None or not hmac.compare_digest(manage_token(gift), token):
        return None
    return gift


def create(db: Session, months: int, *, source: str = "kofi", payment: Optional[models.KofiPayment] = None,
           giver_id: Optional[int] = None, paid_at: Optional[datetime] = None) -> models.GiftMembership:
    """A new unopened gift. Flushed so it has an id (the giver's link needs it)."""
    months = max(1, min(MAX_MONTHS, int(months)))
    while True:
        salt = secrets.token_hex(16)
        digest = code_hash(_code(salt))
        if not db.query(models.GiftMembership.id).filter(models.GiftMembership.code_hash == digest).first():
            break
    gift = models.GiftMembership(salt=salt, code_hash=digest, months=months, source=source,
                                 payment_id=payment.id if payment is not None else None, giver_id=giver_id,
                                 paid_at=paid_at or _now(), created_at=_now(), opened=0)
    db.add(gift)
    db.flush()
    return gift


def from_webhook(db: Session, payment: models.KofiPayment, giver: Optional[models.User]) -> models.GiftMembership:
    """The gift a just-recorded Ko-fi payment bought (called inside the webhook's transaction)."""
    payment.gift = True
    db.flush()
    return create(db, months_for(payment.amount), payment=payment, giver_id=giver.id if giver else None,
                  paid_at=payment.received_at)


def state(gift: models.GiftMembership) -> str:
    if gift.redeemed_at is not None:
        return "opened"
    if gift.cancelled_at is not None:
        return "cancelled"
    return "open"


def ends_if_opened_now(db: Session, user: Optional[models.User], gift: models.GiftMembership,
                       now: Optional[datetime] = None) -> datetime:
    """When the perks would run until if this member opened the gift now."""
    now = now or _now()
    supporter = supporters.get_supporter(db, user.id) if user is not None else None
    start = max(supporter.active_until, now) if supporter is not None and supporter.active_until else now
    return start + timedelta(days=days_for(gift.months))


# ---------------------------------------------------------------- the card

def _clean(value, limit: int, *, lines: bool = False) -> Optional[str]:
    """Plain text with nothing invisible in it. Notes keep up to one blank line between paragraphs."""
    if value is None:
        return None
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    if lines:
        parts = [" ".join(_CONTROL.sub(" ", line).split()) for line in text.split("\n")]
        text = re.sub(r"\n{3,}", "\n\n", "\n".join(parts)).strip()
    else:
        text = " ".join(_CONTROL.sub(" ", text).split())
    if len(text) > limit:
        raise GiftError(422, f"Keep it to {limit} characters.")
    return text or None


def save_card(db: Session, gift: models.GiftMembership, changes: dict) -> models.GiftMembership:
    """The giver's wording: who it's for, who it's from and a short note. Fixed once the gift is opened."""
    if gift.redeemed_at is not None:
        raise GiftError(409, "This gift has been opened, so the card can't change any more.")
    if gift.cancelled_at is not None:
        raise GiftError(409, "This gift was turned off.")
    if "to_name" in changes:
        gift.to_name = _clean(changes["to_name"], TO_LIMIT)
    if "from_name" in changes:
        gift.from_name = _clean(changes["from_name"], FROM_LIMIT)
    if "note" in changes:
        gift.note = _clean(changes["note"], NOTE_LIMIT, lines=True)
    db.commit()
    db.refresh(gift)
    return gift


def count_open(db: Session, gift: models.GiftMembership) -> None:
    """Someone other than the giver opened the gift's page. Never raises."""
    try:
        db.query(models.GiftMembership).filter(models.GiftMembership.id == gift.id).update(
            {models.GiftMembership.opened: models.GiftMembership.opened + 1}, synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()


# ---------------------------------------------------------------- opening a gift

def _grant(db: Session, user_id: int, gift: models.GiftMembership, now: datetime) -> models.Supporter:
    supporter = supporters._supporter_for_grant(db, user_id)
    if supporter is None:
        supporter = models.Supporter(user_id=user_id, since=gift.paid_at, active_until=now, show_badge=True,
                                     number=supporters.next_number(db))
        db.add(supporter)
    start = max(supporter.active_until or now, now)
    supporter.active_until = start + timedelta(days=days_for(gift.months))
    supporter.since = min(supporter.since or gift.paid_at, gift.paid_at)
    supporter.monthly = bool(supporter.member_until and supporter.member_until > now)
    return supporter


def redeem(db: Session, user: models.User, raw_code: str) -> models.GiftMembership:
    """Open a gift on this member's account. Raises GiftError with what to tell them."""
    gift = by_code(db, raw_code)
    if gift is None or gift.cancelled_at is not None:
        raise GiftError(404, "That gift code doesn't work. Check it against the card, or ask whoever sent it for the link.")
    if gift.redeemed_at is not None:
        if gift.redeemed_by == user.id:
            return gift
        raise GiftError(409, "This gift has already been opened.")
    if gift.giver_id == user.id:
        raise GiftError(403, "You bought this gift, so it can't go on your own account. Send the link to the person it's for.")
    now = _now()
    # One account wins even if two press at the same moment: only one update finds it unopened.
    claimed = (db.query(models.GiftMembership)
               .filter(models.GiftMembership.id == gift.id, models.GiftMembership.redeemed_at.is_(None),
                       models.GiftMembership.cancelled_at.is_(None))
               .update({models.GiftMembership.redeemed_at: now, models.GiftMembership.redeemed_by: user.id},
                       synchronize_session=False))
    if claimed != 1:
        db.rollback()
        raise GiftError(409, "This gift has already been opened.")
    _grant(db, user.id, gift, now)
    db.commit()
    db.refresh(gift)
    _tell_giver(db, gift)
    return gift


def _tell_giver(db: Session, gift: models.GiftMembership) -> None:
    if not gift.giver_id:
        return
    try:
        from .crud.friends import create_notification  # avoids a circular import
        who = f"for {gift.to_name}" if gift.to_name else f"of {months_label(gift.months)}"
        create_notification(db, gift.giver_id, "gift_opened",
                            f"Your OmniTrackr gift {who} was just opened. Thank you for giving it!",
                            link="/supporters/gift#your-gifts")
    except Exception:
        db.rollback()


def tell_giver_ready(db: Session, gift: models.GiftMembership) -> None:
    """An in-app note for a member whose Ko-fi gift just arrived. Never raises."""
    if not gift.giver_id:
        return
    try:
        from .crud.friends import create_notification  # avoids a circular import
        create_notification(db, gift.giver_id, "gift_ready",
                            f"Your Ko-fi gift came through: {months_label(gift.months)} of supporter perks. "
                            "Send the link to whoever it's for, or print the card.",
                            link="/supporters/gift#your-gifts")
    except Exception:
        db.rollback()


# ---------------------------------------------------------------- lists

def view(gift: models.GiftMembership) -> dict:
    return {"id": gift.id, "months": gift.months, "months_label": months_label(gift.months), "state": state(gift),
            "code": code_of(gift), "path": path_of(gift), "manage_path": manage_path(gift),
            "to_name": gift.to_name, "from_name": gift.from_name, "note": gift.note,
            "paid_at": gift.paid_at, "redeemed_at": gift.redeemed_at, "opened": int(gift.opened or 0),
            "source": gift.source}


def given_by(db: Session, user_id: int, limit: int = 50) -> list[models.GiftMembership]:
    return (db.query(models.GiftMembership).filter(models.GiftMembership.giver_id == user_id)
            .order_by(models.GiftMembership.paid_at.desc(), models.GiftMembership.id.desc()).limit(limit).all())


def received_by(db: Session, user_id: int) -> list[models.GiftMembership]:
    return (db.query(models.GiftMembership).filter(models.GiftMembership.redeemed_by == user_id)
            .order_by(models.GiftMembership.redeemed_at.desc()).limit(20).all())


def received_summary(db: Session, user_id: int) -> Optional[dict]:
    """For Account → Supporter: how many gifts this member has opened and who the newest was from."""
    rows = received_by(db, user_id)
    if not rows:
        return None
    return {"count": len(rows), "from_name": rows[0].from_name, "months": rows[0].months,
            "opened_at": rows[0].redeemed_at.isoformat() if rows[0].redeemed_at else None}


def for_payer_email(db: Session, email: str) -> list[models.GiftMembership]:
    """Gifts paid for from this Ko-fi email (case, Gmail dots and "+tags" aside), newest first."""
    exact, key = supporters.email_hash(email), supporters.email_key(email)
    matches = [models.KofiPayment.email_hash == exact] if exact else []
    if key:
        matches.append(models.KofiPayment.email_key == key)
    if not matches:
        return []
    return (db.query(models.GiftMembership)
            .join(models.KofiPayment, models.KofiPayment.id == models.GiftMembership.payment_id)
            .filter(or_(*matches), models.GiftMembership.cancelled_at.is_(None))
            .order_by(models.GiftMembership.paid_at.desc()).limit(10).all())


# ---------------------------------------------------------------- the site owner

def owner_make(db: Session, months: int) -> models.GiftMembership:
    """A gift the owner hands out by hand: a giveaway, or a prize. Nobody paid for it on Ko-fi."""
    if not 1 <= int(months) <= MAX_MONTHS:
        raise GiftError(422, f"Pick between 1 and {MAX_MONTHS} months.")
    gift = create(db, months, source="owner")
    db.commit()
    return gift


def owner_from_payment(db: Session, message_id: str) -> models.GiftMembership:
    """A payer meant a gift but left OT-GIFT out. Turn their waiting payment into one."""
    payment = db.query(models.KofiPayment).filter(models.KofiPayment.message_id == message_id).first()
    if payment is None:
        raise GiftError(404, "Payment not found")
    if payment.user_id is not None or payment.gift or payment.dismissed_at is not None or supporters.looks_like_test(payment):
        raise GiftError(409, "Only a payment still waiting to be linked can become a gift.")
    if payment.kind not in supporters.PERK_TYPES or payment.monthly:
        raise GiftError(409, "Only a one-time Ko-fi payment can become a gift.")
    gift = from_webhook(db, payment, None)
    db.commit()
    return gift


def owner_cancel(db: Session, gift_id: int) -> models.GiftMembership:
    """Turn off an unopened gift (a refunded payment, a code posted somewhere public)."""
    gift = db.get(models.GiftMembership, gift_id)
    if gift is None:
        raise GiftError(404, "Gift not found")
    if gift.redeemed_at is not None:
        raise GiftError(409, "That gift has been opened already.")
    gift.cancelled_at = gift.cancelled_at or _now()
    db.commit()
    return gift


def owner_list(db: Session, limit: int = OWNER_LIST_LIMIT) -> list[dict]:
    rows = (db.query(models.GiftMembership, models.User.username)
            .outerjoin(models.User, models.User.id == models.GiftMembership.giver_id)
            .order_by(models.GiftMembership.created_at.desc(), models.GiftMembership.id.desc()).limit(limit).all())
    result = []
    for gift, giver in rows:
        item = view(gift)
        item.update({"giver": giver, "paid_at": gift.paid_at.isoformat() if gift.paid_at else None,
                     "redeemed_at": gift.redeemed_at.isoformat() if gift.redeemed_at else None})
        result.append(item)
    return result


def stats(db: Session, start: datetime) -> dict:
    gift = models.GiftMembership
    def count(*filters) -> int:
        return int(db.query(gift.id).filter(*filters).count())
    return {
        "bought": count(gift.source == "kofi", gift.paid_at >= start),
        "made": count(gift.source == "owner", gift.created_at >= start),
        "opened": count(gift.redeemed_at >= start),
        "waiting": count(gift.redeemed_at.is_(None), gift.cancelled_at.is_(None)),
    }


# ---------------------------------------------------------------- email

def email_item(gift: models.GiftMembership) -> dict:
    from .email import APP_URL
    base = APP_URL.rstrip("/")
    return {"months_label": months_label(gift.months), "code": code_of(gift), "url": f"{base}{path_of(gift)}",
            "manage_url": f"{base}{manage_path(gift)}", "state": state(gift)}


async def send_links(email: str, items: list, resend: bool = False) -> None:
    """Email gift links to the Ko-fi address that paid. Never raises: the webhook has already answered Ko-fi."""
    from . import email as email_utils
    try:
        await email_utils.send_gift_email(email, items, resend=resend)
    except Exception:
        print("Failed to send a Ko-fi gift email.")
