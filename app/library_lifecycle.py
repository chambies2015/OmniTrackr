"""Delete owned media without allowing polymorphic references to inherit reused IDs."""
from sqlalchemy.orm import Session

from . import models
from .progress import lock_progress_owner

MEDIA_MODELS = {
    "movies": models.Movie, "tv-shows": models.TVShow, "anime": models.Anime,
    "video-games": models.VideoGame, "music": models.Music, "books": models.Book,
}
REVIEW_CATEGORIES = {
    "movies": "movie", "tv-shows": "tv_show", "anime": "anime",
    "video-games": "video_game", "music": "music", "books": "book",
}


def delete_owned_media(db: Session, user_id: int, category: str, item_id: int):
    """Clean references and delete the item in one owner-first transaction.

    Completion reflections retain their snapshots. A deleted reflection stores
    ``item_id = -moment.id``: media IDs are positive, and the unique negative
    marker cannot collide with a future title or another retained reflection.
    Review writes using that reflection then correctly find no library item.
    """
    try:
        lock_progress_owner(db, user_id)
        model = MEDIA_MODELS[category]
        item = db.query(model).filter_by(user_id=user_id, id=item_id).with_for_update().first()
        if item is None:
            db.rollback()
            return None
        for reference in (models.NextUpItem, models.ProgressCheckpoint):
            db.query(reference).filter_by(user_id=user_id, category=category, item_id=item_id).delete(synchronize_session=False)
        owned_collections = db.query(models.Collection.id).filter(models.Collection.user_id == user_id)
        db.query(models.CollectionItem).filter(
            models.CollectionItem.collection_id.in_(owned_collections),
            models.CollectionItem.category == category, models.CollectionItem.item_id == item_id,
        ).delete(synchronize_session=False)
        db.query(models.ActivityEntry).filter_by(user_id=user_id, category=category, item_id=item_id).update(
            {models.ActivityEntry.item_id: None}, synchronize_session=False,
        )
        db.query(models.CompletionMoment).filter_by(user_id=user_id, category=category, item_id=item_id).update(
            {models.CompletionMoment.item_id: -models.CompletionMoment.id}, synchronize_session=False,
        )
        owned_requests = db.query(models.RecommendationRequest.id).filter(models.RecommendationRequest.owner_id == user_id)
        db.query(models.RecommendationSubmission).filter(
            models.RecommendationSubmission.request_id.in_(owned_requests),
            models.RecommendationSubmission.category == category,
            models.RecommendationSubmission.accepted_item_id == item_id,
        ).update({models.RecommendationSubmission.accepted_item_id: None}, synchronize_session=False)
        review_category = REVIEW_CATEGORIES[category]
        db.query(models.ReviewReaction).filter_by(category=review_category, item_id=item_id).delete(synchronize_session=False)
        states = db.query(models.PublicReviewState.id).filter_by(category=review_category, item_id=item_id)
        db.query(models.PublicReviewReport).filter(models.PublicReviewReport.state_id.in_(states)).delete(synchronize_session=False)
        db.query(models.PublicReviewState).filter_by(category=review_category, item_id=item_id).delete(synchronize_session=False)
        db.delete(item)
        db.commit()
        return item
    except Exception:
        db.rollback()
        raise
