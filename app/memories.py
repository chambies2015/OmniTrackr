"""On this day: what a member did on today's date in earlier years, and a month or six months ago (Oct 2026).

Nothing new is stored. Memories come from the journal (finishes, revisits, starts
and notes), completion reflections, collections the member published, titles added
to the library and the day they joined. Only the member ever sees them.

Dates are the member's own calendar days. The dashboard sends the browser's UTC
offset like the diary does; the weekly email and push notifications use the time
zone saved with push settings, or UTC. A memory from February 29 shows on February
28 in years without one. "A month ago" is skipped on days the previous month doesn't
have (no March 31 memory of February 31), so a memory never repeats on several days.
"""
from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timedelta
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from . import diary, models, title_pages

logger = logging.getLogger(__name__)

CARD_LIMIT = 3
NOTE_CHARS = 160
# Adding more than this on one day reads as an import, so it becomes one "you added N titles" memory.
BULK_ADD = 3
OLDEST_YEAR = 1950
WEEK_LIMIT = 3

# Past tense and "started ..." wording by journal category.
VERBS = {
    "movies": ("watched", "rewatched", "started watching"),
    "tv-shows": ("finished", "rewatched", "started watching"),
    "anime": ("finished", "rewatched", "started watching"),
    "video-games": ("finished", "replayed", "started playing"),
    "music": ("listened to", "went back to", "started listening to"),
    "books": ("finished", "reread", "started reading"),
    "manga": ("finished", "reread", "started reading"),
    "podcasts": ("finished", "went back to", "started listening to"),
    "audiobooks": ("finished", "went back to", "started listening to"),
}
# Which memory wins when one day has several.
RANK = {"finished": 0, "revisited": 1, "started": 2, "noted": 3, "collection": 4, "joined": 5, "added": 6,
        "added_many": 7}

LocalToUtc = Callable[[datetime], datetime]


def offset_converter(tz_offset_minutes: int) -> LocalToUtc:
    """Browser offsets follow Date.getTimezoneOffset(): minutes behind UTC."""
    shift = timedelta(minutes=tz_offset_minutes)
    return lambda local: local + shift


def zone_converter(tz: Optional[ZoneInfo]) -> LocalToUtc:
    if tz is None:
        return lambda local: local

    def convert(local: datetime) -> datetime:
        return local.replace(tzinfo=tz).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    return convert


def _year_back(day: date, years: int) -> Optional[date]:
    year = day.year - years
    if year < OLDEST_YEAR:
        return None
    if day.month == 2 and day.day == 29 and not calendar.isleap(year):
        return None  # shown on the 28th that year instead
    return day.replace(year=year)


def _months_back(day: date, months: int) -> Optional[date]:
    month = day.month - months
    year = day.year
    while month < 1:
        month += 12
        year -= 1
    if day.day > calendar.monthrange(year, month)[1]:
        return None
    return date(year, month, day.day)


def anchors(today: date, earliest: date, months: bool = True) -> list[tuple[date, str, int, date]]:
    """[(past day, "years" or "months", how many, last day of the window)] for every day worth looking at.

    The window is one day, except February 28 in a year without a 29th, which also
    covers the 29th of the leap years before it.
    """
    found = []
    for years in range(1, today.year - max(earliest.year, OLDEST_YEAR) + 1):
        year = today.year - years
        if today.month == 2 and today.day == 28 and not calendar.isleap(today.year) and calendar.isleap(year):
            found.append((date(year, 2, 28), "years", years, date(year, 2, 29)))
            continue
        day = _year_back(today, years)
        if day is not None and day >= earliest:
            found.append((day, "years", years, day))
    if months:
        for count in (6, 1):
            day = _months_back(today, count)
            if day is not None and day >= earliest:
                found.append((day, "months", count, day))
    return found


def ago_label(unit: str, count: int) -> str:
    if unit == "months":
        return "A month ago today" if count == 1 else f"{count} months ago today"
    return "A year ago today" if count == 1 else f"{count} years ago today"


def _rating_text(rating) -> Optional[str]:
    if rating is None:
        return None
    try:
        value = float(rating)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return f"{value:g}/10"


def _clip(text: Optional[str]) -> Optional[str]:
    text = " ".join((text or "").split())
    if not text:
        return None
    return text if len(text) <= NOTE_CHARS else text[:NOTE_CHARS - 1].rstrip() + "…"


def _line(kind: str, category: Optional[str], title: str, rating, count: int = 0) -> str:
    if kind == "joined":
        return "You joined OmniTrackr."
    if kind == "added_many":
        return f"You added {count} titles to your library."
    if kind == "collection":
        return f"You published your collection {title}."
    done, again, started = VERBS.get(category, ("finished", "went back to", "started"))
    if kind == "finished":
        line = f"You {done} {title}"
        rated = _rating_text(rating)
        return f"{line} and gave it {rated}." if rated else f"{line}."
    if kind == "revisited":
        return f"You {again} {title}."
    if kind == "started":
        return f"You {started} {title}."
    if kind == "noted":
        return f"You wrote about {title} in your journal."
    return f"You added {title} to your library."


