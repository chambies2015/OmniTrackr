"""Private, authenticated stopping points for serialized media and books."""
from typing import Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import episode_notes, episodes, models
from ..dependencies import get_current_user, get_db
from ..progress import (
    EpisodeWrite, PositiveItemId, ProgressCategory, ProgressClear, ProgressWrite,
    _checkpoint_query, _envelope, _owned_item, clear_progress, get_progress, save_episode, save_progress,
)

router = APIRouter(prefix="/progress", tags=["progress"])
EpisodeCategory = Literal["tv-shows", "anime"]


def _episode_guide(db: Session, user_id: int, category: str, item_id: int, fetched=None, item=None) -> dict:
    """The progress envelope plus the season grid and progress numbers.

    Reads the show and its checkpoint once each. ``item`` may be the show the
    caller just loaded, when nothing has been committed since.
    """
    if item is None or inspect(item).expired:
        item = _owned_item(db, user_id, category, item_id)
    entry = _checkpoint_query(db, user_id, category, item_id).first()
    result = _envelope(item, category, entry)
    if fetched is None:
        fetched = episodes.cached_layouts(db, [episodes.layout_key(category, item.title or "", item.year)])
        fetched = next(iter(fetched.values()), [])
    layout = episodes.layout_for(item, category, fetched)
    result["layout"] = layout
    result["episodes"] = episodes.summarize(layout, entry)
    notes = episode_notes.for_item(db, user_id, category, item_id)
    result["episode_notes"] = notes
    result["episode_note_summary"] = episode_notes.summary(notes)
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
    return await run_in_threadpool(_episode_guide, db, current_user.id, category, item_id, fetched, item)


@router.put("/{category}/{item_id}/episode")
def write_episode(
    category: EpisodeCategory,
    item_id: PositiveItemId,
    payload: EpisodeWrite,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set the last watched episode, keeping the member's private reminder."""
    user_id = current_user.id  # read before the commit expires the member row
    save_episode(db, user_id, category, item_id, payload)
    return _episode_guide(db, user_id, category, item_id)


@router.put("/{category}/{item_id}/episode-notes")
def write_episode_note(
    request: Request,
    category: EpisodeCategory,
    item_id: PositiveItemId,
    payload: episode_notes.EpisodeNoteWrite,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rate an episode or keep a private note on it. Empty rating and note removes the entry."""
    user_id = current_user.id  # read before the commit expires the member row
    episode_notes.save(db, user_id, category, item_id, payload)
    return _episode_guide(db, user_id, category, item_id)


@router.delete("/{category}/{item_id}/episode-notes")
def remove_episode_note(
    request: Request,
    category: EpisodeCategory,
    item_id: PositiveItemId,
    payload: episode_notes.EpisodeRef,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id  # read before the commit expires the member row
    episode_notes.remove(db, user_id, category, item_id, payload)
    return _episode_guide(db, user_id, category, item_id)


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
