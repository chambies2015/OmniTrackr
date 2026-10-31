"""
Audiobook endpoints for the OmniTrackr API.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..integer_bounds import PositiveDatabaseId
from .. import crud, schemas, models
from ..dependencies import get_db, get_current_user
from .activity import record_finished_on_add

router = APIRouter(prefix="/audiobooks", tags=["audiobooks"])


@router.get("/", response_model=List[schemas.Audiobook])
def list_audiobooks(
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud.get_audiobooks(db, current_user.id, search=search, sort_by=sort_by, order=order)


@router.get("/{audiobook_id}", response_model=schemas.Audiobook)
def get_audiobook(
    audiobook_id: PositiveDatabaseId,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_audiobook = crud.get_audiobook_by_id(db, current_user.id, audiobook_id)
    if db_audiobook is None:
        raise HTTPException(status_code=404, detail="Audiobook not found")
    return db_audiobook


@router.post("/", response_model=schemas.Audiobook, status_code=201)
def create_audiobook(
    audiobook: schemas.AudiobookCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return record_finished_on_add(db, current_user.id, "audiobooks", crud.create_audiobook(db, current_user.id, audiobook))


@router.put("/{audiobook_id}", response_model=schemas.Audiobook)
def update_audiobook(
    audiobook_id: PositiveDatabaseId,
    audiobook: schemas.AudiobookUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_audiobook = crud.update_audiobook(db, current_user.id, audiobook_id, audiobook)
    if db_audiobook is None:
        raise HTTPException(status_code=404, detail="Audiobook not found")
    return db_audiobook


@router.delete("/{audiobook_id}", response_model=schemas.Audiobook)
def delete_audiobook(
    audiobook_id: PositiveDatabaseId,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_audiobook = crud.delete_audiobook(db, current_user.id, audiobook_id)
    if db_audiobook is None:
        raise HTTPException(status_code=404, detail="Audiobook not found")
    return db_audiobook
