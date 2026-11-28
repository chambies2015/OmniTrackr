"""The year's big ones: a poster grid on "Fill in your year" for titles that aren't in the library yet.

"Fill in your year" (app/year_fill.py) asks about titles already in a member's
library. A member who signed up and saved little or nothing has nothing to be
asked about, so their Year in Review stays empty and the December email skipped
them. This grid fills that gap with the year's big releases (app/year_catchup_data.py):

- Tap a poster and pick the month: the title is saved to the library, finished,
  and the finish is dated the way "Fill in your year" dates one (an earlier month
  is the 15th, journal source "filled-in"; this month is a normal tick today).
- "Want to" saves it, not started. "Not for me" only remembers the answer.
- A title already in the library shows as such and is never asked about here.
- Every answer can be taken back. A title an answer saved in the last day is
  removed again; after that it stays in the library and only the date goes.

The grid is on /year-in-review/<year>/fill for members and on the emailed
/fill-in/<token> page, which works without signing in. Counters go into the
"yearfill" kind with a "catchup_" prefix and name no member.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import friend_feed, models, title_pages, year_fill
from .year_catchup_data import EDITIONS

ANSWERS = ("month", "want", "no")
KIND_ORDER = ("movie", "tv", "anime", "game", "album", "book", "manga", "podcast", "audiobook")
GROUPS = {"movie": "Movies", "tv": "TV", "anime": "Anime", "game": "Games", "album": "Albums", "book": "Books",
          "manga": "Manga", "podcast": "Podcasts", "audiobook": "Audiobooks"}
QUESTIONS = {"movie": "When did you watch it?", "tv": "When did you finish it?", "anime": "When did you finish it?",
             "game": "When did you play it?", "album": "When did you listen to it?", "book": "When did you read it?",
             "manga": "When did you read it?", "podcast": "When did you listen to it?",
             "audiobook": "When did you listen to it?"}
WANTS = {"movie": "Want to watch", "tv": "Want to watch", "anime": "Want to watch", "game": "Want to play",
         "album": "Want to listen", "book": "Want to read", "manga": "Want to read", "podcast": "Want to listen",
         "audiobook": "Want to listen"}
VERBS = {"movie": "Watched", "tv": "Watched", "anime": "Watched", "game": "Played", "album": "Listened",
         "book": "Read", "manga": "Read", "podcast": "Listened", "audiobook": "Listened"}
THIN_BELOW = 5               # a recap with fewer finishes than this gets the big-ones email in December
EMAIL_POSTERS = 6
UNDO_WINDOW = timedelta(hours=24)
COUNTER_KEYS = ("got", "want", "no", "undone")


def years() -> list[int]:
    return sorted(EDITIONS)


def has_year(year: int) -> bool:
    return year in EDITIONS


@lru_cache(maxsize=8)
def _entries(year: int) -> tuple[dict, ...]:
    found = []
    for raw in EDITIONS.get(year, {}).get("entries", ()):
        kind = raw["kind"]
        out_year, out_month = (int(part) for part in raw["out"].split("-"))
        slug = title_pages.title_slug(raw["title"], raw.get("year"))
        when = f"{year_fill.MONTHS[out_month - 1]} {out_year}"
        if raw.get("season"):
            when = f"Season {raw['season']} · {when}"
        found.append({
            "id": f"{kind}/{slug}", "kind": kind, "slug": slug, "anchor": f"yc-{kind}-{slug}"[:150],
            "category": title_pages.KINDS[kind][2], "label": title_pages.KINDS[kind][3],
            "title": raw["title"], "year": raw.get("year"), "creator": raw.get("creator"),
            "out_year": out_year, "out_month": out_month, "season": raw.get("season"), "when": when,
            "feature": int(raw.get("feature") or 999),
            "question": (f"When did you finish season {raw['season']}?" if raw.get("season") else QUESTIONS[kind]),
            "want_label": WANTS[kind], "verb": VERBS[kind],
        })
    found.sort(key=lambda entry: (KIND_ORDER.index(entry["kind"]), entry["feature"]))
    return tuple(found)


def entries(year: int) -> list[dict]:
    """Every title in the year's list, in grid order (by format, biggest first). Copies, safe to change."""
    return [dict(entry) for entry in _entries(year)]


