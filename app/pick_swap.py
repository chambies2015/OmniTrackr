"""Pick swap: Secret Santa where everyone gives one recommendation (Nov 2026).

A member starts a swap, names an unwrap day and shares the invite link. Friends join
(signing up first if they're new) until names are drawn, either when the host presses
the button or on the draw day. Everyone then picks one title for the person they drew,
with a note on why, and nobody sees what they got or who it came from until unwrap day.

* The draw is one loop through everyone, so nobody draws themselves and no two people
  simply trade with each other unless only two are in.
* Before unwrap day the only thing anyone learns about the picks is whether each person
  has wrapped theirs. Who drew whom is never sent to anyone else's browser.
* The person you drew is shown with their wish line and a few titles they rated highly
  from shelves they don't keep private or hidden. Picking something already on one of
  those shelves asks first.
* Someone who leaves (or is taken out, or deactivates) after the draw is stepped over:
  whoever drew them now picks for the person they drew, and is told to pick again.
* An unwrapped pick goes into the library with one tap (its "where it came from" note
  names the giver), and a reaction goes back to the giver.
* The bell (and push, under the "Pick swaps" switch) covers joins, the draw, a wrapped
  pick, the reminder two days before, unwrap day and reactions. Up to three emails per
  swap per person: who you drew, the reminder if you haven't picked, and unwrap day.

New tables only (pick_swaps, pick_swap_members, pick_swap_removals).
"""
from __future__ import annotations

import asyncio
import os
import re
import secrets
from datetime import date, datetime, time, timedelta, timezone
from html import escape
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models, title_pages

KIND_LABEL = {"movie": "Film", "tv": "TV show", "anime": "Anime", "game": "Game", "album": "Album", "book": "Book",
              "manga": "Manga", "podcast": "Podcast", "audiobook": "Audiobook"}
KIND_PLURAL = {"movie": "films", "tv": "shows", "anime": "anime", "game": "games", "album": "albums", "book": "books",
               "manga": "manga", "podcast": "podcasts", "audiobook": "audiobooks"}
THANKS = {"love": "Love it", "thanks": "Thank you", "perfect": "Perfect pick", "seen": "Already seen it"}

MEMBERS_MAX = 30
DRAW_MIN = 2
ACTIVE_MAX = 6                  # swaps one member can be in before unwrap day
NAME_MAX = 60
NOTE_MAX = 300                  # the host's rules
WISH_MAX = 160
GIFT_NOTE_MAX = 500
REVEAL_WITHIN_DAYS = 90
OPEN_HOUR = 8                   # draws and unwrap days start at 8 a.m. in the host's time zone
REMIND_DAYS = 2
SHOWN_AFTER_DAYS = 30           # an unwrapped swap stays on the home card and hub this long
STALE_DAYS = 30                 # a swap never drawn is closed this long after its unwrap day
INVITE_AGAIN_DAYS = 3
HINTS_MAX = 8
LOVED_RATING = 8
CHECK_EVERY_SECONDS = 900
FIRST_CHECK_DELAY_SECONDS = 120
PER_RUN_LIMIT = 40
SEND_PREFIX = "swap-"
UTM = "utm_source=email&utm_campaign=swap"
NOTE_TYPES = ("swap_invite", "swap_joined", "swap_short", "swap_drawn", "swap_wrapped", "swap_reminder",
              "swap_unwrap", "swap_late", "swap_added", "swap_thanks", "swap_off")

# One-tap starting points on the start form and the guide. kinds = [] means anything goes.
THEMES = (
    {"key": "anything", "name": "Holiday pick swap", "kinds": [],
     "note": "Anything you'd press into their hands: a film, a show, a book, a game, an album."},
    {"key": "comfort", "name": "Comfort watch swap", "kinds": ["movie", "tv", "anime"],
     "note": "Something you rewatch after a long week."},
    {"key": "short-books", "name": "Short book swap", "kinds": ["book", "manga"],
     "note": "A book under 300 pages, or a manga that's finished in a few volumes."},
    {"key": "weekend-games", "name": "Holiday game swap", "kinds": ["game"],
     "note": "A game you can finish over the holidays."},
    {"key": "before-they-were-born", "name": "Before you were born swap", "kinds": [],
     "note": "Something that came out before the person you drew was born."},
    {"key": "albums", "name": "Album swap", "kinds": ["album"],
     "note": "An album start to finish, not a playlist. Say which track to wait for."},
    {"key": "gateway-anime", "name": "Gateway anime swap", "kinds": ["anime", "manga"],
     "note": "The one you'd use to get a friend into anime."},
)


class SwapError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


_RANDOM = secrets.SystemRandom()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def clamp_tz(value) -> int:
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return 0
    return max(-14 * 60, min(14 * 60, minutes))


def local_today(tz: int = 0, now: Optional[datetime] = None) -> date:
    return ((now or _now()) + timedelta(minutes=clamp_tz(tz))).date()


def emails_enabled() -> bool:
    if os.getenv("PICK_SWAP_EMAILS", "").strip().lower() in ("off", "0", "false", "no"):
        return False
    return True


def loop_enabled() -> bool:
    return os.getenv("TESTING", "").lower() != "true"


def daily_limit() -> int:
    try:
        return max(0, int(os.getenv("PICK_SWAP_DAILY_LIMIT", "60")))
    except ValueError:
        return 60


def count(event: str, request=None) -> None:
    from . import funnel
    funnel.record(event, request)


# ---------------------------------------------------------------- words

def _day(value: Optional[date]) -> str:
    if value is None:
        return ""
    return f"{value.strftime('%a, %b')} {value.day}"


def _moment(day: date, tz: int) -> datetime:
    """8 a.m. on ``day`` in the host's time zone, in UTC."""
    return datetime.combine(day, time(OPEN_HOUR, 0)) - timedelta(minutes=clamp_tz(tz))


