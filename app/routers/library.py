"""Bounded, private library browsing and cross-media search."""
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import String, case, cast, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..integer_bounds import PositiveDatabaseId
from .. import episodes, models, schemas
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
    "manga": (models.Manga, schemas.Manga, "Manga", "read", ("title", "author", "genre")),
    "podcasts": (models.Podcast, schemas.Podcast, "Podcast", "listened", ("title", "host", "genre")),
}
PROGRESS_CATEGORIES = {"tv-shows", "anime", "books", "manga", "podcasts"}
NO_STORE = {"Cache-Control": "private, no-store"}
TAG_MAX_LENGTH = 32
TAGS_PER_ITEM = 10
VIEWS_PER_SHELF = 12
SORTS = {"", "rating-asc", "rating-desc", "year-asc", "year-desc", "release_date-asc", "release_date-desc"}


def clean_tag(raw: str) -> str:
    """Tidy one typed tag: single spaces, no leading #, no commas or control characters."""
    label = " ".join(str(raw).split()).lstrip("#").strip()
    if "," in label or not label.isprintable():
        raise HTTPException(422, "Tags can't contain commas or hidden characters", headers=NO_STORE)
    if len(label) > TAG_MAX_LENGTH:
        raise HTTPException(422, f"Keep each tag to {TAG_MAX_LENGTH} characters", headers=NO_STORE)
    return label


def tag_key(label: str) -> str:
    return label.casefold()[:TAG_MAX_LENGTH]


def tags_for(db: Session, user_id: int, category: str, item_ids) -> dict[int, list[str]]:
    found: dict[int, list[str]] = {}
    if not item_ids:
        return found
    rows = db.query(models.LibraryTag.item_id, models.LibraryTag.label).filter(
        models.LibraryTag.user_id == user_id, models.LibraryTag.category == category,
        models.LibraryTag.item_id.in_(list(item_ids)),
    ).order_by(models.LibraryTag.label_key).all()
    for item_id, label in rows:
        found.setdefault(item_id, []).append(label)
    return found


