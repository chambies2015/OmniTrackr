"""Public title pages: which titles get one, and what OmniTrackr knows about each.

A title is identified by its kind, normalized title and year, e.g.
/titles/movie/interstellar-2014. Pages are built on request from the members'
libraries (counts, average rating when enough members rated it, public reviews),
public collections, Release Radar, and cached public facts (title_metadata).
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models
from .editorial_collections import EDITOR_USERNAME
from .review_quality import evaluate_public_review

# URL kind -> (model, review category, library category, label, creator field)
KINDS = {
    "movie": (models.Movie, "movie", "movies", "Movie", "director"),
    "tv": (models.TVShow, "tv_show", "tv-shows", "TV show", None),
    "anime": (models.Anime, "anime", "anime", "Anime", None),
    "game": (models.VideoGame, "video_game", "video-games", "Video game", None),
    "album": (models.Music, "music", "music", "Album", "artist"),
    "book": (models.Book, "book", "books", "Book", "author"),
}
REVIEW_TO_KIND = {review: kind for kind, (_, review, _, _, _) in KINDS.items()}
LIBRARY_TO_KIND = {library: kind for kind, (_, _, library, _, _) in KINDS.items()}
COMPLETE_FIELD = {"movie": "watched", "tv": "watched", "anime": "watched", "game": "played", "album": "listened", "book": "read"}
IMAGE_FIELD = {"movie": "poster_url", "tv": "poster_url", "anime": "poster_url", "game": "cover_art_url",
               "album": "cover_art_url", "book": "cover_art_url"}
MIN_RATINGS_SHOWN = 3
INDEX_MIN_MEMBERS = 3
REVIEW_MIN_CHARS = 80
REVIEW_DETAIL_MIN_CHARS = 240


def normalize(title: str) -> str:
    return " ".join((title or "").strip().casefold().split())


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:120] or "title"


def title_slug(title: str, year: Optional[int]) -> str:
    base = slugify(title)
    return f"{base}-{year}" if year else base


def title_path(kind: str, title: str, year: Optional[int]) -> str:
    return f"/titles/{kind}/{title_slug(title, year)}"


def item_year(kind: str, item) -> Optional[int]:
    if kind == "game":
        return item.release_date.year if getattr(item, "release_date", None) else None
    return getattr(item, "year", None) or None


def path_for_item(kind: str, item) -> str:
    return title_path(kind, item.title or "", item_year(kind, item))


def path_for_review_category(category: str, title: str, year=None, release_date=None) -> Optional[str]:
    kind = REVIEW_TO_KIND.get(category)
    if not kind or not (title or "").strip():
        return None
    if kind == "game" and release_date:
        year = int(str(release_date)[:4]) if str(release_date)[:4].isdigit() else None
    return title_path(kind, title, year)


def _editor_ids(db: Session):
    return db.query(models.User.id).filter(models.User.username == EDITOR_USERNAME)


def _active_ids(db: Session):
    return db.query(models.User.id).filter(models.User.is_active == True)


# A member who made a category private ("not visible to anyone") never feeds that
# category's public pages, counts, or "also track" suggestions.
PRIVATE_FLAG = {"movie": "movies_private", "tv": "tv_shows_private", "anime": "anime_private",
                "game": "video_games_private", "album": "music_private", "book": "books_private"}


def _shareable_ids(db: Session, kind: str):
    flag = getattr(models.User, PRIVATE_FLAG[kind])
    return db.query(models.User.id).filter(models.User.is_active == True, flag == False)


def _visible_rows(db: Session, kind: str, model):
    """Library rows that may appear on public pages: shareable members, plus any review the member chose to publish."""
    from sqlalchemy import or_
    return db.query(model).filter(model.user_id.in_(_active_ids(db))).filter(or_(
        model.user_id.in_(_shareable_ids(db, kind)), model.review_public == True))


@dataclass
class TitleGroup:
    kind: str
    title: str
    year: Optional[int]
    normalized: str
    items: list = field(default_factory=list)

    @property
    def path(self) -> str:
        return title_path(self.kind, self.title, self.year)


def find(db: Session, kind: str, slug: str) -> Optional[TitleGroup]:
    """Every library entry (any member) that this slug names."""
    if kind not in KINDS or not re.fullmatch(r"[a-z0-9-]{1,130}", slug or ""):
        return None
    model = KINDS[kind][0]
    base, separator, year_suffix = slug.rpartition("-")
    candidates_slugs = [(slug, None)]
    if base and separator and len(year_suffix) == 4 and year_suffix.isdigit():
        candidates_slugs.insert(0, (base, int(year_suffix)))
    for base, year in candidates_slugs:
        words = [w for w in base.split("-") if w]
        if not words:
            continue
        query = _visible_rows(db, kind, model)
        longest = max(words, key=len)
        if len(longest) >= 2:
            query = query.filter(func.lower(model.title).contains(longest))
        rows = [row for row in query.limit(2000).all()
                if slugify(row.title or "") == base and item_year(kind, row) == year]
        if not rows and len(longest) >= 2:
            # Accented titles ("Pokémon") don't contain their ASCII slug words; scan without the filter.
            rows = [row for row in _visible_rows(db, kind, model).limit(20000).all()
                    if slugify(row.title or "") == base and item_year(kind, row) == year]
        if rows:
            names = Counter((row.title or "").strip() for row in rows)
            display = names.most_common(1)[0][0]
            return TitleGroup(kind, display, year, normalize(display), rows)
    return None


def _public_reviews(db: Session, kind: str, items: list) -> list[dict]:
    from .routers.reviews import _current_state_hides_review
    _, review_category, _, _, _ = KINDS[kind]
    ids = [item.id for item in items if item.review_public and (item.review or "").strip()]
    items = sorted(items, key=lambda item: -len((item.review or "").strip()))
    if not ids:
        return []
    states = {s.item_id: s for s in db.query(models.PublicReviewState).filter(
        models.PublicReviewState.category == review_category, models.PublicReviewState.item_id.in_(ids)).all()}
    users = {u.id: u for u in db.query(models.User).filter(models.User.id.in_([i.user_id for i in items])).all()}
    reviews = []
    for item in items:
        if item.id not in ids or len((item.review or "").strip()) < REVIEW_MIN_CHARS:
            continue
        user = users.get(item.user_id)
        if user is None or not user.is_active:
            continue
        quality = evaluate_public_review(item.review, REVIEW_MIN_CHARS, REVIEW_DETAIL_MIN_CHARS)
        if not quality.safe or not quality.community_ready or _current_state_hides_review(states.get(item.id), review_category, item):
            continue
        if any(existing["user_id"] == user.id for existing in reviews):
            continue  # One review per member on a title page.
        reviews.append({
            "user_id": user.id,
            "id": item.id, "category": review_category, "username": user.username, "rating": item.rating,
            "review": item.review.strip(), "search_ready": quality.search_ready,
            "url": f"/reviews/{item.id}?category={review_category}",
        })
    reviews.sort(key=lambda r: (not r["search_ready"], -len(r["review"])))
    from .public_profiles import enabled_profile_paths
    profiles = enabled_profile_paths(db, [review["user_id"] for review in reviews])
    for review in reviews:
        review["profile_url"] = profiles.get(review["user_id"])
    return reviews


def _collections_featuring(db: Session, kind: str, items: list) -> list[dict]:
    from .routers.collections import _collection_is_discoverable
    library_category = KINDS[kind][2]
    rows = db.query(models.Collection).join(
        models.CollectionItem, models.CollectionItem.collection_id == models.Collection.id
    ).filter(
        models.Collection.is_public == True,
        models.CollectionItem.category == library_category,
        models.CollectionItem.item_id.in_([item.id for item in items]),
    ).distinct().limit(12).all()
    featured = []
    for collection in rows:
        try:
            if not _collection_is_discoverable(collection, db):
                continue
        except Exception:
            continue
        featured.append({"name": collection.name, "url": f"/collections/public/{collection.id}",
                         "description": (collection.description or "")[:180]})
    return featured[:6]


def _related(db: Session, kind: str, group: TitleGroup, limit: int = 8) -> list[dict]:
    """Titles most often tracked by the same members (any kind), excluding the editors account."""
    shareable = {uid for uid, in _shareable_ids(db, kind).all()}
    member_ids = {item.user_id for item in group.items if item.user_id in shareable}
    editors = {uid for uid, in _editor_ids(db).all()}
    member_ids -= editors
    if len(member_ids) < 2:
        return []
    counts: Counter = Counter()
    samples: dict = {}
    for other_kind, (model, _, _, label, _) in KINDS.items():
        normalized = func.lower(func.trim(model.title))
        rows = db.query(normalized, func.count(func.distinct(model.user_id)), func.min(model.id)).filter(
            model.user_id.in_(member_ids), model.user_id.in_(_shareable_ids(db, other_kind))).group_by(normalized).having(func.count(func.distinct(model.user_id)) >= 2).all()
        for name, members, sample_id in rows:
            if not name or (other_kind == kind and name == group.normalized):
                continue
            counts[(other_kind, name)] = members
            samples[(other_kind, name)] = sample_id
    related = []
    for (other_kind, name), members in counts.most_common(limit * 2):
        model = KINDS[other_kind][0]
        item = db.get(model, samples[(other_kind, name)])
        if item is None:
            continue
        related.append({"kind": other_kind, "label": KINDS[other_kind][3], "title": item.title.strip(),
                        "year": item_year(other_kind, item), "url": path_for_item(other_kind, item),
                        "image": _safe_image(getattr(item, IMAGE_FIELD[other_kind], None)), "shared": members})
        if len(related) >= limit:
            break
    return related


def _safe_image(url) -> Optional[str]:
    if isinstance(url, str) and url.startswith(("https://", "http://")) and url != "N/A" and len(url) < 1000:
        return url
    return None


def summarize(db: Session, group: TitleGroup) -> dict:
    """Member data for a title page (aggregates only, never who tracks it)."""
    kind = group.kind
    editors = {uid for uid, in _editor_ids(db).all()}
    member_items = [item for item in group.items if item.user_id not in editors]
    members = len({item.user_id for item in member_items})
    finished = len({item.user_id for item in member_items if getattr(item, COMPLETE_FIELD[kind], False)})
    # One rating per member even if they saved the title twice.
    per_member: dict = {}
    for item in sorted(member_items, key=lambda entry: entry.id):
        if item.rating is not None:
            per_member[item.user_id] = item.rating
    ratings = list(per_member.values())
    average = round(sum(ratings) / len(ratings), 1) if len(ratings) >= MIN_RATINGS_SHOWN else None
    creator_field = KINDS[kind][4]
    creator = None
    if creator_field:
        names = Counter((getattr(item, creator_field) or "").strip() for item in group.items if getattr(item, creator_field, None))
        creator = names.most_common(1)[0][0] if names else None
    images = Counter(_safe_image(getattr(item, IMAGE_FIELD[kind], None)) for item in group.items)
    images.pop(None, None)
    reviews = _public_reviews(db, kind, group.items)
    return {
        "members": members,
        "finished": finished,
        "rated": len(ratings),
        "average_rating": average,
        "creator": creator,
        "image": images.most_common(1)[0][0] if images else None,
        "reviews": reviews,
        "search_ready_reviews": sum(1 for review in reviews if review["search_ready"]),
        "collections": _collections_featuring(db, kind, group.items),
        "related": _related(db, kind, group),
    }


def is_indexable(summary: dict, metadata: Optional[dict]) -> bool:
    """Only pages with real substance are offered to search engines."""
    if summary["search_ready_reviews"] >= 1:
        return True
    has_description = bool(metadata and metadata.get("description"))
    if has_description and summary["reviews"]:
        return True
    if has_description and summary["members"] >= INDEX_MIN_MEMBERS:
        return True
    return has_description and bool(summary["collections"])


def popular(db: Session, kind: str, limit: int = 24, min_members: int = 2) -> list[dict]:
    """Titles tracked by the most members, for the /titles index and the sitemap."""
    model = KINDS[kind][0]
    normalized = func.lower(func.trim(model.title))
    members = func.count(func.distinct(model.user_id))
    rows = db.query(normalized, members, func.min(model.id)).filter(
        model.user_id.in_(_shareable_ids(db, kind)), ~model.user_id.in_(_editor_ids(db)),
    ).group_by(normalized).having(members >= min_members).order_by(members.desc(), normalized).limit(limit).all()
    results = []
    for name, count, sample_id in rows:
        item = db.get(model, sample_id)
        if item is None or not (item.title or "").strip():
            continue
        results.append({"kind": kind, "label": KINDS[kind][3], "title": item.title.strip(),
                        "year": item_year(kind, item), "url": path_for_item(kind, item), "members": int(count),
                        "image": _safe_image(getattr(item, IMAGE_FIELD[kind], None)), "normalized": name})
    return results


def reviewed_titles(db: Session, limit: int = 300) -> list[dict]:
    """Titles with at least one search-ready public review."""
    results = []
    for kind, (model, review_category, _, label, _) in KINDS.items():
        rows = db.query(model).filter(
            model.user_id.in_(_active_ids(db)), model.review_public == True, model.review.isnot(None),
            func.length(func.trim(model.review)) >= REVIEW_DETAIL_MIN_CHARS,
        ).limit(limit).all()
        seen = set()
        for item in rows:
            if not (item.title or "").strip():
                continue
            if not evaluate_public_review(item.review, REVIEW_MIN_CHARS, REVIEW_DETAIL_MIN_CHARS).search_ready:
                continue
            path = path_for_item(kind, item)
            if path in seen:
                continue
            seen.add(path)
            results.append({"kind": kind, "title": item.title.strip(), "year": item_year(kind, item), "url": path})
    return results
