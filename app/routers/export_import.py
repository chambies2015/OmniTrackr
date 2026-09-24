"""
Export/Import endpoints for the OmniTrackr API.
"""
import json
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from .. import crud, schemas, models
from ..dependencies import get_db, get_current_user
from ..progress import CATEGORIES as PROGRESS_CATEGORIES, get_checkpoint_map, serialize_checkpoint, validate_checkpoint, stage_import_checkpoint, lock_progress_owner
from .activity import _serialize as serialize_activity, import_activity_entries

router = APIRouter(prefix="", tags=["export-import"])

MAX_JSON_IMPORT_BYTES = 25 * 1024 * 1024
COLLECTION_MEDIA_MODELS = {
    "movies": models.Movie, "tv-shows": models.TVShow, "anime": models.Anime,
    "video-games": models.VideoGame, "music": models.Music, "books": models.Book,
}
COLLECTION_MATCH_FIELDS = {
    "movies": ("year", "director"),
    "tv-shows": ("year",),
    "anime": ("year",),
    "video-games": ("release_date",),
    "music": ("year", "artist"),
    "books": ("year", "author"),
}


def _collection_media_lookup(db: Session, collections: list[models.Collection], user_id: int) -> dict:
    references = {category: set() for category in COLLECTION_MEDIA_MODELS}
    for collection in collections:
        for item in collection.items:
            if item.category in references:
                references[item.category].add(item.item_id)
    lookup = {}
    for category, item_ids in references.items():
        if not item_ids:
            continue
        model = COLLECTION_MEDIA_MODELS[category]
        for media in db.query(model).filter(model.user_id == user_id, model.id.in_(item_ids)).all():
            lookup[(category, media.id)] = media
    return lookup


def _exported_identity(media, category: str) -> dict:
    identity = {}
    for field in COLLECTION_MATCH_FIELDS[category]:
        value = getattr(media, field, None)
        identity[field] = value.isoformat() if isinstance(value, date) else value
    return identity


def _apply_import_identity(query, model, category: str, raw_item: dict):
    """Narrow new backups to the exact same-titled edition; retain old backup compatibility."""
    for field in COLLECTION_MATCH_FIELDS[category]:
        if field not in raw_item or raw_item[field] is None:
            continue
        value = raw_item[field]
        try:
            if field == "release_date" and isinstance(value, str):
                value = date.fromisoformat(value)
            elif field == "year":
                value = int(value)
        except (TypeError, ValueError):
            return None
        column = getattr(model, field)
        if isinstance(value, str):
            query = query.filter(func.lower(column) == value.strip().lower())
        else:
            query = query.filter(column == value)
    return query


def _export_collections(db: Session, user_id: int) -> list[dict]:
    collections = db.query(models.Collection).options(selectinload(models.Collection.items)).filter(
        models.Collection.user_id == user_id
    ).all()
    media_lookup = _collection_media_lookup(db, collections, user_id)
    exported = []
    for collection in collections:
        items = []
        for item in sorted(collection.items, key=lambda entry: (entry.position, entry.id)):
            media = media_lookup.get((item.category, item.item_id))
            if media:
                items.append({
                    "category": item.category,
                    "title": media.title,
                    "position": item.position,
                    "curator_note": item.curator_note,
                    **_exported_identity(media, item.category),
                })
        exported.append({
            "name": collection.name,
            "description": collection.description,
            "cover_url": collection.cover_url,
            "items": items,
        })
    return exported


def _export_progress(db: Session, user_id: int) -> list[dict]:
    checkpoints = get_checkpoint_map(db, user_id)
    exported = []
    for category, model in PROGRESS_CATEGORIES.items():
        ids = [item_id for (key, item_id) in checkpoints if key == category]
        if not ids:
            continue
        for media in db.query(model).filter(model.user_id == user_id, model.id.in_(ids)).order_by(model.id).all():
            progress = serialize_checkpoint(checkpoints[(category, media.id)])
            exported.append({
                "category": category, "title": media.title, **_exported_identity(media, category),
                "checkpoint": {key: progress[key] for key in ("unit", "position", "season", "note")},
                "updated_at": progress["updated_at"],
            })
    return exported


