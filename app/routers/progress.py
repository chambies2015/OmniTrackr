"""Private, authenticated stopping points for serialized media and books."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..dependencies import get_current_user, get_db
from ..progress import (
    PositiveItemId, ProgressCategory, ProgressClear, ProgressWrite,
    clear_progress, get_progress, save_progress,
)

router = APIRouter(prefix="/progress", tags=["progress"])


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
