"""The diary: a month-by-month view of the journal's finishes and revisits (Oct 2026).

Nothing new is stored. The diary reads the "completed" and "revisited" journal
entries a member already has, numbers each visit to a title ("2nd watch"), and
finds the title's artwork in the library. The public diary on /u/<username> is
off until the member switches it on, never shows notes, and skips private
categories and titles no longer in the library.
"""
from __future__ import annotations

import calendar
import re
from datetime import datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from . import models, title_pages

DIARY_ACTIONS = ("completed", "revisited")
# Library category -> (title page kind, label, first-visit verb, repeat noun)
CATEGORIES = {
    "movies": ("movie", "Movie", "Watched", "Rewatch"),
    "tv-shows": ("tv", "TV show", "Watched", "Rewatch"),
    "anime": ("anime", "Anime", "Watched", "Rewatch"),
    "video-games": ("game", "Game", "Played", "Replay"),
    "music": ("album", "Album", "Listened", "Relisten"),
    "books": ("book", "Book", "Read", "Reread"),
    "manga": ("manga", "Manga", "Read", "Reread"),
    "podcasts": ("podcast", "Podcast", "Listened", "Relisten"),
}
PUBLIC_DIARY_LIMIT = 24
# Letterboxd diary dates have no time of day. Noon UTC keeps the same calendar day
# for members anywhere from UTC-11 to UTC+11.
IMPORTED_DATE_HOUR = 12
MAX_DIARY_IMPORT = 5000


def _key(category: str, title: str) -> tuple[str, str]:
    return category, re.sub(r"\s+", " ", (title or "").strip().casefold())


def _model(category: str):
    return title_pages.KINDS[CATEGORIES[category][0]][0]


def visit_numbers(db: Session, user_id: int, entries: Iterable[models.ActivityEntry]) -> dict[int, int]:
    """{entry id: which visit to the title this was}, counting every earlier finish or revisit."""
    entries = list(entries)
    wanted = {_key(entry.category, entry.title) for entry in entries}
    if not wanted:
        return {}
    history = db.query(
        models.ActivityEntry.id, models.ActivityEntry.category, models.ActivityEntry.title,
    ).filter(
        models.ActivityEntry.user_id == user_id,
        models.ActivityEntry.action.in_(DIARY_ACTIONS),
        models.ActivityEntry.category.in_({category for category, _ in wanted}),
    ).order_by(models.ActivityEntry.occurred_at.asc(), models.ActivityEntry.id.asc())
    counts: dict[tuple[str, str], int] = {}
    numbers: dict[int, int] = {}
    for entry_id, category, title in history:
        key = _key(category, title)
        if key not in wanted:
            continue
        counts[key] = counts.get(key, 0) + 1
        numbers[entry_id] = counts[key]
    return numbers


def library_items(db: Session, user_id: int, entries: Iterable[models.ActivityEntry]) -> dict[tuple[str, int], object]:
    """The member's library rows behind ``entries``, one query per category."""
    wanted: dict[str, set[int]] = {}
    for entry in entries:
        if entry.item_id and entry.category in CATEGORIES:
            wanted.setdefault(entry.category, set()).add(entry.item_id)
    found = {}
    for category, ids in wanted.items():
        model = _model(category)
        for item in db.query(model).filter(model.user_id == user_id, model.id.in_(ids)):
            found[(category, item.id)] = item
    return found


def _image(category: str, item) -> Optional[str]:
    if item is None:
        return None
    kind = CATEGORIES[category][0]
    return title_pages._safe_image(getattr(item, title_pages.IMAGE_FIELD[kind], None))


def is_repeat(entry: models.ActivityEntry, visit: int) -> bool:
    return entry.action == "revisited" or visit > 1


def visit_label(category: str, entry: models.ActivityEntry, visit: int) -> str:
    """"Watched", "Rewatch", "3rd read"... as the diary shows it."""
    _, _, first, again = CATEGORIES[category]
    if not is_repeat(entry, visit):
        return first
    if visit <= 2:
        return again
    suffix = "th" if 10 <= visit % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(visit % 10, "th")
    noun = {"Watched": "watch", "Played": "play", "Listened": "listen", "Read": "read"}[first]
    return f"{visit}{suffix} {noun}"