def _import_progress(db: Session, user_id: int, payloads: list[dict]) -> tuple[int, int]:
    """Restore only an unambiguous owned edition; never overwrite current progress."""
    if not payloads:
        return 0, 0
    created = skipped = 0
    try:
        lock_progress_owner(db, user_id)
        for raw in payloads:
            category = raw.get("category")
            title = raw.get("title")
            if not isinstance(category, str) or category not in PROGRESS_CATEGORIES or not isinstance(title, str) or not title.strip():
                skipped += 1
                continue
            try:
                checkpoint = validate_checkpoint(category, raw.get("checkpoint"))
                # New backups always carry complete edition identity, including nulls.
                if "year" not in raw or (raw["year"] is not None and (type(raw["year"]) is not int or not -2147483648 <= raw["year"] <= 2147483647)):
                    raise ValueError("Missing edition year")
                if category == "books" and ("author" not in raw or (raw["author"] is not None and not isinstance(raw["author"], str))):
                    raise ValueError("Missing edition author")
            except (ValidationError, ValueError, TypeError):
                skipped += 1
                continue
            model = PROGRESS_CATEGORIES[category]
            query = db.query(model).filter(
                model.user_id == user_id, func.lower(func.trim(model.title)) == func.lower(func.trim(title)),
                model.year == raw["year"],
            )
            if category == "books":
                author = raw["author"]
                query = query.filter(model.author.is_(None) if author is None else func.lower(func.trim(model.author)) == func.lower(func.trim(author)))
            matches = query.limit(2).all()
            if len(matches) != 1:
                skipped += 1
                continue
            if stage_import_checkpoint(db, user_id, category, matches[0].id, checkpoint):
                created += 1
            else:
                skipped += 1
        db.commit()
        return created, skipped
    except Exception:
        db.rollback()
        raise


def _import_collections(db: Session, user_id: int, payloads: list[dict]) -> tuple[int, int]:
    created = skipped = 0
    for raw in payloads[:200]:
        try:
            clean = schemas.CollectionCreate(
                name=raw.get("name"), description=raw.get("description"), cover_url=raw.get("cover_url")
            )
        except (ValidationError, AttributeError, TypeError):
            skipped += 1
            continue
        duplicate = db.query(models.Collection.id).filter(
            models.Collection.user_id == user_id,
            models.Collection.name == clean.name,
        ).first()
        if duplicate:
            skipped += 1
            continue
        collection = models.Collection(
            user_id=user_id,
            name=clean.name,
            description=clean.description,
            cover_url=clean.cover_url,
            is_public=False,
            moderation_status="pending",
        )
        db.add(collection)
        db.flush()
        position = 0
        raw_items = raw.get("items", [])
        if not isinstance(raw_items, list):
            raw_items = []
        for raw_item in raw_items[:50]:
            if not isinstance(raw_item, dict):
                continue
            category = raw_item.get("category")
            title = str(raw_item.get("title", "")).strip()
            model = COLLECTION_MEDIA_MODELS.get(category)
            if not model or not title:
                continue
            media_query = db.query(model).filter(
                model.user_id == user_id,
                func.lower(model.title) == title.lower(),
            )
            media_query = _apply_import_identity(media_query, model, category, raw_item)
            media = media_query.first() if media_query is not None else None
            if not media:
                continue
            note = str(raw_item.get("curator_note") or "").strip()[:500] or None
            db.add(models.CollectionItem(
                collection_id=collection.id,
                category=category,
                item_id=media.id,
                position=position,
                curator_note=note,
            ))
            position += 1
        created += 1
    db.commit()
    return created, skipped


