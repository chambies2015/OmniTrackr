"""Private, ordered Next Up queue endpoints."""
from datetime import datetime
from typing import Dict, List, Tuple, Type

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..integer_bounds import PositiveDatabaseId
from .. import episodes, models, schemas, title_pages
from ..progress import lock_progress_owner
from ..dependencies import get_current_user, get_db
from ..progress import get_checkpoint_map, serialize_checkpoint

router = APIRouter(prefix="/next-up", tags=["next-up"])

CategoryDetails = Tuple[Type[models.Movie], str]
CATEGORIES: Dict[str, CategoryDetails] = {
    "movies": (models.Movie, "Movie"),
    "tv-shows": (models.TVShow, "TV show"),
    "anime": (models.Anime, "Anime"),
    "video-games": (models.VideoGame, "Game"),
    "music": (models.Music, "Album"),
    "books": (models.Book, "Book"),
    "manga": (models.Manga, "Manga"),
    "podcasts": (models.Podcast, "Podcast"),
    "audiobooks": (models.Audiobook, "Audiobook"),
}


# The verb a queued title gets once it's started, for the queue row and the Continue card.
NOW_LABELS = {
    "movies": "Watching", "tv-shows": "Watching", "anime": "Watching",
    "video-games": "Playing", "books": "Reading", "manga": "Reading",
    "music": "Listening", "podcasts": "Listening", "audiobooks": "Listening",
}
SUGGESTION_LIMIT = 6


def _referenced_item(db: Session, user_id: int, category: str, item_id: int):
    model, _ = CATEGORIES[category]
    return db.query(model).filter(model.id == item_id, model.user_id == user_id).first()


def _referenced_items(db: Session, user_id: int, entries) -> dict:
    """Load every queued library item with one query per category in the queue."""
    ids: Dict[str, List[int]] = {}
    for entry in entries:
        if entry.category in CATEGORIES:
            ids.setdefault(entry.category, []).append(entry.item_id)
    found = {}
    for category, item_ids in ids.items():
        model, _ = CATEGORIES[category]
        for item in db.query(model).filter(model.user_id == user_id, model.id.in_(item_ids)).all():
            found[(category, item.id)] = item
    return found


def _finished(item, category: str) -> bool:
    return bool(getattr(item, title_pages.COMPLETE_FIELD[title_pages.LIBRARY_TO_KIND[category]], False))


_MISSING = object()


def _serialize(entry: models.NextUpItem, db: Session, user_id: int, checkpoints=None, item=_MISSING) -> dict:
    if item is _MISSING:
        item = _referenced_item(db, user_id, entry.category, entry.item_id)
    _, category_label = CATEGORIES[entry.category]
    checkpoints = get_checkpoint_map(db, user_id) if checkpoints is None else checkpoints
    kind = title_pages.LIBRARY_TO_KIND[entry.category]
    return {
        "id": entry.id,
        "category": entry.category,
        "item_id": entry.item_id,
        "title": item.title if item else "Deleted library item",
        "category_label": category_label,
        "position": entry.position,
        "available": item is not None,
        "progress": serialize_checkpoint(checkpoints.get((entry.category, entry.item_id))) if item else None,
        "finished": _finished(item, entry.category) if item else False,
        "image": title_pages._safe_image(getattr(item, title_pages.IMAGE_FIELD[kind], None)) if item else None,
        "started_at": entry.started_at.isoformat() if entry.started_at else None,
        "now_label": NOW_LABELS[entry.category],
    }


def _serialize_all(db: Session, user_id: int, entries) -> list[dict]:
    checkpoints = get_checkpoint_map(db, user_id)
    items = _referenced_items(db, user_id, entries)
    return _with_episodes(db, user_id, [
        _serialize(entry, db, user_id, checkpoints, item=items.get((entry.category, entry.item_id)))
        for entry in entries
    ])


def _with_episodes(db: Session, user_id: int, entries: list[dict]) -> list[dict]:
    episodes.attach(db, user_id, entries, id_key="item_id")
    return entries


def _ordered_entries(db: Session, user_id: int) -> List[models.NextUpItem]:
    return db.query(models.NextUpItem).filter(
        models.NextUpItem.user_id == user_id,
    ).order_by(models.NextUpItem.position, models.NextUpItem.id).all()


