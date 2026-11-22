"""Rankings: put the titles you've finished in order, two at a time (Nov 2026).

Scores out of ten bunch up. Most members give their favourites an 8 or a 9 and then can't
say which of twenty 8s they liked best, so "my top ten" is a list nobody keeps. Here the
member only ever answers one question, "which did you like more?", about two titles they
finished. Each answer halves the stretch of their list the new title can land in, so placing
a film among a hundred others takes about seven taps (a binary search). Every finish is a
reason to open OmniTrackr again: "Dune: Part Two just went in at #4."

* One ranking per format (films with films, books with books), one row per member and format
  in ``rankings``. Only finished titles are ranked. The library itself is never changed.
* The first answer starts a placement, so the home card can show a question straight away
  without writing anything until the member taps. The question being asked is the only state
  kept between taps; a tap for a question that is no longer the current one (a double tap, a
  second tab) gets the current question back instead of being applied twice.
* "Too close to call" puts the title right below the other one. "Skip this one" moves it to the
  back of the queue, "Leave it out" never offers it again (it can be put back).
* Titles finished in the last two weeks are offered first: that is when people know where a
  title belongs, and it's the moment the finish dialog and the home card ask about.
* The top ten of a format can go on the member's public profile (off until they turn it on, and
  never for a format they hide) or be saved as a ranked collection, which they can share by link.

Counters go into ``site_traffic_daily`` under kind "rank" and name no member.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models

MAX_RANKED = 1000          # titles in one format's ranking
MAX_LISTED = 2000          # finished titles read for the queue
MAX_LATER = 200
MAX_LEFT_OUT = 1000
RECENT = timedelta(days=14)
FRESH = timedelta(days=7)  # a finish this recent makes the home card ask about it first
PUBLIC_TOP = 10
CHUNK = 400                # stays under SQLite's bound-parameter limit

CHOICES = ("placing", "against", "tie")

# Singular and plural for "your #4 film" and "12 films ranked".
NOUNS = {
    "movies": ("film", "films"), "tv-shows": ("show", "shows"), "anime": ("anime", "anime"),
    "video-games": ("game", "games"), "music": ("album", "albums"), "books": ("book", "books"),
    "manga": ("manga", "manga"), "podcasts": ("podcast", "podcasts"), "audiobooks": ("audiobook", "audiobooks"),
}
LABELS = {
    "movies": "Films", "tv-shows": "TV shows", "anime": "Anime", "video-games": "Games", "music": "Albums",
    "books": "Books", "manga": "Manga", "podcasts": "Podcasts", "audiobooks": "Audiobooks",
}
VERBS = {
    "movies": "watched", "tv-shows": "finished", "anime": "finished", "video-games": "finished",
    "music": "listened to", "books": "read", "manga": "read", "podcasts": "listened to", "audiobooks": "finished",
}

COUNTERS = {
    "seen_home": "Saw the home card",
    "seen_tab": "Opened the Rankings tab",
    "answered": "Questions answered",
    "tie": "Too close to call",
    "placed": "Titles placed",
    "first": "Members who placed their first title",
    "from_home": "Placed from the home card",
    "from_tab": "Placed from the Rankings tab",
    "from_finish": "Placed from the finish dialog",
    "skipped": "Skipped a title",
    "left_out": "Left a title out",
    "moved": "Moved a title by hand",
    "removed": "Took a title off a ranking",
    "public_on": "Put a top ten on their profile",
    "public_off": "Took a top ten off their profile",
    "collection": "Saved a top ten as a collection",
}
SOURCES = ("home", "tab", "finish")


class Stale(Exception):
    """The answer was for a question that is no longer the one being asked."""


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def count(key: str) -> bool:
    """Add 1 to a "rank" counter for today. Never raises."""
    if key not in COUNTERS:
        return False
    try:
        from .site_traffic import RECORDER
        if not RECORDER.enabled:
            return False
        day = datetime.now(timezone.utc).date()
        with RECORDER._lock:
            RECORDER._pending[(day, "rank", key)] += 1
            RECORDER._events += 1
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- the member's titles

def _categories():
    from .check_in import CATEGORIES
    return CATEGORIES


def categories() -> list[str]:
    return list(_categories())


def _visible(user: models.User) -> list[str]:
    from .user_columns import VISIBLE, ensure_loaded
    ensure_loaded(user, VISIBLE)
    return [category for category in _categories()
            if getattr(user, f"{category.replace('-', '_')}_visible", True) is not False]


def _check_category(category: str) -> None:
    if category not in _categories():
        raise LookupError("That isn't one of the nine formats.")


def _ids(text: Optional[str]) -> list[int]:
    """A stored JSON list of ids. Anything that isn't a positive whole number is dropped."""
    try:
        values = json.loads(text or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(values, list):
        return []
    seen: set[int] = set()
    result = []
    for value in values:
        if type(value) is int and 0 < value <= 2147483647 and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _dump(ids: Iterable[int]) -> str:
    return json.dumps(list(ids), separators=(",", ":"))


def _finished(db: Session, user_id: int, category: str) -> list[tuple[int, Optional[float]]]:
    """(id, score) of every finished, titled title in one format: best scored first, then newest."""
    model, done_field, _label, _button = _categories()[category]
    return [(item_id, rating) for item_id, rating in db.query(model.id, model.rating).filter(
        model.user_id == user_id, getattr(model, done_field) == True,  # noqa: E712
        model.title.isnot(None), func.trim(model.title) != "",
    ).order_by(model.rating.is_(None), model.rating.desc(), model.id.desc()).limit(MAX_LISTED).all()]


def _existing(db: Session, user_id: int, category: str, ids: list[int]) -> set[int]:
    model = _categories()[category][0]
    found: set[int] = set()
    for start in range(0, len(ids), CHUNK):
        part = ids[start:start + CHUNK]
        found.update(item_id for (item_id,) in db.query(model.id).filter(model.user_id == user_id, model.id.in_(part)).all())
    return found


def _rows(db: Session, user_id: int, category: str, ids: list[int]) -> dict[int, object]:
    model = _categories()[category][0]
    found = {}
    for start in range(0, len(ids), CHUNK):
        part = ids[start:start + CHUNK]
        for row in db.query(model).filter(model.user_id == user_id, model.id.in_(part)).all():
            found[row.id] = row
    return found


def _is_finished(db: Session, user_id: int, category: str, item_id: int) -> bool:
    model, done_field, _label, _button = _categories()[category]
    return db.query(model.id).filter(
        model.user_id == user_id, model.id == item_id, getattr(model, done_field) == True,  # noqa: E712
        model.title.isnot(None), func.trim(model.title) != "",
    ).first() is not None


def _recent(db: Session, user_id: int, category: str, now: datetime, within: timedelta = RECENT) -> list[int]:
    """Ids finished (or finished again) in the journal recently, newest first."""
    rows = db.query(models.ActivityEntry.item_id, func.max(models.ActivityEntry.occurred_at)).filter(
        models.ActivityEntry.user_id == user_id, models.ActivityEntry.category == category,
        models.ActivityEntry.action.in_(("completed", "revisited")), models.ActivityEntry.item_id.isnot(None),
        models.ActivityEntry.occurred_at >= now - within,
    ).group_by(models.ActivityEntry.item_id).all()
    return [item_id for item_id, _ in sorted(rows, key=lambda row: row[1], reverse=True)]


# ---------------------------------------------------------------- one card

def _score(value) -> Optional[str]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return f"{number:.1f}".rstrip("0").rstrip(".")


def card(category: str, row) -> dict:
    from . import title_pages
    kind = title_pages.LIBRARY_TO_KIND[category]
    year = title_pages.item_year(kind, row)
    title = " ".join((row.title or "").split())[:200]
    creator_field = title_pages.KINDS[kind][4]
    creator = " ".join(str(getattr(row, creator_field, "") or "").split())[:120] if creator_field else ""
    image = title_pages._safe_image(getattr(row, title_pages.IMAGE_FIELD[kind], None))
    return {
        "category": category,
        "id": row.id,
        "title": title,
        "year": year,
        "creator": creator or None,
        "score": _score(getattr(row, "rating", None)),
        "image": image if image and image.startswith("https://") else None,
        "url": title_pages.title_path(kind, title, year) if title else None,
    }


# ---------------------------------------------------------------- the stored ranking

def _row(db: Session, user_id: int, category: str, lock: bool = False) -> Optional[models.Ranking]:
    query = db.query(models.Ranking).filter(models.Ranking.user_id == user_id, models.Ranking.category == category)
    if lock and db.get_bind().dialect.name != "sqlite":
        query = query.with_for_update()
    return query.first()


def _row_for_write(db: Session, user_id: int, category: str) -> models.Ranking:
    row = _row(db, user_id, category, lock=True)
    if row is not None:
        return row
    row = models.Ranking(user_id=user_id, category=category, ranked="[]")
    db.add(row)
    try:
        db.flush()
    except IntegrityError:  # another tab made it a moment ago
        db.rollback()
        row = _row(db, user_id, category, lock=True)
        if row is None:
            raise
    return row


def _tidy(db: Session, user_id: int, category: str, row: Optional[models.Ranking]) -> list[int]:
    """The ranked ids that still exist in the library. A title deleted since drops out."""
    if row is None:
        return []
    ranked = _ids(row.ranked)
    if not ranked:
        return []
    found = _existing(db, user_id, category, ranked)
    return [item_id for item_id in ranked if item_id in found]


def _cancel(row: models.Ranking) -> None:
    row.placing_id = None
    row.low = row.high = row.steps = 0


def _window(row: models.Ranking, ranked: list[int]) -> tuple[int, int]:
    """Where the title being placed can still land: the stretch [low, high) of ``ranked``.

    ``low`` and ``high`` were saved against the stored list. A title deleted from the library since
    then is gone from ``ranked`` (see _tidy), and every place after it moves up one, so the saved
    numbers are counted again over the titles still there. Otherwise a deletion above the stretch
    lands the new title one place too low. When nothing of the stretch is left, the question starts
    again from the whole list: a few more picks, never a wrong place.
    """
    stored = _ids(row.ranked)
    low, high = max(0, min(row.low or 0, len(stored))), max(0, min(row.high or 0, len(stored)))
    if stored != ranked:
        keep = set(ranked)
        low = sum(1 for item_id in stored[:low] if item_id in keep)
        high = sum(1 for item_id in stored[:high] if item_id in keep)
    if low >= high:
        return 0, len(ranked)
    return low, high


def _remaining(low: int, high: int) -> int:
    """About how many more answers place the title (a stretch of n places needs about log2(n+1))."""
    span = max(0, high - low)
    return max(1, math.ceil(math.log2(span + 1))) if span else 0


def _queue(db: Session, user_id: int, category: str, row: Optional[models.Ranking], ranked: list[int],
           now: datetime, finished: Optional[list[tuple[int, Optional[float]]]] = None) -> list[int]:
    """Unranked finished titles in the order they're offered: recent finishes, then best scored, skipped ones last."""
    in_ranking = set(ranked)
    left_out = set(_ids(row.left_out)) if row else set()
    later = _ids(row.later) if row else []
    if finished is None:
        finished = _finished(db, user_id, category)
    waiting = [item_id for item_id, _ in finished if item_id not in in_ranking and item_id not in left_out]
    waiting_set = set(waiting)
    later_set = set(later)
    first = [item_id for item_id in _recent(db, user_id, category, now)
             if item_id in waiting_set and item_id not in later_set]
    first_set = set(first)
    middle = [item_id for item_id in waiting if item_id not in later_set and item_id not in first_set]
    last = [item_id for item_id in later if item_id in waiting_set]
    return first + middle + last


def _question(db: Session, user_id: int, category: str, placing_id: int, against_id: int, *, ranked: list[int],
              low: int, high: int, steps: int, finished: int, fresh: bool = False) -> Optional[dict]:
    rows = _rows(db, user_id, category, [placing_id, against_id])
    if placing_id not in rows or against_id not in rows:
        return None
    against = card(category, rows[against_id])
    if against_id in ranked:
        against["position"] = ranked.index(against_id) + 1
    singular, plural = NOUNS[category]
    return {
        "category": category,
        "label": LABELS[category],
        "noun": singular,
        "nouns": plural,
        "placing": card(category, rows[placing_id]),
        "against": against,
        "step": steps + 1,
        "left": _remaining(low, high) if ranked else 1,
        "ranked": len(ranked),
        "finished": finished,
        "fresh": fresh,
    }


def question(db: Session, user: models.User, category: str, now: Optional[datetime] = None) -> Optional[dict]:
    """The question to ask next in one format, without writing anything. None when there's nothing to compare."""
    _check_category(category)
    now = now or _now()
    row = _row(db, user.id, category)
    ranked = _tidy(db, user.id, category, row)
    finished = _finished(db, user.id, category)
    finished_count = len(finished)
    if row is not None and row.placing_id and ranked:
        # answer() takes the same stretch, so the question shown is always the one it accepts.
        if row.placing_id not in ranked and _is_finished(db, user.id, category, row.placing_id):
            low, high = _window(row, ranked)
            mid = (low + high) // 2
            return _question(db, user.id, category, row.placing_id, ranked[mid], ranked=ranked, low=low, high=high,
                             steps=row.steps or 0, finished=finished_count)
    queue = _queue(db, user.id, category, row, ranked, now, finished)
    if not queue:
        return None
    placing = queue[0]
    fresh = placing in set(_recent(db, user.id, category, now, FRESH))
    if not ranked:
        if len(queue) < 2:
            return None
        return _question(db, user.id, category, placing, queue[1], ranked=[], low=0, high=0, steps=0,
                         finished=finished_count, fresh=fresh)
    return _question(db, user.id, category, placing, ranked[len(ranked) // 2], ranked=ranked, low=0, high=len(ranked),
                     steps=0, finished=finished_count, fresh=fresh)


def _insert(row: models.Ranking, ranked: list[int], item_id: int, at: int) -> int:
    at = max(0, min(at, len(ranked)))
    ranked.insert(at, item_id)
    row.ranked = _dump(ranked[:MAX_RANKED])
    later = [value for value in _ids(row.later) if value != item_id]
    row.later = _dump(later) if later else None
    row.placed_total = (row.placed_total or 0) + 1
    _cancel(row)
    return at + 1


def _placed(db: Session, user_id: int, category: str, ranked: list[int], position: int, steps: int) -> dict:
    """What the member sees once a title lands: where, and its neighbours either side."""
    index = position - 1
    around = [ranked[i] for i in (index - 1, index, index + 1) if 0 <= i < len(ranked)]
    rows = _rows(db, user_id, category, around)
    item_id = ranked[index]
    above = card(category, rows[ranked[index - 1]]) if index > 0 and ranked[index - 1] in rows else None
    below = card(category, rows[ranked[index + 1]]) if index + 1 < len(ranked) and ranked[index + 1] in rows else None
    singular, plural = NOUNS[category]
    return {
        "category": category,
        "label": LABELS[category],
        "noun": singular,
        "nouns": plural,
        "title": card(category, rows[item_id]) if item_id in rows else None,
        "position": position,
        "total": len(ranked),
        "above": above,
        "below": below,
        "steps": steps,
    }


def answer(db: Session, user: models.User, category: str, placing_id: int, against_id: int, choice: str,
           source: str = "tab", now: Optional[datetime] = None) -> dict:
    """Apply one answer. {"placed": {...}} once the title lands, else {"question": {...}} for the next one.

    Raises Stale when the answer is for a question that isn't the current one, and LookupError when
    either title isn't a finished title of the member's in this format.
    """
    _check_category(category)
    if choice not in CHOICES:
        raise ValueError("Pick one of the two, or say it's too close to call.")
    if placing_id == against_id:
        raise Stale()
    now = now or _now()
    from .progress import lock_progress_owner
    lock_progress_owner(db, user.id)
    row = _row_for_write(db, user.id, category)
    ranked = _tidy(db, user.id, category, row)
    first_ever = not ranked and not (row.placed_total or 0)
    if row.placing_id and (row.placing_id in ranked or not ranked
                           or not _is_finished(db, user.id, category, row.placing_id)):
        _cancel(row)  # what was being placed was deleted, unfinished or placed some other way since
    if row.placing_id is None:
        if placing_id in ranked or not _is_finished(db, user.id, category, placing_id):
            raise Stale()
        if placing_id in set(_ids(row.left_out)):
            raise Stale()
        if not ranked:
            if against_id in set(_ids(row.left_out)) or not _is_finished(db, user.id, category, against_id):
                raise Stale()
            ranked = [against_id]
            row.ranked = _dump(ranked)
            row.placed_total = (row.placed_total or 0) + 1
        row.placing_id = placing_id
        row.ranked = _dump(ranked)
        row.low, row.high, row.steps = 0, len(ranked), 0
    elif row.placing_id != placing_id:
        raise Stale()
    low, high = _window(row, ranked)
    row.ranked = _dump(ranked)  # the stretch saved below counts places in this list, deleted titles gone
    mid = (low + high) // 2
    if ranked[mid] != against_id:
        raise Stale()
    steps = (row.steps or 0) + 1
    count("answered")
    position = None
    if choice == "tie":
        count("tie")
        position = _insert(row, ranked, placing_id, mid + 1)
    elif choice == "placing":
        high = mid
    else:
        low = mid + 1
    if position is None and low >= high:
        position = _insert(row, ranked, placing_id, low)
    row.updated_at = now
    if position is None:
        row.low, row.high, row.steps = low, high, steps
        db.commit()
        result = _question(db, user.id, category, placing_id, ranked[(low + high) // 2], ranked=ranked, low=low, high=high,
                           steps=steps, finished=len(_finished(db, user.id, category)))
        return {"question": result}
    db.commit()
    count("placed")
    count(f"from_{source}" if source in SOURCES else "from_tab")
    if first_ever:
        count("first")
    return {"placed": _placed(db, user.id, category, ranked, position, steps)}


def place(db: Session, user: models.User, category: str, item_id: int, source: str = "tab",
          now: Optional[datetime] = None) -> dict:
    """Start placing one title the member chose (again, if it's ranked already). The first title lands at #1."""
    _check_category(category)
    now = now or _now()
    if not _is_finished(db, user.id, category, item_id):
        raise LookupError("Mark it finished first, then rank it.")
    from .progress import lock_progress_owner
    lock_progress_owner(db, user.id)
    row = _row_for_write(db, user.id, category)
    ranked = [value for value in _tidy(db, user.id, category, row) if value != item_id]
    row.ranked = _dump(ranked)
    left_out = [value for value in _ids(row.left_out) if value != item_id]
    row.left_out = _dump(left_out) if left_out else None
    row.updated_at = now
    if not ranked:
        first_ever = not (row.placed_total or 0)
        position = _insert(row, ranked, item_id, 0)
        db.commit()
        count("placed")
        count(f"from_{source}" if source in SOURCES else "from_tab")
        if first_ever:
            count("first")
        return {"placed": _placed(db, user.id, category, ranked, position, 0)}
    row.placing_id = item_id
    row.low, row.high, row.steps = 0, len(ranked), 0
    db.commit()
    return {"question": _question(db, user.id, category, item_id, ranked[len(ranked) // 2], ranked=ranked, low=0,
                                  high=len(ranked), steps=0, finished=len(_finished(db, user.id, category)))}


def skip(db: Session, user: models.User, category: str, item_id: int, leave_out: bool = False,
         now: Optional[datetime] = None) -> None:
    """Stop placing a title: to the back of the queue, or ("Leave it out") never offered again."""
    _check_category(category)
    now = now or _now()
    row = _row_for_write(db, user.id, category)
    if row.placing_id == item_id:
        _cancel(row)
    if leave_out:
        left_out = [value for value in _ids(row.left_out) if value != item_id] + [item_id]
        row.left_out = _dump(left_out[-MAX_LEFT_OUT:])
        stored = _ids(row.ranked)
        ranked = [value for value in stored if value != item_id]
        row.ranked = _dump(ranked)
        if row.placing_id and len(ranked) != len(stored):
            row.low, row.high, row.steps = 0, len(ranked), 0  # the stretch moved; ask again from the middle
        count("left_out")
    else:
        later = [value for value in _ids(row.later) if value != item_id] + [item_id]
        row.later = _dump(later[-MAX_LATER:])
        count("skipped")
    row.updated_at = now
    db.commit()


def move(db: Session, user: models.User, category: str, item_id: int, position: int,
         now: Optional[datetime] = None) -> int:
    """Move a ranked title to a place (1 = top) by hand. Returns where it ended up."""
    _check_category(category)
    row = _row_for_write(db, user.id, category)
    ranked = _tidy(db, user.id, category, row)
    if item_id not in ranked:
        raise LookupError("That title isn't in this ranking.")
    ranked.remove(item_id)
    at = max(0, min(int(position) - 1, len(ranked)))
    ranked.insert(at, item_id)
    row.ranked = _dump(ranked)
    if row.placing_id:  # the stretch it could land in moved; ask again from the middle
        row.low, row.high, row.steps = 0, len(ranked), 0
    row.updated_at = now or _now()
    db.commit()
    count("moved")
    return at + 1


def remove(db: Session, user: models.User, category: str, item_id: int, now: Optional[datetime] = None) -> None:
    """Take a title off the ranking. It goes back to the titles waiting to be ranked."""
    _check_category(category)
    row = _row_for_write(db, user.id, category)
    ranked = _tidy(db, user.id, category, row)
    if item_id not in ranked:
        raise LookupError("That title isn't in this ranking.")
    ranked.remove(item_id)
    row.ranked = _dump(ranked)
    later = [value for value in _ids(row.later) if value != item_id] + [item_id]
    row.later = _dump(later[-MAX_LATER:])
    if row.placing_id:
        if ranked:
            row.low, row.high, row.steps = 0, len(ranked), 0
        else:
            _cancel(row)
    row.updated_at = now or _now()
    db.commit()
    count("removed")


def restore(db: Session, user: models.User, category: str, item_id: int, now: Optional[datetime] = None) -> None:
    """Put a left-out title back with the ones waiting to be ranked."""
    _check_category(category)
    row = _row(db, user.id, category, lock=True)
    if row is None:
        return
    left_out = [value for value in _ids(row.left_out) if value != item_id]
    row.left_out = _dump(left_out) if left_out else None
    row.updated_at = now or _now()
    db.commit()


def set_public(db: Session, user: models.User, category: str, public: bool, now: Optional[datetime] = None) -> bool:
    _check_category(category)
    row = _row_for_write(db, user.id, category)
    changed = bool(row.public) != bool(public)
    row.public = bool(public)
    row.updated_at = now or _now()
    db.commit()
    if changed:
        count("public_on" if public else "public_off")
    return row.public


def to_collection(db: Session, user: models.User, category: str, top: int = 10,
                  now: Optional[datetime] = None) -> dict:
    """Save the top of a ranking as a new ranked collection (private, shareable by link from Collections)."""
    _check_category(category)
    row = _row(db, user.id, category)
    ranked = _tidy(db, user.id, category, row)
    top = max(3, min(int(top or 10), 50))
    picks = ranked[:top]
    if len(picks) < 3:
        raise LookupError("Rank at least three to make a list of them.")
    singular, plural = NOUNS[category]
    name = f"My top {len(picks)} {plural}"
    collection = models.Collection(
        user_id=user.id, name=name[:80], ranked=True,
        description=f"My favourite {plural}, best first. I put them in order on OmniTrackr two at a time.",
    )
    db.add(collection)
    db.flush()
    for position, item_id in enumerate(picks):
        db.add(models.CollectionItem(collection_id=collection.id, category=category, item_id=item_id, position=position))
    db.commit()
    count("collection")
    return {"id": collection.id, "name": collection.name, "count": len(picks)}


# ---------------------------------------------------------------- what the pages show

def _summary(db: Session, user: models.User, category: str, row: Optional[models.Ranking], now: datetime) -> dict:
    ranked = _tidy(db, user.id, category, row)
    finished = _finished(db, user.id, category)
    left_out = set(_ids(row.left_out)) if row else set()
    in_ranking = set(ranked)
    waiting = sum(1 for item_id, _ in finished if item_id not in in_ranking and item_id not in left_out)
    top_rows = _rows(db, user.id, category, ranked[:3])
    singular, plural = NOUNS[category]
    return {
        "category": category,
        "label": LABELS[category],
        "noun": singular,
        "nouns": plural,
        "verb": VERBS[category],
        "finished": len(finished),
        "ranked": len(ranked),
        "waiting": waiting,
        "public": bool(row and row.public),
        "placing": bool(row and row.placing_id),
        "top": [card(category, top_rows[item_id]) for item_id in ranked[:3] if item_id in top_rows],
    }


def overview(db: Session, user: models.User, now: Optional[datetime] = None) -> dict:
    """Every visible format: how many are finished, ranked and waiting, and the top three."""
    now = now or _now()
    visible = _visible(user)
    rows = {row.category: row for row in db.query(models.Ranking).filter(models.Ranking.user_id == user.id).all()}
    formats = [_summary(db, user, category, rows.get(category), now) for category in visible]
    return {
        "formats": formats,
        "ranked": sum(item["ranked"] for item in formats),
        "profile": _profile_state(db, user),
    }


def _profile_state(db: Session, user: models.User) -> dict:
    """Whether the member has a public profile the top tens could go on, and its address."""
    profile = db.query(models.PublicProfile).filter(models.PublicProfile.user_id == user.id).first()
    enabled = bool(profile and profile.enabled)
    path = None
    if enabled:
        try:
            from .public_profiles import profile_path
            path = profile_path(user)
        except Exception:
            path = None
    return {"enabled": enabled, "path": path}


def detail(db: Session, user: models.User, category: str, now: Optional[datetime] = None) -> dict:
    """One format: the whole ranking, the titles waiting, the ones left out and the next question."""
    _check_category(category)
    now = now or _now()
    row = _row(db, user.id, category)
    ranked = _tidy(db, user.id, category, row)
    queue = _queue(db, user.id, category, row, ranked, now)
    left_out = _ids(row.left_out) if row else []
    rows = _rows(db, user.id, category, ranked + queue[:120] + left_out[:120])
    singular, plural = NOUNS[category]
    ranked_cards = []
    for position, item_id in enumerate(ranked, start=1):
        if item_id in rows:
            item = card(category, rows[item_id])
            item["position"] = position
            ranked_cards.append(item)
    return {
        "category": category,
        "label": LABELS[category],
        "noun": singular,
        "nouns": plural,
        "verb": VERBS[category],
        "ranked": ranked_cards,
        "waiting": [card(category, rows[item_id]) for item_id in queue[:120] if item_id in rows],
        "waiting_total": len(queue),
        "left_out": [card(category, rows[item_id]) for item_id in left_out[:120] if item_id in rows],
        "public": bool(row and row.public),
        "question": question(db, user, category, now),
        "profile": _profile_state(db, user),
    }


def home(db: Session, user: models.User, now: Optional[datetime] = None) -> Optional[dict]:
    """The home card: a placement under way, then a title finished this week, then a format to start or go on with.

    status is "placing" (part-way through one), "fresh" (finished in the last week), "start"
    (nothing ranked yet but enough finished to begin) or "more" (titles still waiting). None hides
    the card: fewer than two finished titles in every format, or everything ranked.
    """
    now = now or _now()
    visible = _visible(user)
    rows = {row.category: row for row in db.query(models.Ranking).filter(models.Ranking.user_id == user.id).all()}
    ranked_total = sum(len(_ids(row.ranked)) for category, row in rows.items() if category in visible)
    placing = sorted((row for category, row in rows.items() if category in visible and row.placing_id),
                     key=lambda row: row.updated_at or datetime.min, reverse=True)
    for row in placing:
        found = question(db, user, row.category, now)
        if found and found["step"] > 1:
            return {"status": "placing", "question": found, "ranked_total": ranked_total}
    latest = db.query(models.ActivityEntry.category, func.max(models.ActivityEntry.occurred_at)).filter(
        models.ActivityEntry.user_id == user.id, models.ActivityEntry.category.in_(visible),
        models.ActivityEntry.action.in_(("completed", "revisited")), models.ActivityEntry.item_id.isnot(None),
        models.ActivityEntry.occurred_at >= now - FRESH,
    ).group_by(models.ActivityEntry.category).all()
    fresh = [category for category, _ in sorted(latest, key=lambda row: row[1], reverse=True)]
    for category in fresh:
        found = question(db, user, category, now)
        if found and found["fresh"]:
            return {"status": "fresh", "question": found, "ranked_total": ranked_total}
    for row in placing:
        found = question(db, user, row.category, now)
        if found:
            return {"status": "placing", "question": found, "ranked_total": ranked_total}
    counts = []
    for category in visible:
        model, done_field, _label, _button = _categories()[category]
        finished = db.query(func.count(model.id)).filter(
            model.user_id == user.id, getattr(model, done_field) == True).scalar() or 0  # noqa: E712
        if finished >= 2:
            counts.append((finished, category))
    for finished, category in sorted(counts, reverse=True):
        found = question(db, user, category, now)
        if found:
            return {"status": "more" if ranked_total else "start", "question": found, "ranked_total": ranked_total}
    return None


def public_lists(db: Session, user: models.User, visible: Optional[Iterable[str]] = None) -> list[dict]:
    """The top tens a member chose to show on their public profile, biggest ranking first."""
    shown = set(_visible(user))
    if visible is not None:
        shown &= set(visible)
    lists = []
    for row in db.query(models.Ranking).filter(models.Ranking.user_id == user.id, models.Ranking.public == True).all():  # noqa: E712
        if row.category not in shown:
            continue
        ranked = _tidy(db, user.id, row.category, row)
        if len(ranked) < 3:
            continue
        rows = _rows(db, user.id, row.category, ranked[:PUBLIC_TOP])
        items = []
        for position, item_id in enumerate(ranked[:PUBLIC_TOP], start=1):
            if item_id in rows:
                item = card(row.category, rows[item_id])
                item.pop("score", None)  # the order is shared, never the scores
                item["position"] = position
                items.append(item)
        singular, plural = NOUNS[row.category]
        lists.append({"category": row.category, "label": LABELS[row.category], "nouns": plural,
                      "total": len(ranked), "items": items})
    order = list(_categories())
    return sorted(lists, key=lambda item: (-item["total"], order.index(item["category"])))


def ranked_total(db: Session, user_id: int) -> int:
    """Titles in all of a member's rankings (for the badge). Ids only, so deleted titles may count until next read."""
    return sum(len(_ids(text)) for (text,) in db.query(models.Ranking.ranked).filter(models.Ranking.user_id == user_id).all())


def stats(db: Session, days: int, now: datetime) -> dict:
    table = models.SiteTrafficDaily
    counts = dict(db.query(table.key, func.sum(table.count)).filter(
        table.kind == "rank", table.day >= (now - timedelta(days=days - 1)).date(),
    ).group_by(table.key).all())
    members: dict[int, int] = {}
    public_now = 0
    by_format: dict[str, int] = {}
    for user_id, category, ranked, public in db.query(models.Ranking.user_id, models.Ranking.category,
                                                       models.Ranking.ranked, models.Ranking.public).all():
        size = len(_ids(ranked))
        if size:
            members[user_id] = members.get(user_id, 0) + size
            by_format[category] = by_format.get(category, 0) + 1
        if public and size >= 3:
            public_now += 1
    return {
        "counts": {key: int(counts.get(key) or 0) for key in COUNTERS},
        "labels": COUNTERS,
        "members_now": len(members),
        "members_ten_now": sum(1 for size in members.values() if size >= 10),
        "titles_now": sum(members.values()),
        "public_now": public_now,
        "by_format": [{"label": LABELS[category], "count": by_format[category]}
                      for category in _categories() if by_format.get(category)],
    }
