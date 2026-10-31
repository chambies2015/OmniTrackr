"""Your year so far: a look at the member's year during November, before Year in Review opens.

From November 1 to 30 the dashboard shows a card with the year to date (titles
finished, estimated hours, top genre) and one thing still in reach before
December 31. The weekly email carries the same summary, and members who turned
on the "Cheers, badges and goals" notifications get one push in the second half
of the month. On December 1 the Year in Review banner takes over
(``year_in_review.season_year``), so the two never show at the same time.

Everything is counted the way Year in Review counts it. Nothing new is stored,
apart from the ``push_nudges`` row that keeps the push to one a year.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.orm import Session

from . import goals, models, web_push, year_in_review

logger = logging.getLogger(__name__)

MONTH = 11
RECAP_OPENS = "December 1"
# The dated journal began in September 2026, so that year's count starts there.
COUNTED_SINCE = {2026: "September"}
PUSH_KIND = "year_so_far"
PUSH_FROM_DAY = 15
PUSH_MIN_FINISHED = 3
PUSH_FROM_HOUR = 10   # member's local time, when their time zone is known
PUSH_UNTIL_HOUR = 20
PER_RUN_LIMIT = 50
# Members checked today who had too little to say, so the hourly job doesn't rebuild their year every hour.
_quiet_until: dict[int, date] = {}
# Where each entry point sends the member; the page counts the visit by its ``from`` value.
SOURCES = {"card": "year_so_far_card_opened", "email": "year_so_far_email_opened", "push": "year_so_far_push_opened"}


def _today() -> date:
    return datetime.utcnow().date()


def active_year(today: Optional[date] = None) -> Optional[int]:
    """The year to preview right now: this year during November, otherwise None."""
    today = today or _today()
    return today.year if today.month == MONTH else None


def link(year: int, source: str) -> str:
    return f"/year-in-review/{year}?from={source}"


def _plural(count: int, singular: str, plural: Optional[str] = None) -> str:
    return f"{count:,} {singular if count == 1 else (plural or singular + 's')}"


def summary(db: Session, user: models.User, today: Optional[date] = None) -> Optional[dict]:
    """The member's year so far, or None outside November or when nothing was finished this year."""
    today = today or _today()
    year = active_year(today)
    if year is None:
        return None
    visible = list(year_in_review.CATEGORIES)
    _, finished = year_in_review._finishes(db, user.id, year, visible)
    if not finished:
        return None
    counts = {key: 0 for key in visible}
    for row in finished.values():
        counts[row["category"]] = counts.get(row["category"], 0) + 1
    ordered = sorted(finished.values(), key=lambda row: row["finished_at"])
    try:
        genres = year_in_review._genres(db, ordered, year_in_review._library_items(db, user.id, ordered))
    except Exception:
        db.rollback()
        genres = []
    spent = year_in_review._time(db, user, year, visible)
    top = max(counts, key=lambda key: counts[key])
    days_left = (date(year + 1, 1, 1) - today).days
    return {
        "year": year,
        "finished": len(finished),
        "hours": spent["hours"] if spent else None,
        "genre": genres[0]["name"] if genres else None,
        "top_shelf": {"category": top, "noun": goals.NOUNS[top][1], "finished": counts[top]},
        "days_left": days_left,
        "since": COUNTED_SINCE.get(year),
        "recap_opens": RECAP_OPENS,
        "hint": hint(db, user, year, today, counts, days_left),
        "url": link(year, "card"),
    }