def _earliest(db: Session, user: models.User) -> date:
    first = db.query(models.ActivityEntry.occurred_at).filter(
        models.ActivityEntry.user_id == user.id,
    ).order_by(models.ActivityEntry.occurred_at.asc()).first()
    days = [value.date() for value in (first[0] if first else None, user.created_at) if value]
    return min(days) if days else date.today()


def _windows(column, spans: list[tuple[datetime, datetime]]):
    return or_(*[and_(column >= start, column < end) for start, end in spans])


def collect(db: Session, user: models.User, today, to_utc: LocalToUtc, months: bool = True,
            limit: Optional[int] = CARD_LIMIT) -> list[dict]:
    """Up to ``limit`` memories for ``today`` (the member's local date), oldest first, one per day.

    ``today`` can also be a list of dates, so the weekly email reads a whole week in one pass.
    """
    earliest = _earliest(db, user)
    days = [anchor for day in ([today] if isinstance(today, date) else today)
            for anchor in anchors(day, earliest, months)]
    if not days:
        return []
    spans = []
    for day, unit, count, last in days:
        start = to_utc(datetime.combine(day, datetime.min.time()))
        end = to_utc(datetime.combine(last + timedelta(days=1), datetime.min.time()))
        spans.append((start, end, day, unit, count))
    windows = [(start, end) for start, end, *_ in spans]

    def which(moment: datetime):
        for start, end, day, unit, count in spans:
            if start <= moment < end:
                return day, unit, count
        return None

    candidates: dict[date, list[dict]] = {}

    def add(moment: datetime, memory: dict) -> None:
        found = which(moment)
        if found is None:
            return
        day, unit, count = found
        memory.update({"day": day.isoformat(), "unit": unit, "ago": count, "label": ago_label(unit, count),
                       "occurred_at": moment.isoformat()})
        candidates.setdefault(day, []).append(memory)

    entries = db.query(models.ActivityEntry).filter(
        models.ActivityEntry.user_id == user.id,
        models.ActivityEntry.category.in_(diary.CATEGORIES),
        models.ActivityEntry.action.in_(("completed", "revisited", "started", "noted")),
        _windows(models.ActivityEntry.occurred_at, windows),
    ).order_by(models.ActivityEntry.occurred_at.asc(), models.ActivityEntry.id.asc()).limit(400).all()
    items = diary.library_items(db, user.id, entries)
    moments = {}
    if entries:
        for moment in db.query(models.CompletionMoment).filter(
                models.CompletionMoment.user_id == user.id,
                models.CompletionMoment.item_id.in_({entry.item_id for entry in entries if entry.item_id})):
            moments[(moment.category, moment.item_id)] = moment
    for entry in entries:
        kind = {"completed": "finished"}.get(entry.action, entry.action)
        if kind == "noted" and not (entry.note or "").strip():
            continue
        item = items.get((entry.category, entry.item_id)) if entry.item_id else None
        note = entry.note
        moment = moments.get((entry.category, entry.item_id)) if entry.item_id else None
        if kind == "finished" and not (note or "").strip() and moment is not None:
            note = moment.takeaway
        title = (entry.title or "").strip() or "Untitled"
        add(entry.occurred_at, {
            "kind": kind,
            "category": entry.category,
            "category_label": diary.CATEGORIES[entry.category][1],
            "item_id": item.id if item is not None else None,
            "title": title,
            "rating": entry.rating,
            "note": _clip(note),
            "image": diary._image(entry.category, item),
            "finished": bool(item is not None and getattr(item, activity_done_field(entry.category), False)),
            "line": _line(kind, entry.category, title, entry.rating),
        })

    for collection in db.query(models.Collection).filter(
            models.Collection.user_id == user.id, models.Collection.published_at.isnot(None),
            _windows(models.Collection.published_at, windows)).limit(20):
        name = (collection.name or "").strip() or "Untitled"
        add(collection.published_at, {"kind": "collection", "category": None, "category_label": "Collection",
                                      "item_id": None, "collection_id": collection.id, "title": name,
                                      "rating": None, "note": None,
                                      "image": title_pages._safe_image(collection.cover_url), "finished": False,
                                      "line": _line("collection", None, name, None)})

    if user.created_at and which(user.created_at):
        add(user.created_at, {"kind": "joined", "category": None, "category_label": "OmniTrackr", "item_id": None,
                              "title": "OmniTrackr", "rating": None, "note": None, "image": None,
                              "finished": False, "line": _line("joined", None, "", None)})

    added: dict[date, list[dict]] = {}
    for category in diary.CATEGORIES:
        model = diary._model(category)
        for item in db.query(model).filter(model.user_id == user.id, model.added_at.isnot(None),
                                           _windows(model.added_at, windows)).limit(200):
            found = which(item.added_at)
            if found is None:
                continue
            added.setdefault(found[0], []).append({
                "kind": "added", "category": category, "category_label": diary.CATEGORIES[category][1],
                "item_id": item.id, "title": (item.title or "").strip() or "Untitled", "rating": item.rating,
                "note": None, "image": diary._image(category, item),
                "finished": bool(getattr(item, activity_done_field(category), False)), "moment": item.added_at,
            })
    for day, rows in added.items():
        if len(rows) > BULK_ADD:
            first = min(rows, key=lambda row: row["moment"])
            add(first["moment"], {"kind": "added_many", "category": None, "category_label": "Library",
                                  "item_id": None, "title": f"{len(rows)} titles", "rating": None, "note": None,
                                  "image": next((row["image"] for row in rows if row["image"]), None),
                                  "finished": False, "count": len(rows),
                                  "line": _line("added_many", None, "", None, len(rows))})
            continue
        for row in rows:
            moment = row.pop("moment")
            row["line"] = _line("added", row["category"], row["title"], None)
            add(moment, row)

    picked = []
    for day in sorted(candidates):
        rows = sorted(candidates[day], key=lambda row: (RANK[row["kind"]], -(row["rating"] or 0), row["occurred_at"]))
        best = rows[0]
        best["more"] = len(rows) - 1
        picked.append(best)
    # Years ago first (oldest first), then six months, then a month.
    picked.sort(key=lambda row: (row["unit"] != "years", -row["ago"]))
    return picked if limit is None else picked[:limit]


