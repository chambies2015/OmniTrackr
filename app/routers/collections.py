"""Private-by-default cross-media collections and moderated public discovery."""
from datetime import datetime, timedelta
import hashlib
import hmac
from html import escape
import json
import os
from pathlib import Path
import secrets
from typing import Dict, List, Tuple, Type

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .. import auth, models, schemas
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db

router = APIRouter(prefix="/collections", tags=["collections"])

CategoryDetails = Tuple[Type[models.Movie], str]
CATEGORIES: Dict[str, CategoryDetails] = {
    "movies": (models.Movie, "Movie"),
    "tv-shows": (models.TVShow, "TV show"),
    "anime": (models.Anime, "Anime"),
    "video-games": (models.VideoGame, "Game"),
    "music": (models.Music, "Album"),
    "books": (models.Book, "Book"),
}
PUBLIC_COLLECTION_MIN_DESCRIPTION_CHARS = 300
PUBLIC_COLLECTION_MIN_ITEMS = 3
PUBLIC_COLLECTION_MAX_ITEMS = 50
PUBLIC_COLLECTION_GALLERY_MIN = 3
VISITOR_COOKIE = "omnitrackr_collection_visitor"
ARTWORK_FIELDS = {
    "movies": "poster_url",
    "tv-shows": "poster_url",
    "anime": "poster_url",
    "video-games": "cover_art_url",
    "music": "cover_art_url",
    "books": "cover_art_url",
}

COPY_FIELDS = {
    "movies": ("title", "director", "year", "poster_url"),
    "tv-shows": ("title", "year", "seasons", "episodes", "poster_url"),
    "anime": ("title", "year", "seasons", "episodes", "poster_url"),
    "video-games": ("title", "release_date", "genres", "cover_art_url", "rawg_link"),
    "music": ("title", "artist", "year", "genre", "cover_art_url"),
    "books": ("title", "author", "year", "genre", "cover_art_url"),
}


