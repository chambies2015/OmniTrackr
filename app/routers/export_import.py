"""
Export/Import endpoints for the OmniTrackr API.
"""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from .. import crud, schemas, models
from ..dependencies import get_db, get_current_user

router = APIRouter(prefix="", tags=["export-import"])


@router.get("/export/", response_model=schemas.ExportData)
async def export_data(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export all movies, TV shows, anime, video games, music, books, and custom tabs as JSON"""
    movies = crud.get_all_movies(db, current_user.id)
    tv_shows = crud.get_all_tv_shows(db, current_user.id)
    anime = crud.get_all_anime(db, current_user.id)
    video_games = crud.get_all_video_games(db, current_user.id)
    music = crud.get_all_music(db, current_user.id)
    books = crud.get_all_books(db, current_user.id)
    custom_tabs = crud.get_all_custom_tabs_with_items(db, current_user.id)

    export_metadata = {
        "export_timestamp": datetime.now().isoformat(),
        "version": "1.0",
        "total_movies": len(movies),
        "total_tv_shows": len(tv_shows),
        "total_anime": len(anime),
        "total_video_games": len(video_games),
        "total_music": len(music),
        "total_books": len(books),
        "total_custom_tabs": len(custom_tabs)
    }

    return schemas.ExportData(
        movies=movies,
        tv_shows=tv_shows,
        anime=anime,
        video_games=video_games,
        music=music,
        books=books,
        custom_tabs=custom_tabs,
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
        content = await file.read()
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

        import_data = schemas.ImportData(movies=movies, tv_shows=tv_shows, anime=anime, video_games=video_games, music=music, books=books, custom_tabs=custom_tabs)

        # Import the data
        movies_created, movies_updated, movie_errors = crud.import_movies(db, current_user.id, import_data.movies)
        tv_shows_created, tv_shows_updated, tv_show_errors = crud.import_tv_shows(db, current_user.id, import_data.tv_shows)
        anime_created, anime_updated, anime_errors = crud.import_anime(db, current_user.id, import_data.anime)
        video_games_created, video_games_updated, video_game_errors = crud.import_video_games(db, current_user.id, import_data.video_games)
        music_created, music_updated, music_errors = crud.import_music(db, current_user.id, import_data.music)
        books_created, books_updated, book_errors = crud.import_books(db, current_user.id, import_data.books)
        custom_tabs_created, custom_tabs_updated, custom_tab_errors = crud.import_custom_tabs(db, current_user.id, import_data.custom_tabs)

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
            errors=all_errors
        )

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

