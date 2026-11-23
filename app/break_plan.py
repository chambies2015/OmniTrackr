"""Plan your break (/break): days off, filled from the member's own list (Nov 2026).

Thanksgiving is a Thursday-to-Sunday weekend for most of our members, and the stretch from
Christmas Eve to New Year's Day is the longest run of free days in the year. People go into
both with a vague idea ("I'll finally finish Severance") and come out of them having scrolled.
A plan is what turns a free afternoon into one more title ticked off, and a plan that sits on
the home screen gives a reason to open OmniTrackr on every day of the break.

* The member says which days (a holiday preset, the weekend, or any dates up to 16 days) and
  about how much time they have on each one (Thanksgiving Day itself starts light).
* The plan fills those days from their own library: what they're part-way through first, then
  their Up next queue, then titles they saved and never started, in a mix of formats. Long
  titles are split into stretches that fit a day ("Episodes 4-7", "Pages 121-240", "Play for
  about 2 hours"); films and albums stay whole. A saved title only goes in if the break can
  finish it (or its first season), so the plan ends in things done.
* Each stretch has a tick. Ticking the last stretch of a film, show, book or manga marks it
  finished in the library (check_in.answer, so goals and challenges count it); ticking an
  earlier one moves the library's own checkpoint forward, never back. Logging progress in the
  library ticks the matching stretches here too.
* Swap, move, remove or add a title, "Try another mix", fill any free time again.
* Optional: one email the morning the break starts and one the morning after it ends; a .ics
  with one event per day; a share link (/break/s/<token>) that shows the plan from the shelves
  the member shares publicly, with a 1200x630 card and a 1080x1920 story picture
  (app/break_share.py). Whoever opens it can plan the same days from their own list, with the
  titles they liked from it going in first.

New tables only (break_plans, break_plan_items). Funnel events are "break_*" (funnel.py).
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import random
import re
import secrets
import zlib
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from html import escape
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models

MAX_DAYS = 16
START_WITHIN_DAYS = 60
DAY_CHOICES = (0, 30, 60, 90, 120, 180, 240, 300, 360, 480)
DEFAULT_MINUTES = 180
LIGHT_MINUTES = 60          # Thanksgiving Day, Christmas Day: family first
MAX_PER_DAY = 6
MAX_ITEMS = 80
MAX_ADDED_TITLES = 30
GAME_SHARE = 0.4            # a game the member hasn't started takes at most this much of the break
MIN_CHUNK = 15
BLOCK = 30                  # games, audiobooks and books without a page count go in half hours
POOL_PER_CATEGORY = 250
SAVED_LOOKED_AT = 60
WRAP_DAYS = 4               # the home card shows how it went for this many days after the break
SEND_PREFIX = "break-"
START_HOUR = 8
WRAP_HOUR = 10
LATE = timedelta(hours=4)
CHECK_EVERY_SECONDS = 900
FIRST_CHECK_DELAY_SECONDS = 540
PER_RUN_LIMIT = 20
UTM = "utm_source=email&utm_campaign=break"
SHARE_KEEP_DAYS = 30        # a share link stops working this long after the break ends
SHARE_TOKEN = re.compile(r"[A-Za-z0-9_-]{16,40}")
MAX_PICKS = 30              # titles taken from a shared plan onto a new one

CATEGORIES = ("movies", "tv-shows", "anime", "video-games", "music", "books", "manga", "audiobooks")
LABELS = {"movies": "Movie", "tv-shows": "TV show", "anime": "Anime", "video-games": "Game", "music": "Album",
          "books": "Book", "manga": "Manga", "audiobooks": "Audiobook"}
VERB = {"movies": "Watch", "tv-shows": "Watch", "anime": "Watch", "video-games": "Play", "music": "Listen to",
        "books": "Read", "manga": "Read", "audiobooks": "Listen to"}
BLOCK_VERB = {"video-games": "Play", "audiobooks": "Listen", "books": "Read"}


class BreakError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def clamp_tz(value) -> int:
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return 0
    return max(-14 * 60, min(14 * 60, minutes))


def local_today(value: Optional[str], now: Optional[datetime] = None) -> date:
    """The member's date from the browser, trusted only within a day of UTC's."""
    utc_today = (now or _now()).date()
    try:
        given = date.fromisoformat(value or "")
    except ValueError:
        return utc_today
    return given if abs((given - utc_today).days) <= 1 else utc_today


def count(event: str, request=None) -> None:
    from . import funnel
    funnel.record(event, request)


def daily_limit() -> int:
    try:
        return max(0, int(os.getenv("BREAK_PLAN_DAILY_LIMIT", "40")))
    except ValueError:
        return 40


def emails_enabled() -> bool:
    if os.getenv("BREAK_PLAN_EMAILS", "").strip().lower() in ("off", "0", "false", "no"):
        return False
    return os.getenv("TESTING", "").lower() != "true"


# ---------------------------------------------------------------- dates and presets

def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th weekday (0 = Monday) of a month; n = -1 is the last one."""
    if n > 0:
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    last = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1))
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def thanksgiving(year: int) -> date:
    return _nth_weekday(year, 11, 3, 4)


def _monday_weekend(day: date) -> tuple[date, date]:
    return day - timedelta(days=2), day


def _july_fourth(year: int) -> tuple[date, date]:
    day = date(year, 7, 4)
    weekday = day.weekday()
    if weekday == 3:            # Thursday: most people take Friday too
        return day, day + timedelta(days=3)
    if weekday == 4:
        return day, day + timedelta(days=2)
    if weekday == 5:            # Saturday, observed on Friday
        return day - timedelta(days=1), day + timedelta(days=1)
    if weekday == 6:            # Sunday, observed on Monday
        return day - timedelta(days=1), day + timedelta(days=1)
    if weekday == 0:
        return day - timedelta(days=2), day
    if weekday == 1:
        return day - timedelta(days=3), day
    return day, day


def _holidays(year: int) -> list[dict]:
    """The long weekends of one year, in order. ``light`` days start with less time on them."""
    found = []
    start, end = _monday_weekend(_nth_weekday(year, 1, 0, 3))
    found.append({"slug": "mlk", "name": "Martin Luther King Jr. weekend", "short": "MLK weekend",
                  "starts_on": start, "ends_on": end, "light": [], "lead": 6})
    start, end = _monday_weekend(_nth_weekday(year, 2, 0, 3))
    found.append({"slug": "presidents", "name": "Presidents' Day weekend", "short": "Presidents' Day weekend",
                  "starts_on": start, "ends_on": end, "light": [], "lead": 6})
    start, end = _monday_weekend(_nth_weekday(year, 5, 0, -1))
    found.append({"slug": "memorial", "name": "Memorial Day weekend", "short": "Memorial Day weekend",
                  "starts_on": start, "ends_on": end, "light": [], "lead": 6})
    start, end = _july_fourth(year)
    found.append({"slug": "july-4", "name": "Fourth of July weekend", "short": "Fourth of July",
                  "starts_on": start, "ends_on": end, "light": [date(year, 7, 4)], "lead": 6})
    start, end = _monday_weekend(_nth_weekday(year, 9, 0, 1))
    found.append({"slug": "labor", "name": "Labor Day weekend", "short": "Labor Day weekend",
                  "starts_on": start, "ends_on": end, "light": [], "lead": 6})
    day = thanksgiving(year)
    found.append({"slug": "thanksgiving", "name": "Thanksgiving weekend", "short": "Thanksgiving",
                  "starts_on": day, "ends_on": day + timedelta(days=3), "light": [day], "lead": 10})
    found.append({"slug": "winter", "name": "Christmas to New Year's", "short": "the holidays",
                  "starts_on": date(year, 12, 24), "ends_on": date(year + 1, 1, 1),
                  "light": [date(year, 12, 25)], "lead": 12})
    for entry in found:
        entry["key"] = f"{entry['slug']}-{entry['starts_on'].year}"
    return found


def _weekend(today: date) -> dict:
    """The coming weekend, or what is left of this one."""
    if today.weekday() == 6:
        start = today
    elif today.weekday() == 5:
        start = today
    else:
        start = today + timedelta(days=5 - today.weekday())
    end = start + timedelta(days=6 - start.weekday())
    return {"slug": "weekend", "key": f"weekend-{start.isoformat()}", "name": "This weekend", "short": "the weekend",
            "starts_on": start, "ends_on": end, "light": [], "lead": 0}


def presets(today: date, within_days: int = 45) -> list[dict]:
    """The breaks to offer: holidays that haven't ended and start within ``within_days``, then the weekend.

    A holiday already under way starts today, so its first days aren't planned after the fact.
    """
    found = []
    for year in (today.year - 1, today.year, today.year + 1):
        for entry in _holidays(year):
            if entry["ends_on"] < today or (entry["starts_on"] - today).days > within_days:
                continue
            entry = dict(entry)
            if entry["starts_on"] < today:
                entry["starts_on"] = today
                entry["light"] = [day for day in entry["light"] if day >= today]
            found.append(entry)
    found.sort(key=lambda entry: entry["starts_on"])
    weekend = _weekend(today)
    if not any(entry["starts_on"] <= weekend["ends_on"] and entry["ends_on"] >= weekend["starts_on"] for entry in found):
        found.append(weekend)
    return found


def preset(key: str, today: date) -> Optional[dict]:
    return next((entry for entry in presets(today, within_days=START_WITHIN_DAYS) if entry["key"] == key), None)


def prompt_preset(today: date) -> Optional[dict]:
    """The holiday the home card offers to plan, inside its lead-up and before its last day."""
    for entry in presets(today):
        if entry["lead"] and (entry["starts_on"] - today).days <= entry["lead"] and today < entry["ends_on"]:
            return entry
    return None


def days_of(starts_on: date, ends_on: date) -> list[date]:
    return [starts_on + timedelta(days=offset) for offset in range((ends_on - starts_on).days + 1)]


def _day_label(day: date) -> str:
    return f"{day.strftime('%a')} {day.strftime('%b')} {day.day}"


def span_label(starts_on: date, ends_on: date) -> str:
    if starts_on == ends_on:
        return _day_label(starts_on)
    return f"{_day_label(starts_on)} to {_day_label(ends_on)}"


def default_minutes(days: list[date], daily: int, light: Iterable[date] = ()) -> dict[str, int]:
    light = set(light)
    return {day.isoformat(): (min(daily, LIGHT_MINUTES) if day in light else daily) for day in days}


def clean_minutes(value) -> int:
    """The nearest of DAY_CHOICES (minutes the member has on a day)."""
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return DEFAULT_MINUTES
    return min(DAY_CHOICES, key=lambda choice: (abs(choice - minutes), choice))


def length_words(minutes: float, guessed: bool = False) -> str:
    minutes = int(round(minutes or 0))
    if minutes <= 0:
        return ""
    if minutes < 60:
        words = f"{minutes} min"
    elif not guessed:
        hours, rest = divmod(minutes, 60)
        words = f"{hours}h {rest:02d}m" if rest else f"{hours}h"
    else:
        half_hours = max(2, round(minutes / 30))
        hours = half_hours / 2
        shown = f"{hours:g}"
        words = f"{shown} hour{'s' if hours != 1 else ''}"
    return f"About {words}" if guessed else words


def hours_words(minutes: float) -> str:
    """Totals, rounded to the half hour: "12.5 hours"."""
    minutes = int(round(minutes or 0))
    if minutes < 60:
        return f"{minutes} minutes" if minutes != 1 else "1 minute"
    hours = round(minutes / 60 * 2) / 2
    return f"{hours:g} hour{'s' if hours != 1 else ''}"


# ---------------------------------------------------------------- candidates

@dataclass
class Candidate:
    category: str
    item_id: int
    title: str
    year: Optional[int] = None
    image: Optional[str] = None
    group: str = "saved"          # started, queued, saved
    unit: str = "whole"           # whole, episode, page, chapter, block
    step: float = 0.0             # minutes per unit
    done: int = 0                 # units already behind the member
    total: int = 1                # units in the whole title
    target: int = 1               # where this break should aim to get to (the first season of a new show)
    guessed: bool = False
    seasons: list = field(default_factory=list)

    @property
    def key(self) -> tuple[str, int]:
        return (self.category, self.item_id)