def hint(db: Session, user: models.User, year: int, today: date, counts: dict, days_left: int) -> str:
    """One thing still in reach this year: the closest open goal, the top of Next Up, or the days left."""
    try:
        member_goals = goals.progress(db, user, year, today=today, counts=counts)
    except Exception:
        db.rollback()
        member_goals = []
    open_goals = [goal for goal in member_goals if goal["done"] < goal["target"]]
    if open_goals:
        goal = min(open_goals, key=lambda goal: (goal["target"] - goal["done"], goal["target"]))
        left = goal["target"] - goal["done"]
        singular, plural = goals.NOUNS[goal["category"]]
        return f"{_plural(left, singular, plural)} to go and you reach your goal of {goal['target']}."
    try:
        from .digest import next_up_line
        queued = next_up_line(db, user.id)
    except Exception:
        db.rollback()
        queued = None
    if queued:
        return f"Next in your queue is {queued['title']}. Finish it by December 31 and it makes your recap."
    if member_goals:
        return "You've already reached your goal for the year. Everything from here is extra."
    return f"{_plural(days_left, 'day')} left. Anything you finish by December 31 goes in your recap."


def headline(data: dict) -> str:
    """'23 titles finished and about 61 hours. Top genre: Fantasy.' Shared by the email and the push."""
    text = f"{_plural(data['finished'], 'title')} finished"
    if data.get("hours"):
        text += f" and about {_plural(data['hours'], 'hour')}"
    text += "."
    if data.get("genre"):
        text += f" Top genre: {data['genre']}."
    return text


# ---------------------------------------------------------------- push

def _local(pref: Optional[models.PushPreference], now: datetime) -> datetime:
    tz = web_push.zone(pref.time_zone) if pref is not None else None
    return now.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz).replace(tzinfo=None) if tz else now


def push_message(data: dict) -> str:
    return f"{data['year']} so far: {headline(data)} {data['hint']}"[:web_push.MAX_BODY_CHARS]


def send_pushes(db: Session, http: Optional[httpx.Client] = None, now: Optional[datetime] = None) -> dict:
    """One push per member per year, from November 15, to members whose "Cheers, badges and goals" switch is on."""
    now = now or datetime.utcnow()
    stats = {"sent": 0, "members": 0, "quiet": 0, "nothing_to_say": 0}
    year = active_year(now.date())
    if year is None or now.day < PUSH_FROM_DAY:
        return stats
    wanting = web_push.members_wanting(db, PUSH_KIND)
    if not wanting:
        return stats
    already = {user_id for (user_id,) in db.query(models.PushNudge.user_id).filter(
        models.PushNudge.kind == PUSH_KIND, models.PushNudge.sent_at >= datetime(year, 1, 1),
        models.PushNudge.user_id.in_(wanting))}
    candidates = [user_id for user_id in wanting
                  if user_id not in already and _quiet_until.get(user_id, date.min) < now.date()]
    if not candidates:
        return stats
    prefs = {pref.user_id: pref for pref in
             db.query(models.PushPreference).filter(models.PushPreference.user_id.in_(candidates)).all()}
    for user_id in candidates:
        if stats["members"] >= PER_RUN_LIMIT:
            break
        pref = prefs.get(user_id)
        if web_push.in_quiet_hours(pref, now) or not PUSH_FROM_HOUR <= _local(pref, now).hour < PUSH_UNTIL_HOUR:
            stats["quiet"] += 1
            continue
        user = db.get(models.User, user_id)
        if user is None or not user.is_active:
            continue
        try:
            data = summary(db, user, now.date())
        except Exception:
            db.rollback()
            logger.exception("Could not build the year so far for member %s", user_id)
            data = None
        if not data or data["finished"] < PUSH_MIN_FINISHED:
            _quiet_until[user_id] = now.date()
            stats["nothing_to_say"] += 1
            continue
        # Recorded before sending, so a second worker running at the same moment doesn't send a twin.
        db.add(models.PushNudge(user_id=user_id, kind=PUSH_KIND, sent_at=now))
        db.commit()
        delivered = web_push.deliver(db, [(user_id, PUSH_KIND, push_message(data), link(year, "push"))],
                                     http=http, now=now)
        stats["sent"] += delivered["sent"]
        stats["members"] += 1
    return stats
