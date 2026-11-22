"""Watch together, read together: one title, a weekly pace, and notes that wait for you (Nov 2026).

Two to six people take the same title at the same pace: a season of a show, an anime,
a book or manga by chapter, a podcast or an audiobook. The plan splits it into weeks
("2 episodes a week"), everyone's place shows on one track, and notes left at an
episode or chapter stay folded until the reader gets there, so nobody spoils anybody.

* A plan copies the title in when it starts and never reads anyone's library for it
  again, except for one thing a member chooses: while "follow my library" is on, their
  place follows the checkpoint they save in their own library. Only checkpoints saved
  after they joined (or last moved here) count, so a rewatch never jumps ahead.
* Moving forward here moves the member's own library checkpoint forward too, never
  back, and only while they keep that switch on.
* Notes are only ever shown to people in the plan, and only once their place reaches
  the note's part. Part 0 is "before we start" and everyone can read it.
* The bell (and so push, under the "Watch together" switch) says when someone joins,
  leaves a note you can already read, gets through the week's stretch before you, or
  finishes, and when a new week starts. One optional email a week goes to members who
  have been away for a few days and have fallen behind someone, or have a note waiting.

New tables only (together_plans, together_members, together_notes).
"""
from __future__ import annotations

import asyncio
import os
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from html import escape
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models

# library category -> (title kind, unit, label, verb, done verb)
CATEGORIES = {
    "tv-shows": ("tv", "episode", "TV show", "Watch", "watched"),
    "anime": ("anime", "episode", "Anime", "Watch", "watched"),
    "books": ("book", "chapter", "Book", "Read", "read"),
    "manga": ("manga", "chapter", "Manga", "Read", "read"),
    "podcasts": ("podcast", "episode", "Podcast", "Listen", "heard"),
    "audiobooks": ("audiobook", "chapter", "Audiobook", "Listen", "heard"),
}
DONE_FIELD = {"tv-shows": "watched", "anime": "watched", "books": "read", "manga": "read", "podcasts": "listened",
              "audiobooks": "listened"}
# The button that moves a member on by one: "Watched episode 4".
NEXT_WORD = {"tv-shows": "Watched", "anime": "Watched", "books": "Finished", "manga": "Finished",
             "podcasts": "Listened to", "audiobooks": "Finished"}
MEMBERS_MAX = 6
ACTIVE_MAX = 8                  # plans one member can be in at once
TOTAL_MAX = 1000
NOTE_MAX = 500
NOTES_PER_MEMBER = 300
START_WITHIN_DAYS = 60
ENDED_SHOWN = 6
QUIET_END_WEEKS = 8             # a plan this many weeks past its last week ends on its own
EMAIL_AWAY_DAYS = 3             # the reminder only goes to members who haven't opened OmniTrackr for this long
EMAIL_FROM_DAY = 2              # ...and not before the third day of a plan week
SEND_PREFIX = "together-"
CHECK_EVERY_SECONDS = 3600
FIRST_CHECK_DELAY_SECONDS = 600
PER_RUN_LIMIT = 25
UTM = "utm_source=email&utm_campaign=together"
NOTE_TYPES = ("together_invite", "together_joined", "together_note", "together_ahead", "together_done",
              "together_week")


class TogetherError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def clamp_tz(value) -> int:
    """Minutes east of UTC from the browser, kept to real time zones."""
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return 0
    return max(-14 * 60, min(14 * 60, minutes))


def local_today(tz: int = 0, now: Optional[datetime] = None) -> date:
    return ((now or _now()) + timedelta(minutes=clamp_tz(tz))).date()


def daily_limit() -> int:
    try:
        return max(0, int(os.getenv("TOGETHER_DAILY_LIMIT", "30")))
    except ValueError:
        return 30


def emails_enabled() -> bool:
    if os.getenv("TOGETHER_EMAILS", "").strip().lower() in ("off", "0", "false", "no"):
        return False
    return os.getenv("TESTING", "").lower() != "true"


def count(event: str, request=None) -> None:
    from . import funnel
    funnel.record(event, request)


# ---------------------------------------------------------------- the schedule