def _model(category: str):
    from .check_in import CATEGORIES as LIBRARY
    return LIBRARY[category][0]


def _done_field(category: str) -> str:
    from .check_in import CATEGORIES as LIBRARY
    return LIBRARY[category][1]


def _visible(user: models.User) -> list[str]:
    from .user_columns import VISIBLE, ensure_loaded
    ensure_loaded(user, VISIBLE)
    return [category for category in CATEGORIES
            if getattr(user, f"{category.replace('-', '_')}_visible", True) is not False]


def _image(category: str, row) -> Optional[str]:
    from . import title_pages
    kind = title_pages.LIBRARY_TO_KIND[category]
    image = title_pages._safe_image(getattr(row, title_pages.IMAGE_FIELD[kind], None))
    return image if image and image.startswith("https://") else None


def _year(category: str, row) -> Optional[int]:
    from . import title_pages
    return title_pages.item_year(title_pages.LIBRARY_TO_KIND[category], row)


def _clean_title(value) -> str:
    return " ".join((value or "").split())[:200]


def _refs(db: Session, user: models.User) -> dict[str, list[int]]:
    """Ids of every unfinished, titled row per visible format. Ids only."""
    from sqlalchemy import func as sql
    found = {}
    for category in _visible(user):
        model = _model(category)
        ids = db.query(model.id).filter(
            model.user_id == user.id, getattr(model, _done_field(category)) != True,  # noqa: E712
            model.title.isnot(None), sql.trim(model.title) != "",
        ).order_by(model.id).limit(POOL_PER_CATEGORY).all()
        found[category] = [item_id for (item_id,) in ids]
    return found


def _still_open(db: Session, user_id: int, refs: list[tuple[str, int]]) -> set[tuple[str, int]]:
    """Which of these library titles are the member's, unfinished and titled."""
    from sqlalchemy import func as sql
    wanted: dict[str, list[int]] = {}
    for category, item_id in refs:
        if category in CATEGORIES:
            wanted.setdefault(category, []).append(item_id)
    found = set()
    for category, ids in wanted.items():
        model = _model(category)
        for start in range(0, len(ids), 400):
            for (item_id,) in db.query(model.id).filter(
                    model.user_id == user_id, model.id.in_(ids[start:start + 400]),
                    getattr(model, _done_field(category)) != True,  # noqa: E712
                    model.title.isnot(None), sql.trim(model.title) != ""):
                found.add((category, item_id))
    return found


def _started(db: Session, user_id: int) -> dict[tuple[str, int], datetime]:
    """Titles the member is part-way through, with when they last moved, newest first later."""
    found = {}
    for category, item_id, updated in db.query(
            models.ProgressCheckpoint.category, models.ProgressCheckpoint.item_id,
            models.ProgressCheckpoint.updated_at).filter(
            models.ProgressCheckpoint.user_id == user_id, models.ProgressCheckpoint.position > 0).all():
        found[(category, item_id)] = updated or datetime(2000, 1, 1)
    for category, item_id, started in db.query(
            models.NextUpItem.category, models.NextUpItem.item_id, models.NextUpItem.started_at).filter(
            models.NextUpItem.user_id == user_id, models.NextUpItem.started_at.isnot(None)).all():
        key = (category, item_id)
        found[key] = max(found.get(key) or datetime(2000, 1, 1), started)
    return found


def _queue(db: Session, user_id: int) -> list[tuple[str, int]]:
    return [(category, item_id) for category, item_id in db.query(
        models.NextUpItem.category, models.NextUpItem.item_id).filter(
        models.NextUpItem.user_id == user_id, models.NextUpItem.started_at.is_(None)).order_by(
        models.NextUpItem.position, models.NextUpItem.id).all()]


def _mixed(refs: list[tuple[str, int]], seed: str) -> list[tuple[str, int]]:
    """A seeded shuffle that takes a different format each turn while there are formats left."""
    by_format: dict[str, list[tuple[str, int]]] = {}
    rng = random.Random(zlib.crc32(seed.encode()))
    for ref in sorted(refs):
        by_format.setdefault(ref[0], []).append(ref)
    for entries in by_format.values():
        rng.shuffle(entries)
    order = sorted(by_format)
    rng.shuffle(order)
    mixed = []
    while any(by_format.values()):
        for category in order:
            if by_format[category]:
                mixed.append(by_format[category].pop())
    return mixed


def _rows(db: Session, user_id: int, refs: list[tuple[str, int]]) -> dict[tuple[str, int], object]:
    wanted: dict[str, list[int]] = {}
    for category, item_id in refs:
        wanted.setdefault(category, []).append(item_id)
    found = {}
    for category, ids in wanted.items():
        model = _model(category)
        for start in range(0, len(ids), 400):
            for row in db.query(model).filter(model.user_id == user_id, model.id.in_(ids[start:start + 400])).all():
                found[(category, row.id)] = row
    return found


def _facts(db: Session, rows: dict) -> dict:
    from . import time_spent, title_metadata, title_pages
    keys = {}
    for (category, item_id), row in rows.items():
        kind = title_pages.LIBRARY_TO_KIND[category]
        keys[(category, item_id)] = title_metadata.cache_key(kind, title_pages.normalize(row.title or ""),
                                                            title_pages.item_year(kind, row))
    try:
        facts = time_spent._cached_facts(db, list(keys.values()))
    except Exception:
        db.rollback()
        facts = {}
    return {ref: facts.get(key, {}) for ref, key in keys.items()}


def _episode_state(db: Session, user_id: int, category: str, rows: list) -> dict[int, tuple[list, int, Optional[int]]]:
    """item id -> (season layout, episodes watched, episodes in the show) from the cached episode guide."""
    from . import episodes
    if not rows:
        return {}
    keys = {row.id: episodes.layout_key(category, row.title or "", row.year) for row in rows}
    layouts = episodes.cached_layouts(db, list(keys.values()))
    checkpoints = {entry.item_id: entry for entry in db.query(models.ProgressCheckpoint).filter(
        models.ProgressCheckpoint.user_id == user_id, models.ProgressCheckpoint.category == category,
        models.ProgressCheckpoint.item_id.in_(list(keys)))}
    found = {}
    for row in rows:
        layout = episodes.layout_for(row, category, layouts.get(keys[row.id], []))
        summary = episodes.summarize(layout, checkpoints.get(row.id))
        # watched is None when the member's place can't be read against the episode list (a specials
        # checkpoint, or a later season the list doesn't have). Such a show is never planned by episode,
        # and its checkpoint is never written from here.
        found[row.id] = (layout["seasons"], summary["watched"], summary["total"])
    return found


def _checkpoints(db: Session, user_id: int, refs: Iterable[tuple[str, int]]) -> dict[tuple[str, int], object]:
    refs = list(refs)
    if not refs:
        return {}
    found = {}
    by_category: dict[str, list[int]] = {}
    for category, item_id in refs:
        by_category.setdefault(category, []).append(item_id)
    for category, ids in by_category.items():
        for entry in db.query(models.ProgressCheckpoint).filter(
                models.ProgressCheckpoint.user_id == user_id, models.ProgressCheckpoint.category == category,
                models.ProgressCheckpoint.item_id.in_(ids)):
            found[(category, entry.item_id)] = entry
    return found


