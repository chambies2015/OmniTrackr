"""Members can mark a review as containing spoilers (Oct 2026).

The flag lives in its own table, keyed by review category and library item id, so
library tables and existing reviews are untouched. Public pages show a flagged
review behind a "Show review" toggle, and teaser surfaces (homepage, weekly email,
chart quotes, search snippets) skip it.
"""
from sqlalchemy.orm import Session

from . import models


def flagged(db: Session, keys) -> dict:
    """{(category, item_id): user_id} for the flags among `keys`."""
    keys = {(category, int(item_id)) for category, item_id in keys}
    if not keys:
        return {}
    by_category: dict = {}
    for category, item_id in keys:
        by_category.setdefault(category, set()).add(item_id)
    table = models.ReviewSpoiler
    found = {}
    for category, ids in by_category.items():
        rows = db.query(table.item_id, table.user_id).filter(table.category == category, table.item_id.in_(sorted(ids))).all()
        found.update({(category, item_id): user_id for item_id, user_id in rows})
    return found


def attach(db: Session, reviews: list) -> list:
    """Set review["spoilers"] on serialized public reviews (dicts with category and id)."""
    marked = flagged(db, [(review["category"], review["id"]) for review in reviews])
    for review in reviews:
        owner = marked.get((review["category"], int(review["id"])))
        review["spoilers"] = owner is not None and owner == review.get("user_id")
    return reviews


def is_flagged(db: Session, category: str, item) -> bool:
    return db.query(models.ReviewSpoiler.id).filter_by(category=category, item_id=item.id, user_id=item.user_id).first() is not None


def set_flag(db: Session, category: str, item, spoilers: bool) -> None:
    """Mark or clear the writer's spoiler flag for one library entry (caller commits)."""
    row = db.query(models.ReviewSpoiler).filter_by(category=category, item_id=item.id).first()
    if spoilers and row is None:
        db.add(models.ReviewSpoiler(category=category, item_id=item.id, user_id=item.user_id))
    elif spoilers and row.user_id != item.user_id:
        row.user_id = item.user_id
    elif not spoilers and row is not None:
        db.delete(row)


def wrap(review: dict, inner_html: str) -> str:
    """Fold a flagged review's (already escaped) markup behind a "Show it" toggle."""
    if not review.get("spoilers"):
        return inner_html
    return ('<details class="review-spoiler"><summary><span class="review-spoiler__tag">Spoilers</span> '
            f'This review gives away plot details. Show it</summary>{inner_html}</details>')
