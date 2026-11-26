"""The yearbook (Nov 2026): friends sign your year with a note and a "most likely to" vote.

A member writes the name for the cover and a yearbook quote, picks up to four titles from
their year, and sends the link. Anyone with the link can sign:

* Friends (accepted friendships) who sign show up straight away.
* Other members and people without an account write a note that waits until the owner lets
  it in, so a forwarded link can't put anything on the page the owner hasn't read.
* A member signs once per book and can change or take back their note until signing closes.
  Someone without an account types a name; one address can leave at most a few notes in a
  book, and notes with links, email addresses or phone numbers are refused.
* Each note can carry one vote from SUPERLATIVES. The page shows the top votes from notes
  that are shown.

Signing closes after New Year's Day (EDITIONS). The book stays readable while the link is on.
Only shelves the owner shows and doesn't keep private feed the picks and the numbers.

The owner hears about notes on the bell (and push, under the "Yearbook" switch), and by email
at most three times while signing is open plus once when it closes. Friends hear once when a
friend opens their yearbook. New tables only (yearbooks, yearbook_signatures).
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from html import escape
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models

# Year -> when setup and signing open (a date, UTC) and when signing closes (UTC). Add the next
# year here, with its guide copy, before November.
EDITIONS = {
    2026: {"opens": date(2026, 11, 26), "closes": datetime(2027, 1, 2, 12, 0)},
}
AFTER_DAYS = 14             # the home card and the hub keep the closed book this long
COVER_MAX = 40
QUOTE_MAX = 140
NOTE_MAX = 300
NOTE_MIN = 2
GUEST_NAME_MAX = 40
PICKS_MAX = 4
OPTIONS_MAX = 40
NOTES_MAX = 300             # notes in one book, every status counted
WAITING_MAX = 60            # notes waiting for the owner at once
GUEST_PER_ADDRESS = 3       # notes one address can leave in one book
FRIENDS_TOLD_MAX = 50
FRIEND_BOOKS_MAX = 30
CLASS_MAX = 200
TALLY_SHOWN = 3
LOVED_RATING = 8
NOTES_EMAILS_MAX = 3
NOTES_EMAIL_GAP = timedelta(days=4)
NOTES_EMAIL_WAIT = timedelta(hours=20)   # give the bell a chance first
CLOSED_EMAIL_WITHIN = timedelta(days=7)
CHECK_EVERY_SECONDS = 1800
FIRST_CHECK_DELAY_SECONDS = 180
PER_RUN_LIMIT = 40
SEND_PREFIX = "yearbook-"
UTM = "utm_source=email&utm_campaign=yearbook"
NOTE_TYPES = ("yearbook_signed", "yearbook_waiting", "yearbook_friend", "yearbook_closed")
STATUSES = ("shown", "waiting", "hidden")

# (key, the vote as it reads on the page). Kind ones only: the owner shares this page.
SUPERLATIVES = (
    ("one_more_episode", "Most likely to say \"one more episode\" at 2 a.m."),
    ("never_finishes", "Most likely to start a new show before finishing the last one"),
    ("comfort_rewatch", "Most likely to rewatch the same comfort show again"),
    ("best_recs", "Most likely to recommend something you end up loving"),
    ("book_better", "Most likely to say the book was better"),
    ("hundred_hours", "Most likely to put 100 hours into one game"),
    ("backlog", "Most likely to have a backlog taller than they are"),
    ("soundtrack", "Most likely to know the whole soundtrack by heart"),
    ("cries", "Most likely to cry at an animated film"),
    ("twist", "Most likely to guess the twist in the first ten minutes"),
    ("podcasts", "Most likely to have a podcast for every mood"),
    ("best_taste", "Best taste in the class, no contest"),
)
SUPERLATIVE_LABEL = dict(SUPERLATIVES)

# Quotes offered on the setup form when the box is empty.
QUOTE_IDEAS = (
    "I'll start it after this episode.",
    "My backlog is a lifestyle.",
    "Spoilers were the real enemy.",
    "Read the book, then watched it, then complained.",
    "Next year I finish the ones I started. Probably.",
    "Every season finale ruined me a little.",
)

CATEGORY_LABEL = {"movies": "films", "tv-shows": "shows", "anime": "anime", "video-games": "games",
                  "music": "albums", "books": "books", "manga": "manga", "podcasts": "podcasts",
                  "audiobooks": "audiobooks"}
CATEGORY_ONE = {"movies": "film", "tv-shows": "show", "anime": "anime", "video-games": "game", "music": "album",
                "books": "book", "manga": "manga", "podcasts": "podcast", "audiobooks": "audiobook"}
FORMAT_LABEL = {"movies": "Film", "tv-shows": "TV show", "anime": "Anime", "video-games": "Game", "music": "Album",
                "books": "Book", "manga": "Manga", "podcasts": "Podcast", "audiobooks": "Audiobook"}

CONTACT = (re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE),
           re.compile(r"\b[a-z0-9-]{2,}\.(?:com|net|org|io|gg|xyz|ly|me|co|app|link|tv|info|ru|cn)\b(?:/\S*)?",
                      re.IGNORECASE),
           re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
           re.compile(r"\+\d[\d\s().-]{7,}\d"),
           re.compile(r"\(?\b\d{3}\)?[\s.-]?\d{3}[\s.-]\d{4}\b"),
           re.compile(r"\b\d{10,}\b"))


class YearbookError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def emails_enabled() -> bool:
    return os.getenv("YEARBOOK_EMAILS", "").strip().lower() not in ("off", "0", "false", "no")


def loop_enabled() -> bool:
    return os.getenv("TESTING", "").lower() != "true"


def daily_limit() -> int:
    try:
        return max(0, int(os.getenv("YEARBOOK_DAILY_LIMIT", "40")))
    except ValueError:
        return 40


def count(event: str, request=None) -> None:
    from . import funnel
    funnel.record(event, request)


# ---------------------------------------------------------------- the season

def opens_on(year: int) -> Optional[date]:
    edition = EDITIONS.get(year)
    if edition is None:
        return None
    # YEARBOOK_OPENS=YYYY-MM-DD moves the newest edition's opening day (for a late deploy or a test run).
    override = os.getenv("YEARBOOK_OPENS", "").strip()
    if override and year == max(EDITIONS):
        try:
            return date.fromisoformat(override)
        except ValueError:
            pass
    return edition["opens"]


def closes_at(year: int) -> Optional[datetime]:
    edition = EDITIONS.get(year)
    return edition["closes"] if edition else None


def state_of(year: int, now: Optional[datetime] = None) -> Optional[str]:
    """"soon", "open" (setup and signing), "closed" (read only) or None for a year with no edition."""
    now = now or _now()
    opens = opens_on(year)
    if opens is None:
        return None
    if now.date() < opens:
        return "soon"
    return "open" if now < closes_at(year) else "closed"


def current_year(now: Optional[datetime] = None) -> Optional[int]:
    """The newest edition that has opened, or None before the first one."""
    now = now or _now()
    opened = [year for year in EDITIONS if now.date() >= opens_on(year)]
    return max(opened) if opened else None


def season_year(now: Optional[datetime] = None) -> Optional[int]:
    """The edition the home card talks about: open, or closed less than AFTER_DAYS ago."""
    now = now or _now()
    year = current_year(now)
    if year is None or now >= closes_at(year) + timedelta(days=AFTER_DAYS):
        return None
    return year


def _day(value) -> str:
    if value is None:
        return ""
    return f"{value:%B} {value.day}"


def closes_label(year: int) -> str:
    """The last day to sign, as people read it: the day before the closing moment's date."""
    closes = closes_at(year)
    return _day((closes - timedelta(hours=13)).date()) if closes else ""


