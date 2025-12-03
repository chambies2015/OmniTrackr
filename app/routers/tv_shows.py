"""
TV Shows endpoints for the OmniTrackr API.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas, models
from ..dependencies import get_db, get_current_user

router = APIRouter(prefix="/tv-shows", tags=["tv-shows"])


@router.get("/", response_model=List[schemas.TVShow])
async def list_tv_shows(
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud.get_tv_shows(db, current_user.id, search=search, sort_by=sort_by, order=order)


@router.get("/{tv_show_id}", response_model=schemas.TVShow)
async def get_tv_show(
    tv_show_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_tv_show = crud.get_tv_show_by_id(db, current_user.id, tv_show_id)
    if db_tv_show is None:
        raise HTTPException(status_code=404, detail="TV Show not found")
    return db_tv_show


@router.post("/", response_model=schemas.TVShow, status_code=201)
async def create_tv_show(
    tv_show: schemas.TVShowCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return crud.create_tv_show(db, current_user.id, tv_show)


@router.put("/{tv_show_id}", response_model=schemas.TVShow)
async def update_tv_show(
    tv_show_id: int,
    tv_show: schemas.TVShowUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_tv_show = crud.update_tv_show(db, current_user.id, tv_show_id, tv_show)
    if db_tv_show is None:
        raise HTTPException(status_code=404, detail="TV Show not found")
    return db_tv_show


@router.delete("/{tv_show_id}", response_model=schemas.TVShow)
async def delete_tv_show(
    tv_show_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_tv_show = crud.delete_tv_show(db, current_user.id, tv_show_id)
    if db_tv_show is None:
        raise HTTPException(status_code=404, detail="TV Show not found")
    return db_tv_show