def shown(year: int, today: Optional[date] = None) -> list[dict]:
    """The titles that are out by this month."""
    today = today or year_fill._now().date()
    return [entry for entry in entries(year) if (entry["out_year"], entry["out_month"]) <= (today.year, today.month)]


def find(year: int, entry_id: str, today: Optional[date] = None) -> Optional[dict]:
    for entry in shown(year, today):
        if entry["id"] == entry_id:
            return entry
    return None


def months_for(entry: dict, year: int, today: Optional[date] = None) -> list[dict]:
    """The month buttons for one title: from the month it came out (in that year) to this month."""
    start = entry["out_month"] if entry["out_year"] == year else 1
    return [month for month in year_fill.months_for(year, today) if month["n"] >= start]


def available(year: int, today: Optional[date] = None) -> bool:
    """True while the grid can be answered: a year with a list, while it can still be filled in."""
    return has_year(year) and year_fill.is_fill_year(year, today) and bool(shown(year, today))


# ---------------------------------------------------------------- what the member has

def in_library(db: Session, user_id: int, items: list[dict]) -> dict[str, dict]:
    """{entry id: {"item_id", "done"}} for titles already in this member's library (same name, any case)."""
    by_kind: dict[str, dict[str, str]] = {}
    for entry in items:
        by_kind.setdefault(entry["kind"], {})[title_pages.normalize(entry["title"])] = entry["id"]
    found: dict[str, dict] = {}
    for kind, names in by_kind.items():
        model = title_pages.KINDS[kind][0]
        done_field = title_pages.COMPLETE_FIELD[kind]
        rows = db.query(model.id, model.title, getattr(model, done_field)).filter(
            model.user_id == user_id, func.lower(func.trim(model.title)).in_(list(names))).all()
        for item_id, title, done in rows:
            entry_id = names.get(title_pages.normalize(title))
            if entry_id and (entry_id not in found or (done and not found[entry_id]["done"])):
                found[entry_id] = {"item_id": item_id, "done": bool(done)}
    return found


def _answers(db: Session, user_id: int, year: int) -> dict[str, models.YearCatchupAnswer]:
    return {row.entry_id: row for row in db.query(models.YearCatchupAnswer).filter(
        models.YearCatchupAnswer.user_id == user_id, models.YearCatchupAnswer.year == year)}


def covers(db: Session, items: list[dict]) -> dict[str, str]:
    """{entry id: cover} from covers already on the site. Never fetches."""
    if not items:
        return {}
    from .taste_quiz import cached_art_many
    return cached_art_many(db, items)


def _state(entry: dict, answer: Optional[models.YearCatchupAnswer], owned: Optional[dict]) -> dict:
    item = {key: entry[key] for key in ("id", "kind", "slug", "anchor", "category", "label", "title", "when",
                                        "question", "want_label", "verb", "out_month", "out_year")}
    item["month"] = None
    if answer is not None:
        item["state"] = answer.answer
        item["month"] = answer.month
    elif owned is not None:
        item["state"] = "library_done" if owned["done"] else "library_saved"
    else:
        item["state"] = "open"
    return item


def grid(db: Session, user_id: int, year: int, today: Optional[date] = None) -> dict:
    """Everything the grid shows: titles grouped by format, each with its state, and the counts."""
    today = today or year_fill._now().date()
    items = shown(year, today)
    answers = _answers(db, user_id, year)
    owned = in_library(db, user_id, [entry for entry in items if entry["id"] not in answers])
    images = covers(db, items)
    groups: list[dict] = []
    counts = {"total": len(items), "got": 0, "open": 0, "want": 0}
    for entry in items:
        item = _state(entry, answers.get(entry["id"]), owned.get(entry["id"]))
        item["image"] = images.get(entry["id"])
        item["months"] = months_for(entry, year, today) if item["state"] == "open" else []
        if item["state"] in ("month", "library_done"):
            counts["got"] += 1
        elif item["state"] == "open":
            counts["open"] += 1
        elif item["state"] in ("want", "library_saved"):
            counts["want"] += 1
        if not groups or groups[-1]["kind"] != entry["kind"]:
            groups.append({"kind": entry["kind"], "label": GROUPS[entry["kind"]], "items": []})
        groups[-1]["items"].append(item)
    return {"year": year, "groups": groups, **counts}