def can_preview(user) -> bool:
    from .admin_access import is_site_admin
    return user is not None and is_site_admin(user)


def setup_open(year: int, user=None, now: Optional[datetime] = None) -> bool:
    current = state_of(year, now)
    return current == "open" or (current == "soon" and can_preview(user))


# ---------------------------------------------------------------- words and text

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


def has_contact(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in CONTACT)


def _plural(number: int, one: str, many: Optional[str] = None) -> str:
    return f"{number} {one if number == 1 else (many or one + 's')}"


# ---------------------------------------------------------------- the book

def path_for(book) -> Optional[str]:
    return f"/yearbook/{book.token}" if book is not None and book.token else None


def url_for(book) -> Optional[str]:
    from .digest import app_url
    path = path_for(book)
    return app_url() + path if path else None


def get(db: Session, user_id: int, year: int) -> Optional[models.Yearbook]:
    return db.query(models.Yearbook).filter_by(user_id=user_id, year=year).first()


def by_token(db: Session, token) -> Optional[models.Yearbook]:
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,40}", token):
        return None
    book = db.query(models.Yearbook).filter(models.Yearbook.token == token).first()
    if book is None:
        return None
    owner = db.get(models.User, book.user_id)
    return book if owner is not None and owner.is_active else None


def _new_token() -> str:
    return secrets.token_urlsafe(18)


def shareable(user) -> list[str]:
    """Shelves the owner shows in their library and doesn't keep private: the only ones a book reads."""
    from .ranking_shares import _shareable
    from .check_in import CATEGORIES
    return [category for category in CATEGORIES if _shareable(user, category)]


def _model(category: str):
    from .check_in import CATEGORIES
    return CATEGORIES[category][0]


def _card(category: str, row) -> dict:
    from . import rankings
    card = rankings.card(category, row)
    return {"category": category, "id": row.id, "title": card["title"], "year": card["year"],
            "creator": card["creator"], "image": card["image"], "url": card["url"],
            "format": FORMAT_LABEL.get(category, "")}


def _stored_picks(book) -> list[dict]:
    try:
        raw = json.loads(book.picks or "[]")
    except (TypeError, ValueError):
        return []
    picks = []
    for entry in raw if isinstance(raw, list) else []:
        if isinstance(entry, dict) and isinstance(entry.get("category"), str) and isinstance(entry.get("id"), int):
            picks.append({"category": entry["category"], "id": entry["id"]})
    return picks[:PICKS_MAX]


def picks_of(db: Session, book, owner) -> list[dict]:
    """The book's picks as cards, leaving out anything on a shelf that is now hidden or private, or deleted."""
    allowed = set(shareable(owner))
    cards = []
    for entry in _stored_picks(book):
        if entry["category"] not in allowed:
            continue
        model = _model(entry["category"])
        row = db.query(model).filter(model.id == entry["id"], model.user_id == owner.id).first()
        if row is not None and (row.title or "").strip():
            cards.append(_card(entry["category"], row))
    return cards


def numbers(db: Session, owner, year: int) -> dict:
    """Titles finished in the year on shelves the owner shares, counted the way Year in Review counts them."""
    from . import year_in_review
    allowed = shareable(owner)
    _, finished = year_in_review._finishes(db, owner.id, year, allowed)
    per = {}
    for row in finished.values():
        per[row["category"]] = per.get(row["category"], 0) + 1
    shelves = [{"category": category, "count": per[category],
                "label": _plural(per[category], CATEGORY_ONE[category], CATEGORY_LABEL[category])}
               for category in allowed if per.get(category)]
    shelves.sort(key=lambda shelf: -shelf["count"])
    return {"total": sum(per.values()), "shelves": shelves}


