"""Draw from your backlog: a home-screen card that turns a title saved and never started into a plan (Nov 2026).

Site stats: of 100 members who started a library, 31 reached five titles and 6 ever came back.
The home screen already brings up unfinished titles four ways (Today's pick, Next Up suggestions,
the Welcome Back Deck, For you), but each one is a list to scroll, and none of them ends in a plan.
A plan is what brings someone back: "Friday, Dune" is a reason to open OmniTrackr on Saturday and
tick it off. This card makes one, in a minute, from the member's own list:

* Deal three. Three face-down cards from titles the member saved and hasn't started (not finished,
  no progress saved, not marked "on the go" in Next Up). The same deal number gives the same three
  cards all day, mixing formats where it can. Each card says how long it has waited and roughly
  how long it takes.
* Keep one. One kept card per member at a time (a row in backlog_draws). The library isn't changed.
* Pick a night: tonight, tomorrow or a day this week. Then, if they want, a calendar event (.ics) and
  one email at 6 pm their time that day ("Tonight: Dune"). The member asks for it, so there is no
  owner switch, but it shares the daily email budget and the product-updates unsubscribe.
* After the night the card asks "How was it?": Finished it (and a score), Didn't get to it (pick
  another night) or Not for me (never dealt again; the title stays in the library). Finishing it
  anywhere else (the library, the check-in page linked from the email) closes the pick as well.

Counters go into ``site_traffic_daily`` under kind "draw" and name no member. The number to watch
is "Came back after their night" against "Picked a night".
"""
from __future__ import annotations

import asyncio
import os
import random
import zlib
from datetime import date, datetime, time, timedelta, timezone
from html import escape
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models

MIN_BACKLOG = 3                    # fewer titles than this waiting: Today's pick is enough
HAND = 3
POOL_PER_CATEGORY = 250
NIGHT_DAYS = 7                     # a night can be today or one of the next six days
REMIND_HOUR = 18                   # local time on the night: before it starts, after work
NIGHT_HOUR = 20                    # the calendar event starts at 8 pm local
EVENT_MINUTES = 120
LATE = timedelta(hours=3)          # a reminder that can't go out within this long is dropped, never sent late
PUT_BACK_REST = timedelta(hours=20)  # a title put back isn't dealt again the same evening
FINISHED_SHOWN = timedelta(days=2)   # a finished pick without a score can still be scored from the card
SEND_PREFIX = "backlog-draw-"
CHECK_EVERY_SECONDS = 900
FIRST_CHECK_DELAY_SECONDS = 480
PER_RUN_LIMIT = 20
UTM = "utm_source=email&utm_campaign=backlog-draw"

ACTIVE = "picked"
CLOSED = ("finished", "put_back", "not_for_me", "replaced", "gone")

