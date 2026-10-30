"""
Audiobook CRUD operations for the OmniTrackr API.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc

from .. import models, schemas


def get_audiobooks(
    db: Session,
    user_id: int,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
) -> List[models.Audiobook]:
    query = db.query(models.Audiobook).filter(models.Audiobook.user_id == user_id)
    if search:
        like_pattern = f"%{search}%"
        query = query.filter(
            models.Audiobook.title.ilike(like_pattern) |
            models.Audiobook.author.ilike(like_pattern) |
            models.Audiobook.narrator.ilike(like_pattern) |
            models.Audiobook.genre.ilike(like_pattern)
        )
    sort_order = asc
    if order and order.lower() == "desc":
        sort_order = desc
    if sort_by == "rating":
        query = query.order_by(sort_order(models.Audiobook.rating))
    elif sort_by == "year":
        query = query.order_by(sort_order(models.Audiobook.year))
    elif sort_by == "length":
        query = query.order_by(sort_order(models.Audiobook.length_hours))
    return query.all()


def get_audiobook_by_id(db: Session, user_id: int, audiobook_id: int) -> Optional[models.Audiobook]:
    return db.query(models.Audiobook).filter(
        models.Audiobook.id == audiobook_id,
        models.Audiobook.user_id == user_id
    ).first()


def create_audiobook(db: Session, user_id: int, audiobook: schemas.AudiobookCreate) -> models.Audiobook:
    audiobook_dict = audiobook.model_dump()
    if audiobook_dict.get('rating') is not None:
        audiobook_dict['rating'] = round(float(audiobook_dict['rating']), 1)
    if audiobook_dict.get('length_hours') is not None:
        audiobook_dict['length_hours'] = round(float(audiobook_dict['length_hours']), 2)
    db_audiobook = models.Audiobook(**audiobook_dict, user_id=user_id)
    db.add(db_audiobook)
    db.commit()
    db.refresh(db_audiobook)
    return db_audiobook


def update_audiobook(db: Session, user_id: int, audiobook_id: int, audiobook_update: schemas.AudiobookUpdate) -> Optional[models.Audiobook]:
    db_audiobook = get_audiobook_by_id(db, user_id, audiobook_id)
    if db_audiobook is None:
        return None
    update_dict = audiobook_update.model_dump(exclude_unset=True)

    allowed_fields = {'title', 'author', 'narrator', 'year', 'genre', 'length_hours', 'rating', 'listened', 'review', 'review_public', 'cover_art_url'}
    for field, value in update_dict.items():
        if field not in allowed_fields:
            continue
        if field in ('rating', 'length_hours') and value is not None:
            value = round(float(value), 1 if field == 'rating' else 2)
        setattr(db_audiobook, field, value)
    db.commit()
    db.refresh(db_audiobook)
    return db_audiobook


def delete_audiobook(db: Session, user_id: int, audiobook_id: int) -> Optional[models.Audiobook]:
    from ..library_lifecycle import delete_owned_media
    return delete_owned_media(db, user_id, "audiobooks", audiobook_id)
