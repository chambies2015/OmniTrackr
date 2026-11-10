"""The New Year challenge: a member pledges yearly goals for the coming year (Nov 2026).

A pledge is a thin layer over yearly goals (app/goals.py). The targets are
ordinary ``YearlyGoal`` rows, so the dashboard goals card, the weekly email and
Year in Review keep working exactly as before. The ``YearPledge`` row only
records that the member signed up for the challenge and, while they share it,
the token for the public pledge card.

Each edition opens on December 1 of the year before, so members can plan with
a full year's finishes in front of them. Before that the page is visible only
to site admins (a preview). ``NEW_YEAR_CHALLENGE_OPENS`` (YYYY-MM-DD) moves the
opening day of the next edition without a code change.

Public pages show aggregate numbers only once at least ``MIN_PUBLIC_COUNT``
members have pledged, and a shared pledge shows only goals for shelves the
member keeps public.
"""
from __future__ import annotations

import os
import secrets
import statistics
from datetime import date, datetime
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import goals, models, time_spent, year_in_review

SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
BASE_PATH = "/new-year-challenge"
MIN_PUBLIC_COUNT = 3
# The dashboard card runs from opening day to the end of January.
CARD_LAST_MONTH = 1
# Editions with a written guide. The page for any other year is a 404.
EDITIONS = {
    2027: {"published": "2026-12-01"},
}
# Typical hours one finished title takes, from the defaults time_spent.py uses
# when a title's own length is unknown. The overall "any kind" goal has none.
HOURS = {
    "movies": time_spent.MOVIE_MINUTES / 60,
    "tv-shows": time_spent.TV_EPISODE_MINUTES * time_spent.TV_EPISODES / 60,
    "anime": time_spent.ANIME_EPISODE_MINUTES * time_spent.ANIME_EPISODES / 60,
    "video-games": float(time_spent.GAME_HOURS),
    "music": time_spent.ALBUM_MINUTES / 60,
    "books": time_spent.BOOK_PAGES * time_spent.MINUTES_PER_PAGE / 60,
    "manga": time_spent.MANGA_CHAPTER_MINUTES * time_spent.MANGA_CHAPTERS / 60,
    "podcasts": time_spent.PODCAST_EPISODE_MINUTES * time_spent.PODCAST_EPISODES / 60,
    "audiobooks": float(time_spent.AUDIOBOOK_HOURS),
}
# What one title means for the hours estimate, in the words the page uses.
HOURS_BASIS = {
    "movies": "a two-hour film",
    "tv-shows": "a ten-episode season of 42-minute episodes",
    "anime": "a 12-episode cour",
    "video-games": "a 20-hour game",
    "music": "a 45-minute album",
    "books": "a 320-page book at about 40 pages an hour",
    "manga": "a 50-chapter series",
    "podcasts": "ten 45-minute episodes",
    "audiobooks": "a ten-hour audiobook",
}
# Never project from fewer days of tracking than this: a new member's first weeks are often
# a backlog being marked finished, which says little about a normal year.
MIN_PROJECTION_DAYS = 60
# And never suggest more than double what the member actually finished.
MAX_PROJECTION_SCALE = 2.0


def _today() -> date:
    return datetime.utcnow().date()


def opens(year: int) -> date:
    """Opening day for an edition: December 1 of the year before, unless the env var moves it."""
    configured = os.getenv("NEW_YEAR_CHALLENGE_OPENS", "").strip()
    if configured:
        try:
            moved = date.fromisoformat(configured)
            if moved.year in (year - 1, year):
                return moved
        except ValueError:
            pass
    return date(year - 1, 12, 1)


def is_open(year: int, today: Optional[date] = None) -> bool:
    """Pledges for ``year`` are taken from opening day to December 31 of that year."""
    today = today or _today()
    return year in EDITIONS and opens(year) <= today <= date(year, 12, 31)


def has_started(year: int, today: Optional[date] = None) -> bool:
    return (today or _today()) >= date(year, 1, 1)


def is_public(year: int, today: Optional[date] = None) -> bool:
    """The guide is public from opening day on, and stays up as an archive after the year ends."""
    return year in EDITIONS and (today or _today()) >= opens(year)


def current_year(today: Optional[date] = None) -> Optional[int]:
    """The edition the site points at: next year's from its opening day, otherwise this year's."""
    today = today or _today()
    for year in (today.year + 1, today.year):
        if is_public(year, today):
            return year
    public = [year for year in EDITIONS if is_public(year, today)]
    return max(public) if public else None


def card_year(today: Optional[date] = None) -> Optional[int]:
    """The edition the dashboard card promotes: from opening day to the end of January."""
    today = today or _today()
    year = today.year + 1 if today.month >= 11 else today.year
    if year not in EDITIONS or today < opens(year):
        return None
    if today.year == year and today.month > CARD_LAST_MONTH:
        return None
    return year


def path(year: int) -> str:
    return f"{BASE_PATH}/{year}"


