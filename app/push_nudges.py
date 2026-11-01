"""Away reminders: one push to a member who hasn't opened OmniTrackr in a week.

The reminder always says something concrete from the member's own library: an
episode of their show out this week, a release they track that's coming up, or
a title still waiting to be finished. A member with nothing of the kind gets no
reminder at all.

Rules (all of them, every time):
- Only members who turned notifications on for a device and left the
  "When you've been away" switch on. Turning either off stops these at once.
- At most one every two weeks, and none once two went unanswered: a member who
  doesn't come back isn't chased.
- Never inside the member's quiet hours; the check runs again the next hour.
- Nothing is shown in the bell for these, so a member coming back after weeks
  doesn't find reminders about being away.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import models, web_push

KIND = "away_nudge"
AWAY_DAYS = 7
EVERY_DAYS = 14
MAX_UNANSWERED = 2
PER_RUN_LIMIT = 50
LINK = "/?utm_source=push&utm_campaign=away-reminder"
UPCOMING_DAYS = 14
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def away_since(user: models.User) -> datetime:
    from .comeback import _away_since
    return _away_since(user)


def due_members(db: Session, now: datetime) -> list[models.User]:
    """Members with a device and the switch on, away a week or more, not reminded lately or too often."""
    wanting = web_push.members_wanting(db, KIND)
    if not wanting:
        return []
    cutoff = now - timedelta(days=AWAY_DAYS)
    candidates = db.query(models.User).filter(
        models.User.id.in_(wanting),
        models.User.is_active == True, models.User.is_verified == True,  # noqa: E712
        or_(models.User.created_at.is_(None), models.User.created_at < cutoff),
        or_(models.User.last_login_at.is_(None), models.User.last_login_at < cutoff),
        or_(models.User.last_seen_on.is_(None), models.User.last_seen_on < cutoff.date()),
    ).order_by(models.User.id).all()
    if not candidates:
        return []
    sent_by_user: dict[int, list[datetime]] = {}
    for user_id, sent_at in db.query(models.PushNudge.user_id, models.PushNudge.sent_at).filter(
            models.PushNudge.kind == KIND, models.PushNudge.user_id.in_([user.id for user in candidates])):
        sent_by_user.setdefault(user_id, []).append(sent_at)
    due = []
    for user in candidates:
        since = away_since(user)
        if since >= cutoff:
            continue
        sent = sent_by_user.get(user.id, [])
        if any(sent_at > now - timedelta(days=EVERY_DAYS) for sent_at in sent):
            continue
        if sum(1 for sent_at in sent if sent_at > since) >= MAX_UNANSWERED:
            continue
        due.append(user)
    return due


# ---------------------------------------------------------------- what to say

def when(day: date, today: date) -> str:
    if day <= today:
        return "today"
    if day == today + timedelta(days=1):
        return "tomorrow"
    return f"on {WEEKDAYS[day.weekday()]}"


def _episode_line(db: Session, user: models.User, today: date) -> Optional[str]:
    from .episode_calendar import week_ahead
    shows = week_ahead(db, user, today)
    if not shows:
        return None
    show = shows[0]
    episode = show["episodes"][0]
    try:
        day = date.fromisoformat(episode["date"])
    except (KeyError, ValueError):
        return None
    name = f", {episode['name']}" if episode.get("name") else ""
    return f"{show['title']} {episode['code']}{name} is out {when(day, today)}."


def _release_line(db: Session, user: models.User, today: date, pool) -> Optional[str]:
    from .for_you import RADAR_LABELS, coming_up
    if not pool:
        return None
    matches = coming_up(db, user.id, today=today, pool=pool)["matches"]
    soon = []
    for card in matches:
        try:
            day = date.fromisoformat(card.get("date") or "")
        except ValueError:
            continue
        if today <= day <= today + timedelta(days=UPCOMING_DAYS):
            soon.append((day, card))
    if not soon:
        return None
    day, card = soon[0]
    label = RADAR_LABELS.get(card.get("category"), "")
    label = f" ({label})" if label else ""
    return f"{card['title']}{label} is out {when(day, today)}, and it's connected to your library."


def _waiting_line(db: Session, user: models.User) -> Optional[str]:
    from .comeback import library_snapshot
    _total, waiting = library_snapshot(db, user.id)
    if not waiting:
        return None
    first = waiting[0]["title"]
    rest = len(waiting) - 1
    more = f" and {rest} more" if rest else ""
    return f"{first}{more} {'are' if rest else 'is'} still waiting in your library. One for tonight?"


def message_for(db: Session, user: models.User, today: date, pool=None) -> Optional[str]:
    """Something concrete from the member's library, or None when there's nothing worth a buzz."""
    for build in (lambda: _episode_line(db, user, today), lambda: _release_line(db, user, today, pool),
                  lambda: _waiting_line(db, user)):
        try:
            line = build()
        except Exception:
            db.rollback()
            line = None
        if line:
            return line[:web_push.MAX_BODY_CHARS]
    return None


# ---------------------------------------------------------------- sending

def send_nudges(db: Session, http: Optional[httpx.Client] = None, now: Optional[datetime] = None) -> dict:
    """Push one reminder to each member who is due. Returns counts for logging and tests."""
    now = now or datetime.utcnow()
    today = now.date()
    stats = {"sent": 0, "members": 0, "quiet": 0, "nothing_to_say": 0}
    due = due_members(db, now)[:PER_RUN_LIMIT]
    if not due:
        return stats
    try:
        from .for_you import radar_pool
        pool = radar_pool(today)
    except Exception:
        pool = []
    prefs = {pref.user_id: pref for pref in
             db.query(models.PushPreference).filter(models.PushPreference.user_id.in_([u.id for u in due])).all()}
    for user in due:
        if web_push.in_quiet_hours(prefs.get(user.id), now):
            stats["quiet"] += 1
            continue
        message = message_for(db, user, today, pool)
        if not message:
            stats["nothing_to_say"] += 1
            continue
        # Recorded before sending, so a second worker running at the same moment doesn't send a twin.
        db.add(models.PushNudge(user_id=user.id, kind=KIND, sent_at=now))
        db.commit()
        delivered = web_push.deliver(db, [(user.id, KIND, message, LINK)], http=http, now=now)
        stats["sent"] += delivered["sent"]
        stats["members"] += 1
    return stats
