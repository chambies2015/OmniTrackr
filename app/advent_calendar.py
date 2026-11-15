"""The December advent calendar (/holidays/advent-calendar), whose writing lives in advent_calendar_data.py.

Twenty-four doors, one opening each day from December 1. Each holds one pick that
members add to their library the way the holiday hub's picks are added (title,
year and creator only); visitors keep it in their browser-only guest list.

A door counts as open from midnight on its date in the earliest time zone on
Earth (UTC+14), so the server never hides a door from someone whose day has
started. The page then keeps doors whose date hasn't reached the reader's own
time zone closed, which is the one reader it can see.

Before opening day the page is a 404 for everyone except site admins, who get a
noindex preview with every door open. ``ADVENT_CALENDAR_OPENS`` (YYYY-MM-DD)
moves the day door 1 opens, and the other doors follow a day apart, so the
calendar can be tried on the live site without a code change.

What is stored, all in new tables: the doors a member opened (``AdventDoor``,
for their own progress and the Door Opener badge) and whether they asked for a
morning reminder (``AdventReminder``). Library state is read from the library
each time.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import in_order, models, seasonal, title_pages
from .advent_calendar_data import EDITIONS

BASE_PATH = "/holidays/advent-calendar"
SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
DOORS = 24
# The earliest time zone (Kiribati's Line Islands): a door is open somewhere once its date starts there.
EARLIEST_OFFSET = timedelta(hours=14)
# The dashboard card and reminders run from opening day to the end of December.
CARD_LAST_DAY = (12, 31)
# Morning reminders go out from this hour in the member's own time zone.
REMINDER_HOUR = 8
REMINDER_KIND = "advent_door"
DEFAULT_ZONE = "America/New_York"
PER_RUN_LIMIT = 500


def _now() -> datetime:
    return datetime.utcnow()


def earliest_today(now: Optional[datetime] = None) -> date:
    """The latest date anywhere on Earth right now."""
    return ((now or _now()) + EARLIEST_OFFSET).date()


def opens(year: int) -> date:
    """The day door 1 opens: December 1, unless ADVENT_CALENDAR_OPENS moves it within the same year."""
    configured = os.getenv("ADVENT_CALENDAR_OPENS", "").strip()
    if configured:
        try:
            moved = date.fromisoformat(configured)
            if moved.year == year:
                return moved
        except ValueError:
            pass
    return date(year, 12, 1)


def door_date(year: int, day: int) -> date:
    return opens(year) + timedelta(days=day - 1)


def edition(year: int) -> Optional[dict]:
    return EDITIONS.get(year)


def is_public(year: int, now: Optional[datetime] = None) -> bool:
    return year in EDITIONS and earliest_today(now) >= opens(year)


def current_year(now: Optional[datetime] = None) -> Optional[int]:
    """The newest edition that has opened."""
    public = [year for year in EDITIONS if is_public(year, now)]
    return max(public) if public else None


def unlocked(year: int, now: Optional[datetime] = None, preview: bool = False) -> list[int]:
    """The days whose door has opened somewhere; every day for an admin preview."""
    if year not in EDITIONS:
        return []
    if preview:
        return list(range(1, DOORS + 1))
    today = earliest_today(now)
    return [day for day in range(1, DOORS + 1) if door_date(year, day) <= today]


def path(year: Optional[int] = None) -> str:
    return BASE_PATH


def door_path(year: int, day: int) -> str:
    return f"{BASE_PATH}/{year}/{day}"


def door_anchor(day: int) -> str:
    return f"door-{day}"


def doors(year: int) -> list[dict]:
    return EDITIONS[year]["doors"]


def door(year: int, day: int) -> Optional[dict]:
    if year not in EDITIONS or not 1 <= day <= DOORS:
        return None
    return doors(year)[day - 1]


def entry_for(item: dict) -> dict:
    """A door's pick in the shape saving uses (pick.add_to_library or browse.add_to_library)."""
    year = item["year"]
    slug = title_pages.title_slug(item["title"], year)
    found = {"id": f"{item['kind']}/{slug}", "kind": item["kind"], "slug": slug, "title": item["title"],
             "year": year, "creator": item.get("creator"), "extra": {}}
    if item["kind"] in seasonal.EXTRA_KINDS:
        found["browse_kind"] = seasonal.EXTRA_KINDS[item["kind"]]
    return found


