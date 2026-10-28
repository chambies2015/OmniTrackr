"""
Manga endpoints for the OmniTrackr API.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..integer_bounds import PositiveDatabaseId
from .. import crud, schemas, models
from ..dependencies import get_db, get_current_user
from .activity import record_finished_on_add

router = APIRouter(prefix="/manga", tags=["manga"])


@router.get("/", response_model=List[schemas.Manga])
def list_manga(
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud.get_manga(db, current_user.id, search=search, sort_by=sort_by, order=order)


@router.get("/{manga_id}", response_model=schemas.Manga)
def get_manga(
    manga_id: PositiveDatabaseId,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_manga = crud.get_manga_by_id(db, current_user.id, manga_id)
    if db_manga is None:
        raise HTTPException(status_code=404, detail="Manga not found")
    return db_manga


@router.post("/", response_model=schemas.Manga, status_code=201)
def create_manga(
    manga: schemas.MangaCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return record_finished_on_add(db, current_user.id, "manga", crud.create_manga(db, current_user.id, manga))


@router.put("/{manga_id}", response_model=schemas.Manga)
def update_manga(
    manga_id: PositiveDatabaseId,
    manga: schemas.MangaUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_manga = crud.update_manga(db, current_user.id, manga_id, manga)
    if db_manga is None:
        raise HTTPException(status_code=404, detail="Manga not found")
    return db_manga


@router.delete("/{manga_id}", response_model=schemas.Manga)
def delete_manga(
    manga_id: PositiveDatabaseId,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_manga = crud.delete_manga(db, current_user.id, manga_id)
    if db_manga is None:
        raise HTTPException(status_code=404, detail="Manga not found")
    return db_manga
