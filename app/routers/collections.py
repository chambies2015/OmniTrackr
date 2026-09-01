"""Private cross-media collection endpoints."""
from typing import Dict, List, Tuple, Type

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..dependencies import get_current_user, get_db

router = APIRouter(prefix="/collections", tags=["collections"])

CategoryDetails = Tuple[Type[models.Movie], str]
CATEGORIES: Dict[str, CategoryDetails] = {
    "movies": (models.Movie, "Movie"),
    "tv-shows": (models.TVShow, "TV show"),
    "anime": (models.Anime, "Anime"),
    "video-games": (models.VideoGame, "Game"),
    "music": (models.Music, "Album"),
    "books": (models.Book, "Book"),
}


def _get_collection(db: Session, user_id: int, collection_id: int) -> models.Collection:
    collection = db.query(models.Collection).filter(
        models.Collection.id == collection_id,
        models.Collection.user_id == user_id,
    ).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


def _get_media_item(db: Session, user_id: int, category: str, item_id: int):
    model, _ = CATEGORIES[category]
    return db.query(model).filter(model.id == item_id, model.user_id == user_id).first()


def _serialize_item(item: models.CollectionItem, db: Session, user_id: int) -> dict:
    media = _get_media_item(db, user_id, item.category, item.item_id)
    return {
        "id": item.id,
        "category": item.category,
        "category_label": CATEGORIES[item.category][1],
        "item_id": item.item_id,
        "title": media.title if media else "Deleted library item",
        "position": item.position,
        "available": media is not None,
    }


def _serialize_collection(collection: models.Collection, db: Session, user_id: int) -> dict:
    items = sorted(collection.items, key=lambda item: (item.position, item.id))
    return {
        "id": collection.id,
        "name": collection.name,
        "description": collection.description,
        "created_at": collection.created_at,
        "items": [_serialize_item(item, db, user_id) for item in items],
    }


@router.get("/", response_model=List[schemas.Collection])
async def list_collections(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    collections = db.query(models.Collection).filter(
        models.Collection.user_id == current_user.id,
    ).order_by(models.Collection.created_at.desc(), models.Collection.id.desc()).all()
    return [_serialize_collection(collection, db, current_user.id) for collection in collections]


@router.post("/", response_model=schemas.Collection, status_code=status.HTTP_201_CREATED)
async def create_collection(
    payload: schemas.CollectionCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    collection = models.Collection(user_id=current_user.id, name=payload.name, description=payload.description)
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return _serialize_collection(collection, db, current_user.id)


@router.patch("/{collection_id}", response_model=schemas.Collection)
async def update_collection(
    collection_id: int,
    payload: schemas.CollectionUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    collection = _get_collection(db, current_user.id, collection_id)
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        normalized = updates["name"].strip()
        if not normalized:
            raise HTTPException(status_code=422, detail="Collection name cannot be blank")
        collection.name = normalized
    if "description" in updates:
        collection.description = updates["description"].strip() or None if updates["description"] else None
    db.commit()
    db.refresh(collection)
    return _serialize_collection(collection, db, current_user.id)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    collection = _get_collection(db, current_user.id, collection_id)
    db.delete(collection)
    db.commit()


@router.post("/{collection_id}/items", response_model=schemas.CollectionItem, status_code=status.HTTP_201_CREATED)
async def add_collection_item(
    collection_id: int,
    payload: schemas.CollectionItemCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_collection(db, current_user.id, collection_id)
    if not _get_media_item(db, current_user.id, payload.category, payload.item_id):
        raise HTTPException(status_code=404, detail="Library item not found")
    duplicate = db.query(models.CollectionItem).filter(
        models.CollectionItem.collection_id == collection_id,
        models.CollectionItem.category == payload.category,
        models.CollectionItem.item_id == payload.item_id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="That item is already in this collection")
    highest_position = db.query(func.max(models.CollectionItem.position)).filter(
        models.CollectionItem.collection_id == collection_id,
    ).scalar()
    item = models.CollectionItem(
        collection_id=collection_id,
        category=payload.category,
        item_id=payload.item_id,
        position=(highest_position if highest_position is not None else -1) + 1,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That item is already in this collection")
    db.refresh(item)
    return _serialize_item(item, db, current_user.id)


@router.put("/{collection_id}/items/{item_id}/position", response_model=List[schemas.CollectionItem])
async def move_collection_item(
    collection_id: int,
    item_id: int,
    payload: schemas.CollectionItemMove,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_collection(db, current_user.id, collection_id)
    items = db.query(models.CollectionItem).filter(
        models.CollectionItem.collection_id == collection_id,
    ).order_by(models.CollectionItem.position, models.CollectionItem.id).all()
    target = next((item for item in items if item.id == item_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Collection item not found")
    items.remove(target)
    items.insert(min(payload.position, len(items)), target)
    for position, item in enumerate(items):
        item.position = position
    db.commit()
    return [_serialize_item(item, db, current_user.id) for item in items]


@router.delete("/{collection_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_collection_item(
    collection_id: int,
    item_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_collection(db, current_user.id, collection_id)
    item = db.query(models.CollectionItem).filter(
        models.CollectionItem.id == item_id,
        models.CollectionItem.collection_id == collection_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Collection item not found")
    db.delete(item)
    db.commit()
