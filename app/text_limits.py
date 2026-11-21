"""Length limits for the text members write into their library.

The limits only apply to new text. A title or review saved before they existed
stays exactly as it was: it can still be read, exported and edited, and an edit
may shorten it, but an edit can't make it any longer. Saving a different field of
the same entry never trips the limit. Imports shorten anything new that is too
long instead of turning the row (or the whole file) away; a restore from an
OmniTrackr backup allows RESTORE_FACTOR times the limits first.

Nothing here touches stored rows; there is no migration and no truncation of
existing data.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

from fastapi import HTTPException

TITLE_MAX = 500
CREATOR_MAX = 1000
GENRE_MAX = 500
REVIEW_MAX = 20000
LINK_MAX = 2000

# Library entry fields and their limits. Every field is a member-supplied string.
LIMITS: dict[str, int] = {
    "title": TITLE_MAX,
    "director": CREATOR_MAX,
    "artist": CREATOR_MAX,
    "author": CREATOR_MAX,
    "host": CREATOR_MAX,
    "narrator": CREATOR_MAX,
    "genre": GENRE_MAX,
    "genres": GENRE_MAX,
    "review": REVIEW_MAX,
    "poster_url": LINK_MAX,
    "cover_art_url": LINK_MAX,
    "rawg_link": LINK_MAX,
}

# A link cut short points nowhere, so an import drops a too-long link instead.
LINKS = frozenset({"poster_url", "cover_art_url", "rawg_link"})

# (plural for the rule, singular for "this ... was saved before the limit")
_NOUNS: dict[str, tuple[str, str]] = {
    "title": ("Titles", "title"),
    "director": ("Director names", "director name"),
    "artist": ("Artist names", "artist name"),
    "author": ("Author names", "author name"),
    "host": ("Host names", "host name"),
    "narrator": ("Narrator names", "narrator name"),
    "genre": ("Genres", "genre list"),
    "genres": ("Genres", "genre list"),
    "review": ("Reviews", "review"),
    "poster_url": ("Poster links", "poster link"),
    "cover_art_url": ("Cover art links", "cover art link"),
    "rawg_link": ("RAWG links", "RAWG link"),
}

ELLIPSIS = "\u2026"

# A restore from an OmniTrackr backup is the member's own library coming back, so it
# keeps text up to this many times the limits: a title saved before them still comes
# back whole and still matches its progress, tags and notes in the same file.
# Imports from other services (Import Studio) use the limits themselves.
RESTORE_FACTOR = 10


def problem(field: str, value: Any, current: Any = None) -> Optional[str]:
    """Why ``value`` can't be saved in ``field``, or None when it can.

    ``current`` is what the entry holds now (None for a new entry). Text that is
    no longer than what is already saved is always fine, so an entry saved before
    the limits can be edited and shortened but not made longer.
    """
    limit = LIMITS.get(field)
    if limit is None or not isinstance(value, str) or len(value) <= limit:
        return None
    if isinstance(current, str) and len(value) <= len(current):
        return None
    plural, single = _NOUNS[field]
    if isinstance(current, str) and len(current) > limit:
        return (f"This {single} was saved before the {limit:,}-character limit, so it can be edited "
                f"and shortened but not made longer. It has {len(current):,} characters now.")
    return f"{plural} can be up to {limit:,} characters. This one has {len(value):,}."


def first_problem(values: Mapping[str, Any], current: Any = None) -> Optional[str]:
    """The first limit ``values`` breaks; ``current`` is the stored entry, if any."""
    for field, value in values.items():
        message = problem(field, value, getattr(current, field, None) if current is not None else None)
        if message:
            return message
    return None


def check_update(current: Any, values: Mapping[str, Any]) -> None:
    """Refuse an edit that makes a library field too long (422, a sentence for the notice)."""
    message = first_problem(values, current)
    if message:
        raise HTTPException(status_code=422, detail=message)


def check_value(field: str, value: Any, current: Any = None) -> None:
    """Refuse one field's new text when it is too long (422, a sentence for the notice)."""
    message = problem(field, value, current)
    if message:
        raise HTTPException(status_code=422, detail=message)


def shorten(value: Any, limit: int) -> Any:
    """Text cut to at most ``limit`` characters, ending in an ellipsis when it was cut."""
    if not isinstance(value, str) or len(value) <= limit:
        return value
    return value[:limit - 1].rstrip() + ELLIPSIS


def ceiling(field: str, restore: bool = False) -> Optional[int]:
    """The most characters ``field`` keeps: its limit, or RESTORE_FACTOR times it for a restore."""
    limit = LIMITS.get(field)
    return None if limit is None else limit * (RESTORE_FACTOR if restore else 1)


def _too_long(field: str, value: Any, restore: bool) -> bool:
    limit = ceiling(field, restore)
    return limit is not None and isinstance(value, str) and len(value) > limit


def clip(field: str, value: Any, restore: bool = False) -> Any:
    """``value`` cut to fit ``field``: text ends in an ellipsis, a link is dropped."""
    if not _too_long(field, value, restore):
        return value
    if field in LINKS:
        return None
    return shorten(value, ceiling(field, restore))


def clip_fields(values: dict, restore: bool = False) -> list[str]:
    """Shorten too-long text in a new entry's ``values`` in place; returns the fields it changed."""
    changed = []
    for field in list(values):
        if _too_long(field, values[field], restore):
            values[field] = clip(field, values[field], restore)
            changed.append(field)
    return changed


def clip_for_existing(values: dict, current: Any, restore: bool = False) -> list[str]:
    """Shorten an import's values for an entry that already exists, in place.

    Text no longer than what the entry holds is kept as it is. Text that would make
    a field longer than the limit is shortened; when the entry already holds more
    than the limit, its own text is kept instead of being cut.
    """
    changed = []
    for field in list(values):
        value = values[field]
        if not _too_long(field, value, restore):
            continue
        stored = getattr(current, field, None)
        if isinstance(stored, str) and len(value) <= len(stored):
            continue
        if isinstance(stored, str) and len(stored) > ceiling(field, restore):
            values.pop(field)
        else:
            values[field] = clip(field, value, restore)
        changed.append(field)
    return changed


def describe(changed: Iterable[str]) -> Optional[str]:
    """A short note for an import row whose fields were shortened, or None."""
    fields = list(dict.fromkeys(changed))
    if not fields:
        return None
    links = [field for field in fields if field in LINKS]
    text = [field for field in fields if field not in LINKS]
    parts = []
    if text:
        names = [_NOUNS[field][1] for field in text]
        joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        parts.append(f"The {joined} {'was' if len(names) == 1 else 'were'} shortened to fit the length limit.")
    if links:
        parts.append("A link too long to use was left out.")
    return " ".join(parts)
