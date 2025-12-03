"""
Movies endpoints for the OmniTrackr API.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas, models
from ..dependencies import get_db, get_current_user

router = APIRouter(prefix="/movies", tags=["movies"])


@router.get("/", response_model=List[schemas.Movie])
async def list_movies(
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud.get_movies(db, current_user.id, search=search, sort_by=sort_by, order=order)


@router.get("/{movie_id}", response_model=schemas.Movie)
async def get_movie(
    movie_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_movie = crud.get_movie_by_id(db, current_user.id, movie_id)
    if db_movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return db_movie


@router.post("/", response_model=schemas.Movie, status_code=201)
async def create_movie(
    movie: schemas.MovieCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return crud.create_movie(db, current_user.id, movie)


@router.put("/{movie_id}", response_model=schemas.Movie)
async def update_movie(
    movie_id: int,
    movie: schemas.MovieUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_movie = crud.update_movie(db, current_user.id, movie_id, movie)
    if db_movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return db_movie


@router.delete("/{movie_id}", response_model=schemas.Movie)
async def delete_movie(
    movie_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_movie = crud.delete_movie(db, current_user.id, movie_id)
    if db_movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return db_movie

