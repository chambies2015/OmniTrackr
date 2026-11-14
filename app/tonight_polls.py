"""Tonight polls (/tonight): a member asks "what should we watch tonight?" and friends vote by link.

* A member picks two to eight titles, usually from their Next Up queue or library,
  sets how long voting stays open and shares the link (``/tonight/<token>``).
* Anyone with the link can vote, no account needed. Members vote as themselves,
  visitors by a keyed hash of their browser cookie and an optional first name.
  Everyone can change their vote until the poll closes.
* The poll closes when its time runs out, or earlier when the owner calls it.
  Most votes wins; a tie is settled by a random pick among the tied titles, and
  the result is stored so everyone sees the same winner.
* A visitor who votes and then signs up in the same browser keeps their vote,
  now under their username.

* A closed poll can go another round: the owner starts a new poll from the same
  titles (usually without the winner) and the old link points at the new one, so
  the group keeps using the link already in their chat.
* Visitors build a shortlist before signing up. It is kept in their browser and
  nothing is stored for them here until they have an account.

Options copy the title (kind, name, year, art) when the poll is made. Voting never reads
or changes anyone's library; a member who keeps the winner gets it added like any other
title, and a title they already have is left as it is.
"""
from __future__ import annotations

import os
import random
import re
import secrets
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import image_sizes, models, title_pages, title_search
from .shared_lists import KIND_LABELS, _initials

SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{16,32}")
OPTIONS_MIN = 2
OPTIONS_MAX = 8
HOURS = (1, 3, 6, 24, 72)
DEFAULT_HOURS = 3
DAILY_POLLS = 20
VOTES_MAX = 200
SUGGESTIONS_MAX = 24
MY_POLLS_SHOWN = 12
NAMES_SHOWN = 12
STARTERS_MAX = 18
STARTERS_CACHE_SECONDS = 600
_starters_cache = {"at": 0.0, "titles": []}
_starters_lock = threading.Lock()
STARTER_KINDS = ("movie", "tv", "anime")
LOOKUP_MAX = OPTIONS_MAX
VERB = {"movie": "watch", "tv": "watch", "anime": "watch", "game": "play", "book": "read", "album": "play",
        "manga": "read", "podcast": "play", "audiobook": "play"}
LIBRARY = {
    "movies": models.Movie, "tv-shows": models.TVShow, "anime": models.Anime, "video-games": models.VideoGame,
    "music": models.Music, "books": models.Book, "manga": models.Manga, "podcasts": models.Podcast,
    "audiobooks": models.Audiobook,
}


class PollError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _now() -> datetime:
    return datetime.utcnow()


def valid_token(token) -> bool:
    return isinstance(token, str) and TOKEN_RE.fullmatch(token) is not None


def url_for(poll: models.TonightPoll) -> str:
    return f"{SITE_URL}/tonight/{poll.token}"


def by_token(db: Session, token) -> Optional[tuple[models.TonightPoll, models.User]]:
    """A poll whose owner is still active, with that owner, or None."""
    if not valid_token(token):
        return None
    poll = db.query(models.TonightPoll).filter(models.TonightPoll.token == token).first()
    if poll is None:
        return None
    owner = db.get(models.User, poll.owner_id)
    if owner is None or not owner.is_active:
        return None
    return poll, owner


# ------------------------------------------------------------------ choosing titles

def _index_map(db: Session) -> dict[tuple[str, str], dict]:
    return {(entry["kind"], entry["slug"]): entry for entry in title_search.index(db)}


def _from_library(kind: str, item, indexed: dict) -> dict:
    year = title_pages.item_year(kind, item)
    slug = title_pages.path_for_item(kind, item).rsplit("/", 1)[1]
    found = indexed.get((kind, slug))
    image = title_pages._safe_image(getattr(item, title_pages.IMAGE_FIELD[kind], None))
    return {"kind": kind, "label": KIND_LABELS.get(kind, "Title"), "title": " ".join((item.title or "").split())[:200],
            "year": year, "slug": slug if found else None,
            "image": image or (title_pages._safe_image(found["image"]) if found else None)}