def pick_options(db: Session, owner, year: int) -> list[dict]:
    """What the owner can put on the cover: the year's finishes first (favourites, then by score), then
    titles they rated highly at any time. Shared shelves only."""
    from . import year_in_review
    allowed = shareable(owner)
    _, finished = year_in_review._finishes(db, owner.id, year, allowed)
    wanted: list[tuple[str, int]] = []
    for row in sorted(finished.values(), key=lambda r: (not r["favorite"], -(r["rating"] or 0), r["finished_at"])):
        if row.get("item_id") and (row["category"], row["item_id"]) not in wanted:
            wanted.append((row["category"], row["item_id"]))
    loved = []
    for category in allowed:
        model = _model(category)
        rating = getattr(model, "rating", None)
        if rating is None:
            continue
        for item_id, score in (db.query(model.id, rating)
                               .filter(model.user_id == owner.id, rating >= LOVED_RATING, model.title.isnot(None))
                               .order_by(rating.desc(), model.id.desc()).limit(12)):
            loved.append((float(score or 0), category, item_id))
    for _score, category, item_id in sorted(loved, key=lambda entry: -entry[0]):
        if (category, item_id) not in wanted:
            wanted.append((category, item_id))
    wanted = wanted[:OPTIONS_MAX]
    by_category: dict[str, list[int]] = {}
    for category, item_id in wanted:
        by_category.setdefault(category, []).append(item_id)
    rows = {}
    for category, ids in by_category.items():
        model = _model(category)
        for row in db.query(model).filter(model.user_id == owner.id, model.id.in_(ids)):
            rows[(category, row.id)] = row
    finished_keys = {(row["category"], row.get("item_id")) for row in finished.values()}
    options = []
    for key in wanted:
        row = rows.get(key)
        if row is None or not (row.title or "").strip():
            continue
        card = _card(key[0], row)
        card["this_year"] = key in finished_keys
        options.append(card)
    return options


def save(db: Session, owner, year: int, *, cover_name, quote, picks, show_numbers: bool, listed: bool,
         now: Optional[datetime] = None) -> tuple[models.Yearbook, bool]:
    """Make or change the owner's book. Returns (book, made). A new book gets its link straight away."""
    now = now or _now()
    if year not in EDITIONS:
        raise YearbookError("There's no yearbook for that year.", 404)
    if not setup_open(year, owner, now):
        if state_of(year, now) == "soon":
            raise YearbookError(f"Yearbooks open on {_day(opens_on(year))}.", 409)
        raise YearbookError("Signing closed after New Year's Day, so this yearbook can't change now.", 409)
    cover = clean_line(cover_name, COVER_MAX)
    if not cover:
        raise YearbookError("Put a name on the cover. It can be your first name or a nickname.", 422)
    if has_contact(cover):
        raise YearbookError("The cover name can't have a link, an email address or a phone number.", 422)
    text = clean_line(quote, QUOTE_MAX) or None
    if text and has_contact(text):
        raise YearbookError("Your quote can't have a link, an email address or a phone number.", 422)
    allowed = set(shareable(owner))
    chosen = []
    for entry in picks or []:
        category, item_id = entry.get("category"), entry.get("id")
        if category not in allowed or not isinstance(item_id, int) or {"category": category, "id": item_id} in chosen:
            continue
        model = _model(category)
        if db.query(model.id).filter(model.id == item_id, model.user_id == owner.id).first() is None:
            continue
        chosen.append({"category": category, "id": item_id})
        if len(chosen) >= PICKS_MAX:
            break
    book = get(db, owner.id, year)
    made = book is None
    if made:
        book = models.Yearbook(user_id=owner.id, year=year, token=_new_token(), created_at=now)
        db.add(book)
    book.cover_name = cover
    book.quote = text
    book.picks = json.dumps(chosen)
    book.show_numbers = bool(show_numbers)
    book.listed = bool(listed)
    book.updated_at = now
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise YearbookError("Your yearbook was just made in another tab. Reload to see it.", 409)
    # Once per book, on the first save while signing is open. A site admin's preview book, made before
    # opening day, tells friends the first time it's saved after that.
    _tell_friends(db, book, owner, now)
    return book, made


def new_link(db: Session, book, now: Optional[datetime] = None) -> str:
    """A new link. The old one stops working; notes already in stay in."""
    book.token = _new_token()
    book.opened = 0
    book.updated_at = now or _now()
    db.flush()
    return url_for(book)


def link_off(db: Session, book, now: Optional[datetime] = None) -> None:
    book.token = None
    book.updated_at = now or _now()
    db.flush()


def _notify(db: Session, user_id: int, kind: str, message: str, link: str, *, once_unread: bool = False) -> None:
    if once_unread:
        waiting = db.query(models.Notification.id).filter(
            models.Notification.user_id == user_id, models.Notification.type == kind,
            models.Notification.read_at.is_(None)).first()
        if waiting is not None:
            return
    db.add(models.Notification(user_id=user_id, type=kind, message=message[:250], link=link))