def find(kind: str, slug: str, now: Optional[datetime] = None) -> Optional[dict]:
    """For the saved-before-sign-up import: the entry of an opened door's pick, if one matches."""
    for year in EDITIONS:
        if not is_public(year, now):
            continue
        for day in unlocked(year, now):
            found = entry_for(door(year, day))
            if found["kind"] == kind and found["slug"] == slug:
                return found
    return None


# ---------------------------------------------------------------- a member's calendar

def opened_days(db: Session, user_id: int, year: int) -> list[int]:
    rows = db.query(models.AdventDoor.day).filter(models.AdventDoor.user_id == user_id,
                                                  models.AdventDoor.year == year).all()
    return sorted(day for (day,) in rows)


def open_doors(db: Session, user_id: int, year: int, days, allowed: list[int]) -> list[int]:
    """Record doors as opened (only ones already unlocked). Returns the days that were new. Commits."""
    have = set(opened_days(db, user_id, year))
    fresh = sorted({day for day in days if day in allowed and day not in have})
    if not fresh:
        return []
    now = _now()
    for day in fresh:
        db.add(models.AdventDoor(user_id=user_id, year=year, day=day, opened_at=now))
    try:
        db.commit()
    except IntegrityError:
        # A second tab opened one of the same doors first; keep the rest.
        db.rollback()
        added = []
        for day in fresh:
            if day in set(opened_days(db, user_id, year)):
                continue
            db.add(models.AdventDoor(user_id=user_id, year=year, day=day, opened_at=now))
            try:
                db.commit()
                added.append(day)
            except IntegrityError:
                db.rollback()
        return added
    return fresh


def most_doors(db: Session, user_id: int) -> int:
    """The most doors the member opened in any one year (what the Door Opener badge counts)."""
    counts = db.query(func.count(models.AdventDoor.id)).filter(
        models.AdventDoor.user_id == user_id).group_by(models.AdventDoor.year).all()
    return max((int(count) for (count,) in counts), default=0)


def library(db: Session, user_id: int, year: int, days: list[int]) -> dict[int, dict]:
    """{day: {"state": "done" | "tracked", "library_url"}} for opened-door picks already in the library."""
    if not days:
        return {}
    items = []
    for day in days:
        item = door(year, day)
        items.append({"id": str(day), "kind": item["kind"], "title": item["title"], "year": item["year"]})
    matchable = {"entries": items}
    found = in_order.library_matches(db, user_id, matchable)
    found.update(seasonal._extra_matches(db, user_id, matchable))
    return {int(key): value for key, value in found.items()}


def reminder(db: Session, user_id: int, year: int) -> Optional[models.AdventReminder]:
    return db.query(models.AdventReminder).filter_by(user_id=user_id, year=year).first()


def set_reminder(db: Session, user_id: int, year: int, on: bool, now: Optional[datetime] = None) -> bool:
    """Turn the morning reminder on or off. Turning it on never re-announces a door that is already open."""
    row = reminder(db, user_id, year)
    if not on:
        if row is not None:
            db.delete(row)
            db.commit()
        return False
    if row is None:
        pref = db.query(models.PushPreference).filter_by(user_id=user_id).first()
        already = [day for day in unlocked(year, now) if door_date(year, day) <= _local_today(pref, now)]
        db.add(models.AdventReminder(user_id=user_id, year=year, last_day=max(already, default=0)))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return True


# ---------------------------------------------------------------- morning reminders

def _zone(pref: Optional[models.PushPreference]) -> ZoneInfo:
    from . import web_push
    return web_push.zone(pref.time_zone if pref else None) or ZoneInfo(DEFAULT_ZONE)


def _local(pref: Optional[models.PushPreference], now: datetime) -> datetime:
    return now.replace(tzinfo=ZoneInfo("UTC")).astimezone(_zone(pref))


def _local_today(pref: Optional[models.PushPreference], now: Optional[datetime] = None) -> date:
    return _local(pref, now or _now()).date()


