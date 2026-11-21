"""Share your reviews: private reviews a member could put on title pages (Nov 2026).

Most reviews on OmniTrackr are private, because the Public switch starts off and
imports (Letterboxd, Goodreads, AniList...) always arrive private. Some of those
reviews are written for other people and would be the only review on their title's
page. The dashboard card built on this module lists them and lets the member share
one at a time.

Nothing here changes a review on its own. Sharing sets review_public, the same field
the library editor's Public switch sets, and only after the member presses Share for
that review. A review that was public before and later made private is never offered
again, and "Keep private" is remembered until the review is rewritten.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models, review_spoilers, title_pages
from .review_quality import evaluate_public_review, word_count

# review category -> (title kind, model, library category, label, User privacy flag)
CATEGORIES = {
    review: (kind, model, library, label, title_pages.PRIVATE_FLAG[kind])
    for kind, (model, review, library, label, _) in title_pages.KINDS.items()
}
MIN_CHARS = title_pages.REVIEW_MIN_CHARS
DETAIL_MIN_CHARS = title_pages.REVIEW_DETAIL_MIN_CHARS
EXCERPT_CHARS = 320
SCAN_PER_CATEGORY = 400  # a member's private reviews read per format; far more than anyone has
LIST_LIMIT = 30


def content_hash(text: Optional[str]) -> str:
    """Identifies the exact review text the member was shown (whitespace-insensitive)."""
    normalized = " ".join(str(text or "").split())
    return hashlib.sha256(normalized.encode("utf-8", "surrogatepass")).hexdigest()


def _excerpt(text: str, limit: int = EXCERPT_CHARS) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:-")
    return cut + "…"


def _ever_public(db: Session, category: str, ids: list[int]) -> set[int]:
    """Entries that were public at some point: readers marked them helpful or reported them.

    A member who made one of those private again did it on purpose, so it isn't offered.
    """
    if not ids:
        return set()
    found = set()
    for table in (models.ReviewReaction, models.PublicReviewState):
        found.update(item_id for (item_id,) in db.query(table.item_id).filter(
            table.category == category, table.item_id.in_(ids)).distinct())
    return found


def _reviewed_titles(db: Session, model, user_id: int, normalized: set[str]) -> set[str]:
    """Which of these titles already show another member's public review."""
    if not normalized:
        return set()
    title = func.lower(func.trim(model.title))
    rows = db.query(title).join(models.User, models.User.id == model.user_id).filter(
        models.User.is_active == True, model.user_id != user_id, model.review_public == True,
        func.length(func.trim(model.review)) >= MIN_CHARS, title.in_(sorted(normalized)),
    ).distinct().all()
    return {value for (value,) in rows}


def _choices(db: Session, user_id: int) -> dict:
    rows = db.query(models.ReviewShareChoice).filter(models.ReviewShareChoice.user_id == user_id).all()
    return {(row.category, row.item_id): row for row in rows}


def candidates(db: Session, user: models.User, limit: int = LIST_LIMIT) -> dict:
    """The member's private reviews that would appear on a title page if shared, best first."""
    choices = _choices(db, user.id)
    found = []
    for category, (kind, model, library, label, private_flag) in CATEGORIES.items():
        rows = db.query(model).filter(
            model.user_id == user.id, model.review_public == False, model.review.isnot(None),
            func.length(func.trim(model.review)) >= MIN_CHARS,
        ).order_by(model.id.desc()).limit(SCAN_PER_CATEGORY).all()
        rows = [row for row in rows if (row.title or "").strip()]
        if not rows:
            continue
        skip = _ever_public(db, category, [row.id for row in rows])
        ready = []
        for row in rows:
            text = (row.review or "").strip()
            choice = choices.get((category, row.id))
            # A "kept" answer holds until the review is rewritten; a review shared from here
            # and then made private again in the library stays private.
            if row.id in skip or (choice and (choice.choice == "shared" or choice.content_hash == content_hash(text))):
                continue
            quality = evaluate_public_review(text, MIN_CHARS, DETAIL_MIN_CHARS)
            if quality.community_ready:
                ready.append((row, text, quality))
        if not ready:
            continue
        reviewed = _reviewed_titles(db, model, user.id, {title_pages.normalize(row.title) for row, _, _ in ready})
        flagged = review_spoilers.flagged(db, [(category, row.id) for row, _, _ in ready])
        for row, text, quality in ready:
            found.append({
                "category": category,
                "library_category": library,
                "id": row.id,
                "kind": kind,
                "label": label,
                "title": row.title.strip(),
                "year": title_pages.item_year(kind, row),
                "rating": row.rating,
                "excerpt": _excerpt(text),
                "words": quality.word_count,
                "version": content_hash(text),
                # Long enough for a review page of its own (and to count towards search).
                "standalone": quality.search_ready,
                "first": title_pages.normalize(row.title) not in reviewed,
                "private_list": bool(getattr(user, private_flag, False)),
                "spoilers": flagged.get((category, row.id)) == user.id,
                "path": title_pages.path_for_item(kind, row),
            })
    found.sort(key=lambda item: (not item["first"], not item["standalone"], -item["words"]))
    return {"total": len(found), "items": found[:limit]}


