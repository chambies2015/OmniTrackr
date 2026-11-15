"""Read several of a member's columns in one query.

The signed-in member is loaded with only the columns sign-in needs
(crud.get_user_by_id_auth). Reading the nine "<library>_visible" or
"<library>_private" flags afterwards then cost one query per flag. Callers that
need a group of them ask for it here first, which is one query in all.
"""
from __future__ import annotations

from sqlalchemy import inspect

from . import models

LIBRARY_KEYS = ("movies", "tv_shows", "anime", "video_games", "music", "books", "manga", "podcasts", "audiobooks")
VISIBLE = tuple(f"{key}_visible" for key in LIBRARY_KEYS)
PRIVATE = tuple(f"{key}_private" for key in LIBRARY_KEYS)


def ensure_loaded(user, names) -> None:
    """Load whichever of `names` the user row hasn't loaded yet, together. Never changes a loaded value."""
    if not isinstance(user, models.User):
        return
    state = inspect(user)
    if state.session is None or not state.persistent:
        return
    missing = [name for name in names if name in state.unloaded]
    if missing:
        state.session.refresh(user, attribute_names=missing)
