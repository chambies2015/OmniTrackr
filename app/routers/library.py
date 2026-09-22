"""Bounded, private library browsing and cross-media search."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import String, case, cast, func, or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..dependencies import get_current_user, get_db

router = APIRouter(prefix="/library", tags=["library"])
# category: model, response schema, label, completion field, category-search fields
CATEGORIES = {
    "movies": (models.Movie, schemas.Movie, "Movie", "watched", ("title", "director")),
    "tv-shows": (models.TVShow, schemas.TVShow, "TV show", "watched", ("title",)),
    "anime": (models.Anime, schemas.Anime, "Anime", "watched", ("title",)),
    "video-games": (models.VideoGame, schemas.VideoGame, "Game", "played", ("title", "genres")),
    "music": (models.Music, schemas.Music, "Album", "listened", ("title", "artist", "genre")),
    "books": (models.Book, schemas.Book, "Book", "read", ("title", "author", "genre")),
}


@router.get("/search")
def search_library(
    response: Response,
    q: str = Query(..., min_length=1, max_length=200),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "private, no-store"
    needle = q.strip().lower()
    if not needle:
        return []
    matches = []
    for category, (model, _, label, done, _) in CATEGORIES.items():
        fields = [getattr(model, name) for name in (
            "title", "director", "author", "artist", "genre", "genres", "year", "review"
        ) if hasattr(model, name)]
        title = func.lower(model.title)
        rank = case((title == needle, 0), (title.startswith(needle, autoescape=True), 1),
                    (title.contains(needle, autoescape=True), 2), else_=3)
        rows = db.query(model.id, model.title, getattr(model, done), rank.label("rank")).filter(
            model.user_id == current_user.id,
            or_(*(func.lower(cast(field, String)).contains(needle, autoescape=True) for field in fields)),
        ).order_by(rank, title, model.id).limit(8).all()
        for item_id, item_title, completed, score in rows:
            statuses = {"watched": ("Not watched", "Watched"), "played": ("Not played", "Played"),
                        "listened": ("Not listened", "Listened"), "read": ("Not read", "Read")}
            status = "In progress" if category in {"tv-shows", "anime"} and not completed else statuses[done][bool(completed)]
            matches.append({"id": item_id, "tab": category, "label": label, "title": item_title,
                            "status": status, "score": score})
    matches.sort(key=lambda item: (item["score"], item["title"].lower(), item["tab"], item["id"]))
    return [{key: value for key, value in item.items() if key != "score"} for item in matches[:8]]


@router.get("/page/{category}")
def library_page(
    category: str, response: Response,
    search: str = Query("", max_length=500), sort_by: str = Query("", max_length=30),
    order: str = Query("", max_length=10), offset: int = Query(0, ge=0, le=2147483647),
    limit: int = Query(50, ge=1, le=100), focus_id: int | None = Query(None, ge=1),
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "private, no-store"
    if category not in CATEGORIES:
        raise HTTPException(status_code=404, detail="Unknown media category")
    model, schema, _, _, fields = CATEGORIES[category]
    query = db.query(model).filter(model.user_id == current_user.id)
    if search:
        query = query.filter(or_(*(getattr(model, field).ilike(f"%{search}%") for field in fields)))
    total = query.count()
    # A direct item navigation can surface an exact ID even among duplicate titles.
    if focus_id is not None:
        query = query.order_by(case((model.id == focus_id, 0), else_=1))
    sort_field = "release_date" if category == "video-games" and sort_by == "year" else sort_by
    if sort_field in {"rating", "year", "release_date"} and hasattr(model, sort_field):
        column = getattr(model, sort_field)
        query = query.order_by(column.desc() if order.lower() == "desc" else column.asc())
    # Stable tie breaking prevents missing/duplicated rows on adjacent pages.
    query = query.order_by(model.id)
    offset = min(offset, ((total - 1) // limit) * limit) if total else 0
    items = query.offset(offset).limit(limit).all()
    return {"items": [schema.model_validate(item).model_dump() for item in items],
            "total": total, "offset": offset, "limit": limit}


@router.get("/item/{category}/{item_id}")
def library_item(
    category: str, item_id: int, response: Response,
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Resolve an exact owned item without requiring complete catalog metadata."""
    response.headers["Cache-Control"] = "private, no-store"
    if category not in CATEGORIES:
        raise HTTPException(400, "Unknown media category", headers={"Cache-Control": "private, no-store"})
    model = CATEGORIES[category][0]
    item = db.query(model.id, model.title).filter(model.id == item_id, model.user_id == current_user.id).first()
    if item is None:
        raise HTTPException(404, "Library item not found", headers={"Cache-Control": "private, no-store"})
    return {"id": item.id, "title": item.title}
