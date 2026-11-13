"""Private ratings and notes on single episodes of TV shows and anime.

Each row belongs to one member and one library record, and is read and written
only through the owner's own episode guide. Nothing here touches the show's
rating, review, finished status or progress checkpoint.

Episodes are named the way the guide numbers them. ``season`` is None for a
show numbered straight through (most anime, or a show with only an episode
count), 0 for specials, and the season number otherwise.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Callable, Optional

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models
from .progress import _owned_item, lock_progress_owner

CATEGORIES = {"tv-shows": models.TVShow, "anime": models.Anime}
MAX_NOTE = 1000
MAX_PER_SHOW = 3000
MAX_PER_MEMBER = 50000

Season = Annotated[int, Field(ge=0, le=10000)]
Episode = Annotated[int, Field(ge=1, le=1000000)]


class EpisodeRef(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    season: Season | None = None
    episode: Episode


class EpisodeNoteWrite(EpisodeRef):
    """Save a rating, a note, or both. Leaving both empty removes the episode's entry."""
    rating: Annotated[int, Field(ge=1, le=10)] | None = None
    note: Annotated[str, Field(max_length=MAX_NOTE)] | None = None
    spoiler: bool = False

    @field_validator("note")
    @classmethod
    def tidy_note(cls, value):
        if value is None:
            return None
        # Keep line breaks, drop other control characters and trailing space.
        cleaned = "".join(ch for ch in value if ch in "\n\t" or ch.isprintable()).strip()
        return cleaned or None


def episode_key(season: Optional[int], episode: int) -> str:
    return f"e{episode}" if season is None else f"s{season}e{episode}"


def _iso(moment: Optional[datetime]) -> Optional[str]:
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.isoformat().replace("+00:00", "Z")


def serialize(row: models.EpisodeNote) -> dict:
    return {
        "season": row.season,
        "episode": row.episode,
        "rating": row.rating,
        "note": row.note,
        "spoiler": bool(row.spoiler),
        "updated_at": _iso(row.updated_at),
    }


def _rows(db: Session, user_id: int, category: str, item_id: int):
    return db.query(models.EpisodeNote).filter(
        models.EpisodeNote.user_id == user_id,
        models.EpisodeNote.category == category,
        models.EpisodeNote.item_id == item_id,
    )


def for_item(db: Session, user_id: int, category: str, item_id: int) -> list[dict]:
    """All of one member's entries for one show, in watching order."""
    rows = _rows(db, user_id, category, item_id).all()
    rows.sort(key=lambda row: (row.season is None, row.season or 0, row.episode))
    return [serialize(row) for row in rows]


def summary(entries: list[dict]) -> dict:
    """Counts and the average for the guide's header."""
    rated = [entry["rating"] for entry in entries if entry["rating"] is not None]
    return {
        "rated": len(rated),
        "noted": sum(1 for entry in entries if entry["note"]),
        "average": round(sum(rated) / len(rated), 1) if rated else None,
    }


def counts_by_item(db: Session, user_id: int) -> dict[tuple[str, int], int]:
    """How many episodes a member has rated or noted, per show. One grouped query."""
    return {
        (category, item_id): count
        for category, item_id, count in db.query(
            models.EpisodeNote.category, models.EpisodeNote.item_id, func.count(models.EpisodeNote.id),
        ).filter(models.EpisodeNote.user_id == user_id).group_by(
            models.EpisodeNote.category, models.EpisodeNote.item_id,
        )
    }


def _check_category(category: str) -> None:
    if category not in CATEGORIES:
        raise HTTPException(422, "Episode ratings are available for TV shows and anime")