def suggestions(db: Session, user) -> list[dict]:
    """Titles to start a poll from: the Next Up queue first, then things in the library not finished yet."""
    indexed = _index_map(db)
    found: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def keep(category: str, item, source: str) -> None:
        kind = title_pages.LIBRARY_TO_KIND[category]
        if not (item.title or "").strip() or getattr(item, title_pages.COMPLETE_FIELD[kind], False):
            return
        key = (kind, title_pages.normalize(item.title))
        if key in seen:
            return
        seen.add(key)
        found.append(dict(_from_library(kind, item, indexed), category=category, item_id=item.id, source=source))

    queue = (db.query(models.NextUpItem).filter(models.NextUpItem.user_id == user.id)
             .order_by(models.NextUpItem.position, models.NextUpItem.id).limit(SUGGESTIONS_MAX).all())
    for entry in queue:
        model = LIBRARY.get(entry.category)
        item = db.query(model).filter(model.id == entry.item_id, model.user_id == user.id).first() if model else None
        if item is not None:
            keep(entry.category, item, "Next Up")
    recent = []
    for category, model in LIBRARY.items():
        kind = title_pages.LIBRARY_TO_KIND[category]
        done = getattr(model, title_pages.COMPLETE_FIELD[kind])
        rows = (db.query(model).filter(model.user_id == user.id, (done.is_(False)) | (done.is_(None)))
                .order_by(model.id.desc()).limit(SUGGESTIONS_MAX).all())
        recent.extend((getattr(item, "added_at", None) or datetime.min, item.id, category, item) for item in rows)
    recent.sort(key=lambda row: (row[0], row[1]), reverse=True)
    for _, _, category, item in recent:
        if len(found) >= SUGGESTIONS_MAX:
            break
        keep(category, item, "Library")
    return found[:SUGGESTIONS_MAX]


def starters(db: Session) -> list[dict]:
    """Titles a visitor can start a shortlist from, the same for everyone.

    Every signed-out visit to /tonight asks for these, and working them out groups three
    whole library tables, so one answer is kept for STARTERS_CACHE_SECONDS like the
    homepage's "Start your list" picks are.
    """
    now = time.monotonic()
    with _starters_lock:
        if _starters_cache["at"] and now - _starters_cache["at"] < STARTERS_CACHE_SECONDS:
            return [dict(entry) for entry in _starters_cache["titles"]]
    found = _find_starters(db)
    with _starters_lock:
        _starters_cache["at"], _starters_cache["titles"] = now, found
    return [dict(entry) for entry in found]


def clear_starters_cache() -> None:
    with _starters_lock:
        _starters_cache["at"], _starters_cache["titles"] = 0.0, []


def _find_starters(db: Session) -> list[dict]:
    """What members track most, then the editors' picks."""
    indexed = _index_map(db)
    found: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def keep(kind: str, title: str, year, slug: Optional[str]) -> None:
        key = (kind, title_pages.normalize(title))
        entry = indexed.get((kind, slug)) if slug else None
        if key in seen or entry is None or not entry.get("image"):
            return
        seen.add(key)
        found.append({"kind": kind, "label": KIND_LABELS.get(kind, "Title"), "title": entry["title"][:200],
                      "year": _clean_year(entry["year"]), "slug": entry["slug"],
                      "image": image_sizes.sized(title_pages._safe_image(entry["image"]), 200)})

    per_kind = {kind: title_pages.popular(db, kind, limit=8, min_members=2) for kind in STARTER_KINDS}
    while any(per_kind.values()) and len(found) < STARTERS_MAX:
        for kind in STARTER_KINDS:
            if per_kind[kind]:
                item = per_kind[kind].pop(0)
                keep(kind, item["title"], item["year"], item["url"].rsplit("/", 1)[1])
    if len(found) < STARTERS_MAX:
        from . import pick
        for entry in pick.candidates():
            if len(found) >= STARTERS_MAX:
                break
            if entry["kind"] in STARTER_KINDS:
                keep(entry["kind"], entry["title"], entry["year"], entry["slug"])
    return found[:STARTERS_MAX]