# ---------------------------------------------------------------- the member's own diary

def parse_month(value: Optional[str], now: datetime) -> tuple[int, int]:
    if not value:
        return now.year, now.month
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise ValueError("month must use YYYY-MM format") from exc
    if parsed.year < 1900:
        raise ValueError("month is too far back")
    return parsed.year, parsed.month


def month_view(db: Session, user_id: int, month: Optional[str], tz_offset_minutes: int = 0) -> dict:
    """One calendar month of finishes and revisits, in the member's local time."""
    local_now = datetime.utcnow() - timedelta(minutes=tz_offset_minutes)
    year, month_number = parse_month(month, local_now)
    if (year, month_number) > (local_now.year, local_now.month):
        year, month_number = local_now.year, local_now.month
    local_start = datetime(year, month_number, 1)
    days_in_month = calendar.monthrange(year, month_number)[1]
    local_end = local_start + timedelta(days=days_in_month)
    shift = timedelta(minutes=tz_offset_minutes)
    entries = db.query(models.ActivityEntry).filter(
        models.ActivityEntry.user_id == user_id,
        models.ActivityEntry.action.in_(DIARY_ACTIONS),
        models.ActivityEntry.category.in_(CATEGORIES),
        models.ActivityEntry.occurred_at >= local_start + shift,
        models.ActivityEntry.occurred_at < local_end + shift,
    ).order_by(models.ActivityEntry.occurred_at.asc(), models.ActivityEntry.id.asc()).all()
    visits = visit_numbers(db, user_id, entries)
    items = library_items(db, user_id, entries)

    days: dict[str, list] = {}
    repeats = 0
    for entry in entries:
        local = entry.occurred_at - shift
        visit = visits.get(entry.id, 1)
        repeat = is_repeat(entry, visit)
        repeats += repeat
        item = items.get((entry.category, entry.item_id)) if entry.item_id else None
        days.setdefault(local.date().isoformat(), []).append({
            "id": entry.id,
            "category": entry.category,
            "category_label": CATEGORIES[entry.category][1],
            "item_id": entry.item_id if item is not None else None,
            "title": entry.title,
            "action": entry.action,
            "rating": entry.rating,
            "note": entry.note,
            "occurred_at": entry.occurred_at,
            "visit": visit,
            "repeat": repeat,
            "visit_label": visit_label(entry.category, entry, visit),
            "image": _image(entry.category, item),
        })

    first = db.query(models.ActivityEntry.occurred_at).filter(
        models.ActivityEntry.user_id == user_id,
        models.ActivityEntry.action.in_(DIARY_ACTIONS),
        models.ActivityEntry.category.in_(CATEGORIES),
    ).order_by(models.ActivityEntry.occurred_at.asc()).first()
    earliest = (first[0] - shift) if first else None
    previous_start = (local_start - timedelta(days=1)).replace(day=1)
    has_older = earliest is not None and earliest < local_start
    has_newer = (year, month_number) < (local_now.year, local_now.month)
    by_category = {}
    for day in days.values():
        for row in day:
            by_category[row["category"]] = by_category.get(row["category"], 0) + 1
    return {
        "month": f"{year:04d}-{month_number:02d}",
        "label": local_start.strftime("%B %Y"),
        "first_weekday": local_start.weekday(),  # 0 is Monday
        "days_in_month": days_in_month,
        "today": local_now.date().isoformat(),
        "days": days,
        "entry_count": len(entries),
        "finished_count": len(entries) - repeats,
        "repeat_count": repeats,
        "active_days": len(days),
        "by_category": [
            {"category": category, "label": CATEGORIES[category][1], "count": by_category[category]}
            for category in CATEGORIES if by_category.get(category)
        ],
        "previous_month": previous_start.strftime("%Y-%m") if has_older else None,
        "next_month": (local_end.strftime("%Y-%m") if has_newer else None),
        "earliest_month": earliest.strftime("%Y-%m") if earliest else None,
    }


# ---------------------------------------------------------------- public diary

