"""Gentle "support OmniTrackr" notes at good moments, and the counters that show whether they work.

A member sees at most one note every couple of months, only after something worth marking: a yearly
goal reached, a library milestone, a run of visits, an anniversary, or supporter perks that just ran
out. Nobody sees one in their first three weeks, active supporters never do, "Not now" waits four
months, and "Don't ask again" stops them for good (Settings → Supporter turns them back on).

Counters go into ``site_traffic_daily`` under kind "support" through the same buffer as page views:
how often each moment was shown and how members answered, where /supporters visitors came from,
which Ko-fi button on the page they pressed, and how many Ko-fi presses turned into a linked payment
within two weeks. None of them names a member.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models, supporters

# ---------------------------------------------------------------- rules

NEW_ACCOUNT = timedelta(days=21)       # nobody is asked in their first three weeks
MIN_VISIT_DAYS = 5                     # ...or before they've come back a few times
COOLDOWN = timedelta(days=60)          # one note every two months at most
OPEN_FOR = timedelta(days=7)           # a note stays on the dashboard for a week unless answered
LATER = timedelta(days=120)            # "Not now"
AFTER_KOFI = timedelta(days=90)        # pressed Ko-fi but no payment linked
GOAL_FRESH = timedelta(days=14)        # a goal reached in the last two weeks
ANNIVERSARY_FRESH = timedelta(days=30)
LAPSE_FRESH = timedelta(days=30)       # perks that ended in the last month
CONVERSION_WINDOW = timedelta(days=14)

TITLE_STEPS = (100, 250, 500, 1000, 2500, 5000)
DAY_STEPS = (30, 100, 200, 365, 500, 1000)

# The moments in the order they're picked, with Site stats labels.
MOMENTS = {
    "ended": "Supporter perks just ended",
    "goal": "Yearly goal reached",
    "titles": "Library milestone",
    "days": "Days opened milestone",
    "years": "Anniversary",
}
ANSWERS = {"kofi": "Ko-fi pressed", "perks": "Opened the supporters page", "later": "Not now", "stop": "Don't ask again"}
# Where a /supporters visit came from: ?from= on our own links, else same site or outside.
PAGE_SOURCES = {
    "ask": "Dashboard note", "email": "Weekly email", "recap": "Year in Review", "settings": "Settings → Supporter",
    "footer": "Site footer", "site": "Another OmniTrackr page", "outside": "Outside link or typed in",
}
# Ko-fi buttons on /supporters.
PAGE_PLACES = {
    "hero": "Top of the page", "coffee": "One-time coffee card", "popcorn": "Popcorn tier", "season_pass": "Season Pass tier",
    "directors_cut": "Director's Cut tier", "how": "How it works", "sticky": "Phone bar at the bottom", "faq": "Questions",
}
SOURCE_RE = re.compile(r"^[a-z_]{1,16}$")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def count(key: str) -> bool:
    """Add 1 to a "support" counter for today. Never raises: counting must not break a page."""
    try:
        from .site_traffic import RECORDER
        if not RECORDER.enabled or len(key) > 60:
            return False
        day = datetime.now(timezone.utc).date()
        with RECORDER._lock:
            RECORDER._pending[(day, "support", key)] += 1
            RECORDER._events += 1
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- money words

def coffee_line() -> str:
    """What a $3 coffee does, from KOFI_MONTHLY_COSTS when it's set."""
    total = sum(item["amount"] for item in supporters.monthly_costs())
    if total <= 0:
        return "Every $3 coffee goes straight to the server bill."
    if total <= 3:
        return "One $3 coffee covers a whole month of hosting."
    days = 3 * 30 / total
    if days < 1:
        hours = max(1, round(days * 24))
        return f"A $3 coffee keeps the site up for about {hours} hours."
    days = round(days)
    return f"A $3 coffee keeps the site up for about {days} day{'' if days == 1 else 's'}."