def tally(db: Session, user_id: int, year: int, today: Optional[date] = None) -> dict:
    """The counts alone, for the replies to a tap."""
    found = grid(db, user_id, year, today)
    return {key: found[key] for key in ("total", "got", "open", "want")}


def featured(db: Session, user_id: int, year: int, today: Optional[date] = None,
             limit: int = EMAIL_POSTERS) -> list[dict]:
    """The biggest titles this member hasn't answered and doesn't have, for the email."""
    found = grid(db, user_id, year, today)
    waiting = [item for group in found["groups"] for item in group["items"] if item["state"] == "open"]
    order = {entry["id"]: entry["feature"] for entry in entries(year)}
    waiting.sort(key=lambda item: order.get(item["id"], 999))
    return waiting[:limit]


# ---------------------------------------------------------------- answering

def answer(db: Session, user: models.User, year: int, entry_id: str, choice: str, month: Optional[int] = None,
           source: str = "page", now: Optional[datetime] = None) -> dict:
    """Save one answer. Returns {"state", "id", "title", "month"}; "already" for a title answered before,
    "library" for one that is already in the library. Raises ValueError for anything that can't be saved."""
    from .progress import lock_progress_owner
    from .start_flow import add_known
    from .taste_quiz import cached_art
    now = now or year_fill._now()
    today = now.date()
    if choice not in ANSWERS:
        raise ValueError("unknown answer")
    if not available(year, today):
        raise ValueError("that year can't be filled in")
    entry = find(year, entry_id, today)
    if entry is None:
        raise ValueError("that title isn't on the list")
    if choice == "month":
        allowed = {item["n"] for item in months_for(entry, year, today)}
        if isinstance(month, bool) or not isinstance(month, int) or month not in allowed:
            raise ValueError("pick a month after it came out")
    else:
        month = None
    source = source if source in year_fill.SOURCES else "page"
    lock_progress_owner(db, user.id)
    reply = {"id": entry_id, "title": entry["title"], "month": month}
    existing = db.query(models.YearCatchupAnswer).filter_by(user_id=user.id, year=year, entry_id=entry_id).first()
    if existing is not None:
        db.rollback()
        return {**reply, "state": "already", "month": existing.month}
    owned = in_library(db, user.id, [entry]).get(entry_id)
    if owned is not None:
        db.rollback()
        return {**reply, "state": "library", "done": owned["done"]}
    record = models.YearCatchupAnswer(user_id=user.id, year=year, entry_id=entry_id, answer=choice, month=month,
                                      source=source, created_at=now)
    if choice == "no":
        db.add(record)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return {**reply, "state": "already"}
        return {**reply, "state": "no"}
    kind = entry["kind"]
    image = cached_art(db, entry)
    state, row = add_known(db, user, kind, entry, image)
    record.category = entry["category"]
    record.item_id = row.id
    record.created_row = state == "created"
    if choice == "want":
        db.add(record)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return {**reply, "state": "already"}
        return {**reply, "state": "want"}
    # A finish: tick the new title off, then date it the way "Fill in your year" dates any other.
    # An earlier month isn't news for friends: without the quiet flag the tick below would put a
    # "finished" card on their feed today for something watched in August. The add itself still shows,
    # as "added a film they've watched", the same as any title saved as already seen.
    backdated = year_fill._fill_moment(year, month, now) is not None
    if backdated:
        db.info[friend_feed.QUIET_KEY] = True
    try:
        setattr(row, title_pages.COMPLETE_FIELD[kind], True)
        db.add(record)
        db.flush()
        result = year_fill.answer(db, user, year, entry["category"], row.id, "month", month, source, now)
    except ValueError:
        db.rollback()
        raise
    finally:
        if backdated:
            db.info.pop(friend_feed.QUIET_KEY, None)
    if result is None or result.get("state") != "month":
        db.rollback()
        return {**reply, "state": "already"}
    return {**reply, "state": "month"}


