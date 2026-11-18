"""A member's own weekly email, shown before they sign up for it.

Nobody had turned the weekly email on. Every ask described it in general terms
("a short email when something you track...") and the only sample opened in a new
tab. This module gives the asks something concrete to show:

* ``summary`` lists what this week's email would actually say for the signed-in
  member, as a few lines the Settings panel, the For you invite and the home card
  can show in place (built by the same code as the real email, nothing is sent).
* ``send_copy`` emails the member one copy of this week's email when they ask for
  it, with a "Yes, every week" button. It never subscribes anyone: the button opens
  the usual confirm page. One copy per member every COPY_EVERY, inside the shared
  daily email budget, recorded in EmailCampaignSend like the other one-off emails.

Counters (kind "weeklymail"): preview_<place> when a preview is shown, copy_sent,
copy_failed. Opt-ins from these places count under digest.SOURCES "preview" and
"copy_email".
"""
from __future__ import annotations

import os
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import digest, models

PLACES = ("settings", "for_you", "home_card", "page")
COUNTERS = {f"preview_{place}" for place in PLACES} | {"copy_sent", "copy_failed"}
COPY_PREFIX = "weekly-copy-"
COPY_EVERY = timedelta(days=14)
ITEMS_SHOWN = 5
CACHE_SECONDS = 180
CACHE_SIZE = 500

SECTIONS = {
    "library": "From your library",
    "episodes": "New episodes this week",
    "friends": "New on your friends' shelves",
    "next_up": "Next in your queue",
    "following": "From people you follow",
    "past": "This week in past years",
    "popular": "Popular this month",
}

_cache: dict[int, tuple[float, str, dict]] = {}
_cache_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def count(key: str) -> bool:
    """Add 1 to a "weeklymail" counter for today. Never raises."""
    if key not in COUNTERS:
        return False
    try:
        from .site_traffic import RECORDER
        if not RECORDER.enabled:
            return False
        day = datetime.now(timezone.utc).date()
        with RECORDER._lock:
            RECORDER._pending[(day, "weeklymail", key)] += 1
            RECORDER._events += 1
        return True
    except Exception:
        return False


def copy_daily_limit() -> int:
    try:
        return max(0, int(os.getenv("WEEKLY_COPY_DAILY_LIMIT", "20")))
    except ValueError:
        return 20


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def forget(user_id: int) -> None:
    """Drop a member's cached preview (after they save something, say)."""
    with _cache_lock:
        _cache.pop(user_id, None)


def _relative(url: str) -> str:
    base = digest.app_url()
    if url.startswith(base + "/"):
        return url[len(base):]
    return url if url.startswith("/") else ""


def _line(section: str, title: str, detail: str = "", note: str = "", url: str = "", image: str | None = None) -> dict:
    return {"section": section, "heading": SECTIONS[section], "title": title, "detail": detail,
            "note": note, "url": _relative(url) if url else "", "image": image or None}