def save(db: Session, user_id: int, category: str, item_id: int, payload: EpisodeNoteWrite) -> None:
    """Create, change or remove one episode's entry. Last write wins for that episode."""
    _check_category(category)
    key = episode_key(payload.season, payload.episode)
    empty = payload.rating is None and payload.note is None
    for attempt in range(2):
        try:
            lock_progress_owner(db, user_id)
            _owned_item(db, user_id, category, item_id, lock=True)
            row = _rows(db, user_id, category, item_id).filter(
                models.EpisodeNote.episode_key == key).populate_existing().with_for_update().first()
            if empty:
                if row is not None:
                    db.delete(row)
                db.commit()
                return
            now = datetime.utcnow()
            if row is None:
                if _rows(db, user_id, category, item_id).count() >= MAX_PER_SHOW:
                    raise HTTPException(422, "This show already has as many episode notes as it can hold.")
                total = db.query(func.count(models.EpisodeNote.id)).filter(
                    models.EpisodeNote.user_id == user_id).scalar() or 0
                if total >= MAX_PER_MEMBER:
                    raise HTTPException(422, "Your account already has as many episode notes as it can hold.")
                row = models.EpisodeNote(user_id=user_id, category=category, item_id=item_id, episode_key=key,
                                         season=payload.season, episode=payload.episode, created_at=now)
                db.add(row)
            row.rating = payload.rating
            row.note = payload.note
            row.spoiler = bool(payload.spoiler and payload.note)
            row.updated_at = now
            db.commit()
            return
        except IntegrityError:
            # Two tabs created the same episode's entry at once: the second one updates it.
            db.rollback()
            if attempt:
                raise HTTPException(409, "That episode changed in another tab. Try again.")
        except Exception:
            db.rollback()
            raise


def remove(db: Session, user_id: int, category: str, item_id: int, ref: EpisodeRef) -> None:
    _check_category(category)
    try:
        lock_progress_owner(db, user_id)
        _owned_item(db, user_id, category, item_id, lock=True)
        _rows(db, user_id, category, item_id).filter(
            models.EpisodeNote.episode_key == episode_key(ref.season, ref.episode),
        ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------------- backups

def export_rows(db: Session, user_id: int, identity: Callable[[Any, str], dict] | None = None) -> list[dict]:
    """One row per show, named by title so a backup can be restored into another account."""
    grouped: dict[tuple[str, int], list[dict]] = {}
    for row in db.query(models.EpisodeNote).filter(models.EpisodeNote.user_id == user_id).order_by(
            models.EpisodeNote.category, models.EpisodeNote.item_id, models.EpisodeNote.id):
        grouped.setdefault((row.category, row.item_id), []).append(serialize(row))
    exported = []
    for category, model in CATEGORIES.items():
        ids = [item_id for (key, item_id) in grouped if key == category]
        if not ids:
            continue
        for start in range(0, len(ids), 500):
            for media in db.query(model).filter(model.user_id == user_id, model.id.in_(ids[start:start + 500])).order_by(model.id):
                entries = grouped[(category, media.id)]
                entries.sort(key=lambda entry: (entry["season"] is None, entry["season"] or 0, entry["episode"]))
                row = {"category": category, "title": media.title, "episodes": entries}
                if identity is not None:
                    row.update(identity(media, category))
                exported.append(row)
    return exported


def stage_import(db: Session, user_id: int, item_id: int, category: str, entries: Any,
                 have: set[tuple[str, int, str]], budget: list[int]) -> tuple[int, int]:
    """Add backed-up entries to one owned show, keeping every entry it already has.

    ``have`` holds the member's existing (category, item_id, key) triples and
    ``budget`` the remaining room under MAX_PER_MEMBER; both are updated. The
    caller has locked the owner and commits.
    """
    created = skipped = 0
    per_show = sum(1 for (cat, item, _) in have if cat == category and item == item_id)
    for raw in entries if isinstance(entries, list) else []:
        try:
            if not isinstance(raw, dict):
                raise ValueError
            data = EpisodeNoteWrite.model_validate({
                field: raw.get(field) for field in ("season", "episode", "rating", "note", "spoiler")
                if field in raw and not (field == "spoiler" and raw.get(field) is None)
            })
        except (ValueError, TypeError):
            skipped += 1
            continue
        key = episode_key(data.season, data.episode)
        if (data.rating is None and data.note is None) or (category, item_id, key) in have \
                or per_show >= MAX_PER_SHOW or budget[0] <= 0:
            skipped += 1
            continue
        now = datetime.utcnow()
        db.add(models.EpisodeNote(user_id=user_id, category=category, item_id=item_id, episode_key=key,
                                  season=data.season, episode=data.episode, rating=data.rating, note=data.note,
                                  spoiler=bool(data.spoiler and data.note), created_at=now, updated_at=now))
        have.add((category, item_id, key))
        per_show += 1
        budget[0] -= 1
        created += 1
    return created, skipped


def existing_keys(db: Session, user_id: int) -> set[tuple[str, int, str]]:
    return {(category, item_id, key) for category, item_id, key in db.query(
        models.EpisodeNote.category, models.EpisodeNote.item_id, models.EpisodeNote.episode_key,
    ).filter(models.EpisodeNote.user_id == user_id)}