def tag_counts(db: Session, user_id: int, category: str | None = None) -> list[dict]:
    tag = models.LibraryTag
    query = db.query(tag.label_key, func.min(tag.label), func.count(tag.id)).filter(tag.user_id == user_id)
    if category:
        query = query.filter(tag.category == category)
    rows = query.group_by(tag.label_key).all()
    rows.sort(key=lambda row: (-row[2], row[0]))
    return [{"label": label, "count": count} for _, label, count in rows]


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
    limit: int = Query(50, ge=1, le=100), focus_id: int | None = Query(None, ge=1, le=2147483647),
    completion: Literal["all", "unfinished", "finished"] = Query("all"),
    unrated: bool = Query(False), has_progress: bool = Query(False),
    tag: str = Query("", max_length=40),
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "private, no-store"
    if category not in CATEGORIES:
        raise HTTPException(status_code=404, detail="Unknown media category")
    if has_progress and category not in {"tv-shows", "anime", "books", "manga", "podcasts"}:
        raise HTTPException(
            status_code=422, detail="Saved progress is available for TV shows, anime, books, manga, and podcasts",
            headers={"Cache-Control": "private, no-store"},
        )
    model, schema, _, completion_field, fields = CATEGORIES[category]
    query = db.query(model).filter(model.user_id == current_user.id)
    if search:
        needle = search.lower()
        query = query.filter(or_(*(
            func.lower(getattr(model, field)).contains(needle, autoescape=True) for field in fields
        )))
    completed = getattr(model, completion_field)
    if completion == "finished":
        query = query.filter(completed.is_(True))
    elif completion == "unfinished":
        query = query.filter(or_(completed.is_(False), completed.is_(None)))
    if unrated:
        query = query.filter(model.rating.is_(None))
    if has_progress:
        # A cleared checkpoint retains its row for revision safety. Only active
        # checkpoints of this category and owner qualify; EXISTS avoids joins
        # changing the result count or pagination.
        checkpoint = models.ProgressCheckpoint
        query = query.filter(db.query(checkpoint.id).filter(
            checkpoint.user_id == current_user.id,
            checkpoint.category == category,
            checkpoint.item_id == model.id,
            checkpoint.unit.is_not(None),
        ).exists())
    wanted_tag = tag_key(" ".join(tag.split()).lstrip("#").strip())
    if wanted_tag:
        labels = models.LibraryTag
        query = query.filter(db.query(labels.id).filter(
            labels.user_id == current_user.id,
            labels.category == category,
            labels.item_id == model.id,
            labels.label_key == wanted_tag,
        ).exists())
    total = query.count()
    # A direct item navigation can surface an exact ID even among duplicate titles.
    if focus_id is not None:
        query = query.order_by(case((model.id == focus_id, 0), else_=1))
    sort_field = "release_date" if category == "video-games" and sort_by == "year" else sort_by
    if sort_field in {"rating", "year", "release_date"} and hasattr(model, sort_field):
        column = getattr(model, sort_field)
        # Unrated or undated titles go last both ways, as on Postgres a plain DESC lists NULLs first.
        query = query.order_by((column.desc() if order.lower() == "desc" else column.asc()).nullslast())
    # Stable tie breaking prevents missing/duplicated rows on adjacent pages.
    query = query.order_by(model.id)
    offset = min(offset, ((total - 1) // limit) * limit) if total else 0
    items = query.offset(offset).limit(limit).all()
    rows = [schema.model_validate(item).model_dump() for item in items]
    if category in episodes.KINDS:
        found = episodes.progress_map(db, current_user.id, category, items)
        for row in rows:
            row["episode_progress"] = found.get(row["id"])
    labels = tags_for(db, current_user.id, category, [row["id"] for row in rows])
    for row in rows:
        row["tags"] = labels.get(row["id"], [])
    return {"items": rows, "total": total, "offset": offset, "limit": limit}


@router.get("/item/{category}/{item_id}")
def library_item(
    category: str, item_id: PositiveDatabaseId, response: Response,
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


class TagUpdate(BaseModel):
    tags: list[str] = Field(default_factory=list, max_length=50)


@router.get("/tags")
def list_tags(
    response: Response, category: str = Query("", max_length=16),
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """The member's tags, most used first: on one shelf, or on every shelf when no category is given."""
    response.headers["Cache-Control"] = "private, no-store"
    if category and category not in CATEGORIES:
        raise HTTPException(404, "Unknown media category", headers=NO_STORE)
    return tag_counts(db, current_user.id, category or None)


@router.put("/tags/{category}/{item_id}")
def set_item_tags(
    category: str, item_id: PositiveDatabaseId, body: TagUpdate, response: Response,
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Replace one title's tags. Sending an empty list removes them all."""
    response.headers["Cache-Control"] = "private, no-store"
    if category not in CATEGORIES:
        raise HTTPException(404, "Unknown media category", headers=NO_STORE)
    model = CATEGORIES[category][0]
    if db.query(model.id).filter(model.id == item_id, model.user_id == current_user.id).first() is None:
        raise HTTPException(404, "Library item not found", headers=NO_STORE)
    wanted: dict[str, str] = {}
    for raw in body.tags:
        label = clean_tag(raw)
        if label and tag_key(label) not in wanted:
            wanted[tag_key(label)] = label
    if len(wanted) > TAGS_PER_ITEM:
        raise HTTPException(422, f"A title can have up to {TAGS_PER_ITEM} tags", headers=NO_STORE)
    # Reuse the spelling already in the library, so "Cozy" typed later stays "cozy".
    if wanted:
        known = db.query(models.LibraryTag.label_key, func.min(models.LibraryTag.label)).filter(
            models.LibraryTag.user_id == current_user.id, models.LibraryTag.label_key.in_(list(wanted)),
        ).group_by(models.LibraryTag.label_key).all()
        wanted.update(dict(known))
    try:
        db.query(models.LibraryTag).filter_by(
            user_id=current_user.id, category=category, item_id=item_id,
        ).delete(synchronize_session=False)
        db.add_all(models.LibraryTag(
            user_id=current_user.id, category=category, item_id=item_id, label=label, label_key=key,
        ) for key, label in wanted.items())
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Those tags changed in another tab. Reload and try again.", headers=NO_STORE)
    return {"tags": sorted(wanted.values(), key=str.casefold)}


class ViewFilters(BaseModel):
    search: str = Field("", max_length=500)
    sort: str = Field("", max_length=30)
    completion: Literal["all", "unfinished", "finished"] = "all"
    unrated: bool = False
    has_progress: bool = False
    tag: str = Field("", max_length=40)


class ViewCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    filters: ViewFilters


def view_out(view: models.SavedLibraryView) -> dict:
    try:
        filters = ViewFilters.model_validate(json.loads(view.filters)).model_dump()
    except ValueError:
        filters = ViewFilters().model_dump()
    return {"id": view.id, "name": view.name, "filters": filters}


@router.get("/views/{category}")
def list_views(
    category: str, response: Response,
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "private, no-store"
    if category not in CATEGORIES:
        raise HTTPException(404, "Unknown media category", headers=NO_STORE)
    views = db.query(models.SavedLibraryView).filter_by(user_id=current_user.id, category=category).order_by(
        models.SavedLibraryView.name_key, models.SavedLibraryView.id).all()
    return [view_out(view) for view in views]


@router.post("/views/{category}")
def save_view(
    category: str, body: ViewCreate, response: Response,
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Save the current shelf view. Saving under an existing name updates that view."""
    response.headers["Cache-Control"] = "private, no-store"
    if category not in CATEGORIES:
        raise HTTPException(404, "Unknown media category", headers=NO_STORE)
    name = " ".join(body.name.split())
    if not name or len(name) > 40 or not name.isprintable():
        raise HTTPException(422, "Give the view a name of up to 40 characters", headers=NO_STORE)
    filters = body.filters.model_copy()
    if filters.sort not in SORTS:
        raise HTTPException(422, "Unknown sort order", headers=NO_STORE)
    if filters.has_progress and category not in PROGRESS_CATEGORIES:
        filters.has_progress = False
    filters.search = filters.search.strip()
    filters.tag = clean_tag(filters.tag) if filters.tag else ""
    stored = json.dumps(filters.model_dump(), separators=(",", ":"))
    key = name.casefold()
    views = models.SavedLibraryView
    view = db.query(views).filter_by(user_id=current_user.id, category=category, name_key=key).first()
    if view is None:
        if db.query(views.id).filter_by(user_id=current_user.id, category=category).count() >= VIEWS_PER_SHELF:
            raise HTTPException(
                422, f"Each shelf keeps up to {VIEWS_PER_SHELF} saved views. Delete one to save another.",
                headers=NO_STORE,
            )
        view = views(user_id=current_user.id, category=category, name=name, name_key=key, filters=stored)
        db.add(view)
    else:
        view.name, view.filters = name, stored
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A view with that name was just saved in another tab", headers=NO_STORE)
    db.refresh(view)
    return view_out(view)


@router.delete("/views/{category}/{view_id}", status_code=204)
def delete_view(
    category: str, view_id: PositiveDatabaseId,
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db),
):
    if category not in CATEGORIES:
        raise HTTPException(404, "Unknown media category", headers=NO_STORE)
    deleted = db.query(models.SavedLibraryView).filter_by(
        id=view_id, user_id=current_user.id, category=category,
    ).delete(synchronize_session=False)
    db.commit()
    if not deleted:
        raise HTTPException(404, "Saved view not found", headers=NO_STORE)
    return Response(status_code=204, headers=NO_STORE)