def _tell_friends(db: Session, book, owner, now: datetime) -> int:
    """Once per book: a bell note to friends that the owner's yearbook is open for signing."""
    if book.friends_told_at is not None or book.token is None or state_of(book.year, now) != "open":
        return 0
    from .crud.friends import get_friends
    told = 0
    for friend in get_friends(db, owner.id)[:FRIENDS_TOLD_MAX]:
        if not friend.is_active:
            continue
        _notify(db, friend.id, "yearbook_friend",
                f"{owner.username} opened their {book.year} yearbook. Sign it with a note?", path_for(book))
        told += 1
    book.friends_told_at = now
    return told


# ---------------------------------------------------------------- notes

def _signer_name(sig, people: dict) -> str:
    if sig.signer_id is not None:
        person = people.get(sig.signer_id)
        return person.username if person is not None else "A member"
    return sig.guest_name or "A friend"


def _people(db: Session, sigs) -> dict:
    ids = {sig.signer_id for sig in sigs if sig.signer_id is not None}
    if not ids:
        return {}
    return {person.id: person for person in db.query(models.User).filter(models.User.id.in_(ids))}


def _live(sigs, people: dict) -> list:
    """Notes from members who deactivated drop out until they come back."""
    return [sig for sig in sigs if sig.signer_id is None or (people.get(sig.signer_id) is not None
                                                              and people[sig.signer_id].is_active)]


def _note_out(sig, people: dict, *, owner_view: bool = False) -> dict:
    out = {"id": sig.id if owner_view else None, "name": _signer_name(sig, people), "guest": sig.signer_id is None,
           "note": sig.note, "superlative": SUPERLATIVE_LABEL.get(sig.superlative or ""),
           "when": _day(sig.created_at)}
    if owner_view:
        out["status"] = sig.status
        out["edited"] = bool(sig.updated_at and sig.created_at and sig.updated_at > sig.created_at + timedelta(minutes=1))
    else:
        out.pop("id")
    return out


def signatures(db: Session, book, statuses=STATUSES) -> tuple[list, dict]:
    sigs = (db.query(models.YearbookSignature)
            .filter(models.YearbookSignature.yearbook_id == book.id, models.YearbookSignature.status.in_(statuses))
            .order_by(models.YearbookSignature.created_at.desc(), models.YearbookSignature.id.desc()).all())
    people = _people(db, sigs)
    return _live(sigs, people), people


def tally(sigs) -> list[dict]:
    """Votes from shown notes, most first; ties go to whichever vote came first."""
    counts: dict[str, int] = {}
    first: dict[str, datetime] = {}
    for sig in sigs:
        if sig.status != "shown" or sig.superlative not in SUPERLATIVE_LABEL:
            continue
        counts[sig.superlative] = counts.get(sig.superlative, 0) + 1
        first[sig.superlative] = min(first.get(sig.superlative, sig.created_at), sig.created_at)
    ordered = sorted(counts, key=lambda key: (-counts[key], first[key]))
    return [{"key": key, "label": SUPERLATIVE_LABEL[key], "votes": counts[key]} for key in ordered]


def _mark(request_address: str, book) -> str:
    from .auth import SECRET_KEY
    key = SECRET_KEY.encode() if isinstance(SECRET_KEY, str) else SECRET_KEY
    return hmac.new(key, f"yearbook-guest|{book.id}|{request_address}".encode(), hashlib.sha256).hexdigest()[:32]


def mine_in(db: Session, book, user) -> Optional[models.YearbookSignature]:
    if user is None:
        return None
    return db.query(models.YearbookSignature).filter_by(yearbook_id=book.id, signer_id=user.id).first()


def sign(db: Session, book, *, user=None, guest_name=None, note, superlative=None, address: str = "",
         now: Optional[datetime] = None) -> tuple[models.YearbookSignature, bool]:
    """Leave (or, for a member, change) a note. Returns (note, new)."""
    now = now or _now()
    if book.token is None:
        raise YearbookError("This yearbook's link is off.", 404)
    if state_of(book.year, now) != "open":
        raise YearbookError("Signing closed after New Year's Day. The notes stay here to read.", 409)
    text = clean_text(note, NOTE_MAX)
    if len(text) < NOTE_MIN:
        raise YearbookError("Write a few words first.", 422)
    if has_contact(text):
        raise YearbookError("Links, email addresses and phone numbers can't go in a yearbook note.", 422)
    vote = superlative or None
    if vote is not None and vote not in SUPERLATIVE_LABEL:
        raise YearbookError("Pick one of the votes on the list, or none.", 422)
    owner = db.get(models.User, book.user_id)
    if owner is None or not owner.is_active:
        raise YearbookError("This yearbook isn't here anymore.", 404)
    if user is not None:
        if user.id == owner.id:
            raise YearbookError("This is your own yearbook. Send the link to friends so they can sign it.", 403)
        from .crud.friends import are_friends
        friend = are_friends(db, owner.id, user.id)
        existing = mine_in(db, book, user)
        if existing is not None:
            changed = existing.note != text or (existing.superlative or None) != vote
            existing.note = text
            existing.superlative = vote
            existing.updated_at = now
            # The owner let this note in as they read it. From someone who isn't their friend, new words
            # wait for the owner again, or a note could be swapped for anything once it was let in.
            if changed and existing.status == "shown" and not friend:
                existing.status = "waiting"
                _notify(db, owner.id, "yearbook_waiting",
                        f"{user.username} changed their note in your yearbook. It shows again once you let it in.",
                        "/yearbook#waiting", once_unread=True)
            db.flush()
            return existing, False
        status = "shown" if friend else "waiting"
        name = user.username
        mark = None
    else:
        name = clean_line(guest_name, GUEST_NAME_MAX)
        if not name:
            raise YearbookError("Add your name so they know who wrote it.", 422)
        if has_contact(name):
            raise YearbookError("Your name can't have a link, an email address or a phone number.", 422)
        mark = _mark(address or "unknown", book)
        status = "waiting"
    # One book at a time, so two notes landing together can't both slip past the caps.
    db.query(models.Yearbook).filter(models.Yearbook.id == book.id).with_for_update().first()
    if mark is not None:
        left = db.query(func.count(models.YearbookSignature.id)).filter(
            models.YearbookSignature.yearbook_id == book.id, models.YearbookSignature.guest_mark == mark).scalar() or 0
        if left >= GUEST_PER_ADDRESS:
            raise YearbookError("You've already left a few notes here. Make a free account to sign again.", 429)
    total = db.query(func.count(models.YearbookSignature.id)).filter(
        models.YearbookSignature.yearbook_id == book.id).scalar() or 0
    if total >= NOTES_MAX:
        raise YearbookError("This yearbook is full. That's a lot of friends.", 409)
    if status == "waiting":
        waiting = db.query(func.count(models.YearbookSignature.id)).filter(
            models.YearbookSignature.yearbook_id == book.id, models.YearbookSignature.status == "waiting").scalar() or 0
        if waiting >= WAITING_MAX:
            raise YearbookError(f"A lot of notes are waiting for {book.cover_name} to read them. Try again in a day or two.",
                                429)
    sig = models.YearbookSignature(yearbook_id=book.id, signer_id=user.id if user is not None else None,
                                   guest_name=None if user is not None else name, note=text, superlative=vote,
                                   status=status, guest_mark=mark, created_at=now, updated_at=now)
    db.add(sig)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise YearbookError("You signed this yearbook in another tab. Reload to see your note.", 409)
    if status == "shown":
        _notify(db, owner.id, "yearbook_signed", f"{name} signed your {book.year} yearbook.", "/yearbook#notes",
                once_unread=True)
    else:
        _notify(db, owner.id, "yearbook_waiting",
                f"{name} left a note in your yearbook. It shows once you let it in.", "/yearbook#waiting",
                once_unread=True)
    return sig, True


