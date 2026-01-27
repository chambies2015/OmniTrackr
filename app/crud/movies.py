"""
Movie CRUD operations for the OmniTrackr API.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc

from .. import models, schemas


def get_movies(
    db: Session,
    user_id: int,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
) -> List[models.Movie]:
    query = db.query(models.Movie).filter(models.Movie.user_id == user_id)
    if search:
        like_pattern = f"%{search}%"
        query = query.filter(
            models.Movie.title.ilike(like_pattern) |
            models.Movie.director.ilike(like_pattern)
        )
    sort_order = asc  # default
    if order and order.lower() == "desc":
        sort_order = desc
    if sort_by == "rating":
        query = query.order_by(sort_order(models.Movie.rating))
    elif sort_by == "year":
        query = query.order_by(sort_order(models.Movie.year))
    return query.all()


def get_movie_by_id(db: Session, user_id: int, movie_id: int) -> Optional[models.Movie]:
    return db.query(models.Movie).filter(
        models.Movie.id == movie_id,
        models.Movie.user_id == user_id
    ).first()


def create_movie(db: Session, user_id: int, movie: schemas.MovieCreate) -> models.Movie:
    movie_dict = movie.dict()
    if movie_dict.get('rating') is not None:
        movie_dict['rating'] = round(float(movie_dict['rating']), 1)
    db_movie = models.Movie(**movie_dict, user_id=user_id)
    db.add(db_movie)
    db.commit()
    db.refresh(db_movie)
    return db_movie


def update_movie(db: Session, user_id: int, movie_id: int, movie_update: schemas.MovieUpdate) -> Optional[models.Movie]:
    db_movie = get_movie_by_id(db, user_id, movie_id)
    if db_movie is None:
        return None
    update_dict = movie_update.dict(exclude_unset=True)
    
    allowed_fields = {'title', 'director', 'year', 'rating', 'watched', 'review', 'poster_url'}
    for field, value in update_dict.items():
        if field not in allowed_fields:
            continue
        if field == 'rating' and value is not None:
            value = round(float(value), 1)
        setattr(db_movie, field, value)
    db.commit()
    db.refresh(db_movie)
    return db_movie


def delete_movie(db: Session, user_id: int, movie_id: int) -> Optional[models.Movie]:
    db_movie = get_movie_by_id(db, user_id, movie_id)
    if db_movie is None:
        return None
    db.delete(db_movie)
    db.commit()
    return db_movie

