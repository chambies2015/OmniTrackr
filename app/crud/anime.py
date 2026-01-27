"""
Anime CRUD operations for the OmniTrackr API.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc

from .. import models, schemas


def get_anime(
    db: Session,
    user_id: int,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
) -> List[models.Anime]:
    query = db.query(models.Anime).filter(models.Anime.user_id == user_id).filter(models.Anime.user_id == user_id)
    if search:
        like_pattern = f"%{search}%"
        query = query.filter(
            models.Anime.title.ilike(like_pattern)
        )
    sort_order = asc
    if order and order.lower() == "desc":
        sort_order = desc
    if sort_by == "rating":
        query = query.order_by(sort_order(models.Anime.rating))
    elif sort_by == "year":
        query = query.order_by(sort_order(models.Anime.year))
    return query.all()


def get_anime_by_id(db: Session, user_id: int, anime_id: int) -> Optional[models.Anime]:
    return db.query(models.Anime).filter(models.Anime.user_id == user_id).filter(
        models.Anime.id == anime_id,
        models.Anime.user_id == user_id
    ).first()


def create_anime(db: Session, user_id: int, anime: schemas.AnimeCreate) -> models.Anime:
    anime_dict = anime.dict()
    if anime_dict.get('rating') is not None:
        anime_dict['rating'] = round(float(anime_dict['rating']), 1)
    db_anime = models.Anime(**anime_dict, user_id=user_id)
    db.add(db_anime)
    db.commit()
    db.refresh(db_anime)
    return db_anime


def update_anime(db: Session, user_id: int, anime_id: int, anime_update: schemas.AnimeUpdate) -> Optional[models.Anime]:
    db_anime = get_anime_by_id(db, user_id, anime_id)
    if db_anime is None:
        return None
    update_dict = anime_update.dict(exclude_unset=True)
    
    allowed_fields = {'title', 'year', 'seasons', 'episodes', 'rating', 'watched', 'review', 'poster_url'}
    for field, value in update_dict.items():
        if field not in allowed_fields:
            continue
        if field == 'rating' and value is not None:
            value = round(float(value), 1)
        setattr(db_anime, field, value)
    db.commit()
    db.refresh(db_anime)
    return db_anime


def delete_anime(db: Session, user_id: int, anime_id: int) -> Optional[models.Anime]:
    db_anime = get_anime_by_id(db, user_id, anime_id)
    if db_anime is None:
        return None
    db.delete(db_anime)
    db.commit()
    return db_anime