def reminder_message(year: int, day: int) -> str:
    item = door(year, day)
    left = DOORS - day
    tail = "The last door is open." if left == 0 else f"{left} to go."
    return f"Door {day} is open: {item['hint']}. {tail}"


def send_reminders(db: Session, http=None, now: Optional[datetime] = None) -> dict:
    """One push a morning, in the member's time zone, when that day's door opens. Returns counts.

    Only members who asked for it on the calendar page and have a device. Quiet hours
    hold it back until the next hourly run. The message repeats the door's hint and
    never names the pick.
    """
    from . import web_push
    now = now or _now()
    stats = {"sent": 0, "members": 0, "waiting": 0}
    for year in EDITIONS:
        if not is_public(year, now) or earliest_today(now) > date(year, *CARD_LAST_DAY) + timedelta(days=1):
            continue
        # Nobody can be owed a door that hasn't opened anywhere yet, so members already told
        # about the newest door are left out of the query instead of being read every hour.
        newest = len(unlocked(year, now))
        after = 0
        while True:
            # In pages by id: a fixed first page would keep the same members (say, ones still
            # waiting for 8am) at the front, and nobody after them would ever be reminded.
            rows = (db.query(models.AdventReminder.id, models.AdventReminder.user_id, models.AdventReminder.last_day)
                    .filter(models.AdventReminder.year == year, models.AdventReminder.last_day < newest,
                            models.AdventReminder.id > after)
                    .order_by(models.AdventReminder.id).limit(PER_RUN_LIMIT).all())
            if not rows:
                break
            after = rows[-1].id
            prefs = {pref.user_id: pref for pref in db.query(models.PushPreference).filter(
                models.PushPreference.user_id.in_([row.user_id for row in rows])).all()}
            for pref in prefs.values():
                # Only read from here on. Detached, a commit below doesn't expire them and
                # cost one reload per member for the time zone and quiet hours.
                db.expunge(pref)
            for row in rows:
                pref = prefs.get(row.user_id)
                local = _local(pref, now)
                due = [day for day in range(row.last_day + 1, DOORS + 1) if door_date(year, day) <= local.date()]
                if not due:
                    continue
                day = due[-1]
                if door_date(year, day) != local.date():
                    # A door from an earlier day that was never announced (the member was away): skip it quietly.
                    db.query(models.AdventReminder).filter(
                        models.AdventReminder.id == row.id, models.AdventReminder.last_day < day,
                    ).update({"last_day": day}, synchronize_session=False)
                    db.commit()
                    continue
                if local.hour < REMINDER_HOUR or web_push.in_quiet_hours(pref, now):
                    stats["waiting"] += 1
                    continue
                # Recorded before sending, so a second worker running at the same moment doesn't send a twin.
                claimed = (db.query(models.AdventReminder)
                           .filter(models.AdventReminder.id == row.id, models.AdventReminder.last_day < day)
                           .update({"last_day": day}, synchronize_session=False))
                db.commit()
                if not claimed:
                    continue
                link = f"{BASE_PATH}?utm_source=push&utm_campaign=advent#{door_anchor(day)}"
                delivered = web_push.deliver(db, [(row.user_id, REMINDER_KIND, reminder_message(year, day), link)],
                                             http=http, now=now)
                stats["sent"] += delivered["sent"]
                stats["members"] += 1
            if len(rows) < PER_RUN_LIMIT:
                break
    return stats


# ---------------------------------------------------------------- the dashboard card

def card(db: Session, user: models.User, now: Optional[datetime] = None) -> dict:
    """What the dashboard card needs: the open doors with their hints, and which the member opened.

    {"show": False} outside the calendar's run. The card picks "today's door" in the
    member's own time zone, so it lists every door open anywhere on Earth.
    """
    now = now or _now()
    year = current_year(now)
    if year is None or earliest_today(now) > date(year, *CARD_LAST_DAY):
        return {"show": False}
    return {
        "show": True, "year": year, "page": BASE_PATH, "total": DOORS,
        "doors": [{"day": day, "date": door_date(year, day).isoformat(), "hint": door(year, day)["hint"]}
                  for day in unlocked(year, now)],
        "opened_days": opened_days(db, user.id, year),
    }