def _owned(db: Session, user_id: int, category: str, item_id: int):
    if category not in CATEGORIES:
        return None
    model = CATEGORIES[category][1]
    return db.query(model).filter(model.id == item_id, model.user_id == user_id).first()


def _remember(db: Session, user_id: int, category: str, item_id: int, choice: str, version: str) -> None:
    row = db.query(models.ReviewShareChoice).filter_by(user_id=user_id, category=category, item_id=item_id).first()
    if row is None:
        db.add(models.ReviewShareChoice(user_id=user_id, category=category, item_id=item_id,
                                        choice=choice, content_hash=version))
    else:
        row.choice, row.content_hash, row.created_at = choice, version, datetime.utcnow()


class ShareError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _current(db: Session, user_id: int, category: str, item_id: int, version: str):
    item = _owned(db, user_id, category, item_id)
    if item is None or not (item.review or "").strip():
        raise ShareError(404, "That review isn't in your library any more.")
    if content_hash(item.review) != version:
        raise ShareError(409, "This review changed since the list loaded. Reload to see the latest version.")
    return item


def share(db: Session, user: models.User, category: str, item_id: int, version: str, spoilers: bool) -> dict:
    """Make one review public (the caller commits)."""
    item = _current(db, user.id, category, item_id, version)
    quality = evaluate_public_review(item.review, MIN_CHARS, DETAIL_MIN_CHARS)
    if not quality.community_ready:
        raise ShareError(422, "This review is too short to show on a title page. Add a few sentences first.")
    kind = CATEGORIES[category][0]
    item.review_public = True
    review_spoilers.set_flag(db, category, item, spoilers)
    _remember(db, user.id, category, item.id, "shared", version)
    return {
        "shared": True,
        "path": title_pages.path_for_item(kind, item),
        "review_url": f"/reviews/{item.id}?category={category}" if quality.search_ready else None,
        "words": word_count(item.review),
    }


def keep_private(db: Session, user: models.User, category: str, item_id: int, version: str) -> dict:
    """Stop offering one review (the caller commits). The review itself is untouched."""
    item = _current(db, user.id, category, item_id, version)
    _remember(db, user.id, category, item.id, "kept", version)
    return {"kept": True}


def undo(db: Session, user: models.User, category: str, item_id: int) -> dict:
    """Take back a share made from the card a moment ago, or a "Keep private" answer (the caller commits)."""
    row = db.query(models.ReviewShareChoice).filter_by(user_id=user.id, category=category, item_id=item_id).first()
    item = _owned(db, user.id, category, item_id)
    if row is None or item is None:
        raise ShareError(404, "There's nothing to undo for that review.")
    if row.choice == "shared":
        item.review_public = False
    db.delete(row)
    return {"undone": True, "public": bool(item.review_public)}


def stats(db: Session, days: int, now: Optional[datetime] = None) -> dict:
    """Site stats: answers given on the card in the range, and how many shareable reviews are waiting."""
    now = now or datetime.utcnow()
    start = now - timedelta(days=days)
    table = models.ReviewShareChoice
    answered = dict(db.query(table.choice, func.count(table.id)).filter(table.created_at >= start)
                    .group_by(table.choice).all())
    sharers = db.query(func.count(func.distinct(table.user_id))).filter(
        table.choice == "shared", table.created_at >= start).scalar() or 0
    decided = {(row.user_id, row.category, row.item_id) for row in db.query(table.user_id, table.category, table.item_id)}
    waiting = 0
    members = set()
    for category, (_, model, _, _, _) in CATEGORIES.items():
        rows = db.query(model.id, model.user_id, model.review).join(models.User, models.User.id == model.user_id).filter(
            models.User.is_active == True, model.review_public == False, model.review.isnot(None),
            func.length(func.trim(model.review)) >= MIN_CHARS,
        ).yield_per(500)
        for item_id, user_id, text in rows:
            if (user_id, category, item_id) in decided:
                continue
            # Every member's private reviews: read the shared cache but don't fill it, or one
            # Site stats visit could push the public reviews the feeds rely on out of it.
            if evaluate_public_review(text, MIN_CHARS, DETAIL_MIN_CHARS, remember=False).community_ready:
                waiting += 1
                members.add(user_id)
    return {
        "shared": int(answered.get("shared", 0)),
        "kept": int(answered.get("kept", 0)),
        "sharers": int(sharers),
        "waiting": waiting,
        "waiting_members": len(members),
    }
