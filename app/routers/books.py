"""
Books endpoints for the OmniTrackr API.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas, models
from ..dependencies import get_db, get_current_user

router = APIRouter(prefix="/books", tags=["books"])


@router.get("/", response_model=List[schemas.Book])
async def list_books(
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud.get_books(db, current_user.id, search=search, sort_by=sort_by, order=order)


@router.get("/{book_id}", response_model=schemas.Book)
async def get_book(
    book_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_book = crud.get_book_by_id(db, current_user.id, book_id)
    if db_book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return db_book


@router.post("/", response_model=schemas.Book, status_code=201)
async def create_book(
    book: schemas.BookCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return crud.create_book(db, current_user.id, book)


@router.put("/{book_id}", response_model=schemas.Book)
async def update_book(
    book_id: int,
    book: schemas.BookUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_book = crud.update_book(db, current_user.id, book_id, book)
    if db_book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return db_book


@router.delete("/{book_id}", response_model=schemas.Book)
async def delete_book(
    book_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_book = crud.delete_book(db, current_user.id, book_id)
    if db_book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return db_book