def _content(db: Session, user, now: datetime, client=None, today: date | None = None) -> dict:
    core = digest.gather_core(db, user, now, today=today, client=client)
    extras = digest.gather_extras(db, user, now, today=today)
    built = digest.build_from_parts(user.username, core, extras, unsubscribe_url="#")
    report = core["report"]
    lines: list[dict] = []
    for card in report["matches"]:
        lines.append(_line("library", card["title"], f"{card['label']} · {digest._day(card.get('date'))}",
                           card.get("reason") or "", card.get("url") or "", card.get("image")))
    for show in core["episodes"]:
        lines.append(_line("episodes", show["title"], digest._episode_line(show), url=show.get("url") or ""))
    for friend in core["friends"]:
        titles = [digest._friend_title(entry) for entry in friend["titles"]]
        extra = friend["count"] - len(friend["titles"])
        if extra > 0:
            titles.append(f"{extra} more")
        first = next((entry for entry in friend["titles"] if entry.get("path")), None)
        lines.append(_line("friends", f"{friend['username']} added {digest._and_list(titles)}",
                           url=first["path"] if first else ""))
    personal = bool(lines)
    next_up = extras["next_up"]
    if next_up:
        waiting = next_up["waiting"]
        lines.append(_line("next_up", next_up["title"], next_up["label"],
                           f"{waiting} more behind it" if waiting else "", "/#next-up"))
    for item in extras["following"] or []:
        lines.append(_line("following", digest._following_text(item), url=item.get("url") or ""))
    for memory in extras["past"] or []:
        when = "A year ago" if memory["ago"] == 1 else f"{memory['ago']} years ago"
        lines.append(_line("past", memory["line"], when))
    if not personal:
        for card in report["popular"][:3]:
            lines.append(_line("popular", card["title"], f"{card['label']} · {digest._day(card.get('date'))}",
                               url=card.get("url") or "", image=card.get("image")))
    also = []
    if extras["recap"]:
        also.append("your year so far" if extras["recap"].get("so_far") else "your Year in Review")
    if extras["goals"]:
        also.append(f"your {extras['goals_year']} goals")
    if extras["challenge"]:
        also.append("your New Year's challenge")
    if extras["badge"]:
        also.append("a badge you're close to")
    if extras["ask"]:
        also.append(f"asking a friend about {extras['ask']['title']}")
    return {
        "subject": built[0] if built else None,
        "personal": personal,
        "items": lines[:ITEMS_SHOWN],
        "more": max(0, len(lines) - ITEMS_SHOWN),
        "sections": list(dict.fromkeys(line["heading"] for line in lines)),
        "also": also,
        "library_total": report.get("library_total", 0),
    }


def content(db: Session, user, now: Optional[datetime] = None, client=None, today: date | None = None,
            fresh: bool = False) -> dict:
    """What this week's email would list for the member, cached for a few minutes per member."""
    now = now or _now()
    day = (today or now.date()).isoformat()
    with _cache_lock:
        hit = _cache.get(user.id)
    if hit and not fresh and hit[1] == day and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[2]
    found = _content(db, user, now, client=client, today=today)
    with _cache_lock:
        if len(_cache) >= CACHE_SIZE:
            _cache.pop(next(iter(_cache)))
        _cache[user.id] = (time.monotonic(), day, found)
    return found


# ---------------------------------------------------------------- one copy, on request

def last_copy_at(db: Session, user_id: int) -> Optional[datetime]:
    return db.query(func.max(models.EmailCampaignSend.sent_at)).filter(
        models.EmailCampaignSend.user_id == user_id,
        models.EmailCampaignSend.campaign_key.like(f"{COPY_PREFIX}%"),
        models.EmailCampaignSend.status == "sent",
    ).scalar()


def copy_state(db: Session, user, now: Optional[datetime] = None) -> dict:
    """Whether the member can ask for a copy now, and if not, why (shown next to the button)."""
    now = now or _now()
    if not digest.mail_configured():
        return {"can": False, "reason": "off"}
    if not user.is_verified or not user.email:
        return {"can": False, "reason": "verify"}
    if digest.subscription_for(db, user.id) is not None:
        return {"can": False, "reason": "subscribed"}
    last = last_copy_at(db, user.id)
    if last and last > now - COPY_EVERY:
        return {"can": False, "reason": "recent", "sent_at": last.isoformat() + "Z",
                "again_at": (last + COPY_EVERY).isoformat() + "Z"}
    return {"can": True, "reason": None}


def summary(db: Session, user, now: Optional[datetime] = None, client=None, today: date | None = None) -> dict:
    now = now or _now()
    subscription = digest.subscription_for(db, user.id)
    found = content(db, user, now, client=client, today=today)
    return {
        **found,
        "available": digest.mail_configured(),
        "subscribed": subscription is not None,
        "last_sent_at": subscription.last_sent_at.isoformat() + "Z" if subscription and subscription.last_sent_at else None,
        "copy": copy_state(db, user, now),
    }


