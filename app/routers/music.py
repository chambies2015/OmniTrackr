"""
Music endpoints for the OmniTrackr API.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas, models
from ..dependencies import get_db, get_current_user

router = APIRouter(prefix="/music", tags=["music"])


@router.get("/", response_model=List[schemas.Music])
async def list_music(
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud.get_music(db, current_user.id, search=search, sort_by=sort_by, order=order)


@router.get("/{music_id}", response_model=schemas.Music)
async def get_music(
    music_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_music = crud.get_music_by_id(db, current_user.id, music_id)
    if db_music is None:
        raise HTTPException(status_code=404, detail="Music not found")
    return db_music


@router.post("/", response_model=schemas.Music, status_code=201)
async def create_music(
    music: schemas.MusicCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return crud.create_music(db, current_user.id, music)


@router.put("/{music_id}", response_model=schemas.Music)
async def update_music(
    music_id: int,
    music: schemas.MusicUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_music = crud.update_music(db, current_user.id, music_id, music)
    if db_music is None:
        raise HTTPException(status_code=404, detail="Music not found")
    return db_music


@router.delete("/{music_id}", response_model=schemas.Music)
async def delete_music(
    music_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_music = crud.delete_music(db, current_user.id, music_id)
    if db_music is None:
        raise HTTPException(status_code=404, detail="Music not found")
    return db_music