def _clean_year(year) -> Optional[int]:
    return year if isinstance(year, int) and not isinstance(year, bool) and 1800 <= year <= 2100 else None


def resolve_option(db: Session, user, option: dict, indexed: dict) -> dict:
    """One title for a new poll: from the member's library, a title page, or typed by hand."""
    category, item_id = option.get("category"), option.get("item_id")
    if category is not None or item_id is not None:
        model = LIBRARY.get(category)
        item = db.query(model).filter(model.id == item_id, model.user_id == user.id).first() if model and item_id else None
        if item is None or not (item.title or "").strip():
            raise PollError("One of those titles isn't in your library anymore.", 404)
        return _from_library(title_pages.LIBRARY_TO_KIND[category], item, indexed)
    kind = option.get("kind")
    if kind not in title_pages.KINDS:
        raise PollError("Pick what kind of title each option is.")
    slug = option.get("slug")
    found = indexed.get((kind, slug)) if isinstance(slug, str) and re.fullmatch(r"[a-z0-9-]{1,130}", slug) else None
    if found is not None:
        return {"kind": kind, "label": KIND_LABELS.get(kind, "Title"), "title": found["title"][:200],
                "year": _clean_year(found["year"]), "slug": found["slug"], "image": title_pages._safe_image(found["image"])}
    title = " ".join(str(option.get("title") or "").split())[:200]
    if not title:
        raise PollError("Every option needs a title.")
    return {"kind": kind, "label": KIND_LABELS.get(kind, "Title"), "title": title,
            "year": _clean_year(option.get("year")), "slug": None, "image": None}


# ------------------------------------------------------------------ making and closing polls

def _made_today(db: Session, user_id: int) -> int:
    return db.query(func.count(models.TonightPoll.id)).filter(
        models.TonightPoll.owner_id == user_id,
        models.TonightPoll.created_at > _now() - timedelta(days=1)).scalar() or 0


def create(db: Session, user, question: str, options: list[dict], hours: int,
           previous: Optional[models.TonightPoll] = None) -> models.TonightPoll:
    if hours not in HOURS:
        raise PollError("Pick how long voting stays open.")
    if _made_today(db, user.id) >= DAILY_POLLS:
        raise PollError("That's a lot of polls for one day. Try again tomorrow.", 429)
    indexed = _index_map(db)
    picked, keys = [], set()
    for option in options:
        resolved = resolve_option(db, user, option, indexed)
        key = (resolved["kind"], title_pages.normalize(resolved["title"]), resolved["year"])
        if key in keys:
            continue
        keys.add(key)
        picked.append(resolved)
    if len(picked) < OPTIONS_MIN:
        raise PollError(f"Add at least {OPTIONS_MIN} different titles to vote on.")
    if len(picked) > OPTIONS_MAX:
        raise PollError(f"A poll holds up to {OPTIONS_MAX} titles.")
    return _store(db, user, question, picked, hours, previous)


def _store(db: Session, user, question: str, picked: list[dict], hours: int,
           previous: Optional[models.TonightPoll] = None) -> models.TonightPoll:
    question = " ".join((question or "").split())[:120] or default_question(picked)
    now = _now()
    poll = models.TonightPoll(token=secrets.token_urlsafe(12), owner_id=user.id, question=question,
                              created_at=now, closes_at=now + timedelta(hours=hours),
                              previous_id=previous.id if previous is not None else None)
    db.add(poll)
    db.flush()
    for position, option in enumerate(picked):
        db.add(models.TonightPollOption(poll_id=poll.id, position=position, kind=option["kind"], title=option["title"],
                                        year=option["year"], slug=option["slug"], image=option["image"]))
    db.commit()
    db.refresh(poll)
    return poll


