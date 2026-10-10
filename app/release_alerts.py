"""Release day alerts: tell members when something connected to their library comes out today.

Uses the same matching as "Coming up for you" (the title itself, a new season,
or a sequel of something the member tracks) against Release Radar's cache, so
it never calls an outside service. Each member gets at most one notification
per run, listing everything out that day, and is never told twice about the
same release: sent alerts are recorded in ``release_alerts``.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from . import models
from . import release_radar as radar
from .for_you import LIBRARY, RADAR_LABELS, _matches, normalize_title

LIBRARY_CATEGORIES = ("movies", "tv-shows", "anime", "video-games")
NOTIFICATION_TYPE = "release_day"
SAFE_KEY = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
NAMES_SHOWN = 2


def item_link(item: dict) -> str:
    """The title's card on Release Radar (the category page when the key can't go in a URL fragment)."""
    category = item["category"]
    if category not in radar.CATEGORY_ORDER:
        return "/release-radar"
    if SAFE_KEY.match(item.get("key") or ""):
        return f"/release-radar/{category}#item-{item['key']}"
    return f"/release-radar/{category}"


def out_today(pool: list[dict], today: date) -> list[dict]:
    return [item for item in pool if item.get("date") == today.isoformat() and (item.get("title") or "").strip()]


def _like_escape(word: str) -> str:
    return word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _candidates(db: Session, items: list[dict]) -> dict[int, list[str]]:
    """Library titles (by member) that might match one of today's releases.

    A match means the library title equals the release title or starts it, so
    both share the release's first word; filter on that in SQL, then apply the
    exact rule in Python.
    """
    words = set()
    for item in items:
        for name in (item["title"], item.get("alt_title") or ""):
            normalized = normalize_title(name)
            if normalized:
                words.add(normalized.split()[0])
    if not words:
        return {}
    active = db.query(models.User.id).filter(models.User.is_active == True)
    titles: dict[int, list[str]] = defaultdict(list)
    for category in LIBRARY_CATEGORIES:
        model = LIBRARY[category][0]
        lowered = func.lower(model.title)
        conditions = [lowered.like(f"%{_like_escape(word)}%", escape="\\") for word in words]
        query = db.query(model.user_id, model.title).filter(model.user_id.in_(active), model.title.isnot(None))
        for user_id, title in query.filter(or_(*conditions)).all():
            titles[user_id].append(title)
    return titles


def matches_for(library_titles: list[str], items: list[dict]) -> list[tuple[dict, str]]:
    """(release, library title it connects to) for each of today's releases this member tracks."""
    found = []
    for item in items:
        names = [item["title"]] + ([item["alt_title"]] if item.get("alt_title") else [])
        hit = next((title for title in library_titles if any(_matches(title, name) for name in names)), None)
        if hit is not None:
            found.append((item, hit))
    return found


def message_for(found: list[tuple[dict, str]]) -> str:
    if len(found) == 1:
        item, library_title = found[0]
        label = RADAR_LABELS.get(item["category"], "Title")
        if normalize_title(library_title) == normalize_title(item["title"]):
            return f"Out today: {item['title']} ({label}), from your library."
        return f"Out today: {item['title']} ({label}), because you track {library_title}."
    names = [item["title"] for item, _ in found]
    shown = ", ".join(names[:NAMES_SHOWN])
    rest = len(names) - NAMES_SHOWN
    if rest > 0:
        return f"Out today from your library: {shown} and {rest} more."
    return f"Out today from your library: {names[0]} and {names[1]}."


def send_alerts(db: Session, pool: list[dict], today: Optional[date] = None) -> dict:
    """Create today's release-day notifications. Safe to run repeatedly: each release is announced once."""
    today = today or radar.today_utc()
    stats = {"members": 0, "releases": 0}
    items = out_today(pool, today)
    if not items:
        return stats
    for user_id, library_titles in _candidates(db, items).items():
        found = matches_for(library_titles, items)
        if not found:
            continue
        already = {(row.category, row.item_key) for row in db.query(models.ReleaseAlert).filter(
            models.ReleaseAlert.user_id == user_id,
            models.ReleaseAlert.item_key.in_([item["key"] for item, _ in found]),
        ).all()}
        fresh = [(item, title) for item, title in found if (item["category"], item["key"]) not in already]
        if not fresh:
            continue
        try:
            for item, _ in fresh:
                db.add(models.ReleaseAlert(user_id=user_id, category=item["category"], item_key=item["key"],
                                           title=item["title"][:200], release_date=today))
            link = item_link(fresh[0][0]) if len(fresh) == 1 else "/release-radar"
            db.add(models.Notification(user_id=user_id, type=NOTIFICATION_TYPE, message=message_for(fresh),
                                       link=link))
            db.commit()
        except Exception:
            # Another process announced the same release first (unique constraint); skip this member.
            db.rollback()
            continue
        stats["members"] += 1
        stats["releases"] += len(fresh)
    return stats


def send_due_alerts(session_factory, pool: list[dict], today: Optional[date] = None) -> dict:
    """Background entry point (runs in a worker thread): announce today's releases from a cached pool."""
    db = session_factory()
    try:
        return send_alerts(db, pool, today)
    finally:
        db.close()
