"""
Statistics endpoints for the OmniTrackr API.
"""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import crud, schemas, models
from ..dependencies import get_db, get_current_user

router = APIRouter(prefix="/statistics", tags=["statistics"])


@router.get("/", response_model=schemas.StatisticsDashboard)
async def get_statistics_dashboard(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive statistics dashboard"""
    watch_stats = crud.get_watch_statistics(db, current_user.id)
    rating_stats = crud.get_rating_statistics(db, current_user.id)
    year_stats = crud.get_year_statistics(db, current_user.id)
    director_stats = crud.get_director_statistics(db, current_user.id)

    return schemas.StatisticsDashboard(
        watch_stats=schemas.WatchStatistics(**watch_stats),
        rating_stats=schemas.RatingStatistics(**rating_stats),
        year_stats=schemas.YearStatistics(**year_stats),
        director_stats=schemas.DirectorStatistics(**director_stats),
        generated_at=datetime.now().isoformat()
    )


@router.get("/watch/", response_model=schemas.WatchStatistics)
async def get_watch_statistics(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get watch statistics"""
    stats = crud.get_watch_statistics(db, current_user.id)
    return schemas.WatchStatistics(**stats)


@router.get("/ratings/", response_model=schemas.RatingStatistics)
async def get_rating_statistics(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get rating statistics"""
    stats = crud.get_rating_statistics(db, current_user.id)
    return schemas.RatingStatistics(**stats)


@router.get("/years/", response_model=schemas.YearStatistics)
async def get_year_statistics(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get year-based statistics"""
    stats = crud.get_year_statistics(db, current_user.id)
    return schemas.YearStatistics(**stats)


@router.get("/directors/", response_model=schemas.DirectorStatistics)
async def get_director_statistics(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get director statistics"""
    stats = crud.get_director_statistics(db, current_user.id)
    return schemas.DirectorStatistics(**stats)


@router.get("/movies/", response_model=schemas.MovieStatistics)
async def get_movie_statistics(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get movie-specific statistics"""
    stats = crud.get_movie_statistics(db, current_user.id)
    return schemas.MovieStatistics(
        watch_stats=schemas.CategoryWatchStatistics(**stats["watch_stats"]),
        rating_stats=schemas.CategoryRatingStatistics(**stats["rating_stats"]),
        year_stats=schemas.CategoryYearStatistics(**stats["year_stats"]),
        director_stats=schemas.DirectorStatistics(**stats["director_stats"])
    )


@router.get("/tv-shows/", response_model=schemas.TVShowStatistics)
async def get_tv_show_statistics(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get TV show-specific statistics"""
    stats = crud.get_tv_show_statistics(db, current_user.id)
    return schemas.TVShowStatistics(
        watch_stats=schemas.CategoryWatchStatistics(**stats["watch_stats"]),
        rating_stats=schemas.CategoryRatingStatistics(**stats["rating_stats"]),
        year_stats=schemas.CategoryYearStatistics(**stats["year_stats"]),
        seasons_episodes_stats=schemas.SeasonsEpisodesStatistics(**stats["seasons_episodes_stats"])
    )


@router.get("/anime/", response_model=schemas.AnimeStatistics)
async def get_anime_statistics(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get anime-specific statistics"""
    stats = crud.get_anime_statistics(db, current_user.id)
    return schemas.AnimeStatistics(
        watch_stats=schemas.CategoryWatchStatistics(**stats["watch_stats"]),
        rating_stats=schemas.CategoryRatingStatistics(**stats["rating_stats"]),
        year_stats=schemas.CategoryYearStatistics(**stats["year_stats"]),
        seasons_episodes_stats=schemas.SeasonsEpisodesStatistics(**stats["seasons_episodes_stats"])
    )


@router.get("/video-games/", response_model=schemas.VideoGameStatistics)
async def get_video_game_statistics(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get video game-specific statistics"""
    stats = crud.get_video_game_statistics(db, current_user.id)
    return schemas.VideoGameStatistics(
        watch_stats=schemas.CategoryWatchStatistics(**stats["watch_stats"]),
        rating_stats=schemas.CategoryRatingStatistics(**stats["rating_stats"]),
        year_stats=schemas.CategoryYearStatistics(**stats["year_stats"]),
        genre_stats=schemas.GenreStatistics(**stats["genre_stats"])
    )
