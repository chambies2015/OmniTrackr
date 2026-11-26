"""Fill in your year: date the finishes OmniTrackr never recorded, so Year in Review covers all of it.

Year in Review counts a finish only when it has a date: a journal "Finished"
entry or a completion moment. Dated finishes began in September 2026, so a 2026
recap shows the autumn and nothing before it, even for a member whose library
is full of titles ticked off in spring. Imports leave titles ticked off without
a date too. This asks about those titles, one at a time, with a row of months:

- "Ticked off, no date": finished titles with no finish recorded anywhere.
  A month gives the title a finish on the 15th of that month (journal source
  "filled-in"); "Before 2026" and "Not sure" only remember the answer.
- "Still on your list": titles saved before this month and never ticked off.
  A month ticks the title off with that date; "Not yet" only remembers it.

A finish dated to an earlier month counts where the year is counted (Year in
Review, yearly goals, the New Year pledge presets, badges) and nowhere a month
or a day is judged as it happens: monthly challenges, trending and streak days
skip the "filled-in" source. Picking the current month is the same as ticking
the title off today. Every answer can be undone straight away, and nothing in
the library changes except the done tick on a "Still on your list" title.

The page is /year-in-review/<year>/fill for members. A December email (owner
Start switch on Site stats, Dec 1 to 14 only, once a year) links to a page at
/fill-in/<token> that works without signing in, for the titles named in it.

Email rules (all of them, every time):
- Nothing is sent until the site owner presses Start, and only from December 1
  to 14 (UTC). One per member per year.
- Verified, active members who joined before December; anyone who unsubscribed
  from product updates is skipped, and so are weekly-email subscribers (their
  weekly email links the recap in December already).
- None within 72 hours of any other product email; paused while "What's new"
  is sending; kept inside YEAR_FILL_DAILY_LIMIT (default 30) and the shared
  daily email budget. YEAR_FILL_EMAILS=off stops the loop.
- Members with nothing to fill in and nothing finished that year get none.

Counters go into site_traffic_daily under kind "yearfill" and name no member.
"""
from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, timedelta, timezone
from html import escape
from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models
from .digest import app_url, mail_configured

FILLED_SOURCE = "filled-in"   # journal source of a finish dated here to an earlier month
FIRST_YEAR = 2026             # the first year with dated finishes; earlier years have nothing to fill in
# Years whose recap only starts part way through: the month dated finishes began.
DATED_FROM = {2026: 9}
DECK_LIMIT = 40               # undated titles loaded at once; the page reloads more as they're answered
OPEN_LIMIT = 12               # "still on your list" titles shown at once
BULK_LIMIT = 2000             # "the rest were before" answers at most this many titles in one press
FILL_DAY = 15                 # an earlier month's finish is dated the 15th, at noon UTC
ANSWERS = ("month", "before", "skip")
SOURCES = {"page": "Fill-in page", "email": "December email"}
COUNTER_KEYS = ("opened", "dated", "before", "skipped", "ticked", "undone", "all_done")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]

STATE_KEY = "year-fill"       # the EmailCampaign row holding the owner's on/off switch
SEND_PREFIX = "yearfill-"     # each send is an EmailCampaignSend row keyed by year
SEND_LAST_DAY = 14            # December 1 to 14
GAP = timedelta(hours=72)
CAME_BACK_WITHIN_DAYS = 7
PER_RUN_LIMIT = 10
CHECK_EVERY_SECONDS = 3600
FIRST_CHECK_DELAY_SECONDS = 540
TOKEN_SALT = "omnitrackr-year-fill-v1"
TOKEN_MAX_AGE = 60 * 60 * 24 * 30
TOKEN_MAX_LENGTH = 500
TOKEN_MAX_ITEMS = 6
UTM = "utm_source=email&utm_campaign=year-fill"


def _check_in():
    from . import check_in
    return check_in


def categories() -> dict:
    """Library category -> (model, finished field, label, "finished" button text), shared with check-ins."""
    return _check_in().CATEGORIES


