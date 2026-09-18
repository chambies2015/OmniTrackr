"""
Statistics endpoints for the OmniTrackr API.
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session
from sqlalchemy import and_, case, func, or_
from sqlalchemy.exc import IntegrityError

from .. import crud, schemas, models, return_prompt as return_prompt_tokens
from ..dependencies import get_db, get_current_user
from ..tasteprint import build_tasteprint

router = APIRouter(prefix="/statistics", tags=["statistics"])

LIBRARY_CATEGORIES = [
    {"key": "movies", "label": "Movie", "model": models.Movie, "done": models.Movie.watched, "status_label": "Not watched"},
    {"key": "tv-shows", "label": "TV show", "model": models.TVShow, "done": models.TVShow.watched, "status_label": "In progress"},
    {"key": "anime", "label": "Anime", "model": models.Anime, "done": models.Anime.watched, "status_label": "In progress"},
    {"key": "video-games", "label": "Game", "model": models.VideoGame, "done": models.VideoGame.played, "status_label": "Not played"},
    {"key": "music", "label": "Album", "model": models.Music, "done": models.Music.listened, "status_label": "Not listened"},
    {"key": "books", "label": "Book", "model": models.Book, "done": models.Book.read, "status_label": "Not read"},
]


@router.get("/tasteprint/", response_model=dict)
async def get_tasteprint(
    response: Response,
    categories: str | None = Query(None, max_length=120),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Build a private aggregate portrait from explicitly selected categories."""
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return build_tasteprint(db, current_user, categories)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


def _resolve_queue_pulse_items(
    queue_items: list[models.NextUpItem],
    categories: list[dict],
    db: Session,
    user_id: int,
    *,
    unfinished_only: bool = False,
) -> list[dict]:
    """Resolve an ordered queue with one media query per represented category."""
    category_by_key = {category["key"]: category for category in categories}
    ids_by_category: dict[str, list[int]] = {}
    for queue_item in queue_items:
        if queue_item.category in category_by_key:
            ids_by_category.setdefault(queue_item.category, []).append(queue_item.item_id)

    resolved = {}
    for category_key, item_ids in ids_by_category.items():
        category = category_by_key[category_key]
        model = category["model"]
        query = db.query(model).filter(model.user_id == user_id, model.id.in_(item_ids))
        if unfinished_only:
            query = query.filter(category["done"] == False)
        for item in query.all():
            resolved[(category_key, item.id)] = _pulse_item(item, category, [])

    return [
        resolved[(queue_item.category, queue_item.item_id)]
        for queue_item in queue_items
        if (queue_item.category, queue_item.item_id) in resolved
    ]


def _library_item_count(db: Session, user_id: int) -> int:
    """Count all built-in media with one database round trip."""
    counts = db.query(*[
        db.query(func.count(category["model"].id)).filter(
            category["model"].user_id == user_id
        ).scalar_subquery()
        for category in LIBRARY_CATEGORIES
    ]).one()
    return sum(int(count or 0) for count in counts)


