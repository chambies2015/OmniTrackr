"""
Book CRUD operations for the OmniTrackr API.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc

from .. import models, schemas


def get_books(
    db: Session,
    user_id: int,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
) -> List[models.Book]:
    query = db.query(models.Book).filter(models.Book.user_id == user_id)
    if search:
        like_pattern = f"%{search}%"
        query = query.filter(
            models.Book.title.ilike(like_pattern) |
            models.Book.author.ilike(like_pattern) |
            models.Book.genre.ilike(like_pattern)
        )
    sort_order = asc
    if order and order.lower() == "desc":
        sort_order = desc
    if sort_by == "rating":
        query = query.order_by(sort_order(models.Book.rating))
    elif sort_by == "year":
        query = query.order_by(sort_order(models.Book.year))
    return query.all()


def get_book_by_id(db: Session, user_id: int, book_id: int) -> Optional[models.Book]:
    return db.query(models.Book).filter(
        models.Book.id == book_id,
        models.Book.user_id == user_id
    ).first()


def create_book(db: Session, user_id: int, book: schemas.BookCreate) -> models.Book:
    book_dict = book.dict()
    if book_dict.get('rating') is not None:
        book_dict['rating'] = round(float(book_dict['rating']), 1)
    db_book = models.Book(**book_dict, user_id=user_id)
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    return db_book


def update_book(db: Session, user_id: int, book_id: int, book_update: schemas.BookUpdate) -> Optional[models.Book]:
    db_book = get_book_by_id(db, user_id, book_id)
    if db_book is None:
        return None
    update_dict = book_update.dict(exclude_unset=True)
    
    allowed_fields = {'title', 'author', 'year', 'genre', 'rating', 'read', 'review', 'review_public', 'cover_art_url'}
    for field, value in update_dict.items():
        if field not in allowed_fields:
            continue
        if field == 'rating' and value is not None:
            value = round(float(value), 1)
        setattr(db_book, field, value)
    db.commit()
    db.refresh(db_book)
    return db_book


def delete_book(db: Session, user_id: int, book_id: int) -> Optional[models.Book]:
    db_book = get_book_by_id(db, user_id, book_id)
    if db_book is None:
        return None
    db.delete(db_book)
    db.commit()
    return db_book