def activity_done_field(category: str) -> str:
    from .routers.activity import DONE_FIELDS
    return DONE_FIELDS[category]


def for_dashboard(db: Session, user: models.User, tz_offset_minutes: int = 0, now: Optional[datetime] = None) -> dict:
    now = now or datetime.utcnow()
    today = (now - timedelta(minutes=tz_offset_minutes)).date()
    return {"date": today.isoformat(), "memories": collect(db, user, today, offset_converter(tz_offset_minutes))}


def member_zone(db: Session, user_id: int) -> Optional[ZoneInfo]:
    from . import web_push
    pref = db.get(models.PushPreference, user_id)
    return web_push.zone(pref.time_zone) if pref is not None else None


def week_in_past_years(db: Session, user: models.User, today: date, limit: int = WEEK_LIMIT) -> list[dict]:
    """Finishes and revisits from the seven days ending today, in earlier years, for the weekly email."""
    to_utc = zone_converter(member_zone(db, user.id))
    week = [today - timedelta(days=back) for back in range(7)]
    found = [memory for memory in collect(db, user, week, to_utc, months=False, limit=None)
             if memory["kind"] in ("finished", "revisited")]
    found.sort(key=lambda row: (-row["ago"], row["occurred_at"]))
    return found[:limit]


# ---------------------------------------------------------------- push

PUSH_TYPE = "memory"
PUSH_FROM_HOUR = 9
PUSH_UNTIL_HOUR = 21
# Member id -> the local day they were last looked at. Stops a resend after the member deletes the day's
# notification, and stops the 15-minute loop re-collecting for members with nothing to show that day.
_pushed_on: dict[int, date] = {}


def clear_push_marks() -> None:
    _pushed_on.clear()


def _push_message(memory: dict) -> str:
    line = memory["line"]
    return f"{memory['label']}: {line[0].lower()}{line[1:]}" if line.startswith("You ") else f"{memory['label']}: {line}"


def send_due_pushes(db: Session, now: Optional[datetime] = None) -> int:
    """Once a day, in the member's morning or afternoon, put their best year-ago memory in the bell (and so on
    their devices). Only for members who switched the memories topic on and have a device."""
    from . import web_push
    now = now or datetime.utcnow()
    sent = 0
    prefs = db.query(models.PushPreference).filter(models.PushPreference.topics.like('%"memories"%')).all()
    for pref in prefs:
        if not web_push.chosen_topics(pref).get("memories"):
            continue
        if web_push.in_quiet_hours(pref, now):
            continue
        tz = web_push.zone(pref.time_zone)
        local = now.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz).replace(tzinfo=None) if tz else now
        if not PUSH_FROM_HOUR <= local.hour < PUSH_UNTIL_HOUR:
            continue
        if _pushed_on.get(pref.user_id) == local.date():
            continue
        user = db.get(models.User, pref.user_id)
        if user is None or not user.is_active:
            continue
        has_device = db.query(models.PushSubscription.id).filter(
            models.PushSubscription.user_id == user.id).first()
        if has_device is None:
            continue
        day_start = zone_converter(tz)(datetime.combine(local.date(), datetime.min.time()))
        already = db.query(models.Notification.id).filter(
            models.Notification.user_id == user.id, models.Notification.type == PUSH_TYPE,
            models.Notification.created_at >= day_start).first()
        if already is not None:
            continue
        try:
            found = [memory for memory in collect(db, user, local.date(), zone_converter(tz), months=False, limit=1)
                     if memory["kind"] not in ("added", "added_many")]
        except Exception:
            db.rollback()
            logger.exception("Could not collect memories for member %s", user.id)
            continue
        _pushed_on[user.id] = local.date()
        if not found:
            continue
        db.add(models.Notification(user_id=user.id, type=PUSH_TYPE, message=_push_message(found[0])[:240],
                                   link="/#on-this-day"))
        db.commit()
        sent += 1
    return sent