def goal_line(db: Session) -> Optional[dict]:
    progress = supporters.goal_progress(db)
    # Below 5% the meter reads as "nobody pays", which helps no one; the words carry the ask instead.
    if progress is None or progress["percent"] < 5:
        return None
    return {"percent": progress["percent"], "month": progress["month"],
            "text": f"{progress['month']}'s hosting is {progress['percent']}% paid for so far."}


# ---------------------------------------------------------------- picking a moment

def get_row(db: Session, user_id: int) -> Optional[models.SupportAsk]:
    return db.query(models.SupportAsk).filter(models.SupportAsk.user_id == user_id).first()


def _library_size(db: Session, user_id: int) -> int:
    from .badges import LIBRARY
    total = 0
    for model, _flag in LIBRARY.values():
        total += int(db.query(func.count(model.id)).filter(model.user_id == user_id).scalar() or 0)
    return total


def _highest(steps: tuple, value: int) -> int:
    reached = [step for step in steps if value >= step]
    return reached[-1] if reached else 0


def _years(user: models.User, now: datetime) -> tuple[int, Optional[datetime]]:
    """Whole years since the account was made, and that anniversary's date."""
    created = user.created_at
    if created is None:
        return 0, None
    years = now.year - created.year - ((now.month, now.day) < (created.month, created.day))
    if years < 1:
        return 0, None
    try:
        date = created.replace(year=created.year + years)
    except ValueError:  # Feb 29
        date = created.replace(year=created.year + years, day=28)
    return years, date


def _facts(db: Session, user: models.User, now: datetime) -> dict:
    supporter = supporters.get_supporter(db, user.id)
    goal = (db.query(models.GoalAchievement).filter(models.GoalAchievement.user_id == user.id)
            .order_by(models.GoalAchievement.reached_at.desc(), models.GoalAchievement.id.desc()).first())
    years, anniversary = _years(user, now)
    return {"supporter": supporter, "goal": goal, "titles": _library_size(db, user.id),
            "days": int(user.visit_days or 0), "years": years, "anniversary": anniversary}


def eligible(db: Session, user: models.User, row: Optional[models.SupportAsk], now: datetime) -> bool:
    if row is not None and row.stopped_at is not None:
        return False
    if supporters.is_active(supporters.get_supporter(db, user.id), now):
        return False
    created = user.created_at
    if created is None or now - created < NEW_ACCOUNT or int(user.visit_days or 0) < MIN_VISIT_DAYS:
        return False
    if row is not None:
        if row.snoozed_until and row.snoozed_until > now:
            return False
        if row.shown_at and now - row.shown_at < COOLDOWN:
            return False
    return True


def candidate(db: Session, user: models.User, row: Optional[models.SupportAsk], now: datetime) -> Optional[dict]:
    """The moment to mark now, or None. Doesn't record anything."""
    if not eligible(db, user, row, now):
        return None
    facts = _facts(db, user, now)
    done = {
        "titles": row.titles_done if row else 0, "days": row.days_done if row else 0,
        "years": row.years_done if row else 0, "goal": row.goal_done if row else 0,
        "lapse": row.lapse_done if row else None,
    }
    supporter = facts["supporter"]
    if (supporter is not None and supporter.active_until and now - LAPSE_FRESH <= supporter.active_until <= now
            and done["lapse"] != supporter.active_until):
        return {"moment": "ended", "key": f"ended:{supporter.active_until:%Y-%m-%d}", "facts": facts}
    goal = facts["goal"]
    if goal is not None and goal.id > done["goal"] and goal.reached_at and now - goal.reached_at <= GOAL_FRESH:
        return {"moment": "goal", "key": f"goal:{goal.id}", "facts": facts}
    step = _highest(TITLE_STEPS, facts["titles"])
    if step > done["titles"]:
        return {"moment": "titles", "key": f"titles:{step}", "facts": facts}
    step = _highest(DAY_STEPS, facts["days"])
    if step > done["days"]:
        return {"moment": "days", "key": f"days:{step}", "facts": facts}
    if (facts["years"] > done["years"] and facts["anniversary"] is not None
            and now - facts["anniversary"] <= ANNIVERSARY_FRESH):
        return {"moment": "years", "key": f"years:{facts['years']}", "facts": facts}
    return None