# A podcast never really ends, so it is never asked about as "still on your list".
NEVER_OPEN = {"podcasts"}
OPEN_QUESTIONS = {
    "movies": "Did you watch it in {year}?", "tv-shows": "Did you finish it in {year}?",
    "anime": "Did you finish it in {year}?", "video-games": "Did you finish it in {year}?",
    "music": "Did you listen to it in {year}?", "books": "Did you read it in {year}?",
    "manga": "Did you read it in {year}?", "audiobooks": "Did you finish it in {year}?",
}
UNDATED_QUESTIONS = {
    "movies": "When did you watch it?", "tv-shows": "When did you finish it?", "anime": "When did you finish it?",
    "video-games": "When did you finish it?", "music": "When did you listen to it?", "books": "When did you read it?",
    "manga": "When did you read it?", "podcasts": "When did you finish it?", "audiobooks": "When did you finish it?",
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------- which years

def fill_years(today: Optional[date] = None) -> list[int]:
    """Years a member can fill in now: this year, and last year during January (while its recap is promoted)."""
    from .year_in_review import season_year
    today = today or _now().date()
    years = {today.year}
    season = season_year(today)
    if season:
        years.add(season)
    return sorted((year for year in years if year >= FIRST_YEAR), reverse=True)


def is_fill_year(year: int, today: Optional[date] = None) -> bool:
    return year in fill_years(today)


def months_for(year: int, today: Optional[date] = None) -> list[dict]:
    """The month buttons: every month of a past year, January to this month of this one."""
    today = today or _now().date()
    last = 12 if year < today.year else today.month
    return [{"n": n, "name": MONTHS[n - 1], "short": MONTHS[n - 1][:3],
             "current": year == today.year and n == today.month} for n in range(1, last + 1)]


def dated_from(year: int) -> Optional[str]:
    """"September" for a year whose dated finishes start part way through, else None."""
    month = DATED_FROM.get(year)
    return MONTHS[month - 1] if month else None


# ---------------------------------------------------------------- what to ask about

def _image(category: str, row) -> Optional[str]:
    return _check_in()._image(category, row)


def _release_year(row) -> Optional[int]:
    year = getattr(row, "year", None)
    if isinstance(year, int) and 1000 < year < 2200:
        return year
    released = getattr(row, "release_date", None)
    found = getattr(released, "year", None)
    return found if isinstance(found, int) else None


def _card(category: str, row, kind: str, year: int) -> dict:
    model, done_field, label, _button = categories()[category]
    question = (UNDATED_QUESTIONS[category] if kind == "undated"
                else OPEN_QUESTIONS.get(category, "Did you finish it in {year}?").format(year=year))
    return {
        "category": category,
        "id": row.id,
        "title": " ".join((row.title or "").split())[:200],
        "label": label,
        "kind": kind,
        "question": question,
        "image": _image(category, row),
        "year": _release_year(row),
    }


def _answered(db: Session, user_id: int, year: int) -> dict[str, set[int]]:
    """Titles not to ask about this year: anything answered for this year, and "before" answers from earlier years
    (finished before 2026 is finished before 2027 too)."""
    found: dict[str, set[int]] = {}
    rows = db.query(models.YearFillAnswer.category, models.YearFillAnswer.item_id).filter(
        models.YearFillAnswer.user_id == user_id,
        (models.YearFillAnswer.year == year)
        | ((models.YearFillAnswer.answer == "before") & (models.YearFillAnswer.year < year)),
    ).all()
    for category, item_id in rows:
        found.setdefault(category, set()).add(item_id)
    return found


def _dated(db: Session, user_id: int, category: str) -> set[int]:
    """Library rows of one category that have a finish recorded anywhere (a journal finish or a completion moment)."""
    entries = db.query(models.ActivityEntry.item_id).filter(
        models.ActivityEntry.user_id == user_id, models.ActivityEntry.category == category,
        models.ActivityEntry.action == "completed", models.ActivityEntry.item_id.isnot(None)).distinct()
    moments = db.query(models.CompletionMoment.item_id).filter(
        models.CompletionMoment.user_id == user_id, models.CompletionMoment.category == category).distinct()
    return {item_id for (item_id,) in entries} | {item_id for (item_id,) in moments}


def _undated_ids(db: Session, user_id: int, year: int) -> list[tuple[str, int]]:
    """(category, id) of finished titles with no finish date, the newest rows of each shelf first."""
    answered = _answered(db, user_id, year)
    found: list[tuple[str, int]] = []
    for category, (model, done_field, _label, _button) in categories().items():
        ids = [item_id for (item_id,) in db.query(model.id).filter(
            model.user_id == user_id, getattr(model, done_field) == True,  # noqa: E712
            model.title.isnot(None), func.trim(model.title) != "").all()]
        if not ids:
            continue
        skip = _dated(db, user_id, category) | answered.get(category, set())
        found.extend((category, item_id) for item_id in ids if item_id not in skip)
    found.sort(key=lambda ref: ref[1], reverse=True)
    return found


def _open_ids(db: Session, user_id: int, year: int, today: date) -> list[tuple[datetime, str, int]]:
    """(added_at, category, id) of titles saved before this month (and before the year ended) and never ticked off."""
    answered = _answered(db, user_id, year)
    month_start = datetime(today.year, today.month, 1)
    year_end = datetime(year + 1, 1, 1)
    cutoff = min(month_start, year_end)
    found: list[tuple[datetime, str, int]] = []
    for category, (model, done_field, _label, _button) in categories().items():
        if category in NEVER_OPEN:
            continue
        rows = db.query(model.added_at, model.id).filter(
            model.user_id == user_id, getattr(model, done_field) != True,  # noqa: E712
            model.title.isnot(None), func.trim(model.title) != "",
            (model.added_at.is_(None)) | (model.added_at < cutoff)).all()
        skip = answered.get(category, set())
        found.extend((added_at or datetime(2000, 1, 1), category, item_id)
                     for added_at, item_id in rows if item_id not in skip)
    found.sort(key=lambda ref: (ref[0], ref[2]), reverse=True)
    return found


def _cards(db: Session, refs: list[tuple[str, int]], kind: str, year: int, user_id: int) -> list[dict]:
    by_category: dict[str, list[int]] = {}
    for category, item_id in refs:
        by_category.setdefault(category, []).append(item_id)
    rows: dict[tuple[str, int], dict] = {}
    for category, ids in by_category.items():
        model = categories()[category][0]
        for row in db.query(model).filter(model.user_id == user_id, model.id.in_(ids)).all():
            rows[(category, row.id)] = _card(category, row, kind, year)
    return [rows[ref] for ref in refs if ref in rows]


def undated(db: Session, user_id: int, year: int, limit: int = DECK_LIMIT) -> tuple[list[dict], int]:
    """(cards, how many there are in all) for finished titles with no date."""
    refs = _undated_ids(db, user_id, year)
    return _cards(db, refs[:limit], "undated", year, user_id), len(refs)


def unfinished(db: Session, user_id: int, year: int, limit: int = OPEN_LIMIT,
               today: Optional[date] = None) -> tuple[list[dict], int]:
    """(cards, how many there are in all) for titles still on the list that might have been finished that year."""
    today = today or _now().date()
    refs = [(category, item_id) for _, category, item_id in _open_ids(db, user_id, year, today)]
    return _cards(db, refs[:limit], "open", year, user_id), len(refs)


def finished_total(db: Session, user_id: int, year: int) -> int:
    from .year_in_review import finished_counts
    return sum(finished_counts(db, user_id, year).values())


def filled_total(db: Session, user_id: int, year: int) -> int:
    """Titles this member gave a month for that year."""
    return int(db.query(func.count(models.YearFillAnswer.id)).filter(
        models.YearFillAnswer.user_id == user_id, models.YearFillAnswer.year == year,
        models.YearFillAnswer.answer == "month").scalar() or 0)


def summary(db: Session, user_id: int, year: int, today: Optional[date] = None) -> dict:
    """Counts for the home banner and the recap page box."""
    today = today or _now().date()
    return {
        "year": year,
        "undated": len(_undated_ids(db, user_id, year)),
        "open": len(_open_ids(db, user_id, year, today)),
        "filled": filled_total(db, user_id, year),
        "url": f"/year-in-review/{year}/fill",
        "dated_from": dated_from(year),
    }


def state(db: Session, user_id: int, year: int, today: Optional[date] = None) -> dict:
    """Everything the fill-in page shows."""
    today = today or _now().date()
    deck, deck_total = undated(db, user_id, year)
    still, still_total = unfinished(db, user_id, year, today=today)
    skipped = int(db.query(func.count(models.YearFillAnswer.id)).filter(
        models.YearFillAnswer.user_id == user_id, models.YearFillAnswer.year == year,
        models.YearFillAnswer.answer.in_(("before", "skip")), models.YearFillAnswer.ticked == False,  # noqa: E712
    ).scalar() or 0)
    return {
        "year": year,
        "months": months_for(year, today),
        "dated_from": dated_from(year),
        "undated": deck, "undated_total": deck_total,
        "open": still, "open_total": still_total,
        "finished_total": finished_total(db, user_id, year),
        "filled": filled_total(db, user_id, year),
        "skipped": skipped,
        "recap_url": f"/year-in-review/{year}",
    }


# ---------------------------------------------------------------- answering

def _fill_moment(year: int, month: int, now: datetime) -> Optional[datetime]:
    """When a finish in that month is dated: the 15th at noon, or None for this month (a normal tick, dated now)."""
    if year == now.year and month == now.month:
        return None
    return datetime(year, month, FILL_DAY, 12, 0)


def answer(db: Session, user: models.User, year: int, category: str, item_id: int, choice: str,
           month: Optional[int] = None, source: str = "page", now: Optional[datetime] = None) -> Optional[dict]:
    """Save one answer. Returns {"state", "kind", "month", "title"}, or None when the title is gone.

    "month" dates the finish (and ticks a "still on your list" title off); "before" remembers that it was
    finished before the year, ticking a "still on your list" title off without a date; "skip" only remembers.
    Answering a title twice keeps the first answer (a double tap, or two tabs).
    """
    from .progress import lock_progress_owner
    from .routers.activity import record_completion_activity
    now = now or _now()
    if category not in categories() or choice not in ANSWERS:
        raise ValueError("unknown answer")
    if not is_fill_year(year, now.date()):
        raise ValueError("that year can't be filled in")
    if choice == "month":
        if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= len(months_for(year, now.date())):
            raise ValueError("pick a month of that year")
    else:
        month = None
    model, done_field, _label, _button = categories()[category]
    lock_progress_owner(db, user.id)
    row = db.query(model).filter(model.id == item_id, model.user_id == user.id).first()
    if row is None or not (row.title or "").strip():
        db.rollback()
        return None
    existing = db.query(models.YearFillAnswer).filter_by(
        user_id=user.id, year=year, category=category, item_id=item_id).first()
    if existing is not None:
        db.rollback()
        return {"state": "already", "kind": existing.kind, "month": existing.month, "title": row.title}
    finished = bool(getattr(row, done_field))
    kind = "undated" if finished else "open"
    if kind == "undated" and item_id in _dated(db, user.id, category):
        # Ticked off with a date somewhere else since the page loaded.
        db.rollback()
        return {"state": "dated", "kind": kind, "month": None, "title": row.title}
    if kind == "open" and category in NEVER_OPEN:
        db.rollback()
        raise ValueError("podcasts aren't asked about")
    record = models.YearFillAnswer(user_id=user.id, year=year, category=category, item_id=item_id, kind=kind,
                                   answer=choice, month=month, source=source if source in SOURCES else "page",
                                   created_at=now)
    if choice == "month" or (choice == "before" and kind == "open"):
        if kind == "open":
            setattr(row, done_field, True)
            record.ticked = True
    if choice == "month":
        moment = _fill_moment(year, month, now)
        if moment is None:
            entry = record_completion_activity(db, user.id, category, row)
        else:
            entry = models.ActivityEntry(user_id=user.id, category=category, item_id=row.id, title=row.title,
                                         action="completed", rating=row.rating, source=FILLED_SOURCE,
                                         occurred_at=moment, created_at=now)
            db.add(entry)
        db.flush()
        record.entry_id = entry.id
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"state": "already", "kind": kind, "month": None, "title": row.title}
    return {"state": choice, "kind": kind, "month": month, "title": row.title}


