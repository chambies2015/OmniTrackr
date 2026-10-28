"""
Podcast endpoints for the OmniTrackr API.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..integer_bounds import PositiveDatabaseId
from .. import crud, schemas, models
from ..dependencies import get_db, get_current_user
from .activity import record_finished_on_add

router = APIRouter(prefix="/podcasts", tags=["podcasts"])


@router.get("/", response_model=List[schemas.Podcast])
def list_podcasts(
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud.get_podcasts(db, current_user.id, search=search, sort_by=sort_by, order=order)


@router.get("/{podcast_id}", response_model=schemas.Podcast)
def get_podcast(
    podcast_id: PositiveDatabaseId,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_podcast = crud.get_podcast_by_id(db, current_user.id, podcast_id)
    if db_podcast is None:
        raise HTTPException(status_code=404, detail="Podcast not found")
    return db_podcast


@router.post("/", response_model=schemas.Podcast, status_code=201)
def create_podcast(
    podcast: schemas.PodcastCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return record_finished_on_add(db, current_user.id, "podcasts", crud.create_podcast(db, current_user.id, podcast))


@router.put("/{podcast_id}", response_model=schemas.Podcast)
def update_podcast(
    podcast_id: PositiveDatabaseId,
    podcast: schemas.PodcastUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_podcast = crud.update_podcast(db, current_user.id, podcast_id, podcast)
    if db_podcast is None:
        raise HTTPException(status_code=404, detail="Podcast not found")
    return db_podcast


@router.delete("/{podcast_id}", response_model=schemas.Podcast)
def delete_podcast(
    podcast_id: PositiveDatabaseId,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_podcast = crud.delete_podcast(db, current_user.id, podcast_id)
    if db_podcast is None:
        raise HTTPException(status_code=404, detail="Podcast not found")
    return db_podcast
