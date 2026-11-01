"""Why a member added a title: who recommended it, or where they came across it.

One private row per library record (``models.TitleOrigin``). Members fill it in from
the title's More menu; titles added from a friend recommendation, the friends feed or
a shared list get it filled in for them. Nothing here is shown to anyone but the owner.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from . import models
from .crud.friends import are_friends

SOURCES = {
    "friend": "A friend on OmniTrackr",
    "person": "Someone I know",
    "article": "An article or website",
    "video": "A video, podcast or stream",
    "browsing": "I came across it",
    "other": "Something else",
}
# Sources that name a person, so they count towards "recommended by".
PEOPLE = {"friend", "person"}
WHO_MAX = 60
NOTE_MAX = 280
LIBRARY = {
    "movies": (models.Movie, "watched"), "tv-shows": (models.TVShow, "watched"),
    "anime": (models.Anime, "watched"), "video-games": (models.VideoGame, "played"),
    "music": (models.Music, "listened"), "books": (models.Book, "read"),
    "manga": (models.Manga, "read"), "podcasts": (models.Podcast, "listened"),
    "audiobooks": (models.Audiobook, "listened"),
}


class OriginError(ValueError):
    pass


def tidy(value: Optional[str], limit: int, label: str) -> str:
    text = " ".join(str(value or "").split())
    if text and not text.isprintable():
        raise OriginError(f"The {label} can't contain hidden characters")
    if len(text) > limit:
        raise OriginError(f"Keep the {label} to {limit} characters")
    return text


def who_key(name: str) -> str:
    return name.casefold()[:WHO_MAX]


def _friend(db: Session, user_id: int, friend_id: Optional[int]) -> Optional[models.User]:
    if not friend_id or friend_id == user_id:
        return None
    friend = db.get(models.User, friend_id)
    if friend is None or not friend.is_active or not are_friends(db, user_id, friend_id):
        return None
    return friend


def serialize(db: Session, origin: Optional[models.TitleOrigin], friends: Optional[dict] = None) -> Optional[dict]:
    if origin is None:
        return None
    friend = None
    if origin.friend_id:
        user = friends.get(origin.friend_id) if friends is not None else db.get(models.User, origin.friend_id)
        if user is not None and user.is_active:
            friend = {"id": user.id, "username": user.username}
    return {
        "source": origin.source,
        "source_label": SOURCES.get(origin.source, SOURCES["other"]),
        "friend": friend,
        # A linked friend shows under their current username.
        "who": friend["username"] if friend else (origin.who or ""),
        "who_key": origin.who_key or "",
        "note": origin.note or "",
        "updated_at": origin.updated_at.isoformat() if origin.updated_at else None,
    }


def origins_for(db: Session, user_id: int, category: str, item_ids: Iterable[int]) -> dict[int, dict]:
    ids = list(item_ids)
    if not ids:
        return {}
    rows = db.query(models.TitleOrigin).filter(
        models.TitleOrigin.user_id == user_id, models.TitleOrigin.category == category,
        models.TitleOrigin.item_id.in_(ids),
    ).all()
    friend_ids = {row.friend_id for row in rows if row.friend_id}
    friends = {user.id: user for user in db.query(models.User).filter(models.User.id.in_(friend_ids))} if friend_ids else {}
    return {row.item_id: serialize(db, row, friends) for row in rows}


def get(db: Session, user_id: int, category: str, item_id: int) -> Optional[models.TitleOrigin]:
    return db.query(models.TitleOrigin).filter_by(user_id=user_id, category=category, item_id=item_id).first()


def save(db: Session, user_id: int, category: str, item_id: int, source: str,
         friend_id: Optional[int] = None, who: Optional[str] = None, note: Optional[str] = None) -> models.TitleOrigin:
    """Set one title's origin, replacing any earlier one. Does not commit.

    A friend link is kept only for a current friend; otherwise the name is kept as
    plain text, the same as a typed name.
    """
    if source not in SOURCES:
        raise OriginError("Pick where this title came from")
    who_text = tidy(who, WHO_MAX, "name")
    note_text = tidy(note, NOTE_MAX, "note")
    friend = _friend(db, user_id, friend_id) if source == "friend" else None
    if friend is not None:
        who_text = friend.username
    elif source == "friend":
        if not who_text:
            raise OriginError("Pick a friend, or choose \"Someone I know\" and type their name")
        source = "person"
    if source == "person" and not who_text:
        raise OriginError("Add the name of who recommended it")
    origin = get(db, user_id, category, item_id)
    now = datetime.utcnow()
    if origin is None:
        origin = models.TitleOrigin(user_id=user_id, category=category, item_id=item_id, created_at=now)
        db.add(origin)
    origin.source = source
    origin.friend_id = friend.id if friend is not None else None
    origin.who = who_text or None
    origin.who_key = who_key(who_text) if who_text else None
    origin.note = note_text or None
    origin.updated_at = now
    return origin


def prefill(db: Session, user_id: int, category: str, item_id: int, source: str,
            friend: Optional[models.User] = None, note: Optional[str] = None) -> Optional[models.TitleOrigin]:
    """Record where an automatically added title came from, unless the member already said. Does not commit."""
    if category not in LIBRARY or get(db, user_id, category, item_id) is not None:
        return None
    if friend is not None and not (friend.is_active and are_friends(db, user_id, friend.id)):
        friend = None
    if source == "friend" and friend is None:
        return None
    now = datetime.utcnow()
    origin = models.TitleOrigin(
        user_id=user_id, category=category, item_id=item_id, source=source,
        friend_id=friend.id if friend is not None else None,
        who=friend.username if friend is not None else None,
        who_key=who_key(friend.username) if friend is not None else None,
        note=(" ".join((note or "").split())[:NOTE_MAX] or None), created_at=now, updated_at=now,
    )
    db.add(origin)
    return origin


def _people(db: Session, user_id: int, category: Optional[str] = None):
    query = db.query(models.TitleOrigin).filter(
        models.TitleOrigin.user_id == user_id, models.TitleOrigin.source.in_(PEOPLE),
        models.TitleOrigin.who_key.isnot(None),
    )
    if category:
        query = query.filter(models.TitleOrigin.category == category)
    return query.all()


def _display_names(db: Session, origins: list[models.TitleOrigin]) -> dict[str, str]:
    """The name to show for each recommender: a friend's current username, else the newest spelling typed."""
    friend_ids = {row.friend_id for row in origins if row.friend_id}
    friends = {user.id: user for user in db.query(models.User).filter(models.User.id.in_(friend_ids))} if friend_ids else {}
    names: dict[str, tuple[int, datetime, str]] = {}
    for row in origins:
        user = friends.get(row.friend_id) if row.friend_id else None
        name = user.username if user is not None and user.is_active else row.who
        rank = (1 if user is not None and user.is_active else 0, row.updated_at or datetime.min, name)
        if row.who_key not in names or rank[:2] > names[row.who_key][:2]:
            names[row.who_key] = rank
    return {key: value[2] for key, value in names.items()}