def _allowance(db: Session, now: datetime) -> int:
    from .announcements import shared_cap
    since = now - timedelta(hours=24)
    sent_mine = db.query(func.count(models.EmailCampaignSend.id)).filter(
        models.EmailCampaignSend.campaign_key.like(f"{COPY_PREFIX}%"),
        models.EmailCampaignSend.sent_at >= since).scalar() or 0
    sent_campaign = db.query(func.count(models.EmailCampaignSend.id)).filter(
        models.EmailCampaignSend.sent_at >= since).scalar() or 0
    sent_digest = db.query(func.count(models.EmailDigestSubscription.id)).filter(
        models.EmailDigestSubscription.last_sent_at >= since).scalar() or 0
    return max(0, min(copy_daily_limit() - sent_mine, shared_cap() - sent_campaign - sent_digest))


def copy_link(user_id: int) -> str:
    return digest.subscribe_link(user_id) + "&from=copy"


async def _send(to: str, subject: str, html: str) -> None:
    import asyncio
    from fastapi_mail import FastMail
    from .email import conf, html_message
    # A one-off the member asked for, so no List-Unsubscribe: there is nothing to unsubscribe from.
    await asyncio.wait_for(FastMail(conf).send_message(html_message(subject, [to], html)), timeout=30.0)


class CopyRefused(Exception):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


REFUSALS = {
    "off": "Email isn't set up on this server right now.",
    "verify": "Verify your email address first, then we can send you a copy.",
    "subscribed": "You already get the weekly email.",
    "recent": "We sent you a copy recently. Check your inbox (and the spam folder).",
    "busy": "Lots of email went out today. Try again tomorrow.",
    "empty": "There's nothing to put in it yet. Save a few titles first.",
}


async def send_copy(db: Session, user, now: Optional[datetime] = None, client=None, sender=None) -> dict:
    """Email the member this week's email once. Raises CopyRefused with a reason the page can show."""
    now = now or _now()
    state = copy_state(db, user, now)
    if not state["can"]:
        raise CopyRefused(state["reason"], REFUSALS[state["reason"]])
    core = digest.gather_core(db, user, now, client=client)
    extras = digest.gather_extras(db, user, now)
    built = digest.build_from_parts(user.username, core, extras, unsubscribe_url="#", copy_url=copy_link(user.id))
    if built is None:
        raise CopyRefused("empty", REFUSALS["empty"])
    from .email_quota import lock_email_budget
    lock_email_budget(db)
    if _allowance(db, now) <= 0:
        db.rollback()
        raise CopyRefused("busy", REFUSALS["busy"])
    # Claim before sending, so a double press can never send twice.
    row = models.EmailCampaignSend(campaign_key=f"{COPY_PREFIX}{now.date().isoformat()}", user_id=user.id,
                                   status="sent", sent_at=now)
    db.add(row)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise CopyRefused("recent", REFUSALS["recent"])
    subject, html, _text = built
    try:
        await (sender or _send)(user.email, subject, html)
    except Exception as error:
        print(f"Weekly email copy to user {user.id} failed: {error}")
        db.delete(row)  # nothing arrived, so the member can press again
        db.commit()
        count("copy_failed")
        raise CopyRefused("failed", "The email didn't go through. Try again in a little while.")
    count("copy_sent")
    return {"sent": True, "subject": subject, "copy": copy_state(db, user, now)}


def stats(db: Session, days: int, now: datetime) -> dict:
    """Site stats rows: previews shown by place and copies sent in the range."""
    table = models.SiteTrafficDaily
    counts = dict(db.query(table.key, func.sum(table.count)).filter(
        table.kind == "weeklymail", table.day >= (now - timedelta(days=days - 1)).date(),
    ).group_by(table.key).all())
    labels = {"settings": "Settings", "for_you": "the For you invite", "home_card": "the home screen card",
              "page": "the full preview page"}
    return {
        "previews": [{"place": labels[place], "count": int(counts.get(f"preview_{place}") or 0)} for place in PLACES],
        "copies_sent": int(counts.get("copy_sent") or 0),
        "copies_failed": int(counts.get("copy_failed") or 0),
    }