# ---------------------------------------------------------------- the words on the card

def _number(value: int) -> str:
    return f"{value:,}"


def copy_for(db: Session, user: models.User, moment: str, key: str, facts: Optional[dict] = None) -> Optional[dict]:
    """Eyebrow, title and body for one moment. Plain text only; the page sets it as textContent."""
    now = _now()
    facts = facts or _facts(db, user, now)
    coffee = coffee_line()
    free = "OmniTrackr is free, with no investors and no paywall. Supporters on Ko-fi pay the server bills."
    try:
        value = int(key.split(":", 1)[1]) if moment in ("titles", "days", "years") else 0
    except (IndexError, ValueError):
        value = 0
    if moment == "ended":
        supporter = facts["supporter"]
        when = f"{supporter.active_until:%B} {supporter.active_until.day}" if supporter and supporter.active_until else "recently"
        return {"eyebrow": "Supporter perks", "title": f"Your perks ended on {when}",
                "body": "Thank you for supporting OmniTrackr. Your theme, color, banner and frame picks are saved, "
                        "so they come straight back if you support again.",
                "action": "Support again"}
    if moment == "goal":
        goal = facts["goal"]
        if goal is None:
            return None
        from .goals import NOUNS, ALL
        singular, plural = NOUNS.get(goal.category, NOUNS[ALL])
        noun = singular if goal.target == 1 else plural
        return {"eyebrow": "Goal reached", "title": f"{_number(goal.target)} {noun} in {goal.year}. Nicely done.",
                "body": f"Every one of them is in your library, counted as you went. {free} {coffee}", "action": "Buy a $3 coffee"}
    if moment == "titles":
        return {"eyebrow": f"{_number(facts['titles'])} titles tracked", "title": f"Your library passed {_number(value)}",
                "body": f"That's a lot of watching, playing, reading and listening, all in one place. {free} {coffee}",
                "action": "Buy a $3 coffee"}
    if moment == "days":
        return {"eyebrow": "Thanks for coming back", "title": f"You've opened OmniTrackr on {_number(value)} different days",
                "body": f"Glad it's part of your routine. {free} {coffee}", "action": "Buy a $3 coffee"}
    if moment == "years":
        joined = user.created_at
        since = f" You joined in {joined:%B} {joined.year}." if joined else ""
        what = "One year" if value == 1 else f"{value} years"
        return {"eyebrow": "Anniversary", "title": f"{what} on OmniTrackr", "body": f"Happy anniversary!{since} {free} {coffee}",
                "action": "Buy a $3 coffee"}
    return None


def payload(db: Session, user: models.User, moment: str, key: str, facts: Optional[dict] = None) -> Optional[dict]:
    words = copy_for(db, user, moment, key, facts)
    if words is None:
        return None
    return {**words, "moment": moment, "key": key, "kofi_url": supporters.KOFI_URL,
            "perks_url": "/supporters?from=ask", "goal": goal_line(db),
            "email_note": "Use the same email on Ko-fi as here and your perks switch on by themselves."}


def current(db: Session, user: models.User, now: Optional[datetime] = None) -> Optional[dict]:
    """The note to show on the dashboard right now: one already open, or a new moment."""
    now = now or _now()
    row = get_row(db, user.id)
    if row is not None and row.stopped_at is None and row.shown_at and row.moment and row.ask_key:
        open_note = (now - row.shown_at < OPEN_FOR and (row.answered_at is None or row.answered_at < row.shown_at))
        if open_note:
            if supporters.is_active(supporters.get_supporter(db, user.id), now):
                return None
            return payload(db, user, row.moment, row.ask_key)
    found = candidate(db, user, row, now)
    if found is None:
        return None
    return payload(db, user, found["moment"], found["key"], found["facts"])