def undo(db: Session, user: models.User, year: int, category: str, item_id: int) -> bool:
    """Take back one answer: the finish it dated goes, and a title it ticked off is on the list again."""
    from .progress import lock_progress_owner
    if category not in categories():
        return False
    lock_progress_owner(db, user.id)
    record = db.query(models.YearFillAnswer).filter_by(
        user_id=user.id, year=year, category=category, item_id=item_id).first()
    if record is None:
        db.rollback()
        return False
    if record.entry_id:
        entry = db.get(models.ActivityEntry, record.entry_id)
        if (entry is not None and entry.user_id == user.id and entry.category == category
                and entry.item_id == item_id and entry.action == "completed"):
            db.delete(entry)
    if record.ticked:
        model, done_field, _label, _button = categories()[category]
        row = db.query(model).filter(model.id == item_id, model.user_id == user.id).first()
        if row is not None:
            setattr(row, done_field, False)
    db.delete(record)
    db.commit()
    return True


def answer_rest(db: Session, user: models.User, year: int, kind: str, source: str = "page",
                now: Optional[datetime] = None) -> int:
    """ "The rest were before 2026" (undated titles) or "None of these yet" (still on your list): one press answers
    every title still waiting of that kind, with "before" or "skip". Nothing in the library changes."""
    from .progress import lock_progress_owner
    now = now or _now()
    if kind not in ("undated", "open") or not is_fill_year(year, now.date()):
        raise ValueError("unknown list")
    lock_progress_owner(db, user.id)
    if kind == "undated":
        refs = _undated_ids(db, user.id, year)[:BULK_LIMIT]
        choice = "before"
    else:
        refs = [(category, item_id) for _, category, item_id in _open_ids(db, user.id, year, now.date())][:BULK_LIMIT]
        choice = "skip"
    for category, item_id in refs:
        db.add(models.YearFillAnswer(user_id=user.id, year=year, category=category, item_id=item_id, kind=kind,
                                     answer=choice, source=source if source in SOURCES else "page", created_at=now))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return 0
    return len(refs)


