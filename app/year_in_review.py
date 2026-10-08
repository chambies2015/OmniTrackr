"""Year in Review: a member's year in media, built only from dates we actually recorded.

Sources, all private to the member until they choose to share:
- activity journal entries (finished, started, notes) by ``occurred_at``,
- completion moments (favorites and ratings at the moment of finishing),
- library ``added_at`` dates, which only exist for items added after add-date
  tracking began, so the first tracked year is labelled as partial.

A shared recap is a frozen snapshot: categories the member marked private are
left out, and notes, reviews and journal text are never included.
"""
from __future__ import annotations

import secrets
from datetime import date, datetime
from typing import Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from . import models

# Library category -> (model, plural label, done field, completion verb, privacy flag on the user)
CATEGORIES = {
    "movies": (models.Movie, "Movies", "watched", "watched", "movies_private"),
    "tv-shows": (models.TVShow, "TV shows", "watched", "watched", "tv_shows_private"),
    "anime": (models.Anime, "Anime", "watched", "watched", "anime_private"),
    "video-games": (models.VideoGame, "Games", "played", "played", "video_games_private"),
    "music": (models.Music, "Albums", "listened", "listened to", "music_private"),
    "books": (models.Book, "Books", "read", "read", "books_private"),
}
# Add dates were first recorded in October 2026; earlier items have none.
ADD_DATES_FIRST_YEAR = 2026
TOP_FINISHES_LIMIT = 5
FAVORITES_LIMIT = 6


def season_year(today: Optional[date] = None) -> Optional[int]:
    """The recap year to promote in the app: December for this year, January for last year."""
    today = today or datetime.utcnow().date()
    if today.month == 12:
        return today.year
    if today.month == 1:
        return today.year - 1
    return None


def available_years(user: models.User, today: Optional[date] = None) -> list[int]:
    today = today or datetime.utcnow().date()
    first = max(user.created_at.year if user.created_at else today.year, 2020)
    return list(range(today.year, first - 1, -1))


def _visible(user: models.User, public: bool) -> list[str]:
    return [key for key, details in CATEGORIES.items() if not (public and getattr(user, details[4], False))]


def _title_key(category: str, item_id, title: str) -> tuple:
    return (category, item_id) if item_id is not None else (category, " ".join((title or "").lower().split()))