COUNTERS = {
    "seen": "Saw the card",
    "dealt": "Dealt three cards",
    "redealt": "Dealt again",
    "picked": "Kept one",
    "night_set": "Picked a night for it",
    "calendar": "Added it to their calendar",
    "email_set": "Asked for an email that evening",
    "email_cancel": "Cancelled the email",
    "sent": "Evening emails sent",
    "dropped": "Evening emails dropped (late, finished already, or unsubscribed)",
    "back_after_night": "Came back after their night",
    "back_after_email": "Came back after their evening email",
    "finished": "Finished their pick",
    "rated": "Scored their pick",
    "later": "Didn't get to it (picked another night)",
    "not_for_me": "Not for me",
    "put_back": "Put it back",
    "hidden": "Hid the card",
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def count(key: str) -> bool:
    """Add 1 to a "draw" counter for today. Never raises."""
    if key not in COUNTERS:
        return False
    try:
        from .site_traffic import RECORDER
        if not RECORDER.enabled:
            return False
        day = datetime.now(timezone.utc).date()
        with RECORDER._lock:
            RECORDER._pending[(day, "draw", key)] += 1
            RECORDER._events += 1
        return True
    except Exception:
        return False


def daily_limit() -> int:
    try:
        return max(0, int(os.getenv("BACKLOG_DRAW_DAILY_LIMIT", "30")))
    except ValueError:
        return 30


def emails_enabled() -> bool:
    if os.getenv("BACKLOG_DRAW_EMAILS", "").strip().lower() in ("off", "0", "false", "no"):
        return False
    return os.getenv("TESTING", "").lower() != "true"


def local_today(now: datetime, value: Optional[str]) -> date:
    """The member's date from the browser, trusted only within a day of UTC's."""
    utc_today = now.date()
    try:
        given = date.fromisoformat(value or "")
    except ValueError:
        return utc_today
    return given if abs((given - utc_today).days) <= 1 else utc_today


# ---------------------------------------------------------------- the member's backlog

def _categories():
    from .check_in import CATEGORIES
    return CATEGORIES


def _visible(user: models.User) -> list[str]:
    from .user_columns import VISIBLE, ensure_loaded
    ensure_loaded(user, VISIBLE)
    return [category for category in _categories()
            if getattr(user, f"{category.replace('-', '_')}_visible", True) is not False]


def _started(db: Session, user_id: int) -> set[tuple[str, int]]:
    """Titles with progress saved or marked "on the go" in Next Up: Continue already shows those."""
    started = {(category, item_id) for category, item_id in db.query(
        models.ProgressCheckpoint.category, models.ProgressCheckpoint.item_id,
    ).filter(models.ProgressCheckpoint.user_id == user_id, models.ProgressCheckpoint.position > 0).all()}
    started |= {(category, item_id) for category, item_id in db.query(
        models.NextUpItem.category, models.NextUpItem.item_id,
    ).filter(models.NextUpItem.user_id == user_id, models.NextUpItem.started_at.isnot(None)).all()}
    return started


def _left_out(db: Session, user_id: int, now: datetime) -> set[tuple[str, int]]:
    rows = db.query(models.BacklogDraw.category, models.BacklogDraw.item_id, models.BacklogDraw.status,
                    models.BacklogDraw.closed_at).filter(
        models.BacklogDraw.user_id == user_id,
        models.BacklogDraw.status.in_(("not_for_me", "put_back", ACTIVE))).all()
    return {(category, item_id) for category, item_id, status, closed in rows
            if status != "put_back" or (closed and now - closed < PUT_BACK_REST)}


def backlog(db: Session, user: models.User, now: Optional[datetime] = None) -> list[tuple[str, object]]:
    """(category, library row) for every title the member could be dealt, oldest-saved order per format."""
    now = now or _now()
    skip = _started(db, user.id) | _left_out(db, user.id, now)
    found = []
    for category in _visible(user):
        model, done_field, _label, _button = _categories()[category]
        if category == "podcasts":
            continue  # a podcast is never really "started" or finished in one night
        rows = db.query(model).filter(
            model.user_id == user.id, getattr(model, done_field) != True,  # noqa: E712
            model.title.isnot(None), func.trim(model.title) != "",
        ).order_by(model.id).limit(POOL_PER_CATEGORY).all()
        found += [(category, row) for row in rows if (category, row.id) not in skip]
    return found


def _queued(db: Session, user_id: int) -> set[tuple[str, int]]:
    return {(category, item_id) for category, item_id in db.query(
        models.NextUpItem.category, models.NextUpItem.item_id).filter(models.NextUpItem.user_id == user_id).all()}


# ---------------------------------------------------------------- one card

VERB = {"movies": "watch", "tv-shows": "watch", "anime": "watch", "video-games": "play", "music": "listen to",
        "books": "read", "manga": "read", "podcasts": "listen to", "audiobooks": "listen to"}
FINISH_WORDS = {"movies": "Watched it", "tv-shows": "Finished it", "anime": "Finished it", "video-games": "Finished it",
                "music": "Listened to it", "books": "Read it", "manga": "Read it", "podcasts": "Listened to it",
                "audiobooks": "Finished it"}


def _waited(added: Optional[datetime], today: date) -> tuple[str, int]:
    """("Waiting 3 weeks", days) from when the title was saved. Unknown dates sort as the longest wait."""
    if added is None:
        return "On your list a long while", 10_000
    days = max(0, (today - added.date()).days)
    if days == 0:
        return "Saved today", 0
    if days == 1:
        return "Saved yesterday", 1
    if days < 14:
        return f"Waiting {days} days", days
    if days < 60:
        return f"Waiting {days // 7} weeks", days
    if days < 365:
        return f"Waiting {days // 30} months", days
    return "Waiting over a year", days


def _length_words(category: str, minutes: float, guessed: bool) -> str:
    minutes = int(round(minutes or 0))
    if minutes <= 0:
        return ""
    if minutes < 60:
        words = f"{minutes} min"
    elif minutes < 240 and not guessed:
        hours, rest = divmod(minutes, 60)
        words = f"{hours}h {rest:02d}m" if rest else f"{hours}h"
    else:
        hours = max(1, round(minutes / 60))
        words = f"{hours} hour{'s' if hours != 1 else ''}"
    if guessed:
        words = f"About {words}"
    return words


def _lengths(db: Session, cards: list[tuple[str, object]]) -> dict[tuple[str, int], tuple[float, bool]]:
    """Minutes for each dealt title from the shared title cache (read only), or a typical length."""
    from . import time_spent, title_metadata, title_pages
    keys = {}
    for category, row in cards:
        kind = title_pages.LIBRARY_TO_KIND[category]
        keys[(category, row.id)] = title_metadata.cache_key(kind, title_pages.normalize(row.title or ""),
                                                            title_pages.item_year(kind, row))
    try:
        facts = time_spent._cached_facts(db, list(keys.values()))
    except Exception:
        db.rollback()
        facts = {}
    result = {}
    for category, row in cards:
        try:
            result[(category, row.id)] = time_spent.full_minutes(category, row, facts.get(keys[(category, row.id)], {}))
        except Exception:
            result[(category, row.id)] = (0.0, True)
    return result


def _image(category: str, row) -> Optional[str]:
    from . import title_pages
    kind = title_pages.LIBRARY_TO_KIND[category]
    image = title_pages._safe_image(getattr(row, title_pages.IMAGE_FIELD[kind], None))
    return image if image and image.startswith("https://") else None


def _card(category: str, row, today: date, length: tuple[float, bool] = (0.0, True), queued: bool = False) -> dict:
    from . import title_pages
    kind = title_pages.LIBRARY_TO_KIND[category]
    year = title_pages.item_year(kind, row)
    title = " ".join((row.title or "").split())[:200]
    waited, days = _waited(getattr(row, "added_at", None), today)
    minutes, guessed = length
    return {
        "category": category,
        "id": row.id,
        "title": title,
        "year": year,
        "label": _categories()[category][2],
        "image": _image(category, row),
        "waited": waited,
        "waited_days": days,
        "length": _length_words(category, minutes, guessed),
        "minutes": int(round(minutes or 0)),
        "queued": queued,
        "verb": VERB[category],
        "finish_words": FINISH_WORDS[category],
        "url": title_pages.title_path(kind, title, year) if title else None,
    }


def _tag_hand(hand: list[dict]) -> None:
    """A little reason on two of the cards: the one that has waited longest, the quickest one."""
    if len(hand) < 2:
        return
    longest = max(hand, key=lambda card: card["waited_days"])
    if longest["waited_days"] >= 7:
        longest["tag"] = "Longest on your list"
    timed = [card for card in hand if card["minutes"] and card is not longest]
    if timed:
        quickest = min(timed, key=lambda card: card["minutes"])
        if quickest["minutes"] < max(card["minutes"] for card in hand):
            quickest["tag"] = "Quickest of the three"


def deal(db: Session, user: models.User, today: date, number: int = 0, now: Optional[datetime] = None) -> list[dict]:
    """Three cards. The same member, day and deal number always give the same three."""
    pool = backlog(db, user, now)
    if not pool:
        return []
    pool.sort(key=lambda entry: (entry[0], entry[1].id))
    rng = random.Random(zlib.crc32(f"{user.id}:{today.isoformat()}:{int(number)}".encode()))
    rng.shuffle(pool)
    hand: list[tuple[str, object]] = []
    for entry in pool:  # a different format for each card while there are formats left
        if len(hand) == HAND:
            break
        if all(entry[0] != chosen[0] for chosen in hand):
            hand.append(entry)
    for entry in pool:
        if len(hand) == HAND:
            break
        if entry not in hand:
            hand.append(entry)
    lengths = _lengths(db, hand)
    queued = _queued(db, user.id)
    cards = [_card(category, row, today, lengths[(category, row.id)], (category, row.id) in queued)
             for category, row in hand]
    _tag_hand(cards)
    return cards


# ---------------------------------------------------------------- the kept card

def active(db: Session, user_id: int) -> Optional[models.BacklogDraw]:
    return db.query(models.BacklogDraw).filter(
        models.BacklogDraw.user_id == user_id, models.BacklogDraw.status == ACTIVE,
    ).order_by(models.BacklogDraw.id.desc()).first()


def _item(db: Session, user_id: int, category: str, item_id: int):
    if category not in _categories():
        return None
    model = _categories()[category][0]
    return db.query(model).filter(model.id == item_id, model.user_id == user_id).first()


def _done(category: str, row) -> bool:
    return bool(getattr(row, _categories()[category][1], False))


def _close(db: Session, draw: models.BacklogDraw, status: str, now: datetime) -> None:
    draw.status = status
    draw.closed_at = now
    if draw.reminder_status == "set":
        draw.reminder_status = "dropped"


def _phase(draw: models.BacklogDraw, today: date) -> str:
    """planned: the night is today or later, or no night yet; after: the night has gone."""
    if draw.night is not None:
        return "after" if draw.night < today else "planned"
    return "after" if draw.picked_at.date() < today - timedelta(days=1) else "planned"


def _reminder(draw: models.BacklogDraw) -> Optional[dict]:
    if draw.reminder_status not in ("set", "sent"):
        return None
    return {"status": draw.reminder_status, "at": draw.remind_at.isoformat() + "Z" if draw.remind_at else None}


def _email_offer(db: Session, user: models.User) -> bool:
    return bool(user.email and user.is_verified)


def build(db: Session, user: models.User, today: date, now: Optional[datetime] = None) -> Optional[dict]:
    """The card as it stands, or None when there's nothing to deal and nothing kept."""
    now = now or _now()
    draw = active(db, user.id)
    if draw is not None:
        row = _item(db, user.id, draw.category, draw.item_id)
        if row is None:
            _close(db, draw, "gone", now)
            db.commit()
            draw = None
        elif _done(draw.category, row):
            # Ticked off somewhere else (the library, the check-in page from the email).
            _close(db, draw, "finished", now)
            db.commit()
            count("finished")
            return {"state": "finished", "today": today.isoformat(), "draw_id": draw.id,
                    "pick": _card(draw.category, row, today), "rating": row.rating,
                    "total": len(backlog(db, user, now))}
        else:
            length = _lengths(db, [(draw.category, row)])[(draw.category, row.id)]
            return {
                "state": _phase(draw, today),
                "today": today.isoformat(),
                "draw_id": draw.id,
                "pick": _card(draw.category, row, today, length, (draw.category, row.id) in _queued(db, user.id)),
                "night": draw.night.isoformat() if draw.night else None,
                "picked_on": draw.picked_at.date().isoformat(),
                "reminder": _reminder(draw),
                "calendar": draw.calendar_at is not None,
                "email_offer": _email_offer(db, user),
                "remind_hour": REMIND_HOUR,
            }
    total = len(backlog(db, user, now))
    if total < MIN_BACKLOG:
        return None
    return {"state": "deal", "today": today.isoformat(), "total": total}


def pick(db: Session, user: models.User, category: str, item_id: int, number: int, today: date,
         now: Optional[datetime] = None) -> models.BacklogDraw:
    """Keep one card. Only a title from the member's own backlog; an earlier kept card is replaced."""
    now = now or _now()
    if category not in _categories():
        raise LookupError("That title isn't in your library.")
    if not any(entry[0] == category and entry[1].id == item_id for entry in backlog(db, user, now)):
        raise LookupError("That title isn't waiting on your list any more.")
    current = active(db, user.id)
    if current is not None:
        _close(db, current, "replaced", now)
    draw = models.BacklogDraw(user_id=user.id, category=category, item_id=item_id, status=ACTIVE,
                              deal=max(0, min(int(number), 999)), picked_at=now, created_at=now)
    db.add(draw)
    db.commit()
    count("picked")
    return draw


def plan(db: Session, user: models.User, night: Optional[date], email: bool, tz_minutes: int, today: date,
         now: Optional[datetime] = None) -> models.BacklogDraw:
    """Set (or clear) the night, and the one evening email the member may ask for."""
    now = now or _now()
    draw = active(db, user.id)
    if draw is None:
        raise LookupError("Keep a card first.")
    if night is not None and not 0 <= (night - today).days < NIGHT_DAYS:
        raise ValueError("Pick tonight or a day in the next week.")
    tz_minutes = max(-14 * 60, min(14 * 60, int(tz_minutes)))
    moved = night != draw.night
    if moved and night is not None:
        count("night_set")
    if moved:
        draw.back_at = None  # a new night: coming back counts after this one
    draw.night = night
    draw.tz_minutes = tz_minutes
    if email:
        if night is None:
            raise ValueError("Pick a night first.")
        if not _email_offer(db, user):
            raise ValueError("Confirm your email address first.")
        if not (draw.reminder_status == "sent" and not moved):
            remind_at = datetime.combine(night, time(REMIND_HOUR)) - timedelta(minutes=tz_minutes)
            if remind_at <= now:
                raise ValueError("It's past 6 pm there, so there's no email tonight. Add it to your calendar instead.")
            if draw.reminder_status != "set":
                count("email_set")
            draw.remind_at = remind_at
            draw.reminder_status = "set"
            draw.reminder_set_at = now
            draw.reminder_sent_at = None
    elif draw.reminder_status == "set":
        draw.reminder_status = None
        draw.remind_at = None
        count("email_cancel")
    elif draw.reminder_status == "sent" and moved:
        draw.reminder_status = None
    db.commit()
    return draw


def answer(db: Session, user: models.User, action: str, rating: Optional[int] = None, draw_id: Optional[int] = None,
           now: Optional[datetime] = None) -> Optional[dict]:
    """How it went: finished (with or without a score), rate (a finished pick), later, not_for_me, put_back."""
    from . import check_in
    now = now or _now()
    if action == "rate":
        # The score buttons on a pick finished in the last two days.
        draw = db.query(models.BacklogDraw).filter(
            models.BacklogDraw.user_id == user.id, models.BacklogDraw.id == int(draw_id or 0),
            models.BacklogDraw.status.in_((ACTIVE, "finished"))).first()
        if draw is None or (draw.status == "finished" and (draw.closed_at is None or now - draw.closed_at > FINISHED_SHOWN)):
            raise LookupError("That pick has closed.")
        if rating is None:
            raise ValueError("Pick a score from 1 to 10.")
        card = check_in.answer(db, user, draw.category, draw.item_id, "rate", rating)
        if card is None:
            raise LookupError("That title isn't in your library any more.")
        count("rated")
        return card
    draw = active(db, user.id)
    if draw is None:
        raise LookupError("Keep a card first.")
    if action == "finished":
        card = check_in.answer(db, user, draw.category, draw.item_id, "finished", rating)
        draw = db.get(models.BacklogDraw, draw.id)
        if card is None:
            _close(db, draw, "gone", now)
            db.commit()
            raise LookupError("That title isn't in your library any more.")
        _close(db, draw, "finished", now)
        db.commit()
        count("finished")
        if rating is not None:
            count("rated")
        return card
    if action == "later":
        draw.night = None
        draw.reminder_status = None  # a "set" email is cancelled; a "sent" one is behind them
        draw.remind_at = None
        draw.picked_at = now  # the card asks again in a couple of days if no night is picked
        draw.back_at = None
        db.commit()
        count("later")
        return None
    if action in ("not_for_me", "put_back"):
        _close(db, draw, action, now)
        db.commit()
        count(action)
        return None
    raise ValueError("Unknown answer.")


def note_seen(db: Session, user: models.User, today: date, now: Optional[datetime] = None) -> dict:
    """The card reached the screen today. The first visit after the night counts as coming back."""
    now = now or _now()
    count("seen")
    draw = active(db, user.id)
    if draw is None:
        # A pick ticked off elsewhere closes on the next card load; look at the newest one too.
        draw = db.query(models.BacklogDraw).filter(models.BacklogDraw.user_id == user.id).order_by(
            models.BacklogDraw.id.desc()).first()
        if draw is None or draw.status != "finished" or draw.closed_at is None or now - draw.closed_at > FINISHED_SHOWN:
            return {"back": False}
    if draw.back_at is not None or draw.night is None or draw.night >= today:
        return {"back": False}
    draw.back_at = now
    db.commit()
    count("back_after_night")
    if draw.reminder_status == "sent":
        count("back_after_email")
    return {"back": True}


# ---------------------------------------------------------------- the calendar event

def calendar_ics(db: Session, user: models.User, now: Optional[datetime] = None) -> Optional[str]:
    """One event on the night (8 to 10 pm the member's time), with a link back to tick it off."""
    from .digest import app_url
    from .release_calendar import _escape, _fold
    now = now or _now()
    draw = active(db, user.id)
    if draw is None or draw.night is None:
        return None
    row = _item(db, user.id, draw.category, draw.item_id)
    if row is None:
        return None
    card = _card(draw.category, row, now.date())
    start = datetime.combine(draw.night, time(NIGHT_HOUR)) - timedelta(minutes=draw.tz_minutes or 0)
    end = start + timedelta(minutes=EVENT_MINUTES)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    home = f"{app_url()}/?{UTM.replace('email', 'calendar')}#backlog-draw"
    description = (f"From your OmniTrackr backlog. When you're done, tick it off and give it a score: {home}")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//OmniTrackr//Backlog draw//EN", "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH", "BEGIN:VEVENT",
        f"UID:backlog-draw-{draw.id}@omnitrackr.xyz",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{start.strftime('%Y%m%dT%H%M%SZ')}",
        f"DTEND:{end.strftime('%Y%m%dT%H%M%SZ')}",
        f"SUMMARY:{_escape(card['verb'].capitalize() + ' ' + card['title'])}",
        f"DESCRIPTION:{_escape(description)}",
        f"URL:{home}",
        "END:VEVENT", "END:VCALENDAR",
    ]
    if draw.calendar_at is None:
        draw.calendar_at = now
        db.commit()
        count("calendar")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


