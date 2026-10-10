"""Yearly goals: a member's private targets, e.g. finish 24 books this year.

Progress is counted from the same finishes Year in Review uses (journal
"finished" entries and completion moments), so it can never drift from the
recap. Goals are private: only the member sees them, unless they share their
recap, which then shows the goals for the categories it already shows.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from . import models, year_in_review

ALL = "all"
# Goal category -> (singular, plural) noun for "12 of 24 books".
NOUNS = {
    ALL: ("title", "titles"),
    "movies": ("movie", "movies"),
    "tv-shows": ("TV show", "TV shows"),
    "anime": ("anime", "anime"),
    "video-games": ("game", "games"),
    "music": ("album", "albums"),
    "books": ("book", "books"),
}
ORDER = list(NOUNS)
MAX_TARGET = 1000


def allowed_years(today: Optional[date] = None) -> list[int]:
    """This year, plus next year so goals can be set ahead (in December, for instance)."""
    today = today or datetime.utcnow().date()
    return [today.year, today.year + 1]


def validate(year: int, category: str, target: int, today: Optional[date] = None) -> None:
    if year not in allowed_years(today):
        raise ValueError("Goals can be set for this year or next year.")
    if category not in NOUNS:
        raise ValueError("Unknown goal category.")
    if not isinstance(target, int) or not 1 <= target <= MAX_TARGET:
        raise ValueError(f"Pick a number from 1 to {MAX_TARGET}.")


def save(db: Session, user_id: int, year: int, category: str, target: int,
         today: Optional[date] = None) -> models.YearlyGoal:
    validate(year, category, target, today)
    goal = db.query(models.YearlyGoal).filter_by(user_id=user_id, year=year, category=category).first()
    if goal is None:
        goal = models.YearlyGoal(user_id=user_id, year=year, category=category, target=target)
        db.add(goal)
    else:
        goal.target = target
    db.commit()
    return goal


def remove(db: Session, user_id: int, year: int, category: str) -> bool:
    goal = db.query(models.YearlyGoal).filter_by(user_id=user_id, year=year, category=category).first()
    if goal is None:
        return False
    db.delete(goal)
    db.commit()
    return True


def _pace(done: int, target: int, year: int, today: date, set_on: Optional[date] = None) -> dict:
    """Where the member would be by now if they spread the goal evenly from the day they set it.

    Pace starts on January 1, or on the day the goal was set if that is later, so a
    goal set in October is not "behind" on day one. Earlier finishes still count.
    """
    if done >= target:
        return {"status": "done", "difference": done - target}
    start, end = date(year, 1, 1), date(year + 1, 1, 1)
    if set_on and start < set_on < end:
        start = set_on
    if today < start:
        status = "not_started" if today < date(year, 1, 1) else "on_track"
        return {"status": status, "difference": 0}
    elapsed = min((today - start).days + 1, (end - start).days)
    expected = target * elapsed / (end - start).days
    difference = round(done - expected)
    if difference >= 1:
        return {"status": "ahead", "difference": difference}
    if difference <= -max(1, round(target * 0.1)):
        return {"status": "behind", "difference": -difference}
    return {"status": "on_track", "difference": 0}


def describe(goal: dict) -> str:
    """'12 of 24 books, 2 ahead of pace' as plain text (used by the email)."""
    singular, plural = NOUNS[goal["category"]]
    noun = singular if goal["target"] == 1 else plural
    head = f"{goal['done']} of {goal['target']} {noun}"
    pace = goal["pace"]
    if pace["status"] == "done":
        return f"{head}, goal reached"
    if pace["status"] == "ahead":
        return f"{head}, {pace['difference']} ahead of pace"
    if pace["status"] == "behind":
        return f"{head}, {pace['difference']} behind pace"
    if pace["status"] == "on_track":
        return f"{head}, on pace"
    return head


def progress(db: Session, user: models.User, year: int, *, today: Optional[date] = None,
             categories: Optional[list[str]] = None, counts: Optional[dict] = None) -> list[dict]:
    """The member's goals for the year with progress. ``categories`` limits which goals are listed."""
    today = today or datetime.utcnow().date()
    rows = db.query(models.YearlyGoal).filter_by(user_id=user.id, year=year).all()
    if categories is not None:
        rows = [row for row in rows if row.category in categories]
    if not rows:
        return []
    if counts is None:
        counts = year_in_review.finished_counts(db, user.id, year)
    goals = []
    for row in sorted(rows, key=lambda row: ORDER.index(row.category) if row.category in ORDER else len(ORDER)):
        if row.category not in NOUNS:
            continue
        done = sum(counts.values()) if row.category == ALL else counts.get(row.category, 0)
        singular, plural = NOUNS[row.category]
        goal = {
            "category": row.category, "target": row.target, "done": done,
            "percent": min(100, round(done * 100 / row.target)) if row.target else 0,
            "noun": singular if row.target == 1 else plural,
            "pace": _pace(done, row.target, year, today, row.created_at.date() if row.created_at else None),
        }
        goal["summary"] = describe(goal)
        goals.append(goal)
    return goals


def payload(db: Session, user: models.User, year: int, today: Optional[date] = None) -> dict:
    today = today or datetime.utcnow().date()
    return {
        "year": year,
        "years": allowed_years(today),
        "goals": progress(db, user, year, today=today),
        "categories": [{"key": key, "noun": NOUNS[key][1]} for key in ORDER],
        "max_target": MAX_TARGET,
    }


def public_categories(user: models.User) -> list[str]:
    """Goals a shared recap may show: visible categories, and the overall goal only when nothing is private."""
    visible = year_in_review._visible(user, True)
    shown = [key for key in ORDER if key in visible]
    if len(visible) == len(year_in_review.CATEGORIES):
        shown.insert(0, ALL)
    return shown