# ------------------------------------------------------------------ another round

def next_round(db: Session, poll: models.TonightPoll) -> Optional[models.TonightPoll]:
    """The newest poll started from this one, if it is still there."""
    return (db.query(models.TonightPoll).filter(models.TonightPoll.previous_id == poll.id)
            .order_by(models.TonightPoll.id.desc()).first())


def round_number(db: Session, poll: models.TonightPoll) -> int:
    """1 for a first poll, 2 for the round started from it, and so on. Stops counting at ten."""
    number, current = 1, poll
    while current.previous_id is not None and number < 10:
        current = db.get(models.TonightPoll, current.previous_id)
        if current is None:
            break
        number += 1
    return number


def again(db: Session, poll: models.TonightPoll, user, keep_winner: bool = False) -> tuple[models.TonightPoll, bool]:
    """Start another round from a closed poll. Returns (the new poll, True when it was made just now)."""
    if poll.owner_id != user.id:
        raise PollError("Only whoever made this poll can start another round.", 403)
    refresh(db, poll)
    if poll.closed_at is None:
        raise PollError("This round is still open. Close it first, then start the next one.", 409)
    running = next_round(db, poll)
    if running is not None:
        return running, False
    if _made_today(db, user.id) >= DAILY_POLLS:
        raise PollError("That's a lot of polls for one day. Try again tomorrow.", 429)
    picked = [{"kind": option.kind, "title": option.title, "year": option.year, "slug": option.slug, "image": option.image}
              for option in poll.options if keep_winner or option.id != poll.winner_id]
    if len(picked) < OPTIONS_MIN:
        raise PollError("There is only one title left. Make a new poll to add more.")
    # As long as the last round when it ran its full time. Closing early moves closes_at, so the
    # length that was picked is gone by then and the round gets the usual three hours.
    lasted = (poll.closes_at - poll.created_at).total_seconds() / 3600
    hours = next((value for value in HOURS if abs(value - lasted) < 0.01), DEFAULT_HOURS)
    fresh = _store(db, user, poll.question, picked, hours, previous=poll)
    voters = {user_id for user_id, in db.query(models.TonightPollVote.user_id).filter(
        models.TonightPollVote.poll_id == poll.id, models.TonightPollVote.user_id.isnot(None))}
    voters.discard(user.id)
    active = {row.id for row in db.query(models.User.id).filter(models.User.id.in_(voters), models.User.is_active.is_(True))} if voters else set()
    for user_id in sorted(active):
        db.add(models.Notification(user_id=user_id, type="tonight_poll", link=f"/tonight/{fresh.token}",
                                   message=f'{user.username} started another round: "{fresh.question}"'[:250]))
    db.commit()
    return fresh, True


def default_question(options: list[dict]) -> str:
    verbs = {VERB.get(option["kind"], "start") for option in options}
    return f"What should we {verbs.pop()} tonight?" if len(verbs) == 1 else "What should we start tonight?"


def _tally(db: Session, poll: models.TonightPoll) -> dict[int, int]:
    rows = (db.query(models.TonightPollVote.option_id, func.count(models.TonightPollVote.id))
            .filter(models.TonightPollVote.poll_id == poll.id).group_by(models.TonightPollVote.option_id).all())
    return {option_id: count for option_id, count in rows}


def _settle(db: Session, poll: models.TonightPoll) -> None:
    """Close the poll and store the winner. Does not commit."""
    counts = _tally(db, poll)
    poll.closed_at = poll.closed_at or min(_now(), poll.closes_at)
    if counts:
        top = max(counts.values())
        tied = sorted(option_id for option_id, count in counts.items() if count == top)
        poll.winner_id = tied[0] if len(tied) == 1 else random.SystemRandom().choice(tied)