def _names(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _initials(name: str) -> str:
    letters = [part[0] for part in re.split(r"[^A-Za-z0-9]+", name or "") if part]
    return ("".join(letters[:2]) or (name or "?")[:1]).upper()


def kinds_of(swap) -> list[str]:
    return [kind for kind in (swap.kinds or "").split(",") if kind in KIND_LABEL]


def kinds_label(kinds: list[str]) -> str:
    if not kinds or len(kinds) == len(KIND_LABEL):
        return "Anything: films, shows, books, games, music and more"
    words = [KIND_PLURAL[kind] for kind in KIND_LABEL if kind in kinds]
    text = words[0] if len(words) == 1 else ", ".join(words[:-1]) + " or " + words[-1]
    return text[:1].upper() + text[1:]


def clean_line(value, limit: int) -> str:
    text = " ".join(str(value or "").split())
    # Control characters and angle brackets never make it in: names show up in emails and bell text.
    text = re.sub(r"[\x00-\x1f\x7f<>]", "", text)
    return text[:limit].strip()


def clean_text(value, limit: int) -> str:
    lines = [" ".join(line.split()) for line in str(value or "").replace("\r", "").split("\n")]
    text = "\n".join(lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[\x00-\x09\x0b-\x1f\x7f]", "", text)
    return text[:limit].strip()


def clean_kinds(values) -> list[str]:
    chosen = [kind for kind in KIND_LABEL if kind in set(values or [])]
    return [] if len(chosen) == len(KIND_LABEL) else chosen


def state_of(swap) -> str:
    if swap.cancelled_at is not None:
        return "cancelled"
    if swap.revealed_at is not None:
        return "revealed"
    if swap.drawn_at is not None:
        return "drawn"
    return "open"


def link_for(swap) -> str:
    return f"/swap/{swap.id}"


def invite_path(swap) -> str:
    return f"/swap/join/{swap.token}"


def invite_url(swap) -> str:
    from .digest import app_url
    return app_url() + invite_path(swap)


def _notify(db: Session, user_id: int, kind: str, message: str, link: str, *, once_unread: bool = False) -> None:
    if once_unread:
        waiting = db.query(models.Notification.id).filter(
            models.Notification.user_id == user_id, models.Notification.type == kind,
            models.Notification.link == link, models.Notification.read_at.is_(None)).first()
        if waiting is not None:
            return
    db.add(models.Notification(user_id=user_id, type=kind, message=message[:250], link=link))


# ---------------------------------------------------------------- people

def rows(db: Session, swap_id: int) -> list[tuple[models.PickSwapMember, models.User]]:
    """The swap's active people, in the order they joined."""
    return (db.query(models.PickSwapMember, models.User)
            .join(models.User, models.User.id == models.PickSwapMember.user_id)
            .filter(models.PickSwapMember.swap_id == swap_id, models.User.is_active.is_(True))
            .order_by(models.PickSwapMember.joined_at, models.PickSwapMember.id).all())


def by_token(db: Session, token: str) -> Optional[models.PickSwap]:
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,40}", token):
        return None
    return db.query(models.PickSwap).filter(models.PickSwap.token == token).first()


def member_of(db: Session, swap_id: int, user_id: int) -> Optional[models.PickSwapMember]:
    return db.query(models.PickSwapMember).filter_by(swap_id=swap_id, user_id=user_id).first()


def removed_from(db: Session, swap_id: int, user_id: int) -> bool:
    return db.query(models.PickSwapRemoval.id).filter_by(swap_id=swap_id, user_id=user_id).first() is not None


def active_count(db: Session, user_id: int, now: Optional[datetime] = None) -> int:
    """Swaps the member is in that haven't reached unwrap day and weren't called off."""
    return (db.query(func.count(models.PickSwapMember.id))
            .join(models.PickSwap, models.PickSwap.id == models.PickSwapMember.swap_id)
            .filter(models.PickSwapMember.user_id == user_id, models.PickSwap.cancelled_at.is_(None),
                    models.PickSwap.revealed_at.is_(None)).scalar() or 0)


def get_for_member(db: Session, swap_id: int, user, now: Optional[datetime] = None
                   ) -> tuple[models.PickSwap, models.PickSwapMember]:
    swap = db.get(models.PickSwap, swap_id)
    member = member_of(db, swap_id, user.id) if swap is not None else None
    if swap is None or member is None:
        raise SwapError("This swap isn't here, or you're not in it.", 404)
    advance(db, swap, now)
    db.refresh(member)
    return swap, member


def giver_of(db: Session, swap_id: int, user_id: int) -> Optional[models.PickSwapMember]:
    """The row of whoever drew this person."""
    return (db.query(models.PickSwapMember)
            .filter(models.PickSwapMember.swap_id == swap_id, models.PickSwapMember.gives_to == user_id,
                    models.PickSwapMember.user_id != user_id).first())


def _clear_gift(member: models.PickSwapMember) -> None:
    for field in ("gift_kind", "gift_title", "gift_year", "gift_image", "gift_slug", "gift_creator", "gift_note",
                  "picked_at", "gift_opened_at", "gift_added_at", "gift_thanks", "thanked_at"):
        setattr(member, field, None)


def _step_over(db: Session, swap, leaving: models.PickSwapMember, leaving_name: str) -> None:
    """Take someone out of the loop after the draw: whoever drew them picks for the person they drew.
    Does not commit."""
    giver = giver_of(db, swap.id, leaving.user_id)
    target = leaving.gives_to
    leaving.gives_to = None
    if giver is None:
        return
    had_pick = giver.picked_at is not None
    _clear_gift(giver)
    if target is None or target == giver.user_id:
        giver.gives_to = None
        return
    giver.gives_to = target
    receiver = db.get(models.User, target)
    name = receiver.username if receiver is not None else "someone new"
    again = " The pick you wrapped was for them, so pick again." if had_pick else ""
    _notify(db, giver.user_id, "swap_drawn",
            f"{leaving_name} left {swap.name}, so you're picking for {name} now.{again}", link_for(swap))


def _hand_over(db: Session, swap, leaving_user_id: int) -> bool:
    """Give the swap to the person who joined first after the host. False when nobody is left."""
    people = [person for _member, person in rows(db, swap.id) if person.id != leaving_user_id]
    if not people:
        return False
    swap.owner_id = people[0].id
    _notify(db, people[0].id, "swap_joined", f"You're running {swap.name} now.", link_for(swap))
    return True


def _call_off_if_alone(db: Session, swap, now: datetime) -> None:
    """After the draw a swap needs two people. Does not commit."""
    if state_of(swap) != "drawn":
        return
    people = rows(db, swap.id)
    in_draw = [(member, person) for member, person in people if member.gives_to]
    if len(in_draw) >= 2:
        return
    swap.cancelled_at = now
    swap.updated_at = now
    for _member, person in people:
        _notify(db, person.id, "swap_off", f"{swap.name} is off: everyone else left before unwrap day.", "/swap")


def settle(db: Session, swap, now: Optional[datetime] = None) -> bool:
    """Step over people whose accounts were deactivated, and hand the swap on if the host's was.
    Returns True when something changed. Does not commit."""
    now = now or _now()
    if state_of(swap) in ("cancelled", "revealed"):
        return False
    gone = (db.query(models.PickSwapMember, models.User.username)
            .join(models.User, models.User.id == models.PickSwapMember.user_id)
            .filter(models.PickSwapMember.swap_id == swap.id, models.User.is_active.is_(False)).all())
    changed = False
    for member, username in gone:
        if state_of(swap) == "drawn" and (member.gives_to or giver_of(db, swap.id, member.user_id) is not None):
            _step_over(db, swap, member, username)
            changed = True
        if member.user_id == swap.owner_id:
            if not _hand_over(db, swap, member.user_id):
                swap.cancelled_at = now
            changed = True
    if changed:
        db.flush()
        _call_off_if_alone(db, swap, now)
    return changed


# ---------------------------------------------------------------- making and joining

def _dates(today: date, draw_on: Optional[date], reveal_on: date) -> None:
    if reveal_on <= today:
        raise SwapError("Pick an unwrap day after today.", 422)
    if reveal_on > today + timedelta(days=REVEAL_WITHIN_DAYS):
        raise SwapError(f"Pick an unwrap day within {REVEAL_WITHIN_DAYS} days.", 422)
    if draw_on is not None and (draw_on < today or draw_on >= reveal_on):
        raise SwapError("The draw has to be today or later, and before unwrap day.", 422)


def create(db: Session, user, *, name: str, note: Optional[str], kinds: list[str], draw_on: Optional[date],
           reveal_on: date, tz: int, wish: Optional[str], today: date, now: Optional[datetime] = None
           ) -> models.PickSwap:
    """Start a swap with the host in it. Does not commit."""
    now = now or _now()
    if active_count(db, user.id) >= ACTIVE_MAX:
        raise SwapError(f"You're in {ACTIVE_MAX} swaps already. Wait for one to unwrap, or leave one.", 409)
    name = clean_line(name, NAME_MAX)
    if len(name) < 2:
        raise SwapError("Give the swap a name, like \"Office swap\" or \"Family picks\".", 422)
    _dates(today, draw_on, reveal_on)
    tz = clamp_tz(tz)
    swap = models.PickSwap(owner_id=user.id, token=secrets.token_urlsafe(16), name=name,
                           note=clean_text(note, NOTE_MAX) or None, kinds=",".join(clean_kinds(kinds)), tz=tz,
                           draw_on=draw_on, draw_at=_moment(draw_on, tz) if draw_on else None,
                           reveal_on=reveal_on, reveal_at=_moment(reveal_on, tz), created_at=now, updated_at=now)
    db.add(swap)
    db.flush()
    db.add(models.PickSwapMember(swap_id=swap.id, user_id=user.id, joined_at=now,
                                 wish=clean_line(wish, WISH_MAX) or None))
    db.flush()
    return swap


def update(db: Session, swap, user, *, name=None, note=None, kinds=None, draw_on=None, clear_draw: bool = False,
           reveal_on=None, today: date, now: Optional[datetime] = None) -> None:
    """The host changes the name, rules or dates. Formats and the draw day only before the draw. Commits."""
    now = now or _now()
    if swap.owner_id != user.id:
        raise SwapError("Only the host can change the swap.", 403)
    current = state_of(swap)
    if current in ("revealed", "cancelled"):
        raise SwapError("This swap is over, so it can't change now.", 409)
    if name is not None:
        cleaned = clean_line(name, NAME_MAX)
        if len(cleaned) < 2:
            raise SwapError("Give the swap a name.", 422)
        swap.name = cleaned
    if note is not None:
        swap.note = clean_text(note, NOTE_MAX) or None
    if kinds is not None:
        if current != "open":
            raise SwapError("Names are drawn, so the formats stay as they are.", 409)
        swap.kinds = ",".join(clean_kinds(kinds))
    new_draw = swap.draw_on
    if clear_draw or draw_on is not None:
        if current != "open":
            raise SwapError("Names are drawn already.", 409)
        new_draw = None if clear_draw else draw_on
    new_reveal = reveal_on or swap.reveal_on
    if new_draw != swap.draw_on or new_reveal != swap.reveal_on:
        if new_reveal != swap.reveal_on or new_draw is not None:
            _dates(today, new_draw if current == "open" else None, new_reveal)
        if new_draw != swap.draw_on:
            swap.draw_on = new_draw
            swap.draw_at = _moment(new_draw, swap.tz) if new_draw else None
            swap.short_at = None
        if new_reveal != swap.reveal_on:
            later = new_reveal > swap.reveal_on
            swap.reveal_on = new_reveal
            swap.reveal_at = _moment(new_reveal, swap.tz)
            if later:
                swap.reminded_at = None
            if current == "drawn":
                for member, person in rows(db, swap.id):
                    if person.id != user.id:
                        _notify(db, person.id, "swap_drawn",
                                f"Unwrap day for {swap.name} is now {_day(new_reveal)}.", link_for(swap))
    swap.updated_at = now
    db.commit()


def invite_friends(db: Session, swap, user, friend_ids: list[int], now: Optional[datetime] = None) -> int:
    """Ask friends in from the friends list. Does not commit."""
    from .crud.friends import are_friends
    now = now or _now()
    if state_of(swap) != "open" or len(rows(db, swap.id)) >= MEMBERS_MAX:
        return 0
    inside = {user_id for user_id, in db.query(models.PickSwapMember.user_id).filter_by(swap_id=swap.id)}
    host = swap.owner_id == user.id
    asked = 0
    for friend_id in dict.fromkeys(friend_ids or []):
        if friend_id == user.id or friend_id in inside or not are_friends(db, user.id, friend_id):
            continue
        removal = db.query(models.PickSwapRemoval).filter_by(swap_id=swap.id, user_id=friend_id).first()
        if removal is not None and not host:
            continue
        recent = None if removal is not None else db.query(models.Notification.id).filter(
            models.Notification.user_id == friend_id, models.Notification.type == "swap_invite",
            models.Notification.link == invite_path(swap),
            or_(models.Notification.read_at.is_(None),
                models.Notification.created_at >= now - timedelta(days=INVITE_AGAIN_DAYS))).first()
        if recent is not None:
            continue
        if removal is not None:
            db.delete(removal)
        _notify(db, friend_id, "swap_invite",
                f"{user.username} asked you into {swap.name}, a pick swap. Unwrap day is {_day(swap.reveal_on)}.",
                invite_path(swap))
        asked += 1
    return asked


REMOVED_MESSAGE = "The host took you out of this swap, so this link won't add you back. They can ask you in again."


def join(db: Session, swap, user, *, wish: Optional[str] = None, now: Optional[datetime] = None
         ) -> tuple[models.PickSwapMember, bool]:
    """Join with the link. Returns (member, newly joined). Commits."""
    now = now or _now()
    existing = member_of(db, swap.id, user.id)
    if existing is not None:
        return existing, False
    current = state_of(swap)
    if current == "cancelled":
        raise SwapError("This swap was called off.", 409)
    if current != "open":
        raise SwapError("Names have been drawn for this swap, so it's closed to new people. Start your own, "
                        "it takes a minute.", 409)
    if removed_from(db, swap.id, user.id):
        raise SwapError(REMOVED_MESSAGE, 403)
    people = rows(db, swap.id)
    if len(people) >= MEMBERS_MAX:
        raise SwapError(f"This swap is full: {MEMBERS_MAX} people is the most.", 409)
    if active_count(db, user.id) >= ACTIVE_MAX:
        raise SwapError(f"You're in {ACTIVE_MAX} swaps already. Wait for one to unwrap, or leave one.", 409)
    member = models.PickSwapMember(swap_id=swap.id, user_id=user.id, joined_at=now,
                                   wish=clean_line(wish, WISH_MAX) or None)
    db.add(member)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        found = member_of(db, swap.id, user.id)
        if found is None:
            raise SwapError("That didn't work. Please try again.", 409)
        return found, False
    total = len(people) + 1
    if swap.owner_id != user.id:
        _notify(db, swap.owner_id, "swap_joined",
                f"{user.username} joined {swap.name}. That's {total} people in.", link_for(swap))
    db.query(models.Notification).filter(
        models.Notification.user_id == user.id, models.Notification.type == "swap_invite",
        models.Notification.link == invite_path(swap), models.Notification.read_at.is_(None),
    ).update({"read_at": now}, synchronize_session=False)
    swap.updated_at = now
    db.commit()
    count("swap_joined")
    return member, True


def set_wish(db: Session, swap, member, wish) -> None:
    if state_of(swap) in ("revealed", "cancelled"):
        raise SwapError("This swap is over.", 409)
    member.wish = clean_line(wish, WISH_MAX) or None
    db.commit()


def leave(db: Session, swap, member, user, now: Optional[datetime] = None) -> bool:
    """Leave before unwrap day. Returns True when the swap carries on. Commits."""
    now = now or _now()
    current = state_of(swap)
    if current == "revealed":
        raise SwapError("This swap has been unwrapped already.", 409)
    if current == "drawn":
        _step_over(db, swap, member, user.username)
    kept = True
    if swap.owner_id == user.id and current != "cancelled":
        kept = _hand_over(db, swap, user.id)
        if not kept:
            swap.cancelled_at = now
    db.delete(member)
    db.flush()
    if kept:
        _call_off_if_alone(db, swap, now)
        kept = swap.cancelled_at is None
    swap.updated_at = now
    db.commit()
    return kept


def remove(db: Session, swap, owner, member_id: int, now: Optional[datetime] = None) -> None:
    """The host takes someone out. The link won't add them back. Commits."""
    now = now or _now()
    if swap.owner_id != owner.id:
        raise SwapError("Only the host can take people out.", 403)
    if state_of(swap) in ("revealed", "cancelled"):
        raise SwapError("This swap is over.", 409)
    member = db.query(models.PickSwapMember).filter_by(id=member_id, swap_id=swap.id).first()
    if member is None:
        raise SwapError("They're not in this swap.", 404)
    if member.user_id == owner.id:
        raise SwapError("You can't take yourself out. Leave the swap instead.", 400)
    person = db.get(models.User, member.user_id)
    if state_of(swap) == "drawn":
        _step_over(db, swap, member, person.username if person is not None else "Someone")
    if not removed_from(db, swap.id, member.user_id):
        db.add(models.PickSwapRemoval(swap_id=swap.id, user_id=member.user_id, created_at=now))
    db.delete(member)
    db.flush()
    _call_off_if_alone(db, swap, now)
    swap.updated_at = now
    db.commit()


def cancel(db: Session, swap, user, now: Optional[datetime] = None) -> None:
    now = now or _now()
    if swap.owner_id != user.id:
        raise SwapError("Only the host can call it off.", 403)
    if state_of(swap) in ("revealed", "cancelled"):
        raise SwapError("This swap is over already.", 409)
    swap.cancelled_at = now
    swap.updated_at = now
    for _member, person in rows(db, swap.id):
        if person.id != user.id:
            _notify(db, person.id, "swap_off", f"{user.username} called off {swap.name}.", "/swap")
    db.commit()


def new_link(db: Session, swap, user) -> str:
    if swap.owner_id != user.id:
        raise SwapError("Only the host can make a new link.", 403)
    swap.token = secrets.token_urlsafe(16)
    db.commit()
    return invite_url(swap)


# ---------------------------------------------------------------- the draw and unwrap day

def draw(db: Session, swap, now: Optional[datetime] = None) -> bool:
    """Draw names: one loop through everyone. Returns False when someone else got there first. Commits."""
    now = now or _now()
    if state_of(swap) != "open":
        raise SwapError("Names are drawn already." if swap.drawn_at else "This swap is over.", 409)
    people = rows(db, swap.id)
    if len(people) < DRAW_MIN:
        raise SwapError(f"You need at least {DRAW_MIN} people to draw names. Send the link to a few friends.", 409)
    if now >= swap.reveal_at - timedelta(hours=12):
        raise SwapError("Unwrap day is too close to draw names now. Move it a few days later first.", 409)
    claimed = db.query(models.PickSwap).filter(
        models.PickSwap.id == swap.id, models.PickSwap.drawn_at.is_(None), models.PickSwap.cancelled_at.is_(None),
    ).update({"drawn_at": now, "updated_at": now}, synchronize_session=False)
    if not claimed:
        db.rollback()
        return False
    order = list(people)
    _RANDOM.shuffle(order)
    for index, (member, person) in enumerate(order):
        receiver = order[(index + 1) % len(order)][1]
        member.gives_to = receiver.id
        _notify(db, person.id, "swap_drawn",
                f"Names are drawn in {swap.name}: you're picking for {receiver.username}. "
                f"Unwrap day is {_day(swap.reveal_on)}.", link_for(swap))
    db.commit()
    db.refresh(swap)
    count("swap_drawn")
    return True


def everyone_picked(db: Session, swap) -> bool:
    givers = [member for member, _person in rows(db, swap.id) if member.gives_to]
    return bool(givers) and all(member.picked_at for member in givers)


def reveal(db: Session, swap, now: Optional[datetime] = None, *, early_by=None) -> bool:
    """Open every pick. The host can do it early once everyone has wrapped one. Commits."""
    now = now or _now()
    if state_of(swap) != "drawn":
        raise SwapError("Names haven't been drawn yet." if swap.drawn_at is None else "This swap is unwrapped already.",
                        409)
    if early_by is not None:
        if swap.owner_id != early_by.id:
            raise SwapError("Only the host can open the picks early.", 403)
        if not everyone_picked(db, swap):
            raise SwapError("Wait until everyone has wrapped a pick, or let unwrap day come.", 409)
    claimed = db.query(models.PickSwap).filter(
        models.PickSwap.id == swap.id, models.PickSwap.revealed_at.is_(None), models.PickSwap.cancelled_at.is_(None),
    ).update({"revealed_at": now, "updated_at": now}, synchronize_session=False)
    if not claimed:
        db.rollback()
        return False
    people = rows(db, swap.id)
    names = {person.id: person.username for _member, person in people}
    for member, person in people:
        if not member.gives_to or member.gives_to not in names:
            continue
        if member.picked_at:
            _notify(db, member.gives_to, "swap_unwrap",
                    f"It's unwrap day in {swap.name}. Your pick from {person.username} is ready.", link_for(swap))
        else:
            _notify(db, member.gives_to, "swap_unwrap",
                    f"It's unwrap day in {swap.name}. {person.username} is still wrapping your pick.", link_for(swap))
            _notify(db, person.id, "swap_late",
                    f"It's unwrap day in {swap.name} and {names[member.gives_to]} is waiting on your pick.",
                    link_for(swap))
    db.commit()
    db.refresh(swap)
    count("swap_revealed")
    return True


def remind(db: Session, swap, now: Optional[datetime] = None) -> int:
    """Two days before unwrap day, a nudge to everyone who hasn't picked. Commits."""
    now = now or _now()
    claimed = db.query(models.PickSwap).filter(
        models.PickSwap.id == swap.id, models.PickSwap.reminded_at.is_(None)).update(
        {"reminded_at": now}, synchronize_session=False)
    if not claimed:
        db.rollback()
        return 0
    people = rows(db, swap.id)
    names = {person.id: person.username for _member, person in people}
    sent = 0
    for member, person in people:
        if member.gives_to and not member.picked_at and member.gives_to in names:
            _notify(db, person.id, "swap_reminder",
                    f"Unwrap day in {swap.name} is {_day(swap.reveal_on)}. You haven't wrapped a pick for "
                    f"{names[member.gives_to]} yet.", link_for(swap))
            sent += 1
    db.commit()
    db.refresh(swap)
    return sent


def advance(db: Session, swap, now: Optional[datetime] = None) -> dict:
    """Do whatever the clock says is due: step over deactivated accounts, draw on the draw day,
    remind two days out, and open everything on unwrap day."""
    now = now or _now()
    done = {"drawn": False, "revealed": False, "reminded": 0, "short": False}
    if settle(db, swap, now):
        db.commit()
    current = state_of(swap)
    if current == "open" and now >= swap.reveal_at + timedelta(days=STALE_DAYS):
        # Never drawn, and unwrap day is long gone: nobody is coming back to it.
        db.query(models.PickSwap).filter(
            models.PickSwap.id == swap.id, models.PickSwap.drawn_at.is_(None),
            models.PickSwap.cancelled_at.is_(None)).update({"cancelled_at": now}, synchronize_session=False)
        db.commit()
        db.refresh(swap)
        return done
    if current == "open" and swap.draw_at is not None and now >= swap.draw_at:
        if len(rows(db, swap.id)) >= DRAW_MIN:
            try:
                done["drawn"] = draw(db, swap, now)
            except SwapError:
                db.rollback()
        elif swap.short_at is None:
            swap.short_at = now
            _notify(db, swap.owner_id, "swap_short",
                    f"It's draw day for {swap.name}, but you're the only one in. Send the link to friends and "
                    "draw when they've joined.", link_for(swap))
            db.commit()
            done["short"] = True
    current = state_of(swap)
    if current == "drawn":
        if now >= swap.reveal_at:
            try:
                done["revealed"] = reveal(db, swap, now)
            except SwapError:
                db.rollback()
        elif swap.reminded_at is None and now >= swap.reveal_at - timedelta(days=REMIND_DAYS):
            done["reminded"] = remind(db, swap, now)
    return done


# ---------------------------------------------------------------- picks

def _shelf_ok(user, kind: str) -> bool:
    from .ranking_shares import _shareable
    return _shareable(user, title_pages.KINDS[kind][2])


def recipient_has(db: Session, receiver, kind: str, title: str) -> bool:
    """True when the title is on one of the person's shelves that isn't private or hidden."""
    if kind not in title_pages.KINDS or not _shelf_ok(receiver, kind):
        return False
    model = title_pages.KINDS[kind][0]
    normalized = title_pages.normalize(title)
    return db.query(model.id).filter(model.user_id == receiver.id,
                                     func.lower(func.trim(model.title)) == normalized).first() is not None


def hints(db: Session, receiver, kinds: list[str]) -> list[dict]:
    """A few titles the person rated highly, from shelves they don't keep private or hidden."""
    found = []
    for kind, (model, _review, _category, _label, _creator) in title_pages.KINDS.items():
        if kinds and kind not in kinds:
            continue
        if not _shelf_ok(receiver, kind):
            continue
        image_field = getattr(model, title_pages.IMAGE_FIELD[kind])
        picked = (db.query(model.title, image_field, model.rating)
                  .filter(model.user_id == receiver.id, model.rating >= LOVED_RATING)
                  .order_by(model.rating.desc(), model.id.desc()).limit(HINTS_MAX).all())
        for title, image, rating in picked:
            if not (title or "").strip():
                continue
            found.append({"title": title.strip()[:200], "kind": kind, "label": KIND_LABEL[kind],
                          "image": title_pages._safe_image(image) if (image or "").startswith("https://") else None,
                          "rating": round(float(rating), 1)})
    found.sort(key=lambda item: -item["rating"])
    return found[:HINTS_MAX]


def gift_of(member) -> Optional[dict]:
    if member is None or not member.picked_at:
        return None
    slug = member.gift_slug if member.gift_slug and re.fullmatch(r"[a-z0-9-]{1,140}", member.gift_slug) else None
    return {"kind": member.gift_kind, "label": KIND_LABEL.get(member.gift_kind, "Title"), "title": member.gift_title,
            "year": member.gift_year, "image": member.gift_image, "creator": member.gift_creator or "",
            "note": member.gift_note or "", "url": f"/titles/{member.gift_kind}/{slug}" if slug else None}


def set_gift(db: Session, swap, member, user, *, kind: str, title: str, year: Optional[int] = None,
             image: Optional[str] = None, slug: Optional[str] = None, creator: Optional[str] = None,
             note: Optional[str] = None, anyway: bool = False, now: Optional[datetime] = None) -> dict:
    """Wrap a pick for the person this member drew. Commits when it saves."""
    now = now or _now()
    current = state_of(swap)
    if current == "open":
        raise SwapError("Names haven't been drawn yet.", 409)
    if current == "cancelled":
        raise SwapError("This swap was called off.", 409)
    if not member.gives_to:
        raise SwapError("You weren't in the draw for this swap.", 409)
    if current == "revealed" and member.picked_at:
        raise SwapError("Your pick has been unwrapped, so it stays as it is.", 409)
    if kind not in KIND_LABEL:
        raise SwapError("Pick a film, show, anime, game, album, book, manga, podcast or audiobook.", 422)
    allowed = kinds_of(swap)
    if allowed and kind not in allowed:
        raise SwapError(f"This swap is for {kinds_label(allowed).lower()}.", 422)
    title = clean_line(title, 200)
    if not title:
        raise SwapError("Pick a title first.", 422)
    receiver = db.get(models.User, member.gives_to)
    if receiver is None or not receiver.is_active:
        raise SwapError("The person you drew isn't here anymore. Reload the page.", 409)
    if not anyway and recipient_has(db, receiver, kind, title):
        return {"saved": False, "has_it": True,
                "message": f"{receiver.username} already has {title} in their library. Pick something else, "
                           "or wrap it anyway."}
    first = member.picked_at is None
    member.gift_kind = kind
    member.gift_title = title
    member.gift_year = year if isinstance(year, int) and 1800 <= year <= 2100 else None
    member.gift_image = image if isinstance(image, str) and image.startswith("https://") and len(image) <= 500 else None
    member.gift_slug = slug if isinstance(slug, str) and re.fullmatch(r"[a-z0-9-]{1,140}", slug) else None
    member.gift_creator = clean_line(creator, 200) or None
    member.gift_note = clean_text(note, GIFT_NOTE_MAX) or None
    if first:
        member.picked_at = now
        if current == "revealed":
            _notify(db, receiver.id, "swap_unwrap",
                    f"Your pick from {user.username} in {swap.name} just arrived.", link_for(swap))
        else:
            _notify(db, receiver.id, "swap_wrapped",
                    f"Someone in {swap.name} wrapped a pick for you. It opens on {_day(swap.reveal_on)}.",
                    link_for(swap), once_unread=True)
    db.commit()
    if first:
        count("swap_picked")
    return {"saved": True, "has_it": False, "first": first}


def clear_gift(db: Session, swap, member) -> None:
    if state_of(swap) != "drawn":
        raise SwapError("You can only take a pick back before unwrap day.", 409)
    _clear_gift(member)
    db.commit()


def open_gift(db: Session, swap, user, now: Optional[datetime] = None) -> bool:
    """The person who drew this member gets told nothing; the row just remembers it was opened."""
    now = now or _now()
    if state_of(swap) != "revealed":
        raise SwapError("It isn't unwrap day yet.", 409)
    giver = giver_of(db, swap.id, user.id)
    if giver is None or not giver.picked_at:
        raise SwapError("Your pick isn't here yet.", 409)
    first = giver.gift_opened_at is None
    if first:
        giver.gift_opened_at = now
        db.commit()
        count("swap_unwrapped")
    return first


def add_gift(db: Session, swap, user, *, queue: bool = False, now: Optional[datetime] = None) -> dict:
    """Put the pick in the library (and Up next when asked). Tells the giver once. Commits."""
    from . import title_origins
    from .crud.friends import are_friends
    from .pick import add_to_library
    from .progress import lock_progress_owner
    from .routers.next_up import enqueue
    now = now or _now()
    if state_of(swap) != "revealed":
        raise SwapError("It isn't unwrap day yet.", 409)
    giver = giver_of(db, swap.id, user.id)
    if giver is None or not giver.picked_at or giver.gift_kind not in title_pages.KINDS:
        raise SwapError("Your pick isn't here yet.", 409)
    giver_user = db.get(models.User, giver.user_id)
    lock_progress_owner(db, user.id)
    state, row = add_to_library(db, user, {"kind": giver.gift_kind, "title": giver.gift_title,
                                           "year": giver.gift_year, "creator": giver.gift_creator},
                                image=giver.gift_image)
    category = title_pages.KINDS[giver.gift_kind][2]
    if state == "created" and giver_user is not None:
        note = f"Pick swap: {swap.name}"
        if giver_user.is_active and are_friends(db, user.id, giver_user.id):
            title_origins.prefill(db, user.id, category, row.id, "friend", friend=giver_user, note=note)
        elif title_origins.get(db, user.id, category, row.id) is None:
            db.add(models.TitleOrigin(user_id=user.id, category=category, item_id=row.id, source="person",
                                      who=giver_user.username[:title_origins.WHO_MAX],
                                      who_key=title_origins.who_key(giver_user.username), note=note,
                                      created_at=now, updated_at=now))
    queued = False
    if queue and not getattr(row, title_pages.COMPLETE_FIELD[giver.gift_kind], False):
        queued = enqueue(db, user.id, category, row.id)
    first = giver.gift_added_at is None
    if first:
        giver.gift_added_at = now
        if giver_user is not None and giver_user.is_active:
            where = "Up next" if queued else "library"
            _notify(db, giver_user.id, "swap_added",
                    f"{user.username} put your pick, {giver.gift_title}, in their {where}.", link_for(swap))
    db.commit()
    if first:
        count("swap_gift_added")
    return {"created": state == "created", "queued": queued, "category": category, "item_id": row.id}


def thank(db: Session, swap, user, reaction: str, now: Optional[datetime] = None) -> None:
    now = now or _now()
    if reaction not in THANKS:
        raise SwapError("Pick one of the reactions.", 422)
    if state_of(swap) != "revealed":
        raise SwapError("It isn't unwrap day yet.", 409)
    giver = giver_of(db, swap.id, user.id)
    if giver is None or not giver.picked_at:
        raise SwapError("Your pick isn't here yet.", 409)
    first = giver.thanked_at is None
    giver.gift_thanks = reaction
    if first:
        giver.thanked_at = now
        _notify(db, giver.user_id, "swap_thanks",
                f"{user.username} on your pick, {giver.gift_title}: \"{THANKS[reaction]}\"", link_for(swap))
    db.commit()


# ---------------------------------------------------------------- what pages show

def _days_until(day: date, today: date) -> int:
    return (day - today).days


def _left_words(days: int) -> str:
    if days <= 0:
        return "today"
    if days == 1:
        return "1 day left"
    return f"{days} days left"


def preview(db: Session, swap, today: date) -> dict:
    """What the invite page shows anyone with the link: names, dates and the rules. No picks."""
    people = rows(db, swap.id)
    owner = next((person.username for _member, person in people if person.id == swap.owner_id), None)
    return {
        "name": swap.name, "note": swap.note or "", "owner": owner, "people": [p.username for _m, p in people],
        "count": len(people), "kinds": kinds_of(swap), "kinds_label": kinds_label(kinds_of(swap)),
        "draw_label": _day(swap.draw_on) if swap.draw_on else "", "reveal_label": _day(swap.reveal_on),
        "reveal_on": swap.reveal_on.isoformat(), "state": state_of(swap), "full": len(people) >= MEMBERS_MAX,
        "days": _days_until(swap.reveal_on, today),
    }


def detail(db: Session, swap, me, viewer, today: date, now: Optional[datetime] = None) -> dict:
    """Everything one person in the swap may see. Before unwrap day that never includes who drew
    whom (apart from their own draw) or what anyone wrapped for them."""
    current = state_of(swap)
    people = rows(db, swap.id)
    names = {person.id: person.username for _member, person in people}
    wishes = {person.id: member.wish or "" for member, person in people}
    kinds = kinds_of(swap)
    drawn = current in ("drawn", "revealed")
    givers = [member for member, _person in people if member.gives_to]
    out_people = []
    for member, person in people:
        out_people.append({
            "id": member.id, "username": person.username, "initials": _initials(person.username),
            "you": person.id == viewer.id, "host": person.id == swap.owner_id, "wish": member.wish or "",
            "in_draw": bool(member.gives_to) if drawn else None,
            "wrapped": bool(member.picked_at) if drawn and member.gives_to else None,
        })
    data = {
        "id": swap.id, "name": swap.name, "note": swap.note or "", "state": current, "kinds": kinds,
        "kinds_label": kinds_label(kinds), "host": viewer.id == swap.owner_id,
        "owner": names.get(swap.owner_id, ""),
        "draw_on": swap.draw_on.isoformat() if swap.draw_on else None,
        "draw_label": _day(swap.draw_on) if swap.draw_on else "",
        "reveal_on": swap.reveal_on.isoformat(), "reveal_label": _day(swap.reveal_on),
        "days": _days_until(swap.reveal_on, today), "people": out_people, "count": len(people),
        "min": DRAW_MIN, "max": MEMBERS_MAX,
        "wrapped": sum(1 for member in givers if member.picked_at), "givers": len(givers),
        "invite_url": invite_url(swap) if current == "open" else None,
        "invite_path": invite_path(swap) if current == "open" else None,
        "can_draw": viewer.id == swap.owner_id and current == "open" and len(people) >= DRAW_MIN,
        "can_unwrap": viewer.id == swap.owner_id and current == "drawn" and everyone_picked(db, swap),
        "thanks": [{"key": key, "label": label} for key, label in THANKS.items()],
        "me": {"member_id": me.id, "wish": me.wish or "", "in_draw": bool(me.gives_to)},
    }
    if drawn and me.gives_to and me.gives_to in names:
        receiver = db.get(models.User, me.gives_to)
        data["me"]["gives_to"] = {
            "username": names[me.gives_to], "initials": _initials(names[me.gives_to]),
            "wish": wishes.get(me.gives_to, ""),
            "hints": hints(db, receiver, kinds) if current == "drawn" and receiver is not None else [],
        }
        data["me"]["gift"] = gift_of(me)
    if current == "revealed":
        giver = giver_of(db, swap.id, viewer.id)
        if giver is not None and giver.user_id in names:
            received = gift_of(giver)
            data["me"]["received"] = ({**received, "from": names[giver.user_id], "opened": giver.gift_opened_at is not None,
                                       "added": giver.gift_added_at is not None, "thanks": giver.gift_thanks}
                                      if received else {"from": names[giver.user_id], "pending": True})
        board = []
        for member, person in people:
            gift = gift_of(member)
            if not member.gives_to or member.gives_to not in names:
                continue
            board.append({"from": person.username, "to": names[member.gives_to], "from_you": person.id == viewer.id,
                          "to_you": member.gives_to == viewer.id, "gift": gift,
                          "thanks": THANKS.get(member.gift_thanks or "", "")})
        data["board"] = board
    return data


def _line(db: Session, swap, member, today: date) -> dict:
    """One swap on the home card and the hub: where it stands for this member and the next thing to do."""
    current = state_of(swap)
    path = link_for(swap)
    days = _days_until(swap.reveal_on, today)
    people = rows(db, swap.id)
    total = len(people)
    names = {person.id: person.username for _m, person in people}
    item = {"id": swap.id, "name": swap.name, "path": path, "state": current, "count": total,
            "reveal_label": _day(swap.reveal_on), "days": days, "urgent": False, "action": None,
            "host": swap.owner_id == member.user_id}
    if current == "open":
        if days <= 0:
            item["line"] = ("Unwrap day came before the draw. Pick a new day and draw names."
                            if item["host"] else "Unwrap day came before the draw. The host can pick a new day.")
        elif total < DRAW_MIN:
            item["line"] = "Just you so far. Send the link to the people you want in."
        elif swap.draw_on:
            item["line"] = f"{total} people in · names drawn {_day(swap.draw_on)}"
        else:
            item["line"] = f"{total} people in · {'you draw' if item['host'] else 'the host draws'} names"
        item["action"] = {"label": "Invite people" if total < DRAW_MIN else "Open the swap", "path": path}
    elif current == "drawn":
        target = names.get(member.gives_to)
        if target and not member.picked_at:
            item["line"] = f"Pick something for {target} · {_left_words(days)}"
            item["action"] = {"label": f"Pick for {target}", "path": path}
            item["urgent"] = True
        elif target:
            mine = giver_of(db, swap.id, member.user_id)
            yours = " · yours is wrapped too" if mine is not None and mine.picked_at else ""
            item["line"] = f"You wrapped {member.gift_title} for {target}{yours}"
            item["action"] = {"label": f"Unwrap day: {_day(swap.reveal_on)}", "path": path}
        else:
            item["line"] = f"Names are drawn · unwrap day {_day(swap.reveal_on)}"
            item["action"] = {"label": "Open the swap", "path": path}
    elif current == "revealed":
        giver = giver_of(db, swap.id, member.user_id)
        if giver is not None and giver.picked_at and giver.gift_opened_at is None:
            item["line"] = f"Your pick from {names.get(giver.user_id, 'your Secret Santa')} is ready"
            item["action"] = {"label": "Unwrap it", "path": path}
            item["urgent"] = True
        elif giver is not None and giver.picked_at:
            item["line"] = f"From {names.get(giver.user_id, 'your Secret Santa')}: {giver.gift_title}"
            item["action"] = {"label": "See every pick", "path": path}
        else:
            item["line"] = "Unwrapped · your pick is still on its way"
            item["action"] = {"label": "See every pick", "path": path}
        if member.gives_to and not member.picked_at and member.gives_to in names:
            item["line"] = f"{names[member.gives_to]} is waiting on your pick"
            item["action"] = {"label": f"Pick for {names[member.gives_to]}", "path": path}
            item["urgent"] = True
    return item


def mine(db: Session, user, today: date, now: Optional[datetime] = None) -> dict:
    now = now or _now()
    found = (db.query(models.PickSwapMember, models.PickSwap)
             .join(models.PickSwap, models.PickSwap.id == models.PickSwapMember.swap_id)
             .filter(models.PickSwapMember.user_id == user.id, models.PickSwap.cancelled_at.is_(None),
                     or_(models.PickSwap.revealed_at.is_(None),
                         models.PickSwap.revealed_at >= now - timedelta(days=SHOWN_AFTER_DAYS)))
             .order_by(models.PickSwap.reveal_on, models.PickSwap.id).limit(ACTIVE_MAX + 10).all())
    swaps = []
    for member, swap in found:
        advance(db, swap, now)
        if swap.cancelled_at is not None:
            continue
        db.refresh(member)
        swaps.append(_line(db, swap, member, today))
    swaps.sort(key=lambda item: (not item["urgent"], item["state"] == "revealed", item["days"]))
    return {"swaps": swaps, "active": active_count(db, user.id), "active_max": ACTIVE_MAX}


def card_facts(db: Session, swap) -> dict:
    people = rows(db, swap.id)
    owner = next((person.username for _member, person in people if person.id == swap.owner_id), "A friend")
    return {"name": swap.name, "owner": owner, "people": len(people), "reveal": _day(swap.reveal_on),
            "kinds": kinds_label(kinds_of(swap)), "state": state_of(swap),
            "draw": _day(swap.draw_on) if swap.draw_on else ""}


# ---------------------------------------------------------------- email

def _link(path: str) -> str:
    from .digest import app_url
    joiner = "&" if "?" in path else "?"
    return f"{app_url()}{path}{joiner}{UTM}"


def email_subject(kind: str, swap, other: str) -> str:
    if kind == "drawn":
        return f"You're picking for {other} in {swap.name}"[:150]
    if kind == "remind":
        return f"{_day(swap.reveal_on)} is unwrap day. Still time to pick for {other}"[:150]
    return f"Your pick from {other} is ready to unwrap"[:150]


def build_email(kind: str, swap, user, other: str, wish: str, unsubscribe_url: str) -> tuple[str, str, str]:
    """(subject, html, text). ``other`` is the person they drew, or for unwrap day the one who drew them."""
    subject = email_subject(kind, swap, other)
    page = _link(link_for(swap))
    if kind == "drawn":
        lines = [f"Names are drawn in {swap.name}. You're picking one thing for {other}.",
                 f"Unwrap day is {_day(swap.reveal_on)}. Until then nobody sees what you picked, or who picked for them."]
        if wish:
            lines.insert(1, f"{other} asked for: \"{wish}\"")
        button = f"Pick something for {other}"
    elif kind == "remind":
        lines = [f"Unwrap day in {swap.name} is {_day(swap.reveal_on)}, and you haven't wrapped a pick for {other} yet.",
                 "It takes a minute: find a title, add a line on why, and it waits there until unwrap day."]
        button = f"Pick for {other}"
    else:
        lines = [f"It's unwrap day in {swap.name}. {other} picked something for you, with a note on why.",
                 "Open it, add it to your library in one tap, and see what everyone else got."]
        button = "Unwrap it"
    rules = f"The rules: {swap.note}" if swap.note and kind != "unwrap" else ""
    if rules:
        lines.append(rules)
    paragraph = "".join(f'<p style="color:#1f1640;font-size:15px;line-height:1.6;margin:12px 0">{escape(line)}</p>'
                        for line in lines)
    html = (
        '<html><body style="margin:0;background:#f4f2fb;font-family:Arial,Helvetica,sans-serif">'
        '<div style="max-width:560px;margin:0 auto;padding:24px">'
        '<div style="background:#1a1433;border-radius:14px 14px 0 0;padding:22px 24px;color:#fff">'
        '<div style="font-size:12px;letter-spacing:2px;color:#fcd34d;text-transform:uppercase">Pick swap</div>'
        f'<div style="font-size:22px;font-weight:700;margin-top:6px">{escape(swap.name)}</div>'
        f'<div style="font-size:14px;color:#d4d0ec;margin-top:4px">Unwrap day {escape(_day(swap.reveal_on))} · '
        f'{escape(kinds_label(kinds_of(swap)))}</div>'
        '</div><div style="background:#fff;border-radius:0 0 14px 14px;padding:16px 24px 24px">'
        f'{paragraph}'
        f'<p style="margin:22px 0 8px"><a href="{escape(page, quote=True)}" '
        'style="background:#7c3aed;color:#fff;padding:12px 20px;border-radius:999px;text-decoration:none;font-weight:700">'
        f'{escape(button)}</a></p>'
        '<p style="color:#6f6a8a;font-size:12px;line-height:1.5;margin-top:24px">You get this because you joined '
        f'{escape(swap.name)} on OmniTrackr. A swap sends at most three emails: the draw, a reminder if you '
        'haven\'t picked, and unwrap day. '
        f'<a href="{escape(unsubscribe_url, quote=True)}" style="color:#6d28d9">Unsubscribe from product updates</a>.</p>'
        '</div></div></body></html>'
    )
    text = "\n".join([f"Hi {user.username},", ""] + lines + ["", f"{button}: {page}", "",
                     f"Unsubscribe from product updates: {unsubscribe_url}"])
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


def emails_due(db: Session, swap, now: datetime) -> list[tuple[str, int, int]]:
    """(kind, user id, other person's user id) for the emails this swap still owes."""
    current = state_of(swap)
    due = []
    if current == "drawn":
        for member, _person in rows(db, swap.id):
            if not member.gives_to or member.picked_at:
                continue
            if swap.reminded_at is not None:
                due.append(("remind", member.user_id, member.gives_to))
            elif swap.drawn_at is not None and swap.drawn_at >= now - timedelta(days=3):
                due.append(("drawn", member.user_id, member.gives_to))
    elif current == "revealed" and swap.revealed_at >= now - timedelta(days=2):
        for member, _person in rows(db, swap.id):
            if member.gives_to and member.picked_at and member.gift_opened_at is None:
                due.append(("unwrap", member.gives_to, member.user_id))
    return due


async def _send(to: str, subject: str, html: str, unsubscribe_url: str) -> None:
    from .digest import _send as send_mail
    await send_mail(to, subject, html, unsubscribe_url)


async def run_once(session_factory, now: Optional[datetime] = None, sender=_send) -> dict:
    """Draw, remind and unwrap whatever is due, then send the emails swaps still owe."""
    from .digest import mail_configured
    now = now or _now()
    result = {"swaps": 0, "drawn": 0, "revealed": 0, "reminded": 0, "sent": 0, "failed": 0, "limited": False}
    mail_ok = emails_enabled() and (mail_configured() or sender is not _send)
    db = session_factory()
    try:
        swaps = (db.query(models.PickSwap)
                 .filter(models.PickSwap.cancelled_at.is_(None),
                         or_(models.PickSwap.revealed_at.is_(None),
                             models.PickSwap.revealed_at >= now - timedelta(days=3)))
                 .order_by(models.PickSwap.id).limit(1000).all())
        due = []
        for swap in swaps:
            result["swaps"] += 1
            try:
                done = advance(db, swap, now)
            except Exception as error:  # one broken swap must not stop the rest
                db.rollback()
                print(f"Pick swap {swap.id} check failed: {error}")
                continue
            result["drawn"] += int(bool(done["drawn"]))
            result["revealed"] += int(bool(done["revealed"]))
            result["reminded"] += done["reminded"]
            if swap.cancelled_at is None:
                due.extend((swap.id, *entry) for entry in emails_due(db, swap, now))
        if not mail_ok:
            return result
        from .announcements import unsubscribe_token
        from .digest import app_url
        from .email_quota import lock_email_budget
        for swap_id, kind, user_id, other_id in due:
            if result["sent"] + result["failed"] >= PER_RUN_LIMIT:
                result["limited"] = True
                break
            key = f"{SEND_PREFIX}{swap_id}-{kind}"
            if db.query(models.EmailCampaignSend.id).filter_by(campaign_key=key, user_id=user_id).first() is not None:
                continue
            swap = db.get(models.PickSwap, swap_id)
            user = db.get(models.User, user_id)
            other = db.get(models.User, other_id)
            if swap is None or user is None or other is None or not user.is_active or not user.is_verified \
                    or not user.email or _opted_out(db, user.id):
                continue
            lock_email_budget(db)
            if allowance(db, now) <= 0:
                db.rollback()
                result["limited"] = True
                break
            db.add(models.EmailCampaignSend(campaign_key=key, user_id=user.id, status="sent", sent_at=now))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                continue
            try:
                wish_row = member_of(db, swap.id, other.id)
                unsubscribe_url = f"{app_url()}/email/updates/unsubscribe?token={unsubscribe_token(user.id)}"
                subject, html, _text = build_email(kind, swap, user, other.username,
                                                   (wish_row.wish or "") if wish_row is not None else "",
                                                   unsubscribe_url)
                await sender(user.email, subject, html, unsubscribe_url)
                result["sent"] += 1
                count("swap_email_sent")
            except Exception as error:  # one bad address must not stop the rest
                print(f"Pick swap email to user {user.id} failed: {error}")
                result["failed"] += 1
        return result
    finally:
        db.close()


async def swap_loop(app) -> None:
    """Background task started with the app; never raises."""
    from .database import SessionLocal
    await asyncio.sleep(FIRST_CHECK_DELAY_SECONDS)
    while True:
        try:
            result = await run_once(SessionLocal)
            if result["sent"] or result["drawn"] or result["revealed"] or result["failed"] or result["reminded"]:
                print(f"Pick swap: {result}")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"Pick swap check failed: {error}")
        await asyncio.sleep(CHECK_EVERY_SECONDS)
