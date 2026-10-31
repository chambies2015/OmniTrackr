"""
Podcast CRUD operations for the OmniTrackr API.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc

from .. import models, schemas


def get_podcasts(
    db: Session,
    user_id: int,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
) -> List[models.Podcast]:
    query = db.query(models.Podcast).filter(models.Podcast.user_id == user_id)
    if search:
        like_pattern = f"%{search}%"
        query = query.filter(
            models.Podcast.title.ilike(like_pattern) |
            models.Podcast.host.ilike(like_pattern) |
            models.Podcast.genre.ilike(like_pattern)
        )
    sort_order = asc
    if order and order.lower() == "desc":
        sort_order = desc
    if sort_by == "rating":
        query = query.order_by(sort_order(models.Podcast.rating))
    elif sort_by == "year":
        query = query.order_by(sort_order(models.Podcast.year))
    return query.all()


def get_podcast_by_id(db: Session, user_id: int, podcast_id: int) -> Optional[models.Podcast]:
    return db.query(models.Podcast).filter(
        models.Podcast.id == podcast_id,
        models.Podcast.user_id == user_id
    ).first()


def create_podcast(db: Session, user_id: int, podcast: schemas.PodcastCreate) -> models.Podcast:
    podcast_dict = podcast.model_dump()
    if podcast_dict.get('rating') is not None:
        podcast_dict['rating'] = round(float(podcast_dict['rating']), 1)
    db_podcast = models.Podcast(**podcast_dict, user_id=user_id)
    db.add(db_podcast)
    db.commit()
    db.refresh(db_podcast)
    return db_podcast


def update_podcast(db: Session, user_id: int, podcast_id: int, podcast_update: schemas.PodcastUpdate) -> Optional[models.Podcast]:
    db_podcast = get_podcast_by_id(db, user_id, podcast_id)
    if db_podcast is None:
        return None
    update_dict = podcast_update.model_dump(exclude_unset=True)

    allowed_fields = {'title', 'host', 'year', 'genre', 'episodes', 'rating', 'listened', 'review', 'review_public', 'cover_art_url'}
    for field, value in update_dict.items():
        if field not in allowed_fields:
            continue
        if field == 'rating' and value is not None:
            value = round(float(value), 1)
        setattr(db_podcast, field, value)
    db.commit()
    db.refresh(db_podcast)
    return db_podcast


def delete_podcast(db: Session, user_id: int, podcast_id: int) -> Optional[models.Podcast]:
    from ..library_lifecycle import delete_owned_media
    return delete_owned_media(db, user_id, "podcasts", podcast_id)
