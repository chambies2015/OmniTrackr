"""Private, ordered Next Up queue endpoints."""
from typing import Dict, List, Tuple, Type

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..dependencies import get_current_user, get_db

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


def _serialize(entry: models.NextUpItem, db: Session, user_id: int) -> dict:
    item = _referenced_item(db, user_id, entry.category, entry.item_id)
    _, category_label = CATEGORIES[entry.category]
    return {
        "id": entry.id,
        "category": entry.category,
        "item_id": entry.item_id,
        "title": item.title if item else "Deleted library item",
        "category_label": category_label,
        "position": entry.position,
        "available": item is not None,
    }


def _get_owned_entry(db: Session, user_id: int, queue_id: int) -> models.NextUpItem:
    entry = db.query(models.NextUpItem).filter(
        models.NextUpItem.id == queue_id,
        models.NextUpItem.user_id == user_id,
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Queue item not found")
    return entry


@router.get("/", response_model=List[schemas.NextUpItem])
async def list_next_up(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entries = db.query(models.NextUpItem).filter(
        models.NextUpItem.user_id == current_user.id,
    ).order_by(models.NextUpItem.position, models.NextUpItem.id).all()
    return [_serialize(entry, db, current_user.id) for entry in entries]


@router.post("/", response_model=schemas.NextUpItem, status_code=status.HTTP_201_CREATED)
async def add_next_up(
    payload: schemas.NextUpItemCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That item is already in Next Up")
    db.refresh(entry)
    return _serialize(entry, db, current_user.id)


@router.put("/{queue_id}/position", response_model=List[schemas.NextUpItem])
async def move_next_up(
    queue_id: int,
    payload: schemas.NextUpItemMove,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = _get_owned_entry(db, current_user.id, queue_id)
    entries = db.query(models.NextUpItem).filter(
        models.NextUpItem.user_id == current_user.id,
    ).order_by(models.NextUpItem.position, models.NextUpItem.id).all()

    entries.remove(target)
    destination = min(payload.position, len(entries))
    entries.insert(destination, target)
    for position, entry in enumerate(entries):
        entry.position = position
    db.commit()
    return [_serialize(entry, db, current_user.id) for entry in entries]


@router.delete("/{queue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_next_up(
    queue_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = _get_owned_entry(db, current_user.id, queue_id)
    db.delete(entry)
    db.commit()
