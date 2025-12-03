"""
TV Show CRUD operations for the OmniTrackr API.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc

from .. import models, schemas


def get_tv_shows(
    db: Session,
    user_id: int,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
) -> List[models.TVShow]:
    query = db.query(models.TVShow).filter(models.TVShow.user_id == user_id).filter(models.TVShow.user_id == user_id)
    if search:
        like_pattern = f"%{search}%"
        query = query.filter(
            models.TVShow.title.ilike(like_pattern)
        )
    sort_order = asc
    if order and order.lower() == "desc":
        sort_order = desc
    if sort_by == "rating":
        query = query.order_by(sort_order(models.TVShow.rating))
    elif sort_by == "year":
        query = query.order_by(sort_order(models.TVShow.year))
    return query.all()


def get_tv_show_by_id(db: Session, user_id: int, tv_show_id: int) -> Optional[models.TVShow]:
    return db.query(models.TVShow).filter(models.TVShow.user_id == user_id).filter(
        models.TVShow.id == tv_show_id,
        models.TVShow.user_id == user_id
    ).first()


def create_tv_show(db: Session, user_id: int, tv_show: schemas.TVShowCreate) -> models.TVShow:
    tv_show_dict = tv_show.dict()
    if tv_show_dict.get('rating') is not None:
        tv_show_dict['rating'] = round(float(tv_show_dict['rating']), 1)
    db_tv_show = models.TVShow(**tv_show_dict, user_id=user_id)
    db.add(db_tv_show)
    db.commit()
    db.refresh(db_tv_show)
    return db_tv_show


def update_tv_show(db: Session, user_id: int, tv_show_id: int, tv_show_update: schemas.TVShowUpdate) -> Optional[models.TVShow]:
    db_tv_show = get_tv_show_by_id(db, user_id, tv_show_id)
    if db_tv_show is None:
        return None
    update_dict = tv_show_update.dict(exclude_unset=True)
    if 'rating' in update_dict and update_dict['rating'] is not None:
        update_dict['rating'] = round(float(update_dict['rating']), 1)
    for field, value in update_dict.items():
        setattr(db_tv_show, field, value)
    db.commit()
    db.refresh(db_tv_show)
    return db_tv_show


def delete_tv_show(db: Session, user_id: int, tv_show_id: int) -> Optional[models.TVShow]:
    db_tv_show = get_tv_show_by_id(db, user_id, tv_show_id)
    if db_tv_show is None:
        return None
    db.delete(db_tv_show)
    db.commit()
    return db_tv_show