def _row(db: Session, user_id: int) -> models.SupportAsk:
    row = get_row(db, user_id)
    if row is None:
        row = models.SupportAsk(user_id=user_id, shown_count=0, titles_done=0, days_done=0, years_done=0, goal_done=0)
        db.add(row)
        db.flush()
    return row


def mark_shown(db: Session, user: models.User, key: str, now: Optional[datetime] = None) -> bool:
    """The note for ``key`` reached the member's screen. Marks every moment already reached as asked,
    so one note covers them all instead of a run of notes in a row."""
    now = now or _now()
    row = get_row(db, user.id)
    if row is not None and row.ask_key == key and row.shown_at and now - row.shown_at < OPEN_FOR:
        return True  # already counted
    found = candidate(db, user, row, now)
    if found is None or found["key"] != key:
        return False
    row = _row(db, user.id)
    facts = found["facts"]
    row.moment, row.ask_key, row.shown_at = found["moment"], key, now
    row.shown_count = (row.shown_count or 0) + 1
    row.answer = None
    if found["moment"] == "ended":
        row.lapse_done = facts["supporter"].active_until
    row.titles_done = max(row.titles_done or 0, _highest(TITLE_STEPS, facts["titles"]))
    row.days_done = max(row.days_done or 0, _highest(DAY_STEPS, facts["days"]))
    row.years_done = max(row.years_done or 0, facts["years"])
    if facts["goal"] is not None:
        row.goal_done = max(row.goal_done or 0, facts["goal"].id)
    db.commit()
    count(f"ask_shown_{found['moment']}")
    return True


def answer(db: Session, user: models.User, key: str, reply: str, now: Optional[datetime] = None) -> bool:
    """The member pressed a button on the note."""
    if reply not in ANSWERS:
        raise ValueError("Unknown answer")
    now = now or _now()
    row = get_row(db, user.id)
    if row is None or row.ask_key != key or not row.moment:
        return False
    moment = row.moment
    if reply == "perks":
        count(f"ask_perks_{moment}")  # a look at the page leaves the note where it is
        return True
    row.answer, row.answered_at = reply, now
    if reply == "later":
        row.snoozed_until = now + LATER
    elif reply == "stop":
        row.stopped_at = now
    elif reply == "kofi":
        row.snoozed_until = now + AFTER_KOFI
        row.kofi_at, row.kofi_from = now, moment
    db.commit()
    count(f"ask_{reply}_{moment}")
    return True


def set_on(db: Session, user: models.User, on: bool) -> bool:
    row = get_row(db, user.id)
    if on:
        if row is not None and row.stopped_at is not None:
            row.stopped_at = None
            db.commit()
            count("asks_turned_on")
        return True
    row = _row(db, user.id)
    if row.stopped_at is None:
        row.stopped_at = _now()
        db.commit()
        count("asks_turned_off")
    return False


def is_stopped(db: Session, user_id: int) -> bool:
    row = get_row(db, user_id)
    return bool(row and row.stopped_at)


def note_kofi_press(db: Session, user: models.User, place: str) -> None:
    """A signed-in member pressed a Ko-fi button on /supporters: remember it for two weeks."""
    row = _row(db, user.id)
    row.kofi_at, row.kofi_from = _now(), f"page_{place}"[:24]
    db.commit()


def note_support(db: Session, user_id: int) -> None:
    """A Ko-fi payment was just linked to this member. If they pressed one of our Ko-fi buttons in the last
    two weeks, count where. Called inside the linking transaction; never raises."""
    try:
        row = get_row(db, user_id)
        if row is None or row.kofi_at is None:
            return
        if _now() - row.kofi_at <= CONVERSION_WINDOW and row.kofi_from:
            count(f"converted_{row.kofi_from}")
        row.kofi_at = None
    except Exception:
        pass


# ---------------------------------------------------------------- weekly email

EMAIL_EVERY_WEEKS = 6


def email_week(now: datetime) -> int:
    """Weeks counted straight through, so the six-week cycle doesn't jump at New Year like ISO week numbers do."""
    return now.toordinal() // 7