def unsign(db: Session, book, user, now: Optional[datetime] = None) -> bool:
    if state_of(book.year, now) != "open":
        raise YearbookError("Signing closed after New Year's Day, so notes can't change now.", 409)
    sig = mine_in(db, book, user)
    if sig is None:
        return False
    db.delete(sig)
    db.flush()
    return True


def moderate(db: Session, book, sig_id: int, action: str, now: Optional[datetime] = None) -> Optional[str]:
    """The owner lets a note in, hides it or deletes it. Returns the new status (None once deleted)."""
    sig = db.query(models.YearbookSignature).filter_by(id=sig_id, yearbook_id=book.id).first()
    if sig is None:
        raise YearbookError("That note isn't in your yearbook.", 404)
    if action == "delete":
        db.delete(sig)
        db.flush()
        return None
    if action not in ("show", "hide"):
        raise YearbookError("Unknown action.", 422)
    sig.status = "shown" if action == "show" else "hidden"
    db.flush()
    return sig.status


# ---------------------------------------------------------------- what pages show

def _owner_view_notes(sigs, people) -> dict:
    grouped = {status: [] for status in STATUSES}
    for sig in sigs:
        grouped[sig.status if sig.status in grouped else "waiting"].append(_note_out(sig, people, owner_view=True))
    return grouped


def friend_books(db: Session, user, year: int) -> list[dict]:
    """Friends' open yearbooks for the year, the ones the member hasn't signed first."""
    from .crud.friends import get_friends
    friends = {friend.id: friend for friend in get_friends(db, user.id)}
    if not friends:
        return []
    books = (db.query(models.Yearbook)
             .filter(models.Yearbook.user_id.in_(list(friends)), models.Yearbook.year == year,
                     models.Yearbook.token.isnot(None)).all())
    if not books:
        return []
    signed = {book_id for book_id, in db.query(models.YearbookSignature.yearbook_id).filter(
        models.YearbookSignature.signer_id == user.id,
        models.YearbookSignature.yearbook_id.in_([book.id for book in books]))}
    out = [{"name": friends[book.user_id].username, "cover": book.cover_name, "path": path_for(book),
            "signed": book.id in signed} for book in books]
    out.sort(key=lambda entry: (entry["signed"], entry["name"].lower()))
    return out[:FRIEND_BOOKS_MAX]


def unseen(db: Session, book) -> dict:
    """Notes that came in since the owner last looked: shown ones and ones waiting for them."""
    query = db.query(models.YearbookSignature.status, func.count(models.YearbookSignature.id)).filter(
        models.YearbookSignature.yearbook_id == book.id, models.YearbookSignature.status.in_(("shown", "waiting")))
    if book.seen_at is not None:
        query = query.filter(models.YearbookSignature.created_at > book.seen_at)
    counts = dict(query.group_by(models.YearbookSignature.status).all())
    waiting_all = db.query(func.count(models.YearbookSignature.id)).filter(
        models.YearbookSignature.yearbook_id == book.id, models.YearbookSignature.status == "waiting").scalar() or 0
    return {"new": int(counts.get("shown", 0)) + int(counts.get("waiting", 0)), "waiting": int(waiting_all)}