def _untouched(row) -> bool:
    """True while a row this page saved is still only what the page saved: no rating, no review.
    Taking the answer back then removes the title; once the member has made it their own it stays."""
    return getattr(row, "rating", None) is None and not (getattr(row, "review", None) or "").strip()


def undo(db: Session, user: models.User, year: int, entry_id: str) -> bool:
    """Take back one answer. The finish it dated goes; a title it saved in the last day leaves the library."""
    from .library_lifecycle import delete_owned_media
    from .progress import lock_progress_owner
    lock_progress_owner(db, user.id)
    record = db.query(models.YearCatchupAnswer).filter_by(user_id=user.id, year=year, entry_id=entry_id).first()
    if record is None:
        db.rollback()
        return False
    category, item_id = record.category, record.item_id
    remove_row = False
    if category in year_fill.categories() and item_id:
        model, done_field, _label, _button = year_fill.categories()[category]
        row = db.query(model).filter(model.id == item_id, model.user_id == user.id).first()
        filled = db.query(models.YearFillAnswer).filter_by(
            user_id=user.id, year=year, category=category, item_id=item_id).first()
        if record.answer == "month" and filled is not None:
            if filled.entry_id:
                entry = db.get(models.ActivityEntry, filled.entry_id)
                if (entry is not None and entry.user_id == user.id and entry.category == category
                        and entry.item_id == item_id and entry.action == "completed"):
                    db.delete(entry)
            db.delete(filled)
        # added_at is stamped with the real clock when the row is made, so the window is judged by it too.
        added_at = getattr(row, "added_at", None) if row is not None else None
        remove_row = bool(row is not None and record.created_row and _untouched(row)
                          and (added_at is None or added_at >= datetime.utcnow() - UNDO_WINDOW))
    db.delete(record)
    db.commit()
    if remove_row:
        try:
            delete_owned_media(db, user.id, category, item_id)
        except Exception:
            db.rollback()
    return True


# ---------------------------------------------------------------- counters

def count_answer(result: Optional[dict], source: str) -> None:
    if not result or result.get("state") not in ANSWERS:
        return
    source = source if source in year_fill.SOURCES else "page"
    key = {"month": "got", "want": "want", "no": "no"}[result["state"]]
    year_fill.count(f"catchup_{key}_{source}")


# ---------------------------------------------------------------- covers

async def warm_covers(session_factory, client, year: int, limit: int = 12, pause: float = 3.0) -> int:
    """Look up covers the site doesn't have yet, a few at a time, so the email and the emailed page have them.
    Returns how many lookups ran. Each title is looked up once; misses are remembered by title_metadata."""
    from fastapi.concurrency import run_in_threadpool
    from . import title_metadata
    if client is None or not has_year(year):
        return 0
    db = session_factory()
    ran = 0
    try:
        items = entries(year)
        have = await run_in_threadpool(covers, db, items)
        for entry in items:
            if ran >= limit:
                break
            if entry["id"] in have:
                continue
            key = title_metadata.cache_key(entry["kind"], title_pages.normalize(entry["title"]), entry["year"])
            _data, fresh = await run_in_threadpool(title_metadata.cached, db, key)
            if fresh:
                continue
            if ran:
                await asyncio.sleep(pause)   # Wikidata asks callers to slow down after a burst
            await title_metadata.get_or_fetch(db, client, entry["kind"], title_pages.normalize(entry["title"]),
                                              entry["title"], entry["year"], entry.get("creator"), wait=8)
            ran += 1
        return ran
    finally:
        db.close()