def weeks_total(plan) -> int:
    return -(-plan.total // plan.pace)


def week_index(plan, today: date) -> int:
    """0 for the first week. Negative before the plan starts."""
    return (today - plan.starts_on).days // 7


def week_span(plan, index: int) -> tuple[int, int]:
    """(first part, last part) of one week, 1-based."""
    return index * plan.pace + 1, min(plan.total, (index + 1) * plan.pace)


def target(plan, today: date) -> int:
    """The part everyone should have reached by the end of this week."""
    index = week_index(plan, today)
    if index < 0:
        return 0
    return min(plan.total, (index + 1) * plan.pace)


def ends_on(plan) -> date:
    return plan.starts_on + timedelta(days=7 * weeks_total(plan) - 1)


def week_start(plan, index: int) -> date:
    return plan.starts_on + timedelta(days=7 * index)


def unit_words(plan) -> tuple[str, str]:
    return (plan.unit, plan.unit + "s")


def part_label(plan, part: int) -> str:
    if part <= 0:
        return "Before you start"
    return f"{plan.unit.capitalize()} {part}"


def span_label(plan, first: int, last: int, capital: bool = True) -> str:
    one, many = unit_words(plan)
    word = (many if first != last else one)
    word = word.capitalize() if capital else word
    return f"{word} {first}" if first == last else f"{word} {first}–{last}"


def next_label(plan, position: int) -> Optional[str]:
    """The words on the one-tap button, or None once the member is at the end."""
    if position >= plan.total:
        return None
    return f"{NEXT_WORD[plan.category]} {plan.unit} {position + 1}"


def scope_label(plan) -> str:
    return f"Season {plan.season}" if plan.season else ""


def pace_label(plan) -> str:
    one, many = unit_words(plan)
    return f"{plan.pace} {one if plan.pace == 1 else many} a week"


def verb(plan) -> str:
    return CATEGORIES[plan.category][3]


def _day(value: date) -> str:
    return f"{value.strftime('%a')}, {value.strftime('%b')} {value.day}"


def status_of(plan, position: int, today: date) -> str:
    """finished, waiting (not started), ahead, done (this week's stretch), on, behind."""
    if position >= plan.total:
        return "finished"
    index = week_index(plan, today)
    if index < 0:
        return "waiting"
    if index >= weeks_total(plan):
        return "behind"
    first, last = week_span(plan, index)
    if position > last:
        return "ahead"
    if position == last:
        return "done"
    if position < first - 1:
        return "behind"
    return "on"


# ---------------------------------------------------------------- libraries and checkpoints

def _model(category: str):
    from .progress import CATEGORIES as PROGRESS
    return PROGRESS[category]


def library_row(db: Session, user_id: int, category: str, item_id: Optional[int]):
    if category not in CATEGORIES or not item_id:
        return None
    model = _model(category)
    return db.query(model).filter(model.id == item_id, model.user_id == user_id).first()


def find_library_row(db: Session, user_id: int, category: str, title: str):
    from .title_pages import normalize
    model = _model(category)
    wanted = normalize(title)
    for row in db.query(model).filter(model.user_id == user_id, func.lower(func.trim(model.title)) == wanted).limit(3):
        return row
    return None


def checkpoint(db: Session, user_id: int, category: str, item_id: Optional[int]):
    if not item_id:
        return None
    return db.query(models.ProgressCheckpoint).filter_by(user_id=user_id, category=category, item_id=item_id).first()


def placed(plan, entry) -> Optional[int]:
    """Where a library checkpoint puts someone in this plan, or None when it can't be placed."""
    if entry is None or entry.unit is None or entry.position is None:
        return None
    if entry.unit != plan.unit:
        return None
    position = int(entry.position)
    if plan.unit == "episode" and plan.season:
        if entry.season is not None and entry.season != 0:
            if entry.season > plan.season:
                return plan.total
            if entry.season < plan.season:
                return 0
    elif plan.unit == "episode" and entry.season not in (None, 0, 1):
        return None  # a later season of a show counted from episode 1 can't be placed
    return max(0, min(plan.total, position))


def _library_values(plan, entry, position: int) -> dict:
    note = entry.note if entry is not None and entry.unit is not None else None
    values = {"unit": plan.unit, "position": position, "season": None, "note": note}
    if plan.unit == "episode":
        values["season"] = plan.season if plan.season else (entry.season if entry is not None and entry.unit == "episode" else None)
    return values


def move_library(db: Session, user_id: int, plan, item_id: int, position: int) -> bool:
    """Move the member's own checkpoint forward to ``position``. Never back. Commits when it writes."""
    from fastapi import HTTPException
    from .progress import _write_progress
    if position < 1 or library_row(db, user_id, plan.category, item_id) is None:
        return False
    entry = checkpoint(db, user_id, plan.category, item_id)
    if entry is not None and entry.unit is not None:
        now_at = placed(plan, entry)
        if now_at is None or now_at >= position:
            return False
    revision = entry.revision if entry is not None else 0
    try:
        _write_progress(db, user_id, plan.category, item_id, revision, _library_values(plan, entry, position))
    except HTTPException:
        return False
    return True


# ---------------------------------------------------------------- people

def _initials(name: str) -> str:
    letters = [part[0] for part in re.split(r"[^A-Za-z0-9]+", name or "") if part]
    return ("".join(letters[:2]) or (name or "?")[:1]).upper()


def rows(db: Session, plan_id: int) -> list[tuple[models.TogetherMember, models.User]]:
    """The plan's active people, in the order they joined."""
    return (db.query(models.TogetherMember, models.User)
            .join(models.User, models.User.id == models.TogetherMember.user_id)
            .filter(models.TogetherMember.plan_id == plan_id, models.User.is_active.is_(True))
            .order_by(models.TogetherMember.joined_at, models.TogetherMember.id).all())


def _names(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _with_line(plan, viewer_id: int, people: list[tuple]) -> str:
    others = [user.username for _, user in people if user.id != viewer_id]
    if not others:
        return ""
    if len(others) > 3:
        return f"with {others[0]}, {others[1]} and {len(others) - 2} more"
    return "with " + _names(others)


def _notify(db: Session, user_id: int, kind: str, message: str, link: str, *, once_unread: bool = False) -> None:
    if once_unread:
        waiting = db.query(models.Notification.id).filter(
            models.Notification.user_id == user_id, models.Notification.type == kind,
            models.Notification.link == link, models.Notification.read_at.is_(None)).first()
        if waiting is not None:
            return
    db.add(models.Notification(user_id=user_id, type=kind, message=message[:250], link=link))


def link_for(plan) -> str:
    return f"/together/{plan.id}"


def invite_path(plan) -> str:
    return f"/together/join/{plan.token}"


def invite_url(plan) -> str:
    from .digest import app_url
    return app_url() + invite_path(plan)


def active_count(db: Session, user_id: int) -> int:
    return (db.query(func.count(models.TogetherMember.id))
            .join(models.TogetherPlan, models.TogetherPlan.id == models.TogetherMember.plan_id)
            .filter(models.TogetherMember.user_id == user_id, models.TogetherPlan.ended_at.is_(None)).scalar() or 0)


def by_token(db: Session, token: str) -> Optional[models.TogetherPlan]:
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,40}", token):
        return None
    return db.query(models.TogetherPlan).filter(models.TogetherPlan.token == token).first()


def member_of(db: Session, plan_id: int, user_id: int) -> Optional[models.TogetherMember]:
    return db.query(models.TogetherMember).filter_by(plan_id=plan_id, user_id=user_id).first()


def get_for_member(db: Session, plan_id: int, user) -> tuple[models.TogetherPlan, models.TogetherMember]:
    plan = db.get(models.TogetherPlan, plan_id)
    member = member_of(db, plan_id, user.id) if plan is not None else None
    if plan is None or member is None:
        raise TogetherError("This plan isn't here, or you're not in it.", 404)
    return plan, member


# ---------------------------------------------------------------- moving

def _apply_move(db: Session, plan, member, user, new: int, today: date, now: datetime, people=None) -> int:
    """Set a new place and send the notices it earns. Returns how many notes it opened. Does not commit."""
    old = member.position or 0
    new = max(0, min(plan.total, int(new)))
    if new == old:
        return 0
    member.position = new
    plan.updated_at = now
    people = people if people is not None else rows(db, plan.id)
    others = [(other, person) for other, person in people if person.id != member.user_id]
    link = link_for(plan)
    if new >= plan.total > old:
        member.finished_at = now
        count("together_finished")
        for other, person in others:
            if (other.position or 0) < plan.total:
                _notify(db, person.id, "together_done",
                        f"{user.username} finished {plan.title}. Their notes from the end are waiting for you.", link)
    elif new < plan.total:
        member.finished_at = None
    index = week_index(plan, today)
    if 0 <= index < weeks_total(plan) and new < plan.total:
        _first, last = week_span(plan, index)
        if new >= last > old and member.done_week != index:
            member.done_week = index
            count("together_week_done")
            stretch = span_label(plan, *week_span(plan, index), capital=False)
            for other, person in others:
                if (other.position or 0) < last:
                    _notify(db, person.id, "together_ahead",
                            f"{user.username} is done with this week's {stretch} of {plan.title}. "
                            f"You're on {part_label(plan, other.position or 0).lower()}.", link, once_unread=True)
    opened = 0
    if new > old:
        opened = (db.query(func.count(models.TogetherNote.id))
                  .filter(models.TogetherNote.plan_id == plan.id, models.TogetherNote.user_id != member.user_id,
                          models.TogetherNote.part > old, models.TogetherNote.part <= new).scalar() or 0)
    if people and member in [other for other, _ in people] and all((other.position or 0) >= plan.total
                                                                      for other, _ in people):
        plan.ended_at = plan.ended_at or now
    return int(opened)


def sync(db: Session, plan, people, today: date, now: datetime) -> bool:
    """Pull in checkpoints people saved in their own libraries. Returns True if anything changed."""
    changed = False
    for member, user in people:
        if not member.follow_library or not member.item_id:
            continue
        entry = checkpoint(db, user.id, plan.category, member.item_id)
        if entry is None or entry.unit is None or entry.position is None or entry.updated_at is None:
            continue
        if member.moved_at is not None and entry.updated_at <= member.moved_at:
            continue
        member.moved_at = entry.updated_at
        changed = True
        position = placed(plan, entry)
        if position is not None and position != member.position:
            _apply_move(db, plan, member, user, position, today, now, people)
    return changed


def move(db: Session, plan, member, user, position: int, today: date, library: bool = True,
         now: Optional[datetime] = None) -> dict:
    """The member says where they are. Commits."""
    now = now or _now()
    if plan.ended_at is not None:
        raise TogetherError("This plan has finished, so places are fixed now.", 409)
    if not isinstance(position, int) or isinstance(position, bool) or not 0 <= position <= plan.total:
        raise TogetherError(f"Pick a {plan.unit} between 0 and {plan.total}.", 422)
    old = member.position or 0
    opened = _apply_move(db, plan, member, user, position, today, now)
    member.moved_at = now
    if position > old:
        count("together_moved")
    db.commit()
    saved = False
    if library and member.follow_library and member.item_id and position > old:
        saved = move_library(db, user.id, plan, member.item_id, position)
        if saved:
            # The checkpoint just written is this move, not a new one to pull back in.
            entry = checkpoint(db, user.id, plan.category, member.item_id)
            fresh = member_of(db, plan.id, user.id)
            if entry is not None and fresh is not None and entry.updated_at is not None:
                fresh.moved_at = max(entry.updated_at, fresh.moved_at or entry.updated_at)
                db.commit()
    return {"opened": opened, "library_saved": saved}


# ---------------------------------------------------------------- making, joining, leaving

def _clean_total(value) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= TOTAL_MAX:
        raise TogetherError(f"Pick a length between 1 and {TOTAL_MAX}.", 422)
    return value


def _clean_pace(value, total: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= total:
        raise TogetherError("Pick how many to do each week, no more than the whole thing.", 422)
    return value


def create(db: Session, user, row, category: str, *, total: int, pace: int, starts_on: date, today: date,
           season: Optional[int] = None, position: int = 0, remind_email: bool = True,
           now: Optional[datetime] = None) -> models.TogetherPlan:
    """Start a plan from a title in the member's own library. Does not commit."""
    from .check_in import _image
    now = now or _now()
    if category not in CATEGORIES:
        raise TogetherError("Watch together works for TV shows, anime, books, manga, podcasts and audiobooks.", 422)
    if active_count(db, user.id) >= ACTIVE_MAX:
        raise TogetherError(f"You're in {ACTIVE_MAX} plans already. Finish or leave one to start another.", 409)
    kind, unit, *_ = CATEGORIES[category]
    total = _clean_total(total)
    pace = _clean_pace(pace, total)
    if season is not None and (unit != "episode" or category == "podcasts" or not 1 <= season <= 200):
        raise TogetherError("Only TV shows and anime have seasons here.", 422)
    if starts_on < today - timedelta(days=6) or starts_on > today + timedelta(days=START_WITHIN_DAYS):
        raise TogetherError(f"Pick a start date from this week to {START_WITHIN_DAYS} days from now.", 422)
    title = " ".join((row.title or "").split())[:200]
    if not title:
        raise TogetherError("That title has no name to share.", 422)
    year = getattr(row, "year", None)
    plan = models.TogetherPlan(owner_id=user.id, token=secrets.token_urlsafe(16), category=category, kind=kind,
                               title=title, year=year if isinstance(year, int) else None, image=_image(category, row),
                               unit=unit, season=season, total=total, pace=pace, starts_on=starts_on,
                               created_at=now, updated_at=now)
    db.add(plan)
    db.flush()
    db.add(models.TogetherMember(plan_id=plan.id, user_id=user.id, joined_at=now, moved_at=now, item_id=row.id,
                                 position=max(0, min(total, int(position or 0))), remind_email=bool(remind_email),
                                 seen_at=now, seen_position=max(0, min(total, int(position or 0)))))
    db.flush()
    return plan


def invite_friends(db: Session, plan, user, friend_ids: list[int]) -> int:
    """Ask friends in. Only real friends who aren't in the plan get the note. Does not commit."""
    from .crud.friends import are_friends
    asked = 0
    inside = {user_id for user_id, in db.query(models.TogetherMember.user_id).filter_by(plan_id=plan.id)}
    for friend_id in dict.fromkeys(friend_ids or []):
        if friend_id == user.id or friend_id in inside or not are_friends(db, user.id, friend_id):
            continue
        _notify(db, friend_id, "together_invite",
                f"{user.username} wants to {verb(plan).lower()} {plan.title} with you, {pace_label(plan)}.",
                invite_path(plan), once_unread=True)
        asked += 1
    return asked


def preview(db: Session, plan, today: date) -> dict:
    """What the invite page shows anyone with the link: the title, the pace and first names. No notes, no places."""
    people = rows(db, plan.id)
    owner = next((person for member, person in people if person.id == plan.owner_id), None)
    index = week_index(plan, today)
    return {
        "title": plan.title, "label": CATEGORIES[plan.category][2], "year": plan.year, "image": plan.image,
        "scope": scope_label(plan), "total": plan.total, "unit": plan.unit, "pace": pace_label(plan),
        "length": f"{plan.total} {unit_words(plan)[0] if plan.total == 1 else unit_words(plan)[1]}",
        "starts_on": plan.starts_on.isoformat(), "starts_label": _day(plan.starts_on),
        "started": index >= 0, "week": index + 1 if index >= 0 else 0, "weeks": weeks_total(plan),
        "ends_label": _day(ends_on(plan)), "verb": verb(plan),
        "owner": owner.username if owner is not None else None,
        "people": [person.username for _, person in people],
        "full": len(people) >= MEMBERS_MAX, "ended": plan.ended_at is not None,
    }


def join(db: Session, plan, user, *, position: Optional[int] = None, add_to_library: bool = True,
         remind_email: bool = True, now: Optional[datetime] = None) -> tuple[models.TogetherMember, bool]:
    """Join through the link. Returns (member, newly joined). Commits."""
    from .pick import add_to_library as add_title
    from .progress import lock_progress_owner
    now = now or _now()
    existing = member_of(db, plan.id, user.id)
    if existing is not None:
        return existing, False
    if plan.ended_at is not None:
        raise TogetherError("This plan has finished. Ask whoever made it to start a new one.", 409)
    people = rows(db, plan.id)
    if len(people) >= MEMBERS_MAX:
        raise TogetherError(f"This plan is full: {MEMBERS_MAX} people is the most.", 409)
    if active_count(db, user.id) >= ACTIVE_MAX:
        raise TogetherError(f"You're in {ACTIVE_MAX} plans already. Finish or leave one to join this.", 409)
    row = find_library_row(db, user.id, plan.category, plan.title)
    if row is None and add_to_library:
        lock_progress_owner(db, user.id)
        _state, row = add_title(db, user, {"kind": plan.kind, "title": plan.title, "year": plan.year, "creator": None},
                                image=plan.image)
    if position is None:
        position = placed(plan, checkpoint(db, user.id, plan.category, row.id)) if row is not None else None
    position = max(0, min(plan.total, int(position or 0)))
    member = models.TogetherMember(plan_id=plan.id, user_id=user.id, joined_at=now, moved_at=now,
                                   item_id=row.id if row is not None else None, position=position,
                                   remind_email=bool(remind_email), seen_at=now, seen_position=position,
                                   finished_at=now if position >= plan.total else None)
    db.add(member)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        found = member_of(db, plan.id, user.id)
        if found is None:
            raise TogetherError("That didn't work. Please try again.", 409)
        return found, False
    for other, person in people:
        _notify(db, person.id, "together_joined",
                f"{user.username} joined {plan.title} with you. {pace_label(plan).capitalize()}.", link_for(plan))
    db.query(models.Notification).filter(
        models.Notification.user_id == user.id, models.Notification.type == "together_invite",
        models.Notification.link == invite_path(plan), models.Notification.read_at.is_(None),
    ).update({"read_at": now}, synchronize_session=False)
    plan.updated_at = now
    db.commit()
    count("together_joined")
    return member, True


def _hand_over(db: Session, plan, leaving_user_id: int) -> bool:
    """Give the plan to the next person in it. False when nobody else is left."""
    for member, person in rows(db, plan.id):
        if person.id != leaving_user_id:
            plan.owner_id = person.id
            return True
    return False


def leave(db: Session, plan, member) -> bool:
    """Leave a plan. The member's notes go with them. Returns False when the plan itself went. Commits."""
    user_id = member.user_id
    db.query(models.TogetherNote).filter_by(plan_id=plan.id, user_id=user_id).delete(synchronize_session=False)
    db.delete(member)
    db.flush()
    if plan.owner_id == user_id and not _hand_over(db, plan, user_id):
        db.delete(plan)
        db.commit()
        return False
    plan.updated_at = _now()
    db.commit()
    return True


def remove(db: Session, plan, owner, member_id: int) -> None:
    if plan.owner_id != owner.id:
        raise TogetherError("Only whoever runs the plan can take someone out.", 403)
    member = db.query(models.TogetherMember).filter_by(id=member_id, plan_id=plan.id).first()
    if member is None:
        raise TogetherError("They aren't in this plan.", 404)
    if member.user_id == owner.id:
        raise TogetherError("Use Leave to take yourself out.", 422)
    leave(db, plan, member)


def update_plan(db: Session, plan, user, *, pace: Optional[int] = None, total: Optional[int] = None) -> None:
    if plan.owner_id != user.id:
        raise TogetherError("Only whoever runs the plan can change it.", 403)
    if plan.ended_at is not None:
        raise TogetherError("This plan has finished.", 409)
    if total is not None:
        total = _clean_total(total)
        highest = max((member.position or 0 for member in plan.members), default=0)
        if total < highest:
            raise TogetherError(f"Someone is already on {plan.unit} {highest}, so it can't be shorter than that.", 422)
        plan.total = total
        if (pace or plan.pace) > total:
            plan.pace = total
    if pace is not None:
        plan.pace = _clean_pace(pace, plan.total)
    plan.updated_at = _now()
    db.commit()


def end(db: Session, plan, user) -> None:
    if plan.owner_id != user.id:
        raise TogetherError("Only whoever runs the plan can wrap it up.", 403)
    plan.ended_at = plan.ended_at or _now()
    db.commit()


def new_link(db: Session, plan, user) -> str:
    if plan.owner_id != user.id:
        raise TogetherError("Only whoever runs the plan can make a new link.", 403)
    plan.token = secrets.token_urlsafe(16)
    db.commit()
    return invite_url(plan)


def set_reminder(db: Session, member, remind_email: Optional[bool] = None, follow_library: Optional[bool] = None) -> None:
    if remind_email is not None:
        member.remind_email = bool(remind_email)
    if follow_library is not None:
        member.follow_library = bool(follow_library)
        if follow_library:
            # Only what's saved in the library from now on counts, as when joining.
            member.moved_at = _now()
    db.commit()


# ---------------------------------------------------------------- notes

def clean_body(value) -> str:
    if not isinstance(value, str):
        raise TogetherError("Write something first.", 422)
    lines = [" ".join(line.split()) for line in value.replace("\r", "").split("\n")]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if not text:
        raise TogetherError("Write something first.", 422)
    if len(text) > NOTE_MAX:
        raise TogetherError(f"Keep a note under {NOTE_MAX} characters.", 422)
    return text


def add_note(db: Session, plan, member, user, part: int, body: str, now: Optional[datetime] = None) -> models.TogetherNote:
    now = now or _now()
    if not isinstance(part, int) or isinstance(part, bool) or not 0 <= part <= plan.total:
        raise TogetherError(f"Pick a {plan.unit} between 0 and {plan.total}.", 422)
    if part > (member.position or 0):
        raise TogetherError(f"Leave notes where you are or earlier. You're on {part_label(plan, member.position or 0).lower()}.", 422)
    text = clean_body(body)
    mine = db.query(func.count(models.TogetherNote.id)).filter_by(plan_id=plan.id, user_id=user.id).scalar() or 0
    if mine >= NOTES_PER_MEMBER:
        raise TogetherError(f"You've left {NOTES_PER_MEMBER} notes here, which is the most.", 409)
    note = models.TogetherNote(plan_id=plan.id, user_id=user.id, part=part, body=text, created_at=now)
    db.add(note)
    where = "before you start" if part == 0 else f"at {part_label(plan, part).lower()}"
    for other, person in rows(db, plan.id):
        if person.id != user.id and (other.position or 0) >= part:
            _notify(db, person.id, "together_note", f"{user.username} left a note {where} of {plan.title}.",
                    link_for(plan) + "#notes", once_unread=True)
    plan.updated_at = now
    db.commit()
    count("together_note")
    return note


def delete_note(db: Session, plan, user, note_id: int) -> None:
    note = db.query(models.TogetherNote).filter_by(id=note_id, plan_id=plan.id).first()
    if note is None:
        raise TogetherError("That note isn't here anymore.", 404)
    if note.user_id != user.id and plan.owner_id != user.id:
        raise TogetherError("You can only delete your own notes.", 403)
    db.delete(note)
    db.commit()


# ---------------------------------------------------------------- what people see

def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.replace(microsecond=0).isoformat() + "Z" if value else None


def headline(plan, me, people, today: date) -> str:
    """One sentence about where the viewer stands, for the card and the plan page."""
    position = me.position or 0
    others = [(member, person) for member, person in people if person.id != me.user_id]
    index = week_index(plan, today)
    if plan.ended_at is not None:
        return "Everyone finished." if all((m.position or 0) >= plan.total for m, _ in people) else "This plan has wrapped up."
    if position >= plan.total:
        behind = [person.username for member, person in others if (member.position or 0) < plan.total]
        return f"You finished. Waiting on {_names(behind)}." if behind else "Everyone finished."
    if index < 0:
        days = (plan.starts_on - today).days
        when = "tomorrow" if days == 1 else f"on {_day(plan.starts_on)}"
        return f"Starts {when}. {pace_label(plan).capitalize()}."
    first, last = week_span(plan, min(index, weeks_total(plan) - 1))
    if index >= weeks_total(plan):
        return f"The last week is over. You're on {part_label(plan, position).lower()} of {plan.total}."
    done_others = [person.username for member, person in others if (member.position or 0) >= last]
    if position >= last:
        if index + 1 < weeks_total(plan):
            nxt = week_span(plan, index + 1)
            return f"You're done for this week. Next up: {span_label(plan, *nxt, capital=False)}."
        return "You're done for this week, and that was the last stretch."
    if position < first - 1:
        return (f"You're on {part_label(plan, position).lower()}. "
                f"This week ends at {plan.unit} {last}, so there's some catching up to do.")
    if done_others:
        return f"{_names(done_others)} {'is' if len(done_others) == 1 else 'are'} done with this week. You're on {position} of {last}."
    return f"This week: {span_label(plan, first, last, capital=False)}. You're on {position}."


def _visible(note, me) -> bool:
    return note.user_id == me.user_id or note.part <= (me.position or 0)


def detail(db: Session, plan, me, viewer, today: date, now: Optional[datetime] = None, mark_seen: bool = True) -> dict:
    """Everything the plan page shows one member. Opening it marks its notices read."""
    now = now or _now()
    people = rows(db, plan.id)
    if sync(db, plan, people, today, now):
        db.commit()
        people = rows(db, plan.id)
        me = member_of(db, plan.id, viewer.id) or me
    names = {person.id: person.username for _, person in people}
    index = week_index(plan, today)
    total_weeks = weeks_total(plan)
    current = min(max(index, 0), total_weeks - 1)
    first, last = week_span(plan, current)
    weeks = []
    for number in range(total_weeks):
        start_part, end_part = week_span(plan, number)
        weeks.append({"number": number + 1, "first": start_part, "last": end_part,
                      "starts_on": week_start(plan, number).isoformat(),
                      "label": span_label(plan, start_part, end_part),
                      "state": "past" if number < index else ("now" if number == index else "later")})
    notes = (db.query(models.TogetherNote).filter(models.TogetherNote.plan_id == plan.id)
             .order_by(models.TogetherNote.part, models.TogetherNote.created_at, models.TogetherNote.id).all())
    visible, locked = [], {}
    seen, seen_position = me.seen_at, me.seen_position or 0
    unread = 0
    for note in notes:
        author = names.get(note.user_id)
        if author is None:
            continue
        if _visible(note, me):
            fresh = note.user_id != me.user_id and (seen is None or note.created_at > seen or note.part > seen_position)
            unread += 1 if fresh else 0
            visible.append({"id": note.id, "part": note.part, "part_label": part_label(plan, note.part),
                            "body": note.body, "author": author, "initials": _initials(author),
                            "you": note.user_id == me.user_id, "new": fresh, "created_at": _iso(note.created_at),
                            "can_delete": note.user_id == me.user_id or plan.owner_id == me.user_id})
        else:
            group = locked.setdefault(note.part, {"part": note.part, "part_label": part_label(plan, note.part),
                                                  "count": 0, "authors": []})
            group["count"] += 1
            if author not in group["authors"]:
                group["authors"].append(author)
    owner_view = plan.owner_id == me.user_id
    linked = library_row(db, viewer.id, plan.category, me.item_id) if me.item_id else None
    entry = checkpoint(db, viewer.id, plan.category, me.item_id) if linked is not None else None
    library_at = placed(plan, entry) if entry is not None else None
    result = {
        "id": plan.id, "path": link_for(plan), "invite_url": invite_url(plan), "invite_path": invite_path(plan),
        "title": plan.title, "kind": plan.kind, "category": plan.category, "label": CATEGORIES[plan.category][2],
        "year": plan.year, "image": plan.image, "verb": verb(plan), "unit": plan.unit,
        "unit_plural": unit_words(plan)[1], "season": plan.season, "scope": scope_label(plan),
        "total": plan.total, "pace": plan.pace, "pace_label": pace_label(plan),
        "starts_on": plan.starts_on.isoformat(), "starts_label": _day(plan.starts_on),
        "ends_on": ends_on(plan).isoformat(), "ends_label": _day(ends_on(plan)),
        "weeks_total": total_weeks, "week": index + 1, "started": index >= 0, "weeks": weeks,
        "this_week": {"number": current + 1, "first": first, "last": last, "label": span_label(plan, first, last),
                      "starts_on": week_start(plan, current).isoformat()} if index < total_weeks else None,
        "target": target(plan, today), "ended": plan.ended_at is not None,
        "headline": headline(plan, me, people, today),
        "with": _with_line(plan, viewer.id, people),
        "you": {"position": me.position or 0, "owner": owner_view, "remind_email": bool(me.remind_email),
                "follow_library": bool(me.follow_library), "linked": linked is not None,
                "library_at": library_at,
                "library_done": bool(getattr(linked, DONE_FIELD[plan.category], False)) if linked is not None else False,
                "item_id": linked.id if linked is not None else None,
                "status": status_of(plan, me.position or 0, today), "member_id": me.id},
        "people": [{"member_id": member.id, "username": person.username, "initials": _initials(person.username),
                    "you": person.id == viewer.id, "owner": person.id == plan.owner_id,
                    "position": member.position or 0, "status": status_of(plan, member.position or 0, today),
                    "finished": (member.position or 0) >= plan.total, "joined_at": _iso(member.joined_at)}
                   for member, person in people],
        "notes": visible, "locked": sorted(locked.values(), key=lambda group: group["part"]),
        "unread": unread, "members_max": MEMBERS_MAX, "note_max": NOTE_MAX,
    }
    if mark_seen:
        fresh = member_of(db, plan.id, viewer.id)
        if fresh is not None:
            fresh.seen_at = now
            fresh.seen_position = fresh.position or 0
        db.query(models.Notification).filter(
            models.Notification.user_id == viewer.id,
            models.Notification.link.in_((link_for(plan), link_for(plan) + "#notes")),
            models.Notification.type.in_(NOTE_TYPES), models.Notification.read_at.is_(None),
        ).update({"read_at": now}, synchronize_session=False)
        db.commit()
    return result


def mine(db: Session, user, today: date, now: Optional[datetime] = None) -> dict:
    """The member's plans: running ones with a line each, then a few that ended."""
    now = now or _now()
    memberships = (db.query(models.TogetherMember, models.TogetherPlan)
                   .join(models.TogetherPlan, models.TogetherPlan.id == models.TogetherMember.plan_id)
                   .filter(models.TogetherMember.user_id == user.id)
                   .order_by(models.TogetherPlan.ended_at.isnot(None), models.TogetherPlan.updated_at.desc(),
                             models.TogetherPlan.id.desc()).all())
    running, ended = [], []
    changed = False
    for me, plan in memberships:
        if plan.ended_at is not None:
            if len(ended) < ENDED_SHOWN:
                ended.append({"id": plan.id, "path": link_for(plan), "title": plan.title, "image": plan.image,
                              "label": CATEGORIES[plan.category][2], "scope": scope_label(plan),
                              "ended_on": plan.ended_at.date().isoformat(), "position": me.position or 0,
                              "total": plan.total, "unit": plan.unit})
            continue
        people = rows(db, plan.id)
        if sync(db, plan, people, today, now):
            changed = True
        me = next((member for member, person in people if person.id == user.id), me)
        index = week_index(plan, today)
        total_weeks = weeks_total(plan)
        first, last = week_span(plan, min(max(index, 0), total_weeks - 1))
        unread = (db.query(func.count(models.TogetherNote.id))
                  .filter(models.TogetherNote.plan_id == plan.id, models.TogetherNote.user_id != user.id,
                          models.TogetherNote.part <= (me.position or 0),
                          or_(models.TogetherNote.created_at > (me.seen_at or datetime.min),
                              models.TogetherNote.part > (me.seen_position or 0))).scalar() or 0)
        waiting = (db.query(func.count(models.TogetherNote.id))
                   .filter(models.TogetherNote.plan_id == plan.id, models.TogetherNote.user_id != user.id,
                           models.TogetherNote.part > (me.position or 0)).scalar() or 0)
        position = me.position or 0
        running.append({
            "id": plan.id, "path": link_for(plan), "title": plan.title, "image": plan.image, "kind": plan.kind,
            "label": CATEGORIES[plan.category][2], "scope": scope_label(plan), "unit": plan.unit,
            "verb": verb(plan), "total": plan.total, "pace_label": pace_label(plan),
            "week": index + 1, "weeks_total": total_weeks, "started": index >= 0,
            "this_week": span_label(plan, first, last) if 0 <= index < total_weeks else None,
            "week_first": first if 0 <= index < total_weeks else None,
            "week_last": last if 0 <= index < total_weeks else None,
            "headline": headline(plan, me, people, today), "with": _with_line(plan, user.id, people),
            "position": position, "status": status_of(plan, position, today),
            "next_label": next_label(plan, position),
            "people": [{"username": person.username, "initials": _initials(person.username),
                        "position": member.position or 0, "you": person.id == user.id}
                       for member, person in people],
            "unread": int(unread), "waiting": int(waiting),
        })
    if changed:
        db.commit()
    return {"running": running, "ended": ended, "active_max": ACTIVE_MAX}


# ---------------------------------------------------------------- titles to start from

def suggestions(db: Session, user, limit: int = 24) -> list[dict]:
    """Titles in the member's library a plan can start from: the ones with a saved place first, then unfinished."""
    from .check_in import _image
    found, seen = [], set()
    entries = {(entry.category, entry.item_id): entry for entry in db.query(models.ProgressCheckpoint).filter(
        models.ProgressCheckpoint.user_id == user.id, models.ProgressCheckpoint.position.isnot(None),
        models.ProgressCheckpoint.category.in_(tuple(CATEGORIES))).order_by(models.ProgressCheckpoint.updated_at.desc()).limit(40)}

    def offer(category: str, row) -> None:
        if row is None or (category, row.id) in seen or len(found) >= limit or not (row.title or "").strip():
            return
        seen.add((category, row.id))
        kind, unit, label, *_ = CATEGORIES[category]
        entry = entries.get((category, row.id))
        total = None
        if category in ("tv-shows", "anime", "podcasts"):
            episodes = getattr(row, "episodes", None)
            total = episodes if isinstance(episodes, int) and 0 < episodes <= TOTAL_MAX else None
        elif category == "manga":
            chapters = getattr(row, "chapters", None)
            total = chapters if isinstance(chapters, int) and 0 < chapters <= TOTAL_MAX else None
        found.append({"category": category, "item_id": row.id, "title": " ".join(row.title.split())[:200],
                      "year": getattr(row, "year", None), "label": label, "unit": unit, "image": _image(category, row),
                      "total": total, "seasons": getattr(row, "seasons", None) if category in ("tv-shows", "anime") else None,
                      "at": {"position": entry.position, "season": entry.season, "unit": entry.unit} if entry else None})

    for (category, item_id), _entry in entries.items():
        offer(category, library_row(db, user.id, category, item_id))
    rest = []
    for category in CATEGORIES:
        model = _model(category)
        done = getattr(model, DONE_FIELD[category])
        for row in (db.query(model).filter(model.user_id == user.id, (done.is_(False)) | (done.is_(None)))
                    .order_by(model.id.desc()).limit(limit)):
            rest.append((getattr(row, "added_at", None) or datetime.min, row.id, category, row))
    rest.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    for _, _, category, row in rest:
        offer(category, row)
    return found


# ---------------------------------------------------------------- the weekly loop

def _link(path: str) -> str:
    from .digest import app_url
    joiner = "&" if "?" in path else "?"
    hash_at = path.find("#")
    if hash_at >= 0:
        return f"{app_url()}{path[:hash_at]}{joiner}{UTM}{path[hash_at:]}"
    return f"{app_url()}{path}{joiner}{UTM}"


def week_notices(db: Session, plan, people, today: date) -> int:
    """Announce a new week once. Returns how many notices went out. Does not commit."""
    index = week_index(plan, today)
    if index < 0 or index >= weeks_total(plan) or (plan.week_sent is not None and plan.week_sent >= index):
        return 0
    plan.week_sent = index
    first, last = week_span(plan, index)
    stretch = span_label(plan, first, last, capital=False)
    sent = 0
    for member, person in people:
        if (member.position or 0) >= last:
            continue
        others = [other_person.username for other, other_person in people if other_person.id != person.id]
        company = f" with {_names(others)}" if others and len(others) <= 3 else ""
        if index == 0:
            message = f"{plan.title}{company} starts today: {stretch} this week."
        else:
            message = f"Week {index + 1} of {plan.title}{company}: {stretch}."
        _notify(db, person.id, "together_week", message, link_for(plan))
        sent += 1
    return sent


def reminder_reason(db: Session, plan, member, people, today: date) -> Optional[dict]:
    """Why this member might like a nudge this week, or None."""
    index = week_index(plan, today)
    if index < 0 or index >= weeks_total(plan) or (today - week_start(plan, index)).days < EMAIL_FROM_DAY:
        return None
    if member.emailed_week is not None and member.emailed_week >= index:
        return None
    position = member.position or 0
    _first, last = week_span(plan, index)
    if position >= last or position >= plan.total:
        return None
    ahead = [(other, person) for other, person in people
             if person.id != member.user_id and (other.position or 0) > position]
    notes = (db.query(models.TogetherNote, models.User.username)
             .join(models.User, models.User.id == models.TogetherNote.user_id)
             .filter(models.TogetherNote.plan_id == plan.id, models.TogetherNote.user_id != member.user_id,
                     models.TogetherNote.part > position, models.TogetherNote.part <= last,
                     models.User.is_active.is_(True))
             .order_by(models.TogetherNote.part).all())
    if not ahead and not notes:
        return None
    return {"ahead": [(person.username, other.position or 0) for other, person in ahead],
            "notes": [(username, note.part) for note, username in notes], "last": last, "index": index}


def email_subject(plan, reason: dict) -> str:
    if reason["notes"]:
        author, part = reason["notes"][0]
        return f"{author} left you a note at {plan.unit} {part} of {plan.title}"[:150]
    name, position = max(reason["ahead"], key=lambda pair: pair[1])
    return f"{name} is on {plan.unit} {position} of {plan.title}"[:150]


def build_email(plan, user, people, reason: dict, unsubscribe_url: str) -> tuple[str, str, str]:
    subject = email_subject(plan, reason)
    page = _link(link_for(plan))
    first, last = week_span(plan, reason["index"])
    position = next((member.position or 0 for member, person in people if person.id == user.id), 0)
    track = []
    for member, person in people:
        at = member.position or 0
        share = round(100 * at / plan.total)
        name = "You" if person.id == user.id else person.username
        where = "not started" if at == 0 else ("finished" if at >= plan.total else f"{plan.unit} {at}")
        track.append(
            '<tr><td style="padding:6px 10px 6px 0;color:#1f1640;font-size:14px;font-weight:700;white-space:nowrap">'
            f'{escape(name)}</td><td style="padding:6px 0;width:100%">'
            '<div style="background:#ece8f8;border-radius:999px;height:10px">'
            f'<div style="background:{"#7c3aed" if person.id != user.id else "#0d9488"};border-radius:999px;height:10px;'
            f'width:{max(share, 3)}%"></div></div></td>'
            f'<td style="padding:6px 0 6px 10px;color:#5b5675;font-size:13px;white-space:nowrap">{escape(where)}</td></tr>')
    lines = []
    if reason["notes"]:
        authors = _names(sorted({author for author, _ in reason["notes"]}))
        count_notes = len(reason["notes"])
        lines.append(f"{authors} left {'a note' if count_notes == 1 else f'{count_notes} notes'} between where you are "
                     f"and the end of this week. They open when you get there.")
    if reason["ahead"]:
        lines.append(f"This week is {span_label(plan, first, last, capital=False)}. You're on "
                     f"{part_label(plan, position).lower()}.")
    paragraph = "".join(f'<p style="color:#1f1640;font-size:15px;line-height:1.6;margin:12px 0">{escape(line)}</p>'
                        for line in lines)
    company = _names([person.username for _, person in people if person.id != user.id])
    html = (
        '<html><body style="margin:0;background:#f4f2fb;font-family:Arial,Helvetica,sans-serif">'
        '<div style="max-width:560px;margin:0 auto;padding:24px">'
        '<div style="background:#1a1433;border-radius:14px 14px 0 0;padding:22px 24px;color:#fff">'
        f'<div style="font-size:12px;letter-spacing:2px;color:#99f6e4;text-transform:uppercase">{escape(verb(plan))} together</div>'
        f'<div style="font-size:22px;font-weight:700;margin-top:6px">{escape(plan.title)}</div>'
        f'<div style="font-size:14px;color:#d4d0ec;margin-top:4px">{escape(" · ".join(filter(None, [scope_label(plan), pace_label(plan), "with " + company if company else ""])))}</div>'
        '</div><div style="background:#fff;border-radius:0 0 14px 14px;padding:16px 24px 24px">'
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{"".join(track)}</table>'
        f'{paragraph}'
        f'<p style="margin:22px 0 8px"><a href="{escape(page, quote=True)}" '
        'style="background:#7c3aed;color:#fff;padding:12px 20px;border-radius:999px;text-decoration:none;font-weight:700">'
        f'Open {escape(plan.title[:60])}</a></p>'
        '<p style="color:#6f6a8a;font-size:12px;line-height:1.5;margin-top:24px">You get this at most once a week, and only '
        f'when you\'ve fallen behind {escape(company or "the others")} or a note is waiting. Turn it off on the plan page, '
        f'or <a href="{escape(unsubscribe_url, quote=True)}" style="color:#6d28d9">unsubscribe from product updates</a>.</p>'
        '</div></div></body></html>'
    )
    text = "\n".join([f"Hi {user.username},", ""] + lines + ["", f"Open {plan.title}: {page}", "",
                     "You get this at most once a week. Turn it off on the plan page, or unsubscribe from product "
                     f"updates: {unsubscribe_url}"])
    return subject, html, text


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


async def _send(to: str, subject: str, html: str, unsubscribe_url: str) -> None:
    from .digest import _send as send_mail
    await send_mail(to, subject, html, unsubscribe_url)


async def run_once(session_factory, now: Optional[datetime] = None, sender=_send) -> dict:
    """Sync places, announce new weeks, end long-quiet plans and send the weekly reminders that are due."""
    from .digest import mail_configured
    now = now or _now()
    today = now.date()
    result = {"plans": 0, "weeks": 0, "sent": 0, "failed": 0, "ended": 0, "limited": False}
    mail_ok = mail_configured() or sender is not _send
    db = session_factory()
    try:
        plans = (db.query(models.TogetherPlan).filter(models.TogetherPlan.ended_at.is_(None))
                 .order_by(models.TogetherPlan.id).limit(500).all())
        due = []
        for plan in plans:
            result["plans"] += 1
            people = rows(db, plan.id)
            if not people:
                continue
            sync(db, plan, people, today, now)
            if plan.ended_at is not None:
                db.commit()
                continue
            if week_index(plan, today) >= weeks_total(plan) + QUIET_END_WEEKS:
                plan.ended_at = now
                result["ended"] += 1
                db.commit()
                continue
            result["weeks"] += week_notices(db, plan, people, today)
            db.commit()
            for member, person in people:
                if not member.remind_email or not person.is_verified or not person.email:
                    continue
                if person.last_seen_on is not None and (today - person.last_seen_on).days < EMAIL_AWAY_DAYS:
                    continue
                reason = reminder_reason(db, plan, member, people, today)
                if reason is not None:
                    due.append((plan.id, member.id, reason))
        if not mail_ok:
            return result
        from .announcements import unsubscribe_token
        from .digest import app_url
        from .email_quota import lock_email_budget
        for plan_id, member_id, reason in due:
            if result["sent"] + result["failed"] >= PER_RUN_LIMIT:
                result["limited"] = True
                break
            plan = db.get(models.TogetherPlan, plan_id)
            member = db.get(models.TogetherMember, member_id)
            if plan is None or member is None:
                continue
            user = db.get(models.User, member.user_id)
            if user is None or not user.is_active or _opted_out(db, user.id):
                continue
            lock_email_budget(db)
            if allowance(db, now) <= 0:
                db.rollback()
                result["limited"] = True
                break
            # Claimed before anything goes out, so an overlapping run can never send a twin.
            claimed = db.query(models.TogetherMember).filter(
                models.TogetherMember.id == member.id,
                (models.TogetherMember.emailed_week.is_(None)) | (models.TogetherMember.emailed_week < reason["index"]),
            ).update({"emailed_week": reason["index"]}, synchronize_session=False)
            if not claimed:
                db.rollback()
                continue
            db.add(models.EmailCampaignSend(campaign_key=f"{SEND_PREFIX}{plan.id}-w{reason['index']}",
                                            user_id=user.id, status="sent", sent_at=now))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                continue
            try:
                people = rows(db, plan.id)
                unsubscribe_url = f"{app_url()}/email/updates/unsubscribe?token={unsubscribe_token(user.id)}"
                subject, html, _text = build_email(plan, user, people, reason, unsubscribe_url)
                await sender(user.email, subject, html, unsubscribe_url)
                result["sent"] += 1
                count("together_email_sent")
            except Exception as error:  # one bad address must not stop the rest
                print(f"Watch together email to user {user.id} failed: {error}")
                result["failed"] += 1
        return result
    finally:
        db.close()


async def together_loop(app) -> None:
    """Background task started with the app; never raises."""
    from .database import SessionLocal
    await asyncio.sleep(FIRST_CHECK_DELAY_SECONDS)
    while True:
        try:
            result = await run_once(SessionLocal)
            if result["sent"] or result["weeks"] or result["failed"] or result["ended"]:
                print(f"Watch together: {result}")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"Watch together check failed: {error}")
        await asyncio.sleep(CHECK_EVERY_SECONDS)


# ---------------------------------------------------------------- the link preview image

def card_facts(db: Session, plan) -> dict:
    people = rows(db, plan.id)
    owner = next((person.username for member, person in people if person.id == plan.owner_id), "A friend")
    return {"title": plan.title, "verb": verb(plan), "owner": owner, "label": CATEGORIES[plan.category][2],
            "scope": scope_label(plan), "pace": pace_label(plan),
            "length": f"{plan.total} {unit_words(plan)[0] if plan.total == 1 else unit_words(plan)[1]}",
            "starts": _day(plan.starts_on), "people": len(people), "ended": plan.ended_at is not None,
            "weeks": weeks_total(plan)}