def refresh(db: Session, poll: models.TonightPoll) -> None:
    """A poll past its time closes on the first look after it."""
    if poll.closed_at is None and poll.closes_at <= _now():
        # Two first looks at once would otherwise both draw a tie-break.
        locked = (db.query(models.TonightPoll).filter(models.TonightPoll.id == poll.id).with_for_update().first())
        if locked is not None and locked.closed_at is None:
            _settle(db, locked)
            _tell_voters(db, locked)
            db.commit()
        db.refresh(poll)


def close(db: Session, poll: models.TonightPoll, user) -> None:
    if poll.owner_id != user.id:
        raise PollError("Only whoever made this poll can close it.", 403)
    refresh(db, poll)
    if poll.closed_at is not None:
        return
    if not db.query(models.TonightPollVote.id).filter_by(poll_id=poll.id).first():
        raise PollError("Nobody has voted yet. Share the link first, or delete the poll.")
    poll.closes_at = min(poll.closes_at, _now())
    _settle(db, poll)
    _tell_voters(db, poll)
    db.commit()


def delete(db: Session, poll: models.TonightPoll, user) -> None:
    if poll.owner_id != user.id:
        raise PollError("Only whoever made this poll can delete it.", 403)
    link = f"/tonight/{poll.token}"
    db.query(models.Notification).filter(models.Notification.link == link,
                                         models.Notification.read_at.is_(None)).delete(synchronize_session=False)
    db.delete(poll)
    db.commit()


def _winner(poll: models.TonightPoll) -> Optional[models.TonightPollOption]:
    return next((option for option in poll.options if option.id == poll.winner_id), None)


def _tell_voters(db: Session, poll: models.TonightPoll) -> None:
    """Members who voted (other than the owner) hear what won. Does not commit."""
    winner = _winner(poll)
    if winner is None:
        return
    link = f"/tonight/{poll.token}"
    owner = db.get(models.User, poll.owner_id)
    voters = {user_id for user_id, in db.query(models.TonightPollVote.user_id).filter(
        models.TonightPollVote.poll_id == poll.id, models.TonightPollVote.user_id.isnot(None))}
    voters.discard(poll.owner_id)
    for user_id in voters:
        db.add(models.Notification(user_id=user_id, type="tonight_poll_result", link=link,
                                   message=f'{winner.title} won {owner.username}\'s poll "{poll.question}".'[:250]))


def notify_friends(db: Session, poll: models.TonightPoll, user, friend_ids: list[int]) -> int:
    """Ask friends to vote. Only real friends get the note. Does not commit."""
    from .crud.friends import are_friends
    asked = 0
    for friend_id in dict.fromkeys(friend_ids):
        if friend_id == user.id or not are_friends(db, user.id, friend_id):
            continue
        db.add(models.Notification(user_id=friend_id, type="tonight_poll", link=f"/tonight/{poll.token}",
                                   message=f'{user.username} wants your vote: "{poll.question}"'[:250]))
        asked += 1
    return asked


# ------------------------------------------------------------------ voting

def _find_vote(db: Session, poll: models.TonightPoll, user, visitor: Optional[str]) -> Optional[models.TonightPollVote]:
    """The viewer's vote. A visitor's vote moves under their account once they sign in on the same browser."""
    if user is not None:
        mine = db.query(models.TonightPollVote).filter_by(poll_id=poll.id, user_id=user.id).first()
        guest = (db.query(models.TonightPollVote).filter_by(poll_id=poll.id, visitor=visitor, user_id=None).first()
                 if visitor else None)
        if mine is None and guest is not None:
            guest.user_id, guest.name = user.id, None
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                return db.query(models.TonightPollVote).filter_by(poll_id=poll.id, user_id=user.id).first()
            return guest
        if mine is not None and guest is not None:
            # They voted as a visitor and again after signing in: the signed-in vote counts once.
            db.delete(guest)
            db.commit()
        return mine
    if not visitor:
        return None
    return db.query(models.TonightPollVote).filter_by(poll_id=poll.id, visitor=visitor).first()


def clean_name(value) -> Optional[str]:
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    value = "".join(char for char in value if char.isprintable())[:30]
    return value or None