def email_note_due(db: Session, user: models.User, now: datetime) -> bool:
    """A one-line support note in the weekly email about every six weeks, on a different week for each member,
    never to supporters, new members or anyone who turned the notes off."""
    if email_week(now) % EMAIL_EVERY_WEEKS != (user.id + 3) % EMAIL_EVERY_WEEKS:
        return False
    created = user.created_at
    if created is None or now.replace(tzinfo=None) - created < NEW_ACCOUNT:
        return False
    if is_stopped(db, user.id):
        return False
    return not supporters.is_active(supporters.get_supporter(db, user.id), now.replace(tzinfo=None))


def email_note() -> dict:
    return {"text": "OmniTrackr is free and run by one person. Supporters on Ko-fi pay for the servers, "
                    "this email included. " + coffee_line(),
            "path": "/supporters?from=email"}


# ---------------------------------------------------------------- /supporters extras

def member_summary(db: Session, user: models.User) -> dict:
    """What the member has done here, for the line at the top of /supporters."""
    supporter = supporters.get_supporter(db, user.id)
    created = user.created_at
    return {"titles": _library_size(db, user.id), "days": int(user.visit_days or 0),
            "since": f"{created:%B} {created.year}" if created else None,
            "supporter": supporters.is_active(supporter), "past_supporter": bool(supporter and not supporters.is_active(supporter)),
            "asks_off": is_stopped(db, user.id)}


CHANGELOG = Path(__file__).resolve().parent / "templates" / "changelog.html"
_ENTRY = re.compile(r'<h2 id="([a-z0-9-]+)">([A-Z][a-z]+ \d{1,2}, \d{4}): ([^<]+)</h2>')
_SKIP = re.compile(r"security|speed check|second look|sweep", re.IGNORECASE)


@lru_cache(maxsize=1)
def recent_work(limit: int = 6) -> tuple:
    """The newest feature entries from the changelog (security and speed checks left out): (id, date, title)."""
    try:
        text = CHANGELOG.read_text(encoding="utf-8")
    except OSError:
        return ()
    found = []
    for anchor, date, title in _ENTRY.findall(text):
        if _SKIP.search(title):
            continue
        found.append((anchor, date, title.replace("&amp;", "&").replace("&#x27;", "'").replace("&quot;", '"')))
        if len(found) >= limit:
            break
    return tuple(found)


# ---------------------------------------------------------------- Site stats

def stats(db: Session, days: int, now: datetime) -> dict:
    table = models.SiteTrafficDaily
    counts = dict(db.query(table.key, func.sum(table.count)).filter(
        table.kind == "support", table.day >= (now - timedelta(days=days - 1)).date(),
    ).group_by(table.key).all())
    get = lambda key: int(counts.get(key) or 0)  # noqa: E731
    asks = [{"moment": label, "shown": get(f"ask_shown_{key}"),
             **{reply: get(f"ask_{reply}_{key}") for reply in ANSWERS}} for key, label in MOMENTS.items()]
    converted = [{"place": MOMENTS.get(key, key), "count": get(f"converted_{key}")} for key in MOMENTS]
    converted += [{"place": f"Supporters page: {label}", "count": get(f"converted_page_{key}")} for key, label in PAGE_PLACES.items()]
    return {
        "asks": asks,
        "shown": sum(row["shown"] for row in asks),
        "kofi": sum(row["kofi"] for row in asks),
        "later": sum(row["later"] for row in asks),
        "stopped": sum(row["stop"] for row in asks),
        "turned_on": get("asks_turned_on"),
        "asks_off_now": int(db.query(func.count(models.SupportAsk.id)).filter(models.SupportAsk.stopped_at.isnot(None)).scalar() or 0),
        "page_seen": [{"place": label, "count": get(f"page_seen_{key}")} for key, label in PAGE_SOURCES.items()],
        "page_kofi": [{"place": label, "count": get(f"page_kofi_{key}")} for key, label in PAGE_PLACES.items()],
        "converted": [row for row in converted if row["count"]],
        "converted_total": sum(row["count"] for row in converted),
    }