@router.get("/export/", response_model=schemas.ExportData)
async def export_data(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export private media, custom tabs, journal, collections, and checkpoints."""
    movies = crud.get_all_movies(db, current_user.id)
    tv_shows = crud.get_all_tv_shows(db, current_user.id)
    anime = crud.get_all_anime(db, current_user.id)
    video_games = crud.get_all_video_games(db, current_user.id)
    music = crud.get_all_music(db, current_user.id)
    books = crud.get_all_books(db, current_user.id)
    custom_tabs = crud.get_all_custom_tabs_with_items(db, current_user.id)
    activities = db.query(models.ActivityEntry).filter(
        models.ActivityEntry.user_id == current_user.id
    ).order_by(models.ActivityEntry.occurred_at.desc(), models.ActivityEntry.id.desc()).all()
    collections = _export_collections(db, current_user.id)
    progress_checkpoints = _export_progress(db, current_user.id)

    export_metadata = {
        "export_timestamp": datetime.now().isoformat(),
        "version": "1.3",
        "account_created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "last_login_at": current_user.last_login_at.isoformat() if current_user.last_login_at else None,
        "successful_login_count": current_user.login_count or 0,
        "total_movies": len(movies),
        "total_tv_shows": len(tv_shows),
        "total_anime": len(anime),
        "total_video_games": len(video_games),
        "total_music": len(music),
        "total_books": len(books),
        "total_custom_tabs": len(custom_tabs),
        "total_activities": len(activities),
        "total_collections": len(collections),
        "total_progress_checkpoints": len(progress_checkpoints),
    }

    return schemas.ExportData(
        movies=movies,
        tv_shows=tv_shows,
        anime=anime,
        video_games=video_games,
        music=music,
        books=books,
        custom_tabs=custom_tabs,
        activities=[serialize_activity(entry) for entry in activities],
        collections=collections,
        progress_checkpoints=progress_checkpoints,
        export_metadata=export_metadata
    )


@router.post("/import/", response_model=schemas.ImportResult)
async def import_data(
    import_data: schemas.ImportData,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Import movies, TV shows, anime, video games, music, books, and custom tabs from JSON data"""
    movies_created, movies_updated, movie_errors = crud.import_movies(db, current_user.id, import_data.movies)
    tv_shows_created, tv_shows_updated, tv_show_errors = crud.import_tv_shows(db, current_user.id, import_data.tv_shows)
    anime_created, anime_updated, anime_errors = crud.import_anime(db, current_user.id, import_data.anime)
    video_games_created, video_games_updated, video_game_errors = crud.import_video_games(db, current_user.id, import_data.video_games)
    music_created, music_updated, music_errors = crud.import_music(db, current_user.id, import_data.music)
    books_created, books_updated, book_errors = crud.import_books(db, current_user.id, import_data.books)
    custom_tabs_created, custom_tabs_updated, custom_tab_errors = crud.import_custom_tabs(db, current_user.id, import_data.custom_tabs)
    activities_created, activities_skipped = import_activity_entries(db, current_user.id, import_data.activities)
    collections_created, collections_skipped = _import_collections(db, current_user.id, import_data.collections)
    progress_created, progress_skipped = _import_progress(db, current_user.id, import_data.progress_checkpoints)

    all_errors = movie_errors + tv_show_errors + anime_errors + video_game_errors + music_errors + book_errors + custom_tab_errors

    return schemas.ImportResult(
        movies_created=movies_created,
        movies_updated=movies_updated,
        tv_shows_created=tv_shows_created,
        tv_shows_updated=tv_shows_updated,
        anime_created=anime_created,
        anime_updated=anime_updated,
        video_games_created=video_games_created,
        video_games_updated=video_games_updated,
        music_created=music_created,
        music_updated=music_updated,
        books_created=books_created,
        books_updated=books_updated,
        custom_tabs_created=custom_tabs_created,
        custom_tabs_updated=custom_tabs_updated,
        activities_created=activities_created,
        activities_skipped=activities_skipped,
        collections_created=collections_created,
        collections_skipped=collections_skipped,
        progress_created=progress_created,
        progress_skipped=progress_skipped,
        errors=all_errors
    )


@router.post("/import/file/", response_model=schemas.ImportResult)
async def import_from_file(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Import data from a JSON file upload"""
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="File must be a JSON file")

    try:
        content = await file.read(MAX_JSON_IMPORT_BYTES + 1)
        if len(content) > MAX_JSON_IMPORT_BYTES:
            raise HTTPException(status_code=413, detail="JSON import exceeds the 25MB limit")
        data = json.loads(content.decode('utf-8'))

        # Validate the imported data structure
        # Note: 'anime', 'video_games', 'music', and 'books' are optional for backward compatibility with old export files
        if 'movies' not in data or 'tv_shows' not in data:
            raise HTTPException(status_code=400, detail="Invalid file format. Expected 'movies' and 'tv_shows' arrays. 'anime', 'video_games', 'music', and 'books' are optional for backward compatibility.")

        # Convert to Pydantic models
        movies = [schemas.MovieCreate(**movie) for movie in data.get('movies', [])]
        tv_shows = [schemas.TVShowCreate(**tv_show) for tv_show in data.get('tv_shows', [])]
        anime = [schemas.AnimeCreate(**anime_item) for anime_item in data.get('anime', [])]
        video_games = [schemas.VideoGameCreate(**video_game) for video_game in data.get('video_games', [])]
        music = [schemas.MusicCreate(**music_item) for music_item in data.get('music', [])]
        books = [schemas.BookCreate(**book) for book in data.get('books', [])]
        custom_tabs = data.get('custom_tabs', [])
        activities = [schemas.ActivityEntryImport(**entry) for entry in data.get('activities', [])]
        collections = data.get('collections', [])

        import_data = schemas.ImportData(movies=movies, tv_shows=tv_shows, anime=anime, video_games=video_games, music=music, books=books, custom_tabs=custom_tabs, activities=activities, collections=collections, progress_checkpoints=data.get('progress_checkpoints', []))

        # Import the data
        movies_created, movies_updated, movie_errors = crud.import_movies(db, current_user.id, import_data.movies)
        tv_shows_created, tv_shows_updated, tv_show_errors = crud.import_tv_shows(db, current_user.id, import_data.tv_shows)
        anime_created, anime_updated, anime_errors = crud.import_anime(db, current_user.id, import_data.anime)
        video_games_created, video_games_updated, video_game_errors = crud.import_video_games(db, current_user.id, import_data.video_games)
        music_created, music_updated, music_errors = crud.import_music(db, current_user.id, import_data.music)
        books_created, books_updated, book_errors = crud.import_books(db, current_user.id, import_data.books)
        custom_tabs_created, custom_tabs_updated, custom_tab_errors = crud.import_custom_tabs(db, current_user.id, import_data.custom_tabs)
        activities_created, activities_skipped = import_activity_entries(db, current_user.id, import_data.activities)
        collections_created, collections_skipped = _import_collections(db, current_user.id, import_data.collections)
        progress_created, progress_skipped = _import_progress(db, current_user.id, import_data.progress_checkpoints)

        all_errors = movie_errors + tv_show_errors + anime_errors + video_game_errors + music_errors + book_errors + custom_tab_errors

        return schemas.ImportResult(
            movies_created=movies_created,
            movies_updated=movies_updated,
            tv_shows_created=tv_shows_created,
            tv_shows_updated=tv_shows_updated,
            anime_created=anime_created,
            anime_updated=anime_updated,
            video_games_created=video_games_created,
            video_games_updated=video_games_updated,
            music_created=music_created,
            music_updated=music_updated,
            books_created=books_created,
            books_updated=books_updated,
            custom_tabs_created=custom_tabs_created,
            custom_tabs_updated=custom_tabs_updated,
            activities_created=activities_created,
            activities_skipped=activities_skipped,
            collections_created=collections_created,
            collections_skipped=collections_skipped,
            progress_created=progress_created,
            progress_skipped=progress_skipped,
            errors=all_errors
        )

    except HTTPException:
        # Preserve intentional client errors instead of masking them as a 500.
        raise
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except (ValidationError, TypeError, AttributeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid import data: {str(e)}")
    except Exception:
        raise HTTPException(status_code=500, detail="Error processing import file")

