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


def get_all_music(db: Session, user_id: int) -> List[models.Music]:
    """Get all music for export"""
    return db.query(models.Music).filter(models.Music.user_id == user_id).all()


def get_all_books(db: Session, user_id: int) -> List[models.Book]:
    """Get all books for export"""
    return db.query(models.Book).filter(models.Book.user_id == user_id).all()


def get_all_custom_tabs_with_items(db: Session, user_id: int) -> List[dict]:
    """Get all custom tabs with their items for export"""
    import json
    from ..crud import custom_tabs
    
    tabs = custom_tabs.get_custom_tabs(db, user_id)
    result = []
    
    for tab in tabs:
        items = custom_tabs.get_custom_tab_items(db, user_id, tab.id)
        tab_dict = {
            "name": tab.name,
            "source_type": tab.source_type,
            "allow_uploads": tab.allow_uploads,
            "fields": [
                {
                    "key": field.key,
                    "label": field.label,
                    "field_type": field.field_type,
                    "required": field.required,
                    "order": field.order
                }
                for field in tab.fields
            ],
            "items": [
                {
                    "title": item.title,
                    "field_values": json.loads(item.field_values) if item.field_values else {},
                    "poster_url": item.poster_url
                }
                for item in items
            ]
        }
        result.append(tab_dict)
    
    return result


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
                update_dict = movie_data.dict(exclude_unset=True)
                allowed_fields = {'title', 'director', 'year', 'rating', 'watched', 'review', 'poster_url'}
                for field, value in update_dict.items():
                    if field in allowed_fields:
                        if field == 'rating' and value is not None:
                            value = round(float(value), 1)
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
                update_dict = tv_show_data.dict(exclude_unset=True)
                allowed_fields = {'title', 'year', 'seasons', 'episodes', 'rating', 'watched', 'review', 'poster_url'}
                for field, value in update_dict.items():
                    if field in allowed_fields:
                        if field == 'rating' and value is not None:
                            value = round(float(value), 1)
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
                update_dict = anime_data.dict(exclude_unset=True)
                allowed_fields = {'title', 'year', 'seasons', 'episodes', 'rating', 'watched', 'review', 'poster_url'}
                for field, value in update_dict.items():
                    if field in allowed_fields:
                        if field == 'rating' and value is not None:
                            value = round(float(value), 1)
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
                allowed_fields = {'title', 'release_date', 'genres', 'rating', 'played', 'review', 'cover_art_url', 'rawg_link'}
                for field, value in update_dict.items():
                    if field in allowed_fields:
                        if field == 'rating' and value is not None:
                            value = round(float(value), 1)
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


def find_music_by_title_and_artist(db: Session, user_id: int, title: str, artist: str) -> Optional[models.Music]:
    """Find music by title and artist for import conflict resolution"""
    return db.query(models.Music).filter(
        models.Music.user_id == user_id,
        models.Music.title == title,
        models.Music.artist == artist
    ).first()


def import_music(db: Session, user_id: int, music: List[schemas.MusicCreate]) -> tuple[int, int, List[str]]:
    """Import music, returning (created_count, updated_count, errors)"""
    created = 0
    updated = 0
    errors = []
    
    for music_data in music:
        try:
            existing_music = find_music_by_title_and_artist(
                db, user_id, music_data.title, music_data.artist
            )
            
            if existing_music:
                update_dict = music_data.dict(exclude_unset=True)
                allowed_fields = {'title', 'artist', 'year', 'genre', 'rating', 'listened', 'review', 'cover_art_url'}
                for field, value in update_dict.items():
                    if field in allowed_fields:
                        if field == 'rating' and value is not None:
                            value = round(float(value), 1)
                        setattr(existing_music, field, value)
                updated += 1
            else:
                music_dict = music_data.dict()
                if music_dict.get('rating') is not None:
                    music_dict['rating'] = round(float(music_dict['rating']), 1)
                db_music = models.Music(**music_dict, user_id=user_id)
                db.add(db_music)
                created += 1
        except Exception as e:
            errors.append(f"Error importing music '{music_data.title}': {str(e)}")
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append(f"Database error during music import: {str(e)}")
        return 0, 0, errors
    
    return created, updated, errors


