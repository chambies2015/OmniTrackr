"""Taste Match: how two friends' libraries line up.

Read-only and privacy-aware:
- the friend's categories they marked private are never read, counted or listed,
- the viewer's own library is read in full (only the viewer sees the result),
- only titles, years, creators and artwork are shown; the friend's reviews never are.

Titles are matched within a category by their normalized name (case, punctuation
and a leading "The/A/An" ignored). When both entries carry a year more than a
year apart they are treated as different works (remakes, reboots).
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session, load_only

from . import models
from .for_you import CREATOR_FIELD, IMAGE_FIELD, LIBRARY, PRIVATE_FLAG, _safe_image, normalize_title

LABELS = {"movies": "Movies", "tv-shows": "TV shows", "anime": "Anime", "video-games": "Games",
          "music": "Albums", "books": "Books", "manga": "Manga", "podcasts": "Podcasts"}
ITEM_LABELS = {"movies": "Movie", "tv-shows": "TV show", "anime": "Anime", "video-games": "Game",
               "music": "Album", "books": "Book", "manga": "Manga", "podcasts": "Podcast"}
DONE_FIELD = {"movies": "watched", "tv-shows": "watched", "anime": "watched", "video-games": "played",
              "music": "listened", "books": "read", "manga": "read", "podcasts": "listened"}
MIN_RATED = 3          # shared titles both rated before a score is shown
LOVED = 8.0            # a rating this high counts as a favorite
DISAGREE = 3.0         # rating gap that counts as a real disagreement
FULL_MISS = 5.0        # a gap this large scores zero agreement
LIST_LIMIT = 6
FRIENDS_LIMIT = 100
TIERS = ((85, "Taste twins"), (70, "Great match"), (55, "Good match"), (40, "Some common ground"),
         (0, "Opposites attract"))


def _year(category: str, entry) -> Optional[int]:
    if category == "video-games":
        released = getattr(entry, "release_date", None)
        return released.year if released else None
    value = getattr(entry, "year", None)
    return value if isinstance(value, int) and value > 0 else None


def _row(category: str, entry) -> dict[str, Any]:
    creator_field = CREATOR_FIELD.get(category)
    return {
        "category": category,
        "label": ITEM_LABELS[category],
        "title": (entry.title or "").strip(),
        "year": _year(category, entry),
        "creator": (getattr(entry, creator_field, None) or None) if creator_field else None,
        "image": _safe_image(getattr(entry, IMAGE_FIELD[category], None)),
        "rating": entry.rating,
        "done": bool(getattr(entry, DONE_FIELD[category], False)),
    }


def _columns(category: str) -> list:
    """Only what _row() reads; reviews and notes can be long and are never shown."""
    model = LIBRARY[category][0]
    names = {"user_id", "title", "rating", DONE_FIELD[category], IMAGE_FIELD[category],
             "release_date" if category == "video-games" else "year"}
    if CREATOR_FIELD.get(category):
        names.add(CREATOR_FIELD[category])
    return [getattr(model, name) for name in sorted(names)]


def libraries(db: Session, categories_by_user: dict[int, Iterable[str]]) -> dict[int, dict[str, dict[str, dict]]]:
    """library() for several members, with one query per category instead of one per member and category."""
    result: dict[int, dict[str, dict[str, dict]]] = {user_id: {} for user_id in categories_by_user}
    for category in LIBRARY:
        user_ids = [user_id for user_id, categories in categories_by_user.items() if category in categories]
        if not user_ids:
            continue
        for user_id in user_ids:
            result[user_id][category] = {}
        model = LIBRARY[category][0]
        for start in range(0, len(user_ids), 500):
            chunk = user_ids[start:start + 500]
            for entry in (db.query(model).options(load_only(*_columns(category)))
                          .filter(model.user_id.in_(chunk)).order_by(model.user_id, model.id)):
                key = normalize_title(entry.title)
                if not key:
                    continue
                rows = result[entry.user_id][category]
                row = _row(category, entry)
                if key not in rows or (rows[key]["rating"] is None and row["rating"] is not None):
                    rows[key] = row
    # Keep each member's categories in the order asked for, as library() did.
    return {user_id: {category: result[user_id][category] for category in categories if category in result[user_id]}
            for user_id, categories in categories_by_user.items()}


def library(db: Session, user_id: int, categories: Iterable[str]) -> dict[str, dict[str, dict]]:
    """category -> normalized title -> one row per title (a rated duplicate wins)."""
    categories = list(categories)
    return libraries(db, {user_id: categories})[user_id]


def shared_categories(friend: models.User) -> list[str]:
    return [category for category in LIBRARY if not getattr(friend, PRIVATE_FLAG[category], False)]


def _same_work(mine: dict, theirs: dict) -> bool:
    return not (mine["year"] and theirs["year"] and abs(mine["year"] - theirs["year"]) > 1)


def _public(row: dict, **extra) -> dict:
    data = {key: row[key] for key in ("category", "label", "title", "year", "creator", "image")}
    data.update(extra)
    return data


def tier(score: Optional[int]) -> Optional[str]:
    if score is None:
        return None
    return next(label for floor, label in TIERS if score >= floor)


def compare(mine: dict[str, dict[str, dict]], theirs: dict[str, dict[str, dict]], categories: list[str]) -> dict:
    """The match between the viewer's library and the friend's visible categories."""
    shared, rated = [], []
    per_category = []
    for category in categories:
        their_rows = theirs.get(category, {})
        my_rows = mine.get(category, {})
        count = 0
        for key, their_row in their_rows.items():
            my_row = my_rows.get(key)
            if my_row is None or not _same_work(my_row, their_row):
                continue
            count += 1
            shared.append((my_row, their_row))
            if my_row["rating"] is not None and their_row["rating"] is not None:
                rated.append((my_row, their_row))
        per_category.append({"category": category, "label": LABELS[category], "shared": count,
                             "yours": len(my_rows), "theirs": len(their_rows)})

    score = None
    if len(rated) >= MIN_RATED:
        agreement = sum(max(0.0, 1 - abs(a["rating"] - b["rating"]) / FULL_MISS) for a, b in rated) / len(rated)
        score = round(agreement * 100)

    both_loved = sorted(
        ((a, b) for a, b in rated if a["rating"] >= LOVED and b["rating"] >= LOVED),
        key=lambda pair: (-(pair[0]["rating"] + pair[1]["rating"]), pair[0]["title"].casefold()),
    )
    disagreements = sorted(
        ((a, b) for a, b in rated if abs(a["rating"] - b["rating"]) >= DISAGREE),
        key=lambda pair: (-abs(pair[0]["rating"] - pair[1]["rating"]), pair[0]["title"].casefold()),
    )
    def favorites(rows_by_category, categories_to_read, other):
        picks = []
        for category in categories_to_read:
            for key, row in rows_by_category.get(category, {}).items():
                if row["rating"] is None or row["rating"] < LOVED:
                    continue
                twin = other.get(category, {}).get(key)
                if twin is None or not _same_work(row, twin):
                    picks.append(row)
        picks.sort(key=lambda row: (-row["rating"], row["title"].casefold()))
        return picks[:LIST_LIMIT]

    return {
        "score": score,
        "tier": tier(score),
        "shared_count": len(shared),
        "rated_count": len(rated),
        "needed_for_score": max(0, MIN_RATED - len(rated)),
        "categories": per_category,
        "both_loved": [_public(a, your_rating=a["rating"], their_rating=b["rating"]) for a, b in both_loved[:LIST_LIMIT]],
        "disagreements": [_public(a, your_rating=a["rating"], their_rating=b["rating"]) for a, b in disagreements[:3]],
        # Their favorites the viewer hasn't tracked, and the viewer's favorites missing from the friend's visible shelves.
        "their_picks": [_public(row, their_rating=row["rating"]) for row in favorites(theirs, categories, mine)],
        "your_picks": [_public(row, your_rating=row["rating"]) for row in favorites(mine, categories, theirs)],
    }


def match(db: Session, viewer: models.User, friend: models.User) -> dict:
    categories = shared_categories(friend)
    mine = library(db, viewer.id, LIBRARY)
    theirs = library(db, friend.id, categories)
    result = compare(mine, theirs, categories)
    result["friend"] = {"id": friend.id, "username": friend.username}
    result["private_categories"] = [LABELS[c] for c in LIBRARY if c not in categories]
    return result


def friend_scores(db: Session, viewer: models.User, friends: list[models.User]) -> list[dict]:
    """A compact score for each friend, for the friends list."""
    mine = library(db, viewer.id, LIBRARY)
    friends = friends[:FRIENDS_LIMIT]
    theirs = libraries(db, {friend.id: shared_categories(friend) for friend in friends})
    scores = []
    for friend in friends:
        categories = shared_categories(friend)
        result = compare(mine, theirs[friend.id], categories)
        scores.append({"friend_id": friend.id, "score": result["score"], "tier": result["tier"],
                       "shared_count": result["shared_count"]})
    return scores


def find_friend_entry(db: Session, friend: models.User, category: str, title: str):
    """The friend's entry for a title in a category they share, or None."""
    if category not in shared_categories(friend):
        return None
    key = normalize_title(title)
    if not key:
        return None
    model = LIBRARY[category][0]
    matches = [entry for entry in db.query(model).filter(model.user_id == friend.id).all()
               if normalize_title(entry.title) == key]
    return matches[0] if matches else None


def find_own_entry(db: Session, user_id: int, category: str, title: str):
    key = normalize_title(title)
    model = LIBRARY[category][0]
    for entry in db.query(model).filter(model.user_id == user_id).all():
        if normalize_title(entry.title) == key:
            return entry
    return None


def copy_payload(category: str, entry) -> dict:
    """Public details only: never the friend's rating, review, status or notes."""
    fields = LIBRARY[category][1]
    payload = {field: getattr(entry, field, None) for field in fields}
    image_field = IMAGE_FIELD[category]
    payload[image_field] = _safe_image(payload.get(image_field))
    if category == "video-games" and payload.get("rawg_link"):
        payload["rawg_link"] = _safe_image(payload["rawg_link"])
    return payload
