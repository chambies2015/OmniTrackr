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
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from . import badges, friend_invites, models, supporters, title_pages
from .review_quality import evaluate_public_review, is_public_review_safe

BIO_MAX_CHARS = 280
FAVORITE_MIN_RATING = 8
FAVORITES_LIMIT = 12
REVIEWS_LIMIT = 8
COLLECTIONS_LIMIT = 6
# Titles a member can pin to the top of their profile. Supporters get twice as many.
SHOWCASE_LIMIT = 3
SUPPORTER_SHOWCASE_LIMIT = 6
SHOWCASE_SEARCH_LIMIT = 12
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


class ShowcaseError(ValueError):
    """Raised when a showcase pick is not one of the member's own shareable titles."""


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


def settings_payload(user: models.User, profile: Optional[models.PublicProfile], db: Optional[Session] = None) -> dict:
    showcase = {}
    if db is not None:
        showcase = {"showcase": showcase_items(db, user), "showcase_limit": showcase_limit(db, user),
                    "showcase_supporter_limit": SUPPORTER_SHOWCASE_LIMIT}
    return {**showcase,
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


# ---------------------------------------------------------------- showcase

def showcase_limit(db: Session, user: models.User) -> int:
    return SUPPORTER_SHOWCASE_LIMIT if supporters.is_active(supporters.get_supporter(db, user.id)) else SHOWCASE_LIMIT


def _showcase_entry(category: str, item) -> dict:
    kind = CATEGORIES[category][0]
    return {
        "category": category, "id": item.id, "kind": kind, "label": title_pages.KINDS[kind][3],
        "title": item.title.strip(), "year": title_pages.item_year(kind, item), "rating": item.rating,
        "image": title_pages._safe_image(getattr(item, title_pages.IMAGE_FIELD[kind], None)),
        "url": title_pages.path_for_item(kind, item),
    }


def showcase_items(db: Session, user: models.User, limit: Optional[int] = None) -> list[dict]:
    """The member's pinned titles in order. Pins in private categories or for deleted titles are skipped."""
    visible = set(_visible_categories(user))
    pins = (db.query(models.ProfileShowcaseItem).filter(models.ProfileShowcaseItem.user_id == user.id)
            .order_by(models.ProfileShowcaseItem.position, models.ProfileShowcaseItem.id).all())
    shown = []
    for pin in pins:
        if pin.category not in visible:
            continue
        model = _model(pin.category)
        item = db.query(model).filter(model.id == pin.item_id, model.user_id == user.id).first()
        if item is None or not (item.title or "").strip():
            continue
        shown.append(_showcase_entry(pin.category, item))
        if limit is not None and len(shown) >= limit:
            break
    return shown


def showcase_search(db: Session, user: models.User, query: str = "") -> list[dict]:
    """Titles from the member's own shareable shelves to pick from: matches for ``query``, or their top rated."""
    words = " ".join((query or "").split())[:80]
    pattern = "%" + words.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    found = []
    for category in _visible_categories(user):
        model = _model(category)
        rows = db.query(model).filter(model.user_id == user.id, func.trim(model.title) != "")
        if words:
            rows = rows.filter(model.title.ilike(pattern, escape="\\"))
        rows = rows.order_by(model.rating.is_(None), model.rating.desc(), model.id.desc()).limit(SHOWCASE_SEARCH_LIMIT)
        found.extend(_showcase_entry(category, item) for item in rows.all())
    found.sort(key=lambda entry: (entry["rating"] is None, -(entry["rating"] or 0), entry["title"].casefold()))
    return found[:SHOWCASE_SEARCH_LIMIT]


def save_showcase(db: Session, user: models.User, picks: list) -> list[dict]:
    """Replace the member's pins with ``picks`` ([{"category", "id"}, ...] in order)."""
    limit = showcase_limit(db, user)
    if len(picks) > limit:
        raise ShowcaseError(f"You can pin up to {limit} titles.")
    visible = set(_visible_categories(user))
    seen, rows = set(), []
    for position, pick in enumerate(picks):
        category, item_id = pick.get("category"), pick.get("id")
        if category not in CATEGORIES or not isinstance(item_id, int) or isinstance(item_id, bool):
            raise ShowcaseError("Pick titles from your own library.")
        if category not in visible:
            raise ShowcaseError(f"{CATEGORIES[category][2]} are private, so they can't go on your profile.")
        if (category, item_id) in seen:
            continue
        model = _model(category)
        if db.query(model.id).filter(model.id == item_id, model.user_id == user.id).first() is None:
            raise ShowcaseError("Pick titles from your own library.")
        seen.add((category, item_id))
        rows.append(models.ProfileShowcaseItem(user_id=user.id, category=category, item_id=item_id, position=position))
    db.query(models.ProfileShowcaseItem).filter(models.ProfileShowcaseItem.user_id == user.id).delete()
    db.add_all(rows)
    db.commit()
    return showcase_items(db, user)


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
                "id": item.id, "category": review_category, "label": label, "title": item.title.strip(), "user_id": user.id,
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
    from .review_spoilers import attach
    return attach(db, unique[:REVIEWS_LIMIT])


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
    showcase: list = field(default_factory=list)
    supporting: bool = False  # current supporter, even with the badge hidden (owner hints only)
    friends_brought: int = 0
    badges: list = field(default_factory=list)

    @property
    def path(self) -> str:
        return profile_path(self.user)

    @property
    def total_titles(self) -> int:
        return sum(row["total"] for row in self.stats)

    @property
    def indexable(self) -> bool:
        """Only profiles with original member writing are offered to search engines.

        A short bio over a grid of rated titles is mostly a list of names, so it no
        longer counts on its own (AdSense "low value content", Oct 2026).
        """
        search_ready_review = any(review["search_ready"] for review in self.reviews)
        return bool(search_ready_review or self.collections)


def build(db: Session, user: models.User, profile: models.PublicProfile) -> ProfileView:
    return ProfileView(
        user=user, profile=profile,
        stats=_stats(db, user) if profile.show_stats and not user.statistics_private else [],
        favorites=_favorites(db, user) if profile.show_favorites else [],
        reviews=_reviews(db, user) if profile.show_reviews else [],
        collections=_collections(db, user) if profile.show_collections else [],
        supporter=supporters.public_badge(db, user.id),
        showcase=showcase_items(db, user, limit=showcase_limit(db, user)),
        supporting=supporters.is_active(supporters.get_supporter(db, user.id)),
        # A count only (never who): shown with the library stats the member chose to share.
        friends_brought=friend_invites.friends_brought(db, user.id) if profile.show_stats else 0,
        # Shown with the library stats, never revealing a shelf the member keeps private.
        badges=badges.public_badges(db, user) if profile.show_stats and not user.statistics_private else [],
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