def vote(db: Session, poll: models.TonightPoll, user, visitor: Optional[str], option_id: int, name: Optional[str]) -> bool:
    """Record or change a vote. Returns True for a new voter (not a change of mind)."""
    refresh(db, poll)
    if poll.closed_at is not None:
        raise PollError("Voting on this poll has closed.", 409)
    if user is None and not visitor:
        raise PollError("Your browser didn't keep our cookie, so we can't count your vote. Allow cookies and try again.")
    if not any(option.id == option_id for option in poll.options):
        raise PollError("That title isn't on this poll.", 404)
    row = _find_vote(db, poll, user, visitor)
    if row is not None:
        row.option_id, row.updated_at = option_id, _now()
        if user is None:
            row.name = clean_name(name) or row.name
        db.commit()
        return False
    if db.query(func.count(models.TonightPollVote.id)).filter_by(poll_id=poll.id).scalar() >= VOTES_MAX:
        raise PollError(f"This poll already has {VOTES_MAX} votes, which is as many as one poll takes.", 409)
    row = models.TonightPollVote(poll_id=poll.id, option_id=option_id,
                                 user_id=user.id if user is not None else None,
                                 visitor=visitor if user is None else None,
                                 name=clean_name(name) if user is None else None)
    db.add(row)
    voter = user.username if user is not None else (row.name or "Someone")
    if user is None or user.id != poll.owner_id:
        _tell_owner(db, poll, voter)
    try:
        db.commit()
    except IntegrityError:
        # The same voter in two tabs at once: the other tab's vote stands, so change it instead.
        db.rollback()
        vote(db, poll, user, visitor, option_id, name)
        return False
    return True


def _tell_owner(db: Session, poll: models.TonightPoll, voter: str) -> None:
    """One note per poll until the owner opens it, however many votes come in meanwhile."""
    link = f"/tonight/{poll.token}"
    waiting = db.query(models.Notification.id).filter(
        models.Notification.user_id == poll.owner_id, models.Notification.type == "tonight_poll_vote",
        models.Notification.link == link, models.Notification.read_at.is_(None)).first()
    if waiting is None:
        db.add(models.Notification(user_id=poll.owner_id, type="tonight_poll_vote", link=link,
                                   message=f'{voter} voted in your poll "{poll.question}".'[:250]))


def unvote(db: Session, poll: models.TonightPoll, user, visitor: Optional[str]) -> None:
    refresh(db, poll)
    if poll.closed_at is not None:
        raise PollError("Voting on this poll has closed.", 409)
    row = _find_vote(db, poll, user, visitor)
    if row is not None:
        db.delete(row)
        db.commit()


def mark_seen(db: Session, poll: models.TonightPoll, user) -> None:
    """Opening a poll clears its notifications for that member."""
    db.query(models.Notification).filter(
        models.Notification.user_id == user.id, models.Notification.link == f"/tonight/{poll.token}",
        models.Notification.read_at.is_(None)).update({"read_at": _now()}, synchronize_session=False)
    db.commit()


# ------------------------------------------------------------------ keeping a title

def _own_row(db: Session, user, option: models.TonightPollOption):
    model = title_pages.KINDS[option.kind][0]
    normalized = title_pages.normalize(option.title)
    rows = db.query(model).filter(model.user_id == user.id, func.lower(func.trim(model.title)) == normalized).all()
    # Two editions with one name: the one from the option's year, else the first.
    return next((row for row in rows if title_pages.item_year(option.kind, row) == option.year), rows[0] if rows else None)


