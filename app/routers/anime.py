"""
Anime endpoints for the OmniTrackr API.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas, models
from ..dependencies import get_db, get_current_user

router = APIRouter(prefix="/anime", tags=["anime"])


@router.get("/", response_model=List[schemas.Anime])
async def list_anime(
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud.get_anime(db, current_user.id, search=search, sort_by=sort_by, order=order)


@router.get("/{anime_id}", response_model=schemas.Anime)
async def get_anime(
    anime_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_anime = crud.get_anime_by_id(db, current_user.id, anime_id)
    if db_anime is None:
        raise HTTPException(status_code=404, detail="Anime not found")
    return db_anime


@router.post("/", response_model=schemas.Anime, status_code=201)
async def create_anime(
    anime: schemas.AnimeCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return crud.create_anime(db, current_user.id, anime)


@router.put("/{anime_id}", response_model=schemas.Anime)
async def update_anime(
    anime_id: int,
    anime: schemas.AnimeUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_anime = crud.update_anime(db, current_user.id, anime_id, anime)
    if db_anime is None:
        raise HTTPException(status_code=404, detail="Anime not found")
    return db_anime


@router.delete("/{anime_id}", response_model=schemas.Anime)
async def delete_anime(
    anime_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_anime = crud.delete_anime(db, current_user.id, anime_id)
    if db_anime is None:
        raise HTTPException(status_code=404, detail="Anime not found")
    return db_anime

