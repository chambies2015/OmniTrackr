"""Private completion reflections and monthly replay endpoints."""
from datetime import datetime
from typing import Dict, List, Tuple, Type

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..dependencies import get_current_user, get_db

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
        db.commit()
        db.refresh(moment)
    return _serialize(moment)


@router.patch("/{moment_id}", response_model=schemas.CompletionMoment)
async def update_completion_moment(
    moment_id: int,
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