def shelf_people(db: Session, user_id: int, category: str) -> list[dict]:
    """Recommenders on one shelf, for the "Recommended by" filter, most titles first."""
    rows = _people(db, user_id, category)
    names = _display_names(db, rows)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.who_key] = counts.get(row.who_key, 0) + 1
    ordered = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return [{"key": key, "name": names[key], "count": count} for key, count in ordered]


def recommenders(db: Session, user_id: int, limit: int = 8) -> dict:
    """Whose recommendations the member finished and rated highest, across every shelf."""
    rows = _people(db, user_id)
    names = _display_names(db, rows)
    by_category: dict[str, list[models.TitleOrigin]] = {}
    for row in rows:
        by_category.setdefault(row.category, []).append(row)
    stats: dict[str, dict] = {}
    for category, origins in by_category.items():
        if category not in LIBRARY:
            continue
        model, done = LIBRARY[category]
        found = {item.id: item for item in db.query(model).filter(
            model.user_id == user_id, model.id.in_([row.item_id for row in origins]))}
        for row in origins:
            item = found.get(row.item_id)
            if item is None:
                continue
            entry = stats.setdefault(row.who_key, {
                "key": row.who_key, "name": names[row.who_key], "titles": 0, "finished": 0,
                "rated": 0, "rating_total": 0.0, "shelves": {}, "best": None,
            })
            entry["titles"] += 1
            entry["shelves"][category] = entry["shelves"].get(category, 0) + 1
            if getattr(item, done, False):
                entry["finished"] += 1
                if item.rating is not None:
                    entry["rated"] += 1
                    entry["rating_total"] += float(item.rating)
                    if entry["best"] is None or item.rating > entry["best"]["rating"]:
                        entry["best"] = {"title": item.title, "rating": float(item.rating), "category": category}
    people = []
    for entry in stats.values():
        average = round(entry["rating_total"] / entry["rated"], 1) if entry["rated"] else None
        shelf = max(entry["shelves"].items(), key=lambda pair: (pair[1], pair[0]))[0]
        people.append({
            "key": entry["key"], "name": entry["name"], "titles": entry["titles"],
            "finished": entry["finished"], "rated": entry["rated"], "average_rating": average,
            "best": entry["best"], "top_shelf": shelf,
        })
    # Rated picks first, highest average first; then by how many you finished.
    people.sort(key=lambda p: (p["average_rating"] is None, -(p["average_rating"] or 0), -p["finished"],
                               -p["titles"], p["name"].casefold()))
    return {"people": people[:limit], "total_people": len(people),
            "total_titles": sum(p["titles"] for p in people)}