def bring_back(db: Session, user: models.User, year: int) -> int:
    """Ask again about titles answered "before", "not sure" or "not yet" that year (nothing was dated or ticked)."""
    query = db.query(models.YearFillAnswer).filter(
        models.YearFillAnswer.user_id == user.id, models.YearFillAnswer.year == year,
        models.YearFillAnswer.answer.in_(("before", "skip")), models.YearFillAnswer.ticked == False,  # noqa: E712
        models.YearFillAnswer.entry_id.is_(None))
    removed = query.delete(synchronize_session=False)
    db.commit()
    return int(removed or 0)


# ---------------------------------------------------------------- counters

def count(key: str) -> bool:
    """Add 1 to a "yearfill" counter for today. Never raises."""
    try:
        from .site_traffic import RECORDER
        if not RECORDER.enabled or len(key) > 60:
            return False
        day = datetime.now(timezone.utc).date()
        with RECORDER._lock:
            RECORDER._pending[(day, "yearfill", key)] += 1
            RECORDER._events += 1
        return True
    except Exception:
        return False


def count_answer(result: Optional[dict], source: str) -> None:
    if not result or result.get("state") not in ANSWERS:
        return
    source = source if source in SOURCES else "page"
    state_ = result["state"]
    count(f"{'dated' if state_ == 'month' else 'before' if state_ == 'before' else 'skipped'}_{source}")
    if result.get("kind") == "open" and state_ in ("month", "before"):
        count(f"ticked_{source}")


# ---------------------------------------------------------------- the link

def _serializer() -> URLSafeTimedSerializer:
    from . import auth
    return URLSafeTimedSerializer(auth.SECRET_KEY, salt=TOKEN_SALT)


def make_token(user_id: int, year: int, items: list[dict]) -> str:
    """A signed link for one member, one year and the titles named in one email. It expires after 30 days."""
    refs = [[item["category"], int(item["id"])] for item in items[:TOKEN_MAX_ITEMS]]
    return _serializer().dumps({"u": int(user_id), "y": int(year), "i": refs})


