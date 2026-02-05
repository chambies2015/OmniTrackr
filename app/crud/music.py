"""
Music CRUD operations for the OmniTrackr API.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc

from .. import models, schemas


def get_music(
    db: Session,
    user_id: int,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
) -> List[models.Music]:
    query = db.query(models.Music).filter(models.Music.user_id == user_id)
    if search:
        like_pattern = f"%{search}%"
        query = query.filter(
            models.Music.title.ilike(like_pattern) |
            models.Music.artist.ilike(like_pattern) |
            models.Music.genre.ilike(like_pattern)
        )
    sort_order = asc
    if order and order.lower() == "desc":
        sort_order = desc
    if sort_by == "rating":
        query = query.order_by(sort_order(models.Music.rating))
    elif sort_by == "year":
        query = query.order_by(sort_order(models.Music.year))
    return query.all()


def get_music_by_id(db: Session, user_id: int, music_id: int) -> Optional[models.Music]:
    return db.query(models.Music).filter(
        models.Music.id == music_id,
        models.Music.user_id == user_id
    ).first()


def create_music(db: Session, user_id: int, music: schemas.MusicCreate) -> models.Music:
    music_dict = music.dict()
    if music_dict.get('rating') is not None:
        music_dict['rating'] = round(float(music_dict['rating']), 1)
    db_music = models.Music(**music_dict, user_id=user_id)
    db.add(db_music)
    db.commit()
    db.refresh(db_music)
    return db_music


def update_music(db: Session, user_id: int, music_id: int, music_update: schemas.MusicUpdate) -> Optional[models.Music]:
    db_music = get_music_by_id(db, user_id, music_id)
    if db_music is None:
        return None
    update_dict = music_update.dict(exclude_unset=True)
    
    allowed_fields = {'title', 'artist', 'year', 'genre', 'rating', 'listened', 'review', 'cover_art_url'}
    for field, value in update_dict.items():
        if field not in allowed_fields:
            continue
        if field == 'rating' and value is not None:
            value = round(float(value), 1)
        setattr(db_music, field, value)
    db.commit()
    db.refresh(db_music)
    return db_music


def delete_music(db: Session, user_id: int, music_id: int) -> Optional[models.Music]:
    db_music = get_music_by_id(db, user_id, music_id)
    if db_music is None:
        return None
    db.delete(db_music)
    db.commit()
    return db_music