# ---------------------------------------------------------------- backups

def export_rows(db: Session, user_id: int, identity) -> list[dict]:
    """Every origin with enough of its title to find it again on import.

    ``identity(media, category)`` returns the edition fields the JSON backup uses
    elsewhere. A friend link is written as the friend's username.
    """
    origins = db.query(models.TitleOrigin).filter(models.TitleOrigin.user_id == user_id).order_by(
        models.TitleOrigin.category, models.TitleOrigin.item_id).all()
    by_category: dict[str, list[models.TitleOrigin]] = {}
    for row in origins:
        by_category.setdefault(row.category, []).append(row)
    exported = []
    for category, rows in by_category.items():
        if category not in LIBRARY:
            continue
        model = LIBRARY[category][0]
        found = {item.id: item for item in db.query(model).filter(
            model.user_id == user_id, model.id.in_([row.item_id for row in rows]))}
        for row in rows:
            media = found.get(row.item_id)
            if media is None:
                continue
            shown = serialize(db, row)
            exported.append({
                "category": category, "title": media.title, **identity(media, category),
                "source": row.source, "who": shown["who"], "note": row.note or "",
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            })
    return exported


def import_row(db: Session, user_id: int, category: str, item_id: int, raw: dict) -> bool:
    """Restore one backed-up origin onto an owned title that has none. Does not commit."""
    if get(db, user_id, category, item_id) is not None:
        return False
    source = raw.get("source")
    who = raw.get("who") if isinstance(raw.get("who"), str) else ""
    note = raw.get("note") if isinstance(raw.get("note"), str) else ""
    if source not in SOURCES:
        return False
    friend_id = None
    if source == "friend":
        # Relink by username when that person is still a friend; otherwise keep the name.
        match = db.query(models.User).filter(models.User.username == who.strip()).first() if who.strip() else None
        friend_id = match.id if match is not None else None
    try:
        save(db, user_id, category, item_id, source, friend_id=friend_id, who=who[:WHO_MAX], note=note[:NOTE_MAX])
    except OriginError:
        return False
    return True
