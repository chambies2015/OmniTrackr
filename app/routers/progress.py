"""Private, authenticated stopping points for serialized media and books."""
from typing import Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import episodes, models
from ..dependencies import get_current_user, get_db
from ..progress import (
    EpisodeWrite, PositiveItemId, ProgressCategory, ProgressClear, ProgressWrite,
    _checkpoint_query, _owned_item, clear_progress, get_progress, save_episode, save_progress,
)

router = APIRouter(prefix="/progress", tags=["progress"])
EpisodeCategory = Literal["tv-shows", "anime"]


def _episode_guide(db: Session, user_id: int, category: str, item_id: int, fetched=None) -> dict:
    """The progress envelope plus the season grid and progress numbers."""
    result = get_progress(db, user_id, category, item_id)
    item = _owned_item(db, user_id, category, item_id)
    if fetched is None:
        fetched = episodes.cached_layouts(db, [episodes.layout_key(category, item.title or "", item.year)])
        fetched = next(iter(fetched.values()), [])
    layout = episodes.layout_for(item, category, fetched)
    entry = _checkpoint_query(db, user_id, category, item_id).first()
    result["layout"] = layout
    result["episodes"] = episodes.summarize(layout, entry)
    return result


@router.get("/{category}/{item_id}/episodes")
async def read_episode_guide(
    request: Request,
    category: EpisodeCategory,
    item_id: PositiveItemId,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Season-by-season episode grid for a show in the member's own library."""
    item = await run_in_threadpool(_owned_item, db, current_user.id, category, item_id)
    title, year = item.title or "", item.year
    client = getattr(request.app.state, "external_api_client", None)
    fetched = await episodes.get_or_fetch_layout(db, client, category, title, year)
    return await run_in_threadpool(_episode_guide, db, current_user.id, category, item_id, fetched)


@router.put("/{category}/{item_id}/episode")
def write_episode(
    category: EpisodeCategory,
    item_id: PositiveItemId,
    payload: EpisodeWrite,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set the last watched episode, keeping the member's private reminder."""
    save_episode(db, current_user.id, category, item_id, payload)
    return _episode_guide(db, current_user.id, category, item_id)


@router.get("/{category}/{item_id}")
def read_checkpoint(
    category: ProgressCategory,
    item_id: PositiveItemId,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_progress(db, current_user.id, category, item_id)


@router.put("/{category}/{item_id}")
def write_checkpoint(
    category: ProgressCategory,
    item_id: PositiveItemId,
    payload: ProgressWrite,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return save_progress(db, current_user.id, category, item_id, payload)


@router.delete("/{category}/{item_id}")
def remove_checkpoint(
    category: ProgressCategory,
    item_id: PositiveItemId,
    payload: ProgressClear,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return clear_progress(db, current_user.id, category, item_id, payload)
