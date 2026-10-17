"""Opt-in public profiles at /u/<username>.

Nothing about a member is public until they switch their profile on. Even then:
- categories the member marked private are never counted or listed,
- only reviews that already pass the public review checks (and are not
  suspended by reports) are shown,
- only public collections that pass the collection checks are listed,
- email, friends, notes, progress and unrated items are never shown. The one
  social number is how many people joined through the member's invite link
  (a count, never who), shown only alongside the library stats.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from . import friend_invites, models, supporters, title_pages
from .review_quality import evaluate_public_review, is_public_review_safe

BIO_MAX_CHARS = 280
FAVORITE_MIN_RATING = 8
FAVORITES_LIMIT = 12
REVIEWS_LIMIT = 8
COLLECTIONS_LIMIT = 6
# Usernames made of these characters get a readable /u/<username> address.
# (Kept in step with PUBLIC_PROFILE_PATH in middleware.py, which lets these through the bot filter.)
HANDLE_RE = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,49}")
CONTROL_RE = re.compile(r"[\u0000-\u0008\u000b-\u001f\u007f​-‏‪-‮⁦-⁩]")

# Library category -> (URL kind, privacy flag on the user, plural label, completion verb)
CATEGORIES = {
    "movies": ("movie", "movies_private", "Movies", "watched"),
    "tv-shows": ("tv", "tv_shows_private", "TV shows", "watched"),
    "anime": ("anime", "anime_private", "Anime", "watched"),
    "video-games": ("game", "video_games_private", "Games", "played"),
    "music": ("album", "music_private", "Albums", "listened"),
    "books": ("book", "books_private", "Books", "read"),
}
REVIEW_CATEGORY_TO_LIBRARY = {review: library for _, (_, review, library, _, _) in title_pages.KINDS.items()}
SETTINGS_FIELDS = ("enabled", "show_stats", "show_favorites", "show_reviews", "show_collections")


class BioError(ValueError):
    """Raised when a bio cannot be shown publicly."""


def clean_bio(value: Optional[str]) -> Optional[str]:
    """Normalize a bio and reject anything that would not be safe to publish."""
    if value is None:
        return None
    text = unicodedata.normalize("NFC", str(value))
    text = CONTROL_RE.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))
    lines = [" ".join(line.split()) for line in text.split("\n")]
    text = "\n".join(lines).strip()
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    if not text:
        return None
    if len(text) > BIO_MAX_CHARS:
        raise BioError(f"Keep your bio to {BIO_MAX_CHARS} characters.")
    if not is_public_review_safe(text):
        raise BioError("Bios can't include links, email addresses, phone numbers or promotions.")
    return text


def get_settings(db: Session, user_id: int) -> Optional[models.PublicProfile]:
    return db.query(models.PublicProfile).filter(models.PublicProfile.user_id == user_id).first()


def settings_payload(user: models.User, profile: Optional[models.PublicProfile]) -> dict:
    return {
        "enabled": bool(profile and profile.enabled),
        "bio": (profile.bio if profile else None) or "",
        "show_stats": profile.show_stats if profile else True,
        "show_favorites": profile.show_favorites if profile else True,
        "show_reviews": profile.show_reviews if profile else True,
        "show_collections": profile.show_collections if profile else True,
        "url": profile_path(user),
        "bio_max_chars": BIO_MAX_CHARS,
        "private_categories": [CATEGORIES[c][2] for c in CATEGORIES if getattr(user, CATEGORIES[c][1], False)],
        "statistics_private": bool(user.statistics_private),
    }


def save_settings(db: Session, user: models.User, changes: dict) -> models.PublicProfile:
    profile = get_settings(db, user.id)
    if profile is None:
        profile = models.PublicProfile(user_id=user.id, enabled=False)
        db.add(profile)
    for field in SETTINGS_FIELDS:
        if changes.get(field) is not None:
            setattr(profile, field, bool(changes[field]))
    if "bio" in changes:
        profile.bio = clean_bio(changes["bio"])
    db.commit()
    db.refresh(profile)
    return profile


def profile_path(user: models.User) -> str:
    if HANDLE_RE.fullmatch(user.username or ""):
        return f"/u/{quote(user.username, safe='')}"
    return f"/u/id/{user.id}"


def enabled_profile_paths(db: Session, user_ids) -> dict[int, str]:
    """{user_id: /u/... path} for the given members who have switched their profile on."""
    ids = {int(i) for i in user_ids if i is not None}
    if not ids:
        return {}
    rows = db.query(models.User).join(models.PublicProfile, models.PublicProfile.user_id == models.User.id).filter(
        models.User.id.in_(ids), models.User.is_active == True, models.PublicProfile.enabled == True,
    ).all()
    return {user.id: profile_path(user) for user in rows}


def find_user(db: Session, handle: str) -> Optional[models.User]:
    """The active member with this username (exact match first, then a unique case-insensitive one)."""
    if not HANDLE_RE.fullmatch(handle or ""):
        return None
    active = db.query(models.User).filter(models.User.is_active == True)
    user = active.filter(models.User.username == handle).first()
    if user is not None:
        return user
    matches = active.filter(func.lower(models.User.username) == handle.lower()).limit(2).all()
    return matches[0] if len(matches) == 1 else None


def find_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    user = db.get(models.User, user_id)
    return user if user is not None and user.is_active else None


def visible_profile(db: Session, user: Optional[models.User]) -> Optional[models.PublicProfile]:
    if user is None or not user.is_active:
        return None
    profile = get_settings(db, user.id)
    return profile if profile is not None and profile.enabled else None


def _visible_categories(user: models.User) -> list[str]:
    return [category for category, (_, flag, _, _) in CATEGORIES.items() if not getattr(user, flag, False)]


def _model(category: str):
    return title_pages.KINDS[CATEGORIES[category][0]][0]


def _stats(db: Session, user: models.User) -> list[dict]:
    rows = []
    for category in _visible_categories(user):
        kind, _, label, verb = CATEGORIES[category]
        model = _model(category)
        done_field = getattr(model, title_pages.COMPLETE_FIELD[kind])
        total, finished, rated, average = db.query(
            func.count(model.id),
            func.sum(case((done_field == True, 1), else_=0)),
            func.count(model.rating),
            func.avg(model.rating),
        ).filter(model.user_id == user.id).one()
        if not total:
            continue
        rows.append({
            "category": category, "label": label, "verb": verb, "total": int(total),
            "finished": int(finished or 0), "rated": int(rated or 0),
            "average": round(float(average), 1) if average is not None and rated else None,
        })
    return rows


def _favorites(db: Session, user: models.User) -> list[dict]:
    picks = []
    for category in _visible_categories(user):
        kind = CATEGORIES[category][0]
        model = _model(category)
        image_field = title_pages.IMAGE_FIELD[kind]
        for item in db.query(model).filter(
            model.user_id == user.id, model.rating >= FAVORITE_MIN_RATING, func.trim(model.title) != "",
        ).order_by(model.rating.desc(), model.id.desc()).limit(FAVORITES_LIMIT).all():
            picks.append({
                "kind": kind, "category": category, "label": title_pages.KINDS[kind][3],
                "title": item.title.strip(), "year": title_pages.item_year(kind, item),
                "rating": item.rating, "image": title_pages._safe_image(getattr(item, image_field, None)),
                "url": title_pages.path_for_item(kind, item), "_id": item.id,
            })
    # Highest rated first; spread across categories so one shelf doesn't take every slot.
    picks.sort(key=lambda pick: (-pick["rating"], -pick["_id"]))
    chosen, per_category, seen = [], {}, set()
    for pick in picks:
        identity = (pick["kind"], title_pages.normalize(pick["title"]), pick["year"])
        if identity in seen:
            continue  # The same title saved twice shows once.
        seen.add(identity)
        if per_category.get(pick["category"], 0) >= 4 and len(picks) > FAVORITES_LIMIT:
            continue
        per_category[pick["category"]] = per_category.get(pick["category"], 0) + 1
        chosen.append(pick)
        if len(chosen) >= FAVORITES_LIMIT:
            break
    for pick in chosen:
        pick.pop("_id", None)
    return chosen


def _reviews(db: Session, user: models.User) -> list[dict]:
    from .routers.reviews import _current_state_hides_review
    reviews = []
    for kind, (model, review_category, library_category, label, _) in title_pages.KINDS.items():
        if library_category not in _visible_categories(user):
            continue
        items = db.query(model).filter(
            model.user_id == user.id, model.review_public == True, model.review.isnot(None),
            func.length(func.trim(model.review)) >= title_pages.REVIEW_MIN_CHARS,
        ).all()
        if not items:
            continue
        states = {s.item_id: s for s in db.query(models.PublicReviewState).filter(
            models.PublicReviewState.category == review_category,
            models.PublicReviewState.item_id.in_([item.id for item in items])).all()}
        for item in items:
            if not (item.title or "").strip():
                continue
            quality = evaluate_public_review(item.review, title_pages.REVIEW_MIN_CHARS, title_pages.REVIEW_DETAIL_MIN_CHARS)
            if not quality.safe or not quality.community_ready or _current_state_hides_review(states.get(item.id), review_category, item):
                continue
            reviews.append({
                "id": item.id, "category": review_category, "label": label, "title": item.title.strip(),
                "rating": item.rating, "review": item.review.strip(), "search_ready": quality.search_ready,
                "url": f"/reviews/{item.id}?category={review_category}",
                "title_url": title_pages.path_for_item(kind, item),
            })
    reviews.sort(key=lambda r: (not r["search_ready"], -r["id"]))
    unique, seen = [], set()
    for review in reviews:
        identity = (review["category"], title_pages.normalize(review["title"]))
        if identity not in seen:
            seen.add(identity)
            unique.append(review)
    return unique[:REVIEWS_LIMIT]


def _collections(db: Session, user: models.User) -> list[dict]:
    from .routers.collections import _collection_is_discoverable
    shown = []
    for collection in db.query(models.Collection).filter(
        models.Collection.user_id == user.id, models.Collection.is_public == True,
    ).order_by(models.Collection.id.desc()).limit(40).all():
        try:
            if not _collection_is_discoverable(collection, db):
                continue
        except Exception:
            continue
        shown.append({"name": collection.name, "url": f"/collections/public/{collection.id}",
                      "description": (collection.description or "")[:180], "items": len(collection.items)})
        if len(shown) >= COLLECTIONS_LIMIT:
            break
    return shown


@dataclass
class ProfileView:
    user: models.User
    profile: models.PublicProfile
    stats: list
    favorites: list
    reviews: list
    collections: list
    supporter: Optional[dict] = None
    friends_brought: int = 0

    @property
    def path(self) -> str:
        return profile_path(self.user)

    @property
    def total_titles(self) -> int:
        return sum(row["total"] for row in self.stats)

    @property
    def indexable(self) -> bool:
        """Only profiles with real, original content are offered to search engines."""
        search_ready_review = any(review["search_ready"] for review in self.reviews)
        return bool(search_ready_review or self.collections or (self.profile.bio and len(self.favorites) >= 6))


def build(db: Session, user: models.User, profile: models.PublicProfile) -> ProfileView:
    return ProfileView(
        user=user, profile=profile,
        stats=_stats(db, user) if profile.show_stats and not user.statistics_private else [],
        favorites=_favorites(db, user) if profile.show_favorites else [],
        reviews=_reviews(db, user) if profile.show_reviews else [],
        collections=_collections(db, user) if profile.show_collections else [],
        supporter=supporters.public_badge(db, user.id),
        # A count only (never who): shown with the library stats the member chose to share.
        friends_brought=friend_invites.friends_brought(db, user.id) if profile.show_stats else 0,
    )


def sitemap_paths(db: Session, limit: int = 300) -> list[str]:
    paths = []
    rows = db.query(models.User, models.PublicProfile).join(
        models.PublicProfile, models.PublicProfile.user_id == models.User.id,
    ).filter(models.PublicProfile.enabled == True, models.User.is_active == True).order_by(
        models.PublicProfile.updated_at.desc()).limit(limit * 3).all()
    for user, profile in rows:
        try:
            if build(db, user, profile).indexable:
                paths.append(profile_path(user))
        except Exception:
            continue
        if len(paths) >= limit:
            break
    return paths