# ---------------------------------------------------------------- the evening email

def _link(path: str) -> str:
    from .digest import app_url
    if "#" in path:
        head, anchor = path.split("#", 1)
        joiner = "&" if "?" in head else "?"
        return f"{app_url()}{head}{joiner}{UTM}#{anchor}"
    joiner = "&" if "?" in path else "?"
    return f"{app_url()}{path}{joiner}{UTM}"


def build_email(username: str, card: dict, done_url: str, unsubscribe_url: str) -> tuple[str, str, str]:
    title = card["title"]
    subject = " ".join(f"Tonight: {title}".split())[:150]  # library titles are member-typed: one line, bounded
    detail = " · ".join(part for part in (card["label"], card.get("year") and str(card["year"]), card.get("length")) if part)
    home = _link("/#backlog-draw")
    page = _link(f"{card['url']}#where-title") if card.get("url") else home
    image = card.get("image")
    cover = (f'<img src="{escape(image, quote=True)}" width="96" height="144" alt="" '
             'style="display:block;width:96px;height:144px;object-fit:cover;border-radius:10px;background:#e9e5f5">'
             if image else '<div style="width:96px;height:144px;border-radius:10px;background:#e9e5f5"></div>')
    html = (
        '<html><body style="margin:0;background:#f4f2fb;font-family:Arial,Helvetica,sans-serif">'
        '<div style="max-width:560px;margin:0 auto;padding:24px">'
        '<div style="background:#1a1433;border-radius:14px 14px 0 0;padding:22px 24px;color:#fff">'
        '<div style="font-size:12px;letter-spacing:2px;color:#99f6e4;text-transform:uppercase">Your night in</div>'
        f'<div style="font-size:22px;font-weight:700;margin-top:6px">Tonight’s the night, {escape(username)}</div></div>'
        '<div style="background:#fff;border-radius:0 0 14px 14px;padding:20px 24px 24px">'
        '<p style="color:#1f1640;font-size:15px;line-height:1.6;margin-top:0">You drew this one from your list and picked tonight for it.</p>'
        '<table role="presentation" cellspacing="0" cellpadding="0"><tr>'
        f'<td style="vertical-align:top;padding-right:16px">{cover}</td>'
        '<td style="vertical-align:top">'
        f'<div style="color:#1f1640;font-weight:700;font-size:18px;line-height:1.3"><a href="{escape(page, quote=True)}" '
        f'style="color:#1f1640;text-decoration:none">{escape(title)}</a></div>'
        f'<div style="color:#5b5675;font-size:13px;line-height:1.6;margin-top:4px">{escape(detail)}</div>'
        f'<div style="margin-top:10px"><a href="{escape(page, quote=True)}" style="color:#6d28d9;font-size:13px">Where to {escape(card["verb"])} it</a></div>'
        '</td></tr></table>'
        f'<p style="margin:24px 0 8px"><a href="{escape(done_url, quote=True)}" '
        'style="background:#7c3aed;color:#fff;padding:12px 20px;border-radius:999px;text-decoration:none;font-weight:700">'
        f'{escape(card["finish_words"])}? Give it a score</a></p>'
        f'<p style="margin:22px 0 0"><a href="{escape(home, quote=True)}" style="color:#6d28d9;font-size:14px">'
        'Not tonight? Pick another night</a></p>'
        '<p style="color:#6f6a8a;font-size:12px;line-height:1.5;margin-top:24px">This is the one email you asked for when you '
        'picked a night on your OmniTrackr home screen. The score button works without signing in. '
        f'<a href="{escape(unsubscribe_url, quote=True)}" style="color:#6d28d9">Unsubscribe from product updates</a>.</p>'
        '</div></div></body></html>'
    )
    text = "\n".join([
        f"Hi {username},", "",
        f"Tonight's the night: {title} ({detail}).", "You drew it from your list and picked tonight for it.", "",
        f"Where to {card['verb']} it: {page}",
        f"{card['finish_words']}? Give it a score: {done_url}",
        f"Not tonight? Pick another night: {home}", "",
        "This is the one email you asked for when you picked a night on your OmniTrackr home screen.",
        f"Unsubscribe from product updates: {unsubscribe_url}",
    ])
    return subject, html, text