def mine(db: Session, user, year: int, now: Optional[datetime] = None, *, seen: bool = False) -> dict:
    """Everything the owner's /yearbook page needs."""
    now = now or _now()
    book = get(db, user.id, year)
    current = state_of(year, now)
    out = {
        "year": year, "state": current, "opens": _day(opens_on(year)), "closes": closes_label(year),
        "can_edit": setup_open(year, user, now), "preview": current == "soon" and can_preview(user),
        "superlatives": [{"key": key, "label": label} for key, label in SUPERLATIVES],
        "quote_ideas": list(QUOTE_IDEAS), "limits": {"cover": COVER_MAX, "quote": QUOTE_MAX, "picks": PICKS_MAX},
        "defaults": {"cover_name": user.username[:COVER_MAX]},
        "shelves_shared": len(shareable(user)),
        "friends": friend_books(db, user, year) if current in ("open", "closed") or out_preview(current, user) else [],
        "book": None,
    }
    if out["can_edit"]:
        out["options"] = pick_options(db, user, year)
    else:
        out["options"] = []
    out["numbers"] = numbers(db, user, year)
    if book is None:
        return out
    sigs, people = signatures(db, book)
    fresh = unseen(db, book)
    out["book"] = {
        "cover_name": book.cover_name, "quote": book.quote or "", "picks": _stored_picks(book),
        "pick_cards": picks_of(db, book, user), "show_numbers": bool(book.show_numbers), "listed": bool(book.listed),
        "url": url_for(book), "path": path_for(book), "opened": int(book.opened or 0),
        "card": f"{path_for(book)}/card.png" if book.token else None,
        "story": f"{path_for(book)}/story.png" if book.token else None,
        "notes": _owner_view_notes(sigs, people), "tally": tally(sigs), "new": fresh["new"],
        "seen_at": book.seen_at.isoformat() + "Z" if book.seen_at else None,
    }
    if seen:
        book.seen_at = now
        db.flush()
    return out


def out_preview(current: Optional[str], user) -> bool:
    return current == "soon" and can_preview(user)


def view(db: Session, book, viewer, now: Optional[datetime] = None) -> dict:
    """What /yearbook/<token> shows. Only shown notes; the viewer's own note comes back separately."""
    now = now or _now()
    owner = db.get(models.User, book.user_id)
    sigs, people = signatures(db, book)
    shown = [sig for sig in sigs if sig.status == "shown"]
    own = mine_in(db, book, viewer) if viewer is not None and viewer.id != book.user_id else None
    recheck = False
    if own is not None and own.status == "shown":
        from .crud.friends import are_friends
        recheck = not are_friends(db, book.user_id, viewer.id)
    return {
        "year": book.year, "cover_name": book.cover_name, "quote": book.quote or "",
        "picks": picks_of(db, book, owner),
        "numbers": numbers(db, owner, book.year) if book.show_numbers else None,
        "notes": [_note_out(sig, people) for sig in shown],
        "tally": tally(shown)[:TALLY_SHOWN],
        "state": state_of(book.year, now), "closes": closes_label(book.year), "opens": _day(opens_on(book.year)),
        "is_owner": viewer is not None and viewer.id == book.user_id,
        "own": ({"note": own.note, "superlative": own.superlative or "", "status": own.status, "recheck": recheck}
                if own is not None else None),
        "count": len(shown),
    }


def class_page(db: Session, year: int) -> list[dict]:
    """Members who chose to list their yearbook on the class page (members only), newest change first."""
    rows = (db.query(models.Yearbook, models.User)
            .join(models.User, models.User.id == models.Yearbook.user_id)
            .filter(models.Yearbook.year == year, models.Yearbook.listed.is_(True), models.Yearbook.token.isnot(None),
                    models.User.is_active.is_(True))
            .order_by(models.Yearbook.updated_at.desc()).limit(CLASS_MAX).all())
    if not rows:
        return []
    counts = dict(db.query(models.YearbookSignature.yearbook_id, func.count(models.YearbookSignature.id))
                  .filter(models.YearbookSignature.yearbook_id.in_([book.id for book, _ in rows]),
                          models.YearbookSignature.status == "shown")
                  .group_by(models.YearbookSignature.yearbook_id).all())
    return [{"cover": book.cover_name, "quote": book.quote or "", "path": path_for(book),
             "notes": int(counts.get(book.id, 0))} for book, _owner in rows]


def home(db: Session, user, now: Optional[datetime] = None) -> dict:
    """The home card: start one, what's new in yours, friends' books to sign, and the closed book after."""
    now = now or _now()
    year = season_year(now)
    if year is None:
        return {"show": False}
    current = state_of(year, now)
    book = get(db, user.id, year)
    friends = [entry for entry in friend_books(db, user, year) if not entry["signed"]] if current == "open" else []
    out = {"show": True, "year": year, "state": current, "closes": closes_label(year), "friends": friends[:3],
           "friends_total": len(friends), "new": 0, "waiting": 0, "notes": 0, "status": ""}
    if book is None:
        if current != "open":
            return {"show": False}
        out.update(stage="start", line=(f"Friends sign it with a note and a \"most likely to\" vote. Signing closes "
                                        f"{closes_label(year)}."),
                   action={"label": "Start your yearbook", "path": "/yearbook"})
        out["status"] = "new" if friends else ""
        return out
    sigs, _people = signatures(db, book, statuses=("shown",))
    fresh = unseen(db, book)
    out.update(new=fresh["new"], waiting=fresh["waiting"], notes=len(sigs))
    top = tally(sigs)[:1]
    if current == "closed":
        if not sigs:
            return {"show": False}
        line = f"Signing is closed. {_plural(len(sigs), 'note')} from the class of {year}."
        if top:
            line += f" Voted: {top[0]['label'].lower()}."
        out.update(stage="closed", line=line, action={"label": "Read it", "path": "/yearbook#notes"})
        return out
    if fresh["waiting"]:
        line = f"{_plural(fresh['waiting'], 'note')} waiting for you to let in."
        action = {"label": "Read them", "path": "/yearbook#waiting"}
    elif fresh["new"]:
        line = f"{_plural(fresh['new'], 'new note')} since you last looked. {_plural(len(sigs), 'note')} so far."
        action = {"label": "Read them", "path": "/yearbook#notes"}
    elif sigs:
        line = f"{_plural(len(sigs), 'note')} so far. Send the link to someone who hasn't signed yet."
        action = {"label": "Share the link", "path": "/yearbook#share"}
    else:
        line = "No notes yet. Send the link to the group chat and see who signs first."
        action = {"label": "Share the link", "path": "/yearbook#share"}
    if not book.token:
        line, action = "Your link is off, so nobody can sign right now.", {"label": "Turn it on", "path": "/yearbook#share"}
    out.update(stage="open", line=line, action=action)
    out["status"] = "new" if (fresh["new"] or fresh["waiting"] or friends) else ""
    return out


