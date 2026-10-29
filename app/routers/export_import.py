"""
Export/Import endpoints for the OmniTrackr API.
"""
import json
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, File
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from .. import crud, schemas, models, game_playtime, library_export, title_origins
from ..integer_bounds import SQL_INTEGER_MAX
from ..dependencies import get_db, get_current_user
from ..progress import CATEGORIES as PROGRESS_CATEGORIES, get_checkpoint_map, serialize_checkpoint, validate_checkpoint, stage_import_checkpoint, lock_progress_owner
from .activity import _serialize as serialize_activity, import_activity_entries
from . import library as library_routes

router = APIRouter(prefix="", tags=["export-import"])

MAX_JSON_IMPORT_BYTES = 25 * 1024 * 1024
COLLECTION_MEDIA_MODELS = {
    "movies": models.Movie, "tv-shows": models.TVShow, "anime": models.Anime,
    "video-games": models.VideoGame, "music": models.Music, "books": models.Book,
    "manga": models.Manga, "podcasts": models.Podcast,
}
COLLECTION_MATCH_FIELDS = {
    "movies": ("year", "director"),
    "tv-shows": ("year",),
    "anime": ("year",),
    "video-games": ("release_date",),
    "music": ("year", "artist"),
    "books": ("year", "author"),
    "manga": ("year", "author"),
    "podcasts": ("year", "host"),
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
        if field not in raw_item:
            continue
        value = raw_item[field]
        if value is None:
            query = query.filter(getattr(model, field).is_(None))
            continue
        try:
            if field == "release_date":
                if not isinstance(value, str):
                    return None
                value = datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
            elif field == "year":
                if isinstance(value, bool):
                    return None
                value = int(value)
                if not 0 <= value <= SQL_INTEGER_MAX:
                    return None
            elif not isinstance(value, str):
                return None
        except (TypeError, ValueError, OverflowError):
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
                if category in ("books", "manga") and ("author" not in raw or (raw["author"] is not None and not isinstance(raw["author"], str))):
                    raise ValueError("Missing edition author")
            except (ValidationError, ValueError, TypeError):
                skipped += 1
                continue
            model = PROGRESS_CATEGORIES[category]
            query = db.query(model).filter(
                model.user_id == user_id, func.lower(func.trim(model.title)) == func.lower(func.trim(title)),
                model.year == raw["year"],
            )
            if category in ("books", "manga"):
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


def _import_origins(db: Session, user_id: int, payloads: list[dict]) -> tuple[int, int]:
    """Put back why-I-added-it notes on the one matching title. A title that already has one keeps it."""
    if not payloads:
        return 0, 0
    created = skipped = 0
    try:
        lock_progress_owner(db, user_id)
        for raw in payloads:
            category = raw.get("category") if isinstance(raw, dict) else None
            title = raw.get("title") if isinstance(raw, dict) else None
            model = COLLECTION_MEDIA_MODELS.get(category) if isinstance(category, str) else None
            if model is None or not isinstance(title, str) or not title.strip():
                skipped += 1
                continue
            query = db.query(model).filter(model.user_id == user_id, func.lower(model.title) == title.strip().lower())
            query = _apply_import_identity(query, model, category, raw)
            matches = query.limit(2).all() if query is not None else []
            if len(matches) == 1 and title_origins.import_row(db, user_id, category, matches[0].id, raw):
                db.flush()
                created += 1
            else:
                skipped += 1
        db.commit()
        return created, skipped
    except Exception:
        db.rollback()
        raise


def _import_collections(db: Session, user_id: int, payloads: list[dict]) -> tuple[int, int]:
    if payloads:
        lock_progress_owner(db, user_id)
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
        seen_items = set()
        raw_items = raw.get("items", [])
        if not isinstance(raw_items, list):
            raw_items = []
        for raw_item in raw_items[:50]:
            if not isinstance(raw_item, dict):
                continue
            category = raw_item.get("category")
            title = raw_item.get("title")
            if not isinstance(category, str) or not isinstance(title, str):
                continue
            title = title.strip()
            model = COLLECTION_MEDIA_MODELS.get(category)
            if not model or not title:
                continue
            media_query = db.query(model).filter(
                model.user_id == user_id,
                func.lower(model.title) == title.lower(),
            )
            media_query = _apply_import_identity(media_query, model, category, raw_item)
            matches = media_query.limit(2).all() if media_query is not None else []
            if len(matches) != 1:
                continue
            media = matches[0]
            identity = (category, media.id)
            if identity in seen_items:
                continue
            seen_items.add(identity)
            note = str(raw_item.get("curator_note") or "").strip()[:500] or None
            db.add(models.CollectionItem(
                collection_id=collection.id,
                category=category,
                item_id=media.id,
                position=position,
                curator_note=note,
            ))
            position += 1
        db.flush()
        created += 1
    db.commit()
    return created, skipped


def _export_tags(db: Session, user_id: int) -> list[dict]:
    """One entry per tagged title, with the fields an import uses to find the same edition."""
    rows = db.query(models.LibraryTag.category, models.LibraryTag.item_id, models.LibraryTag.label).filter(
        models.LibraryTag.user_id == user_id).order_by(models.LibraryTag.category, models.LibraryTag.item_id,
                                                         models.LibraryTag.label_key).all()
    wanted: dict[str, dict[int, list[str]]] = {}
    for category, item_id, label in rows:
        wanted.setdefault(category, {}).setdefault(item_id, []).append(label)
    exported = []
    for category, labels in wanted.items():
        model = COLLECTION_MEDIA_MODELS.get(category)
        if model is None:
            continue
        for media in db.query(model).filter(model.user_id == user_id, model.id.in_(list(labels))):
            exported.append({"category": category, "title": media.title, **_exported_identity(media, category),
                             "tags": labels[media.id]})
    return exported


def _export_views(db: Session, user_id: int) -> list[dict]:
    views = db.query(models.SavedLibraryView).filter_by(user_id=user_id).order_by(
        models.SavedLibraryView.category, models.SavedLibraryView.name_key).all()
    return [{"category": view.category, **{key: value for key, value in library_routes.view_out(view).items()
                                           if key != "id"}} for view in views]


def _import_playtimes(db: Session, user_id: int, payloads: list[dict]) -> tuple[int, int]:
    """Put backed-up Steam minutes on the one matching game. A game that already has some keeps them."""
    if not payloads:
        return 0, 0
    created = skipped = 0
    try:
        lock_progress_owner(db, user_id)
        have = {item_id for (item_id,) in db.query(models.GamePlaytime.item_id).filter(
            models.GamePlaytime.user_id == user_id)}
        for raw in payloads:
            title = raw.get("title") if isinstance(raw, dict) else None
            minutes = raw.get("minutes") if isinstance(raw, dict) else None
            source = raw.get("source") if isinstance(raw, dict) else None
            external_id = raw.get("external_id") if isinstance(raw, dict) else None
            if (not isinstance(title, str) or not title.strip() or type(minutes) is not int or minutes < 0
                    or source not in game_playtime.SOURCES):
                skipped += 1
                continue
            model = models.VideoGame
            query = db.query(model).filter(model.user_id == user_id, func.lower(model.title) == title.strip().lower())
            query = _apply_import_identity(query, model, "video-games", raw)
            matches = query.limit(2).all() if query is not None else []
            if len(matches) != 1 or matches[0].id in have:
                skipped += 1
                continue
            external = external_id if isinstance(external_id, str) and external_id.isdigit() and len(external_id) <= 32 else None
            db.add(models.GamePlaytime(user_id=user_id, item_id=matches[0].id, source=source, external_id=external,
                                       minutes=min(minutes, game_playtime.MAX_MINUTES)))
            have.add(matches[0].id)
            created += 1
        db.commit()
        return created, skipped
    except Exception:
        db.rollback()
        raise


def _import_tags(db: Session, user_id: int, payloads: list[dict]) -> tuple[int, int]:
    """Add backed-up tags to the one matching title, keeping the tags it already has."""
    if not payloads:
        return 0, 0
    created = skipped = 0
    try:
        lock_progress_owner(db, user_id)
        spelling = dict(db.query(models.LibraryTag.label_key, func.min(models.LibraryTag.label)).filter(
            models.LibraryTag.user_id == user_id).group_by(models.LibraryTag.label_key).all())
        for raw in payloads:
            category = raw.get("category") if isinstance(raw, dict) else None
            title = raw.get("title") if isinstance(raw, dict) else None
            labels = raw.get("tags") if isinstance(raw, dict) else None
            model = COLLECTION_MEDIA_MODELS.get(category) if isinstance(category, str) else None
            if model is None or not isinstance(title, str) or not title.strip() or not isinstance(labels, list):
                skipped += 1
                continue
            query = db.query(model).filter(model.user_id == user_id, func.lower(model.title) == title.strip().lower())
            query = _apply_import_identity(query, model, category, raw)
            matches = query.limit(2).all() if query is not None else []
            if len(matches) != 1:
                skipped += len(labels) or 1
                continue
            item_id = matches[0].id
            have = {key for (key,) in db.query(models.LibraryTag.label_key).filter_by(
                user_id=user_id, category=category, item_id=item_id)}
            for raw_label in labels[:library_routes.TAGS_PER_ITEM * 2]:
                try:
                    label = library_routes.clean_tag(raw_label) if isinstance(raw_label, str) else ""
                except HTTPException:
                    label = ""
                key = library_routes.tag_key(label) if label else ""
                if not key or key in have or len(have) >= library_routes.TAGS_PER_ITEM:
                    skipped += 1
                    continue
                label = spelling.setdefault(key, label)
                db.add(models.LibraryTag(user_id=user_id, category=category, item_id=item_id, label=label,
                                         label_key=key))
                have.add(key)
                created += 1
            db.flush()
        db.commit()
        return created, skipped
    except Exception:
        db.rollback()
        raise


def _import_views(db: Session, user_id: int, payloads: list[dict]) -> tuple[int, int]:
    """Restore saved views whose names are free, within each shelf's limit."""
    if not payloads:
        return 0, 0
    created = skipped = 0
    views = models.SavedLibraryView
    try:
        lock_progress_owner(db, user_id)
        for raw in payloads:
            category = raw.get("category") if isinstance(raw, dict) else None
            name = " ".join(str(raw.get("name") or "").split()) if isinstance(raw, dict) else ""
            if category not in library_routes.CATEGORIES or not name or len(name) > 40 or not name.isprintable():
                skipped += 1
                continue
            try:
                filters = library_routes.ViewFilters.model_validate(raw.get("filters") or {})
                if filters.sort not in library_routes.SORTS:
                    raise ValueError("unknown sort")
                filters.tag = library_routes.clean_tag(filters.tag) if filters.tag else ""
            except (ValidationError, ValueError, HTTPException):
                skipped += 1
                continue
            if filters.has_progress and category not in library_routes.PROGRESS_CATEGORIES:
                filters.has_progress = False
            filters.search = filters.search.strip()
            filters.recommended_by = title_origins.who_key(" ".join(filters.recommended_by.split()))
            key = name.casefold()
            existing = db.query(views.id).filter_by(user_id=user_id, category=category)
            if existing.filter_by(name_key=key).first() is not None \
                    or existing.count() >= library_routes.VIEWS_PER_SHELF:
                skipped += 1
                continue
            db.add(views(user_id=user_id, category=category, name=name, name_key=key,
                         filters=json.dumps(filters.model_dump(), separators=(",", ":"))))
            db.flush()
            created += 1
        db.commit()
        return created, skipped
    except Exception:
        db.rollback()
        raise


@router.get("/export/", response_model=schemas.ExportData)
def export_data(
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
    manga = crud.get_all_manga(db, current_user.id)
    podcasts = crud.get_all_podcasts(db, current_user.id)
    custom_tabs = crud.get_all_custom_tabs_with_items(db, current_user.id)
    activities = db.query(models.ActivityEntry).filter(
        models.ActivityEntry.user_id == current_user.id
    ).order_by(models.ActivityEntry.occurred_at.desc(), models.ActivityEntry.id.desc()).all()
    collections = _export_collections(db, current_user.id)
    progress_checkpoints = _export_progress(db, current_user.id)
    origins = title_origins.export_rows(db, current_user.id, _exported_identity)
    library_tags = _export_tags(db, current_user.id)
    saved_views = _export_views(db, current_user.id)
    playtimes = game_playtime.export_rows(db, current_user.id, _exported_identity)

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
        "total_manga": len(manga),
        "total_podcasts": len(podcasts),
        "total_custom_tabs": len(custom_tabs),
        "total_activities": len(activities),
        "total_collections": len(collections),
        "total_progress_checkpoints": len(progress_checkpoints),
        "total_title_origins": len(origins),
        "total_tagged_titles": len(library_tags),
        "total_saved_views": len(saved_views),
        "total_game_playtimes": len(playtimes),
    }

    return schemas.ExportData(
        movies=movies,
        tv_shows=tv_shows,
        anime=anime,
        video_games=video_games,
        music=music,
        books=books,
        manga=manga,
        podcasts=podcasts,
        custom_tabs=custom_tabs,
        activities=[serialize_activity(entry) for entry in activities],
        collections=collections,
        progress_checkpoints=progress_checkpoints,
        title_origins=origins,
        library_tags=library_tags,
        saved_views=saved_views,
        game_playtimes=playtimes,
        export_metadata=export_metadata
    )


@router.get("/export/{fmt}/")
def export_format(
    fmt: str,
    request: Request = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download the library as a spreadsheet ZIP, or in the layout Letterboxd or Goodreads imports."""
    if fmt not in library_export.FORMATS:
        raise HTTPException(status_code=404, detail="Unknown export format.")
    now = datetime.utcnow()
    stamp = now.strftime("%Y-%m-%d")
    if fmt == "spreadsheet":
        journal = db.query(models.ActivityEntry).filter(
            models.ActivityEntry.user_id == current_user.id
        ).order_by(models.ActivityEntry.occurred_at.desc(), models.ActivityEntry.id.desc()).all()
        library = library_export.load_library(db, current_user.id)
        content = library_export.spreadsheet_zip(
            library, journal,
            _export_collections(db, current_user.id), _export_progress(db, current_user.id),
            crud.get_all_custom_tabs_with_items(db, current_user.id), now,
            tags=library_export.tag_rows(db, current_user.id, library),
            origins=title_origins.export_rows(db, current_user.id, _exported_identity),
            playtimes=game_playtime.export_rows(db, current_user.id),
        )
        media_type, filename = "application/zip", f"omnitrackr-spreadsheets-{stamp}.zip"
    elif fmt == "goodreads":
        books = library_export.load_library(db, current_user.id, ["books"])["books"]
        content = library_export.goodreads_csv(db, current_user.id, books).encode("utf-8")
        media_type, filename = "text/csv; charset=utf-8", f"omnitrackr-goodreads-{stamp}.csv"
    else:
        movies = library_export.load_library(db, current_user.id, ["movies"])["movies"]
        watchlist = fmt == "letterboxd-watchlist"
        content = library_export.letterboxd_csv(db, current_user.id, movies, watchlist=watchlist).encode("utf-8")
        media_type, filename = "text/csv; charset=utf-8", f"omnitrackr-{fmt}-{stamp}.csv"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


@router.post("/import/", response_model=schemas.ImportResult)
def import_data(
    import_data: schemas.ImportData,
    request: Request = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Import movies, TV shows, anime, video games, music, books, manga, podcasts, and custom tabs from JSON data"""
    # A plain def runs in the threadpool, so a large restore never stalls other visitors.
    return _run_import(import_data, current_user, db)


def _run_import(import_data: schemas.ImportData, current_user: models.User, db: Session) -> schemas.ImportResult:
    movies_created, movies_updated, movie_errors = crud.import_movies(db, current_user.id, import_data.movies)
    tv_shows_created, tv_shows_updated, tv_show_errors = crud.import_tv_shows(db, current_user.id, import_data.tv_shows)
    anime_created, anime_updated, anime_errors = crud.import_anime(db, current_user.id, import_data.anime)
    video_games_created, video_games_updated, video_game_errors = crud.import_video_games(db, current_user.id, import_data.video_games)
    music_created, music_updated, music_errors = crud.import_music(db, current_user.id, import_data.music)
    books_created, books_updated, book_errors = crud.import_books(db, current_user.id, import_data.books)
    manga_created, manga_updated, manga_errors = crud.import_manga(db, current_user.id, import_data.manga)
    podcasts_created, podcasts_updated, podcast_errors = crud.import_podcasts(db, current_user.id, import_data.podcasts)
    custom_tabs_created, custom_tabs_updated, custom_tab_errors = crud.import_custom_tabs(db, current_user.id, import_data.custom_tabs)
    activities_created, activities_skipped = import_activity_entries(db, current_user.id, import_data.activities)
    collections_created, collections_skipped = _import_collections(db, current_user.id, import_data.collections)
    progress_created, progress_skipped = _import_progress(db, current_user.id, import_data.progress_checkpoints)
    origins_created, origins_skipped = _import_origins(db, current_user.id, import_data.title_origins)
    tags_created, tags_skipped = _import_tags(db, current_user.id, import_data.library_tags)
    views_created, views_skipped = _import_views(db, current_user.id, import_data.saved_views)
    playtimes_created, playtimes_skipped = _import_playtimes(db, current_user.id, import_data.game_playtimes)

    all_errors = movie_errors + tv_show_errors + anime_errors + video_game_errors + music_errors + book_errors + manga_errors + podcast_errors + custom_tab_errors

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
        manga_created=manga_created,
        manga_updated=manga_updated,
        podcasts_created=podcasts_created,
        podcasts_updated=podcasts_updated,
        custom_tabs_created=custom_tabs_created,
        custom_tabs_updated=custom_tabs_updated,
        activities_created=activities_created,
        activities_skipped=activities_skipped,
        collections_created=collections_created,
        collections_skipped=collections_skipped,
        progress_created=progress_created,
        progress_skipped=progress_skipped,
        origins_created=origins_created,
        origins_skipped=origins_skipped,
        tags_created=tags_created,
        tags_skipped=tags_skipped,
        views_created=views_created,
        views_skipped=views_skipped,
        playtimes_created=playtimes_created,
        playtimes_skipped=playtimes_skipped,
        errors=all_errors
    )


@router.post("/import/file/", response_model=schemas.ImportResult)
async def import_from_file(
    file: UploadFile = File(...),
    request: Request = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Import data from a JSON file upload"""
    if not file.filename or not file.filename.lower().endswith('.json'):
        raise HTTPException(status_code=400, detail="File must be a JSON file")

    try:
        content = await file.read(MAX_JSON_IMPORT_BYTES + 1)
        if len(content) > MAX_JSON_IMPORT_BYTES:
            raise HTTPException(status_code=413, detail="JSON import exceeds the 25MB limit")
        data = json.loads(content.decode('utf-8'))

        # Validate the imported data structure
        # Note: 'anime', 'video_games', 'music', and 'books' are optional for backward compatibility with old export files
        if not isinstance(data, dict) or 'movies' not in data or 'tv_shows' not in data:
            raise HTTPException(status_code=400, detail="Invalid file format. Expected 'movies' and 'tv_shows' arrays. 'anime', 'video_games', 'music', 'books', 'manga', and 'podcasts' are optional for backward compatibility.")

        # Reuse the body endpoint's schema and import behavior for native backups.
        import_payload = schemas.ImportData.model_validate(data)
        return await run_in_threadpool(_run_import, import_payload, current_user, db)

    except HTTPException:
        # Preserve intentional client errors instead of masking them as a 500.
        raise
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except (ValidationError, TypeError, AttributeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid import data: {str(e)}")
    except Exception:
        raise HTTPException(status_code=500, detail="Error processing import file")

