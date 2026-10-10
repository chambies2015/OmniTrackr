"""
Export/Import CRUD operations for the OmniTrackr API.
"""
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import null
from sqlalchemy.orm import Session

from .. import models, schemas


def _library_row(data: dict) -> dict:
    """Keep a backup's added_at when it is a real past date; otherwise leave it unknown."""
    if "added_at" in data:
        added_at = data["added_at"]
        if added_at is not None and added_at.tzinfo is not None:
            added_at = added_at.astimezone(timezone.utc).replace(tzinfo=None)
        if added_at is not None and added_at > datetime.utcnow():
            added_at = None
        # null() rather than None: the ORM would otherwise fill in today's date.
        data["added_at"] = added_at if added_at is not None else null()
    return data


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


def _import_media(db: Session, user_id: int, entries, model, identity_fields, label):
    """Keep complete edition identity and make each saved row visible to the next."""
    created = updated = 0
    errors = []
    if not entries:
        return created, updated, errors
    from ..progress import lock_progress_owner
    # Reserve SQLite's outer write transaction before nested savepoints, and
    # serialize same-owner imports before their duplicate checks on every DB.
    lock_progress_owner(db, user_id)
    for incoming in entries:
        try:
            with db.begin_nested():
                identity = {field: getattr(incoming, field) for field in identity_fields}
                existing = db.query(model).filter_by(user_id=user_id, **identity).first()
                values = incoming.model_dump(exclude_unset=existing is not None)
                if values.get("rating") is not None:
                    values["rating"] = round(float(values["rating"]), 1)
                if existing is None:
                    db.add(model(**_library_row(values), user_id=user_id))
                else:
                    for field, value in values.items():
                        if field != "added_at":
                            setattr(existing, field, value)
                db.flush()
            if existing is None:
                created += 1
            else:
                updated += 1
        except Exception:
            errors.append(f"Could not import {label} '{incoming.title}'.")
    try:
        db.commit()
    except Exception:
        db.rollback()
        errors.append(f"The {label} import could not be saved.")
        return 0, 0, errors
    return created, updated, errors


def import_movies(db: Session, user_id: int, movies) -> tuple[int, int, List[str]]:
    return _import_media(db, user_id, movies, models.Movie, ("title", "director", "year"), "movie")


def import_tv_shows(db: Session, user_id: int, tv_shows) -> tuple[int, int, List[str]]:
    return _import_media(db, user_id, tv_shows, models.TVShow, ("title", "year"), "TV show")


def import_anime(db: Session, user_id: int, anime) -> tuple[int, int, List[str]]:
    return _import_media(db, user_id, anime, models.Anime, ("title", "year"), "anime")


def import_video_games(db: Session, user_id: int, video_games) -> tuple[int, int, List[str]]:
    return _import_media(db, user_id, video_games, models.VideoGame, ("title", "release_date"), "video game")


def find_music_by_title_and_artist(db: Session, user_id: int, title: str, artist: str) -> Optional[models.Music]:
    return db.query(models.Music).filter_by(user_id=user_id, title=title, artist=artist).first()


def import_music(db: Session, user_id: int, music) -> tuple[int, int, List[str]]:
    return _import_media(db, user_id, music, models.Music, ("title", "artist", "year"), "music")


def find_book_by_title_and_author(db: Session, user_id: int, title: str, author: str) -> Optional[models.Book]:
    return db.query(models.Book).filter_by(user_id=user_id, title=title, author=author).first()


def import_books(db: Session, user_id: int, books) -> tuple[int, int, List[str]]:
    return _import_media(db, user_id, books, models.Book, ("title", "author", "year"), "book")


def import_custom_tabs(db: Session, user_id: int, custom_tabs_data: List[dict]) -> tuple[int, int, List[str]]:
    """Import custom tabs with their items, returning (created_count, updated_count, errors)"""
    import json
    from collections import Counter
    from ..crud import custom_tabs
    from .. import schemas

    def item_identity(title, field_values, poster_url):
        return title, json.dumps(field_values or {}, sort_keys=True, separators=(",", ":")), poster_url

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
            # Preserve duplicate snapshots in a backup, without multiplying
            # those same rows every time the backup is restored.
            remaining = Counter(
                item_identity(item.title, json.loads(item.field_values) if item.field_values else {}, item.poster_url)
                for item in custom_tabs.get_custom_tab_items(db, user_id, tab_id)
            )
            for item_data in items:
                try:
                    item_create = schemas.CustomTabItemCreate(
                        title=item_data["title"],
                        field_values=item_data.get("field_values", {}),
                        poster_url=item_data.get("poster_url")
                    )
                    identity = item_identity(item_create.title, item_create.field_values, item_create.poster_url)
                    if remaining[identity]:
                        remaining[identity] -= 1
                        continue
                    item_result, error_msg = custom_tabs.create_custom_tab_item(db, user_id, tab_id, item_create)
                    if error_msg:
                        errors.append(f"Error importing item '{item_data.get('title', 'unknown')}' in tab '{tab_data['name']}': {error_msg}")
                except Exception as e:
                    errors.append(f"Error importing item '{item_data.get('title', 'unknown')}' in tab '{tab_data['name']}': {str(e)}")
            
        except Exception as e:
            errors.append(f"Error importing custom tab '{tab_data.get('name', 'unknown')}': {str(e)}")
    
    return created, updated, errors