def email_for(db: Session, user: models.User, draw: models.BacklogDraw) -> Optional[tuple[str, str, str, str]]:
    """(subject, html, text, unsubscribe_url), or None when the pick is finished or gone."""
    from . import check_in
    from .announcements import unsubscribe_token
    from .digest import app_url
    row = _item(db, user.id, draw.category, draw.item_id)
    if row is None or _done(draw.category, row):
        return None
    length = _lengths(db, [(draw.category, row)])[(draw.category, row.id)]
    card = _card(draw.category, row, draw.night or _now().date(), length)
    token = check_in.make_token(user.id, [{"category": draw.category, "id": row.id}], "draw")
    done_url = check_in.link_for(token, 0, "finished")
    unsubscribe_url = f"{app_url()}/email/updates/unsubscribe?token={unsubscribe_token(user.id)}"
    subject, html, text = build_email(user.username, card, done_url, unsubscribe_url)
    return subject, html, text, unsubscribe_url


def allowance(db: Session, now: datetime) -> int:
    """How many may go out now: inside this email's own daily limit and the shared daily cap."""
    from .announcements import shared_cap
    since = now - timedelta(hours=24)
    sent_mine = db.query(func.count(models.EmailCampaignSend.id)).filter(
        models.EmailCampaignSend.campaign_key.like(f"{SEND_PREFIX}%"),
        models.EmailCampaignSend.sent_at >= since).scalar() or 0
    sent_campaign = db.query(func.count(models.EmailCampaignSend.id)).filter(
        models.EmailCampaignSend.sent_at >= since).scalar() or 0
    sent_digest = db.query(func.count(models.EmailDigestSubscription.id)).filter(
        models.EmailDigestSubscription.last_sent_at >= since).scalar() or 0
    return max(0, min(daily_limit() - sent_mine, shared_cap() - sent_campaign - sent_digest, PER_RUN_LIMIT))


