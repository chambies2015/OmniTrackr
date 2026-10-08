"""The "Review of the week": one member review highlighted on the homepage and in the weekly email.

Chosen from public, standalone reviews (same quality and moderation checks as /reviews):
the one most marked "helpful" in the last seven days, otherwise the newest thorough review
(150+ words). Cached for an hour; never raises.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

from .review_quality import AD_MIN_REVIEW_WORDS, word_count

CACHE_SECONDS = 3600
WINDOW = timedelta(days=7)
CANDIDATES = 60

_lock = threading.Lock()
_cache = {"at": 0.0, "value": None}


def choose(reviews: list[dict], weekly_marks: dict) -> dict | None:
    """Pure selection rule (see module docstring). `reviews` are newest first."""
    standalone = [r for r in reviews if r.get("search_ready") and (r.get("title") or "").strip()]
    if not standalone:
        return None
    marked = [r for r in standalone if weekly_marks.get((r["category"], int(r["id"])), 0) > 0]
    if marked:
        return max(marked, key=lambda r: (weekly_marks[(r["category"], int(r["id"]))], word_count(r.get("review")), r["id"]))
    thorough = [r for r in standalone if word_count(r.get("review")) >= AD_MIN_REVIEW_WORDS]
    return (thorough or standalone)[0]


def _weekly_marks(db, reviews: list[dict], now: datetime) -> dict:
    from sqlalchemy import func

    from . import models
    table = models.ReviewReaction
    counts = {}
    by_category: dict = {}
    for review in reviews:
        by_category.setdefault(review["category"], set()).add(int(review["id"]))
    for category, ids in by_category.items():
        rows = db.query(table.item_id, func.count(table.id)).filter(
            table.category == category, table.item_id.in_(sorted(ids)), table.created_at >= now - WINDOW,
        ).group_by(table.item_id).all()
        counts.update({(category, item_id): int(n) for item_id, n in rows})
    return counts


def build(db, now: datetime | None = None) -> dict | None:
    from .routers import reviews as reviews_router
    now = now or datetime.utcnow()
    feed = reviews_router._public_review_feed(db, None, "", CANDIDATES, 0)["reviews"]
    chosen = choose(feed, _weekly_marks(db, feed, now))
    if chosen:
        reviews_router._attach_profile_urls(db, [chosen])
    return chosen


def review_of_the_week(session_factory=None) -> dict | None:
    now = time.monotonic()
    with _lock:
        if _cache["at"] and now - _cache["at"] < CACHE_SECONDS:
            return _cache["value"]
    value = None
    try:
        if session_factory is None:
            from .database import SessionLocal as session_factory
        db = session_factory()
        try:
            value = build(db)
        finally:
            db.close()
    except Exception:
        value = None
    with _lock:
        _cache["at"], _cache["value"] = now, value
    return value


def clear_cache() -> None:
    with _lock:
        _cache["at"], _cache["value"] = 0.0, None
