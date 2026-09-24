"""Private cross-media activity journal and weekly recap endpoints."""
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple, Type

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..dependencies import get_current_user, get_db

router = APIRouter(prefix="/activity", tags=["activity"])

CategoryDetails = Tuple[Type, str]
CATEGORIES: Dict[str, CategoryDetails] = {
    "movies": (models.Movie, "Movie"),
    "tv-shows": (models.TVShow, "TV show"),
    "anime": (models.Anime, "Anime"),
    "video-games": (models.VideoGame, "Game"),
    "music": (models.Music, "Album"),
    "books": (models.Book, "Book"),
}
ACTION_LABELS = {
    "started": "Started",
    "progressed": "Made progress",
    "completed": "Finished",
    "revisited": "Revisited",
    "noted": "Added a note",
}


def _naive_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.utcnow()
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    if value > datetime.utcnow() + timedelta(minutes=5):
        raise HTTPException(status_code=422, detail="Activity time cannot be in the future")
    return value


def _media_item(db: Session, user_id: int, category: str, item_id: int):
    model, _ = CATEGORIES[category]
    return db.query(model).filter(model.id == item_id, model.user_id == user_id).first()


def _serialize(entry: models.ActivityEntry) -> dict:
    return {
        "id": entry.id,
        "category": entry.category,
        "category_label": CATEGORIES[entry.category][1],
        "item_id": entry.item_id,
        "title": entry.title,
        "action": entry.action,
        "action_label": ACTION_LABELS[entry.action],
        "note": entry.note,
        "rating": entry.rating,
        "source": entry.source,
        "occurred_at": entry.occurred_at,
    }


def record_completion_activity(db: Session, user_id: int, category: str, item) -> models.ActivityEntry:
    """Stage the first automatic completion entry in the caller's transaction."""
    entry = models.ActivityEntry(
        user_id=user_id,
        category=category,
        item_id=item.id,
        title=item.title,
        action="completed",
        rating=item.rating,
        source="automatic",
    )
    db.add(entry)
    return entry


@router.get("/", response_model=list[schemas.ActivityEntry])
async def list_activity(
    category: str | None = Query(None),
    action: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(models.ActivityEntry).filter(models.ActivityEntry.user_id == current_user.id)
    if category:
        if category not in CATEGORIES:
            raise HTTPException(status_code=422, detail="Unsupported activity category")
        query = query.filter(models.ActivityEntry.category == category)
    if action:
        if action not in ACTION_LABELS:
            raise HTTPException(status_code=422, detail="Unsupported activity action")
        query = query.filter(models.ActivityEntry.action == action)
    entries = query.order_by(
        models.ActivityEntry.occurred_at.desc(), models.ActivityEntry.id.desc()
    ).offset(offset).limit(limit).all()
    return [_serialize(entry) for entry in entries]


@router.post("/", response_model=schemas.ActivityEntry, status_code=status.HTTP_201_CREATED)
async def create_activity(
    payload: schemas.ActivityEntryCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _media_item(db, current_user.id, payload.category, payload.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Library item not found")
    entry = models.ActivityEntry(
        user_id=current_user.id,
        category=payload.category,
        item_id=item.id,
        title=item.title,
        action=payload.action,
        note=payload.note,
        rating=item.rating,
        source="manual",
        occurred_at=_naive_utc(payload.occurred_at),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _serialize(entry)


@router.patch("/{entry_id}", response_model=schemas.ActivityEntry)
async def update_activity(
    entry_id: int,
    payload: schemas.ActivityEntryUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = db.query(models.ActivityEntry).filter(
        models.ActivityEntry.id == entry_id,
        models.ActivityEntry.user_id == current_user.id,
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    updates = payload.model_dump(exclude_unset=True)
    if "occurred_at" in updates:
        updates["occurred_at"] = _naive_utc(updates["occurred_at"])
    for field, value in updates.items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return _serialize(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_activity(
    entry_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = db.query(models.ActivityEntry).filter(
        models.ActivityEntry.id == entry_id,
        models.ActivityEntry.user_id == current_user.id,
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    db.delete(entry)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/weekly/", response_model=dict)
async def weekly_recap(
    offset: int = Query(0, ge=0, le=52),
    tz_offset_minutes: int = Query(0, ge=-840, le=840),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    local_now = datetime.utcnow() - timedelta(minutes=tz_offset_minutes)
    local_monday = datetime(local_now.year, local_now.month, local_now.day) - timedelta(days=local_now.weekday())
    local_start = local_monday - timedelta(weeks=offset)
    local_end = local_start + timedelta(days=7)
    start = local_start + timedelta(minutes=tz_offset_minutes)
    end = local_end + timedelta(minutes=tz_offset_minutes)
    entries = db.query(models.ActivityEntry).filter(
        models.ActivityEntry.user_id == current_user.id,
        models.ActivityEntry.occurred_at >= start,
        models.ActivityEntry.occurred_at < end,
    ).order_by(models.ActivityEntry.occurred_at.desc(), models.ActivityEntry.id.desc()).all()

    category_counts = [
        {"category": key, "label": label, "count": sum(entry.category == key for entry in entries)}
        for key, (_, label) in CATEGORIES.items()
        if any(entry.category == key for entry in entries)
    ]
    action_counts = [
        {"action": key, "label": label, "count": sum(entry.action == key for entry in entries)}
        for key, label in ACTION_LABELS.items()
        if any(entry.action == key for entry in entries)
    ]
    return {
        "week_start": local_start.date().isoformat(),
        "week_end": (local_end - timedelta(days=1)).date().isoformat(),
        "period_label": f"{local_start.strftime('%b %d')} – {(local_end - timedelta(days=1)).strftime('%b %d, %Y')}",
        "entry_count": len(entries),
        "completed_count": sum(entry.action == "completed" for entry in entries),
        "reflection_count": sum(bool((entry.note or "").strip()) for entry in entries),
        "category_counts": category_counts,
        "action_counts": action_counts,
        "highlights": [_serialize(entry) for entry in entries[:5]],
        "offset": offset,
    }


def import_activity_entries(
    db: Session, user_id: int, entries: list[schemas.ActivityEntryImport]
) -> tuple[int, int]:
    """Import optional journal snapshots after media import, skipping exact duplicates."""
    created = skipped = 0
    for incoming in entries:
        model, _ = CATEGORIES[incoming.category]
        item = None
        if incoming.item_id:
            item = db.query(model).filter(model.id == incoming.item_id, model.user_id == user_id).first()
        if item is None:
            item = db.query(model).filter(
                model.user_id == user_id,
                func.lower(func.trim(model.title)) == incoming.title.strip().lower(),
            ).order_by(model.id).first()
        occurred_at = _naive_utc(incoming.occurred_at)
        duplicate = db.query(models.ActivityEntry.id).filter(
            models.ActivityEntry.user_id == user_id,
            models.ActivityEntry.category == incoming.category,
            models.ActivityEntry.title == incoming.title,
            models.ActivityEntry.action == incoming.action,
            models.ActivityEntry.occurred_at == occurred_at,
        ).first()
        if duplicate:
            skipped += 1
            continue
        db.add(models.ActivityEntry(
            user_id=user_id,
            category=incoming.category,
            item_id=item.id if item else None,
            title=incoming.title.strip(),
            action=incoming.action,
            note=incoming.note,
            rating=incoming.rating,
            source="import",
            occurred_at=occurred_at,
        ))
        created += 1
    db.commit()
    return created, skipped
