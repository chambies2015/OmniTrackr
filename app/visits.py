"""One visit day per member per UTC day.

Sign-in sessions last 30 days, so most returning members never log in again and
the last log-in time alone says little about who comes back. This keeps one more
minimal signal on the users row: the last day the member opened OmniTrackr while
signed in, and how many different days they have. No page history is stored.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func, or_, update
from sqlalchemy.orm import Session

from . import models

WELCOME_BACK_MIN_DAYS = 3


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def last_active_on(user: models.User) -> Optional[date]:
    """The later of the last visit day and the last log-in."""
    days = [d for d in (user.last_seen_on, user.last_login_at.date() if user.last_login_at else None) if d]
    return max(days) if days else None


def mark_login(user: models.User, now: datetime) -> None:
    """Count a log-in as a visit (the caller commits)."""
    today = now.date()
    if user.last_seen_on is None or user.last_seen_on < today:
        user.visit_days = (user.visit_days or 0) + 1
        user.last_seen_on = today


def record_visit(db: Session, user: models.User, today: Optional[date] = None) -> Optional[int]:
    """Mark today as a visit day.

    Returns the number of days since the previous visit day when this is the
    member's first visit today and an earlier visit day is known, else None.
    Uses a conditional update so two tabs opening at once count one day.
    """
    today = today or today_utc()
    previous = user.last_seen_on
    if previous is not None and previous >= today:
        return None
    result = db.execute(
        update(models.User)
        .where(models.User.id == user.id,
               or_(models.User.last_seen_on.is_(None), models.User.last_seen_on < today))
        .values(last_seen_on=today, visit_days=func.coalesce(models.User.visit_days, 0) + 1)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    db.refresh(user)
    if not result.rowcount or previous is None:
        return None
    return (today - previous).days

