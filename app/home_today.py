"""What's new for a member since they last opened the home screen (Nov 2026).

The home screen already shows what a member is in the middle of (Continue, Next Up).
This module answers the other question a returning member has: what changed while
I was away? It reads data other features already keep and writes nothing:

* New episodes of the TV shows and anime they haven't finished, from the episode
  schedule cache the private calendar and weekly email use (never the network).
* Releases already announced to them by a release-day alert (``release_alerts``).
* Their friends' latest finishes, ratings and reviews, from the friends feed, which
  applies its own privacy rules.

``since`` comes from the browser (when this device last showed the home screen), so
"new" means new to the person looking, and it is clamped to the last 30 days.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from . import episode_calendar, friend_feed, models, title_pages
from .for_you import IMAGE_FIELD, LABELS
from .user_columns import ensure_loaded

DEFAULT_SINCE = timedelta(days=7)
LONGEST_SINCE = timedelta(days=30)
SHOW_LIMIT = 6
RELEASE_DAYS = 14
RELEASE_LIMIT = 4
FRIEND_LIMIT = 4
VISIBLE_FLAG = {"tv-shows": "tv_shows_visible", "anime": "anime_visible"}


def clamp_since(since: Optional[datetime], now: datetime) -> datetime:
    """A usable "since": naive UTC, not in the future and not more than 30 days back."""
    if since is None:
        return now - DEFAULT_SINCE
    if since.tzinfo is not None:
        since = since.astimezone(timezone.utc).replace(tzinfo=None)
    return max(now - LONGEST_SINCE, min(since, now))


def _checkpoints(db: Session, user_id: int) -> dict[tuple[str, int], tuple[Optional[int], Optional[int]]]:
    rows = db.query(models.ProgressCheckpoint.category, models.ProgressCheckpoint.item_id,
                    models.ProgressCheckpoint.season, models.ProgressCheckpoint.position).filter(
        models.ProgressCheckpoint.user_id == user_id,
        models.ProgressCheckpoint.category.in_(tuple(VISIBLE_FLAG)),
        models.ProgressCheckpoint.position.isnot(None),
    ).all()
    return {(category, item_id): (season, position) for category, item_id, season, position in rows}


def _code(category: str, episode: dict) -> str:
    season = episode.get("season")
    if category == "tv-shows" and season:
        return f"S{season} E{episode['number']}"
    return f"Episode {episode['number']}"


def _behind(category: str, checkpoint, episode: dict) -> Optional[bool]:
    """True when saved progress is before this episode, None when there's no progress to compare."""
    if checkpoint is None:
        return None
    season, position = checkpoint
    if category == "tv-shows" and episode.get("season") and season:
        return (season, position) < (episode["season"], episode["number"])
    return position < episode["number"]


def show_updates(db: Session, user: models.User, today: date, since: datetime) -> list[dict]:
    """One entry per unfinished show with an episode out in the last week or due in the next one."""
    ensure_loaded(user, tuple(VISIBLE_FLAG.values()))
    checkpoints = _checkpoints(db, user.id)
    week_ahead = today + timedelta(days=7)
    shows: dict[tuple[str, int], dict] = {}
    for category, item, schedule, episode, _link in episode_calendar._member_episodes(db, user, today):
        if not getattr(user, VISIBLE_FLAG[category], True):
            continue
        day = date.fromisoformat(episode["date"])
        if day > week_ahead:
            continue
        key = (category, item.id)
        show = shows.setdefault(key, {
            "category": category, "category_label": LABELS[category], "item_id": item.id,
            "title": (schedule.get("show") or item.title or "").strip()[:200],
            "library_title": (item.title or "").strip()[:200],
            "image": title_pages._safe_image(getattr(item, IMAGE_FIELD[category], None)),
            "network": (schedule.get("network") or "")[:60] or None,
            "out": None, "next": None,
        })
        entry = {"code": _code(category, episode), "date": episode["date"],
                 "name": (episode.get("name") or "")[:120] or None}
        if day <= today:
            if show["out"] is None or episode["date"] >= show["out"]["date"]:
                behind = _behind(category, checkpoints.get(key), episode)
                show["out"] = {**entry, "new": day >= since.date(), "waiting": behind}
        elif show["next"] is None or episode["date"] < show["next"]["date"]:
            show["next"] = entry
    found = list(shows.values())
    for show in found:
        progress = checkpoints.get((show["category"], show["item_id"]))
        show["progress"] = None
        if progress:
            season, position = progress
            show["progress"] = (f"S{season} E{position}" if show["category"] == "tv-shows" and season
                                else f"Episode {position}")

    def order(show):
        out, upcoming = show["out"], show["next"]
        if out and out["waiting"] is not False:
            return (0, -date.fromisoformat(out["date"]).toordinal(), show["title"].lower())
        if upcoming:
            return (1, date.fromisoformat(upcoming["date"]).toordinal(), show["title"].lower())
        return (2, -date.fromisoformat(out["date"]).toordinal(), show["title"].lower())

    found.sort(key=order)
    return found[:SHOW_LIMIT]


def releases(db: Session, user_id: int, today: date, since: datetime) -> list[dict]:
    """Release-day alerts the member was sent in the last two weeks, newest first."""
    rows = db.query(models.ReleaseAlert.category, models.ReleaseAlert.title, models.ReleaseAlert.release_date).filter(
        models.ReleaseAlert.user_id == user_id,
        models.ReleaseAlert.release_date >= today - timedelta(days=RELEASE_DAYS),
        models.ReleaseAlert.release_date <= today,
    ).order_by(models.ReleaseAlert.release_date.desc(), models.ReleaseAlert.id.desc()).limit(RELEASE_LIMIT).all()
    return [{"category": category, "category_label": LABELS.get(category, ""), "title": (title or "").strip()[:200],
             "date": released.isoformat(), "new": released >= since.date()}
            for category, title, released in rows]


def friends(db: Session, user_id: int, since: datetime, now: datetime) -> dict:
    """The newest few friends feed cards, plus how many arrived since ``since``."""
    data = friend_feed.page(db, user_id, limit=20, now=now)
    items = data.get("items") or []
    fresh = 0
    for item in items:
        try:
            at = datetime.fromisoformat(item["at"])
        except (KeyError, TypeError, ValueError):
            continue
        if at >= since:
            fresh += 1
    return {"items": items[:FRIEND_LIMIT], "new": fresh, "friends": data.get("friends", 0)}


def build(db: Session, user: models.User, since: Optional[datetime] = None,
          now: Optional[datetime] = None) -> dict:
    now = now or datetime.utcnow()
    since = clamp_since(since, now)
    today = now.date()
    shows = show_updates(db, user, today, since)
    released = releases(db, user.id, today, since)
    friend_part = friends(db, user.id, since, now)
    return {
        "since": since.isoformat(),
        "shows": shows,
        "releases": released,
        "friends": friend_part,
        "counts": {
            "episodes": sum(1 for show in shows if show["out"] and show["out"]["new"]),
            "waiting": sum(1 for show in shows if show["out"] and show["out"]["waiting"]),
            "soon": sum(1 for show in shows if show["next"]),
            "releases": sum(1 for release in released if release["new"]),
            "friends": friend_part["new"],
        },
        # Unfinished shows whose schedules are missing or old; the router asks for them in the background.
        "stale_shows": len(episode_calendar._stale_shows(db, [user.id])),
    }