def keep(db: Session, poll: models.TonightPoll, user, option_id: Optional[int], queue: bool) -> dict:
    """Put a title from the poll in the member's library (not started) and, if asked, at the end of Next Up.

    A title the member already has is left exactly as it is. Does not change the poll.
    """
    from .progress import lock_progress_owner
    option = next((entry for entry in poll.options if entry.id == (option_id or poll.winner_id)), None)
    if option is None:
        raise PollError("That title isn't on this poll.", 404)
    lock_progress_owner(db, user.id)
    row, state = _own_row(db, user, option), "existing"
    if row is None:
        group = title_pages.find(db, option.kind, option.slug) if option.slug else None
        if group is not None:
            from .routers.titles import add_group_to_library
            state, row = add_group_to_library(db, user, group)
        else:
            model, _, _, _, creator = title_pages.KINDS[option.kind]
            fields = {"user_id": user.id, "title": option.title}
            if option.kind == "game":
                fields["release_date"] = datetime(option.year, 1, 1) if option.year else None
            else:
                fields["year"] = option.year
            if creator:
                fields[creator] = ""
            image = title_pages._safe_image(option.image)
            if image:
                fields[title_pages.IMAGE_FIELD[option.kind]] = image
            row = model(**fields)
            db.add(row)
            db.flush()
            state = "created"
    category = title_pages.KINDS[option.kind][2]
    queued = False
    if queue:
        waiting = db.query(models.NextUpItem).filter_by(user_id=user.id, category=category, item_id=row.id).first()
        if waiting is None:
            last = db.query(func.max(models.NextUpItem.position)).filter(models.NextUpItem.user_id == user.id).scalar()
            db.add(models.NextUpItem(user_id=user.id, category=category, item_id=row.id,
                                     position=(last if last is not None else -1) + 1))
            queued = True
    try:
        db.commit()
    except IntegrityError:
        # The same title queued from two tabs at once: it is in Next Up either way.
        db.rollback()
        queued = False
    return {"state": state, "queued": queued, "in_queue": bool(queue), "title": option.title, "category": category}


# ------------------------------------------------------------------ what pages show

def _option_dict(option: models.TonightPollOption) -> dict:
    return {"id": option.id, "kind": option.kind, "label": KIND_LABELS.get(option.kind, "Title"),
            "title": option.title, "year": option.year, "image": option.image,
            "url": f"/titles/{option.kind}/{option.slug}" if option.slug else None,
            "verb": VERB.get(option.kind, "start")}


def _hours_left(poll: models.TonightPoll) -> float:
    return max(0.0, (poll.closes_at - _now()).total_seconds() / 3600)


def closes_label(poll: models.TonightPoll) -> str:
    if poll.closed_at is not None:
        return "Voting closed"
    minutes = int(_hours_left(poll) * 60)
    if minutes < 1:
        return "Closing now"
    if minutes < 60:
        return f"Closes in {minutes} min"
    hours = round(minutes / 60)
    if hours < 48:
        return f"Closes in {hours} hour{'s' if hours != 1 else ''}"
    return f"Closes in {round(hours / 24)} days"


