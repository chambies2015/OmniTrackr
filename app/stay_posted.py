"""Asking members, at a good moment, how they'd like to hear about new episodes and releases (Nov 2026).

OmniTrackr already has three ways to bring news to a member: the weekly email, phone and browser
notifications, and a private calendar feed. Very few members ever found them, because the switches
sit in Settings. This module picks a moment to offer them, keeps the offer polite, and counts how
it does:

* A home-screen card when something the member tracks has an episode or a release coming up (with
  the titles named), or, failing that, once their library has some size to it.
* A short note right after saving a TV show or anime, offering a heads-up for its new episodes.

Nothing is ever switched on here. Each button calls the channel's own endpoint, which checks what
it always checks. Members who already use any of the three channels are never asked. The card
stays for a week unless answered, then rests for a month; "Not now" waits six weeks, and after
three showings, or "Don't ask again", it doesn't come back. The note after saving shows at most
twice, three weeks apart.

Counters go into ``site_traffic_daily`` under kind "stay" through the page-view buffer, and name
no member.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models

# ---------------------------------------------------------------- rules

MIN_AGE = timedelta(days=2)            # the first-week steps already offer the weekly email
MIN_VISIT_DAYS = 2                     # someone who came back at least once
MIN_TITLES = 3                         # enough of a library for news to be about
LIBRARY_TITLES = 10                    # the plain "stay posted" card needs a bigger library
OPEN_FOR = timedelta(days=7)           # a card stays up for a week unless answered
COOLDOWN = timedelta(days=30)          # then rests for a month before it can come back
LATER = timedelta(days=45)             # "Not now"
MAX_SHOWN = 3                          # three showings, then never again
AFTER_SAVE_GAP = timedelta(days=21)
MAX_AFTER_SAVE = 2
SOON_DAYS = 7                          # episodes in the next week
RELEASE_DAYS = 60                      # releases in the next two months
ITEM_LIMIT = 3

MOMENTS = {"soon": "Something they track is coming up", "library": "Library of 10 or more"}
CHANNELS = {"push": "Notifications on this device", "email": "Weekly email", "calendar": "Calendar"}
ANSWERS = {**CHANNELS, "later": "Not now", "stop": "Don't ask again", "sample": "Opened the sample email"}
AFTER_CATEGORIES = {"tv-shows": "TV show", "anime": "Anime"}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def count(key: str) -> bool:
    """Add 1 to a "stay" counter for today. Never raises."""
    try:
        from .site_traffic import RECORDER
        if not RECORDER.enabled or len(key) > 60:
            return False
        day = datetime.now(timezone.utc).date()
        with RECORDER._lock:
            RECORDER._pending[(day, "stay", key)] += 1
            RECORDER._events += 1
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- who is asked

def get_row(db: Session, user_id: int) -> Optional[models.StayPostedAsk]:
    return db.query(models.StayPostedAsk).filter(models.StayPostedAsk.user_id == user_id).first()


def _row(db: Session, user_id: int) -> models.StayPostedAsk:
    row = get_row(db, user_id)
    if row is None:
        row = models.StayPostedAsk(user_id=user_id, shown_count=0, after_save_count=0)
        db.add(row)
        db.flush()
    return row


def channels(db: Session, user: models.User) -> dict:
    """Which ways of hearing about news this member already has."""
    from . import digest
    return {
        "email": digest.subscription_for(db, user.id) is not None,
        "push": db.query(models.PushSubscription.id).filter(models.PushSubscription.user_id == user.id).first() is not None,
        "calendar": db.query(models.CalendarFeed.id).filter(models.CalendarFeed.user_id == user.id).first() is not None,
    }


def email_offer(user: models.User) -> bool:
    from . import digest
    return bool(user.is_verified and digest.mail_configured())


def _library_size(db: Session, user_id: int) -> int:
    """Titles across all nine libraries, in one query (the home screen asks every minute or so)."""
    from .badges import LIBRARY
    parts = [select(func.count(model.id)).where(model.user_id == user_id).scalar_subquery()
             for model, _flag in LIBRARY.values()]
    return int(db.execute(select(sum(parts[1:], parts[0]))).scalar() or 0)


def _settled(user: models.User, now: datetime) -> bool:
    created = user.created_at
    return created is not None and now - created >= MIN_AGE and int(user.visit_days or 0) >= MIN_VISIT_DAYS


def _resting(row: Optional[models.StayPostedAsk], now: datetime) -> bool:
    """Stopped, snoozed, used up, or shown recently enough that it's still resting."""
    if row is None:
        return False
    if row.stopped_at is not None or (row.shown_count or 0) >= MAX_SHOWN:
        return True
    if row.snoozed_until and row.snoozed_until > now:
        return True
    return bool(row.shown_at and now - row.shown_at < OPEN_FOR + COOLDOWN)


