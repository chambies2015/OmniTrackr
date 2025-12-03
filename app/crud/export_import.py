"""
Export/Import CRUD operations for the OmniTrackr API.
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from .. import models, schemas


def get_all_movies(db: Session, user_id: int) -> List[models.Movie]:
    """Get all movies for export"""
    return db.query(models.Movie).filter(models.Movie.user_id == user_id).all()


def get_all_tv_shows(db: Session, user_id: int) -> List[models.TVShow]:
    """Get all TV shows for export"""
    return db.query(models.TVShow).filter(models.TVShow.user_id == user_id).all()


def get_all_anime(db: Session, user_id: int) -> List[models.Anime]:
    """Get all anime for export"""
    return db.query(models.Anime).filter(models.Anime.user_id == user_id).all()


def get_all_video_games(db: Session, user_id: int) -> List[models.VideoGame]:
    """Get all video games for export"""
    return db.query(models.VideoGame).filter(models.VideoGame.user_id == user_id).all()


def find_movie_by_title_and_director(db: Session, user_id: int, title: str, director: str) -> Optional[models.Movie]:
    """Find a movie by title and director for import conflict resolution"""
    return db.query(models.Movie).filter(models.Movie.user_id == user_id).filter(
        models.Movie.user_id == user_id,
        models.Movie.title == title,
        models.Movie.director == director
    ).first()


def find_tv_show_by_title_and_year(db: Session, user_id: int, title: str, year: int) -> Optional[models.TVShow]:
    """Find a TV show by title and year for import conflict resolution"""
    return db.query(models.TVShow).filter(models.TVShow.user_id == user_id).filter(
        models.TVShow.user_id == user_id,
        models.TVShow.title == title,
        models.TVShow.year == year
    ).first()


def find_anime_by_title_and_year(db: Session, user_id: int, title: str, year: int) -> Optional[models.Anime]:
    """Find an anime by title and year for import conflict resolution"""
    return db.query(models.Anime).filter(models.Anime.user_id == user_id).filter(
        models.Anime.user_id == user_id,
        models.Anime.title == title,
        models.Anime.year == year
    ).first()


def find_video_game_by_title_and_release_date(db: Session, user_id: int, title: str, release_date: Optional[datetime]) -> Optional[models.VideoGame]:
    """Find a video game by title and release date for import conflict resolution"""
    query = db.query(models.VideoGame).filter(
        models.VideoGame.user_id == user_id,
        models.VideoGame.title == title
    )
    if release_date is not None:
        query = query.filter(models.VideoGame.release_date == release_date)
    else:
        query = query.filter(models.VideoGame.release_date.is_(None))
    return query.first()


def import_movies(db: Session, user_id: int, movies: List[schemas.MovieCreate]) -> tuple[int, int, List[str]]:
    """Import movies, returning (created_count, updated_count, errors)"""
    created = 0
    updated = 0
    errors = []
    
    for movie_data in movies:
        try:
            existing_movie = find_movie_by_title_and_director(
                db, user_id, movie_data.title, movie_data.director
            )
            
            if existing_movie:
                for field, value in movie_data.dict(exclude_unset=True).items():
                    setattr(existing_movie, field, value)
                updated += 1
            else:
                db_movie = models.Movie(**movie_data.dict(), user_id=user_id)
                db.add(db_movie)
                created += 1
        except Exception as e:
            errors.append(f"Error importing movie '{movie_data.title}': {str(e)}")
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append(f"Database error during movie import: {str(e)}")
        return 0, 0, errors
    
    return created, updated, errors


def import_tv_shows(db: Session, user_id: int, tv_shows: List[schemas.TVShowCreate]) -> tuple[int, int, List[str]]:
    """Import TV shows, returning (created_count, updated_count, errors)"""
    created = 0
    updated = 0
    errors = []
    
    for tv_show_data in tv_shows:
        try:
            existing_tv_show = find_tv_show_by_title_and_year(
                db, user_id, tv_show_data.title, tv_show_data.year
            )
            
            if existing_tv_show:
                for field, value in tv_show_data.dict(exclude_unset=True).items():
                    setattr(existing_tv_show, field, value)
                updated += 1
            else:
                db_tv_show = models.TVShow(**tv_show_data.dict(), user_id=user_id)
                db.add(db_tv_show)
                created += 1
        except Exception as e:
            errors.append(f"Error importing TV show '{tv_show_data.title}': {str(e)}")
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append(f"Database error during TV show import: {str(e)}")
        return 0, 0, errors
    
    return created, updated, errors


def import_anime(db: Session, user_id: int, anime: List[schemas.AnimeCreate]) -> tuple[int, int, List[str]]:
    """Import anime, returning (created_count, updated_count, errors)"""
    created = 0
    updated = 0
    errors = []
    
    for anime_data in anime:
        try:
            existing_anime = find_anime_by_title_and_year(
                db, user_id, anime_data.title, anime_data.year
            )
            
            if existing_anime:
                for field, value in anime_data.dict(exclude_unset=True).items():
                    setattr(existing_anime, field, value)
                updated += 1
            else:
                db_anime = models.Anime(**anime_data.dict(), user_id=user_id)
                db.add(db_anime)
                created += 1
        except Exception as e:
            errors.append(f"Error importing anime '{anime_data.title}': {str(e)}")
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append(f"Database error during anime import: {str(e)}")
        return 0, 0, errors
    
    return created, updated, errors


def import_video_games(db: Session, user_id: int, video_games: List[schemas.VideoGameCreate]) -> tuple[int, int, List[str]]:
    """Import video games, returning (created_count, updated_count, errors)"""
    created = 0
    updated = 0
    errors = []
    
    for video_game_data in video_games:
        try:
            existing_video_game = find_video_game_by_title_and_release_date(
                db, user_id, video_game_data.title, video_game_data.release_date
            )
            
            if existing_video_game:
                update_dict = video_game_data.dict(exclude_unset=True)
                if 'rating' in update_dict and update_dict['rating'] is not None:
                    update_dict['rating'] = round(float(update_dict['rating']), 1)
                for field, value in update_dict.items():
                    setattr(existing_video_game, field, value)
                updated += 1
            else:
                video_game_dict = video_game_data.dict()
                if video_game_dict.get('rating') is not None:
                    video_game_dict['rating'] = round(float(video_game_dict['rating']), 1)
                db_video_game = models.VideoGame(**video_game_dict, user_id=user_id)
                db.add(db_video_game)
                created += 1
        except Exception as e:
            errors.append(f"Error importing video game '{video_game_data.title}': {str(e)}")
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append(f"Database error during video game import: {str(e)}")
        return 0, 0, errors
    
    return created, updated, errors