def state(db: Session, poll: models.TonightPoll, owner, viewer, visitor: Optional[str]) -> dict:
    refresh(db, poll)
    mine = _find_vote(db, poll, viewer, visitor)
    rows = (db.query(models.TonightPollVote, models.User)
            .outerjoin(models.User, models.User.id == models.TonightPollVote.user_id)
            .filter(models.TonightPollVote.poll_id == poll.id)
            .order_by(models.TonightPollVote.created_at, models.TonightPollVote.id).all())
    voters: dict[int, list[dict]] = {}
    counts: dict[int, int] = {}
    for row, user in rows:
        counts[row.option_id] = counts.get(row.option_id, 0) + 1
        if user is not None and not user.is_active:
            continue
        name = user.username if user is not None else (row.name or None)
        you = mine is not None and row.id == mine.id
        if name or you:
            voters.setdefault(row.option_id, []).append(
                {"name": name or "You", "initials": _initials(name or "You"), "member": user is not None, "you": you})
    total = sum(counts.values())
    options = []
    for option in poll.options:
        count = counts.get(option.id, 0)
        named = voters.get(option.id, [])
        options.append(dict(_option_dict(option), votes=count,
                            share=round(100 * count / total) if total else 0,
                            voters=named[:NAMES_SHOWN], others=max(0, count - len(named[:NAMES_SHOWN]))))
    closed = poll.closed_at is not None
    leader = max(counts.values()) if counts else 0
    is_owner = viewer is not None and viewer.id == poll.owner_id
    following = next_round(db, poll) if closed else None
    if following is not None:
        refresh(db, following)
    before = db.get(models.TonightPoll, poll.previous_id) if poll.previous_id else None
    before_winner = _winner(before) if before is not None else None
    return {
        "round": round_number(db, poll) if before is not None else 1,
        "next": {"path": f"/tonight/{following.token}", "closed": following.closed_at is not None,
                 "closes_label": closes_label(following)} if following is not None else None,
        "previous": {"path": f"/tonight/{before.token}",
                     "winner": before_winner.title if before_winner is not None else None} if before is not None else None,
        "token": poll.token, "question": poll.question, "url": url_for(poll),
        "owner": {"name": owner.username, "initials": _initials(owner.username), "you": is_owner},
        "created_at": poll.created_at.isoformat() + "Z", "closes_at": poll.closes_at.isoformat() + "Z",
        "closes_label": closes_label(poll), "closed": closed,
        "winner": poll.winner_id if closed else None,
        "leading": [option["id"] for option in options if leader and option["votes"] == leader] if not closed else [],
        "total": total, "options": options,
        "me": {"option_id": mine.option_id if mine else None, "name": mine.name if mine and viewer is None else None,
               "signed_in": viewer is not None, "owner": is_owner},
    }


def mine(db: Session, user) -> list[dict]:
    """The member's recent polls, newest first, with what's winning."""
    polls = (db.query(models.TonightPoll).filter(models.TonightPoll.owner_id == user.id)
             .order_by(models.TonightPoll.created_at.desc(), models.TonightPoll.id.desc()).limit(MY_POLLS_SHOWN).all())
    found = []
    for poll in polls:
        refresh(db, poll)
        counts = _tally(db, poll)
        total = sum(counts.values())
        if poll.closed_at is not None:
            top = _winner(poll)
        else:
            top = max(poll.options, key=lambda option: (counts.get(option.id, 0), -option.position)) if total else None
        found.append({
            "token": poll.token, "question": poll.question, "url": f"/tonight/{poll.token}",
            "closed": poll.closed_at is not None, "closes_label": closes_label(poll), "total": total,
            "options": len(poll.options),
            "top": _option_dict(top) if top is not None else None,
            "created_at": poll.created_at.isoformat() + "Z",
        })
    return found


# ------------------------------------------------------------------ link previews

def _title_list(titles: list[str], limit: int = 3) -> str:
    shown = titles[:limit]
    if len(titles) > limit:
        return ", ".join(shown) + f" and {len(titles) - limit} more"
    return shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " or " + shown[-1]


def preview_line(poll: models.TonightPoll, owner) -> str:
    """The sentence chat apps show under a poll link."""
    winner = _winner(poll) if poll.closed_at is not None else None
    if winner is not None:
        return f"The group picked {winner.title}. See how the vote went."
    if poll.closed_at is not None:
        return f"{owner.username}'s poll has closed."
    return (f"{owner.username} wants your vote: {_title_list([option.title for option in poll.options])}. "
            "One tap, no account needed.")


def card_facts(db: Session, poll: models.TonightPoll, owner) -> dict:
    """What the preview image shows. An open poll's card has no counts, so it stays the same while votes come in."""
    winner = _winner(poll) if poll.closed_at is not None else None
    counts = _tally(db, poll) if winner is not None else {}
    return {
        "question": poll.question, "owner": owner.username, "closed": poll.closed_at is not None,
        "options": [(KIND_LABELS.get(option.kind, "Title"), option.title, option.year) for option in poll.options],
        "winner": (winner.title, KIND_LABELS.get(winner.kind, "Title"), winner.year) if winner is not None else None,
        "winner_votes": counts.get(winner.id, 0) if winner is not None else 0,
        "total": sum(counts.values()),
    }