@router.get("/today/", response_model=dict)
async def get_todays_pick(
    response: Response,
    offset: int = Query(0, ge=0, le=2147483647),
    category: str | None = Query(None, max_length=20),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Choose one private, unfinished title without modifying the library.

    The choice is stable for the day, while ``offset`` lets the interface offer
    another option. A deliberately ordered Next Up queue takes priority over the
    wider unfinished library so the user remains in control of the suggestion.
    """
    response.headers["Cache-Control"] = "private, no-store"
    categories = [dict(entry) for entry in LIBRARY_CATEGORIES]
    if category is not None:
        categories = [entry for entry in categories if entry["key"] == category]
        if not categories:
            raise HTTPException(status_code=422, detail="Unknown media category")
    by_key = {entry["key"]: entry for entry in categories}
    queue_items = db.query(models.NextUpItem).filter(
        models.NextUpItem.user_id == current_user.id,
        models.NextUpItem.category.in_(by_key),
    ).order_by(models.NextUpItem.position, models.NextUpItem.id).limit(25).all()
    queued = _resolve_queue_pulse_items(
        queue_items, categories, db, current_user.id, unfinished_only=True
    )

    if queued:
        choice = queued[offset % len(queued)]
        choice["reason"] = f"#{(offset % len(queued)) + 1} in your private Next Up queue"
        choice["source"] = "next_up"
        return {"pick": choice, "candidate_count": len(queued)}

    candidates = []
    for category in categories:
        items = db.query(category["model"]).filter(
            category["model"].user_id == current_user.id,
            category["done"] == False,
        ).order_by(category["model"].id.desc()).limit(12).all()
        candidates.extend(_pulse_item(item, category, []) for item in items)

    if not candidates:
        return {"pick": None, "candidate_count": 0}

    choice = candidates[(datetime.now(timezone.utc).date().toordinal() + current_user.id + offset) % len(candidates)]
    choice["reason"] = "A small, unfinished choice from your private library"
    choice["source"] = "library"
    return {"pick": choice, "candidate_count": len(candidates)}


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
        has_review = and_(
            model.review.isnot(None),
            func.length(func.trim(model.review)) > 0,
        )
        count, completed, rated, reviewed, public_review_count = db.query(
            func.count(model.id),
            func.sum(case((category["done_field"] == True, 1), else_=0)),
            func.sum(case((model.rating.isnot(None), 1), else_=0)),
            func.sum(case((has_review, 1), else_=0)),
            func.sum(case((and_(has_review, model.review_public == True), 1), else_=0)),
        ).filter(model.user_id == user_id).one()
        completed = int(completed or 0)
        rated = int(rated or 0)
        reviewed = int(reviewed or 0)
        public_review_count = int(public_review_count or 0)

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
    categories = [dict(entry) for entry in LIBRARY_CATEGORIES]
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

    queued_items = db.query(models.NextUpItem).filter(
        models.NextUpItem.user_id == current_user.id,
    ).order_by(models.NextUpItem.position, models.NextUpItem.id).limit(3).all()
    next_up_items = _resolve_queue_pulse_items(queued_items, categories, db, current_user.id)

    return {
        "continue_items": continue_items[:6],
        "reflection_items": reflection_items[:6],
        "next_up_items": next_up_items,
        "generated_at": datetime.now().isoformat(),
    }


@router.get("/return-deck/", response_model=dict)
async def get_return_deck(
    response: Response,
    request: Request,
    days_away: int | None = Query(None, ge=3, le=90),
    engagement_token: str | None = Header(
        None, alias="X-Return-Prompt", min_length=32, max_length=512
    ),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compose existing private signals into one optional return experience."""
    response.headers["Cache-Control"] = "private, no-store"
    signed_days_away = return_prompt_tokens.return_prompt_days_away(
        engagement_token, current_user.id
    )
    if signed_days_away is None or (days_away is not None and days_away != signed_days_away):
        raise HTTPException(status_code=403, detail="Return prompt is not active")
    days_away = signed_days_away
    library_item_count = _library_item_count(db, current_user.id)
    if library_item_count < 5:
        return {"eligible": False, "library_item_count": library_item_count}

    today = await get_todays_pick(Response(), 0, None, current_user, db)
    pulse = await get_library_pulse(current_user, db)
    primary = today.get("pick")
    alternatives = [
        item for item in pulse["continue_items"]
        if not primary or (item["category"], item["id"]) != (primary["category"], primary["id"])
    ]
    reflection_items = [
        item for item in pulse["reflection_items"]
        if not primary or (item["category"], item["id"]) != (primary["category"], primary["id"])
    ]
    if alternatives:
        reflection_items = [
            item for item in reflection_items
            if (item["category"], item["id"]) != (alternatives[0]["category"], alternatives[0]["id"])
        ]
    if not primary and not reflection_items:
        return {"eligible": False, "library_item_count": library_item_count}

    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_away)
    activity_rows = db.query(
        models.ActivityEntry.category,
        func.count(models.ActivityEntry.id),
        func.sum(case((models.ActivityEntry.action == "completed", 1), else_=0)),
        func.sum(case((func.length(func.trim(func.coalesce(models.ActivityEntry.note, ""))) > 0, 1), else_=0)),
    ).filter(
        models.ActivityEntry.user_id == current_user.id,
        models.ActivityEntry.occurred_at >= since,
    ).group_by(models.ActivityEntry.category).all()
    entry_count = sum(int(row[1] or 0) for row in activity_rows)
    completed_count = sum(int(row[2] or 0) for row in activity_rows)
    reflection_count = sum(int(row[3] or 0) for row in activity_rows)
    category_counts = {category["key"]: 0 for category in LIBRARY_CATEGORIES}
    for category_key, count, _, _ in activity_rows:
        if category_key in category_counts:
            category_counts[category_key] = int(count or 0)
    top_category_key = max(category_counts, key=category_counts.get) if any(category_counts.values()) else None
    category_by_key = {category["key"]: category for category in LIBRARY_CATEGORIES}

    return {
        "eligible": True,
        "library_item_count": library_item_count,
        "days_away": days_away,
        "primary": primary,
        "alternative": alternatives[0] if alternatives else None,
        "reflection": reflection_items[0] if reflection_items else None,
        "recap": {
            "entry_count": entry_count,
            "completed_count": completed_count,
            "reflection_count": reflection_count,
            "top_category_label": category_by_key[top_category_key]["label"] if top_category_key else None,
        },
    }