def public_entries(db: Session, user: models.User, visible_categories: Iterable[str],
                   limit: int = PUBLIC_DIARY_LIMIT) -> list[dict]:
    """The member's latest finishes and revisits for their public profile.

    Only titles still in a shareable shelf of the library are shown, so deleting a
    title or making a category private takes it off the diary too. Notes stay private.
    """
    visible = [category for category in visible_categories if category in CATEGORIES]
    if not visible:
        return []
    rows = db.query(models.ActivityEntry).filter(
        models.ActivityEntry.user_id == user.id,
        models.ActivityEntry.action.in_(DIARY_ACTIONS),
        models.ActivityEntry.category.in_(visible),
        models.ActivityEntry.item_id.isnot(None),
    ).order_by(models.ActivityEntry.occurred_at.desc(), models.ActivityEntry.id.desc()).limit(limit * 3).all()
    items = library_items(db, user.id, rows)
    rows = [row for row in rows if (row.category, row.item_id) in items
            and (items[(row.category, row.item_id)].title or "").strip()][:limit]
    visits = visit_numbers(db, user.id, rows)
    shown = []
    for entry in rows:
        item = items[(entry.category, entry.item_id)]
        kind = CATEGORIES[entry.category][0]
        visit = visits.get(entry.id, 1)
        shown.append({
            "date": entry.occurred_at.date(),
            "title": item.title.strip(),
            "label": CATEGORIES[entry.category][1],
            "rating": item.rating,
            "repeat": is_repeat(entry, visit),
            "visit_label": visit_label(entry.category, entry, visit),
            "image": _image(entry.category, item),
            "url": title_pages.path_for_item(kind, item),
        })
    return shown


# ---------------------------------------------------------------- Letterboxd diary import

def plan_letterboxd_import(db: Session, user_id: int, rows: list[dict]) -> list[dict]:
    """The Letterboxd diary rows that are not already in the member's journal, ready to save.

    Each row is {"title", "year", "date", "rewatch", "rating"} from import_formats.
    A first watch becomes a "Finished" entry and a rewatch a "Revisited" one.
    """
    if not rows:
        return []
    existing = {
        (_key("movies", title)[1], action, occurred_at)
        for title, action, occurred_at in db.query(
            models.ActivityEntry.title, models.ActivityEntry.action, models.ActivityEntry.occurred_at,
        ).filter(models.ActivityEntry.user_id == user_id, models.ActivityEntry.category == "movies",
                 models.ActivityEntry.action.in_(DIARY_ACTIONS))
    }
    today = datetime.utcnow().date()
    planned = []
    for row in rows[:MAX_DIARY_IMPORT]:
        title = (row.get("title") or "").strip()[:500]
        watched = row.get("date")
        if not title or watched is None or watched > today:
            continue
        occurred_at = datetime(watched.year, watched.month, watched.day, IMPORTED_DATE_HOUR)
        action = "revisited" if row.get("rewatch") else "completed"
        identity = (_key("movies", title)[1], action, occurred_at)
        if identity in existing:
            continue
        existing.add(identity)
        planned.append({"title": title, "year": row.get("year"), "action": action,
                        "occurred_at": occurred_at, "rating": row.get("rating")})
    return planned


def save_letterboxd_import(db: Session, user_id: int, planned: list[dict]) -> int:
    """Add the planned diary entries, linked to the library's film when exactly one matches."""
    if not planned:
        return 0
    films: dict[str, list] = {}
    for movie in db.query(models.Movie).filter(models.Movie.user_id == user_id):
        films.setdefault(_key("movies", movie.title)[1], []).append(movie)
    for row in planned:
        matches = films.get(_key("movies", row["title"])[1], [])
        if row.get("year") and len(matches) > 1:
            matches = [movie for movie in matches if movie.year == row["year"]] or matches
        db.add(models.ActivityEntry(
            user_id=user_id, category="movies", item_id=matches[0].id if len(matches) == 1 else None,
            title=row["title"], action=row["action"], rating=row.get("rating"),
            source="import", occurred_at=row["occurred_at"],
        ))
    db.commit()
    return len(planned)
