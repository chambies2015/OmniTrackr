"""Owner-only progress checkpoints with revision-safe writes and backup helpers."""
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models

ProgressCategory = Literal["tv-shows", "anime", "books"]
PositiveItemId = Annotated[int, Field(gt=0, le=2147483647)]
CATEGORIES = {"tv-shows": models.TVShow, "anime": models.Anime, "books": models.Book}


class CheckpointData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    unit: Literal["episode", "page", "chapter"]
    position: Annotated[int, Field(ge=1, le=1000000)]
    season: Annotated[int, Field(ge=0, le=10000)] | None = None
    note: Annotated[str, Field(max_length=300)] | None = None

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value):
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def season_requires_episode(self):
        if self.unit != "episode" and self.season is not None:
            raise ValueError("A season only applies to an episode checkpoint")
        return self


class ProgressWrite(CheckpointData):
    expected_revision: Annotated[int, Field(ge=0, le=2147483646)]


class ProgressClear(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: Annotated[int, Field(ge=0, le=2147483646)]


def validate_checkpoint(category: str, payload: dict | CheckpointData) -> CheckpointData:
    """Validate untrusted checkpoint data, including category-specific units.

    Backup callers should pass only the four checkpoint content fields, never
    an imported revision, owner, item id, or update timestamp.
    """
    if not isinstance(category, str) or category not in CATEGORIES:
        raise ValueError("Progress is available for TV shows, anime, and books")
    if isinstance(payload, CheckpointData):
        payload = payload.model_dump(include={"unit", "position", "season", "note"})
    data = CheckpointData.model_validate(payload)
    if category == "books" and data.unit not in ("page", "chapter"):
        raise ValueError("Books use a page or chapter checkpoint")
    if category != "books" and data.unit != "episode":
        raise ValueError("TV shows and anime use an episode checkpoint")
    return data


def serialize_checkpoint(entry: models.ProgressCheckpoint | None) -> dict | None:
    if entry is None or entry.unit is None:
        return None
    updated_at = entry.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return {
        "unit": entry.unit,
        "position": entry.position,
        "season": entry.season,
        "note": entry.note,
        "updated_at": updated_at.isoformat().replace("+00:00", "Z"),
        "revision": entry.revision,
    }


def get_checkpoint_map(db: Session, user_id: int) -> dict:
    """Batch-load active checkpoints belonging to one account only."""
    return {
        (entry.category, entry.item_id): entry
        for entry in db.query(models.ProgressCheckpoint).filter(
            models.ProgressCheckpoint.user_id == user_id,
            models.ProgressCheckpoint.unit.is_not(None),
        ).all()
    }


def lock_progress_owner(db: Session, user_id: int) -> None:
    """Use the same owner-first lock order for progress and media deletion."""
    query = db.query(models.User).filter(models.User.id == user_id)
    if db.get_bind().dialect.name == "sqlite":
        # SQLite has no row locks. Reserve its write transaction before reads so
        # a media deletion cannot race a subsequent checkpoint insertion.
        exists = query.update({models.User.id: models.User.id}, synchronize_session=False)
    else:
        exists = query.with_for_update().first()
    if not exists:
        raise HTTPException(404, "Library item not found")


def _owned_item(db: Session, user_id: int, category: str, item_id: int, *, lock=False):
    model = CATEGORIES.get(category)
    if model is None or type(item_id) is not int or not 0 < item_id <= 2147483647:
        raise HTTPException(422, "Invalid progress category or item")
    query = db.query(model).filter(model.user_id == user_id, model.id == item_id)
    if lock:
        query = query.populate_existing().with_for_update()
    item = query.first()
    if item is None:
        raise HTTPException(404, "Library item not found")
    return item


def _checkpoint_query(db, user_id, category, item_id):
    return db.query(models.ProgressCheckpoint).filter_by(
        user_id=user_id, category=category, item_id=item_id,
    )


def _envelope(item, category, entry):
    return {
        "category": category,
        "item_id": item.id,
        "title": item.title,
        "revision": entry.revision if entry else 0,
        "checkpoint": serialize_checkpoint(entry),
    }


def get_progress(db: Session, user_id: int, category: str, item_id: int) -> dict:
    item = _owned_item(db, user_id, category, item_id)
    entry = _checkpoint_query(db, user_id, category, item_id).first()
    return _envelope(item, category, entry)


def _same_content(entry, values):
    return entry is not None and all(getattr(entry, field) == value for field, value in values.items())


def _conflict():
    return HTTPException(409, "Your progress changed in another request. Reload it before saving again.")


def _write_progress(db, user_id, category, item_id, expected_revision, values):
    try:
        lock_progress_owner(db, user_id)
        item = _owned_item(db, user_id, category, item_id, lock=True)
        query = _checkpoint_query(db, user_id, category, item_id)
        entry = query.populate_existing().with_for_update().first()
        revision = entry.revision if entry else 0
        if revision != expected_revision:
            # A lost response may be retried once against the exact resulting
            # revision. Older requests must not erase newer edits or tombstones.
            if revision == expected_revision + 1 and _same_content(entry, values):
                result = _envelope(item, category, entry)
                db.commit()
                return result
            raise _conflict()
        if _same_content(entry, values):
            result = _envelope(item, category, entry)
            db.commit()
            return result
        next_values = {**values, "revision": revision + 1, "updated_at": datetime.utcnow()}
        if entry is None:
            entry = models.ProgressCheckpoint(
                user_id=user_id, category=category, item_id=item_id, **next_values,
            )
            db.add(entry)
            db.flush()
        else:
            changed = query.filter(models.ProgressCheckpoint.revision == revision).update(
                next_values, synchronize_session=False,
            )
            if changed != 1:
                raise _conflict()
            db.refresh(entry)
        result = _envelope(item, category, entry)
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        raise _conflict()
    except Exception:
        db.rollback()
        raise


def save_progress(db: Session, user_id: int, category: str, item_id: int, payload: ProgressWrite) -> dict:
    try:
        data = validate_checkpoint(category, payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _write_progress(db, user_id, category, item_id, payload.expected_revision, data.model_dump())


def clear_progress(db: Session, user_id: int, category: str, item_id: int, payload: ProgressClear) -> dict:
    return _write_progress(db, user_id, category, item_id, payload.expected_revision, {
        "unit": None, "position": None, "season": None, "note": None,
    })


def delete_progress_for_item(db: Session, user_id: int, category: str, item_id: int) -> None:
    """Remove a deleted item's checkpoint in its existing deletion transaction.

    The caller first locks the owner and media, in that order. Unlike a clear,
    deletion removes the tombstone too, so reused SQLite ids start cleanly.
    """
    _checkpoint_query(db, user_id, category, item_id).delete(synchronize_session=False)


def stage_import_checkpoint(db: Session, user_id: int, category: str, item_id: int, checkpoint) -> bool:
    """Stage a validated backup checkpoint without overwriting current choices.

    Restores retain neither backup ids nor revisions. Existing tombstones count
    as a user's explicit choice and are never replaced. The caller commits the
    encompassing import transaction after this helper flushes its new record.
    """
    data = validate_checkpoint(category, checkpoint)
    lock_progress_owner(db, user_id)
    _owned_item(db, user_id, category, item_id, lock=True)
    if _checkpoint_query(db, user_id, category, item_id).with_for_update().first() is not None:
        return False
    db.add(models.ProgressCheckpoint(
        user_id=user_id, category=category, item_id=item_id,
        revision=1, updated_at=datetime.utcnow(), **data.model_dump(),
    ))
    db.flush()
    return True