def card_facts(db: Session, book) -> dict:
    sigs, _people = signatures(db, book, statuses=("shown",))
    top = tally(sigs)[:1]
    return {"cover": book.cover_name, "year": book.year, "quote": book.quote or "", "notes": len(sigs),
            "top": top[0]["label"] if top else "", "state": state_of(book.year) or "open",
            "closes": closes_label(book.year),
            "votes": [[entry["label"], entry["votes"]] for entry in tally(sigs)[:TALLY_SHOWN]]}


# ---------------------------------------------------------------- email

def _link(path: str) -> str:
    from .digest import app_url
    joiner = "&" if "?" in path else "?"
    base, _, anchor = path.partition("#")
    return f"{app_url()}{base}{joiner}{UTM}" + (f"#{anchor}" if anchor else "")


def build_email(kind: str, book, user, facts: dict, unsubscribe_url: str) -> tuple[str, str, str]:
    """(subject, html, text) for "notes" (new notes while signing is open) or "closed"."""
    year = book.year
    if kind == "notes":
        waiting = facts.get("waiting", 0)
        fresh = facts.get("new", 0)
        subject = (f"{_plural(fresh, 'new note')} in your {year} yearbook" if fresh
                   else f"Notes are waiting in your {year} yearbook")
        lines = []
        if fresh:
            lines.append(f"People have been signing your yearbook: {_plural(fresh, 'note')} since you last looked.")
        if waiting:
            lines.append(f"{_plural(waiting, 'note is', 'notes are')} waiting for you to let in. Notes from people "
                         "who aren't your friends on OmniTrackr only show once you say so.")
        lines.append(f"Signing closes {closes_label(year)}, so there's still time to send the link to anyone you missed.")
        button, page = "Read your notes", _link("/yearbook#notes")
    else:
        notes = facts.get("notes", 0)
        subject = f"Your {year} yearbook is closed: {_plural(notes, 'note')} to keep"
        lines = [f"Signing closed after New Year's Day. {_plural(notes, 'person', 'people')} signed your {year} yearbook."]
        if facts.get("top"):
            lines.append(f"The class voted you: {facts['top'].lower()}.")
        lines.append("The book stays on your link for as long as you keep it on, so you can read it again next December.")
        button, page = "Open your yearbook", _link("/yearbook#notes")
    if facts.get("names"):
        lines.insert(1, "Signed by " + ", ".join(facts["names"][:5]) + (" and more." if len(facts["names"]) > 5 else "."))
    paragraph = "".join(f'<p style="color:#1f1640;font-size:15px;line-height:1.6;margin:12px 0">{escape(line)}</p>'
                        for line in lines)
    html = (
        '<html><body style="margin:0;background:#f4f2fb;font-family:Arial,Helvetica,sans-serif">'
        '<div style="max-width:560px;margin:0 auto;padding:24px">'
        '<div style="background:#14213d;border-radius:14px 14px 0 0;padding:22px 24px;color:#fff">'
        f'<div style="font-size:12px;letter-spacing:2px;color:#f5c451;text-transform:uppercase">Class of {year}</div>'
        f'<div style="font-size:22px;font-weight:700;margin-top:6px">{escape(book.cover_name)}\'s yearbook</div>'
        '</div><div style="background:#fff;border-radius:0 0 14px 14px;padding:16px 24px 24px">'
        f'{paragraph}'
        f'<p style="margin:22px 0 8px"><a href="{escape(page, quote=True)}" '
        'style="background:#7c3aed;color:#fff;padding:12px 20px;border-radius:999px;text-decoration:none;font-weight:700">'
        f'{escape(button)}</a></p>'
        '<p style="color:#6f6a8a;font-size:12px;line-height:1.5;margin-top:24px">You get this because you made a '
        'yearbook on OmniTrackr. A yearbook sends at most three emails about new notes while signing is open, and '
        'one when it closes. '
        f'<a href="{escape(unsubscribe_url, quote=True)}" style="color:#6d28d9">Unsubscribe from product updates</a>.</p>'
        '</div></div></body></html>'
    )
    text = "\n".join([f"Hi {user.username},", ""] + lines + ["", f"{button}: {page}", "",
                     f"Unsubscribe from product updates: {unsubscribe_url}"])
    return subject[:150], html, text


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


def _sent_keys(db: Session, book) -> set[str]:
    return {key for key, in db.query(models.EmailCampaignSend.campaign_key).filter(
        models.EmailCampaignSend.campaign_key.like(f"{SEND_PREFIX}{book.id}-%"),
        models.EmailCampaignSend.user_id == book.user_id)}


