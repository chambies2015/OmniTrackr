"""Your week: a weekly rhythm on the member's home screen (Nov 2026).

Site stats showed the gap: of 100 members who started a library, 31 reached five titles and 6
ever came back. The home screen had plenty to look at (What's new, Next Up, picks) but nothing
that made a visit this week matter. The first-week card covers an account's first seven days;
this card takes over after that.

* Seven day tiles, Monday to Sunday in the member's own time zone. A day lights up when they
  logged anything: moved a saved place forward, finished, rated or reviewed something, added a
  title, wrote in their journal or noted an episode. Nothing new is asked of them; the card counts
  what they already do.
* A pace they pick once (something every week, three days, most days, or finish one thing). A
  week that meets it is kept, and kept weeks in a row make a run. A week can be taken off (one in
  any four) without breaking the run, and a missed week only ends the run, never the history.
* On the first days of a new week the card opens on last week: days, what they finished, the run.
* An optional Sunday nudge, by email or on their device, only when the week isn't kept yet and one
  more day would keep it. The email's buttons log progress without signing in (the check-in page,
  source "week").

Weeks are saved in ``your_week_weeks`` only after a member picks a pace. Days and finishes in a
saved week only ever grow, so deleting a title later never un-keeps a week. Counters go into
``site_traffic_daily`` under kind "yourweek" and name no member.
"""
from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, time, timedelta, timezone
from html import escape
from typing import Optional

from sqlalchemy import func, literal, select, union_all
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models

# key -> (kind, target, label, hint). "days" counts days with anything logged; "finish" counts finishes.
GOALS = {
    "once": ("days", 1, "Something every week", "Log anything on one day"),
    "three": ("days", 3, "Three days a week", "Log something on three days"),
    "most": ("days", 5, "Most days", "Log something on five days"),
    "finish": ("finish", 1, "Finish one thing a week", "A movie, a season, a book, an album"),
}
GOAL_ORDER = ("once", "three", "most", "finish")
MIN_TITLES = 3                    # smaller libraries have the launchpad instead
HISTORY_WEEKS = 8                 # the row of past weeks on the card
REST_EVERY_WEEKS = 4              # one week off in any four
RECAP_UNTIL_WEEKDAY = 2           # last week's recap shows Monday to Wednesday
TOUCHED_LIMIT = 5
REMIND_WEEKDAY = 6                # Sunday
REMIND_HOUR = 18                  # local time: the evening, with the night still to go
LATE = timedelta(hours=3)         # a nudge that can't go out within this long is skipped, never sent late
MARK_EVERY = timedelta(minutes=30)
SEND_PREFIX = "your-week-"
CHECK_EVERY_SECONDS = 900
FIRST_CHECK_DELAY_SECONDS = 480
PER_RUN_LIMIT = 25
EMAIL_TITLES = 3
UTM = "utm_source=email&utm_campaign=your-week"
PUSH_KIND = "your_week"