def build(db: Session, user: models.User, year: int, *, public: bool = False) -> dict:
    """The recap for one calendar year (UTC). ``public`` drops categories the member keeps private."""
    start, end = datetime(year, 1, 1), datetime(year + 1, 1, 1)
    visible = _visible(user, public)

    entries = db.query(models.ActivityEntry).filter(
        models.ActivityEntry.user_id == user.id,
        models.ActivityEntry.occurred_at >= start,
        models.ActivityEntry.occurred_at < end,
        models.ActivityEntry.category.in_(visible),
    ).order_by(models.ActivityEntry.occurred_at.asc(), models.ActivityEntry.id.asc()).all()
    moments = db.query(models.CompletionMoment).filter(
        models.CompletionMoment.user_id == user.id,
        models.CompletionMoment.completed_at >= start,
        models.CompletionMoment.completed_at < end,
        models.CompletionMoment.category.in_(visible),
    ).order_by(models.CompletionMoment.completed_at.asc()).all()

    # Finished titles: each title counts once, however many times it was logged.
    finished: dict[tuple, dict] = {}
    for entry in entries:
        if entry.action != "completed":
            continue
        key = _title_key(entry.category, entry.item_id, entry.title)
        finished.setdefault(key, {
            "category": entry.category, "title": entry.title, "rating": entry.rating,
            "finished_at": entry.occurred_at, "favorite": False,
        })
    for moment in moments:
        key = _title_key(moment.category, moment.item_id, moment.title)
        row = finished.setdefault(key, {
            "category": moment.category, "title": moment.title, "rating": moment.rating,
            "finished_at": moment.completed_at, "favorite": False,
        })
        row["favorite"] = row["favorite"] or bool(moment.favorite)
        if row["rating"] is None:
            row["rating"] = moment.rating

    categories = []
    for key in visible:
        model, label, done_field, verb, _ = CATEGORIES[key]
        total, done, added = db.query(
            func.count(model.id),
            func.sum(case((getattr(model, done_field) == True, 1), else_=0)),
            func.sum(case(((model.added_at >= start) & (model.added_at < end), 1), else_=0)),
        ).filter(model.user_id == user.id).one()
        finished_count = sum(1 for row in finished.values() if row["category"] == key)
        if not (total or finished_count):
            continue
        categories.append({
            "category": key, "label": label, "verb": verb,
            "finished": finished_count, "added": int(added or 0),
            "library_total": int(total or 0), "library_finished": int(done or 0),
        })

    month_counts = [0] * 12
    for entry in entries:
        month_counts[entry.occurred_at.month - 1] += 1
    busiest = max(range(12), key=lambda m: month_counts[m]) if any(month_counts) else None

    ordered = sorted(finished.values(), key=lambda row: row["finished_at"])
    rated = sorted((row for row in ordered if row["rating"] is not None),
                   key=lambda row: (-row["rating"], row["finished_at"]))
    labels = {key: CATEGORIES[key][1] for key in CATEGORIES}

    def _public_row(row):
        return {"category": row["category"], "label": labels[row["category"]], "title": row["title"],
                "rating": row["rating"], "month": row["finished_at"].strftime("%B")}

    finished_total = len(finished)
    top_category = max(categories, key=lambda c: (c["finished"], c["library_total"])) if categories else None
    if top_category and not top_category["finished"]:
        top_category = None
    library_total = sum(c["library_total"] for c in categories)
    recap = {
        "year": year,
        "username": user.username,
        "finished_total": finished_total,
        "added_total": sum(c["added"] for c in categories),
        "added_partial": year == ADD_DATES_FIRST_YEAR,
        "added_since": "October" if year == ADD_DATES_FIRST_YEAR else None,
        "moments_total": len(entries),
        "categories": categories,
        "top_category": {"category": top_category["category"], "label": top_category["label"],
                         "finished": top_category["finished"]} if top_category else None,
        "busiest_month": {"month": date(year, busiest + 1, 1).strftime("%B"), "count": month_counts[busiest]}
        if busiest is not None else None,
        "months": month_counts,
        "first_finish": _public_row(ordered[0]) if ordered else None,
        "last_finish": _public_row(ordered[-1]) if len(ordered) > 1 else None,
        "top_rated": [_public_row(row) for row in rated[:TOP_FINISHES_LIMIT]],
        "favorites": [_public_row(row) for row in ordered if row["favorite"]][:FAVORITES_LIMIT],
        "library_total": library_total,
        "is_empty": not (finished_total or entries or library_total),
    }
    if not public:
        recap["reflections_total"] = sum(1 for entry in entries if (entry.note or "").strip())
    return recap


# ---------------------------------------------------------------- sharing

def get_share(db: Session, user_id: int, year: int) -> Optional[models.YearInReviewShare]:
    return db.query(models.YearInReviewShare).filter(
        models.YearInReviewShare.user_id == user_id, models.YearInReviewShare.year == year,
    ).first()


def find_share(db: Session, token: str) -> Optional[models.YearInReviewShare]:
    if not token or len(token) > 64:
        return None
    share = db.query(models.YearInReviewShare).filter(models.YearInReviewShare.token == token).first()
    if share is None or share.owner is None or not share.owner.is_active:
        return None
    return share


def share_path(share: models.YearInReviewShare) -> str:
    return f"/recap/{share.token}"


def save_share(db: Session, user: models.User, year: int) -> models.YearInReviewShare:
    """Create or refresh the member's public snapshot for this year. The link stays the same."""
    import json

    snapshot = json.dumps(build(db, user, year, public=True), default=str)
    share = get_share(db, user.id, year)
    if share is None:
        share = models.YearInReviewShare(user_id=user.id, year=year, token=secrets.token_urlsafe(12))
        db.add(share)
    share.snapshot = snapshot
    share.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(share)
    return share


def delete_share(db: Session, user_id: int, year: int) -> bool:
    share = get_share(db, user_id, year)
    if share is None:
        return False
    db.delete(share)
    db.commit()
    return True


def snapshot(share: models.YearInReviewShare) -> dict:
    import json

    try:
        data = json.loads(share.snapshot or "{}")
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}