def due(db: Session, now: datetime) -> list[models.BacklogDraw]:
    return db.query(models.BacklogDraw).filter(
        models.BacklogDraw.reminder_status == "set", models.BacklogDraw.remind_at <= now,
    ).order_by(models.BacklogDraw.remind_at).limit(200).all()


def _opted_out_since(db: Session, draw: models.BacklogDraw) -> bool:
    """Unsubscribed from product updates after asking (the email's footer link is that unsubscribe)."""
    opted = db.query(models.EmailOptOut.created_at).filter(models.EmailOptOut.user_id == draw.user_id).scalar()
    return opted is not None and (draw.reminder_set_at is None or opted >= draw.reminder_set_at)


async def _send(to: str, subject: str, html: str, unsubscribe_url: str) -> None:
    from .digest import _send as send_mail
    await send_mail(to, subject, html, unsubscribe_url)


def _drop(db: Session, draw: models.BacklogDraw, result: dict) -> None:
    draw.reminder_status = "dropped"
    db.commit()
    count("dropped")
    result["dropped"] += 1


async def send_due(session_factory, now: Optional[datetime] = None, sender=_send) -> dict:
    from .digest import mail_configured
    now = now or _now()
    result = {"sent": 0, "failed": 0, "dropped": 0, "limited": False}
    if not mail_configured() and sender is _send:
        return result
    db = session_factory()
    try:
        from .email_quota import lock_email_budget
        for draw in due(db, now):
            user = db.get(models.User, draw.user_id)
            if (user is None or not user.is_active or not user.is_verified or not user.email or draw.status != ACTIVE
                    or draw.night is None or now - draw.remind_at > LATE or _opted_out_since(db, draw)):
                _drop(db, draw, result)
                continue
            lock_email_budget(db)
            if allowance(db, now) <= 0:
                db.rollback()
                result["limited"] = True
                break  # still inside its window; the next run tries again
            try:
                built = email_for(db, user, draw)
            except Exception as error:
                print(f"Backlog draw email for user {user.id} couldn't be built: {error}")
                db.rollback()
                continue
            if built is None:
                _drop(db, draw, result)
                continue
            # Claim first so an overlapping run can never send twice.
            db.add(models.EmailCampaignSend(campaign_key=f"{SEND_PREFIX}{draw.id}", user_id=user.id,
                                            status="sent", sent_at=now))
            draw.reminder_status = "sent"
            draw.reminder_sent_at = now
            try:
                db.commit()
            except Exception:
                db.rollback()
                continue
            subject, html, _text, unsubscribe_url = built
            try:
                await sender(user.email, subject, html, unsubscribe_url)
                result["sent"] += 1
                count("sent")
            except Exception as error:  # One bad address must not stop the rest.
                print(f"Backlog draw email to user {user.id} failed: {error}")
                draw.reminder_status = "failed"
                db.commit()
                result["failed"] += 1
        return result
    finally:
        db.close()


