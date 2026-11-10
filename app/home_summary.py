"""The welcome strip at the top of the signed-in dashboard.

One read-only summary of the member's own library: how much is in each format,
how much is finished and rated, what they finished this month, and the covers of
their latest additions. Nothing here is shared or stored.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from . import models
from .title_pages import COMPLETE_FIELD, IMAGE_FIELD, LIBRARY_TO_KIND, _safe_image

# library key -> (model, one, many, done verb). Same order as the library tabs.
LIBRARIES = (
    ("movies", models.Movie, "movie", "movies", "watched"),
    ("tv-shows", models.TVShow, "show", "shows", "watched"),
    ("anime", models.Anime, "anime", "anime", "watched"),
    ("video-games", models.VideoGame, "game", "games", "played"),
    ("music", models.Music, "album", "albums", "listened"),
    ("books", models.Book, "book", "books", "read"),
    ("manga", models.Manga, "manga", "manga", "read"),
    ("podcasts", models.Podcast, "podcast", "podcasts", "listened"),
    ("audiobooks", models.Audiobook, "audiobook", "audiobooks", "listened"),
)
RECENT_LIMIT = 8
RECENT_PER_LIBRARY = 4


def _visible(user: models.User, key: str) -> bool:
    return getattr(user, f"{key.replace('-', '_')}_visible", True) is not False


def build(db: Session, user: models.User, *, now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    libraries = []
    recent = []
    for key, model, one, many, verb in LIBRARIES:
        kind = LIBRARY_TO_KIND[key]
        done = getattr(model, COMPLETE_FIELD[kind])
        total, finished, rated, average = db.query(
            func.count(model.id),
            func.coalesce(func.sum(case((done == True, 1), else_=0)), 0),  # noqa: E712
            func.count(model.rating),
            func.avg(model.rating),
        ).filter(model.user_id == user.id).one()
        total = int(total or 0)
        visible = _visible(user, key)
        libraries.append({
            "key": key,
            "one": one,
            "many": many,
            "verb": verb,
            "total": total,
            "finished": int(finished or 0),
            "rated": int(rated or 0),
            "average_rating": round(float(average), 1) if average is not None else None,
            "visible": visible,
        })
        if not total or not visible:
            continue
        image = getattr(model, IMAGE_FIELD[kind])
        rows = db.query(model.id, model.title, image, model.added_at).filter(
            model.user_id == user.id, image.isnot(None), image != "",
        ).order_by(
            case((model.added_at.is_(None), 1), else_=0), model.added_at.desc(), model.id.desc(),
        ).limit(RECENT_PER_LIBRARY).all()
        for item_id, title, url, added_at in rows:
            safe = _safe_image(url)
            if safe:
                recent.append({
                    "id": item_id, "category": key, "title": title or "Untitled",
                    "image": safe, "_added": added_at or datetime.min,
                })

    recent.sort(key=lambda item: item["_added"], reverse=True)
    recent = recent[:RECENT_LIMIT]
    for item in recent:
        item.pop("_added")

    # Every finish writes a "completed" journal entry, whether or not the member reflects on it.
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    shown_keys = [library["key"] for library in libraries if library["visible"]]
    finished_this_month = 0 if not shown_keys else db.query(
        models.ActivityEntry.category, models.ActivityEntry.item_id,
    ).filter(
        models.ActivityEntry.user_id == user.id,
        models.ActivityEntry.action == "completed",
        models.ActivityEntry.occurred_at >= month_start,
        # Hidden tabs stay out of every other number on the strip, so out of this one too.
        models.ActivityEntry.category.in_(shown_keys),
    ).distinct().count()

    shown = [library for library in libraries if library["visible"]]
    total = sum(library["total"] for library in shown)
    finished = sum(library["finished"] for library in shown)
    return {
        "name": user.username,
        "total": total,
        "finished": finished,
        "unfinished": total - finished,
        "rated": sum(library["rated"] for library in shown),
        "finished_this_month": int(finished_this_month),
        "libraries": libraries,
        "recent": recent,
    }
