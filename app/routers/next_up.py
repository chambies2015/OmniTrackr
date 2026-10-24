"""Private, ordered Next Up queue endpoints."""
from typing import Dict, List, Tuple, Type

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..integer_bounds import PositiveDatabaseId
from .. import models, schemas, title_pages
from ..progress import lock_progress_owner
from ..dependencies import get_current_user, get_db
from ..progress import get_checkpoint_map, serialize_checkpoint

router = APIRouter(prefix="/next-up", tags=["next-up"])

CategoryDetails = Tuple[Type[models.Movie], str]
CATEGORIES: Dict[str, CategoryDetails] = {
    "movies": (models.Movie, "Movie"),
    "tv-shows": (models.TVShow, "TV show"),
    "anime": (models.Anime, "Anime"),
    "video-games": (models.VideoGame, "Game"),
    "music": (models.Music, "Album"),
    "books": (models.Book, "Book"),
}


def _referenced_item(db: Session, user_id: int, category: str, item_id: int):
    model, _ = CATEGORIES[category]
    return db.query(model).filter(model.id == item_id, model.user_id == user_id).first()


def _finished(item, category: str) -> bool:
    return bool(getattr(item, title_pages.COMPLETE_FIELD[title_pages.LIBRARY_TO_KIND[category]], False))


def _serialize(entry: models.NextUpItem, db: Session, user_id: int, checkpoints=None) -> dict:
    item = _referenced_item(db, user_id, entry.category, entry.item_id)
    _, category_label = CATEGORIES[entry.category]
    checkpoints = get_checkpoint_map(db, user_id) if checkpoints is None else checkpoints
    kind = title_pages.LIBRARY_TO_KIND[entry.category]
    return {
        "id": entry.id,
        "category": entry.category,
        "item_id": entry.item_id,
        "title": item.title if item else "Deleted library item",
        "category_label": category_label,
        "position": entry.position,
        "available": item is not None,
        "progress": serialize_checkpoint(checkpoints.get((entry.category, entry.item_id))) if item else None,
        "finished": _finished(item, entry.category) if item else False,
        "image": title_pages._safe_image(getattr(item, title_pages.IMAGE_FIELD[kind], None)) if item else None,
    }


def _ordered_entries(db: Session, user_id: int) -> List[models.NextUpItem]:
    return db.query(models.NextUpItem).filter(
        models.NextUpItem.user_id == user_id,
    ).order_by(models.NextUpItem.position, models.NextUpItem.id).all()


def enqueue(db: Session, user_id: int, category: str, item_id: int) -> bool:
    """Put an owned library item at the end of the queue. Does not commit.

    Returns False when it is already queued. The caller checks ownership.
    """
    exists = db.query(models.NextUpItem.id).filter(
        models.NextUpItem.user_id == user_id,
        models.NextUpItem.category == category,
        models.NextUpItem.item_id == item_id,
    ).first()
    if exists:
        return False
    highest = db.query(func.max(models.NextUpItem.position)).filter(models.NextUpItem.user_id == user_id).scalar()
    db.add(models.NextUpItem(user_id=user_id, category=category, item_id=item_id,
                             position=(highest if highest is not None else -1) + 1))
    return True


def _get_owned_entry(db: Session, user_id: int, queue_id: int) -> models.NextUpItem:
    entry = db.query(models.NextUpItem).filter(
        models.NextUpItem.id == queue_id,
        models.NextUpItem.user_id == user_id,
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Queue item not found")
    return entry


@router.get("/", response_model=List[schemas.NextUpItem])
def list_next_up(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entries = _ordered_entries(db, current_user.id)
    checkpoints = get_checkpoint_map(db, current_user.id)
    return [_serialize(entry, db, current_user.id, checkpoints) for entry in entries]


@router.post("/", response_model=schemas.NextUpItem, status_code=status.HTTP_201_CREATED)
def add_next_up(
    payload: schemas.NextUpItemCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lock_progress_owner(db, current_user.id)
    if not _referenced_item(db, current_user.id, payload.category, payload.item_id):
        raise HTTPException(status_code=404, detail="Library item not found")

    duplicate = db.query(models.NextUpItem).filter(
        models.NextUpItem.user_id == current_user.id,
        models.NextUpItem.category == payload.category,
        models.NextUpItem.item_id == payload.item_id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="That item is already in Next Up")

    highest_position = db.query(func.max(models.NextUpItem.position)).filter(
        models.NextUpItem.user_id == current_user.id,
    ).scalar()
    entry = models.NextUpItem(
        user_id=current_user.id,
        category=payload.category,
        item_id=payload.item_id,
        position=(highest_position if highest_position is not None else -1) + 1,
    )
    db.add(entry)
    try:
        db.flush()
        result = _serialize(entry, db, current_user.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That item is already in Next Up")
    return result


@router.put("/{queue_id}/position", response_model=List[schemas.NextUpItem])
def move_next_up(
    queue_id: PositiveDatabaseId,
    payload: schemas.NextUpItemMove,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = _get_owned_entry(db, current_user.id, queue_id)
    entries = _ordered_entries(db, current_user.id)

    entries.remove(target)
    destination = min(payload.position, len(entries))
    entries.insert(destination, target)
    for position, entry in enumerate(entries):
        entry.position = position
    db.commit()
    checkpoints = get_checkpoint_map(db, current_user.id)
    return [_serialize(entry, db, current_user.id, checkpoints) for entry in entries]


@router.post("/{queue_id}/finish", response_model=schemas.NextUpFinished)
def finish_next_up(
    queue_id: PositiveDatabaseId,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark the queued title finished in the library and take it off the queue.

    Only the completion flag changes on the library item; rating, review and
    everything else stay as they are. The dashboard then opens the usual
    completion reflection, which logs the finish to the journal.
    """
    lock_progress_owner(db, current_user.id)
    entry = _get_owned_entry(db, current_user.id, queue_id)
    item = _referenced_item(db, current_user.id, entry.category, entry.item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Library item not found")
    was_finished = _finished(item, entry.category)
    if not was_finished:
        setattr(item, title_pages.COMPLETE_FIELD[title_pages.LIBRARY_TO_KIND[entry.category]], True)
    result = {"category": entry.category, "item_id": entry.item_id, "title": item.title, "was_finished": was_finished}
    db.delete(entry)
    db.flush()
    for position, remaining in enumerate(_ordered_entries(db, current_user.id)):
        remaining.position = position
    db.commit()
    return result


@router.post("/clear-finished", response_model=List[schemas.NextUpItem])
def clear_finished_next_up(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Drop queue entries whose library item is already finished (or was deleted)."""
    lock_progress_owner(db, current_user.id)
    checkpoints = get_checkpoint_map(db, current_user.id)
    kept = []
    for entry in _ordered_entries(db, current_user.id):
        item = _referenced_item(db, current_user.id, entry.category, entry.item_id)
        if item is None or _finished(item, entry.category):
            db.delete(entry)
        else:
            kept.append(entry)
    for position, entry in enumerate(kept):
        entry.position = position
    db.commit()
    return [_serialize(entry, db, current_user.id, checkpoints) for entry in kept]


@router.delete("/{queue_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_next_up(
    queue_id: PositiveDatabaseId,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = _get_owned_entry(db, current_user.id, queue_id)
    db.delete(entry)
    db.commit()
