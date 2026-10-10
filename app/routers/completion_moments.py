"""Private completion reflections and monthly replay endpoints."""
from datetime import datetime
from typing import Dict, List, Tuple, Type

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas, title_pages
from ..integer_bounds import PositiveDatabaseId
from ..review_quality import AD_MIN_REVIEW_WORDS, evaluate_public_review
from .reviews import PUBLIC_REVIEW_DETAIL_MIN_CHARS, PUBLIC_REVIEW_MIN_CHARS
from ..progress import lock_progress_owner
from ..dependencies import get_current_user, get_db
from .activity import record_completion_activity

router = APIRouter(prefix="/completion-moments", tags=["completion-moments"])

CategoryDetails = Tuple[Type[models.Movie], str, str]
CATEGORIES: Dict[str, CategoryDetails] = {
    "movies": (models.Movie, "Movie", "watched"),
    "tv-shows": (models.TVShow, "TV show", "watched"),
    "anime": (models.Anime, "Anime", "watched"),
    "video-games": (models.VideoGame, "Game", "played"),
    "music": (models.Music, "Album", "listened"),
    "books": (models.Book, "Book", "read"),
}


def _serialize(moment: models.CompletionMoment) -> dict:
    return {
        "id": moment.id,
        "category": moment.category,
        "category_label": CATEGORIES[moment.category][1],
        "item_id": moment.item_id,
        "title": moment.title,
        "rating": moment.rating,
        "takeaway": moment.takeaway,
        "favorite": moment.favorite,
        "completed_at": moment.completed_at,
    }


def _parse_month(month: str | None) -> tuple[datetime, datetime]:
    if month is None:
        now = datetime.utcnow()
        start = datetime(now.year, now.month, 1)
    else:
        try:
            start = datetime.strptime(month, "%Y-%m")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="month must use YYYY-MM format") from exc
    end = datetime(start.year + 1, 1, 1) if start.month == 12 else datetime(start.year, start.month + 1, 1)
    return start, end


@router.post("/", response_model=schemas.CompletionMoment)
async def create_completion_moment(
    payload: schemas.CompletionMomentCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lock_progress_owner(db, current_user.id)
    model, _, done_field = CATEGORIES[payload.category]
    item = db.query(model).filter(model.id == payload.item_id, model.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Library item not found")
    if not getattr(item, done_field):
        raise HTTPException(status_code=409, detail="Mark this item finished before reflecting on it")

    moment = db.query(models.CompletionMoment).filter(
        models.CompletionMoment.user_id == current_user.id,
        models.CompletionMoment.category == payload.category,
        models.CompletionMoment.item_id == payload.item_id,
    ).first()
    if not moment:
        moment = models.CompletionMoment(
            user_id=current_user.id,
            category=payload.category,
            item_id=payload.item_id,
            title=item.title,
            rating=item.rating,
        )
        db.add(moment)
        record_completion_activity(db, current_user.id, payload.category, item)
        db.flush()
    result = {**_serialize(moment), "has_review": bool((item.review or "").strip())}
    db.commit()
    return result


# Public review URLs use the singular API categories.
REVIEW_CATEGORY = {"movies": "movie", "tv-shows": "tv_show", "anime": "anime", "video-games": "video_game",
                   "music": "music", "books": "book"}


@router.post("/{moment_id}/review", response_model=dict)
async def save_completion_review(
    moment_id: PositiveDatabaseId,
    payload: schemas.CompletionReview,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save a review written right after finishing. Never replaces an existing review."""
    lock_progress_owner(db, current_user.id)
    moment = db.query(models.CompletionMoment).filter(
        models.CompletionMoment.id == moment_id,
        models.CompletionMoment.user_id == current_user.id,
    ).first()
    if not moment:
        raise HTTPException(status_code=404, detail="Completion moment not found")
    model, _, _ = CATEGORIES[moment.category]
    item = db.query(model).filter(model.id == moment.item_id, model.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Library item not found")
    if (item.review or "").strip():
        raise HTTPException(status_code=409, detail="This title already has a review. Edit it from your library.")
    item.review = payload.review
    item.review_public = payload.public
    item_id = item.id
    category = moment.category
    quality = evaluate_public_review(payload.review, PUBLIC_REVIEW_MIN_CHARS, PUBLIC_REVIEW_DETAIL_MIN_CHARS)
    standalone = payload.public and quality.search_ready
    result = {
        "public": payload.public,
        "word_count": quality.word_count,
        "listed": payload.public and quality.community_ready,
        "standalone": standalone,
        "substantial": quality.word_count >= AD_MIN_REVIEW_WORDS,
        "review_url": f"/reviews/{item_id}?category={REVIEW_CATEGORY[category]}" if standalone else None,
        # Listed reviews also appear on the title's public page.
        "title_url": (title_pages.path_for_item(title_pages.LIBRARY_TO_KIND[category], item)
                      if payload.public and quality.community_ready and category in title_pages.LIBRARY_TO_KIND else None),
    }
    db.commit()
    return result


@router.patch("/{moment_id}", response_model=schemas.CompletionMoment)
async def update_completion_moment(
    moment_id: PositiveDatabaseId,
    payload: schemas.CompletionMomentUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    moment = db.query(models.CompletionMoment).filter(
        models.CompletionMoment.id == moment_id,
        models.CompletionMoment.user_id == current_user.id,
    ).first()
    if not moment:
        raise HTTPException(status_code=404, detail="Completion moment not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(moment, field, value)
    db.commit()
    db.refresh(moment)
    return _serialize(moment)


@router.get("/replay/", response_model=dict)
async def get_monthly_replay(
    month: str | None = Query(None, description="Calendar month in YYYY-MM format"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start, end = _parse_month(month)
    moments: List[models.CompletionMoment] = db.query(models.CompletionMoment).filter(
        models.CompletionMoment.user_id == current_user.id,
        models.CompletionMoment.completed_at >= start,
        models.CompletionMoment.completed_at < end,
    ).order_by(
        models.CompletionMoment.favorite.desc(),
        models.CompletionMoment.rating.desc().nullslast(),
        models.CompletionMoment.completed_at.desc(),
    ).all()

    category_counts = []
    for key, (_, label, _) in CATEGORIES.items():
        count = sum(moment.category == key for moment in moments)
        if count:
            category_counts.append({"category": key, "label": label, "count": count})

    return {
        "month": start.strftime("%Y-%m"),
        "month_label": start.strftime("%B %Y"),
        "completed_count": len(moments),
        "reflection_count": sum(bool((moment.takeaway or "").strip()) for moment in moments),
        "favorite_count": sum(moment.favorite for moment in moments),
        "category_counts": category_counts,
        "highlights": [_serialize(moment) for moment in moments[:3]],
    }