def days_until_start(year: int, today: Optional[date] = None) -> int:
    return max(0, (date(year, 1, 1) - (today or _today())).days)


# ---------------------------------------------------------------- hours

def weekly_hours(targets: dict) -> float:
    """Typical hours a week the targets add up to, spread over 52 weeks."""
    total = sum(HOURS[key] * value for key, value in targets.items() if key in HOURS and value)
    return round(total / 52, 1)


def hours_label(hours: float) -> str:
    if hours <= 0:
        return ""
    if hours < 1:
        minutes = max(5, int(round(hours * 60 / 5.0)) * 5)
        return f"about {minutes} minutes a week"
    whole = round(hours * 2) / 2
    shown = int(whole) if whole == int(whole) else whole
    return f"about {shown} hour{'' if shown == 1 else 's'} a week"


# ---------------------------------------------------------------- suggestions

def _half_up(value: float) -> int:
    """Round halves up (Python's round() sends 22.5 to 22), so the presets match what people expect."""
    return int(value + 0.5)


def _tracking_start(user: models.User, year: int) -> date:
    start = date(year, 1, 1)
    joined = user.created_at.date() if getattr(user, "created_at", None) else start
    return max(start, joined)


def suggestions(db: Session, user: models.User, year: int, today: Optional[date] = None) -> dict:
    """Starting points from the year before the edition: last year's count and three presets.

    When the year before is still running (December), the count is projected to a
    full year from the member's pace since the year began or since they joined,
    whichever is later. Too little history means no projection, only the count.
    """
    today = today or _today()
    last_year = year - 1
    counts = year_in_review.finished_counts(db, user.id, last_year)
    end = min(today, date(last_year, 12, 31))
    start = _tracking_start(user, last_year)
    tracked_days = (end - start).days + 1
    full_year = (date(last_year, 12, 31) - date(last_year, 1, 1)).days + 1
    scale = None
    if tracked_days >= MIN_PROJECTION_DAYS:
        scale = min(MAX_PROJECTION_SCALE, full_year / tracked_days)
    rows = {}
    for key in goals.ORDER:
        if key == goals.ALL:
            done = sum(counts.values())
        else:
            done = counts.get(key, 0)
        if done <= 0:
            continue
        projected = min(goals.MAX_TARGET, max(done, _half_up(done * scale))) if scale else done
        keep = max(1, projected)
        more = min(goals.MAX_TARGET, max(keep + 1, _half_up(keep * 1.25)))
        stretch = min(goals.MAX_TARGET, max(more + 1, _half_up(keep * 1.5)))
        rows[key] = {"done": done, "projected": projected, "keep": keep, "more": more, "stretch": stretch}
    return {
        "year": last_year,
        "partial": end < date(last_year, 12, 31),
        "projected": scale is not None and scale > 1.01,
        "since": start.isoformat(),
        "categories": rows,
    }


# ---------------------------------------------------------------- pledges

def get(db: Session, user_id: int, year: int) -> Optional[models.YearPledge]:
    return db.query(models.YearPledge).filter_by(user_id=user_id, year=year).first()


def _clean_targets(raw: dict) -> dict:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("Pick at least one goal.")
    cleaned = {}
    for key, value in raw.items():
        if key not in goals.NOUNS:
            raise ValueError("Unknown goal category.")
        if value in (None, 0, ""):
            cleaned[key] = None
            continue
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= goals.MAX_TARGET:
            raise ValueError(f"Pick a number from 1 to {goals.MAX_TARGET}.")
        cleaned[key] = value
    return cleaned


def pledge(db: Session, user: models.User, year: int, targets: dict,
           today: Optional[date] = None, preview: bool = False) -> tuple[models.YearPledge, bool]:
    """Save the member's goals for ``year`` and sign them up. Returns (pledge, newly made).

    ``targets`` maps a goal category to a number, or to None/0 to drop that goal.
    Categories left out are not touched, so a goal set from the dashboard stays.
    """
    today = today or _today()
    if not (is_open(year, today) or (preview and year in EDITIONS)):
        raise ValueError("Pledges for that year aren't open.")
    cleaned = _clean_targets(targets)
    for key, value in cleaned.items():
        if value is not None:
            goals.validate(year, key, value, today)
    existing = {row.category: row for row in db.query(models.YearlyGoal).filter_by(user_id=user.id, year=year).all()}
    remaining = {key for key in existing if cleaned.get(key, existing[key].target) is not None}
    remaining |= {key for key, value in cleaned.items() if value is not None}
    if not remaining:
        raise ValueError("Pick at least one goal.")
    for key, value in cleaned.items():
        if value is None:
            if key in existing:
                goals.remove(db, user.id, year, key)
        else:
            goals.save(db, user.id, year, key, value, today)
    row = get(db, user.id, year)
    if row is not None:
        row.updated_at = datetime.utcnow()
        db.commit()
        return row, False
    row = models.YearPledge(user_id=user.id, year=year)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return get(db, user.id, year), False
    return row, True