def _card_open(row: Optional[models.StayPostedAsk], now: datetime) -> bool:
    return bool(row and row.stopped_at is None and row.shown_at and now - row.shown_at < OPEN_FOR
                and (row.answered_at is None or row.answered_at < row.shown_at))


def _support_note_open(db: Session, user: models.User) -> bool:
    """One note on the home screen at a time: the support note wins when it's up."""
    try:
        from . import support_asks
        return support_asks.current(db, user) is not None
    except Exception:
        db.rollback()
        return False


# ---------------------------------------------------------------- what's coming up

def upcoming(db: Session, user: models.User, today: Optional[date] = None) -> list[dict]:
    """Up to three things the member tracks with an episode in the next week or a release in the next two
    months, soonest first. Reads only caches the home screen and the weekly email already keep."""
    today = today or _now().date()
    items: list[dict] = []
    try:
        from . import home_today
        for show in home_today.show_updates(db, user, today, datetime.combine(today, datetime.min.time())):
            nxt = show.get("next")
            if nxt and nxt.get("date"):
                items.append({"kind": "episode", "title": show["title"], "label": show["category_label"],
                              "what": nxt["code"], "date": nxt["date"]})
    except Exception:
        db.rollback()
    try:
        from .for_you import coming_up
        horizon = (today + timedelta(days=RELEASE_DAYS)).isoformat()
        for card in coming_up(db, user.id, today).get("matches", []):
            when = card.get("date") or ""
            if not (today.isoformat() < when <= horizon):
                continue
            if card.get("reason", "").startswith("Because"):
                continue  # a sequel or relative is a guess; the card only names titles they actually saved
            items.append({"kind": "release", "title": card["title"], "label": card.get("label") or "",
                          "what": "Out", "date": when})
    except Exception:
        db.rollback()
    seen, found = set(), []
    for item in sorted(items, key=lambda entry: (entry["date"], entry["title"].lower())):
        key = item["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        found.append({**item, "title": item["title"][:200]})
    return found[:ITEM_LIMIT]


# ---------------------------------------------------------------- the home-screen card

def _words(moment: str, items: list[dict], titles: int) -> dict:
    if moment == "soon":
        if len(items) == 1:
            item = items[0]
            title = (f"{item['title']} has a new episode coming" if item["kind"] == "episode"
                     else f"{item['title']} comes out soon")
        else:
            title = f"{len(items)} things you track have something coming up"
        return {"eyebrow": "Coming up", "title": title,
                "body": "Want a heads-up when they're out? Pick whichever suits you, or none. "
                        "You can change it any time in Settings."}
    return {"eyebrow": "Stay posted", "title": "Want a heads-up when something you track comes out?",
            "body": f"New episodes, new seasons, sequels and release days for the {titles:,} titles in your library. "
                    "Pick how you'd like to hear, or skip it."}


def _payload(db: Session, user: models.User, moment: str, items: list[dict], titles: int, have: dict) -> dict:
    # A card opened for one moment keeps that name for counting; its words follow what's coming up today.
    return {**_words("soon" if items else "library", items, titles), "moment": moment, "items": items,
            "offer": {"email": not have["email"] and email_offer(user), "calendar": not have["calendar"]},
            "sample_url": "/email/weekly/preview"}


def current(db: Session, user: models.User, now: Optional[datetime] = None) -> Optional[dict]:
    """The card to show now, if any. Looking doesn't count as shown."""
    now = now or _now()
    row = get_row(db, user.id)
    open_card = _card_open(row, now)
    if not open_card and (_resting(row, now) or not _settled(user, now)):
        return None
    have = channels(db, user)
    if any(have.values()):
        return None
    titles = _library_size(db, user.id)
    if titles < MIN_TITLES:
        return None
    if _support_note_open(db, user):
        return None
    items = upcoming(db, user, now.date())
    if open_card and row.moment in MOMENTS:
        return _payload(db, user, row.moment, items, titles, have)
    if items:
        return _payload(db, user, "soon", items, titles, have)
    if titles >= LIBRARY_TITLES:
        return _payload(db, user, "library", [], titles, have)
    return None


def mark_shown(db: Session, user: models.User, moment: str, now: Optional[datetime] = None) -> bool:
    """The card reached the member's screen."""
    if moment not in MOMENTS:
        return False
    now = now or _now()
    row = get_row(db, user.id)
    if _card_open(row, now):
        return True  # already counted this week
    found = current(db, user, now)
    if found is None or found["moment"] != moment:
        return False
    row = _row(db, user.id)
    row.moment, row.shown_at = moment, now
    row.shown_count = (row.shown_count or 0) + 1
    row.answer = None
    db.commit()
    count(f"card_shown_{moment}")
    return True


def answer(db: Session, user: models.User, reply: str, place: str = "card", now: Optional[datetime] = None) -> bool:
    """A button on the card or the note was pressed. Channel answers are reported after the channel's own
    endpoint turned it on; this only records that the asking worked."""
    if reply not in ANSWERS or place not in ("card", "after"):
        raise ValueError("Unknown answer")
    now = now or _now()
    row = get_row(db, user.id)
    if row is None:
        return False
    # A channel is only counted as turned on when it is on. The buttons report it after the
    # channel's own endpoint answered, so this only stops a hand-made request padding the totals.
    if reply in CHANNELS and not channels(db, user)[reply]:
        return False
    if place == "after":
        if row.after_save_at is None or now - row.after_save_at > timedelta(days=1):
            return False
        count(f"after_{reply}")
        if reply == "stop":
            row.stopped_at = now
            db.commit()
        return True
    moment = row.moment if row.moment in MOMENTS else None
    if moment is None or row.shown_at is None:
        return False
    if reply != "sample" and row.answer == reply and row.answered_at and row.answered_at >= row.shown_at:
        return True  # the same button again for the same showing counts once
    count(f"card_{reply}_{moment}")
    if reply == "sample":
        return True  # a look at the sample leaves the card where it is
    row.answer, row.answered_at = reply[:12], now
    if reply == "later":
        row.snoozed_until = now + LATER
    elif reply == "stop":
        row.stopped_at = now
    db.commit()
    return True


# ---------------------------------------------------------------- the note after saving a show

def after_save(db: Session, user: models.User, category: str, title: str, push_possible: bool,
               now: Optional[datetime] = None) -> Optional[dict]:
    """Whether to offer a heads-up right after a TV show or anime was saved, and which channel.
    Counts it as shown when it says yes."""
    if category not in AFTER_CATEGORIES:
        return None
    now = now or _now()
    row = get_row(db, user.id)
    if row is not None:
        if row.stopped_at is not None or (row.after_save_count or 0) >= MAX_AFTER_SAVE:
            return None
        if row.after_save_at and now - row.after_save_at < AFTER_SAVE_GAP:
            return None
        if _card_open(row, now):
            return None  # the card is already asking
    created = user.created_at
    if created is None or now - created < timedelta(hours=1):
        return None  # a brand-new member is still finding their feet
    have = channels(db, user)
    if any(have.values()):
        return None
    channel = "push" if push_possible else ("email" if email_offer(user) else None)
    if channel is None:
        return None
    row = _row(db, user.id)
    row.after_save_at = now
    row.after_save_count = (row.after_save_count or 0) + 1
    db.commit()
    count("after_shown")
    name = " ".join((title or "").split())[:120]
    if channel == "push":
        text = (f"Want a heads-up when new episodes of {name} come out?" if name
                else "Want a heads-up when new episodes come out?")
        hint = "A notification on this device on the day each one is out."
        action = "Notify me on this device"
    else:
        text = (f"Want an email when {name} has new episodes coming?" if name
                else "Want an email when your shows have new episodes coming?")
        hint = "One email a week, only when there's news."
        action = "Send me the weekly email"
    return {"channel": channel, "text": text, "hint": hint, "action": action}


# ---------------------------------------------------------------- Site stats

def stats(db: Session, days: int, now: datetime) -> dict:
    table = models.SiteTrafficDaily
    counts = dict(db.query(table.key, func.sum(table.count)).filter(
        table.kind == "stay", table.day >= (now - timedelta(days=days - 1)).date(),
    ).group_by(table.key).all())
    get = lambda key: int(counts.get(key) or 0)  # noqa: E731
    cards = [{"moment": label, "shown": get(f"card_shown_{key}"),
              **{reply: get(f"card_{reply}_{key}") for reply in ANSWERS}} for key, label in MOMENTS.items()]
    after = {"shown": get("after_shown"), **{reply: get(f"after_{reply}") for reply in ANSWERS}}
    return {
        "cards": cards,
        "shown": sum(row["shown"] for row in cards),
        "turned_on": {key: sum(row[key] for row in cards) + after[key] for key in CHANNELS},
        "later": sum(row["later"] for row in cards) + after["later"],
        "stopped": sum(row["stop"] for row in cards) + after["stop"],
        "sample": sum(row["sample"] for row in cards),
        "after": after,
        "stopped_now": int(db.query(func.count(models.StayPostedAsk.id)).filter(
            models.StayPostedAsk.stopped_at.isnot(None)).scalar() or 0),
    }
