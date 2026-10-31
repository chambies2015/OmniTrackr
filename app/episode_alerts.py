"""New-episode alerts: tell members the moment a new episode of a show they follow is out.

Air dates come from the episode calendar's cache (TVmaze for TV, AniList for
anime), which the background sweep keeps fresh for members who have a private
calendar with episodes on or a device that gets "New episodes" pushed. Nothing
here calls an outside service.

Each member gets one notification per run listing what's new, and is never told
twice about the same episode: announced ones are recorded in ``episode_alerts``.
The notification lands in the bell and, for members with notifications on, on
their phone or desktop too (see web_push).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from . import episode_calendar, models, web_push
from .title_pages import title_path

NOTIFICATION_TYPE = "episode_today"
# An episode is announced in the window after it's out. One that was already older
# than this when first seen (a new show added late, a long outage) is skipped, not
# announced late.
ANNOUNCE_FOR = timedelta(hours=36)
# Streaming drops have no air time. They count as out from this hour (UTC) on their
# air date: 08:00 UTC is 3 a.m. in New York, after the usual midnight-Pacific drop.
ALL_DAY_HOUR = 8
NAMES_SHOWN = 2


def members(db: Session) -> list[int]:
    """Members with a private calendar that lists episodes, plus those who get new episodes pushed."""
    calendar = [user_id for user_id, in db.query(models.CalendarFeed.user_id).join(
        models.User, models.User.id == models.CalendarFeed.user_id).filter(
        models.CalendarFeed.include_episodes == True,  # noqa: E712
        models.User.is_active == True,  # noqa: E712
    ).all()]
    return sorted(set(calendar) | set(web_push.members_wanting(db, NOTIFICATION_TYPE)))


def episode_key(category: str, schedule: dict, episode: dict) -> str:
    source_id = schedule.get("source_id")
    if category == "tv-shows" and episode.get("season"):
        return f"tvm-{source_id}-s{episode['season']}e{episode['number']}"
    return f"al-{source_id}-e{episode['number']}"


def out_since(episode: dict) -> Optional[datetime]:
    """When (UTC) the episode counts as out, or None when its date can't be read."""
    start = episode.get("start")
    if isinstance(start, str) and start:
        try:
            return datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass
    try:
        day = date.fromisoformat(episode.get("date") or "")
    except ValueError:
        return None
    return datetime.combine(day, datetime.min.time()) + timedelta(hours=ALL_DAY_HOUR)


def is_out(episode: dict, now: datetime) -> bool:
    since = out_since(episode)
    return since is not None and since <= now < since + ANNOUNCE_FOR


def label(category: str, item, schedule: dict, episode: dict) -> str:
    show = (schedule.get("show") or item.title or "").strip()
    if category == "tv-shows" and episode.get("season"):
        text = f"{show} S{episode['season']}E{episode['number']}"
        if episode.get("name"):
            text += f", {episode['name']}"
        return text
    return f"{show} episode {episode['number']}"


def message_for(found: list[tuple[str, object, dict, dict]]) -> str:
    if len(found) == 1:
        category, item, schedule, episode = found[0]
        where = f" on {schedule['network']}" if schedule.get("network") else ""
        return f"{label(category, item, schedule, episode)} is out now{where}."
    names = [label(category, item, schedule, episode) for category, item, schedule, episode in found]
    shown = names[:NAMES_SHOWN]
    rest = len(names) - NAMES_SHOWN
    if rest > 0:
        return f"New episodes out now: {', '.join(shown)} and {rest} more."
    return f"New episodes out now: {shown[0]} and {shown[1]}."


def link_for(user: models.User, found: list[tuple[str, object, dict, dict]]) -> str:
    """The title's page, unless that part of the member's library is private or several shows are new."""
    if len(found) != 1:
        return "/"
    category, item, *_ = found[0]
    if getattr(user, episode_calendar.PRIVATE_FLAG[category], False):
        return "/"
    return title_path(episode_calendar.PAGE_KIND[category], item.title, item.year)


def new_episodes(db: Session, user: models.User, now: datetime) -> list[tuple[str, object, dict, dict]]:
    """Episodes of the member's unfinished shows that are out now, from the cache only, one per episode."""
    found, seen = [], set()
    for category, item, schedule, episode, _link in episode_calendar._member_episodes(db, user, now.date()):
        if not is_out(episode, now):
            continue
        key = episode_key(category, schedule, episode)
        if key in seen:
            continue
        seen.add(key)
        found.append((category, item, schedule, episode))
    found.sort(key=lambda row: (out_since(row[3]) or now, label(*row).lower()))
    return found


def send_alerts(db: Session, now: Optional[datetime] = None) -> dict:
    """Create the new-episode notifications that are due. Safe to run often: each episode is announced once."""
    now = now or datetime.utcnow()
    stats = {"members": 0, "episodes": 0}
    for user_id in members(db):
        user = db.get(models.User, user_id)
        if user is None or not user.is_active:
            continue
        found = new_episodes(db, user, now)
        if not found:
            continue
        keys = [episode_key(category, schedule, episode) for category, _, schedule, episode in found]
        already = {key for key, in db.query(models.EpisodeAlert.episode_key).filter(
            models.EpisodeAlert.user_id == user_id, models.EpisodeAlert.episode_key.in_(keys)).all()}
        fresh = [row for row, key in zip(found, keys) if key not in already]
        if not fresh:
            continue
        try:
            for (category, item, schedule, episode), key in zip(found, keys):
                if key in already:
                    continue
                db.add(models.EpisodeAlert(user_id=user_id, episode_key=key,
                                           title=label(category, item, schedule, episode)[:200],
                                           aired_on=(out_since(episode) or now).date()))
            db.add(models.Notification(user_id=user_id, type=NOTIFICATION_TYPE, message=message_for(fresh),
                                       link=link_for(user, fresh)))
            db.commit()
        except Exception:
            # Another process announced the same episode first (unique constraint); skip this member.
            db.rollback()
            continue
        stats["members"] += 1
        stats["episodes"] += len(fresh)
    return stats


def send_due_alerts(session_factory, now: Optional[datetime] = None) -> dict:
    """Background entry point (runs in a worker thread)."""
    db = session_factory()
    try:
        return send_alerts(db, now)
    finally:
        db.close()