def leave(db: Session, user_id: int, year: int) -> bool:
    """Leave the challenge. The goals stay: they belong to the member, not to the challenge."""
    row = get(db, user_id, year)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def share(db: Session, row: models.YearPledge) -> models.YearPledge:
    if not row.share_token:
        row.share_token = secrets.token_urlsafe(12)
        db.commit()
    return row


def unshare(db: Session, row: models.YearPledge) -> models.YearPledge:
    row.share_token = None
    db.commit()
    return row


def share_path(row: models.YearPledge) -> str:
    return f"/pledge/{row.share_token}"


def find_shared(db: Session, token: str) -> Optional[models.YearPledge]:
    """A shared pledge whose owner is active; otherwise None. Public goals are checked by the caller."""
    if not token or len(token) > 32:
        return None
    row = db.query(models.YearPledge).filter(models.YearPledge.share_token == token).first()
    if row is None:
        return None
    owner = db.get(models.User, row.user_id)
    if owner is None or not owner.is_active:
        return None
    return row


def public_goals(db: Session, owner: models.User, year: int, today: Optional[date] = None) -> list[dict]:
    """The goals a shared pledge may show: only shelves the member keeps public."""
    return goals.progress(db, owner, year, today=today or _today(), categories=goals.public_categories(owner))


def payload(db: Session, user: models.User, year: int, today: Optional[date] = None,
            preview: bool = False) -> dict:
    today = today or _today()
    row = get(db, user.id, year)
    goal_rows = goals.progress(db, user, year, today=today)
    targets = {goal["category"]: goal["target"] for goal in goal_rows}
    weekly = weekly_hours(targets)
    return {
        "year": year,
        "open": is_open(year, today) or (preview and year in EDITIONS),
        "started": has_started(year, today),
        "days_until_start": days_until_start(year, today),
        "pledged": row is not None,
        "pledged_at": row.created_at.isoformat() if row is not None and row.created_at else None,
        "shared": bool(row and row.share_token),
        "url": SITE_URL + share_path(row) if row is not None and row.share_token else None,
        "goals": goal_rows,
        "reached": sum(1 for goal in goal_rows if goal["pace"]["status"] == "done"),
        "weekly_hours": weekly,
        "weekly_label": hours_label(weekly),
        "suggestions": suggestions(db, user, year, today),
        "categories": [{"key": key, "noun": goals.NOUNS[key][1], "singular": goals.NOUNS[key][0],
                        "hours": round(HOURS.get(key, 0), 2)} for key in goals.ORDER],
        "max_target": goals.MAX_TARGET,
        "page": path(year),
    }


def card_payload(db: Session, user: models.User, today: Optional[date] = None) -> dict:
    """The dashboard card: hidden outside the window, otherwise the member's pledge in brief."""
    today = today or _today()
    year = card_year(today)
    if year is None:
        return {"show": False}
    row = get(db, user.id, year)
    count = 0
    if row is not None:
        count = db.query(models.YearlyGoal).filter_by(user_id=user.id, year=year).count()
    return {
        "show": True,
        "year": year,
        "pledged": row is not None,
        "goals": count,
        "started": has_started(year, today),
        "days_until_start": days_until_start(year, today),
        "shared": bool(row and row.share_token),
        "url": SITE_URL + share_path(row) if row is not None and row.share_token else None,
        "page": path(year),
    }


# ---------------------------------------------------------------- public numbers

def public_counts(db: Session, year: int) -> dict:
    """Aggregate pledge numbers for the guide. Nothing below the floor is shown."""
    rows = (db.query(models.YearPledge.user_id)
            .join(models.User, models.User.id == models.YearPledge.user_id)
            .filter(models.YearPledge.year == year, models.User.is_active.is_(True))
            .all())
    members = [user_id for (user_id,) in rows]
    result = {"pledged": len(members), "show": len(members) >= MIN_PUBLIC_COUNT, "categories": [], "titles": 0}
    if not result["show"]:
        return result
    goal_rows = (db.query(models.YearlyGoal.category, models.YearlyGoal.target)
                 .filter(models.YearlyGoal.year == year, models.YearlyGoal.user_id.in_(members))
                 .all())
    by_category: dict[str, list[int]] = {}
    for category, target in goal_rows:
        if category in goals.NOUNS:
            by_category.setdefault(category, []).append(target)
    result["titles"] = sum(target for category, target in goal_rows if category != goals.ALL)
    for key in goals.ORDER:
        values = by_category.get(key, [])
        if len(values) < MIN_PUBLIC_COUNT:
            continue
        median = int(round(statistics.median(values)))
        singular, plural = goals.NOUNS[key]
        result["categories"].append({
            "key": key, "members": len(values), "median": median,
            "noun": singular if median == 1 else plural,
        })
    result["categories"].sort(key=lambda item: (-item["members"], goals.ORDER.index(item["key"])))
    return result


def headline(username: str, year: int) -> str:
    return f"{username}'s {year} challenge"