def email_due(db: Session, book, now: datetime) -> Optional[tuple[str, str, dict]]:
    """(kind, send key, facts) for the email this book owes its owner now, or None."""
    current = state_of(book.year, now)
    sent = _sent_keys(db, book)
    if current == "closed":
        key = f"{SEND_PREFIX}{book.id}-closed"
        if key in sent or now >= closes_at(book.year) + CLOSED_EMAIL_WITHIN or book.token is None:
            return None
        sigs, people = signatures(db, book, statuses=("shown",))
        if not sigs:
            return None
        top = tally(sigs)[:1]
        return "closed", key, {"notes": len(sigs), "top": top[0]["label"] if top else "",
                               "names": [_signer_name(sig, people) for sig in sigs]}
    if current != "open" or book.token is None:
        return None
    notes_sent = sum(1 for key in sent if key.startswith(f"{SEND_PREFIX}{book.id}-notes-"))
    if notes_sent >= NOTES_EMAILS_MAX:
        return None
    if book.last_email_at is not None and now - book.last_email_at < NOTES_EMAIL_GAP:
        return None
    query = db.query(models.YearbookSignature).filter(
        models.YearbookSignature.yearbook_id == book.id, models.YearbookSignature.status.in_(("shown", "waiting")))
    if book.seen_at is not None:
        query = query.filter(models.YearbookSignature.created_at > book.seen_at)
    if book.last_email_at is not None:
        query = query.filter(models.YearbookSignature.created_at > book.last_email_at)
    fresh = query.order_by(models.YearbookSignature.created_at).all()
    people = _people(db, fresh)
    fresh = _live(fresh, people)
    if not fresh or now - fresh[0].created_at < NOTES_EMAIL_WAIT:
        return None
    waiting = sum(1 for sig in fresh if sig.status == "waiting")
    return "notes", f"{SEND_PREFIX}{book.id}-notes-{notes_sent + 1}", {
        "new": len(fresh) - waiting, "waiting": waiting,
        "names": [_signer_name(sig, people) for sig in fresh if sig.status == "shown"]}


async def _send(to: str, subject: str, html: str, unsubscribe_url: str) -> None:
    from .digest import _send as send_mail
    await send_mail(to, subject, html, unsubscribe_url)


async def run_once(session_factory, now: Optional[datetime] = None, sender=_send) -> dict:
    """Send the emails books owe their owners, and the bell note when a book closes."""
    from .digest import mail_configured
    now = now or _now()
    result = {"books": 0, "sent": 0, "failed": 0, "closed_notes": 0, "limited": False}
    year = season_year(now)
    if year is None:
        return result
    mail_ok = emails_enabled() and (mail_configured() or sender is not _send)
    db = session_factory()
    try:
        books = (db.query(models.Yearbook).filter(models.Yearbook.year == year, models.Yearbook.token.isnot(None))
                 .order_by(models.Yearbook.id).limit(5000).all())
        due = []
        for book in books:
            result["books"] += 1
            try:
                found = email_due(db, book, now)
            except Exception as error:  # one broken book must not stop the rest
                db.rollback()
                print(f"Yearbook {book.id} check failed: {error}")
                continue
            if found is None:
                continue
            if found[0] == "closed" and book.closed_told_at is None:
                _notify(db, book.user_id, "yearbook_closed",
                        f"Your {book.year} yearbook is closed: {_plural(found[2]['notes'], 'note')} to keep.",
                        "/yearbook#notes")
                book.closed_told_at = now
                # Saved now: a later book's failed check rolls the session back, which would take this
                # bell note with it while its email still went out.
                db.commit()
                result["closed_notes"] += 1
            due.append((book.id, *found))
        db.commit()
        if not mail_ok:
            return result
        from .announcements import unsubscribe_token
        from .digest import app_url
        from .email_quota import lock_email_budget
        for book_id, kind, key, facts in due:
            if result["sent"] + result["failed"] >= PER_RUN_LIMIT:
                result["limited"] = True
                break
            book = db.get(models.Yearbook, book_id)
            user = db.get(models.User, book.user_id) if book is not None else None
            if book is None or user is None or not user.is_active or not user.is_verified or not user.email \
                    or _opted_out(db, user.id):
                continue
            if db.query(models.EmailCampaignSend.id).filter_by(campaign_key=key, user_id=user.id).first() is not None:
                continue
            lock_email_budget(db)
            if allowance(db, now) <= 0:
                db.rollback()
                result["limited"] = True
                break
            db.add(models.EmailCampaignSend(campaign_key=key, user_id=user.id, status="sent", sent_at=now))
            book.last_email_at = now
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                continue
            try:
                unsubscribe_url = f"{app_url()}/email/updates/unsubscribe?token={unsubscribe_token(user.id)}"
                subject, html, _text = build_email(kind, book, user, facts, unsubscribe_url)
                await sender(user.email, subject, html, unsubscribe_url)
                result["sent"] += 1
                count("yearbook_email_sent")
            except Exception as error:  # one bad address must not stop the rest
                print(f"Yearbook email to user {user.id} failed: {error}")
                result["failed"] += 1
        return result
    finally:
        db.close()


async def yearbook_loop(app) -> None:
    """Background task started with the app; never raises."""
    from .database import SessionLocal
    await asyncio.sleep(FIRST_CHECK_DELAY_SECONDS)
    while True:
        try:
            result = await run_once(SessionLocal)
            if result["sent"] or result["failed"] or result["closed_notes"]:
                print(f"Yearbook: {result}")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"Yearbook check failed: {error}")
        await asyncio.sleep(CHECK_EVERY_SECONDS)