def _sign_visitor_token(payload: str) -> str:
    signature = hmac.new(auth.SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def _visitor_identity(request: Request) -> tuple[str, str | None, bool]:
    """Return a signed pseudonymous identity and whether the browser retained it."""
    supplied_token = request.cookies.get(VISITOR_COOKIE, "")
    if 80 <= len(supplied_token) <= 160 and "." in supplied_token:
        payload, supplied_signature = supplied_token.rsplit(".", 1)
        expected = hmac.new(
            auth.SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        signature_is_hex = (
            len(supplied_signature) == 64
            and supplied_signature.isascii()
            and all(character in "0123456789abcdef" for character in supplied_signature)
        )
        if payload and signature_is_hex and hmac.compare_digest(supplied_signature, expected):
            digest = hashlib.sha256(
                f"{auth.SECRET_KEY}:{supplied_token}".encode("utf-8")
            ).hexdigest()
            return digest, None, True

    # Keep request-controlled bytes out of the response-cookie dataflow. Only a
    # freshly generated, server-signed value can be returned for Set-Cookie.
    new_token = _sign_visitor_token(secrets.token_urlsafe(32))
    digest = hashlib.sha256(f"{auth.SECRET_KEY}:{new_token}".encode("utf-8")).hexdigest()
    return digest, new_token, False


def _set_visitor_cookie(response, token: str | None) -> None:
    if token:
        response.set_cookie(
            VISITOR_COOKIE,
            token,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            secure=os.getenv("ENVIRONMENT", "development").lower() == "production",
            samesite="lax",
        )


def _moderator_usernames() -> set[str]:
    return {
        username.strip().lower()
        for username in os.getenv("COLLECTION_MODERATOR_USERNAMES", "").split(",")
        if username.strip()
    }


def _require_moderator(current_user: models.User) -> None:
    if current_user.username.lower() not in _moderator_usernames():
        raise HTTPException(status_code=403, detail="Collection moderator access required")


def _count(db: Session, model, *filters) -> int:
    query = db.query(func.count(model.id))
    if filters:
        query = query.filter(*filters)
    return int(query.scalar() or 0)


def _moderator_site_insights(db: Session) -> dict:
    """Return privacy-conscious operational metrics for trusted moderators."""
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    total_users = _count(db, models.User)
    users = {
        "total": total_users,
        "active": _count(db, models.User, models.User.is_active == True),
        "verified": _count(db, models.User, models.User.is_verified == True),
        "new_7_days": _count(db, models.User, models.User.created_at >= seven_days_ago),
        "new_30_days": _count(db, models.User, models.User.created_at >= thirty_days_ago),
        "deactivated": _count(db, models.User, models.User.is_active == False),
        "unverified_older_than_7_days": _count(
            db,
            models.User,
            models.User.is_verified == False,
            models.User.created_at < seven_days_ago,
        ),
    }

    category_definitions = [
        ("movies", "Movies", models.Movie, models.Movie.watched),
        ("tv_shows", "TV shows", models.TVShow, models.TVShow.watched),
        ("anime", "Anime", models.Anime, models.Anime.watched),
        ("video_games", "Video games", models.VideoGame, models.VideoGame.played),
        ("music", "Music", models.Music, models.Music.listened),
        ("books", "Books", models.Book, models.Book.read),
    ]
    categories = []
    total_items = completed_items = rated_items = reviewed_items = public_reviews = 0
    users_with_library: set[int] = set()
    for key, label, model, completed_field in category_definitions:
        has_review = (model.review.isnot(None)) & (func.length(func.trim(model.review)) > 0)
        total, completed, rated, reviewed, public = db.query(
            func.count(model.id),
            func.sum(case((completed_field == True, 1), else_=0)),
            func.sum(case((model.rating.isnot(None), 1), else_=0)),
            func.sum(case((has_review, 1), else_=0)),
            func.sum(case((has_review & (model.review_public == True), 1), else_=0)),
        ).one()
        total = int(total or 0)
        completed = int(completed or 0)
        rated = int(rated or 0)
        reviewed = int(reviewed or 0)
        public = int(public or 0)
        total_items += total
        completed_items += completed
        rated_items += rated
        reviewed_items += reviewed
        public_reviews += public
        categories.append({
            "key": key,
            "label": label,
            "total": total,
            "completed": completed,
            "rated": rated,
            "reviewed": reviewed,
        })
        users_with_library.update(
            user_id for user_id, in db.query(model.user_id).distinct().all()
        )

    users["with_library_items"] = len(users_with_library)
    users["without_library_items"] = max(total_users - len(users_with_library), 0)
    content = {
        "total_items": total_items,
        "completed_items": completed_items,
        "rated_items": rated_items,
        "reviewed_items": reviewed_items,
        "public_reviews": public_reviews,
        "completion_percentage": round((completed_items / total_items * 100) if total_items else 0, 1),
        "categories": categories,
        "custom_tabs": _count(db, models.CustomTab),
        "custom_items": _count(db, models.CustomTabItem),
    }

    approved_collections = db.query(models.Collection).options(
        selectinload(models.Collection.items)
    ).filter(models.Collection.moderation_status == "approved").all()
    approved_media = _media_lookup_for_collections(db, approved_collections)
    stale_approvals = sum(
        1 for collection in approved_collections
        if not _approval_is_current(collection, db, approved_media)
    )
    collection_totals = db.query(
        func.coalesce(func.sum(models.Collection.view_count), 0),
        func.coalesce(func.sum(models.Collection.helpful_count), 0),
        func.coalesce(func.sum(models.Collection.report_count), 0),
    ).one()
    reports_by_reason = [
        {"reason": reason, "count": int(count)}
        for reason, count in db.query(
            models.CollectionReport.reason,
            func.count(models.CollectionReport.id),
        ).group_by(models.CollectionReport.reason).order_by(func.count(models.CollectionReport.id).desc()).all()
    ]
    moderation = {
        "collections_total": _count(db, models.Collection),
        "public": _count(db, models.Collection, models.Collection.is_public == True),
        "pending": _count(
            db, models.Collection,
            models.Collection.is_public == True,
            models.Collection.moderation_status == "pending",
        ),
        "approved": len(approved_collections) - stale_approvals,
        "stale_approvals": stale_approvals,
        "rejected": _count(db, models.Collection, models.Collection.moderation_status == "rejected"),
        "views": int(collection_totals[0] or 0),
        "helpful": int(collection_totals[1] or 0),
        "reports": int(collection_totals[2] or 0),
        "reports_by_reason": reports_by_reason,
    }

    engagement = {
        "activity_entries_7_days": _count(
            db, models.ActivityEntry, models.ActivityEntry.occurred_at >= seven_days_ago
        ),
        "activity_entries_30_days": _count(
            db, models.ActivityEntry, models.ActivityEntry.occurred_at >= thirty_days_ago
        ),
        "active_journal_users_30_days": int(db.query(
            func.count(func.distinct(models.ActivityEntry.user_id))
        ).filter(models.ActivityEntry.occurred_at >= thirty_days_ago).scalar() or 0),
        "completion_moments": _count(db, models.CompletionMoment),
        "next_up_items": _count(db, models.NextUpItem),
        "friendships": _count(db, models.Friendship),
        "recommendation_requests": _count(db, models.RecommendationRequest),
        "recommendation_submissions": _count(db, models.RecommendationSubmission),
    }

    signup_dates = [
        created_at for created_at, in db.query(models.User.created_at).filter(
            models.User.created_at >= thirty_days_ago
        ).all() if created_at
    ]
    signup_counts = {}
    for created_at in signup_dates:
        key = created_at.date().isoformat()
        signup_counts[key] = signup_counts.get(key, 0) + 1
    growth = []
    for days_ago in range(29, -1, -1):
        day = (now - timedelta(days=days_ago)).date().isoformat()
        growth.append({"date": day, "signups": signup_counts.get(day, 0)})

    recent_users = db.query(models.User).order_by(
        models.User.created_at.desc(), models.User.id.desc()
    ).limit(50).all()
    recent_ids = [user.id for user in recent_users]
    library_counts = {user_id: 0 for user_id in recent_ids}
    for _, _, model, _ in category_definitions:
        for user_id, count in db.query(model.user_id, func.count(model.id)).filter(
            model.user_id.in_(recent_ids)
        ).group_by(model.user_id).all():
            library_counts[user_id] += int(count)
    activity_by_user = {
        user_id: {"count": int(count), "last": last_activity}
        for user_id, count, last_activity in db.query(
            models.ActivityEntry.user_id,
            func.count(models.ActivityEntry.id),
            func.max(models.ActivityEntry.occurred_at),
        ).filter(models.ActivityEntry.user_id.in_(recent_ids)).group_by(models.ActivityEntry.user_id).all()
    }
    public_by_user = {
        user_id: int(count)
        for user_id, count in db.query(
            models.Collection.user_id, func.count(models.Collection.id)
        ).filter(
            models.Collection.user_id.in_(recent_ids),
            models.Collection.is_public == True,
        ).group_by(models.Collection.user_id).all()
    }
    user_rows = [{
        "username": user.username,
        "joined_at": user.created_at.isoformat() if user.created_at else None,
        "is_active": bool(user.is_active),
        "is_verified": bool(user.is_verified),
        "library_items": library_counts.get(user.id, 0),
        "activity_entries": activity_by_user.get(user.id, {}).get("count", 0),
        "last_activity_at": (
            activity_by_user[user.id]["last"].isoformat()
            if user.id in activity_by_user and activity_by_user[user.id]["last"] else None
        ),
        "public_collections": public_by_user.get(user.id, 0),
    } for user in recent_users]

    return {
        "generated_at": now.isoformat(),
        "users": users,
        "content": content,
        "engagement": engagement,
        "moderation": moderation,
        "growth": growth,
        "recent_users": user_rows,
        "privacy_note": "Operational aggregates only. Emails, private notes, reviews, and library titles are excluded.",
    }


def _return_to_review(collection: models.Collection) -> None:
    if collection.moderation_status in {"approved", "rejected"}:
        collection.moderation_status = "pending"
        collection.approved_at = None
        collection.approved_content_hash = None


def _get_collection(db: Session, user_id: int, collection_id: int) -> models.Collection:
    collection = db.query(models.Collection).filter(
        models.Collection.id == collection_id,
        models.Collection.user_id == user_id,
    ).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


def _get_media_item(db: Session, user_id: int, category: str, item_id: int):
    model, _ = CATEGORIES[category]
    return db.query(model).filter(model.id == item_id, model.user_id == user_id).first()


def _media_lookup_for_collections(db: Session, collections: list[models.Collection]) -> dict:
    """Resolve polymorphic collection items in at most six media queries."""
    references: dict[str, set[tuple[int, int]]] = {category: set() for category in CATEGORIES}
    for collection in collections:
        for item in collection.items:
            if item.category in references:
                references[item.category].add((collection.user_id, item.item_id))
    lookup = {}
    for category, pairs in references.items():
        if not pairs:
            continue
        model, _ = CATEGORIES[category]
        owner_ids = {owner_id for owner_id, _ in pairs}
        item_ids = {item_id for _, item_id in pairs}
        for media in db.query(model).filter(model.user_id.in_(owner_ids), model.id.in_(item_ids)).all():
            lookup[(media.user_id, category, media.id)] = media
    return lookup


def _serialize_item(
    item: models.CollectionItem,
    db: Session,
    user_id: int,
    media_lookup: dict | None = None,
) -> dict:
    media = (
        media_lookup.get((user_id, item.category, item.item_id))
        if media_lookup is not None
        else _get_media_item(db, user_id, item.category, item.item_id)
    )
    artwork_field = ARTWORK_FIELDS[item.category]
    return {
        "id": item.id,
        "category": item.category,
        "category_label": CATEGORIES[item.category][1],
        "item_id": item.item_id,
        "title": media.title if media else "Deleted library item",
        "position": item.position,
        "available": media is not None,
        "curator_note": item.curator_note,
        "artwork_url": getattr(media, artwork_field, None) if media else None,
    }


def _serialize_collection(
    collection: models.Collection,
    db: Session,
    user_id: int,
    media_lookup: dict | None = None,
) -> dict:
    items = sorted(collection.items, key=lambda item: (item.position, item.id))
    moderation_status = collection.moderation_status
    if moderation_status == "approved" and not _approval_is_current(collection, db, media_lookup):
        moderation_status = "pending"
    return {
        "id": collection.id,
        "name": collection.name,
        "description": collection.description,
        "cover_url": collection.cover_url,
        "is_public": collection.is_public,
        "moderation_status": moderation_status,
        "public_url": f"/collections/public/{collection.id}" if collection.is_public else None,
        "view_count": collection.view_count or 0,
        "helpful_count": collection.helpful_count or 0,
        "report_count": collection.report_count or 0,
        "created_at": collection.created_at,
        "items": [_serialize_item(item, db, user_id, media_lookup) for item in items],
    }


def _available_items(
    collection: models.Collection,
    db: Session,
    user_id: int,
    media_lookup: dict | None = None,
) -> list[dict]:
    return [
        serialized for item in sorted(collection.items, key=lambda entry: (entry.position, entry.id))
        if (serialized := _serialize_item(item, db, user_id, media_lookup))["available"]
    ]


def _media_identity_key(media, category: str) -> tuple:
    """Return the fields that distinguish same-titled editions for reuse/copy."""
    identity_fields = {
        "movies": ("year", "director"),
        "tv-shows": ("year",),
        "anime": ("year",),
        "video-games": ("release_date",),
        "music": ("year", "artist"),
        "books": ("year", "author"),
    }[category]
    values = [media.title.strip().casefold()]
    for field in identity_fields:
        value = getattr(media, field, None)
        values.append(value.strip().casefold() if isinstance(value, str) else value)
    return tuple(values)


def _approval_content_hash(
    collection: models.Collection,
    db: Session,
    media_lookup: dict | None = None,
) -> str:
    items = _available_items(collection, db, collection.user_id, media_lookup)
    payload = {
        "name": collection.name,
        "description": collection.description,
        "cover_url": collection.cover_url,
        "items": [
            {
                "category": item["category"],
                "title": item["title"],
                "position": item["position"],
                "curator_note": item["curator_note"],
                "artwork_url": item["artwork_url"],
            }
            for item in items
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _approval_is_current(
    collection: models.Collection,
    db: Session,
    media_lookup: dict | None = None,
) -> bool:
    if collection.moderation_status != "approved" or not collection.approved_content_hash:
        return False
    current_hash = _approval_content_hash(collection, db, media_lookup)
    return hmac.compare_digest(collection.approved_content_hash, current_hash)


def _require_public_ready(collection: models.Collection, description: str | None, db: Session) -> None:
    if len((description or "").strip()) < PUBLIC_COLLECTION_MIN_DESCRIPTION_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"Add at least {PUBLIC_COLLECTION_MIN_DESCRIPTION_CHARS} characters of original context before publishing.",
        )
    if len(_available_items(collection, db, collection.user_id)) < PUBLIC_COLLECTION_MIN_ITEMS:
        raise HTTPException(
            status_code=422,
            detail=f"Add at least {PUBLIC_COLLECTION_MIN_ITEMS} available titles before publishing.",
        )


def _copy_media_for_user(
    db: Session,
    source,
    category: str,
    user_id: int,
    existing_lookup: dict | None = None,
):
    """Reuse a matching title or create a clean, private library record."""
    model, _ = CATEGORIES[category]
    key = (category, _media_identity_key(source, category))
    existing = existing_lookup.get(key) if existing_lookup is not None else None
    if existing_lookup is None:
        # Keep the SQL comparison aligned with the database's LOWER() behavior;
        # the stricter in-memory identity comparison below still uses casefold().
        title = source.title.strip().lower()
        candidates = db.query(model).filter(
            model.user_id == user_id,
            func.lower(model.title) == title,
        ).all()
        existing = next(
            (candidate for candidate in candidates if _media_identity_key(candidate, category) == key[1]),
            None,
        )
    if existing:
        return existing
    values = {field: getattr(source, field, None) for field in COPY_FIELDS[category]}
    values.update({"user_id": user_id, "rating": None, "review": None, "review_public": False})
    completion_field = {
        "movies": "watched", "tv-shows": "watched", "anime": "watched",
        "video-games": "played", "music": "listened", "books": "read",
    }[category]
    values[completion_field] = False
    copied = model(**values)
    db.add(copied)
    db.flush()
    if existing_lookup is not None:
        existing_lookup[key] = copied
    return copied


@router.get("/", response_model=List[schemas.Collection])
async def list_collections(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    collections = db.query(models.Collection).options(selectinload(models.Collection.items)).filter(
        models.Collection.user_id == current_user.id,
    ).order_by(models.Collection.created_at.desc(), models.Collection.id.desc()).all()
    media_lookup = _media_lookup_for_collections(db, collections)
    return [_serialize_collection(collection, db, current_user.id, media_lookup) for collection in collections]


@router.post("/", response_model=schemas.Collection, status_code=status.HTTP_201_CREATED)
async def create_collection(
    payload: schemas.CollectionCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    collection = models.Collection(
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        cover_url=payload.cover_url,
    )
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return _serialize_collection(collection, db, current_user.id)


@router.patch("/{collection_id}", response_model=schemas.Collection)
async def update_collection(
    collection_id: int,
    payload: schemas.CollectionUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    collection = _get_collection(db, current_user.id, collection_id)
    updates = payload.model_dump(exclude_unset=True)
    proposed_description = updates.get("description", collection.description)
    proposed_public = updates.get("is_public", collection.is_public)
    if proposed_public:
        _require_public_ready(collection, proposed_description, db)
    content_changed = False
    if "name" in updates and updates["name"] is not None:
        normalized = updates["name"].strip()
        if not normalized:
            raise HTTPException(status_code=422, detail="Collection name cannot be blank")
        content_changed = content_changed or normalized != collection.name
        collection.name = normalized
    if "description" in updates:
        normalized_description = (updates["description"] or "").strip() or None
        content_changed = content_changed or normalized_description != collection.description
        collection.description = normalized_description
    if "cover_url" in updates:
        content_changed = content_changed or updates["cover_url"] != collection.cover_url
        collection.cover_url = updates["cover_url"]
    if content_changed:
        _return_to_review(collection)
    if "is_public" in updates:
        was_public = collection.is_public
        collection.is_public = updates["is_public"]
        if collection.is_public and not was_public:
            collection.published_at = datetime.utcnow()
        elif not collection.is_public:
            collection.published_at = None
            collection.moderation_status = "pending"
            collection.approved_at = None
            collection.approved_content_hash = None
    db.commit()
    db.refresh(collection)
    return _serialize_collection(collection, db, current_user.id)


@router.get("/moderation/queue")
async def collection_moderation_queue(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    collections = db.query(models.Collection).options(selectinload(models.Collection.items)).filter(
        models.Collection.is_public == True,
        models.Collection.moderation_status.in_(("pending", "approved")),
    ).order_by(models.Collection.report_count.desc(), models.Collection.published_at.asc()).limit(100).all()
    media_lookup = _media_lookup_for_collections(db, collections)
    return [_serialize_collection(collection, db, collection.user_id, media_lookup) for collection in collections]


@router.get("/moderation/insights")
async def collection_moderator_insights(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Give trusted moderators a read-only, privacy-conscious site health view."""
    _require_moderator(current_user)
    return _moderator_site_insights(db)


@router.patch("/{collection_id}/moderation", response_model=schemas.Collection)
async def moderate_collection(
    collection_id: int,
    payload: schemas.CollectionModerationUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    collection = db.query(models.Collection).filter(models.Collection.id == collection_id).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    if payload.status == "approved":
        if not collection.is_public:
            raise HTTPException(status_code=422, detail="Only a published collection can be approved")
        _require_public_ready(collection, collection.description, db)
        collection.approved_at = datetime.utcnow()
        collection.approved_content_hash = _approval_content_hash(collection, db)
    else:
        collection.approved_at = None
        collection.approved_content_hash = None
    collection.moderation_status = payload.status
    db.commit()
    db.refresh(collection)
    return _serialize_collection(collection, db, collection.user_id)


@router.get("/{collection_id}/moderation/reports")
async def collection_moderation_reports(
    collection_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_moderator(current_user)
    if not db.query(models.Collection.id).filter(models.Collection.id == collection_id).first():
        raise HTTPException(status_code=404, detail="Collection not found")
    reports = db.query(models.CollectionReport).filter(
        models.CollectionReport.collection_id == collection_id,
    ).order_by(models.CollectionReport.created_at.desc()).all()
    return [
        {"id": report.id, "reason": report.reason, "details": report.details, "created_at": report.created_at}
        for report in reports
    ]


@router.post("/public/{collection_id}/copy", response_model=schemas.Collection, status_code=status.HTTP_201_CREATED)
async def copy_public_collection(
    collection_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    source_collection = _public_collection_or_404(db, collection_id)
    source_items = sorted(source_collection.items, key=lambda item: (item.position, item.id))[:PUBLIC_COLLECTION_MAX_ITEMS]
    source_lookup = _media_lookup_for_collections(db, [source_collection])
    titles_by_category: dict[str, set[str]] = {category: set() for category in CATEGORIES}
    for source_item in source_items:
        source_media = source_lookup.get((source_collection.user_id, source_item.category, source_item.item_id))
        if source_media:
            titles_by_category[source_item.category].add(source_media.title.strip().lower())
    existing_lookup = {}
    for category, titles in titles_by_category.items():
        if not titles:
            continue
        model, _ = CATEGORIES[category]
        for media in db.query(model).filter(
            model.user_id == current_user.id,
            func.lower(model.title).in_(titles),
        ).all():
            existing_lookup[(category, _media_identity_key(media, category))] = media
    copy = models.Collection(
        user_id=current_user.id,
        name=f"{source_collection.name} — saved"[:80],
        description=source_collection.description,
        cover_url=source_collection.cover_url,
        is_public=False,
        moderation_status="pending",
    )
    db.add(copy)
    db.flush()
    copied_position = 0
    for source_item in source_items:
        source_media = source_lookup.get((source_collection.user_id, source_item.category, source_item.item_id))
        if not source_media:
            continue
        media = _copy_media_for_user(
            db, source_media, source_item.category, current_user.id, existing_lookup
        )
        db.add(models.CollectionItem(
            collection_id=copy.id,
            category=source_item.category,
            item_id=media.id,
            position=copied_position,
            curator_note=source_item.curator_note,
        ))
        copied_position += 1
    db.commit()
    db.refresh(copy)
    return _serialize_collection(copy, db, current_user.id)


def _public_collection_or_404(db: Session, collection_id: int) -> models.Collection:
    collection = db.query(models.Collection).options(selectinload(models.Collection.items)).join(
        models.User, models.Collection.user_id == models.User.id
    ).filter(
        models.Collection.id == collection_id,
        models.Collection.is_public == True,
        models.Collection.moderation_status != "rejected",
        models.User.is_active == True,
    ).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Shared collection not found")
    media_lookup = _media_lookup_for_collections(db, [collection])
    items = _available_items(collection, db, collection.user_id, media_lookup)
    if (
        len((collection.description or "").strip()) < PUBLIC_COLLECTION_MIN_DESCRIPTION_CHARS
        or len(items) < PUBLIC_COLLECTION_MIN_ITEMS
    ):
        raise HTTPException(status_code=404, detail="Shared collection not available")
    return collection


@router.get("/explore")
async def explore_collections(
    request: Request,
    q: str = "",
    category: str = "",
    db: Session = Depends(get_db),
):
    """Render the quality-gated, moderator-approved public collection directory."""
    query = db.query(models.Collection).options(selectinload(models.Collection.items)).join(
        models.User, models.Collection.user_id == models.User.id
    ).filter(
        models.Collection.is_public == True,
        models.Collection.moderation_status == "approved",
        models.User.is_active == True,
    )
    normalized_query = q.strip()[:80]
    if normalized_query:
        search = f"%{normalized_query}%"
        query = query.filter(
            (models.Collection.name.ilike(search)) | (models.Collection.description.ilike(search))
        )
    if category in CATEGORIES:
        query = query.filter(models.Collection.items.any(models.CollectionItem.category == category))
    collections = query.order_by(
        models.Collection.helpful_count.desc(),
        models.Collection.published_at.desc(),
    ).limit(500).all()
    media_lookup = _media_lookup_for_collections(db, collections)
    cards = []
    for collection in collections:
        if not _approval_is_current(collection, db, media_lookup):
            continue
        items = _available_items(collection, db, collection.user_id, media_lookup)
        if len(items) < PUBLIC_COLLECTION_MIN_ITEMS:
            continue
        cover = collection.cover_url or next((item["artwork_url"] for item in items if item["artwork_url"]), "")
        image = (
            f'<img src="{escape(cover, quote=True)}" alt="" loading="lazy" referrerpolicy="no-referrer">'
            if cover else '<span class="collection-tile__placeholder" aria-hidden="true">✦</span>'
        )
        categories = " · ".join(dict.fromkeys(item["category_label"] for item in items))
        cards.append(
            '<article class="collection-tile">'
            f'<a class="collection-tile__art" href="/collections/public/{collection.id}">{image}</a>'
            '<div class="collection-tile__copy">'
            f'<p>{escape(categories)}</p><h2><a href="/collections/public/{collection.id}">{escape(collection.name)}</a></h2>'
            f'<span>{len(items)} picks · {collection.helpful_count or 0} helpful</span>'
            f'<p class="collection-tile__intro">{escape((collection.description or "")[:180])}</p>'
            '</div></article>'
        )
        if len(cards) >= 48:
            break
    template = (Path(__file__).parents[1] / "templates" / "collection_gallery.html").read_text(encoding="utf-8")
    if cards:
        gallery_content = "".join(cards)
    elif normalized_query or category:
        gallery_content = '<div class="collection-gallery__empty"><h2>No collections found</h2><p>Try a different search or media type.</p></div>'
    else:
        gallery_content = (
            '<div class="collection-gallery__empty"><h2>The gallery is opening soon</h2>'
            '<p>The first reviewed member collections will appear here. '
            '<a href="/#landing-auth">Create your library</a> and start shaping one.</p></div>'
        )
    values = {
        "COLLECTIONS": gallery_content,
        "QUERY": escape(normalized_query, quote=True),
        "CATEGORY": escape(category, quote=True),
        "COUNT": str(len(cards)),
        "SELECT_ALL": "selected" if not category else "",
        "SELECT_MOVIES": "selected" if category == "movies" else "",
        "SELECT_TV_SHOWS": "selected" if category == "tv-shows" else "",
        "SELECT_ANIME": "selected" if category == "anime" else "",
        "SELECT_VIDEO_GAMES": "selected" if category == "video-games" else "",
        "SELECT_MUSIC": "selected" if category == "music" else "",
        "SELECT_BOOKS": "selected" if category == "books" else "",
    }
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    gallery_is_indexable = not normalized_query and not category and len(cards) >= PUBLIC_COLLECTION_GALLERY_MIN
    if not gallery_is_indexable:
        template = template.replace(
            '<meta name="robots" content="index, follow">',
            '<meta name="robots" content="noindex, follow">',
        )
    response = strict_html_response(template)
    response.headers["Cache-Control"] = "public, max-age=120"
    if not gallery_is_indexable:
        response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


@router.get("/public/{collection_id}")
async def public_collection(collection_id: int, request: Request, db: Session = Depends(get_db)):
    """Render the deliberately limited public view of an explicitly shared shelf."""
    collection = _public_collection_or_404(db, collection_id)
    template = (Path(__file__).parents[1] / "templates" / "public_collection.html").read_text(encoding="utf-8")
    visitor_hash, visitor_token, trusted_visitor = _visitor_identity(request)
    if trusted_visitor:
        existing_view = db.query(models.CollectionView.id).filter(
            models.CollectionView.collection_id == collection.id,
            models.CollectionView.visitor_hash == visitor_hash,
        ).first()
        if not existing_view:
            db.add(models.CollectionView(collection_id=collection.id, visitor_hash=visitor_hash))
            try:
                db.flush()
                db.query(models.Collection).filter(models.Collection.id == collection.id).update(
                    {models.Collection.view_count: models.Collection.view_count + 1},
                    synchronize_session=False,
                )
                db.commit()
                db.refresh(collection)
            except IntegrityError:
                db.rollback()
    media_lookup = _media_lookup_for_collections(db, [collection])
    items = _available_items(collection, db, collection.user_id, media_lookup)
    item_cards = "".join(
        '<li class="collection-entry">'
        f'<span class="collection-entry__number">{position:02d}</span>'
        + (f'<img src="{escape(item["artwork_url"], quote=True)}" alt="" loading="lazy" referrerpolicy="no-referrer">' if item["artwork_url"] else '')
        + f'<div><p>{escape(item["category_label"])}</p><h2>{escape(item["title"])}</h2>'
        + (f'<div class="collection-entry__note">{escape(item["curator_note"])}</div>' if item["curator_note"] else '')
        + '</div></li>'
        for position, item in enumerate(items, 1)
    )
    description = (collection.description or "").strip()
    approved = _approval_is_current(collection, db, media_lookup)
    cover = collection.cover_url or next((item["artwork_url"] for item in items if item["artwork_url"]), "")
    values = {
        "TITLE": escape(collection.name),
        "DESCRIPTION": escape(description[:160], quote=True),
        "PATH": f"/collections/public/{collection.id}",
        "INTRO": escape(description),
        "ITEMS": item_cards,
        "COUNT": str(len(items)),
        "VIEWS": str(collection.view_count or 0),
        "HELPFUL": str(collection.helpful_count or 0),
        "COLLECTION_ID": str(collection.id),
        "ROBOTS": "index, follow" if approved else "noindex, follow",
        "COVER": (
            f'<img class="share-cover" src="{escape(cover, quote=True)}" alt="" referrerpolicy="no-referrer">'
            if cover else ""
        ),
        "OG_IMAGE": (
            f'<meta property="og:image" content="{escape(cover, quote=True)}">' if cover else ""
        ),
        "STRUCTURED_DATA": json.dumps({
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": collection.name,
            "description": description,
            "numberOfItems": len(items),
            "itemListElement": [
                {"@type": "ListItem", "position": position, "item": {"@type": "CreativeWork", "name": item["title"]}}
                for position, item in enumerate(items, 1)
            ],
        }, ensure_ascii=True).replace("<", "\\u003c"),
    }
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    response = strict_html_response(template)
    response.headers["X-Robots-Tag"] = "index, follow" if approved else "noindex, follow"
    response.headers["Cache-Control"] = "private, no-cache, must-revalidate"
    _set_visitor_cookie(response, visitor_token)
    return response


@router.post("/public/{collection_id}/helpful")
async def mark_collection_helpful(collection_id: int, request: Request, db: Session = Depends(get_db)):
    collection = _public_collection_or_404(db, collection_id)
    visitor_hash, visitor_token, _ = _visitor_identity(request)
    existing = db.query(models.CollectionReaction.id).filter(
        models.CollectionReaction.collection_id == collection.id,
        models.CollectionReaction.visitor_hash == visitor_hash,
    ).first()
    if not existing:
        db.add(models.CollectionReaction(collection_id=collection.id, visitor_hash=visitor_hash))
        try:
            db.flush()
            db.query(models.Collection).filter(models.Collection.id == collection.id).update(
                {models.Collection.helpful_count: models.Collection.helpful_count + 1},
                synchronize_session=False,
            )
            db.commit()
            db.refresh(collection)
        except IntegrityError:
            db.rollback()
            db.refresh(collection)
    response = JSONResponse({"helpful": True, "count": collection.helpful_count or 0})
    response.headers["Cache-Control"] = "no-store"
    _set_visitor_cookie(response, visitor_token)
    return response


@router.post("/public/{collection_id}/report", status_code=status.HTTP_201_CREATED)
async def report_collection(
    collection_id: int,
    payload: schemas.CollectionReportCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    collection = _public_collection_or_404(db, collection_id)
    visitor_hash, visitor_token, _ = _visitor_identity(request)
    existing = db.query(models.CollectionReport.id).filter(
        models.CollectionReport.collection_id == collection.id,
        models.CollectionReport.visitor_hash == visitor_hash,
    ).first()
    if not existing:
        db.add(models.CollectionReport(
            collection_id=collection.id,
            visitor_hash=visitor_hash,
            reason=payload.reason,
            details=payload.details.strip() if payload.details else None,
        ))
        try:
            db.flush()
            db.query(models.Collection).filter(models.Collection.id == collection.id).update(
                {models.Collection.report_count: models.Collection.report_count + 1},
                synchronize_session=False,
            )
            db.commit()
        except IntegrityError:
            db.rollback()
    response = JSONResponse({"reported": True}, status_code=201)
    response.headers["Cache-Control"] = "no-store"
    _set_visitor_cookie(response, visitor_token)
    return response


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    collection = _get_collection(db, current_user.id, collection_id)
    db.delete(collection)
    db.commit()


@router.post("/{collection_id}/items", response_model=schemas.CollectionItem, status_code=status.HTTP_201_CREATED)
async def add_collection_item(
    collection_id: int,
    payload: schemas.CollectionItemCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    collection = _get_collection(db, current_user.id, collection_id)
    if len(collection.items) >= PUBLIC_COLLECTION_MAX_ITEMS:
        raise HTTPException(
            status_code=422,
            detail=f"Collections can contain up to {PUBLIC_COLLECTION_MAX_ITEMS} titles",
        )
    if not _get_media_item(db, current_user.id, payload.category, payload.item_id):
        raise HTTPException(status_code=404, detail="Library item not found")
    duplicate = db.query(models.CollectionItem).filter(
        models.CollectionItem.collection_id == collection_id,
        models.CollectionItem.category == payload.category,
        models.CollectionItem.item_id == payload.item_id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="That item is already in this collection")
    highest_position = db.query(func.max(models.CollectionItem.position)).filter(
        models.CollectionItem.collection_id == collection_id,
    ).scalar()
    item = models.CollectionItem(
        collection_id=collection_id,
        category=payload.category,
        item_id=payload.item_id,
        position=(highest_position if highest_position is not None else -1) + 1,
    )
    db.add(item)
    _return_to_review(collection)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That item is already in this collection")
    db.refresh(item)
    return _serialize_item(item, db, current_user.id)


@router.patch("/{collection_id}/items/{item_id}", response_model=schemas.CollectionItem)
async def update_collection_item(
    collection_id: int,
    item_id: int,
    payload: schemas.CollectionItemUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    collection = _get_collection(db, current_user.id, collection_id)
    item = db.query(models.CollectionItem).filter(
        models.CollectionItem.id == item_id,
        models.CollectionItem.collection_id == collection_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Collection item not found")
    item.curator_note = payload.curator_note
    _return_to_review(collection)
    db.commit()
    db.refresh(item)
    return _serialize_item(item, db, current_user.id)


@router.put("/{collection_id}/items/{item_id}/position", response_model=List[schemas.CollectionItem])
async def move_collection_item(
    collection_id: int,
    item_id: int,
    payload: schemas.CollectionItemMove,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    collection = _get_collection(db, current_user.id, collection_id)
    items = db.query(models.CollectionItem).filter(
        models.CollectionItem.collection_id == collection_id,
    ).order_by(models.CollectionItem.position, models.CollectionItem.id).all()
    target = next((item for item in items if item.id == item_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Collection item not found")
    items.remove(target)
    items.insert(min(payload.position, len(items)), target)
    for position, item in enumerate(items):
        item.position = position
    _return_to_review(collection)
    db.commit()
    return [_serialize_item(item, db, current_user.id) for item in items]


@router.delete("/{collection_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_collection_item(
    collection_id: int,
    item_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    collection = _get_collection(db, current_user.id, collection_id)
    item = db.query(models.CollectionItem).filter(
        models.CollectionItem.id == item_id,
        models.CollectionItem.collection_id == collection_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Collection item not found")
    db.delete(item)
    _return_to_review(collection)
    db.commit()