def enqueue(db: Session, user_id: int, category: str, item_id: int) -> bool:
    """Put an owned library item at the end of the queue. Does not commit.

    Returns False when it is already queued. The caller checks ownership.
    """
    exists = db.query(models.NextUpItem.id).filter(
        models.NextUpItem.user_id == user_id,
        models.NextUpItem.category == category,
        models.NextUpItem.item_id == item_id,
    ).first()
    if exists:
        return False
    highest = db.query(func.max(models.NextUpItem.position)).filter(models.NextUpItem.user_id == user_id).scalar()
    db.add(models.NextUpItem(user_id=user_id, category=category, item_id=item_id,
                             position=(highest if highest is not None else -1) + 1))
    return True


def _get_owned_entry(db: Session, user_id: int, queue_id: int) -> models.NextUpItem:
    entry = db.query(models.NextUpItem).filter(
        models.NextUpItem.id == queue_id,
        models.NextUpItem.user_id == user_id,
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Queue item not found")
    return entry


@router.get("/", response_model=List[schemas.NextUpItem])
def list_next_up(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _serialize_all(db, current_user.id, _ordered_entries(db, current_user.id))


@router.get("/suggestions", response_model=List[schemas.NextUpSuggestion])
def next_up_suggestions(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unfinished library titles that aren't queued yet, so an empty queue has a way in.

    Newest additions first, taking turns between formats so six suggestions
    aren't all books. Tabs the member hid in Settings are left out. Read only.
    """
    queued = {(category, item_id) for category, item_id in db.query(
        models.NextUpItem.category, models.NextUpItem.item_id,
    ).filter(models.NextUpItem.user_id == current_user.id).all()}
    lanes = []
    for category, (model, label) in CATEGORIES.items():
        if getattr(current_user, f"{category.replace('-', '_')}_visible", True) is False:
            continue
        kind = title_pages.LIBRARY_TO_KIND[category]
        done = getattr(model, title_pages.COMPLETE_FIELD[kind])
        query = db.query(model).filter(
            model.user_id == current_user.id,
            or_(done.is_(None), done == False),  # noqa: E712
        )
        queued_ids = [item_id for queued_category, item_id in queued if queued_category == category]
        if queued_ids:
            query = query.filter(model.id.notin_(queued_ids))
        rows = query.order_by(
            case((model.added_at.is_(None), 1), else_=0), model.added_at.desc(), model.id.desc(),
        ).limit(SUGGESTION_LIMIT).all()
        lane = [{
            "category": category,
            "item_id": item.id,
            "title": item.title or "Untitled",
            "category_label": label,
            "image": title_pages._safe_image(getattr(item, title_pages.IMAGE_FIELD[kind], None)),
            "_added": item.added_at or datetime.min,
        } for item in rows]
        if lane:
            lanes.append(lane)
    # Fill round by round: everyone's newest first, then everyone's second newest.
    lanes.sort(key=lambda lane: (lane[0]["_added"], lane[0]["item_id"]), reverse=True)
    picked = []
    while lanes and len(picked) < SUGGESTION_LIMIT:
        for lane in list(lanes):
            picked.append(lane.pop(0))
            if not lane:
                lanes.remove(lane)
            if len(picked) == SUGGESTION_LIMIT:
                break
    for suggestion in picked:
        suggestion.pop("_added")
    return picked


@router.post("/", response_model=schemas.NextUpItem, status_code=status.HTTP_201_CREATED)
def add_next_up(
    payload: schemas.NextUpItemCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lock_progress_owner(db, current_user.id)
    if not _referenced_item(db, current_user.id, payload.category, payload.item_id):
        raise HTTPException(status_code=404, detail="Library item not found")

    duplicate = db.query(models.NextUpItem).filter(
        models.NextUpItem.user_id == current_user.id,
        models.NextUpItem.category == payload.category,
        models.NextUpItem.item_id == payload.item_id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="That item is already in Next Up")

    highest_position = db.query(func.max(models.NextUpItem.position)).filter(
        models.NextUpItem.user_id == current_user.id,
    ).scalar()
    entry = models.NextUpItem(
        user_id=current_user.id,
        category=payload.category,
        item_id=payload.item_id,
        position=(highest_position if highest_position is not None else -1) + 1,
    )
    db.add(entry)
    try:
        db.flush()
        result = _serialize(entry, db, current_user.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That item is already in Next Up")
    return result


@router.put("/{queue_id}/position", response_model=List[schemas.NextUpItem])
def move_next_up(
    queue_id: PositiveDatabaseId,
    payload: schemas.NextUpItemMove,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = _get_owned_entry(db, current_user.id, queue_id)
    entries = _ordered_entries(db, current_user.id)

    entries.remove(target)
    destination = min(payload.position, len(entries))
    entries.insert(destination, target)
    for position, entry in enumerate(entries):
        entry.position = position
    db.commit()
    # The commit expired every row, so serialising them as they are would reload each one
    # with its own query. One fresh read of the queue costs a single query instead.
    return _serialize_all(db, current_user.id, _ordered_entries(db, current_user.id))


@router.post("/{queue_id}/start", response_model=List[schemas.NextUpItem])
def start_next_up(
    queue_id: PositiveDatabaseId,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a queued title as started and move it to the top.

    This only touches the queue entry. The library item, its finished flag and
    any saved progress stay as they are. Starting twice keeps the first date.
    """
    lock_progress_owner(db, current_user.id)
    target = _get_owned_entry(db, current_user.id, queue_id)
    if _referenced_item(db, current_user.id, target.category, target.item_id) is None:
        raise HTTPException(status_code=404, detail="Library item not found")
    if target.started_at is None:
        target.started_at = datetime.utcnow()
    entries = _ordered_entries(db, current_user.id)
    entries.remove(target)
    entries.insert(0, target)
    for position, entry in enumerate(entries):
        entry.position = position
    db.commit()
    # The commit expired every row, so serialising them as they are would reload each one
    # with its own query. One fresh read of the queue costs a single query instead.
    return _serialize_all(db, current_user.id, _ordered_entries(db, current_user.id))


@router.delete("/{queue_id}/start", response_model=List[schemas.NextUpItem])
def unstart_next_up(
    queue_id: PositiveDatabaseId,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Undo Start: the title stays where it is in the queue, just not marked as started."""
    target = _get_owned_entry(db, current_user.id, queue_id)
    target.started_at = None
    db.commit()
    return _serialize_all(db, current_user.id, _ordered_entries(db, current_user.id))


@router.post("/{queue_id}/finish", response_model=schemas.NextUpFinished)
def finish_next_up(
    queue_id: PositiveDatabaseId,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark the queued title finished in the library and take it off the queue.

    Only the completion flag changes on the library item; rating, review and
    everything else stay as they are. The dashboard then opens the usual
    completion reflection, which logs the finish to the journal.
    """
    lock_progress_owner(db, current_user.id)
    entry = _get_owned_entry(db, current_user.id, queue_id)
    item = _referenced_item(db, current_user.id, entry.category, entry.item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Library item not found")
    was_finished = _finished(item, entry.category)
    if not was_finished:
        setattr(item, title_pages.COMPLETE_FIELD[title_pages.LIBRARY_TO_KIND[entry.category]], True)
    result = {"category": entry.category, "item_id": entry.item_id, "title": item.title, "was_finished": was_finished}
    db.delete(entry)
    db.flush()
    for position, remaining in enumerate(_ordered_entries(db, current_user.id)):
        remaining.position = position
    db.commit()
    return result


@router.post("/clear-finished", response_model=List[schemas.NextUpItem])
def clear_finished_next_up(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Drop queue entries whose library item is already finished (or was deleted)."""
    lock_progress_owner(db, current_user.id)
    entries = _ordered_entries(db, current_user.id)
    items = _referenced_items(db, current_user.id, entries)
    kept = []
    for entry in entries:
        item = items.get((entry.category, entry.item_id))
        if item is None or _finished(item, entry.category):
            db.delete(entry)
        else:
            kept.append(entry)
    for position, entry in enumerate(kept):
        entry.position = position
    db.commit()
    return _serialize_all(db, current_user.id, _ordered_entries(db, current_user.id))


@router.delete("/{queue_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_next_up(
    queue_id: PositiveDatabaseId,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = _get_owned_entry(db, current_user.id, queue_id)
    db.delete(entry)
    db.commit()