def find_book_by_title_and_author(db: Session, user_id: int, title: str, author: str) -> Optional[models.Book]:
    """Find book by title and author for import conflict resolution"""
    return db.query(models.Book).filter(
        models.Book.user_id == user_id,
        models.Book.title == title,
        models.Book.author == author
    ).first()


def import_books(db: Session, user_id: int, books: List[schemas.BookCreate]) -> tuple[int, int, List[str]]:
    """Import books, returning (created_count, updated_count, errors)"""
    created = 0
    updated = 0
    errors = []
    
    for book_data in books:
        try:
            existing_book = find_book_by_title_and_author(
                db, user_id, book_data.title, book_data.author
            )
            
            if existing_book:
                update_dict = book_data.dict(exclude_unset=True)
                allowed_fields = {'title', 'author', 'year', 'genre', 'rating', 'read', 'review', 'cover_art_url'}
                for field, value in update_dict.items():
                    if field in allowed_fields:
                        if field == 'rating' and value is not None:
                            value = round(float(value), 1)
                        setattr(existing_book, field, value)
                updated += 1
            else:
                book_dict = book_data.dict()
                if book_dict.get('rating') is not None:
                    book_dict['rating'] = round(float(book_dict['rating']), 1)
                db_book = models.Book(**book_dict, user_id=user_id)
                db.add(db_book)
                created += 1
        except Exception as e:
            errors.append(f"Error importing book '{book_data.title}': {str(e)}")
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append(f"Database error during book import: {str(e)}")
        return 0, 0, errors
    
    return created, updated, errors


def import_custom_tabs(db: Session, user_id: int, custom_tabs_data: List[dict]) -> tuple[int, int, List[str]]:
    """Import custom tabs with their items, returning (created_count, updated_count, errors)"""
    from ..crud import custom_tabs
    from .. import schemas
    
    created = 0
    updated = 0
    errors = []
    
    for tab_data in custom_tabs_data:
        try:
            if "name" not in tab_data:
                errors.append("Custom tab missing 'name' field")
                continue
            
            existing_tabs = custom_tabs.get_custom_tabs(db, user_id)
            existing_tab = next((t for t in existing_tabs if t.name == tab_data["name"]), None)
            
            tab_create_data = {
                "name": tab_data["name"],
                "source_type": tab_data.get("source_type", "none"),
                "allow_uploads": tab_data.get("allow_uploads", True),
                "fields": tab_data.get("fields", [])
            }
            
            tab_create = schemas.CustomTabCreate(**tab_create_data)
            
            if existing_tab:
                tab_update = schemas.CustomTabUpdate(
                    name=tab_create.name,
                    source_type=tab_create.source_type,
                    allow_uploads=tab_create.allow_uploads,
                    fields=tab_create.fields
                )
                updated_tab = custom_tabs.update_custom_tab(db, user_id, existing_tab.id, tab_update)
                if updated_tab:
                    tab_id = updated_tab.id
                    updated += 1
                else:
                    errors.append(f"Failed to update custom tab '{tab_data['name']}'")
                    continue
            else:
                new_tab = custom_tabs.create_custom_tab(db, user_id, tab_create)
                tab_id = new_tab.id
                created += 1
            
            items = tab_data.get("items", [])
            for item_data in items:
                try:
                    item_create = schemas.CustomTabItemCreate(
                        title=item_data["title"],
                        field_values=item_data.get("field_values", {}),
                        poster_url=item_data.get("poster_url")
                    )
                    item_result, error_msg = custom_tabs.create_custom_tab_item(db, user_id, tab_id, item_create)
                    if error_msg:
                        errors.append(f"Error importing item '{item_data.get('title', 'unknown')}' in tab '{tab_data['name']}': {error_msg}")
                except Exception as e:
                    errors.append(f"Error importing item '{item_data.get('title', 'unknown')}' in tab '{tab_data['name']}': {str(e)}")
            
        except Exception as e:
            errors.append(f"Error importing custom tab '{tab_data.get('name', 'unknown')}': {str(e)}")
    
    return created, updated, errors

