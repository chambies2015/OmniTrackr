"""
Video Games endpoints for the OmniTrackr API.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas, models
from ..dependencies import get_db, get_current_user

router = APIRouter(prefix="/video-games", tags=["video-games"])


@router.get("/", response_model=List[schemas.VideoGame])
async def list_video_games(
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud.get_video_games(db, current_user.id, search=search, sort_by=sort_by, order=order)


@router.get("/{game_id}", response_model=schemas.VideoGame)
async def get_video_game(
    game_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_video_game = crud.get_video_game_by_id(db, current_user.id, game_id)
    if db_video_game is None:
        raise HTTPException(status_code=404, detail="Video game not found")
    return db_video_game


@router.post("/", response_model=schemas.VideoGame, status_code=201)
async def create_video_game(
    video_game: schemas.VideoGameCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return crud.create_video_game(db, current_user.id, video_game)


@router.put("/{game_id}", response_model=schemas.VideoGame)
async def update_video_game(
    game_id: int,
    video_game: schemas.VideoGameUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_video_game = crud.update_video_game(db, current_user.id, game_id, video_game)
    if db_video_game is None:
        raise HTTPException(status_code=404, detail="Video game not found")
    return db_video_game


@router.delete("/{game_id}", response_model=schemas.VideoGame)
async def delete_video_game(
    game_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_video_game = crud.delete_video_game(db, current_user.id, game_id)
    if db_video_game is None:
        raise HTTPException(status_code=404, detail="Video game not found")
    return db_video_game

