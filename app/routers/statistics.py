"""
Statistics endpoints for the OmniTrackr API.
"""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from .. import crud, schemas, models
from ..dependencies import get_db, get_current_user

router = APIRouter(prefix="/statistics", tags=["statistics"])


def _count_public_reviews(db: Session, model, user_id: int) -> int:
    return db.query(model).filter(
        model.user_id == user_id,
        model.review_public == True,
        model.review.isnot(None),
        func.length(func.trim(model.review)) > 0
    ).count()


def _count_reviewed_items(db: Session, model, user_id: int) -> int:
    return db.query(model).filter(
        model.user_id == user_id,
        model.review.isnot(None),
        func.length(func.trim(model.review)) > 0
    ).count()


def _count_rated_items(db: Session, model, user_id: int) -> int:
    return db.query(model).filter(
        model.user_id == user_id,
        model.rating.isnot(None)
    ).count()


def _pulse_item(item, category: dict, prompts: list[str]) -> dict:
    """Serialize only the small, current-user fields needed by the dashboard pulse."""
    return {
        "id": item.id,
        "title": item.title,
        "category": category["key"],
        "category_label": category["label"],
        "status_label": category["status_label"],
        "prompts": prompts,
    }


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


@router.get("/insights/", response_model=dict)
async def get_library_insights(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get high-level library insights for the dashboard."""
    user_id = current_user.id
    categories = [
        {
            "key": "movies",
            "label": "Movies",
            "model": models.Movie,
            "done_field": models.Movie.watched,
        },
        {
            "key": "tv_shows",
            "label": "TV Shows",
            "model": models.TVShow,
            "done_field": models.TVShow.watched,
        },
        {
            "key": "anime",
            "label": "Anime",
            "model": models.Anime,
            "done_field": models.Anime.watched,
        },
        {
            "key": "video_games",
            "label": "Video Games",
            "model": models.VideoGame,
            "done_field": models.VideoGame.played,
        },
        {
            "key": "music",
            "label": "Music",
            "model": models.Music,
            "done_field": models.Music.listened,
        },
        {
            "key": "books",
            "label": "Books",
            "model": models.Book,
            "done_field": models.Book.read,
        },
    ]

    category_summaries = []
    total_items = 0
    completed_items = 0
    rated_items = 0
    reviewed_items = 0
    public_reviews = 0

    for category in categories:
        model = category["model"]
        count = db.query(model).filter(model.user_id == user_id).count()
        completed = db.query(model).filter(
            model.user_id == user_id,
            category["done_field"] == True
        ).count()
        rated = _count_rated_items(db, model, user_id)
        reviewed = _count_reviewed_items(db, model, user_id)
        public_review_count = _count_public_reviews(db, model, user_id)

        total_items += count
        completed_items += completed
        rated_items += rated
        reviewed_items += reviewed
        public_reviews += public_review_count

        category_summaries.append({
            "key": category["key"],
            "label": category["label"],
            "total": count,
            "completed": completed,
            "backlog": max(count - completed, 0),
            "rated": rated,
            "reviewed": reviewed,
            "public_reviews": public_review_count,
            "completion_percentage": round((completed / count * 100) if count else 0, 1),
        })

    top_category = max(category_summaries, key=lambda item: item["total"], default=None)
    most_complete_category = max(
        category_summaries,
        key=lambda item: (item["completion_percentage"], item["completed"]),
        default=None
    )

    return {
        "total_items": total_items,
        "completed_items": completed_items,
        "backlog_items": max(total_items - completed_items, 0),
        "rated_items": rated_items,
        "reviewed_items": reviewed_items,
        "public_reviews": public_reviews,
        "completion_percentage": round((completed_items / total_items * 100) if total_items else 0, 1),
        "rating_coverage_percentage": round((rated_items / total_items * 100) if total_items else 0, 1),
        "review_coverage_percentage": round((reviewed_items / total_items * 100) if total_items else 0, 1),
        "top_category": top_category,
        "most_complete_category": most_complete_category,
        "categories": category_summaries,
        "generated_at": datetime.now().isoformat()
    }


@router.get("/pulse/", response_model=dict)
async def get_library_pulse(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return a small, action-oriented slice of the current user's library.

    This intentionally avoids creating a new persistence model. It is a read-only
    dashboard helper that surfaces records that are unfinished or still missing the
    personal context that makes a library useful later.
    """
    categories = [
        {"key": "movies", "label": "Movie", "model": models.Movie, "done": models.Movie.watched, "status_label": "Not watched"},
        {"key": "tv-shows", "label": "TV show", "model": models.TVShow, "done": models.TVShow.watched, "status_label": "In progress"},
        {"key": "anime", "label": "Anime", "model": models.Anime, "done": models.Anime.watched, "status_label": "In progress"},
        {"key": "video-games", "label": "Game", "model": models.VideoGame, "done": models.VideoGame.played, "status_label": "Not played"},
        {"key": "music", "label": "Album", "model": models.Music, "done": models.Music.listened, "status_label": "Not listened"},
        {"key": "books", "label": "Book", "model": models.Book, "done": models.Book.read, "status_label": "Not read"},
    ]
    continue_items = []
    reflection_items = []

    for category in categories:
        model = category["model"]
        unfinished = db.query(model).filter(
            model.user_id == current_user.id,
            category["done"] == False,
        ).order_by(model.id.desc()).limit(2).all()
        continue_items.extend(_pulse_item(item, category, []) for item in unfinished)

        needs_context = db.query(model).filter(
            model.user_id == current_user.id,
            or_(
                model.rating.is_(None),
                model.review.is_(None),
                func.length(func.trim(model.review)) == 0,
            ),
        ).order_by(model.id.desc()).limit(2).all()
        for item in needs_context:
            prompts = []
            if item.rating is None:
                prompts.append("Add a rating")
            if not (item.review or "").strip():
                prompts.append("Leave a note")
            reflection_items.append(_pulse_item(item, category, prompts))

    return {
        "continue_items": continue_items[:6],
        "reflection_items": reflection_items[:6],
        "generated_at": datetime.now().isoformat(),
    }


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


@router.get("/music/", response_model=schemas.MusicStatistics)
async def get_music_statistics(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get music-specific statistics"""
    stats = crud.get_music_statistics(db, current_user.id)
    return schemas.MusicStatistics(
        watch_stats=schemas.CategoryWatchStatistics(**stats["watch_stats"]),
        rating_stats=schemas.CategoryRatingStatistics(**stats["rating_stats"]),
        year_stats=schemas.CategoryYearStatistics(**stats["year_stats"])
    )


@router.get("/books/", response_model=schemas.BookStatistics)
async def get_books_statistics(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get book-specific statistics"""
    stats = crud.get_books_statistics(db, current_user.id)
    return schemas.BookStatistics(
        watch_stats=schemas.CategoryWatchStatistics(**stats["watch_stats"]),
        rating_stats=schemas.CategoryRatingStatistics(**stats["rating_stats"]),
        year_stats=schemas.CategoryYearStatistics(**stats["year_stats"])
    )