COUNTERS = {
    "seen": "Saw the Your week card",
    "set_goal": "Picked a weekly pace",
    "changed_goal": "Changed their pace",
    "stopped": "Stopped keeping count",
    "kept": "Weeks kept",
    "first_kept": "Members who kept their first week",
    "recap_seen": "Opened last week's recap",
    "rest": "Took a week off",
    "remind_email": "Turned on the Sunday email",
    "remind_push": "Turned on the Sunday notification",
    "remind_off": "Turned a Sunday nudge off",
    "sent": "Sunday emails sent",
    "push_sent": "Sunday notifications sent",
    "skipped": "Sunday nudges not needed (week already kept, or out of reach)",
    "dropped": "Sunday nudges dropped (late, or email no longer possible)",
    "back_after_nudge": "Opened the home screen after a Sunday nudge",
    "kept_after_nudge": "Kept their week after a Sunday nudge",
    "logged_from_email": "Logged progress from the email's buttons",
    "hidden": "Hid the card",
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def count(key: str) -> bool:
    """Add 1 to a "yourweek" counter for today. Never raises."""
    if key not in COUNTERS:
        return False
    try:
        from .site_traffic import RECORDER
        if not RECORDER.enabled:
            return False
        day = datetime.now(timezone.utc).date()
        with RECORDER._lock:
            RECORDER._pending[(day, "yourweek", key)] += 1
            RECORDER._events += 1
        return True
    except Exception:
        return False


def daily_limit() -> int:
    try:
        return max(0, int(os.getenv("YOUR_WEEK_DAILY_LIMIT", "40")))
    except ValueError:
        return 40


def emails_enabled() -> bool:
    if os.getenv("YOUR_WEEK_EMAILS", "").strip().lower() in ("off", "0", "false", "no"):
        return False
    return os.getenv("TESTING", "").lower() != "true"


# ---------------------------------------------------------------- weeks and time zones

def clamp_tz(value) -> int:
    """Minutes east of UTC from the browser, kept to real time zones."""
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return 0
    return max(-14 * 60, min(14 * 60, minutes))


def local_now(now: datetime, tz: int) -> datetime:
    return now + timedelta(minutes=tz)


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_bounds(week_start: date, tz: int) -> tuple[datetime, datetime]:
    """The UTC times a member's local Monday-to-Sunday week starts and ends."""
    start = datetime.combine(week_start, time()) - timedelta(minutes=tz)
    return start, start + timedelta(days=7)


def next_remind_at(now: datetime, tz: int) -> datetime:
    """The next Sunday at 6 pm in the member's time zone, as UTC, strictly after ``now``."""
    local = local_now(now, tz)
    day = local.date() + timedelta(days=(REMIND_WEEKDAY - local.weekday()) % 7)
    when = datetime.combine(day, time(REMIND_HOUR)) - timedelta(minutes=tz)
    if when <= now:
        when += timedelta(days=7)
    return when


def _bits(mask: int) -> int:
    return bin(int(mask or 0) & 0x7F).count("1")


def is_kept(goal: Optional[str], mask: int, finishes: int) -> bool:
    if goal not in GOALS:
        return False
    kind, target, *_ = GOALS[goal]
    return (_bits(mask) if kind == "days" else int(finishes or 0)) >= target


def still_needed(goal: Optional[str], mask: int, finishes: int) -> int:
    if goal not in GOALS:
        return 0
    kind, target, *_ = GOALS[goal]
    return max(0, target - (_bits(mask) if kind == "days" else int(finishes or 0)))


# ---------------------------------------------------------------- what the member logged

def _library() -> dict:
    from .check_in import CATEGORIES
    return {category: details[0] for category, details in CATEGORIES.items()}


def _stamps(db: Session, user_id: int, start: datetime, end: datetime) -> list[datetime]:
    """Every time the member logged something between ``start`` and ``end`` (UTC). Reads only.

    One round trip: the sixteen places a day can come from are read as one UNION ALL
    (it was sixteen queries on every home screen load).
    """
    def between(model, column, *extra):
        return select(column.label("at")).where(model.user_id == user_id, column >= start, column < end, *extra)

    entry, feed, mark = models.ActivityEntry, models.FriendFeedEvent, models.ProgressMark
    point, note = models.ProgressCheckpoint, models.EpisodeNote
    parts = [
        between(entry, entry.occurred_at),
        between(feed, feed.created_at),
        between(mark, mark.at),
        between(point, point.updated_at, point.unit.isnot(None)),
        between(note, note.created_at),
        between(note, note.updated_at),
    ]
    parts += [between(model, model.added_at) for model in _library().values()]
    return [value for (value,) in db.execute(union_all(*parts)) if value is not None]


def _finished(db: Session, user_id: int, start: datetime, end: datetime) -> list[models.ActivityEntry]:
    entry = models.ActivityEntry
    rows = db.query(entry).filter(entry.user_id == user_id, entry.action == "completed",
                                  entry.occurred_at >= start, entry.occurred_at < end) \
        .order_by(entry.occurred_at.desc(), entry.id.desc()).all()
    seen, unique = set(), []
    for row in rows:
        key = (row.category, row.item_id) if row.item_id else (row.category, (row.title or "").strip().lower())
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def measure(db: Session, user_id: int, first_week: date, last_week: date, tz: int) -> dict[date, tuple[int, int]]:
    """{week_start: (day_mask, finishes)} for every week from ``first_week`` to ``last_week``, in one pass."""
    start, _ = week_bounds(first_week, tz)
    _, end = week_bounds(last_week, tz)
    weeks: dict[date, list[int]] = {}
    week = first_week
    while week <= last_week:
        weeks[week] = [0, 0]
        week += timedelta(days=7)
    for stamp in _stamps(db, user_id, start, end):
        day = local_now(stamp, tz).date()
        found = weeks.get(monday_of(day))
        if found is not None:
            found[0] |= 1 << day.weekday()
    for row in _finished(db, user_id, start, end):
        found = weeks.get(monday_of(local_now(row.occurred_at, tz).date()))
        if found is not None:
            found[1] += 1
    return {week: (mask, finishes) for week, (mask, finishes) in weeks.items()}


def stage_mark(db: Session, user_id: int, now: Optional[datetime] = None) -> bool:
    """Note that a saved place moved forward, in the caller's transaction. At most one row a half hour."""
    now = now or _now()
    mark = models.ProgressMark
    with db.no_autoflush:
        recent = db.query(mark.id).filter(mark.user_id == user_id, mark.at > now - MARK_EVERY).first()
    if recent is not None:
        return False
    db.add(mark(user_id=user_id, at=now))
    return True


def note_logged(db: Session, user: models.User, now: Optional[datetime] = None) -> None:
    """Progress logged from the Sunday email's buttons ("Made some progress")."""
    stage_mark(db, user.id, now)
    db.commit()
    count("logged_from_email")


def _image(category: str, row) -> Optional[str]:
    from .check_in import _image as image
    return image(category, row)


def _titles(db: Session, user_id: int, refs: list[tuple[str, int, str]], limit: int) -> list[dict]:
    """[{title, category, label, image}] for (category, item_id, fallback title) refs, in order, deduplicated."""
    from .check_in import CATEGORIES
    found, seen = [], set()
    library = _library()
    # The library rows come in one query per format, not one per title.
    wanted: dict[str, set[int]] = {}
    unique: list[tuple[str, int, str]] = []
    for category, item_id, fallback in refs:
        if category not in library or (category, item_id or fallback) in seen:
            continue
        seen.add((category, item_id or fallback))
        unique.append((category, item_id, fallback))
    unique = unique[:limit * 4]  # enough to fill the list when a few have no title left
    for category, item_id, _fallback in unique:
        if item_id:
            wanted.setdefault(category, set()).add(item_id)
    rows: dict[tuple[str, int], object] = {}
    for category, ids in wanted.items():
        model = library[category]
        for row in db.query(model).filter(model.user_id == user_id, model.id.in_(sorted(ids))):
            rows[(category, row.id)] = row
    for category, item_id, fallback in unique:
        row = rows.get((category, item_id)) if item_id else None
        title = " ".join(((row.title if row is not None else None) or fallback or "").split())[:200]
        if not title:
            continue
        found.append({"title": title, "category": category, "label": CATEGORIES[category][2],
                      "image": _image(category, row) if row is not None else None})
        if len(found) >= limit:
            break
    return found


def touched(db: Session, user_id: int, start: datetime, end: datetime, limit: int = TOUCHED_LIMIT) -> list[dict]:
    """Titles the member did something with in a week, newest first: finished, moved forward, added."""
    refs: list[tuple[datetime, str, int, str]] = []
    entry = models.ActivityEntry
    for row in db.query(entry.occurred_at, entry.category, entry.item_id, entry.title).filter(
            entry.user_id == user_id, entry.occurred_at >= start, entry.occurred_at < end).limit(40):
        refs.append((row[0], row[1], row[2] or 0, row[3] or ""))
    point = models.ProgressCheckpoint
    for row in db.query(point.updated_at, point.category, point.item_id).filter(
            point.user_id == user_id, point.unit.isnot(None), point.updated_at >= start, point.updated_at < end).limit(40):
        refs.append((row[0], row[1], row[2], ""))
    # The newest adds across all nine libraries in one query (it was one per library).
    adds = union_all(*[
        select(model.added_at.label("at"), literal(category).label("category"), model.id.label("item_id"),
               model.title.label("title"))
        .where(model.user_id == user_id, model.added_at >= start, model.added_at < end, model.title.isnot(None))
        for category, model in _library().items()
    ]).subquery()
    for row in db.execute(select(adds).order_by(adds.c.at.desc()).limit(limit * 2)):
        refs.append((row[0], row[1], row[2], row[3] or ""))
    refs.sort(key=lambda ref: ref[0], reverse=True)
    return _titles(db, user_id, [(category, item_id, title) for _at, category, item_id, title in refs], limit)


# ---------------------------------------------------------------- saved weeks

def get_plan(db: Session, user_id: int) -> Optional[models.YourWeekPlan]:
    return db.query(models.YourWeekPlan).filter(models.YourWeekPlan.user_id == user_id).first()


def _plan(db: Session, user_id: int) -> models.YourWeekPlan:
    plan = get_plan(db, user_id)
    if plan is None:
        plan = models.YourWeekPlan(user_id=user_id)
        db.add(plan)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()  # another tab made it a moment ago
            plan = get_plan(db, user_id)
    return plan


def _weeks(db: Session, user_id: int, since: Optional[date] = None) -> dict[date, models.YourWeekWeek]:
    query = db.query(models.YourWeekWeek).filter(models.YourWeekWeek.user_id == user_id)
    if since is not None:
        query = query.filter(models.YourWeekWeek.week_start >= since)
    return {row.week_start: row for row in query.all()}


def _apply(row: models.YourWeekWeek, mask: int, finishes: int, now: datetime) -> bool:
    """Grow a saved week with what was measured. True when this made it kept.

    Only a week that actually grew is written: the card is built on every home screen
    load, and rewriting an unchanged week's time each time was a write (and a commit,
    and a reload of every saved week after it) on each visit.
    """
    grown_mask = int(row.day_mask or 0) | int(mask or 0)
    grown_finishes = max(int(row.finishes or 0), int(finishes or 0))
    if grown_mask != (row.day_mask or 0) or grown_finishes != (row.finishes or 0) or row.updated_at is None:
        row.day_mask = grown_mask
        row.finishes = grown_finishes
        row.updated_at = now
    if row.kept_at is None and is_kept(row.goal, row.day_mask, row.finishes):
        row.kept_at = now
        return True
    return False


def _note_kept(rows: list[models.YourWeekWeek], had_kept: bool) -> None:
    for row in rows:
        count("kept")
        if row.nudged_at is not None:
            count("kept_after_nudge")
    if rows and not had_kept:
        count("first_kept")


def sync(db: Session, user: models.User, plan: models.YourWeekPlan, this_monday: date, now: datetime,
         measured: Optional[dict] = None) -> dict[date, models.YourWeekWeek]:
    """Save this week and any ended week since the pace was picked that isn't final yet. Returns the saved weeks."""
    first = this_monday - timedelta(days=7 * HISTORY_WEEKS)
    rows = _weeks(db, user.id, since=min(first, plan.started_week or first))
    if plan.goal not in GOALS or plan.started_week is None:
        return rows
    begin = max(plan.started_week, first)
    wanted, week = [], begin
    while week <= this_monday:
        row = rows.get(week)
        if row is None or not row.final:
            wanted.append(week)
        week += timedelta(days=7)
    if not wanted:
        return rows
    if measured is None or any(week not in measured for week in wanted):
        measured = measure(db, user.id, min(wanted), this_monday, plan.tz_minutes or 0)
    had_kept = any(row.kept_at is not None for row in rows.values())
    kept_now = []
    for week in wanted:
        mask, finishes = measured.get(week, (0, 0))
        row = rows.get(week)
        if row is None:
            row = models.YourWeekWeek(user_id=user.id, week_start=week, goal=plan.goal, day_mask=0, finishes=0)
            db.add(row)
            rows[week] = row
        elif week == this_monday and row.goal != plan.goal:
            row.goal = plan.goal  # the week in progress follows the latest pace
        if _apply(row, mask, finishes, now):
            kept_now.append(row)
        if week < this_monday and not row.final:
            row.final = True
    if not db.new and not db.dirty:
        return rows  # nothing grew since the last look: no write, no commit
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # two tabs saved the same week at once; the next look counts it
        return _weeks(db, user.id, since=min(first, plan.started_week))
    _note_kept(kept_now, had_kept)
    return rows


def run_lengths(rows: dict[date, models.YourWeekWeek], this_monday: date) -> tuple[int, int, int]:
    """(run up to last week, run including this week, best run). A week off neither adds nor breaks."""
    if not rows:
        return 0, 0, 0
    week = min(rows)
    current = best = 0
    while week < this_monday:
        row = rows.get(week)
        if row is not None and row.kept_at is not None:
            current += 1
        elif row is None or row.rest_at is None:
            current = 0
        best = max(best, current)
        week += timedelta(days=7)
    before = current
    this = rows.get(this_monday)
    if this is not None and this.kept_at is not None:
        current += 1
    return before, current, max(best, current)


def can_rest(rows: dict[date, models.YourWeekWeek], this_monday: date) -> bool:
    for back in range(1, REST_EVERY_WEEKS):
        row = rows.get(this_monday - timedelta(days=7 * back))
        if row is not None and row.rest_at is not None and row.kept_at is None:
            return False
    return True


# ---------------------------------------------------------------- the card

def _library_size(db: Session, user_id: int) -> int:
    from .stay_posted import _library_size as size
    return size(db, user_id)


def _has_push(db: Session, user_id: int) -> bool:
    return db.query(models.PushSubscription.id).filter(models.PushSubscription.user_id == user_id).first() is not None


def email_offer(user: models.User, db: Optional[Session] = None) -> bool:
    """The Sunday email can be offered: a confirmed address, mail set up, and (given ``db``) product emails on.

    The email's footer link is the product-updates unsubscribe. For a member who had already
    unsubscribed, that link only says "you're already unsubscribed", so a weekly email sent to
    them could never be stopped from the email itself. Those members get the device nudge only.
    """
    from . import digest
    if not (user.is_verified and digest.mail_configured()):
        return False
    return db is None or not _opted_out(db, user.id)


def _opted_out(db: Session, user_id: int) -> bool:
    return db.query(models.EmailOptOut.id).filter(models.EmailOptOut.user_id == user_id).first() is not None


def _goal_payload(key: Optional[str]) -> Optional[dict]:
    if key not in GOALS:
        return None
    kind, target, label, hint = GOALS[key]
    return {"key": key, "kind": kind, "target": target, "label": label, "hint": hint}


def _week_label(week_start: date) -> str:
    end = week_start + timedelta(days=6)
    if week_start.month == end.month:
        return f"{week_start:%b} {week_start.day} to {end.day}"
    return f"{week_start:%b} {week_start.day} to {end:%b} {end.day}"


def _recap(db: Session, user: models.User, plan: models.YourWeekPlan, rows: dict, this_monday: date,
           today: date, run_before: int) -> Optional[dict]:
    last = rows.get(this_monday - timedelta(days=7))
    if (last is None or not last.final or last.recap_seen_at is not None or last.goal not in GOALS
            or today.weekday() > RECAP_UNTIL_WEEKDAY):
        return None
    start, end = week_bounds(last.week_start, plan.tz_minutes or 0)
    finished = _finished(db, user.id, start, end)
    titles = _titles(db, user.id, [(row.category, row.item_id or 0, row.title or "") for row in finished], 4)
    return {
        "week_start": last.week_start.isoformat(), "label": _week_label(last.week_start),
        "kept": last.kept_at is not None, "rest": last.rest_at is not None and last.kept_at is None,
        "days": _bits(last.day_mask), "finishes": int(last.finishes or 0), "goal": _goal_payload(last.goal),
        "finished": titles, "more": max(0, len(finished) - len(titles)), "run": run_before,
    }


def _note_back(db: Session, row: Optional[models.YourWeekWeek], now: datetime) -> None:
    """The first home screen visit after this week's nudge."""
    if row is None or row.nudged_at is None or row.back_at is not None or now <= row.nudged_at:
        return
    row.back_at = now
    db.commit()
    count("back_after_nudge")


def build(db: Session, user: models.User, tz: int, now: Optional[datetime] = None, show: bool = False) -> Optional[dict]:
    """The card for this member right now, or None. Looking doesn't count as seen."""
    from . import week_one
    now = now or _now()
    tz = clamp_tz(tz)
    today = local_now(now, tz).date()
    this_monday = monday_of(today)
    plan = get_plan(db, user.id)
    if plan is not None and plan.hidden_at is not None and not show:
        return None
    if not show and week_one.active(db, user, now):
        return None  # the first-week card has the home screen for an account's first seven days
    goal = plan.goal if plan is not None and plan.goal in GOALS else None
    if goal is None and _library_size(db, user.id) < MIN_TITLES:
        return None
    if plan is not None and (plan.tz_minutes or 0) != tz:
        plan.tz_minutes = tz
        if plan.remind_email or plan.remind_push:
            plan.next_remind_at = next_remind_at(now, tz)
        db.commit()
    first = this_monday - timedelta(days=7 * HISTORY_WEEKS)
    measured = measure(db, user.id, first, this_monday, tz)
    rows = sync(db, user, plan, this_monday, now, measured) if goal else (
        _weeks(db, user.id, since=first) if plan is not None else {})
    this_row = rows.get(this_monday) if goal else None
    mask, finishes = measured[this_monday]
    if this_row is not None:
        mask, finishes = this_row.day_mask, this_row.finishes
        _note_back(db, this_row, now)
    run_before, run, best = run_lengths(rows, this_monday) if goal else (0, 0, 0)
    days = []
    for offset in range(7):
        day = this_monday + timedelta(days=offset)
        days.append({"date": day.isoformat(), "logged": bool(mask & (1 << offset)),
                     "today": day == today, "future": day > today})
    history = []
    for back in range(HISTORY_WEEKS, 0, -1):
        week = this_monday - timedelta(days=7 * back)
        row = rows.get(week)
        logged = _bits(measured.get(week, (0, 0))[0])
        if row is not None and row.kept_at is not None:
            state = "kept"
        elif row is not None and row.rest_at is not None:
            state = "rest"
        elif row is not None:
            state = "missed"
        else:
            state = "active" if logged else "quiet"
        history.append({"week_start": week.isoformat(), "state": state, "days": max(logged, _bits(row.day_mask) if row else 0)})
    kept = this_row is not None and this_row.kept_at is not None
    rest = this_row is not None and this_row.rest_at is not None and not kept
    start, end = week_bounds(this_monday, tz)
    status = "setup" if goal is None else ("kept" if kept else "rest" if rest else "open")
    days_left = 7 - today.weekday()
    offer_email = email_offer(user, db)
    kept_total = 0
    if plan is not None:
        kept_total = db.query(func.count(models.YourWeekWeek.id)).filter(
            models.YourWeekWeek.user_id == user.id, models.YourWeekWeek.kept_at.isnot(None)).scalar() or 0
    return {
        "today": today.isoformat(),
        "week_start": this_monday.isoformat(),
        "label": _week_label(this_monday),
        "status": status,
        "goal": _goal_payload(goal),
        "goals": [_goal_payload(key) for key in GOAL_ORDER],
        "days": days,
        "logged_days": _bits(mask),
        "finishes": int(finishes or 0),
        "needed": still_needed(goal, mask, finishes) if goal and not kept else 0,
        "days_left": days_left,
        "run": run, "run_before": run_before, "best": best, "kept_total": int(kept_total),
        "history": history,
        "active_weeks": sum(1 for week in history if week["state"] in ("kept", "active") or week["days"]),
        "touched": touched(db, user.id, start, end),
        "recap": _recap(db, user, plan, rows, this_monday, today, run_before) if goal else None,
        # A week off only makes sense with a run to protect.
        "can_rest": bool(goal) and not kept and not rest and run_before >= 1 and can_rest(rows, this_monday),
        "remind": {
            # After an unsubscribe from the email itself the switch reads off straight away
            # (the next Sunday check turns the saved one off too).
            "email": bool(plan and plan.remind_email and offer_email), "push": bool(plan and plan.remind_push),
            "offer_email": offer_email, "has_push": _has_push(db, user.id), "hour": REMIND_HOUR,
        },
        "hidden": bool(plan and plan.hidden_at),
    }


# ---------------------------------------------------------------- buttons

def mark_seen(db: Session, user: models.User, tz: int, now: Optional[datetime] = None) -> bool:
    now = now or _now()
    today = local_now(now, clamp_tz(tz)).date()
    plan = _plan(db, user.id)
    changed = False
    if plan.first_seen_on is None:
        plan.first_seen_on = today
        count("seen")
        changed = True
    if plan.last_seen_on != today:
        plan.last_seen_on = today
        changed = True
    if changed:
        db.commit()
    return True


def set_goal(db: Session, user: models.User, goal: Optional[str], tz: int, now: Optional[datetime] = None) -> None:
    """Pick (or change) the weekly pace. None stops keeping count; saved weeks stay for the badge."""
    now = now or _now()
    tz = clamp_tz(tz)
    if goal is not None and goal not in GOALS:
        raise ValueError("Pick one of the paces on the card.")
    plan = _plan(db, user.id)
    plan.tz_minutes = tz
    this_monday = monday_of(local_now(now, tz).date())
    if goal is None:
        if plan.goal is None:
            return
        plan.goal = None
        plan.remind_email = plan.remind_push = False
        plan.next_remind_at = None
        db.commit()
        count("stopped")
        return
    first_time = plan.goal_set_at is None
    plan.goal = goal
    plan.goal_set_at = now
    plan.hidden_at = None
    if plan.started_week is None or plan.started_week > this_monday:
        plan.started_week = this_monday
    db.commit()
    count("set_goal" if first_time else "changed_goal")


def set_reminder(db: Session, user: models.User, email: Optional[bool], push: Optional[bool], tz: int,
                 now: Optional[datetime] = None) -> None:
    now = now or _now()
    tz = clamp_tz(tz)
    plan = _plan(db, user.id)
    if plan.goal not in GOALS:
        raise ValueError("Pick a pace first, then the nudge has something to check.")
    plan.tz_minutes = tz
    if email is True and not plan.remind_email:
        if not email_offer(user):
            raise ValueError("Confirm your email address first, then try again.")
        if _opted_out(db, user.id):
            raise ValueError("You turned off OmniTrackr emails. Turn product emails back on in Settings, "
                             "or use the nudge on this device instead.")
        plan.remind_email = True
        plan.remind_set_at = now
        count("remind_email")
    elif email is False and plan.remind_email:
        plan.remind_email = False
        count("remind_off")
    if push is True and not plan.remind_push:
        if not _has_push(db, user.id):
            raise ValueError("Turn on notifications for this device first.")
        plan.remind_push = True
        count("remind_push")
    elif push is False and plan.remind_push:
        plan.remind_push = False
        count("remind_off")
    plan.next_remind_at = next_remind_at(now, tz) if (plan.remind_email or plan.remind_push) else None
    db.commit()


def take_rest(db: Session, user: models.User, tz: int, undo: bool = False, now: Optional[datetime] = None) -> None:
    now = now or _now()
    tz = clamp_tz(tz)
    plan = get_plan(db, user.id)
    if plan is None or plan.goal not in GOALS:
        raise ValueError("Pick a pace first.")
    this_monday = monday_of(local_now(now, tz).date())
    rows = sync(db, user, plan, this_monday, now)
    row = rows.get(this_monday)
    if row is None:
        raise ValueError("This week isn't on the card yet. Reload and try again.")
    if undo:
        if row.rest_at is not None:
            row.rest_at = None
            db.commit()
        return
    if row.kept_at is not None:
        raise ValueError("This week is already kept.")
    if row.rest_at is None:
        if not can_rest(rows, this_monday):
            raise ValueError("You took a week off recently. One week off in any four keeps a run honest.")
        row.rest_at = now
        db.commit()
        count("rest")


def recap_seen(db: Session, user: models.User, tz: int, now: Optional[datetime] = None) -> None:
    now = now or _now()
    last = monday_of(local_now(now, clamp_tz(tz)).date()) - timedelta(days=7)
    row = db.query(models.YourWeekWeek).filter(models.YourWeekWeek.user_id == user.id,
                                               models.YourWeekWeek.week_start == last).first()
    if row is not None and row.recap_seen_at is None:
        row.recap_seen_at = now
        db.commit()
        count("recap_seen")


def hide(db: Session, user: models.User, now: Optional[datetime] = None) -> None:
    plan = _plan(db, user.id)
    if plan.hidden_at is None:
        plan.hidden_at = now or _now()
        db.commit()
        count("hidden")


def unhide(db: Session, user: models.User) -> None:
    plan = get_plan(db, user.id)
    if plan is not None and plan.hidden_at is not None:
        plan.hidden_at = None
        db.commit()


# ---------------------------------------------------------------- the Sunday nudge

def _link(path: str) -> str:
    from .digest import app_url
    joiner = "&" if "?" in path else "?"
    return f"{app_url()}{path}{joiner}{UTM}"


def in_progress(db: Session, user_id: int, limit: int = EMAIL_TITLES) -> list[dict]:
    """Titles worth a button in the email: ones with a saved place first, then started Next Up, then newest unfinished."""
    from .check_in import CATEGORIES, _card, candidates
    found: list[dict] = []
    seen = set()

    def offer(category: str, row) -> None:
        if row is None or (category, row.id) in seen or len(found) >= limit or not (row.title or "").strip():
            return
        model, done_field, *_ = CATEGORIES[category]
        if getattr(row, done_field):
            return
        seen.add((category, row.id))
        found.append(_card(category, row))

    point = models.ProgressCheckpoint
    for category, item_id in db.query(point.category, point.item_id).filter(
            point.user_id == user_id, point.position.isnot(None)).order_by(point.updated_at.desc()).limit(12):
        if category in CATEGORIES:
            model = CATEGORIES[category][0]
            offer(category, db.query(model).filter(model.id == item_id, model.user_id == user_id).first())
    queue = models.NextUpItem
    for entry in db.query(queue).filter(queue.user_id == user_id, queue.started_at.isnot(None)) \
            .order_by(queue.started_at.desc()).limit(6):
        category = getattr(entry, "category", None)
        item_id = getattr(entry, "item_id", None)
        if category in CATEGORIES and item_id:
            model = CATEGORIES[category][0]
            offer(category, db.query(model).filter(model.id == item_id, model.user_id == user_id).first())
    if len(found) < limit:
        for card in candidates(db, user_id, limit=limit, unfinished_only=True):
            if (card["category"], card["id"]) not in seen and len(found) < limit:
                seen.add((card["category"], card["id"]))
                found.append({key: value for key, value in card.items() if key != "added_at"})
    for card in found:
        card.pop("added_at", None)
    return found


def _strip_html(days: list[bool], today_index: int) -> str:
    cells = []
    for index, letter in enumerate("MTWTFSS"):
        logged = days[index]
        background = "#7c3aed" if logged else ("#ffffff" if index > today_index else "#ece8f8")
        border = "2px solid #7c3aed" if index == today_index and not logged else "2px solid transparent"
        color = "#ffffff" if logged else "#5b5675"
        mark = "✓" if logged else letter
        cells.append(f'<td style="padding:0 3px"><div style="width:34px;height:34px;line-height:34px;border-radius:10px;'
                     f'text-align:center;font-weight:700;font-size:14px;background:{background};color:{color};border:{border}">'
                     f'{mark}</div></td>')
    return f'<table role="presentation" cellspacing="0" cellpadding="0" style="margin:6px 0 4px"><tr>{"".join(cells)}</tr></table>'


def nudge_copy(goal: str, mask: int, finishes: int, run: int) -> tuple[str, str]:
    """(subject, the sentence under the day tiles)."""
    kind, target, *_ = GOALS[goal]
    keeps = f"keeps your run of {run} weeks going" if run >= 2 else "keeps your week"
    if kind == "finish":
        return ("Anything to finish tonight?",
                f"Nothing finished yet this week. Finish one thing today and it {keeps}.")
    logged = _bits(mask)
    if target == 1:
        return ("One thing logged today keeps your week",
                f"Nothing logged yet this week. One episode, chapter or rating today {keeps}.")
    return (f"One more day keeps your week ({logged} of {target})",
            f"You logged something on {logged} of {target} days this week. One more today {keeps}.")


def build_email(username: str, goal: str, mask: int, finishes: int, run: int, titles: list[dict], token: Optional[str],
                unsubscribe_url: str) -> tuple[str, str, str]:
    from .check_in import link_for
    subject, line = nudge_copy(goal, mask, finishes, run)
    home = _link("/#your-week")
    rows = []
    for index, item in enumerate(titles):
        image = item.get("image")
        cover = (f'<img src="{escape(image, quote=True)}" width="44" height="66" alt="" '
                 'style="display:block;width:44px;height:66px;object-fit:cover;border-radius:6px;background:#e9e5f5">'
                 if image else '<div style="width:44px;height:66px;border-radius:6px;background:#e9e5f5"></div>')
        button = ""
        if token:
            button = (f'<a href="{escape(link_for(token, index), quote=True)}" style="display:inline-block;margin-top:6px;'
                      'border:1px solid #7c3aed;color:#6d28d9;padding:6px 12px;border-radius:999px;text-decoration:none;'
                      'font-size:13px;font-weight:700">Log it</a>')
        rows.append(
            '<tr><td style="padding:10px 12px 10px 0;border-top:1px solid #e9e5f5;vertical-align:top;width:44px">'
            f'{cover}</td><td style="padding:10px 0;border-top:1px solid #e9e5f5;vertical-align:top">'
            f'<div style="color:#1f1640;font-weight:700;font-size:15px">{escape(item["title"])}</div>'
            f'<div style="color:#5b5675;font-size:13px;line-height:1.5">{escape(item.get("label") or "")}</div>{button}</td></tr>')
    days = [bool(mask & (1 << index)) for index in range(7)]
    listing = ""
    if rows:
        listing = ('<p style="color:#1f1640;font-size:15px;line-height:1.6;margin:18px 0 4px">On the go in your library. '
                   'Tap one to log it, no sign-in needed:</p>'
                   f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{"".join(rows)}</table>')
    html = (
        '<html><body style="margin:0;background:#f4f2fb;font-family:Arial,Helvetica,sans-serif">'
        '<div style="max-width:560px;margin:0 auto;padding:24px">'
        '<div style="background:#1a1433;border-radius:14px 14px 0 0;padding:22px 24px;color:#fff">'
        '<div style="font-size:12px;letter-spacing:2px;color:#99f6e4;text-transform:uppercase">Your week</div>'
        f'<div style="font-size:22px;font-weight:700;margin-top:6px">It’s Sunday, {escape(username)}</div></div>'
        '<div style="background:#fff;border-radius:0 0 14px 14px;padding:14px 24px 24px">'
        f'{_strip_html(days, 6)}'
        f'<p style="color:#1f1640;font-size:15px;line-height:1.6">{escape(line)}</p>'
        f'{listing}'
        f'<p style="margin:24px 0 8px"><a href="{escape(home, quote=True)}" '
        'style="background:#7c3aed;color:#fff;padding:12px 20px;border-radius:999px;text-decoration:none;font-weight:700">'
        'Open my week</a></p>'
        '<p style="color:#6f6a8a;font-size:12px;line-height:1.5;margin-top:24px">You turned on this Sunday nudge on your '
        'OmniTrackr home screen. It only comes when your week isn’t kept yet, and you can turn it off on the card. '
        f'<a href="{escape(unsubscribe_url, quote=True)}" style="color:#6d28d9">Unsubscribe from product updates</a>.</p>'
        '</div></div></body></html>'
    )
    text_lines = [f"Hi {username},", "", line, ""]
    if titles:
        text_lines.append("On the go in your library:")
        for index, item in enumerate(titles):
            text_lines.append(f"- {item['title']}" + (f": {link_for(token, index)}" if token else ""))
        text_lines.append("")
    text_lines += [f"Open my week: {home}", "",
                   "You turned on this Sunday nudge on your OmniTrackr home screen. It only comes when your week "
                   "isn't kept yet, and you can turn it off on the card.",
                   f"Unsubscribe from product updates: {unsubscribe_url}"]
    return " ".join(subject.split())[:150], html, "\n".join(text_lines)


def allowance(db: Session, now: datetime) -> int:
    """How many emails may go out now: inside this email's own daily limit and the shared daily cap."""
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


def due(db: Session, now: datetime) -> list[models.YourWeekPlan]:
    plan = models.YourWeekPlan
    return db.query(plan).filter(plan.next_remind_at.isnot(None), plan.next_remind_at <= now) \
        .order_by(plan.next_remind_at).limit(200).all()


def _opted_out_since(db: Session, plan: models.YourWeekPlan) -> bool:
    """Unsubscribed from product updates: the Sunday email stops (its footer link is that unsubscribe).

    Unlike the one-off reminders (first week, backlog draw), this email comes every week, so an
    opt-out from any time stops it. Counting only opt-outs made after the email was turned on
    left the footer link powerless for anyone who had unsubscribed before.
    """
    return _opted_out(db, plan.user_id)


def push_message(goal: str, mask: int, finishes: int, run: int) -> str:
    kind, target, *_ = GOALS[goal]
    keeps = f"keeps your {run}-week run going" if run >= 2 else "keeps your week"
    if kind == "finish":
        return f"Nothing finished yet this week. Finish one thing tonight and it {keeps}."
    if target == 1:
        return f"Nothing logged yet this week. One episode or chapter tonight {keeps}."
    return f"{_bits(mask)} of {target} days so far. One more tonight {keeps}."


async def _send(to: str, subject: str, html: str, unsubscribe_url: str) -> None:
    from .digest import _send as send_mail
    await send_mail(to, subject, html, unsubscribe_url)


def _push(db: Session, user_id: int, message: str, now: datetime) -> int:
    from . import web_push
    link = "/?utm_source=push&utm_campaign=your-week#your-week"
    return int(web_push.deliver(db, [(user_id, PUSH_KIND, message, link)], now=now).get("sent") or 0)


async def send_due(session_factory, now: Optional[datetime] = None, sender=_send, pusher=_push) -> dict:
    """Send the Sunday nudges that are due. Each plan is moved on to next Sunday whatever happens."""
    from .digest import mail_configured
    now = now or _now()
    result = {"sent": 0, "pushed": 0, "skipped": 0, "dropped": 0, "failed": 0, "limited": False}
    mail_ok = mail_configured() or sender is not _send
    db = session_factory()
    try:
        from .email_quota import lock_email_budget
        for plan in due(db, now):
            if result["sent"] + result["failed"] >= PER_RUN_LIMIT:
                # allowance() counts this run's own sends, so the per-run limit is kept here;
                # the rest are still due and go out on the next check, 15 minutes on.
                result["limited"] = True
                break
            user = db.get(models.User, plan.user_id)
            tz = plan.tz_minutes or 0
            scheduled = plan.next_remind_at
            plan.next_remind_at = next_remind_at(max(now, scheduled + timedelta(minutes=1)), tz)
            if user is None or not user.is_active or plan.goal not in GOALS or now - scheduled > LATE:
                db.commit()
                count("dropped")
                result["dropped"] += 1
                continue
            this_monday = monday_of(local_now(scheduled, tz).date())
            rows = sync(db, user, plan, this_monday, now)
            row = rows.get(this_monday)
            if row is None:
                db.commit()
                continue
            needed = still_needed(row.goal, row.day_mask, row.finishes)
            if row.kept_at is not None or row.rest_at is not None or needed != 1 or row.nudged_at is not None:
                db.commit()
                count("skipped")
                result["skipped"] += 1
                continue
            # Claimed before anything goes out, so an overlapping run can never send a twin.
            claimed = db.query(models.YourWeekWeek).filter(
                models.YourWeekWeek.id == row.id, models.YourWeekWeek.nudged_at.is_(None),
            ).update({"nudged_at": now}, synchronize_session=False)
            db.commit()
            if not claimed:
                continue
            _before, run, _best = run_lengths(rows, this_monday)
            if plan.remind_push:
                try:
                    if pusher(db, user.id, push_message(row.goal, row.day_mask, row.finishes, run), now):
                        result["pushed"] += 1
                        count("push_sent")
                except Exception as error:
                    db.rollback()
                    print(f"Your week notification for user {user.id} failed: {error}")
            if not plan.remind_email:
                continue
            opted_out = _opted_out_since(db, plan)
            if not mail_ok or not user.is_verified or opted_out:
                if opted_out:
                    plan.remind_email = False
                    db.commit()
                count("dropped")
                result["dropped"] += 1
                continue
            lock_email_budget(db)
            if allowance(db, now) <= 0:
                db.rollback()
                result["limited"] = True
                count("dropped")
                result["dropped"] += 1
                continue  # the budget is spent for today; Sunday comes round again
            from .announcements import unsubscribe_token
            from .check_in import make_token
            from .digest import app_url
            try:
                titles = in_progress(db, user.id)
                token = make_token(user.id, titles, "week") if titles else None
                unsubscribe_url = f"{app_url()}/email/updates/unsubscribe?token={unsubscribe_token(user.id)}"
                subject, html, _text = build_email(user.username, row.goal, row.day_mask, row.finishes, run, titles,
                                                   token, unsubscribe_url)
            except Exception as error:
                db.rollback()
                print(f"Your week email for user {user.id} couldn't be built: {error}")
                continue
            db.add(models.EmailCampaignSend(campaign_key=f"{SEND_PREFIX}{this_monday.isoformat()}",
                                            user_id=user.id, status="sent", sent_at=now))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                continue
            try:
                await sender(user.email, subject, html, unsubscribe_url)
                result["sent"] += 1
                count("sent")
            except Exception as error:  # one bad address must not stop the rest
                print(f"Your week email to user {user.id} failed: {error}")
                result["failed"] += 1
        return result
    finally:
        db.close()


async def your_week_loop(app) -> None:
    """Background task started with the app; never raises."""
    from .database import SessionLocal
    await asyncio.sleep(FIRST_CHECK_DELAY_SECONDS)
    while True:
        try:
            result = await send_due(SessionLocal)
            if result["sent"] or result["pushed"] or result["failed"]:
                print(f"Your week nudges: {result}")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"Your week nudge check failed: {error}")
        await asyncio.sleep(CHECK_EVERY_SECONDS)


# ---------------------------------------------------------------- Site stats

def stats(db: Session, days: int, now: datetime) -> dict:
    table = models.SiteTrafficDaily
    counts = dict(db.query(table.key, func.sum(table.count)).filter(
        table.kind == "yourweek", table.day >= (now - timedelta(days=days - 1)).date(),
    ).group_by(table.key).all())
    plan, week = models.YourWeekPlan, models.YourWeekWeek
    recent = (now - timedelta(days=28)).date()
    kept_recently = db.query(week.user_id).filter(week.kept_at.isnot(None), week.week_start >= recent) \
        .group_by(week.user_id).having(func.count(week.id) >= 2).count()
    return {
        "counts": {key: int(counts.get(key) or 0) for key in COUNTERS},
        "labels": COUNTERS,
        "with_pace": int(db.query(func.count(plan.id)).filter(plan.goal.isnot(None)).scalar() or 0),
        "by_pace": [{"pace": GOALS[key][2], "count": int(db.query(func.count(plan.id)).filter(plan.goal == key).scalar() or 0)}
                    for key in GOAL_ORDER],
        "email_on": int(db.query(func.count(plan.id)).filter(plan.remind_email.is_(True)).scalar() or 0),
        "push_on": int(db.query(func.count(plan.id)).filter(plan.remind_push.is_(True)).scalar() or 0),
        "kept_two_of_four": int(kept_recently),
        "kept_all_time": int(db.query(func.count(week.id)).filter(week.kept_at.isnot(None)).scalar() or 0),
    }