def candidate_for(category: str, row, facts: dict, group: str, episode_state=None, checkpoint=None,
                  done_blocks: int = 0) -> Optional[Candidate]:
    """How much of one library title is left, in units a day can hold. None when nothing is left."""
    from . import time_spent
    title = _clean_title(row.title)
    if not title:
        return None
    base = {"category": category, "item_id": row.id, "title": title, "year": _year(category, row),
            "image": _image(category, row), "group": group}
    if category in ("movies", "music"):
        minutes, guessed = time_spent.full_minutes(category, row, facts)
        return Candidate(unit="whole", step=max(1.0, float(minutes)), done=0, total=1, target=1, guessed=guessed, **base)
    if category in ("tv-shows", "anime"):
        seasons, watched, total = episode_state or ([], 0, None)
        if watched is None:
            return None
        per_episode = time_spent.parse_minutes(facts.get("Episode length"))
        guessed = per_episode is None or total is None
        step = per_episode or (time_spent.TV_EPISODE_MINUTES if category == "tv-shows" else time_spent.ANIME_EPISODE_MINUTES)
        if total is None:
            total = time_spent.parse_count(facts.get("Episodes")) or (
                (row.seasons or 1) * time_spent.TV_EPISODES if category == "tv-shows" and getattr(row, "seasons", None)
                else time_spent.TV_EPISODES if category == "tv-shows" else time_spent.ANIME_EPISODES)
        total = max(1, min(int(total), time_spent.MAX_COUNT))
        watched = max(0, min(int(watched or 0), total))
        if watched >= total:
            return None
        target = total
        numbered = [entry for entry in seasons if entry.get("number") is not None]
        if group == "saved" and watched == 0 and len(numbered) > 1:
            target = min(total, numbered[0]["episodes"])  # a new show: its first season
        return Candidate(unit="episode", step=float(step), done=watched, total=total, target=target,
                         guessed=guessed, seasons=list(seasons), **base)
    if category == "manga":
        minutes, guessed = time_spent.full_minutes(category, row, facts)
        chapters = max(1, round(minutes / time_spent.MANGA_CHAPTER_MINUTES))
        at = checkpoint.position if checkpoint is not None and checkpoint.unit == "chapter" and checkpoint.position else 0
        if at >= chapters:
            return None
        return Candidate(unit="chapter", step=float(time_spent.MANGA_CHAPTER_MINUTES), done=int(at), total=chapters,
                         target=chapters, guessed=guessed, **base)
    if category == "books" and (checkpoint is None or checkpoint.unit in (None, "page") or not checkpoint.position):
        pages = time_spent.parse_count(facts.get("Pages"))
        guessed = pages is None
        pages = pages or time_spent.BOOK_PAGES
        at = checkpoint.position if checkpoint is not None and checkpoint.unit == "page" and checkpoint.position else 0
        if at >= pages:
            return None
        return Candidate(unit="page", step=time_spent.MINUTES_PER_PAGE, done=int(at), total=pages, target=pages,
                         guessed=guessed, **base)
    if category in ("books", "video-games", "audiobooks"):
        minutes, guessed = time_spent.full_minutes(category, row, facts)
        if category != "video-games":
            behind, _ = time_spent.partial_minutes(category, row, facts, None, checkpoint)
        else:
            behind = 0.0
        blocks = max(1, math.ceil(minutes / BLOCK))
        done = max(int(behind // BLOCK), int(done_blocks))
        if done >= blocks:
            return None
        return Candidate(unit="block", step=float(BLOCK), done=done, total=blocks, target=blocks, guessed=guessed, **base)
    return None


def candidates(db: Session, user: models.User, plan: Optional[models.BreakPlan] = None, seed: str = "",
               exclude: Iterable[tuple[str, int]] = (), games: bool = True,
               first: Iterable[tuple[str, int]] = ()) -> list[Candidate]:
    """Everything the plan could hold, best first: part-way through, Up next, then saved titles in a mix.

    ``first`` are titles the member picked from a plan someone shared with them. They go ahead of
    everything else, and like the Up next queue they don't have to finish over the break.
    """
    refs = _refs(db, user)
    unfinished = {(category, item_id) for category, ids in refs.items() for item_id in ids}
    skip = set(exclude)
    if plan is not None:
        skip |= set(left_out(plan))
    if not games:
        skip |= {ref for ref in unfinished if ref[0] == "video-games"}
    visible = set(refs)
    started = _started(db, user.id)
    started_all = sorted((ref for ref in started if ref[0] in visible and ref not in skip
                          and (games or ref[0] != "video-games")),
                         key=lambda ref: started[ref], reverse=True)
    queued_all = [ref for ref in _queue(db, user.id) if ref[0] in visible and ref not in skip and ref not in started
                  and (games or ref[0] != "video-games")]
    # The saved pool stops at POOL_PER_CATEGORY rows a format, so a big library's newer titles can fall outside
    # it. What the member is part-way through or queued is checked on its own.
    picked = [ref for ref in dict.fromkeys(first) if ref[0] in visible and ref not in skip
              and (games or ref[0] != "video-games")][:MAX_PICKS]
    unfinished |= _still_open(db, user.id, [ref for ref in started_all[:60] + queued_all[:60] + picked
                                            if ref not in unfinished])
    picked = [ref for ref in picked if ref in unfinished]
    chosen = set(picked)
    started_refs = [ref for ref in started_all if ref in unfinished and ref not in chosen][:30]
    queued = [ref for ref in queued_all if ref in unfinished and ref not in chosen][:30]
    taken = set(started_refs) | set(queued) | chosen
    saved_pool = [ref for ref in unfinished if ref not in skip and ref not in taken]
    saved = _mixed(saved_pool, f"{user.id}:{seed}")[:SAVED_LOOKED_AT]
    ordered = [(ref, "started" if ref in started else "queued") for ref in picked] + \
              [(ref, "started") for ref in started_refs] + [(ref, "queued") for ref in queued] + \
              [(ref, "saved") for ref in saved]
    rows = _rows(db, user.id, [ref for ref, _ in ordered])
    facts = _facts(db, rows)
    episode_rows: dict[str, list] = {}
    for (category, _item_id), row in rows.items():
        if category in ("tv-shows", "anime"):
            episode_rows.setdefault(category, []).append(row)
    episode_state = {}
    for category, items in episode_rows.items():
        for item_id, value in _episode_state(db, user.id, category, items).items():
            episode_state[(category, item_id)] = value
    checkpoints = _checkpoints(db, user.id, [ref for ref in rows if ref[0] in ("books", "manga", "audiobooks")])
    blocks_done = _plan_blocks_done(plan) if plan is not None else {}
    found = []
    for ref, group in ordered:
        row = rows.get(ref)
        if row is None:
            continue
        try:
            candidate = candidate_for(ref[0], row, facts.get(ref, {}), group, episode_state.get(ref),
                                      checkpoints.get(ref), blocks_done.get(ref, 0))
        except Exception:
            candidate = None
        if candidate is not None:
            found.append(candidate)
    return found


# ---------------------------------------------------------------- filling the days

@dataclass
class Day:
    day: date
    budget: int
    free: float
    count: int = 0


def _episode_label(seasons: list, first: int, last: int) -> str:
    from . import episodes
    numbered = [entry for entry in seasons if entry.get("number") is not None]
    if len(numbered) > 1:
        start, end = episodes.locate(seasons, first), episodes.locate(seasons, last)
        if start and end and start[0] is not None and end[0] is not None:
            if start[0] == end[0]:
                if start[1] == end[1]:
                    return f"Season {start[0]}, episode {start[1]}"
                return f"Season {start[0]}, episodes {start[1]}–{end[1]}"
            return f"S{start[0]} E{start[1]} to S{end[0]} E{end[1]}"
    return f"Episode {first}" if first == last else f"Episodes {first}–{last}"


def chunk_label(candidate: Candidate, first: int, last: int) -> str:
    unit = candidate.unit
    if unit == "whole":
        return f"{VERB[candidate.category]} it"
    if unit == "episode":
        return _episode_label(candidate.seasons, first, last)
    if unit == "page":
        if first == 1 and last >= candidate.total:
            return "The whole book"
        if last >= candidate.total:
            return f"Page {first} to the end"
        return f"Pages {first}–{last}"
    if unit == "chapter":
        if first == 1 and last >= candidate.total:
            return "All of it"
        return f"Chapter {first}" if first == last else f"Chapters {first}–{last}"
    minutes = (last - first + 1) * BLOCK
    verb = BLOCK_VERB.get(candidate.category, "Spend")
    words = hours_words(minutes)
    if last >= candidate.total and candidate.category != "video-games":
        return f"{verb} to the end (about {words})"
    return f"{verb} for about {words}"


def what_line(entry: dict) -> str:
    """The line under a title, such as "Episodes 2-3 · 1h 50m". A game's label already says how long."""
    if entry.get("unit") == "block" or not entry.get("length"):
        return entry["label"]
    return f"{entry['label']} · {entry['length']}"


def _chunk(candidate: Candidate, day: date, first: int, last: int, minutes: float) -> dict:
    return {"day": day, "category": candidate.category, "item_id": candidate.item_id, "title": candidate.title,
            "year": candidate.year, "image": candidate.image, "unit": candidate.unit, "first": first, "last": last,
            "total": candidate.total, "minutes": int(round(minutes)), "label": chunk_label(candidate, first, last),
            "guessed": candidate.guessed}


def _place_whole(days: list[Day], candidate: Candidate) -> list[dict]:
    """A film or album goes whole onto the day with the most time left that holds it."""
    length = candidate.step
    for slack in (1.0, 0.85):
        fits = [day for day in days if day.count < MAX_PER_DAY and day.budget and day.free >= length * slack]
        if fits:
            day = max(fits, key=lambda entry: (entry.free, -entry.day.toordinal()))
            day.free -= length
            day.count += 1
            return [_chunk(candidate, day.day, 1, 1, length)]
    return []


def _min_chunk(candidate: Candidate) -> float:
    """The shortest stretch worth a slot on a day (unless it's what's left of the title)."""
    if candidate.unit == "block":
        return 60
    if candidate.unit in ("page", "chapter"):
        return 30
    return MIN_CHUNK


def _place_split(days: list[Day], candidate: Candidate, limit_units: Optional[int] = None) -> tuple[list[dict], bool]:
    """Stretches of the title over the days in date order. (chunks, reached the target). Changes ``days``."""
    goal = candidate.target if limit_units is None else min(candidate.target, candidate.done + limit_units)
    left = goal - candidate.done
    first = candidate.done + 1
    chunks = []
    step = max(0.1, candidate.step)
    smallest = _min_chunk(candidate)
    for day in days:
        if left <= 0:
            break
        if day.count >= MAX_PER_DAY or not day.budget or day.free < step:
            continue
        if candidate.unit != "episode" and day.free < min(left * step, max(smallest, day.budget * 0.4)):
            continue  # a book or a game wants a real sitting, not the scraps of a full day
        units = min(left, int(day.free // step))
        if units <= 0:
            continue
        rest = left - units
        if 0 < rest and rest * step <= 30 and (units + rest) * step <= day.free + 15:
            units += rest  # don't leave a scrap for the next day
            rest = 0
        if 0 < rest and rest * step < smallest:
            # Hand the next day a real sitting (90 + 60 minutes, not 120 + 30) when this day keeps one too.
            give = math.ceil((smallest - rest * step) / step)
            if (units - give) * step >= smallest:
                units -= give
        minutes = units * step
        if minutes < smallest and units < left:
            continue
        chunks.append(_chunk(candidate, day.day, first, first + units - 1, minutes))
        day.free -= minutes
        day.count += 1
        first += units
        left -= units
    return chunks, left <= 0


def _copy(days: list[Day]) -> list[Day]:
    return [Day(day.day, day.budget, day.free, day.count) for day in days]


def _limit(candidate: Candidate, total_budget: int) -> Optional[int]:
    """Most units one title may take: a game, or a long title that can't finish, leaves room for others."""
    if candidate.category == "video-games":
        share = GAME_SHARE if candidate.group == "saved" else 0.5
        return max(1, int(total_budget * share // BLOCK))
    left_minutes = (candidate.target - candidate.done) * candidate.step
    if candidate.group != "saved" and left_minutes > total_budget * 0.85:
        return max(1, int(total_budget * 0.6 // max(0.1, candidate.step)))
    return None


def _layout(days: list[Day], chosen: list[Candidate], total_budget: int,
            before: dict[tuple[str, int], tuple[bool, int]]) -> Optional[tuple[list[dict], list[Day], dict]]:
    """Lay the chosen titles out: films and albums first onto the roomiest days, then the long titles in
    priority order from the first day. None when something chosen no longer fits as well as it did."""
    days = _copy(days)
    placed: dict[tuple[str, int], list[dict]] = {}
    for candidate in sorted((entry for entry in chosen if entry.unit == "whole"), key=lambda entry: -entry.step):
        chunks = _place_whole(days, candidate)
        if not chunks:
            return None
        placed[candidate.key] = chunks
    outcome = {}
    for candidate in chosen:
        if candidate.unit == "whole":
            outcome[candidate.key] = (True, 1)
            continue
        chunks, reached = _place_split(days, candidate, _limit(candidate, total_budget))
        units = sum(chunk["last"] - chunk["first"] + 1 for chunk in chunks)
        if not chunks:
            return None
        if not reached and candidate.group == "saved" and candidate.category != "video-games":
            return None
        if not reached and units * candidate.step < 30:
            return None
        placed[candidate.key] = chunks
        outcome[candidate.key] = (reached, units)
    for key, (reached, units) in before.items():
        now_reached, now_units = outcome.get(key, (False, 0))
        if (reached and not now_reached) or now_units < units:
            return None  # a title already in can't lose out to a later one
    order = {candidate.key: index for index, candidate in enumerate(chosen)}
    chunks = sorted((chunk for entries in placed.values() for chunk in entries),
                    key=lambda chunk: (chunk["day"], order[(chunk["category"], chunk["item_id"])], chunk["first"]))
    return chunks, days, outcome


def fill_days(days: list[Day], pool: list[Candidate], *, max_titles: int, titles_in: int = 0,
              games_in: int = 0) -> list[dict]:
    """Chunks for as many candidates as fit, best first. Each new title is tried by laying the whole set out
    again, so a film can still find an evening after a long show is spread over the break."""
    total_budget = sum(day.budget for day in days)
    chosen: list[Candidate] = []
    outcome: dict = {}
    chunks: list[dict] = []
    left = _copy(days)
    games = games_in
    for candidate in pool:
        if titles_in + len(chosen) >= max_titles or sum(max(0.0, day.free) for day in left) < 20:
            break
        if candidate.category == "video-games" and candidate.group == "saved" and (games >= 1 or total_budget < 360):
            continue  # one new game at most, and none on a short break
        tried = _layout(days, chosen + [candidate], total_budget, outcome)
        if tried is None:
            continue
        chunks, left, outcome = tried
        chosen.append(candidate)
        games += candidate.category == "video-games"
    days[:] = left
    return chunks


def max_titles_for(day_count: int) -> int:
    return max(3, min(16, day_count * 3 + 2))


# ---------------------------------------------------------------- the plan's rows

def minutes_by_day(plan: models.BreakPlan) -> dict[date, int]:
    try:
        raw = json.loads(plan.day_minutes or "{}")
    except ValueError:
        raw = {}
    found = {}
    for day in days_of(plan.starts_on, plan.ends_on):
        found[day] = clean_minutes(raw.get(day.isoformat(), DEFAULT_MINUTES))
    return found


def left_out(plan: models.BreakPlan) -> list[tuple[str, int]]:
    try:
        raw = json.loads(plan.left_out or "[]")
    except ValueError:
        return []
    found = []
    for entry in raw if isinstance(raw, list) else []:
        category, _, item_id = str(entry).partition(":")
        if category in CATEGORIES and item_id.isdigit():
            found.append((category, int(item_id)))
    return found


def _leave_out(plan: models.BreakPlan, ref: tuple[str, int]) -> None:
    current = left_out(plan)
    if ref not in current:
        current.append(ref)
    plan.left_out = json.dumps([f"{category}:{item_id}" for category, item_id in current[-200:]])


def _plan_blocks_done(plan: models.BreakPlan) -> dict[tuple[str, int], int]:
    found = {}
    for item in plan.items:
        if item.unit == "block" and item.done_at is not None:
            ref = (item.category, item.item_id)
            found[ref] = max(found.get(ref, 0), item.last)
    return found


def items_of(db: Session, plan: models.BreakPlan) -> list[models.BreakPlanItem]:
    return db.query(models.BreakPlanItem).filter(models.BreakPlanItem.plan_id == plan.id).order_by(
        models.BreakPlanItem.day, models.BreakPlanItem.position, models.BreakPlanItem.id).all()


def _store(db: Session, plan: models.BreakPlan, chunks: list[dict], added: bool = False) -> int:
    if not chunks:
        return 0
    existing = items_of(db, plan)
    room = MAX_ITEMS - len(existing)
    positions: dict[date, int] = {}
    for item in existing:
        positions[item.day] = max(positions.get(item.day, 0), item.position + 1)
    stored = 0
    for chunk in chunks[:max(0, room)]:
        position = positions.get(chunk["day"], 0)
        positions[chunk["day"]] = position + 1
        db.add(models.BreakPlanItem(plan_id=plan.id, user_id=plan.user_id, position=position, added=added,
                                    created_at=_now(), **chunk))
        stored += 1
    return stored


def _open_days(db: Session, plan: models.BreakPlan, today: date, only: Optional[date] = None) -> list[Day]:
    """Days from today on with the time not yet planned."""
    budgets = minutes_by_day(plan)
    planned: dict[date, list[models.BreakPlanItem]] = {}
    for item in items_of(db, plan):
        planned.setdefault(item.day, []).append(item)
    days = []
    for day, budget in budgets.items():
        if day < today or (only is not None and day != only):
            continue
        used = sum(item.minutes for item in planned.get(day, []))
        days.append(Day(day, budget, budget - used, len(planned.get(day, []))))
    return days


def _titles_waiting(db: Session, plan: models.BreakPlan) -> set[tuple[str, int]]:
    """Titles with a stretch still to do on the plan: they aren't offered again."""
    return {(item.category, item.item_id) for item in items_of(db, plan) if item.done_at is None}


def fill(db: Session, user: models.User, plan: models.BreakPlan, today: date, only: Optional[date] = None,
         first: Iterable[tuple[str, int]] = ()) -> int:
    """Put titles into the free time from today on. Returns how many stretches went in. Doesn't commit."""
    days = _open_days(db, plan, today, only)
    if not days:
        return 0
    waiting = _titles_waiting(db, plan)
    pool = candidates(db, user, plan, seed=f"{plan.id}:{plan.seed}", exclude=waiting, games=plan.games, first=first)
    titles_in = len(waiting)
    games_in = len({ref for ref in waiting if ref[0] == "video-games"})
    chunks = fill_days(days, pool, max_titles=max_titles_for(len(minutes_by_day(plan))), titles_in=titles_in,
                       games_in=games_in)
    return _store(db, plan, chunks)


# ---------------------------------------------------------------- making and changing a plan

def active(db: Session, user_id: int, today: date) -> Optional[models.BreakPlan]:
    """The member's current plan: not cancelled, and not over for longer than the wrap-up shows."""
    return db.query(models.BreakPlan).filter(
        models.BreakPlan.user_id == user_id, models.BreakPlan.status == "active",
        models.BreakPlan.ends_on >= today - timedelta(days=WRAP_DAYS),
    ).order_by(models.BreakPlan.starts_on.desc(), models.BreakPlan.id.desc()).first()


def owned(db: Session, user_id: int, plan_id: int) -> models.BreakPlan:
    plan = db.query(models.BreakPlan).filter(models.BreakPlan.id == plan_id, models.BreakPlan.user_id == user_id,
                                             models.BreakPlan.status == "active").first()
    if plan is None:
        raise BreakError("That plan isn't here anymore.", 404)
    return plan


def _check_dates(starts_on: date, ends_on: date, today: date) -> None:
    if ends_on < starts_on:
        raise BreakError("The last day has to be on or after the first day.", 422)
    if starts_on < today:
        raise BreakError("Pick days from today on.", 422)
    if (starts_on - today).days > START_WITHIN_DAYS:
        raise BreakError(f"Plan a break that starts in the next {START_WITHIN_DAYS} days.", 422)
    if (ends_on - starts_on).days + 1 > MAX_DAYS:
        raise BreakError(f"A plan can cover up to {MAX_DAYS} days.", 422)


def _clean_name(value: Optional[str], fallback: str) -> str:
    name = " ".join((value or "").split())[:60]
    return name or fallback


def create(db: Session, user: models.User, *, starts_on: date, ends_on: date, minutes: dict[str, int],
           today: date, tz_minutes: int = 0, name: Optional[str] = None, preset_key: Optional[str] = None,
           games: bool = True, emails: bool = False, picks: Iterable[tuple[str, int]] = ()) -> models.BreakPlan:
    """A new plan, filled. ``picks`` are library titles to put in first (titles taken from a shared plan);
    they count as put there by hand, so "Try another mix" leaves them where they are."""
    _check_dates(starts_on, ends_on, today)
    current = active(db, user.id, today)
    if current is not None and current.ends_on >= today:
        raise BreakError("You already have a break planned. Change that one, or start over.", 409)
    chosen = preset(preset_key, today) if preset_key else None
    fallback = chosen["name"] if chosen and chosen["starts_on"] == starts_on and chosen["ends_on"] == ends_on else (
        "Your weekend" if (ends_on - starts_on).days <= 2 and starts_on.weekday() >= 4 else "Your break")
    days = days_of(starts_on, ends_on)
    clean = {day.isoformat(): clean_minutes(minutes.get(day.isoformat(), DEFAULT_MINUTES)) for day in days}
    if not any(clean.values()):
        raise BreakError("Give at least one day some time.", 422)
    if emails and not (user.email and user.is_verified):
        emails = False
    now = _now()
    if current is not None:
        current.status = "cancelled"  # a finished break's wrap-up gives way to the next one
    plan = models.BreakPlan(user_id=user.id, name=_clean_name(name, fallback),
                            preset=(chosen["key"] if chosen else None), starts_on=starts_on, ends_on=ends_on,
                            tz_minutes=clamp_tz(tz_minutes), day_minutes=json.dumps(clean), games=bool(games),
                            seed=0, left_out="[]", status="active", emails=bool(emails), created_at=now,
                            updated_at=now)
    db.add(plan)
    db.flush()
    picks = list(dict.fromkeys(picks))[:MAX_PICKS]
    fill(db, user, plan, today, first=picks)
    if picks:
        wanted = set(picks)
        db.flush()
        for item in items_of(db, plan):
            if (item.category, item.item_id) in wanted:
                item.added = True
    db.commit()
    count("break_created")
    return plan


def update(db: Session, user: models.User, plan: models.BreakPlan, today: date, *, minutes: Optional[dict] = None,
           ends_on: Optional[date] = None, name: Optional[str] = None, games: Optional[bool] = None,
           emails: Optional[bool] = None) -> None:
    """Change the times, the last day, the name or the switches. More time gets filled; less time keeps what's planned."""
    refill = False
    if ends_on is not None and ends_on != plan.ends_on:
        if ends_on < plan.starts_on or (ends_on - plan.starts_on).days + 1 > MAX_DAYS:
            raise BreakError(f"A plan can cover up to {MAX_DAYS} days.", 422)
        if ends_on < today:
            raise BreakError("The last day can't be in the past.", 422)
        if ends_on < plan.ends_on:
            for item in items_of(db, plan):
                if item.day > ends_on and item.done_at is None:
                    db.delete(item)
                elif item.day > ends_on:
                    item.day = ends_on  # ticked already: it stays on the board, on the new last day
        plan.ends_on = ends_on
        refill = True
    if minutes is not None:
        current = {day.isoformat(): value for day, value in minutes_by_day(plan).items()}
        for key, value in minutes.items():
            if key in current:
                try:
                    if date.fromisoformat(key) < today:
                        continue
                except ValueError:
                    continue
                if clean_minutes(value) > current[key]:
                    refill = True
                current[key] = clean_minutes(value)
        plan.day_minutes = json.dumps(current)
    else:
        current = {day.isoformat(): value for day, value in minutes_by_day(plan).items()}
        plan.day_minutes = json.dumps(current)
    if name is not None:
        plan.name = _clean_name(name, plan.name)
    if games is not None:
        if plan.games and not games:
            for item in items_of(db, plan):
                if item.category == "video-games" and item.done_at is None and not item.added and item.day >= today:
                    db.delete(item)
        refill = refill or (games and not plan.games)
        plan.games = bool(games)
    if emails is not None:
        if emails and not (user.email and user.is_verified):
            raise BreakError("Confirm your email address first.", 422)
        plan.emails = bool(emails)
    plan.updated_at = _now()
    db.flush()
    if refill:
        fill(db, user, plan, today)
    db.commit()


def refill(db: Session, user: models.User, plan: models.BreakPlan, today: date, only: Optional[date] = None) -> int:
    added = fill(db, user, plan, today, only)
    plan.updated_at = _now()
    db.commit()
    return added


def reshuffle(db: Session, user: models.User, plan: models.BreakPlan, today: date) -> int:
    """"Try another mix": everything not ticked and not put here by the member, from today on, gets drawn again."""
    for item in items_of(db, plan):
        if item.done_at is None and not item.added and item.day >= today:
            db.delete(item)
    plan.seed = (plan.seed or 0) + 1
    db.flush()
    added = fill(db, user, plan, today)
    plan.updated_at = _now()
    db.commit()
    count("break_reshuffled")
    return added


def cancel(db: Session, plan: models.BreakPlan) -> None:
    plan.status = "cancelled"
    plan.share_token = None
    plan.updated_at = _now()
    db.commit()


def _item(db: Session, plan: models.BreakPlan, item_id: int) -> models.BreakPlanItem:
    item = db.query(models.BreakPlanItem).filter(models.BreakPlanItem.id == item_id,
                                                 models.BreakPlanItem.plan_id == plan.id).first()
    if item is None:
        raise BreakError("That isn't on your plan anymore.", 404)
    return item


def move(db: Session, plan: models.BreakPlan, item_id: int, day: date) -> None:
    item = _item(db, plan, item_id)
    if not plan.starts_on <= day <= plan.ends_on:
        raise BreakError("Pick a day of your break.", 422)
    if item.day != day:
        last = db.query(func.max(models.BreakPlanItem.position)).filter(
            models.BreakPlanItem.plan_id == plan.id, models.BreakPlanItem.day == day).scalar()
        item.day = day
        item.position = (last if last is not None else -1) + 1
    plan.updated_at = _now()
    db.commit()


def remove(db: Session, user: models.User, plan: models.BreakPlan, item_id: int, today: date,
           swap: bool = False) -> int:
    """Take a title's stretches still to do off the plan. It stays off when free time is filled again (adding
    it by hand brings it back). With ``swap`` the time it leaves gets filled straight away."""
    item = _item(db, plan, item_id)
    ref = (item.category, item.item_id)
    day = item.day
    for other in items_of(db, plan):
        if (other.category, other.item_id) == ref and other.done_at is None:
            db.delete(other)
    _leave_out(plan, ref)
    plan.updated_at = _now()
    db.flush()
    added = fill(db, user, plan, max(today, day)) if swap else 0
    db.commit()
    if swap:
        count("break_swapped")
    return added


SEARCH_LIMIT = 40


def _search_refs(db: Session, user: models.User, query: str) -> list[tuple[str, int]]:
    """Unfinished titles whose name contains ``query`` (as typed, no wildcards), in every format shown."""
    from sqlalchemy import func as sql
    needle = " ".join(query.split()).lower()[:80]
    found = []
    for category in _visible(user):
        model = _model(category)
        found += [(category, item_id) for (item_id,) in db.query(model.id).filter(
            model.user_id == user.id, getattr(model, _done_field(category)) != True,  # noqa: E712
            sql.lower(model.title).contains(needle, autoescape=True),
        ).order_by(model.title, model.id).limit(SEARCH_LIMIT)]
    return found


def addable(db: Session, user: models.User, plan: models.BreakPlan, limit: int = 48,
            query: Optional[str] = None) -> list[dict]:
    """Unfinished titles the member could put on the plan by hand, A to Z within each format.

    Without a search every format gets a share of ``limit`` (the panel shows that many), so a long film list
    can't push the shows out; a search looks through the whole library."""
    waiting = _titles_waiting(db, plan)
    if query and query.strip():
        refs = [ref for ref in _search_refs(db, user, query) if ref not in waiting]
    else:
        refs = [(category, item_id) for category, ids in _refs(db, user).items() for item_id in ids
                if (category, item_id) not in waiting]
    rows = _rows(db, user.id, refs[:1000])
    by_format: dict[str, list[dict]] = {}
    for (category, item_id), row in rows.items():
        title = _clean_title(row.title)
        if title:
            by_format.setdefault(category, []).append({
                "category": category, "id": item_id, "title": title, "label": LABELS[category],
                "year": _year(category, row), "image": _image(category, row)})
    for entries in by_format.values():
        entries.sort(key=lambda entry: entry["title"].lower())
    if query and query.strip():
        found = [entry for category in CATEGORIES for entry in by_format.get(category, [])]
        found.sort(key=lambda entry: (not entry["title"].lower().startswith(" ".join(query.split()).lower()),
                                      CATEGORIES.index(entry["category"]), entry["title"].lower()))
        return found[:SEARCH_LIMIT]
    share = max(6, limit // max(1, len(by_format)))
    found = [entry for category in CATEGORIES for entry in by_format.get(category, [])[:share]]
    return found[:limit]


def add(db: Session, user: models.User, plan: models.BreakPlan, category: str, item_id: int, day: date,
        today: date) -> int:
    """Put one of the member's titles on the plan from ``day`` on, in the time left (at least one stretch on that day)."""
    if category not in CATEGORIES:
        raise BreakError("That kind of title can't go on a break plan.", 422)
    if not plan.starts_on <= day <= plan.ends_on or day < today:
        raise BreakError("Pick a day of your break from today on.", 422)
    if (category, item_id) in _titles_waiting(db, plan):
        raise BreakError("That's already on your plan.", 409)
    if len({(item.category, item.item_id) for item in items_of(db, plan) if item.added}) >= MAX_ADDED_TITLES:
        raise BreakError("That's a lot for one break. Take something off first.", 409)
    model = _model(category)
    row = db.query(model).filter(model.id == item_id, model.user_id == user.id).first()
    if row is None:
        raise BreakError("That title isn't in your library.", 404)
    if getattr(row, _done_field(category), False):
        raise BreakError("You've already finished that one.", 409)
    facts = _facts(db, {(category, item_id): row}).get((category, item_id), {})
    episode_state = None
    checkpoint = None
    if category in ("tv-shows", "anime"):
        episode_state = _episode_state(db, user.id, category, [row]).get(row.id)
        if episode_state is not None and episode_state[1] is None:
            raise BreakError("We don't have an episode list that shows where you are in that one, so it can't "
                             "go on the plan by episode yet.", 409)
    else:
        checkpoint = _checkpoints(db, user.id, [(category, item_id)]).get((category, item_id))
    candidate = candidate_for(category, row, facts, "added", episode_state, checkpoint,
                              _plan_blocks_done(plan).get((category, item_id), 0))
    if candidate is None:
        raise BreakError("There's nothing left of that one to plan.", 409)
    current = left_out(plan)
    if (category, item_id) in current:
        plan.left_out = json.dumps([f"{c}:{i}" for c, i in current if (c, i) != (category, item_id)])
    days = [entry for entry in _open_days(db, plan, today) if entry.day >= day]
    if candidate.unit == "whole":
        chunks = [_chunk(candidate, day, 1, 1, candidate.step)]
    else:
        chunks, _ = _place_split(days, candidate)
        if not chunks or chunks[0]["day"] != day:
            units = max(1, min(candidate.target - candidate.done, math.ceil(60 / max(0.1, candidate.step))))
            first = candidate.done + 1
            chunks = [_chunk(candidate, day, first, first + units - 1, units * candidate.step)]
    stored = _store(db, plan, chunks, added=True)
    if not stored:
        raise BreakError("That plan is full. Take something off first.", 409)
    plan.updated_at = _now()
    db.commit()
    count("break_added")
    return stored


# ---------------------------------------------------------------- ticking things off

def _library_row(db: Session, user_id: int, category: str, item_id: int):
    if category not in CATEGORIES:
        return None
    model = _model(category)
    return db.query(model).filter(model.id == item_id, model.user_id == user_id).first()


def _place(entry) -> Optional[dict]:
    """The checkpoint's content, or None when there is none (never set, or cleared)."""
    if entry is None or entry.unit is None:
        return None
    return {"unit": entry.unit, "position": entry.position, "season": entry.season}


def _move_checkpoint(db: Session, user: models.User, item: models.BreakPlanItem) -> bool:
    """Move the library checkpoint forward to the end of this stretch. Never back, and never when the member's
    place can't be read (a specials checkpoint, a season the episode list doesn't have, another unit).

    Commits when it writes, and keeps what the checkpoint was in ``item.undo_progress`` so unticking can put
    it back while nobody has changed it since."""
    from fastapi import HTTPException
    from . import episodes
    from .progress import _write_progress
    entry = db.query(models.ProgressCheckpoint).filter_by(user_id=user.id, category=item.category,
                                                         item_id=item.item_id).first()
    revision = entry.revision if entry is not None else 0
    note = entry.note if entry is not None and entry.unit is not None else None
    before = _place(entry)
    if item.unit == "episode":
        if entry is not None and entry.unit is not None and entry.unit != "episode":
            return False
        row = _library_row(db, user.id, item.category, item.item_id)
        if row is None:
            return False
        seasons, watched, _total = _episode_state(db, user.id, item.category, [row]).get(row.id, ([], 0, None))
        if watched is None or watched >= item.last:
            return False
        numbered = [season for season in seasons if season.get("number") is not None]
        season, position = None, item.last
        if numbered and len(numbered) == len(seasons):
            place = episodes.locate(seasons, item.last)
            if place is None:
                return False
            season, position = place
        values = {"unit": "episode", "position": position, "season": season, "note": note}
    elif item.unit in ("page", "chapter"):
        if entry is not None and entry.unit is not None and entry.unit != item.unit:
            return False
        if entry is not None and entry.unit == item.unit and (entry.position or 0) >= item.last:
            return False
        values = {"unit": item.unit, "position": item.last, "season": None, "note": note}
    else:
        return False
    try:
        written = _write_progress(db, user.id, item.category, item.item_id, revision, values)
    except HTTPException:
        db.rollback()
        return False
    item.undo_progress = json.dumps({"before": before, "revision": written["revision"]})
    db.commit()
    return True


def _put_back(db: Session, user: models.User, item: models.BreakPlanItem) -> bool:
    """Undo this stretch's own checkpoint write, only if the checkpoint is still exactly what the tick left."""
    from fastapi import HTTPException
    from .progress import _write_progress
    try:
        saved = json.loads(item.undo_progress or "null")
    except ValueError:
        saved = None
    if not isinstance(saved, dict) or not isinstance(saved.get("revision"), int):
        return False
    entry = db.query(models.ProgressCheckpoint).filter_by(user_id=user.id, category=item.category,
                                                         item_id=item.item_id).first()
    if entry is None or entry.revision != saved["revision"]:
        return False
    before = saved.get("before")
    if isinstance(before, dict) and before.get("unit") in ("episode", "page", "chapter") \
            and isinstance(before.get("position"), int):
        values = {"unit": before["unit"], "position": before["position"],
                  "season": before.get("season") if isinstance(before.get("season"), int) else None,
                  "note": entry.note if entry.unit is not None else None}
    else:
        values = {"unit": None, "position": None, "season": None, "note": None}
    try:
        _write_progress(db, user.id, item.category, item.item_id, saved["revision"], values)
    except HTTPException:
        db.rollback()
        return False
    return True


def _library_past(db: Session, user: models.User, item: models.BreakPlanItem) -> bool:
    """The library already has the member at or beyond the end of this stretch (so the plan ticks it)."""
    if item.unit == "episode":
        row = _library_row(db, user.id, item.category, item.item_id)
        if row is None:
            return False
        _seasons, watched, _total = _episode_state(db, user.id, item.category, [row]).get(row.id, ([], 0, None))
        return (watched or 0) >= item.last
    if item.unit in ("page", "chapter"):
        entry = db.query(models.ProgressCheckpoint).filter_by(user_id=user.id, category=item.category,
                                                             item_id=item.item_id).first()
        return entry is not None and entry.unit == item.unit and (entry.position or 0) >= item.last
    return False


def _ending(db: Session, user: models.User, item: models.BreakPlanItem, row) -> tuple[bool, bool]:
    """(this stretch ends the title, and we know that rather than guess it).

    The plan was made from the lengths known then. A show may have gained a season since, and a book's page
    count may have been looked up; a length that is still a guess never finishes a title on its own."""
    from . import time_spent
    ref = (item.category, item.item_id)
    if item.unit == "whole":
        return True, True
    if item.unit == "episode":
        _seasons, _watched, total = _episode_state(db, user.id, item.category, [row]).get(row.id, ([], 0, None))
        if total is None:
            total = time_spent.parse_count(_facts(db, {ref: row}).get(ref, {}).get("Episodes"))
        if total is None:
            return item.last >= item.total, False
        total = max(1, min(int(total), time_spent.MAX_COUNT))
        if total > item.total:
            item.total = total
        return item.last >= total, True
    if item.unit == "page":
        pages = time_spent.parse_count(_facts(db, {ref: row}).get(ref, {}).get("Pages"))
        if pages is not None:
            if pages > item.total:
                item.total = pages
            return item.last >= pages, True
        return item.last >= item.total, not item.guessed
    if item.unit == "chapter":
        return item.last >= item.total, not item.guessed
    return item.last >= item.total, False


def _finish_title(db: Session, user: models.User, plan: models.BreakPlan, ref: tuple[str, int],
                  now: datetime, ticked: Optional[models.BreakPlanItem] = None, rating: Optional[int] = None) -> Optional[dict]:
    from . import check_in
    for other in items_of(db, plan):
        if (other.category, other.item_id) == ref and other.done_at is None:
            other.done_at = now
    if ticked is not None:
        ticked.finished_title = True
    card = check_in.answer(db, user, ref[0], ref[1], "finished", rating)
    return card


def tick(db: Session, user: models.User, plan: models.BreakPlan, item_id: int, now: Optional[datetime] = None) -> dict:
    """Tick one stretch. The last stretch of a title finishes it in the library when its length is known;
    when the length is a guess (or it's a game, an audiobook or a book counted in hours) it asks instead."""
    now = now or _now()
    item = _item(db, plan, item_id)
    if item.done_at is not None:
        return {"finished": item.finished_title, "ask_finish": False}
    ref = (item.category, item.item_id)
    row = _library_row(db, user.id, *ref)
    if row is None:
        db.delete(item)
        db.commit()
        raise BreakError("That title isn't in your library anymore, so it's off the plan.", 404)
    item.done_at = now
    plan.updated_at = now
    result = {"finished": False, "ask_finish": False}
    last, known = _ending(db, user, item, row)
    if last and known:
        if getattr(row, _done_field(item.category), False):
            item.finished_title = True
            db.commit()
        else:
            _finish_title(db, user, plan, ref, now, ticked=item)
            count("break_finished")
        result["finished"] = True
    else:
        db.commit()  # the tick stands even if the library can't take the new place
        if not last and item.unit in ("episode", "page", "chapter"):
            _move_checkpoint(db, user, item)
        result["ask_finish"] = last
    count("break_ticked")
    return result


def untick(db: Session, user: models.User, plan: models.BreakPlan, item_id: int) -> None:
    """Untick a stretch. The library's place goes back only when this tick put it there and nothing has
    changed it since; a title finished in the library, or a place logged past this stretch, keeps it ticked."""
    item = _item(db, plan, item_id)
    if item.done_at is None:
        return
    row = _library_row(db, user.id, item.category, item.item_id)
    if item.finished_title or (row is not None and getattr(row, _done_field(item.category), False)):
        raise BreakError("That one is marked finished in your library. Change it there if you need to.", 409)
    if item.unit in ("episode", "page", "chapter") and not _put_back(db, user, item) and _library_past(db, user, item):
        raise BreakError("Your library already has you past this part, so it stays ticked. Change your place "
                         "there if you need to.", 409)
    item.done_at = None
    item.undo_progress = None
    plan.updated_at = _now()
    db.commit()


def finish(db: Session, user: models.User, plan: models.BreakPlan, item_id: int, rating: Optional[int] = None,
           now: Optional[datetime] = None) -> Optional[dict]:
    """"Finished the whole thing": every stretch of the title is done and the library marks it finished."""
    now = now or _now()
    item = _item(db, plan, item_id)
    ref = (item.category, item.item_id)
    if _library_row(db, user.id, *ref) is None:
        raise BreakError("That title isn't in your library anymore.", 404)
    card = _finish_title(db, user, plan, ref, now, ticked=item, rating=rating)
    db.commit()
    count("break_finished")
    return card


def rate(db: Session, user: models.User, plan: models.BreakPlan, item_id: int, rating: int) -> Optional[dict]:
    from . import check_in
    item = _item(db, plan, item_id)
    card = check_in.answer(db, user, item.category, item.item_id, "rate", rating)
    if card is None:
        raise BreakError("That title isn't in your library anymore.", 404)
    count("break_rated")
    return card


def sync(db: Session, user: models.User, plan: models.BreakPlan, now: Optional[datetime] = None) -> bool:
    """Follow the library: a title finished or logged past a stretch there ticks it here; a deleted one goes."""
    now = now or _now()
    waiting = [item for item in items_of(db, plan) if item.done_at is None]
    if not waiting:
        return False
    refs = {(item.category, item.item_id) for item in waiting}
    rows = _rows(db, user.id, list(refs))
    checkpoints = _checkpoints(db, user.id, [ref for ref in refs if ref[0] in ("books", "manga")])
    shows: dict[str, list] = {}
    for ref, row in rows.items():
        if ref[0] in ("tv-shows", "anime"):
            shows.setdefault(ref[0], []).append(row)
    watched = {}
    for category, items in shows.items():
        for item_id, (_seasons, count_watched, _total) in _episode_state(db, user.id, category, items).items():
            watched[(category, item_id)] = count_watched or 0
    changed = False
    for item in waiting:
        ref = (item.category, item.item_id)
        row = rows.get(ref)
        if row is None:
            db.delete(item)
            changed = True
            continue
        if getattr(row, _done_field(item.category), False):
            item.done_at = now
            changed = True
            continue
        if item.unit == "episode" and watched.get(ref, 0) >= item.last:
            item.done_at = now
            changed = True
        elif item.unit in ("page", "chapter"):
            entry = checkpoints.get(ref)
            if entry is not None and entry.unit == item.unit and (entry.position or 0) >= item.last:
                item.done_at = now
                changed = True
    if changed:
        db.commit()
    return changed


# ---------------------------------------------------------------- reading a plan

def phase(plan: models.BreakPlan, today: date) -> str:
    if today < plan.starts_on:
        return "upcoming"
    if today <= plan.ends_on:
        return "during"
    return "after"


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() + "Z" if value else None


def _item_view(item: models.BreakPlanItem, finished: set[tuple[str, int]], ratings: dict) -> dict:
    from . import title_pages
    kind = title_pages.LIBRARY_TO_KIND.get(item.category)
    ref = (item.category, item.item_id)
    return {
        "id": item.id, "category": item.category, "item_id": item.item_id, "title": item.title, "year": item.year,
        "image": item.image, "label": item.label, "kind_label": LABELS.get(item.category, ""),
        "minutes": item.minutes, "length": length_words(item.minutes, item.guessed), "unit": item.unit,
        "first": item.first, "last": item.last, "total": item.total, "last_part": item.last >= item.total,
        "done": item.done_at is not None, "finished_title": item.finished_title or ref in finished,
        # Its last part is ticked but the title isn't finished in the library: a game, an audiobook, or a
        # length we guessed. The plan offers "Mark it finished" instead of finishing it on its own.
        "confirm_finish": (item.done_at is not None and item.last >= item.total and item.unit != "whole"
                           and not (item.finished_title or ref in finished)),
        "added": item.added, "rating": ratings.get(ref),
        "url": title_pages.title_path(kind, item.title, item.year) if kind else None,
    }


def summary(items: list[models.BreakPlanItem], finished: set[tuple[str, int]]) -> dict:
    titles = {(item.category, item.item_id) for item in items}
    done = [item for item in items if item.done_at is not None]
    finished_titles = {(item.category, item.item_id) for item in items
                       if item.finished_title or (item.category, item.item_id) in finished}
    touched = {(item.category, item.item_id) for item in done}
    return {
        "titles": len(titles), "stretches": len(items), "done": len(done),
        "minutes": sum(item.minutes for item in items), "done_minutes": sum(item.minutes for item in done),
        "finished": len(finished_titles), "touched": len(touched),
        "hours": hours_words(sum(item.minutes for item in items)),
        "done_hours": hours_words(sum(item.minutes for item in done)),
    }


def _finished_refs(db: Session, user_id: int, items: list[models.BreakPlanItem]) -> tuple[set, dict]:
    refs = {(item.category, item.item_id) for item in items}
    rows = _rows(db, user_id, list(refs))
    finished = {ref for ref, row in rows.items() if getattr(row, _done_field(ref[0]), False)}
    ratings = {ref: (int(row.rating) if row.rating is not None else None) for ref, row in rows.items()}
    return finished, ratings


def view(db: Session, user: models.User, plan: models.BreakPlan, today: date, now: Optional[datetime] = None) -> dict:
    """The whole plan for the /break page, after following the library."""
    from .digest import app_url
    sync(db, user, plan, now)
    items = items_of(db, plan)
    finished, ratings = _finished_refs(db, user.id, items)
    budgets = minutes_by_day(plan)
    by_day: dict[date, list] = {}
    for item in items:
        by_day.setdefault(item.day, []).append(_item_view(item, finished, ratings))
    days = []
    for day, budget in budgets.items():
        entries = by_day.get(day, [])
        planned = sum(entry["minutes"] for entry in entries)
        days.append({"day": day.isoformat(), "label": _day_label(day), "weekday": day.strftime("%A"),
                     "budget": budget, "planned": planned, "free": max(0, budget - planned),
                     "over": max(0, planned - budget), "today": day == today, "past": day < today,
                     "items": entries})
    state = phase(plan, today)
    totals = summary(items, finished)
    day_number = (today - plan.starts_on).days + 1 if state == "during" else None
    finished_list = []
    seen = set()
    for item in items:
        ref = (item.category, item.item_id)
        if ref in seen or not (item.finished_title or ref in finished):
            continue
        if not any(other.done_at is not None for other in items if (other.category, other.item_id) == ref):
            continue
        seen.add(ref)
        finished_list.append(_item_view(item, finished, ratings))
    return {
        "id": plan.id, "name": plan.name, "preset": plan.preset, "starts_on": plan.starts_on.isoformat(),
        "ends_on": plan.ends_on.isoformat(), "span": span_label(plan.starts_on, plan.ends_on),
        "day_count": len(budgets), "phase": state, "day_number": day_number, "today": today.isoformat(),
        "games": plan.games, "emails": plan.emails,
        "email_offer": bool(user.email and user.is_verified),
        "share": f"{app_url()}{share_path(plan)}" if plan.share_token else None,
        "share_opened": int(plan.share_opened or 0) if plan.share_token else 0,
        "share_story": f"{share_path(plan)}/story.png" if plan.share_token else None,
        "share_card": f"{share_path(plan)}/card.png" if plan.share_token else None,
        "share_until": (plan.ends_on + timedelta(days=SHARE_KEEP_DAYS)).isoformat(),
        "days": days, "totals": totals, "finished": finished_list,
        "budget_minutes": sum(budgets.values()), "choices": list(DAY_CHOICES),
        "max_days": MAX_DAYS,
    }


def home(db: Session, user: models.User, today: date, now: Optional[datetime] = None, enough: Optional[bool] = None) -> Optional[dict]:
    """The home card: an offer before a holiday, the plan before and during the break, how it went after."""
    plan = active(db, user.id, today)
    if plan is not None:
        state = phase(plan, today)
        if state == "after" and plan.wrap_hidden_at is not None:
            plan = None
        else:
            sync(db, user, plan, now)
            items = items_of(db, plan)
            finished, ratings = _finished_refs(db, user.id, items)
            totals = summary(items, finished)
            card = {"state": state, "id": plan.id, "name": plan.name, "span": span_label(plan.starts_on, plan.ends_on),
                    "starts_on": plan.starts_on.isoformat(), "ends_on": plan.ends_on.isoformat(),
                    "day_count": (plan.ends_on - plan.starts_on).days + 1, "totals": totals,
                    "starts_in": (plan.starts_on - today).days}
            if state == "during":
                card["day_number"] = (today - plan.starts_on).days + 1
                card["today_items"] = [_item_view(item, finished, ratings) for item in items if item.day == today]
                card["today_minutes"] = minutes_by_day(plan).get(today, 0)
                ahead = [item for item in items if item.day > today and item.done_at is None]
                card["tomorrow"] = [_item_view(item, finished, ratings) for item in ahead
                                    if item.day == today + timedelta(days=1)][:3]
            elif state == "upcoming":
                first_day = [item for item in items if item.day == plan.starts_on]
                card["first_day"] = [_item_view(item, finished, ratings) for item in first_day][:4]
            else:
                seen = set()
                card["finished"] = []
                for item in items:
                    ref = (item.category, item.item_id)
                    if ref in seen or not (item.finished_title or ref in finished):
                        continue
                    seen.add(ref)
                    card["finished"].append(_item_view(item, finished, ratings))
                card["finished"] = card["finished"][:6]
                card["share"] = share_path(plan) if plan.share_token else None
            return card
    offer = prompt_preset(today)
    if offer is None:
        return None
    if enough is None:
        enough = sum(len(ids) for ids in _refs(db, user).values()) >= 3
    if not enough:
        return None
    return {"state": "offer", "key": offer["key"], "name": offer["name"], "short": offer["short"],
            "span": span_label(offer["starts_on"], offer["ends_on"]), "starts_on": offer["starts_on"].isoformat(),
            "ends_on": offer["ends_on"].isoformat(), "starts_in": (offer["starts_on"] - today).days,
            "day_count": (offer["ends_on"] - offer["starts_on"]).days + 1}


def note_seen(db: Session, user: models.User, today: date) -> dict:
    """The plan reached the screen on a day of the break: counted once a day."""
    plan = active(db, user.id, today)
    if plan is None or phase(plan, today) != "during" or plan.last_seen_on == today:
        return {"counted": False}
    plan.last_seen_on = today
    plan.days_opened = (plan.days_opened or 0) + 1
    db.commit()
    count("break_day_opened")
    return {"counted": True}


def hide_wrap(db: Session, plan: models.BreakPlan) -> None:
    plan.wrap_hidden_at = _now()
    db.commit()


# ---------------------------------------------------------------- sharing

def share_path(plan: models.BreakPlan) -> str:
    return f"/break/s/{plan.share_token}"


def share_on(db: Session, plan: models.BreakPlan) -> str:
    if not plan.share_token:
        plan.share_token = secrets.token_urlsafe(16)
        plan.share_opened = 0
        db.commit()
        count("break_shared")
    return share_path(plan)


def share_off(db: Session, plan: models.BreakPlan) -> None:
    plan.share_token = None
    db.commit()


def valid_token(token) -> bool:
    return isinstance(token, str) and SHARE_TOKEN.fullmatch(token) is not None


def share_ended(plan: models.BreakPlan, today: date) -> bool:
    """A link stops working a month after the break, so an old plan doesn't stay out there for good."""
    return plan.ends_on < today - timedelta(days=SHARE_KEEP_DAYS)


def by_token(db: Session, token: str, today: Optional[date] = None) -> Optional[models.BreakPlan]:
    if not valid_token(token):
        return None
    plan = db.query(models.BreakPlan).filter(models.BreakPlan.share_token == token,
                                             models.BreakPlan.status == "active").first()
    if plan is None or share_ended(plan, today or _now().date()):
        return None
    owner = db.get(models.User, plan.user_id)
    if owner is None or not owner.is_active:
        return None
    return plan


def count_open(db: Session, plan: models.BreakPlan) -> None:
    try:
        db.query(models.BreakPlan).filter(models.BreakPlan.id == plan.id).update(
            {models.BreakPlan.share_opened: models.BreakPlan.share_opened + 1}, synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()


def _month_day(day: date) -> str:
    return f"{day.strftime('%b')} {day.day}"


def _weekday_span(days: list[date], long_break: bool) -> str:
    """When a title is on the plan: "Thursday", "Fri to Sun", "Dec 26 to 28", "3 days"."""
    days = sorted(set(days))
    if not days:
        return ""
    if len(days) == 1:
        return _month_day(days[0]) if long_break else days[0].strftime("%A")
    contiguous = (days[-1] - days[0]).days == len(days) - 1
    if not contiguous:
        return f"{len(days)} days"
    if long_break:
        if days[0].month == days[-1].month:
            return f"{_month_day(days[0])} to {days[-1].day}"
        return f"{_month_day(days[0])} to {_month_day(days[-1])}"
    return f"{days[0].strftime('%a')} to {days[-1].strftime('%a')}"


def shared_view(db: Session, plan: models.BreakPlan, today: date) -> dict:
    """What a share link shows: titles from the shelves the member shares publicly, ticks, and totals.

    Never the member's scores, notes, library ids or the time they set aside each day. Their name only
    shows when they already have a public profile (the same rule as the other share links).
    """
    from . import tier_list, title_pages
    from .ranking_shares import _credit, _shareable
    owner = db.get(models.User, plan.user_id)
    items = items_of(db, plan)
    allowed = {category for category in CATEGORIES if _shareable(owner, category)}
    # Titles are copied onto the plan, so one taken out of the library would stay on the link until the
    # member next opened the plan. Only titles still in the library are shown.
    kept = set(_rows(db, owner.id, list({(item.category, item.item_id) for item in items if item.category in allowed})))
    shown = [item for item in items if item.category in allowed and (item.category, item.item_id) in kept]
    hidden_titles = {(item.category, item.item_id) for item in items if item.category not in allowed}
    budgets = minutes_by_day(plan)
    long_break = len(budgets) > 7
    titles: dict[tuple[str, int], dict] = {}
    for item in shown:
        ref = (item.category, item.item_id)
        entry = titles.get(ref)
        if entry is None:
            kind = title_pages.LIBRARY_TO_KIND[item.category]
            path = title_pages.title_path(kind, item.title, item.year)
            image = title_pages._safe_image(item.image)
            # A cover can be any address the member typed in, and visitors' browsers load it, so only the poster
            # hosts the tier list image proxy allows show (no tracking pixels, nothing on a home network).
            if image and not (image.startswith("https://") and tier_list.image_allowed(image)):
                image = None
            entry = titles[ref] = {
                "index": len(titles), "kind": kind, "slug": path.rsplit("/", 1)[-1], "url": path,
                "title": item.title, "year": item.year, "category": item.category,
                "kind_label": LABELS.get(item.category, ""),
                "image": image,
                "stretches": 0, "done": 0, "finished": False, "_days": [],
            }
        entry["stretches"] += 1
        entry["done"] += item.done_at is not None
        entry["finished"] = entry["finished"] or bool(item.finished_title and item.done_at is not None)
        entry["_days"].append(item.day)
    for entry in titles.values():
        entry["when"] = _weekday_span(entry.pop("_days"), long_break)
        entry["all_done"] = entry["done"] == entry["stretches"]
    days = []
    seen: set[tuple[str, int]] = set()
    for day in budgets:
        entries = []
        for item in shown:
            if item.day != day:
                continue
            ref = (item.category, item.item_id)
            entries.append({"title": item.title, "year": item.year, "image": titles[ref]["image"], "label": item.label,
                            "kind_label": LABELS.get(item.category, ""), "category": item.category,
                            "length": length_words(item.minutes, item.guessed), "unit": item.unit,
                            "done": item.done_at is not None, "finished_title": item.finished_title,
                            "index": titles[ref]["index"], "first": ref not in seen})
            seen.add(ref)
        days.append({"day": day.isoformat(), "label": _day_label(day), "items": entries,
                     "weekday": day.strftime("%a").upper(), "date": _month_day(day),
                     "today": day == today})
    totals = summary(shown, set())
    credit = _credit(db, owner)
    state = phase(plan, today)
    return {"plan_id": plan.id, "owner_id": owner.id, "token": plan.share_token, "path": share_path(plan),
            "by": credit[0] if credit else None, "profile": credit[1] if credit else None,
            "name": plan.name, "span": span_label(plan.starts_on, plan.ends_on),
            "starts_on": plan.starts_on.isoformat(), "ends_on": plan.ends_on.isoformat(),
            "phase": state, "day_number": (today - plan.starts_on).days + 1 if state == "during" else None,
            "days": days, "titles": list(titles.values()), "totals": totals,
            "private_titles": len(hidden_titles), "day_count": len(budgets), "opened": int(plan.share_opened or 0)}


def card_facts(db: Session, plan: models.BreakPlan, today: date) -> dict:
    """Everything the two pictures draw, so their fingerprint changes when the picture would."""
    view_ = shared_view(db, plan, today)
    return {"by": view_["by"], "name": view_["name"], "span": view_["span"], "phase": view_["phase"],
            "day_number": view_["day_number"], "day_count": view_["day_count"],
            "titles": view_["totals"]["titles"], "hours": view_["totals"]["hours"],
            "finished": view_["totals"]["finished"], "done": view_["totals"]["done"],
            "stretches": view_["totals"]["stretches"],
            "days": [[entry["index"] for entry in day["items"]] for day in view_["days"]],
            "done_days": [sum(1 for entry in day["items"] if entry["done"]) for day in view_["days"]],
            "day_labels": [[day["weekday"], day["date"]] for day in view_["days"]],
            "shown": [[entry["title"], entry["image"] or "", entry["when"], entry["all_done"], entry["finished"],
                       entry["category"]] for entry in view_["titles"][:24]]}


def same_days(plan: models.BreakPlan, today: date) -> Optional[dict]:
    """The days of a shared plan as a new plan would take them (from today on), or None once they're past.

    Only the dates carry over. The time on each day starts from the planner's own defaults, so a
    friend's plan never shows how much time its owner set aside.
    """
    if plan.ends_on < today:
        return None
    start = max(plan.starts_on, today)
    if (start - today).days > START_WITHIN_DAYS:
        return None
    key, light, name = None, [], None
    if plan.preset:
        chosen = preset(plan.preset, today)
        if chosen and chosen["starts_on"] == start and chosen["ends_on"] == plan.ends_on:
            key, light, name = chosen["key"], chosen["light"], chosen["name"]
    return {"starts_on": start.isoformat(), "ends_on": plan.ends_on.isoformat(), "preset": key, "name": name,
            "light": [day.isoformat() for day in light], "span": span_label(start, plan.ends_on),
            "day_count": (plan.ends_on - start).days + 1}


# ---------------------------------------------------------------- the calendar

def calendar_ics(db: Session, user: models.User, plan: models.BreakPlan, now: Optional[datetime] = None) -> str:
    """One all-day event per day of the break that has something on it, listing the day's stretches."""
    from .digest import app_url
    from .release_calendar import _escape, _fold
    now = now or _now()
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    link = f"{app_url()}/break?utm_source=calendar&utm_campaign=break"
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//OmniTrackr//Break plan//EN", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH"]
    by_day: dict[date, list] = {}
    for item in items_of(db, plan):
        by_day.setdefault(item.day, []).append(item)
    for day in days_of(plan.starts_on, plan.ends_on):
        entries = by_day.get(day, [])
        if not entries:
            continue
        names = [entry.title for entry in entries]
        summary_line = names[0] if len(names) == 1 else f"{names[0]} and {len(names) - 1} more"
        details = "\n".join(f"{entry.title}: {entry.label}" if entry.unit == "block" else
                            f"{entry.title}: {entry.label} ({length_words(entry.minutes, entry.guessed)})"
                            for entry in entries)
        lines += ["BEGIN:VEVENT", f"UID:break-{plan.id}-{day.isoformat()}@omnitrackr.xyz", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}",
                  f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}",
                  f"SUMMARY:{_escape(summary_line)}",
                  f"DESCRIPTION:{_escape(details + chr(10) + chr(10) + 'Tick things off as you go: ' + link)}",
                  f"URL:{link}", "TRANSP:TRANSPARENT", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    count("break_calendar")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


# ---------------------------------------------------------------- the two emails

def _link(path: str) -> str:
    from .digest import app_url
    joiner = "&" if "?" in path else "?"
    return f"{app_url()}{path}{joiner}{UTM}"


def send_key(plan: models.BreakPlan, which: str) -> str:
    return f"{SEND_PREFIX}{plan.id}-{which}"


def send_at(plan: models.BreakPlan, which: str) -> datetime:
    """UTC time of the start-day email (8 am local) or the wrap-up (10 am the day after)."""
    local = (datetime.combine(plan.starts_on, time(START_HOUR)) if which == "start"
             else datetime.combine(plan.ends_on + timedelta(days=1), time(WRAP_HOUR)))
    return local - timedelta(minutes=plan.tz_minutes or 0)


def _cover(image: Optional[str]) -> str:
    if image:
        return (f'<img src="{escape(image, quote=True)}" width="48" height="72" alt="" '
                'style="display:block;width:48px;height:72px;object-fit:cover;border-radius:8px;background:#e9e5f5">')
    return '<div style="width:48px;height:72px;border-radius:8px;background:#e9e5f5"></div>'


def _rows_html(entries: list[dict]) -> str:
    rows = []
    for entry in entries:
        detail = what_line(entry)
        rows.append(
            '<tr><td style="padding:8px 12px 8px 0;vertical-align:top">' + _cover(entry.get("image")) + '</td>'
            '<td style="padding:8px 0;vertical-align:top">'
            f'<div style="color:#1f1640;font-weight:700;font-size:15px;line-height:1.35">{escape(entry["title"])}</div>'
            f'<div style="color:#5b5675;font-size:13px;line-height:1.5;margin-top:2px">{escape(detail)}</div></td></tr>')
    return '<table role="presentation" cellspacing="0" cellpadding="0">' + "".join(rows) + '</table>'


def _frame(eyebrow: str, heading: str, body: str, unsubscribe_url: str, why: str) -> str:
    return (
        '<html><body style="margin:0;background:#f4f2fb;font-family:Arial,Helvetica,sans-serif">'
        '<div style="max-width:560px;margin:0 auto;padding:24px">'
        '<div style="background:#1a1433;border-radius:14px 14px 0 0;padding:22px 24px;color:#fff">'
        f'<div style="font-size:12px;letter-spacing:2px;color:#fcd34d;text-transform:uppercase">{escape(eyebrow)}</div>'
        f'<div style="font-size:22px;font-weight:700;margin-top:6px">{escape(heading)}</div></div>'
        f'<div style="background:#fff;border-radius:0 0 14px 14px;padding:20px 24px 24px">{body}'
        f'<p style="color:#6f6a8a;font-size:12px;line-height:1.5;margin-top:24px">{escape(why)} '
        f'<a href="{escape(unsubscribe_url, quote=True)}" style="color:#6d28d9">Unsubscribe from product updates</a>.</p>'
        '</div></div></body></html>')


def _button(url: str, label: str) -> str:
    return (f'<p style="margin:22px 0 6px"><a href="{escape(url, quote=True)}" style="background:#7c3aed;color:#fff;'
            f'padding:12px 20px;border-radius:999px;text-decoration:none;font-weight:700">{escape(label)}</a></p>')


WHY = "You get two emails per break plan, the morning it starts and the day after it ends, because you asked for them."


def build_start_email(username: str, plan_name: str, day_count: int, totals: dict, first_day: list[dict],
                      unsubscribe_url: str) -> tuple[str, str, str]:
    name = " ".join(plan_name.split())[:60]
    subject = f"{name} starts today"[:150]
    page = _link("/break")
    lead = (f"Here's day one of {day_count} days. {totals['titles']} titles on the plan, about {totals['hours']} "
            "in all. Tick things off as you go, and if a day goes sideways, move what's left to tomorrow.")
    today_block = (_rows_html(first_day) if first_day
                   else '<p style="color:#5b5675;font-size:14px">Nothing on day one. A rest day is allowed.</p>')
    body = (f'<p style="color:#1f1640;font-size:15px;line-height:1.6;margin-top:0">Hi {escape(username)}. '
            f'{escape(lead)}</p>'
            '<div style="font-size:12px;letter-spacing:1px;color:#6d28d9;text-transform:uppercase;margin-top:18px">Today</div>'
            + today_block + _button(page, "Open my plan"))
    html = _frame("Your break plan", f"{name} starts today", body, unsubscribe_url, WHY)
    lines = [f"Hi {username},", "", lead, "", "Today:"]
    lines += [f"- {entry['title']}: {entry['label']} ({entry['length']})" for entry in first_day] or ["- Nothing planned"]
    lines += ["", f"Open my plan: {page}", "", WHY, f"Unsubscribe from product updates: {unsubscribe_url}"]
    return subject, html, "\n".join(lines)


def build_wrap_email(username: str, plan_name: str, totals: dict, finished: list[dict], unticked: list[dict],
                     check_links: dict[int, str], unsubscribe_url: str) -> tuple[str, str, str]:
    name = " ".join(plan_name.split())[:60]
    subject = f"How did {name} go?"[:150]
    page = _link("/break")
    if totals["done"]:
        lead = (f"You got through {totals['done']} of {totals['stretches']} things on your plan, about "
                f"{totals['done_hours']}, and finished {totals['finished']} "
                f"{'title' if totals['finished'] == 1 else 'titles'}.")
    else:
        lead = "Nothing got ticked off on your plan. That happens. If you did watch or read something, say so below."
    body = f'<p style="color:#1f1640;font-size:15px;line-height:1.6;margin-top:0">Hi {escape(username)}. {escape(lead)}</p>'
    if finished:
        body += ('<div style="font-size:12px;letter-spacing:1px;color:#6d28d9;text-transform:uppercase;margin-top:18px">'
                 'Finished</div>' + _rows_html(finished))
    if unticked:
        rows = []
        for entry in unticked:
            url = check_links.get(entry["item_id"])
            button = (f' <a href="{escape(url, quote=True)}" style="color:#6d28d9;font-size:13px">Finished it after all?</a>'
                      if url else "")
            rows.append(f'<li style="margin:6px 0;color:#1f1640;font-size:14px">{escape(entry["title"])}{button}</li>')
        body += ('<div style="font-size:12px;letter-spacing:1px;color:#6d28d9;text-transform:uppercase;margin-top:18px">'
                 'Still on your list</div><ul style="padding-left:18px;margin:6px 0">' + "".join(rows) + '</ul>')
    body += _button(page, "See how it went")
    html = _frame("Your break plan", subject, body, unsubscribe_url, WHY)
    lines = [f"Hi {username},", "", lead, ""]
    if finished:
        lines += ["Finished:"] + [f"- {entry['title']}" for entry in finished] + [""]
    if unticked:
        lines += ["Still on your list:"]
        for entry in unticked:
            url = check_links.get(entry["item_id"])
            lines.append(f"- {entry['title']}" + (f" (finished it after all? {url})" if url else ""))
        lines.append("")
    lines += [f"See how it went: {page}", "", WHY, f"Unsubscribe from product updates: {unsubscribe_url}"]
    return subject, html, "\n".join(lines)


def email_for(db: Session, user: models.User, plan: models.BreakPlan, which: str) -> Optional[tuple[str, str, str, str]]:
    from . import check_in
    from .announcements import unsubscribe_token
    from .digest import app_url
    sync(db, user, plan)
    items = items_of(db, plan)
    if not items:
        return None
    unsubscribe_url = f"{app_url()}/email/updates/unsubscribe?token={unsubscribe_token(user.id)}"
    finished, ratings = _finished_refs(db, user.id, items)
    totals = summary(items, finished)
    if which == "start":
        first_day = [_item_view(item, finished, ratings) for item in items if item.day == plan.starts_on][:6]
        subject, html, text = build_start_email(user.username, plan.name, (plan.ends_on - plan.starts_on).days + 1,
                                                totals, first_day, unsubscribe_url)
        return subject, html, text, unsubscribe_url
    seen = set()
    finished_list, unticked = [], []
    for item in items:
        ref = (item.category, item.item_id)
        if ref in seen:
            continue
        seen.add(ref)
        entry = _item_view(item, finished, ratings)
        if entry["finished_title"]:
            finished_list.append(entry)
        elif not any(other.done_at is not None for other in items if (other.category, other.item_id) == ref):
            unticked.append(entry)
    unticked = unticked[:4]
    links = {}
    if unticked:
        token = check_in.make_token(user.id, [{"category": entry["category"], "id": entry["item_id"]} for entry in unticked],
                                    "break")
        links = {entry["item_id"]: check_in.link_for(token, index, "finished") for index, entry in enumerate(unticked)}
    subject, html, text = build_wrap_email(user.username, plan.name, totals, finished_list[:6], unticked, links,
                                           unsubscribe_url)
    return subject, html, text, unsubscribe_url


def allowance(db: Session, now: datetime) -> int:
    from .announcements import shared_cap
    since = now - timedelta(hours=24)
    sent_mine = db.query(func.count(models.EmailCampaignSend.id)).filter(
        models.EmailCampaignSend.campaign_key.like(f"{SEND_PREFIX}%"),
        models.EmailCampaignSend.sent_at >= since).scalar() or 0
    sent_campaign = db.query(func.count(models.EmailCampaignSend.id)).filter(
        models.EmailCampaignSend.sent_at >= since).scalar() or 0
    sent_digest = db.query(func.count(models.EmailDigestSubscription.id)).filter(
        models.EmailDigestSubscription.last_sent_at >= since).scalar() or 0
    return max(0, min(daily_limit() - sent_mine, shared_cap() - sent_campaign - sent_digest, PER_RUN_LIMIT))


def _opted_out(db: Session, user_id: int) -> bool:
    return db.query(models.EmailOptOut.id).filter(models.EmailOptOut.user_id == user_id).first() is not None


def due(db: Session, now: datetime) -> list[tuple[models.BreakPlan, str]]:
    """Plans with an email whose time has come (or passed within LATE), oldest first."""
    today = now.date()
    plans = db.query(models.BreakPlan).filter(
        models.BreakPlan.status == "active", models.BreakPlan.emails == True,  # noqa: E712
        models.BreakPlan.starts_on <= today + timedelta(days=1),
        models.BreakPlan.ends_on >= today - timedelta(days=2),
    ).order_by(models.BreakPlan.id).limit(400).all()
    found = []
    for plan in plans:
        for which, status in (("start", plan.start_email), ("wrap", plan.wrap_email)):
            if status is None and send_at(plan, which) <= now:
                found.append((plan, which))
    found.sort(key=lambda entry: send_at(*entry))
    return found


def _mark(plan: models.BreakPlan, which: str, value: str) -> None:
    if which == "start":
        plan.start_email = value
    else:
        plan.wrap_email = value


async def _send(to: str, subject: str, html: str, unsubscribe_url: str) -> None:
    from .digest import _send as send_mail
    await send_mail(to, subject, html, unsubscribe_url)


async def send_due(session_factory, now: Optional[datetime] = None, sender=_send) -> dict:
    from .digest import mail_configured
    now = now or _now()
    result = {"sent": 0, "failed": 0, "dropped": 0, "limited": False}
    if not mail_configured() and sender is _send:
        return result
    db = session_factory()
    try:
        from .email_quota import lock_email_budget
        for plan, which in due(db, now):
            user = db.get(models.User, plan.user_id)
            created_late = which == "start" and plan.created_at and plan.created_at > send_at(plan, which)
            if (user is None or not user.is_active or not user.is_verified or not user.email
                    or now - send_at(plan, which) > LATE or created_late or _opted_out(db, user.id)):
                _mark(plan, which, "skipped" if created_late else "dropped")
                db.commit()
                result["dropped"] += 1
                continue
            lock_email_budget(db)
            if result["sent"] + result["failed"] >= PER_RUN_LIMIT or allowance(db, now) <= 0:
                db.rollback()
                result["limited"] = True
                break
            try:
                built = email_for(db, user, plan, which)
            except Exception as error:
                print(f"Break plan email for user {user.id} couldn't be built: {error}")
                db.rollback()
                continue
            if built is None:
                _mark(plan, which, "dropped")
                db.commit()
                result["dropped"] += 1
                continue
            db.add(models.EmailCampaignSend(campaign_key=send_key(plan, which), user_id=user.id, status="sent",
                                            sent_at=now))
            _mark(plan, which, "sent")
            try:
                db.commit()
            except Exception:
                db.rollback()
                continue  # already claimed by an overlapping run
            subject, html, _text, unsubscribe_url = built
            try:
                await sender(user.email, subject, html, unsubscribe_url)
                result["sent"] += 1
                count("break_email_sent")
            except Exception as error:
                print(f"Break plan email to user {user.id} failed: {error}")
                _mark(plan, which, "failed")
                db.commit()
                result["failed"] += 1
        return result
    finally:
        db.close()


async def break_plan_loop(app) -> None:
    """Background task started with the app; never raises."""
    from .database import SessionLocal
    await asyncio.sleep(FIRST_CHECK_DELAY_SECONDS)
    while True:
        try:
            result = await send_due(SessionLocal)
            if result["sent"] or result["failed"]:
                print(f"Break plan emails: {result}")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"Break plan email check failed: {error}")
        await asyncio.sleep(CHECK_EVERY_SECONDS)


# ---------------------------------------------------------------- the demo on the guide page

SAMPLE = (
    # (category, title, year, unit, step minutes, total units)
    ("tv-shows", "Severance, season 1", 2022, "episode", 55, 9),
    ("movies", "The Holdovers", 2023, "whole", 133, 1),
    ("music", "Rumours", 1977, "whole", 39, 1),
    ("video-games", "What Remains of Edith Finch", 2017, "block", BLOCK, 5),
    ("books", "Piranesi", 2020, "page", 1.5, 272),
    ("anime", "Frieren: Beyond Journey's End, season 1", 2023, "episode", 24, 28),
    ("movies", "Paddington 2", 2017, "whole", 103, 1),
    ("tv-shows", "Arcane, season 1", 2021, "episode", 40, 9),
    ("audiobooks", "Project Hail Mary", 2021, "block", BLOCK, 33),
    ("movies", "Knives Out", 2019, "whole", 130, 1),
    ("video-games", "Unpacking", 2021, "block", BLOCK, 8),
    ("music", "Folklore", 2020, "whole", 63, 1),
)


def demo(starts_on: date, minutes: dict[str, int]) -> list[dict]:
    """The guide page's sample plan: the same filling rules over a made-up library of twelve titles."""
    days = [Day(day, clean_minutes(minutes.get(day.isoformat(), DEFAULT_MINUTES)),
                clean_minutes(minutes.get(day.isoformat(), DEFAULT_MINUTES)))
            for day in sorted(date.fromisoformat(key) for key in minutes)][:MAX_DAYS]
    pool = []
    for index, (category, title, year, unit, step, total) in enumerate(SAMPLE):
        started = index == 0  # the sample member is halfway through Severance
        pool.append(Candidate(category=category, item_id=index + 1, title=title, year=year,
                              group="started" if started else "saved", unit=unit, step=float(step),
                              done=total // 2 if started else 0, total=total, target=total))
    chunks = fill_days(days, pool, max_titles=max_titles_for(len(days)))
    found = []
    for day in days:
        entries = [{"title": chunk["title"], "label": chunk["label"], "kind_label": LABELS[chunk["category"]],
                    "category": chunk["category"], "length": length_words(chunk["minutes"]), "minutes": chunk["minutes"],
                    "unit": chunk["unit"]}
                   for chunk in chunks if chunk["day"] == day.day]
        found.append({"day": day.day.isoformat(), "label": _day_label(day.day), "budget": day.budget,
                      "planned": sum(entry["minutes"] for entry in entries), "items": entries})
    return found


# ---------------------------------------------------------------- Site stats

def stats(db: Session) -> dict:
    plans = models.BreakPlan
    return {
        "plans": int(db.query(func.count(plans.id)).filter(plans.status == "active").scalar() or 0),
        "shared": int(db.query(func.count(plans.id)).filter(plans.share_token.isnot(None)).scalar() or 0),
        "ticked": int(db.query(func.count(models.BreakPlanItem.id)).filter(
            models.BreakPlanItem.done_at.isnot(None)).scalar() or 0),
    }
