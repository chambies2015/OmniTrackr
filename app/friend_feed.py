"""Friends feed: what friends recently added, finished, rated and reviewed (Oct 2026).

The feed only shows what a friend can already open from the Friends panel: titles in
categories the member hasn't made private, with their current finished flag, rating
and review. Activity Journal entries and completion moments stay private and are
never read here.

* Adds come straight from each library entry's ``added_at``.
* Finishes, ratings and reviews of titles already in the library are noted in
  ``friend_feed_events`` by a flush hook as the change is saved. An event is shown
  only while the entry still says so: un-ticking Watched or clearing a rating hides it.
* A member can switch sharing off from the feed. After switching it back on, only
  updates from then on are shown.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import event, func, or_, select
from sqlalchemy.orm import Session, attributes

from . import models, review_spoilers, title_pages
from .for_you import CREATOR_FIELD, IMAGE_FIELD, LABELS, LIBRARY

logger = logging.getLogger(__name__)

WINDOW = timedelta(days=30)
PAGE_SIZE = 20
ROWS_PER_CATEGORY = 300
BURST_MIN = 4  # This many plain adds by one friend on one day become a single "added N titles" card.
BURST_SHOWN = 6
REVIEW_EXCERPT = 280
DONE_FIELD = {"movies": "watched", "tv-shows": "watched", "anime": "watched",
              "video-games": "played", "music": "listened", "books": "read",
              "manga": "read"}
PRIVATE_FLAG = {category: category.replace("-", "_") + "_private" for category in LIBRARY}
_CATEGORY_BY_MODEL = {model: category for category, (model, _fields) in LIBRARY.items()}
KIND_RANK = {"added": 0, "rated": 1, "reviewed": 2, "finished": 3}


# ---------------------------------------------------------------- recording

def _saved_values(session: Session, obj, names: tuple) -> dict:
    """The stored values of the watched attributes, read only when some changed without a loaded old value."""
    needed = [name for name in names if attributes.get_history(obj, name).has_changes()
              and not attributes.get_history(obj, name).deleted]
    if not needed:
        return {}
    model = type(obj)
    with session.no_autoflush:
        row = session.execute(select(*(getattr(model, name) for name in needed)).where(model.id == obj.id)).first()
    return dict(zip(needed, row)) if row is not None else {}


def events_for(obj, session: Optional[Session] = None) -> Optional[str]:
    """The feed event a pending change to a library entry makes, if any: finished > reviewed > rated."""
    category = _CATEGORY_BY_MODEL.get(type(obj))
    if category is None or obj.id is None or obj.user_id is None:
        return None
    done_field = DONE_FIELD[category]
    saved = _saved_values(session, obj, (done_field, "review", "rating")) if session is not None else {}

    def changed(name):
        history = attributes.get_history(obj, name)
        if not history.has_changes():
            return None
        if history.deleted:
            return history.deleted[0], getattr(obj, name)
        if name in saved:
            return saved[name], getattr(obj, name)
        return None  # Old value unknown: say nothing rather than guess.

    done = changed(done_field)
    if done and done[1] and not done[0]:
        return "finished"
    review = changed("review")
    if review and (review[1] or "").strip() and not (review[0] or "").strip():
        return "reviewed"
    rating = changed("rating")
    if rating and rating[1] is not None and rating[1] != rating[0]:
        return "rated"
    return None


@event.listens_for(Session, "before_flush")
def _record(session: Session, flush_context, instances) -> None:
    # A feed row must never stop a library save.
    try:
        for obj in list(session.dirty):
            if type(obj) not in _CATEGORY_BY_MODEL or not session.is_modified(obj):
                continue
            kind = events_for(obj, session)
            if kind:
                session.add(models.FriendFeedEvent(user_id=obj.user_id, category=_CATEGORY_BY_MODEL[type(obj)],
                                                   item_id=obj.id, kind=kind, created_at=datetime.utcnow()))
    except Exception:
        logger.exception("Could not note a friends feed event")


# ---------------------------------------------------------------- reading

def friend_ids(db: Session, user_id: int) -> set[int]:
    pairs = db.query(models.Friendship.user1_id, models.Friendship.user2_id).filter(
        or_(models.Friendship.user1_id == user_id, models.Friendship.user2_id == user_id)).all()
    return {a if b == user_id else b for a, b in pairs} - {user_id}


def sharing(db: Session, user_id: int) -> bool:
    row = db.query(models.FriendFeedSetting.sharing).filter(models.FriendFeedSetting.user_id == user_id).first()
    return True if row is None else bool(row[0])


def set_sharing(db: Session, user_id: int, value: bool) -> bool:
    row = db.query(models.FriendFeedSetting).filter(models.FriendFeedSetting.user_id == user_id).first()
    if row is None:
        if value:
            return True  # No row already means sharing; keep earlier updates visible.
        row = models.FriendFeedSetting(user_id=user_id, sharing=value)
        db.add(row)
    elif bool(row.sharing) != value:
        row.sharing = value
        row.changed_at = datetime.utcnow()
    db.commit()
    return value


@dataclass
class Entry:
    friend_id: int
    category: str
    item: object
    kind: str
    at: datetime


@dataclass
class Burst:
    friend_id: int
    at: datetime
    entries: list = field(default_factory=list)


def _visible_friends(db: Session, viewer_id: int) -> tuple[dict, dict]:
    """Active friends who share their feed, and the earliest update to show for each."""
    ids = friend_ids(db, viewer_id)
    if not ids:
        return {}, {}
    friends = {friend.id: friend for friend in db.query(models.User).filter(
        models.User.id.in_(ids), models.User.is_active.is_(True)).all()}
    since = {}
    for user_id, on, changed_at in db.query(models.FriendFeedSetting.user_id, models.FriendFeedSetting.sharing,
                                            models.FriendFeedSetting.changed_at).filter(
            models.FriendFeedSetting.user_id.in_(list(friends) or [0])):
        if not on:
            friends.pop(user_id, None)
        elif changed_at is not None:
            since[user_id] = changed_at
    return friends, since


def _still_true(category: str, item, kind: str) -> bool:
    if kind == "finished":
        return bool(getattr(item, DONE_FIELD[category], False))
    if kind == "reviewed":
        return bool((item.review or "").strip())
    if kind == "rated":
        return item.rating is not None
    return True


def collect(db: Session, viewer_id: int, now: Optional[datetime] = None) -> tuple[list, dict]:
    """Every feed card in the window, newest first, plus the friends they belong to."""
    now = now or datetime.utcnow()
    start = now - WINDOW
    friends, since = _visible_friends(db, viewer_id)
    if not friends:
        return [], friends
    best: dict[tuple, Entry] = {}

    def offer(entry: Entry) -> None:
        if entry.at < since.get(entry.friend_id, start) or entry.at < start or entry.at > now:
            return
        key = (entry.friend_id, entry.category, entry.item.id)
        current = best.get(key)
        if current is None or (entry.at, KIND_RANK[entry.kind]) > (current.at, KIND_RANK[current.kind]):
            best[key] = entry

    for category, (model, _fields) in LIBRARY.items():
        visible = [fid for fid, friend in friends.items() if not getattr(friend, PRIVATE_FLAG[category], False)]
        if not visible:
            continue
        titled = (model.title.isnot(None), func.trim(model.title) != "")
        for item in db.query(model).filter(model.user_id.in_(visible), model.added_at >= start,
                                           model.added_at <= now, *titled).order_by(
                model.added_at.desc(), model.id.desc()).limit(ROWS_PER_CATEGORY):
            offer(Entry(item.user_id, category, item, "added", item.added_at))
        rows = db.query(models.FriendFeedEvent).filter(
            models.FriendFeedEvent.user_id.in_(visible), models.FriendFeedEvent.category == category,
            models.FriendFeedEvent.created_at >= start).order_by(
            models.FriendFeedEvent.created_at.desc(), models.FriendFeedEvent.id.desc()).limit(ROWS_PER_CATEGORY).all()
        if not rows:
            continue
        items = {item.id: item for item in db.query(model).filter(
            model.id.in_({row.item_id for row in rows}), model.user_id.in_(visible), *titled)}
        for row in rows:
            item = items.get(row.item_id)
            # A reused id must not pick up an event from a deleted entry.
            if item is None or item.user_id != row.user_id or (item.added_at and item.added_at > row.created_at):
                continue
            if _still_true(category, item, row.kind):
                offer(Entry(row.user_id, category, item, row.kind, row.created_at))

    cards: list = []
    plain_adds: dict[tuple, list] = {}
    for entry in best.values():
        if entry.kind == "added" and entry.item.rating is None and not getattr(entry.item, DONE_FIELD[entry.category], False):
            plain_adds.setdefault((entry.friend_id, entry.at.date()), []).append(entry)
        else:
            cards.append(entry)
    for (friend_id, _day), entries in plain_adds.items():
        if len(entries) >= BURST_MIN:
            entries.sort(key=lambda e: (e.at, e.item.id), reverse=True)
            cards.append(Burst(friend_id, entries[0].at, entries))
        else:
            cards.extend(entries)
    cards.sort(key=lambda card: (card.at, card.friend_id), reverse=True)
    return cards, friends


def _title_paths(db: Session, entries: list[Entry]) -> dict[tuple, Optional[str]]:
    """Public title page paths for these entries, one lookup per kind."""
    wanted: dict[str, dict[str, list]] = {}
    for entry in entries:
        kind = title_pages.LIBRARY_TO_KIND[entry.category]
        path = title_pages.path_for_item(kind, entry.item)
        wanted.setdefault(kind, {}).setdefault(path.rsplit("/", 1)[1], []).append(entry)
    paths = {}
    for kind, by_slug in wanted.items():
        found = title_pages.find_many(db, kind, list(by_slug))
        for slug, group_entries in by_slug.items():
            group = found.get(slug)
            for entry in group_entries:
                paths[(entry.category, entry.item.id)] = group.path if group is not None else None
    return paths


def _year(category: str, item) -> Optional[int]:
    if category == "video-games":
        value = getattr(item, "release_date", None)
        return value.year if value else None
    year = getattr(item, "year", None)
    return year if isinstance(year, int) and year > 0 else None


def _owned(db: Session, viewer_id: int, entries: list[Entry]) -> set[tuple]:
    owned = set()
    by_category: dict[str, set] = {}
    for entry in entries:
        by_category.setdefault(entry.category, set()).add(entry.item.title.strip().lower())
    for category, titles in by_category.items():
        model = LIBRARY[category][0]
        for (title,) in db.query(func.lower(func.trim(model.title))).filter(
                model.user_id == viewer_id, func.lower(func.trim(model.title)).in_(titles)):
            owned.add((category, title))
    return owned


def _excerpt(text: Optional[str]) -> Optional[str]:
    text = " ".join((text or "").split())
    if not text:
        return None
    return text if len(text) <= REVIEW_EXCERPT else text[:REVIEW_EXCERPT - 1].rstrip() + "…"


def _friend(user) -> dict:
    return {"id": user.id, "username": user.username, "avatar": user.profile_picture_url or None}


def page(db: Session, viewer_id: int, before: Optional[datetime] = None, limit: int = PAGE_SIZE,
         now: Optional[datetime] = None) -> dict:
    cards, friends = collect(db, viewer_id, now)
    if before is not None:
        cards = [card for card in cards if card.at < before]
    shown, more = cards[:limit], len(cards) > limit
    singles = [card for card in shown if isinstance(card, Entry)]
    in_bursts = [entry for card in shown if isinstance(card, Burst) for entry in card.entries[:BURST_SHOWN]]
    paths = _title_paths(db, singles + in_bursts)
    owned = _owned(db, viewer_id, singles)
    spoilers, cheers, mine = set(), {}, set()
    if singles:
        keys = {(entry.category, entry.item.id) for entry in singles}
        item_ids = list({item_id for _category, item_id in keys})
        review_category = {library: review for _kind, (_m, review, library, _l, _c) in title_pages.KINDS.items()}
        marked = review_spoilers.flagged(db, [(review_category[e.category], e.item.id) for e in singles if e.item.review])
        spoilers = {(e.category, e.item.id) for e in singles
                    if marked.get((review_category[e.category], e.item.id)) == e.friend_id}
        for category, item_id, user_id in db.query(models.FriendFeedCheer.category, models.FriendFeedCheer.item_id,
                                                   models.FriendFeedCheer.user_id).filter(
                models.FriendFeedCheer.item_id.in_(item_ids),
                models.FriendFeedCheer.owner_id.in_({entry.friend_id for entry in singles})):
            if (category, item_id) in keys:
                cheers[(category, item_id)] = cheers.get((category, item_id), 0) + 1
                if user_id == viewer_id:
                    mine.add((category, item_id))

    items = []
    for card in shown:
        friend = _friend(friends[card.friend_id])
        if isinstance(card, Burst):
            items.append({
                "type": "burst", "id": f"burst-{card.friend_id}-{card.at.date().isoformat()}",
                "friend": friend, "at": card.at.isoformat(), "count": len(card.entries),
                "titles": [{"title": e.item.title.strip(), "category": e.category,
                            "category_label": LABELS[e.category],
                            "image": title_pages._safe_image(getattr(e.item, IMAGE_FIELD[e.category], None)),
                            "title_path": paths.get((e.category, e.item.id))}
                           for e in card.entries[:BURST_SHOWN]],
            })
            continue
        item, category = card.item, card.category
        key = (category, item.id)
        review = _excerpt(item.review)
        creator = getattr(item, CREATOR_FIELD.get(category, ""), None) if category in CREATOR_FIELD else None
        items.append({
            "type": "title", "id": f"{category}-{item.id}", "friend": friend, "at": card.at.isoformat(),
            "kind": card.kind, "category": category, "category_label": LABELS[category], "item_id": item.id,
            "title": item.title.strip(), "year": _year(category, item), "creator": (creator or "").strip() or None,
            "image": title_pages._safe_image(getattr(item, IMAGE_FIELD[category], None)),
            "finished": bool(getattr(item, DONE_FIELD[category], False)), "rating": item.rating,
            "review": review, "spoiler": bool(review) and key in spoilers,
            "title_path": paths.get(key), "in_library": (category, item.title.strip().lower()) in owned,
            "cheers": cheers.get(key, 0), "cheered": key in mine,
        })
    return {"items": items, "next_before": shown[-1].at.isoformat() if more and shown else None,
            "friends": len(friends_of_viewer(db, viewer_id))}


def friends_of_viewer(db: Session, viewer_id: int) -> set[int]:
    """Active friends, whether or not they share a feed (for the empty state)."""
    ids = friend_ids(db, viewer_id)
    if not ids:
        return set()
    return {row[0] for row in db.query(models.User.id).filter(models.User.id.in_(ids), models.User.is_active.is_(True))}


def visible_item(db: Session, viewer_id: int, friend_id: int, category: str, item_id: int):
    """A friend's library entry the viewer may act on from the feed, or None."""
    if category not in LIBRARY or friend_id not in friends_of_viewer(db, viewer_id):
        return None
    friend = db.get(models.User, friend_id)
    if friend is None or getattr(friend, PRIVATE_FLAG[category], False):
        return None
    model = LIBRARY[category][0]
    item = db.query(model).filter(model.id == item_id, model.user_id == friend_id).first()
    if item is None or not (item.title or "").strip():
        return None
    return item
