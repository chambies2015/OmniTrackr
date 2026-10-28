"""Public title pages: which titles get one, and what OmniTrackr knows about each.

A title is identified by its kind, normalized title and year, e.g.
/titles/movie/interstellar-2014. Pages are built on request from the members'
libraries (counts, average rating when enough members rated it, public reviews),
public collections, Release Radar, and cached public facts (title_metadata).
"""
from __future__ import annotations

import os
import re
import threading
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, event, func, or_
from sqlalchemy.orm import Session

from . import models
from .editorial_collections import EDITOR_USERNAME
from .review_quality import AD_MIN_REVIEW_WORDS, evaluate_public_review, word_count

# URL kind -> (model, review category, library category, label, creator field)
KINDS = {
    "movie": (models.Movie, "movie", "movies", "Movie", "director"),
    "tv": (models.TVShow, "tv_show", "tv-shows", "TV show", None),
    "anime": (models.Anime, "anime", "anime", "Anime", None),
    "game": (models.VideoGame, "video_game", "video-games", "Video game", None),
    "album": (models.Music, "music", "music", "Album", "artist"),
    "book": (models.Book, "book", "books", "Book", "author"),
    "manga": (models.Manga, "manga", "manga", "Manga", "author"),
    "podcast": (models.Podcast, "podcast", "podcasts", "Podcast", "host"),
}
REVIEW_TO_KIND = {review: kind for kind, (_, review, _, _, _) in KINDS.items()}
LIBRARY_TO_KIND = {library: kind for kind, (_, _, library, _, _) in KINDS.items()}
COMPLETE_FIELD = {"movie": "watched", "tv": "watched", "anime": "watched", "game": "played", "album": "listened", "book": "read", "manga": "read", "podcast": "listened"}
IMAGE_FIELD = {"movie": "poster_url", "tv": "poster_url", "anime": "poster_url", "game": "cover_art_url",
               "album": "cover_art_url", "book": "cover_art_url", "manga": "cover_art_url",
               "podcast": "cover_art_url"}
MIN_RATINGS_SHOWN = 3
SPREAD_MIN_RATINGS = 5  # A breakdown of three ratings would all but show each member's score.
# (label, lowest rating in the band), highest band first; ratings are out of 10.
RATING_BANDS = (("9 to 10", 9.0), ("8 to 8.9", 8.0), ("7 to 7.9", 7.0), ("5 to 6.9", 5.0), ("Below 5", 0.0))
INDEX_MIN_MEMBERS = 3
RECENT_DAYS = 30
RECENT_MIN_MEMBERS = 2  # "1 member added it this month" points at one person; wait for two.
REVIEW_MIN_CHARS = 80
REVIEW_DETAIL_MIN_CHARS = 240


def normalize(title: str) -> str:
    return " ".join((title or "").strip().casefold().split())


@lru_cache(maxsize=16384)
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
                "game": "video_games_private", "album": "music_private", "book": "books_private",
                "manga": "manga_private", "podcast": "podcasts_private"}


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


# ---------------------------------------------------------------- slug index

SLUG_INDEX_REBUILD_SECONDS = 30 * 60


def _year_column(kind: str, model):
    return model.release_date if kind == "game" else model.year


def _row_year(kind: str, value) -> Optional[int]:
    if kind == "game":
        return value.year if value else None
    return value or None