async def backlog_draw_loop(app) -> None:
    """Background task started with the app; never raises."""
    from .database import SessionLocal
    await asyncio.sleep(FIRST_CHECK_DELAY_SECONDS)
    while True:
        try:
            result = await send_due(SessionLocal)
            if result["sent"] or result["failed"]:
                print(f"Backlog draw emails: {result}")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"Backlog draw email check failed: {error}")
        await asyncio.sleep(CHECK_EVERY_SECONDS)


# ---------------------------------------------------------------- Site stats

def stats(db: Session, days: int, now: datetime) -> dict:
    table = models.SiteTrafficDaily
    counts = dict(db.query(table.key, func.sum(table.count)).filter(
        table.kind == "draw", table.day >= (now - timedelta(days=days - 1)).date(),
    ).group_by(table.key).all())
    draws = models.BacklogDraw
    return {
        "counts": {key: int(counts.get(key) or 0) for key in COUNTERS},
        "labels": COUNTERS,
        "kept_now": int(db.query(func.count(draws.id)).filter(draws.status == ACTIVE).scalar() or 0),
        "pending_emails": int(db.query(func.count(draws.id)).filter(draws.reminder_status == "set").scalar() or 0),
        "finished_all_time": int(db.query(func.count(draws.id)).filter(draws.status == "finished").scalar() or 0),
    }