def read_token(token: str | None) -> Optional[dict]:
    """{"user_id", "year", "items": [(category, id)]} for a fresh, untampered link, else None."""
    if not token or len(token) > TOKEN_MAX_LENGTH:
        return None
    try:
        data = _serializer().loads(token, max_age=TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    user_id, year, refs = data.get("u"), data.get("y"), data.get("i")
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        return None
    if not isinstance(year, int) or isinstance(year, bool) or not FIRST_YEAR <= year <= 2200:
        return None
    if not isinstance(refs, list) or not 0 < len(refs) <= TOKEN_MAX_ITEMS:
        return None
    items = []
    for ref in refs:
        if (not isinstance(ref, list) or len(ref) != 2 or ref[0] not in categories()
                or not isinstance(ref[1], int) or isinstance(ref[1], bool) or not 0 < ref[1] <= 2147483647):
            return None
        items.append((ref[0], ref[1]))
    return {"user_id": user_id, "year": year, "items": items}


def link_for(token: str, index: Optional[int] = None) -> str:
    path = f"/fill-in/{token}?{UTM}"
    if index is not None:
        path += f"#yf-{index}"
    return f"{app_url()}{path}"


def token_items(db: Session, user_id: int, year: int, refs: list[tuple[str, int]]) -> list[Optional[dict]]:
    """The titles a link names, as they are now, in the link's order, with how each one was answered.
    None for a title deleted since."""
    found: list[Optional[dict]] = []
    answers = {(row.category, row.item_id): row for row in db.query(models.YearFillAnswer).filter(
        models.YearFillAnswer.user_id == user_id, models.YearFillAnswer.year == year)}
    for category, item_id in refs:
        model, done_field, _label, _button = categories()[category]
        row = db.query(model).filter(model.id == item_id, model.user_id == user_id).first()
        if row is None or not (row.title or "").strip():
            found.append(None)
            continue
        record = answers.get((category, item_id))
        kind = record.kind if record is not None else ("undated" if getattr(row, done_field) else "open")
        card = _card(category, row, kind, year)
        card["answer"] = record.answer if record is not None else None
        card["month"] = record.month if record is not None else None
        if record is None and kind == "undated" and item_id in _dated(db, user_id, category):
            card["answer"] = "dated"  # dated somewhere else since the email went out
        found.append(card)
    return found


# ---------------------------------------------------------------- owner switch

def campaign(db: Session) -> models.EmailCampaign:
    row = db.query(models.EmailCampaign).filter_by(key=STATE_KEY).first()
    if row is None:
        row = models.EmailCampaign(key=STATE_KEY, status="draft")
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def set_status(db: Session, new_status: str) -> models.EmailCampaign:
    row = campaign(db)
    if new_status == "sending" and row.started_at is None:
        row.started_at = datetime.utcnow()
    row.status = new_status
    db.commit()
    return row


def _whats_new_sending(db: Session) -> bool:
    from .announcements import CAMPAIGN_KEY
    row = db.query(models.EmailCampaign).filter_by(key=CAMPAIGN_KEY).first()
    return row is not None and row.status == "sending"


def daily_limit() -> int:
    try:
        return max(0, int(os.getenv("YEAR_FILL_DAILY_LIMIT", "30")))
    except ValueError:
        return 30


def enabled_for_process() -> bool:
    setting = os.getenv("YEAR_FILL_EMAILS", "").strip().lower()
    if setting in ("off", "0", "false", "no"):
        return False
    return os.getenv("TESTING", "").lower() != "true"


def send_window(now: datetime) -> Optional[int]:
    """The recap year the email is about while it may go out (December 1 to 14), else None."""
    if now.month == 12 and now.day <= SEND_LAST_DAY and now.year >= FIRST_YEAR:
        return now.year
    return None


def send_key(year: int) -> str:
    return f"{SEND_PREFIX}{year}"


# ---------------------------------------------------------------- who is due

def _with_library(db: Session, user_ids: list[int]) -> set[int]:
    """Members among ``user_ids`` with anything in their library (the cheap test before building an email)."""
    found: set[int] = set()
    for start in range(0, len(user_ids), 400):
        chunk = user_ids[start:start + 400]
        for model, _done, _label, _button in categories().values():
            found.update(user_id for (user_id,) in db.query(model.user_id).filter(
                model.user_id.in_(chunk)).distinct().all())
    return found


def due_members(db: Session, now: datetime, limit: int | None = None) -> list[models.User]:
    """Members who may get this year's email now, oldest accounts first. Empty outside December 1 to 14."""
    from .editorial_collections import EDITOR_USERNAME
    year = send_window(now)
    if year is None:
        return []
    opted = db.query(models.EmailOptOut.user_id)
    weekly = db.query(models.EmailDigestSubscription.user_id)
    sent = db.query(models.EmailCampaignSend.user_id).filter(
        models.EmailCampaignSend.campaign_key == send_key(year), models.EmailCampaignSend.status != "test")
    members = db.query(models.User).filter(
        models.User.is_active == True, models.User.is_verified == True,  # noqa: E712
        models.User.email.isnot(None), models.User.email != "",
        models.User.username != EDITOR_USERNAME,
        models.User.created_at.isnot(None), models.User.created_at < datetime(year, 12, 1),
        ~models.User.id.in_(opted), ~models.User.id.in_(weekly), ~models.User.id.in_(sent),
    ).order_by(models.User.id).all()
    if not members:
        return []
    ids = [user.id for user in members]
    last_email: dict[int, datetime] = {}
    for start in range(0, len(ids), 400):
        for user_id, sent_at in db.query(models.EmailCampaignSend.user_id, func.max(models.EmailCampaignSend.sent_at)).filter(
                models.EmailCampaignSend.user_id.in_(ids[start:start + 400]), models.EmailCampaignSend.status == "sent",
        ).group_by(models.EmailCampaignSend.user_id):
            if sent_at is not None:
                last_email[user_id] = sent_at
    waiting = [user for user in members if not (user.id in last_email and last_email[user.id] > now - GAP)]
    stocked = _with_library(db, [user.id for user in waiting]) if waiting else set()
    due = [user for user in waiting if user.id in stocked]
    return due[:limit] if limit is not None else due


def stats(db: Session, days: int, now: datetime) -> dict:
    table = models.SiteTrafficDaily
    counts = dict(db.query(table.key, func.sum(table.count)).filter(
        table.kind == "yearfill", table.day >= (now - timedelta(days=days - 1)).date(),
    ).group_by(table.key).all())
    get = lambda key: int(counts.get(key) or 0)  # noqa: E731
    by_source = [{"source": label, **{key: get(f"{key}_{source}") for key in COUNTER_KEYS}}
                 for source, label in SOURCES.items()]
    return {"by_source": by_source, "sent": get("sent"),
            **{key: sum(row[key] for row in by_source) for key in COUNTER_KEYS}}


def status(db: Session, now: datetime | None = None, days: int = 30) -> dict:
    now = now or datetime.utcnow()
    row = campaign(db)
    sends = db.query(models.EmailCampaignSend).filter(
        models.EmailCampaignSend.campaign_key.like(f"{SEND_PREFIX}%"),
        models.EmailCampaignSend.status == "sent",
        models.EmailCampaignSend.sent_at >= now - timedelta(days=45),
    ).all()
    users = {user.id: user for user in db.query(models.User).filter(
        models.User.id.in_({send.user_id for send in sends}))} if sends else {}
    came_back = 0
    for send in sends:
        user = users.get(send.user_id)
        if user is None:
            continue
        window_end = send.sent_at + timedelta(days=CAME_BACK_WITHIN_DAYS)
        back = user.last_seen_on and send.sent_at.date() <= user.last_seen_on <= window_end.date()
        logged = user.last_login_at and send.sent_at <= user.last_login_at <= window_end
        if back or logged:
            came_back += 1
    year = send_window(now)
    upcoming = now.year if now.month < 12 or now.day <= SEND_LAST_DAY else now.year + 1
    return {
        "status": row.status,
        "started_at": row.started_at.isoformat() + "Z" if row.started_at else None,
        "window_open": year is not None,
        "window": f"December 1 to {SEND_LAST_DAY}, {year or upcoming}",
        "sent_recent": len(sends),
        "sent_all_time": int(db.query(func.count(models.EmailCampaignSend.id)).filter(
            models.EmailCampaignSend.campaign_key.like(f"{SEND_PREFIX}%"),
            models.EmailCampaignSend.status == "sent").scalar() or 0),
        "came_back": came_back,
        "came_back_window_days": CAME_BACK_WITHIN_DAYS,
        "due_now": len(due_members(db, now)),
        "waiting_on_whats_new": _whats_new_sending(db),
        "daily_limit": daily_limit(),
        "mail_configured": mail_configured(),
        "page": stats(db, days, now),
    }


# ---------------------------------------------------------------- the email

def _link(path: str) -> str:
    joiner = "&" if "?" in path.split("#")[0] else "?"
    if "#" in path:
        head, anchor = path.split("#", 1)
        return f"{app_url()}{head}{joiner}{UTM}#{anchor}"
    return f"{app_url()}{path}{joiner}{UTM}"


def _plural(count_: int, one: str, many: Optional[str] = None) -> str:
    return f"{count_} {one if count_ == 1 else (many or one + 's')}"


def _also_this_month(now: datetime) -> list[tuple[str, str]]:
    """(sentence, path) for December things that are open right now: the advent calendar and the yearbook."""
    lines: list[tuple[str, str]] = []
    try:
        from . import advent_calendar
        if advent_calendar.is_public(now.year, now):
            lines.append(("The advent calendar opens a door a day until Christmas Eve, one pick behind each.",
                          advent_calendar.BASE_PATH))
    except Exception:
        pass
    try:
        from . import yearbook
        if yearbook.state_of(now.year, now) == "open":
            lines.append((f"Friends can sign your {now.year} yearbook until {yearbook.closes_label(now.year)}.",
                          "/yearbook"))
    except Exception:
        pass
    return lines


def _row_html(index: int, item: dict, token: str) -> str:
    check = _check_in()
    question = item["question"]
    meta = item["label"] + (f" · {item['year']}" if item.get("year") else "")
    return (
        '<tr><td style="padding:12px 12px 12px 0;border-top:1px solid #e9e5f5;vertical-align:top;width:52px">'
        f'{check._cover(item.get("image"))}</td>'
        '<td style="padding:12px 0;border-top:1px solid #e9e5f5;vertical-align:top">'
        f'<div style="color:#1f1640;font-weight:700;font-size:15px">{escape(item["title"])}</div>'
        f'<div style="color:#5b5675;font-size:13px;line-height:1.5">{escape(meta)} · {escape(question)}</div>'
        f'<div>{check._pill("Pick the month", link_for(token, index), True)}</div></td></tr>')


def build_email(username: str, year: int, finished: int, undated_total: int, open_total: int,
                items: list[dict], token: Optional[str], unsubscribe_url: str,
                now: datetime) -> tuple[str, str, str]:
    """(subject, html, text) for one member."""
    since = dated_from(year)
    recap_link = _link(f"/year-in-review/{year}#story")
    if finished:
        so_far = f"So far your recap has {_plural(finished, 'finish', 'finishes')}"
        so_far += f", all from {since} on, because that's when OmniTrackr started dating what you finish." if since else "."
    else:
        so_far = (f"Right now your recap is empty, because OmniTrackr only started dating what you finish in {since}."
                  if since else "Right now your recap is empty.")
    if undated_total:
        subject = f"Your {year} recap is missing {_plural(undated_total, 'title')}"
        ask = (f"{_plural(undated_total, 'title')} in your library {'is' if undated_total == 1 else 'are'} ticked off "
               "with no date, so the recap leaves them out. Tell us roughly when you finished each one and it counts. "
               "A guess at the month is fine, and you don't need to sign in.")
    elif open_total:
        subject = f"Did you get to these in {year}?"
        ask = (f"{_plural(open_total, 'title')} you saved {'is' if open_total == 1 else 'are'} still on your list. "
               f"If you finished any of them this year, pick the month and {'it goes' if open_total == 1 else 'they go'} "
               "into your recap. You don't need to sign in.")
    else:
        subject = f"Your {year} in review is ready"
        ask = ("Tap through it for your top rated titles, your busiest month and your type for the year, "
               "then save the story image to post.")
    subject = " ".join(subject.split())[:150]
    intro = so_far
    rows = "".join(_row_html(index, item, token) for index, item in enumerate(items)) if token else ""
    more = max(0, undated_total + open_total - len(items)) if token else 0
    main_label, main_link = ("Fill in your " + str(year), link_for(token)) if token else ("Play your year", recap_link)
    also = _also_this_month(now)
    also_html = ""
    also_text: list[str] = []
    if also:
        also_html = ('<h2 style="font-size:16px;color:#1f1640;margin:26px 0 4px">Also on OmniTrackr this month</h2>'
                     + "".join(f'<p style="color:#5b5675;font-size:14px;line-height:1.55;margin:6px 0">{escape(line)} '
                               f'<a href="{escape(_link(path), quote=True)}" style="color:#6d28d9;font-weight:700">Open it</a></p>'
                               for line, path in also))
        also_text = ["Also on OmniTrackr this month:"] + [f"- {line} {_link(path)}" for line, path in also] + [""]
    html = (
        '<html><body style="margin:0;background:#f4f2fb;font-family:Arial,Helvetica,sans-serif">'
        '<div style="max-width:560px;margin:0 auto;padding:24px">'
        '<div style="background:#1a1433;border-radius:14px 14px 0 0;padding:22px 24px;color:#fff">'
        f'<div style="font-size:12px;letter-spacing:2px;color:#99f6e4;text-transform:uppercase">Year in Review {year}</div>'
        f'<div style="font-size:22px;font-weight:700;margin-top:6px">Hi {escape(username)}, your {year} is ready</div></div>'
        '<div style="background:#fff;border-radius:0 0 14px 14px;padding:8px 24px 24px">'
        f'<p style="color:#1f1640;font-size:15px;line-height:1.6">{escape(intro)}</p>'
        f'<p style="color:#1f1640;font-size:15px;line-height:1.6">{escape(ask)}</p>'
        + (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{rows}</table>' if rows else "")
        + (f'<p style="color:#5b5675;font-size:13px;margin:10px 0 0">{more:,} more {"is" if more == 1 else "are"} '
           'waiting on the full page once you sign in.</p>' if more else "")
        + f'<p style="margin:26px 0 8px"><a href="{escape(main_link, quote=True)}" '
        'style="background:#1a1433;color:#fff;padding:12px 20px;border-radius:999px;text-decoration:none;font-weight:700">'
        f'{escape(main_label)}</a></p>'
        + (f'<p style="color:#5b5675;font-size:14px;margin:12px 0 0">Then <a href="{escape(recap_link, quote=True)}" '
           'style="color:#6d28d9;font-weight:700">play your year</a> and save the story image.</p>' if token else "")
        + also_html +
        '<p style="color:#6f6a8a;font-size:12px;line-height:1.5;margin-top:24px">You’re getting this because you have '
        f'an OmniTrackr account and your {year} recap just opened. It’s the only one of these you’ll get this year. '
        'The month buttons only work for the titles above and expire in 30 days. '
        f'<a href="{escape(unsubscribe_url, quote=True)}" style="color:#6d28d9">Unsubscribe from product updates</a> '
        'with one click.</p>'
        '</div></div></body></html>'
    )
    text = [f"Hi {username},", "", intro, "", ask, ""]
    if token:
        text += [f"- {item['title']} ({item['label']}): {item['question']} {link_for(token, index)}"
                 for index, item in enumerate(items)]
        text += ["", f"Fill in your {year}: {link_for(token)}", f"Then play your year: {recap_link}", ""]
    else:
        text += [f"Play your year: {recap_link}", ""]
    text += also_text
    text += [f"You're getting this because you have an OmniTrackr account and your {year} recap just opened. "
             "It's the only one of these you'll get this year.",
             f"Unsubscribe from product updates: {unsubscribe_url}"]
    return subject, html, "\n".join(text)


def email_for(db: Session, user: models.User, now: Optional[datetime] = None,
              year: Optional[int] = None) -> Optional[tuple[str, str, str, str]]:
    """(subject, html, text, unsubscribe_url), or None when there's nothing to fill in and nothing finished."""
    from .announcements import unsubscribe_token
    now = now or _now()
    year = year or send_window(now) or now.year
    today = now.date()
    deck, undated_total = undated(db, user.id, year, limit=TOKEN_MAX_ITEMS)
    still, open_total = unfinished(db, user.id, year, limit=TOKEN_MAX_ITEMS, today=today)
    finished = finished_total(db, user.id, year)
    if not (undated_total or open_total or finished):
        return None
    items = (deck + still)[:TOKEN_MAX_ITEMS]
    token = make_token(user.id, year, items) if items else None
    unsubscribe_url = f"{app_url()}/email/updates/unsubscribe?token={unsubscribe_token(user.id)}"
    subject, html, text = build_email(user.username, year, finished, undated_total, open_total, items, token,
                                      unsubscribe_url, now)
    return subject, html, text, unsubscribe_url


# ---------------------------------------------------------------- sending

async def _send(to: str, subject: str, html: str, unsubscribe_url: str) -> None:
    from .digest import _send as send_mail
    await send_mail(to, subject, html, unsubscribe_url)


def allowance(db: Session, now: datetime) -> int:
    """How many may go out now: inside this email's own limit and the shared daily cap."""
    from .announcements import shared_cap
    since = now - timedelta(hours=24)
    sent_here = db.query(func.count(models.EmailCampaignSend.id)).filter(
        models.EmailCampaignSend.campaign_key.like(f"{SEND_PREFIX}%"),
        models.EmailCampaignSend.status != "test",
        models.EmailCampaignSend.sent_at >= since).scalar() or 0
    sent_campaign = db.query(func.count(models.EmailCampaignSend.id)).filter(
        models.EmailCampaignSend.sent_at >= since).scalar() or 0
    sent_digest = db.query(func.count(models.EmailDigestSubscription.id)).filter(
        models.EmailDigestSubscription.last_sent_at >= since).scalar() or 0
    return max(0, min(daily_limit() - sent_here, shared_cap() - sent_campaign - sent_digest, PER_RUN_LIMIT))


async def send_due(session_factory, now: datetime | None = None, sender=_send) -> dict:
    now = now or datetime.utcnow()
    out = {"sent": 0, "failed": 0, "limited": False}
    year = send_window(now)
    if year is None or (not mail_configured() and sender is _send):
        return out
    db = session_factory()
    try:
        if campaign(db).status != "sending" or _whats_new_sending(db):
            return out
        budget = allowance(db, now)
        if budget <= 0:
            out["limited"] = True
            return out
        from .email_quota import lock_email_budget
        # Every member who may get one, in order: a member whose email turns out empty (say, an import whose
        # finishes are all dated in other years) is passed over without using up the run.
        for user in due_members(db, now):
            if out["sent"] + out["failed"] >= budget:
                break
            lock_email_budget(db)
            if allowance(db, now) <= 0:
                db.rollback()
                out["limited"] = True
                break
            try:
                built = email_for(db, user, now, year)
            except Exception as error:
                print(f"Year fill-in email for user {user.id} couldn't be built: {error}")
                db.rollback()
                continue
            if built is None:
                db.rollback()
                continue
            # Claim first so an overlapping run can never send twice.
            claim = models.EmailCampaignSend(campaign_key=send_key(year), user_id=user.id, status="sent", sent_at=now)
            db.add(claim)
            try:
                db.commit()
            except Exception:
                db.rollback()
                continue
            subject, html, _text, unsubscribe_url = built
            try:
                await sender(user.email, subject, html, unsubscribe_url)
                out["sent"] += 1
                count("sent")
            except Exception as error:  # One bad address must not stop the rest.
                print(f"Year fill-in email to user {user.id} failed: {error}")
                db.rollback()
                claim.status = "failed"
                db.commit()
                out["failed"] += 1
        return out
    finally:
        db.close()


async def send_test(db: Session, user: models.User, sender=_send, now: Optional[datetime] = None) -> bool:
    """Send the email to the owner only (it doesn't count as their December email). False if there's nothing to say."""
    built = email_for(db, user, now)
    if built is None:
        return False
    subject, html, _text, unsubscribe_url = built
    await sender(user.email, "[Test] " + subject, html, unsubscribe_url)
    return True


async def year_fill_loop(app) -> None:
    """Background task started with the app; never raises."""
    from .database import SessionLocal
    await asyncio.sleep(FIRST_CHECK_DELAY_SECONDS)
    while True:
        try:
            result = await send_due(SessionLocal)
            if result["sent"] or result["failed"]:
                print(f"Year fill-in emails: {result}")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"Year fill-in email check failed: {error}")
        await asyncio.sleep(CHECK_EVERY_SECONDS)