class SlugIndex:
    """Which stored titles give each (title slug, year), per kind, kept in memory.

    Matching a slug used to read every title of a kind and slugify it on each lookup:
    a third of a second for one mistyped link, a second for the friends feed and most
    of the sitemap's minute. With the index, a lookup asks the database for rows with
    those exact titles (the title column is indexed). The titles are only candidates:
    rows are still read through _visible_rows() and their slugs compared again, so a
    stale entry can never put the wrong row on a page, and privacy and deactivation
    apply at once.

    New rows are read from the highest id seen. Renames and year edits saved through
    this process are noted as they flush (see _note_library_flush). Anything else, such
    as another process or a hand edit, shows up at the next rebuild.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._kinds: dict = {}

    def clear(self) -> None:
        with self._lock:
            self._kinds.clear()

    @staticmethod
    def _add(entry: dict, kind: str, title, year_value) -> None:
        if title is not None:
            entry["pairs"].setdefault((slugify(title), _row_year(kind, year_value)), set()).add(title)

    def _build(self, db: Session, kind: str, top: int) -> dict:
        model = KINDS[kind][0]
        entry = {"pairs": {}, "max_id": top, "built": time.monotonic()}
        for title, year_value in (db.query(model.title, _year_column(kind, model))
                                  .filter(model.id <= top).distinct()):
            self._add(entry, kind, title, year_value)
        return entry

    def titles(self, db: Session, kind: str, pairs) -> dict[tuple, set]:
        model = KINDS[kind][0]
        with self._lock:
            entry = self._kinds.get(kind)
            top = db.query(func.max(model.id)).scalar() or 0
            if (entry is None or time.monotonic() - entry["built"] >= SLUG_INDEX_REBUILD_SECONDS
                    or top < entry["max_id"]):
                # The table shrank at the top (a deleted newest row, or a different database): start over.
                entry = self._kinds[kind] = self._build(db, kind, top)
            elif top > entry["max_id"]:
                for title, year_value in (db.query(model.title, _year_column(kind, model))
                                          .filter(model.id > entry["max_id"], model.id <= top)):
                    self._add(entry, kind, title, year_value)
                entry["max_id"] = top
            return {pair: set(entry["pairs"][pair]) for pair in pairs if pair in entry["pairs"]}

    def note(self, kind: str, title: Optional[str], year: Optional[int]) -> None:
        with self._lock:
            entry = self._kinds.get(kind)
            if entry is not None and title is not None:
                entry["pairs"].setdefault((slugify(title), year), set()).add(title)


SLUG_INDEX = SlugIndex()
_KIND_BY_MODEL = {model: kind for kind, (model, _, _, _, _) in KINDS.items()}


@event.listens_for(Session, "after_flush")
def _note_library_flush(session: Session, flush_context) -> None:
    """Index new and edited library titles as soon as they are saved."""
    try:
        for obj in list(session.new) + list(session.dirty):
            kind = _KIND_BY_MODEL.get(type(obj))
            if kind is not None:
                SLUG_INDEX.note(kind, obj.title, item_year(kind, obj))
    except Exception:
        pass  # The index is a shortcut; a failure here must never stop a save.


def _candidate_rows(db: Session, kind: str, pairs, column, grouped: bool = False):
    """(pair, title, column) for the visible rows with a title the index lists for these pairs.

    grouped=True gives one row per stored title and year, with `column` an aggregate.
    """
    titles = SLUG_INDEX.titles(db, kind, pairs)
    wanted = sorted({title for found in titles.values() for title in found})
    model = KINDS[kind][0]
    year_column = _year_column(kind, model)
    for start in range(0, len(wanted), 500):
        query = (_visible_rows(db, kind, model).with_entities(model.title, year_column, column)
                 .filter(model.title.in_(wanted[start:start + 500])))
        query = query.group_by(model.title, year_column) if grouped else query.order_by(model.id)
        for title, year_value, value in query:
            pair = (slugify(title or ""), _row_year(kind, year_value))
            if pair in titles:
                yield pair, title, value


def _matching_rows(db: Session, kind: str, pairs) -> dict[tuple, list[tuple[int, str]]]:
    """(id, title) of the visible rows whose title and year give each (slug, year) pair, oldest first."""
    found: dict = {}
    for pair, title, row_id in _candidate_rows(db, kind, pairs, KINDS[kind][0].id):
        found.setdefault(pair, []).append((row_id, title))
    return {pair: sorted(rows) for pair, rows in found.items()}


def find(db: Session, kind: str, slug: str) -> Optional[TitleGroup]:
    """Every library entry (any member) that this slug names."""
    if kind not in KINDS or not re.fullmatch(r"[a-z0-9-]{1,130}", slug or ""):
        return None
    model = KINDS[kind][0]
    pairs = _slug_candidates(slug)
    matches = _matching_rows(db, kind, pairs)
    for pair in pairs:
        if matches.get(pair):
            rows = db.query(model).filter(model.id.in_([row_id for row_id, _ in matches[pair]])).order_by(model.id).all()
            if rows:
                names = Counter((row.title or "").strip() for row in rows)
                display = names.most_common(1)[0][0]
                return TitleGroup(kind, display, pair[1], normalize(display), rows)
    return None


def _slug_candidates(slug: str) -> list[tuple[str, Optional[int]]]:
    """The (title slug, year) pairs a URL slug can name, in the order find() tries them."""
    base, separator, year_suffix = slug.rpartition("-")
    pairs = [(slug, None)]
    if base and separator and len(year_suffix) == 4 and year_suffix.isdigit():
        pairs.insert(0, (base, int(year_suffix)))
    return [(base, year) for base, year in pairs if any(base.split("-"))]


def find_many(db: Session, kind: str, slugs, reviewed_only: bool = False) -> dict[str, TitleGroup]:
    """find() for many slugs of one kind, reading titles and years once instead of once per slug.

    The sitemap checks hundreds of titles; one find() each scanned the library tables
    hundreds of times. reviewed_only=True puts only the rows with a public review long
    enough to be search-ready in each group, which is all is_indexable() looks at; a
    popular title otherwise loads thousands of whole rows only to count them. Which
    title a slug names is still decided from every row, as find() does.
    """
    if kind not in KINDS:
        return {}
    plans = {slug: _slug_candidates(slug) for slug in dict.fromkeys(slugs)
             if re.fullmatch(r"[a-z0-9-]{1,130}", slug or "")}
    wanted = {pair for pairs in plans.values() for pair in pairs}
    if not wanted:
        return {}
    model = KINDS[kind][0]
    ids_by_pair = {pair: [row_id for row_id, _ in rows] for pair, rows in _matching_rows(db, kind, wanted).items()}
    load = {row_id for ids in ids_by_pair.values() for row_id in ids}
    if reviewed_only and load:
        # SQL trim() strips only spaces, so this flags every row Python's strip() would pass.
        reviewed = and_(model.review_public == True, func.length(func.trim(model.review)) >= REVIEW_DETAIL_MIN_CHARS)
        ordered, load = sorted(load), set()
        for start in range(0, len(ordered), 1000):
            load.update(row_id for row_id, in db.query(model.id).filter(
                model.id.in_(ordered[start:start + 1000]), reviewed))
    needed = sorted(load)
    rows_by_id = {}
    for start in range(0, len(needed), 1000):
        chunk = needed[start:start + 1000]
        rows_by_id.update({row.id: row for row in db.query(model).filter(model.id.in_(chunk))})
    groups = {}
    for slug, pairs in plans.items():
        for pair in pairs:
            rows = [rows_by_id[row_id] for row_id in ids_by_pair.get(pair, ()) if row_id in rows_by_id]
            if reviewed_only and pair in ids_by_pair and not rows:
                break  # The slug names this title, which has no search-ready review.
            if rows:
                names = Counter((row.title or "").strip() for row in rows)
                display = names.most_common(1)[0][0]
                groups[slug] = TitleGroup(kind, display, pair[1], normalize(display), rows)
                break
    return groups


def paths_many(db: Session, kind: str, slugs) -> dict[str, str]:
    """The title page path each slug leads to, like find_many() but without loading the library rows.

    The friends feed links every card to its title page; a popular title's group is
    thousands of rows, and the feed only needs to know the page exists. Every title in a
    group slugifies the same way, so the path follows from the matched (slug, year).
    """
    if kind not in KINDS:
        return {}
    plans = {slug: _slug_candidates(slug) for slug in dict.fromkeys(slugs)
             if re.fullmatch(r"[a-z0-9-]{1,130}", slug or "")}
    found = {pair for pair, _, _ in _candidate_rows(db, kind, {pair for pairs in plans.values() for pair in pairs},
                                                    func.count(), grouped=True)}
    paths = {}
    for slug, pairs in plans.items():
        for base, year in pairs:
            if (base, year) in found:
                paths[slug] = f"/titles/{kind}/{base}-{year}" if year else f"/titles/{kind}/{base}"
                break
    return paths


def _public_reviews(db: Session, kind: str, items: list, decorate: bool = True) -> list[dict]:
    """Public reviews among `items`, best first.

    decorate=False leaves out helpful counts, profile links, supporter badges and spoiler
    flags (four more queries) for callers that only count the reviews, like the sitemap.
    """
    from .routers.reviews import _current_state_hides_review
    _, review_category, _, _, _ = KINDS[kind]
    ids = [item.id for item in items if item.review_public and (item.review or "").strip()]
    items = sorted(items, key=lambda item: -len((item.review or "").strip()))
    if not ids:
        return []
    states = {s.item_id: s for s in db.query(models.PublicReviewState).filter(
        models.PublicReviewState.category == review_category, models.PublicReviewState.item_id.in_(ids)).all()}
    # Only the reviewers: a popular title has thousands of rows but a handful of public reviews.
    reviewer_ids = {item.user_id for item in items if item.review_public and (item.review or "").strip()}
    users = {u.id: u for u in db.query(models.User).filter(models.User.id.in_(reviewer_ids)).all()}
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
    if not decorate:
        return reviews
    if reviews:
        # Readers' "helpful" marks lead the page; ties keep the longer, standalone reviews first.
        from .routers.reviews import review_helpful_counts
        counts = review_helpful_counts(db, [(review_category, r["id"]) for r in reviews])
        for review in reviews:
            review["helpful"] = counts.get((review_category, review["id"]), 0)
        reviews.sort(key=lambda r: -r["helpful"])
    from .public_profiles import enabled_profile_paths
    profiles = enabled_profile_paths(db, [review["user_id"] for review in reviews])
    from .supporters import public_badges
    badges = public_badges(db, [review["user_id"] for review in reviews])
    from .review_spoilers import attach
    attach(db, reviews)
    for review in reviews:
        review["profile_url"] = profiles.get(review["user_id"])
        review["supporter"] = badges.get(review["user_id"])
    return reviews


def _collections_featuring(db: Session, kind: str, items: list) -> list[dict]:
    from sqlalchemy.orm import selectinload
    from .routers.collections import _collection_is_discoverable, _media_lookup_for_collections
    library_category = KINDS[kind][2]
    rows = db.query(models.Collection).options(selectinload(models.Collection.items)).join(
        models.CollectionItem, models.CollectionItem.collection_id == models.Collection.id
    ).filter(
        models.Collection.is_public == True,
        models.CollectionItem.category == library_category,
        models.CollectionItem.item_id.in_([item.id for item in items]),
    ).distinct().limit(12).all()
    # Each check reads the collection's titles; look them all up at once, not one query per title.
    try:
        media = _media_lookup_for_collections(db, rows)
    except Exception:
        media = None
    featured = []
    for collection in rows:
        try:
            if not _collection_is_discoverable(collection, db, media):
                continue
        except Exception:
            continue
        featured.append({"name": collection.name, "url": f"/collections/public/{collection.id}",
                         "description": (collection.description or "")[:180]})
    return featured[:6]


# "Also tracked" and "more by" read most of the library for a popular title (a fifth of a
# second each). They shift slowly, so each title's lists are kept for a few minutes.
SECTION_CACHE_SECONDS = 10 * 60
SECTION_CACHE_SIZE = 2000
_section_cache: dict = {}
_section_lock = threading.Lock()


def _section_cache_enabled() -> bool:
    # Tests change data between requests and expect the page to follow at once.
    return os.getenv("TESTING", "").lower() != "true"


def clear_section_cache() -> None:
    with _section_lock:
        _section_cache.clear()


def _cached_section(key: tuple, build) -> list[dict]:
    if not _section_cache_enabled():
        return build()
    now = time.monotonic()
    with _section_lock:
        hit = _section_cache.get(key)
    if hit is not None and now - hit[0] < SECTION_CACHE_SECONDS:
        return [dict(entry) for entry in hit[1]]
    value = build()
    with _section_lock:
        if len(_section_cache) >= SECTION_CACHE_SIZE:
            _section_cache.clear()
        _section_cache[key] = (now, value)
    return [dict(entry) for entry in value]


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
    top = counts.most_common(limit * 2)
    wanted: dict = {}
    for key, _ in top:
        wanted.setdefault(key[0], []).append(samples[key])
    loaded = {}
    for other_kind, ids in wanted.items():
        model = KINDS[other_kind][0]
        loaded.update({(other_kind, item.id): item for item in db.query(model).filter(model.id.in_(ids))})
    related = []
    for (other_kind, name), members in top:
        item = loaded.get((other_kind, samples[(other_kind, name)]))
        if item is None:
            continue
        related.append({"kind": other_kind, "label": KINDS[other_kind][3], "title": item.title.strip(),
                        "year": item_year(other_kind, item), "url": path_for_item(other_kind, item),
                        "image": _safe_image(getattr(item, IMAGE_FIELD[other_kind], None)), "shared": members})
        if len(related) >= limit:
            break
    return related


def more_from_creator(db: Session, kind: str, creator: str, exclude: str, limit: int = 8) -> list[dict]:
    """Other titles by the same director, artist or author that members track, most tracked first."""
    creator_field = KINDS[kind][4]
    name = " ".join((creator or "").split()).casefold()
    if not creator_field or not name:
        return []
    model = KINDS[kind][0]
    normalized = func.lower(func.trim(model.title))
    members = func.count(func.distinct(model.user_id))
    try:
        rows = db.query(normalized, members, func.min(model.id)).filter(
            func.lower(func.trim(getattr(model, creator_field))) == name,
            model.user_id.in_(_shareable_ids(db, kind)), ~model.user_id.in_(_editor_ids(db)),
        ).group_by(normalized).order_by(members.desc(), normalized).limit(limit + 1).all()
    except Exception:
        db.rollback()
        return []
    ids = [sample_id for title, _, sample_id in rows if title and title != exclude][:limit]
    loaded = {item.id: item for item in db.query(model).filter(model.id.in_(ids))} if ids else {}
    results = []
    for sample_id in ids:
        item = loaded.get(sample_id)
        if item is None or not (item.title or "").strip():
            continue
        results.append({"kind": kind, "label": KINDS[kind][3], "title": item.title.strip(),
                        "year": item_year(kind, item), "url": path_for_item(kind, item),
                        "image": _safe_image(getattr(item, IMAGE_FIELD[kind], None))})
    return results


def _safe_image(url) -> Optional[str]:
    if isinstance(url, str) and url.startswith(("https://", "http://")) and url != "N/A" and len(url) < 1000:
        return url
    return None


def summarize(db: Session, group: TitleGroup, *, page_sections: bool = True) -> dict:
    """Member data for a title page (aggregates only, never who tracks it).

    page_sections=False skips the collections and "also tracked" lists and the review
    decorations (helpful counts, profile links, badges, spoiler flags), which only the
    page itself shows. The sitemap checks hundreds of titles and needs none of them.
    """
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
    reviews = _public_reviews(db, kind, group.items, decorate=page_sections)
    since = datetime.utcnow() - timedelta(days=RECENT_DAYS)
    recent = len({item.user_id for item in member_items if getattr(item, "added_at", None) and item.added_at >= since})
    return {
        "members": members,
        "finished": finished,
        "rated": len(ratings),
        "average_rating": average,
        "spread": rating_spread(ratings),
        "creator": creator,
        "image": images.most_common(1)[0][0] if images else None,
        "reviews": reviews,
        "search_ready_reviews": sum(1 for review in reviews if review["search_ready"]),
        "collections": _collections_featuring(db, kind, group.items) if page_sections else [],
        "related": _cached_section(("related", group.path), lambda: _related(db, kind, group)) if page_sections else [],
        "recent_members": recent if recent >= RECENT_MIN_MEMBERS else 0,
        "by_creator": (_cached_section(("creator", group.path, creator),
                                       lambda: more_from_creator(db, kind, creator, group.normalized))
                       if page_sections and creator else []),
    }


def rating_spread(ratings: list) -> Optional[list[dict]]:
    """How member ratings split across RATING_BANDS, once enough members have rated."""
    if len(ratings) < SPREAD_MIN_RATINGS:
        return None
    counts = Counter()
    for rating in ratings:
        for label, low in RATING_BANDS:
            if rating >= low:
                counts[label] += 1
                break
        else:
            counts[RATING_BANDS[-1][0]] += 1
    return [{"label": label, "count": counts[label], "percent": round(100 * counts[label] / len(ratings))}
            for label, _ in RATING_BANDS]


def member_words(summary: dict) -> int:
    """Words of original member writing on the page: search-ready public reviews only."""
    return sum(word_count(review["review"]) for review in summary["reviews"] if review["search_ready"])


def is_indexable(summary: dict, metadata: Optional[dict]) -> bool:
    """Offered to search engines (and eligible for ads) only with original member writing.

    Facts and descriptions borrowed from Wikipedia, TVmaze and others are useful to
    visitors but aren't ours; a page needs enough public member review text to carry it
    before it counts as OmniTrackr content (AdSense "low value content"). Since Oct 27
    that is the same 150 words that index a standalone review page: one 40-word review
    under a borrowed description and a list of streaming links is mostly someone else's
    page. Shorter reviews still show on the page; it just stays out of search.
    """
    return summary["search_ready_reviews"] >= 1 and member_words(summary) >= AD_MIN_REVIEW_WORDS


def is_ad_eligible(summary: dict, metadata: Optional[dict]) -> bool:
    """Ads go only on pages search engines are offered: enough member writing to carry the page."""
    return is_indexable(summary, metadata)


def popular(db: Session, kind: str, limit: int = 24, min_members: int = 2) -> list[dict]:
    """Titles tracked by the most members, for the /titles index and the sitemap."""
    model = KINDS[kind][0]
    normalized = func.lower(func.trim(model.title))
    members = func.count(func.distinct(model.user_id))
    rows = db.query(normalized, members, func.min(model.id)).filter(
        model.user_id.in_(_shareable_ids(db, kind)), ~model.user_id.in_(_editor_ids(db)),
    ).group_by(normalized).having(members >= min_members).order_by(members.desc(), normalized).limit(limit).all()
    samples = {}
    sample_ids = [sample_id for _, _, sample_id in rows]
    for start in range(0, len(sample_ids), 1000):
        samples.update({item.id: item for item in db.query(model).filter(model.id.in_(sample_ids[start:start + 1000]))})
    results = []
    for name, count, sample_id in rows:
        item = samples.get(sample_id)
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
