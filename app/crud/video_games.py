"""
Video Game CRUD operations for the OmniTrackr API.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc

from .. import models, schemas


def get_video_games(
    db: Session,
    user_id: int,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
) -> List[models.VideoGame]:
    query = db.query(models.VideoGame).filter(models.VideoGame.user_id == user_id)
    if search:
        like_pattern = f"%{search}%"
        query = query.filter(
            models.VideoGame.title.ilike(like_pattern) |
            models.VideoGame.genres.ilike(like_pattern)
        )
    sort_order = asc
    if order and order.lower() == "desc":
        sort_order = desc
    if sort_by == "rating":
        query = query.order_by(sort_order(models.VideoGame.rating))
    elif sort_by == "release_date" or sort_by == "year":
        query = query.order_by(sort_order(models.VideoGame.release_date))
    return query.all()


def get_video_game_by_id(db: Session, user_id: int, game_id: int) -> Optional[models.VideoGame]:
    return db.query(models.VideoGame).filter(
        models.VideoGame.id == game_id,
        models.VideoGame.user_id == user_id
    ).first()


def create_video_game(db: Session, user_id: int, video_game: schemas.VideoGameCreate) -> models.VideoGame:
    video_game_dict = video_game.dict()
    if video_game_dict.get('rating') is not None:
        video_game_dict['rating'] = round(float(video_game_dict['rating']), 1)
    db_video_game = models.VideoGame(**video_game_dict, user_id=user_id)
    db.add(db_video_game)
    db.commit()
    db.refresh(db_video_game)
    return db_video_game


def update_video_game(db: Session, user_id: int, game_id: int, video_game_update: schemas.VideoGameUpdate) -> Optional[models.VideoGame]:
    db_video_game = get_video_game_by_id(db, user_id, game_id)
    if db_video_game is None:
        return None
    update_dict = video_game_update.dict(exclude_unset=True)
    
    allowed_fields = {'title', 'release_date', 'genres', 'rating', 'played', 'review', 'review_public', 'cover_art_url', 'rawg_link'}
    for field, value in update_dict.items():
        if field not in allowed_fields:
            continue
        if field == 'rating' and value is not None:
            value = round(float(value), 1)
        setattr(db_video_game, field, value)
    db.commit()
    db.refresh(db_video_game)
    return db_video_game


def delete_video_game(db: Session, user_id: int, game_id: int) -> Optional[models.VideoGame]:
    db_video_game = get_video_game_by_id(db, user_id, game_id)
    if db_video_game is None:
        return None
    db.delete(db_video_game)
    db.commit()
    return db_video_game