@router.post("/return-deck/engagement", response_model=dict)
async def record_return_deck_engagement(
    payload: schemas.ReturnPromptEngagement,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record one anonymous impression and one terminal outcome per signed deck."""
    if return_prompt_tokens.return_prompt_days_away(
        payload.engagement_token, current_user.id
    ) is None:
        raise HTTPException(status_code=403, detail="Return prompt is not active")
    # Receipts exist only to make the 24-hour prompt idempotent; retain a small
    # grace window for delayed requests without building a long-lived ledger.
    db.query(models.ReturnPromptEngagementReceipt).filter(
        models.ReturnPromptEngagementReceipt.created_at
        < datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
    ).delete(synchronize_session=False)
    metric_date = datetime.now(timezone.utc).date()
    metric_exists = db.query(models.ReturnPromptDailyMetric.id).filter(
        models.ReturnPromptDailyMetric.metric_date == metric_date
    ).first()
    if not metric_exists:
        db.add(models.ReturnPromptDailyMetric(metric_date=metric_date))
        try:
            db.commit()
        except IntegrityError:
            # Another request may create today's single aggregate row first.
            db.rollback()

    token_digest = return_prompt_tokens.return_prompt_token_digest(payload.engagement_token)
    event_kind = "shown" if payload.action == "shown" else "resolved"
    receipt = models.ReturnPromptEngagementReceipt(
        token_digest=token_digest,
        event_kind=event_kind,
        action=payload.action,
    )
    db.add(receipt)
    field = {
        "shown": "shown_count",
        "opened": "opened_count",
        "dismissed": "dismissed_count",
    }[payload.action]
    column = getattr(models.ReturnPromptDailyMetric, field)
    db.query(models.ReturnPromptDailyMetric).filter(
        models.ReturnPromptDailyMetric.metric_date == metric_date
    ).update({column: column + 1}, synchronize_session=False)
    try:
        db.commit()
    except IntegrityError:
        # The receipt uniqueness makes an impression and terminal outcome
        # idempotent. The receipt and aggregate increment commit together.
        db.rollback()
        return {"recorded": False}
    return {"recorded": True}


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
