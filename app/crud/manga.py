"""
Manga CRUD operations for the OmniTrackr API.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc

from .. import models, schemas


def get_manga(
    db: Session,
    user_id: int,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
) -> List[models.Manga]:
    query = db.query(models.Manga).filter(models.Manga.user_id == user_id)
    if search:
        like_pattern = f"%{search}%"
        query = query.filter(
            models.Manga.title.ilike(like_pattern) |
            models.Manga.author.ilike(like_pattern) |
            models.Manga.genre.ilike(like_pattern)
        )
    sort_order = asc
    if order and order.lower() == "desc":
        sort_order = desc
    if sort_by == "rating":
        query = query.order_by(sort_order(models.Manga.rating))
    elif sort_by == "year":
        query = query.order_by(sort_order(models.Manga.year))
    return query.all()


def get_manga_by_id(db: Session, user_id: int, manga_id: int) -> Optional[models.Manga]:
    return db.query(models.Manga).filter(
        models.Manga.id == manga_id,
        models.Manga.user_id == user_id
    ).first()


def create_manga(db: Session, user_id: int, manga: schemas.MangaCreate) -> models.Manga:
    manga_dict = manga.model_dump()
    if manga_dict.get('rating') is not None:
        manga_dict['rating'] = round(float(manga_dict['rating']), 1)
    db_manga = models.Manga(**manga_dict, user_id=user_id)
    db.add(db_manga)
    db.commit()
    db.refresh(db_manga)
    return db_manga


def update_manga(db: Session, user_id: int, manga_id: int, manga_update: schemas.MangaUpdate) -> Optional[models.Manga]:
    db_manga = get_manga_by_id(db, user_id, manga_id)
    if db_manga is None:
        return None
    update_dict = manga_update.model_dump(exclude_unset=True)

    allowed_fields = {'title', 'author', 'year', 'genre', 'volumes', 'chapters', 'rating', 'read', 'review', 'review_public', 'cover_art_url'}
    for field, value in update_dict.items():
        if field not in allowed_fields:
            continue
        if field == 'rating' and value is not None:
            value = round(float(value), 1)
        setattr(db_manga, field, value)
    db.commit()
    db.refresh(db_manga)
    return db_manga


def delete_manga(db: Session, user_id: int, manga_id: int) -> Optional[models.Manga]:
    from ..library_lifecycle import delete_owned_media
    return delete_owned_media(db, user_id, "manga", manga_id)
