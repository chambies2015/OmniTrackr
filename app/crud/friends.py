"""
Friends, Friend Requests, Notifications, and Friend Profile CRUD operations for the OmniTrackr API.
"""
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func

from .. import models, schemas
from .users import get_user_by_id
from .statistics import get_watch_statistics, get_rating_statistics


# ============================================================================
# Friend Request CRUD operations
# ============================================================================

def create_friend_request(db: Session, sender_id: int, receiver_id: int) -> Optional[models.FriendRequest]:
    """Create a new friend request."""
    if are_friends(db, sender_id, receiver_id, include_deactivated=True):
        raise ValueError("Users are already friends")
    
    existing = db.query(models.FriendRequest).filter(
        or_(
            and_(models.FriendRequest.sender_id == sender_id, models.FriendRequest.receiver_id == receiver_id),
            and_(models.FriendRequest.sender_id == receiver_id, models.FriendRequest.receiver_id == sender_id)
        ),
        models.FriendRequest.status == "pending"
    ).first()
    
    if existing and existing.expires_at and existing.expires_at < datetime.utcnow():
        existing.status = "expired"
        db.commit()
        existing = None

    if existing and existing.sender_id == receiver_id:
        # They already asked us: sending one back means yes, so accept theirs.
        return accept_friend_request(db, existing.id, sender_id)

    if existing:
        # The receiver may have dismissed the notification, which was the only
        # place to answer it; bring it back so the request isn't stuck.
        has_notification = db.query(models.Notification.id).filter(
            models.Notification.friend_request_id == existing.id,
            models.Notification.user_id == receiver_id,
        ).first()
        if not has_notification:
            create_notification(
                db=db,
                user_id=receiver_id,
                type="friend_request_received",
                message=f"{get_user_by_id(db, sender_id).username} sent you a friend request",
                friend_request_id=existing.id
            )
        raise ValueError("Friend request already exists")
    
    friend_request = models.FriendRequest(
        sender_id=sender_id,
        receiver_id=receiver_id,
        status="pending",
        expires_at=datetime.utcnow() + timedelta(days=30)
    )
    db.add(friend_request)
    db.commit()
    db.refresh(friend_request)
    
    receiver = get_user_by_id(db, receiver_id)
    if receiver:
        create_notification(
            db=db,
            user_id=receiver_id,
            type="friend_request_received",
            message=f"{get_user_by_id(db, sender_id).username} sent you a friend request",
            friend_request_id=friend_request.id
        )
    
    return friend_request


def get_friend_request(db: Session, request_id: int) -> Optional[models.FriendRequest]:
    """Get a friend request by ID."""
    return db.query(models.FriendRequest).filter(models.FriendRequest.id == request_id).first()


def get_friend_requests_by_user(db: Session, user_id: int) -> Tuple[List[models.FriendRequest], List[models.FriendRequest]]:
    """Get pending friend requests for a user (sent and received)."""
    sent = db.query(models.FriendRequest).filter(
        models.FriendRequest.sender_id == user_id,
        models.FriendRequest.status == "pending"
    ).all()
    
    received = db.query(models.FriendRequest).filter(
        models.FriendRequest.receiver_id == user_id,
        models.FriendRequest.status == "pending"
    ).all()
    
    return sent, received


def accept_friend_request(db: Session, request_id: int, user_id: int) -> Optional[models.FriendRequest]:
    """Accept a friend request."""
    friend_request = get_friend_request(db, request_id)
    if not friend_request:
        return None
    
    # Verify user is the receiver
    if friend_request.receiver_id != user_id:
        raise ValueError("You can only accept friend requests sent to you")
    
    if friend_request.status != "pending":
        raise ValueError("Friend request is not pending")
    
    if friend_request.expires_at < datetime.utcnow():
        friend_request.status = "expired"
        db.commit()
        raise ValueError("Friend request has expired")
    
    notification = db.query(models.Notification).filter(
        models.Notification.friend_request_id == request_id,
        models.Notification.user_id == user_id
    ).first()
    if notification:
        db.delete(notification)
    
    friend_request.status = "accepted"
    db.commit()
    
    user1_id = min(friend_request.sender_id, friend_request.receiver_id)
    user2_id = max(friend_request.sender_id, friend_request.receiver_id)
    create_friendship(db, user1_id, user2_id)
    
    sender = get_user_by_id(db, friend_request.sender_id)
    receiver = get_user_by_id(db, friend_request.receiver_id)
    
    if sender:
        create_notification(
            db=db,
            user_id=friend_request.sender_id,
            type="friend_request_accepted",
            message=f"{receiver.username} accepted your friend request",
            friend_request_id=request_id
        )
    
    return friend_request


def deny_friend_request(db: Session, request_id: int, user_id: int) -> Optional[models.FriendRequest]:
    """Deny a friend request."""
    friend_request = get_friend_request(db, request_id)
    if not friend_request:
        return None
    
    if friend_request.receiver_id != user_id:
        raise ValueError("You can only deny friend requests sent to you")
    
    if friend_request.status != "pending":
        raise ValueError("Friend request is not pending")
    
    notification = db.query(models.Notification).filter(
        models.Notification.friend_request_id == request_id,
        models.Notification.user_id == user_id
    ).first()
    if notification:
        db.delete(notification)
    
    friend_request.status = "denied"
    db.commit()
    
    return friend_request


def cancel_friend_request(db: Session, request_id: int, user_id: int) -> Optional[models.FriendRequest]:
    """Cancel a sent friend request."""
    friend_request = get_friend_request(db, request_id)
    if not friend_request:
        return None
    
    if friend_request.sender_id != user_id:
        raise ValueError("You can only cancel friend requests you sent")
    
    if friend_request.status != "pending":
        raise ValueError("Friend request is not pending")
    
    # Remove the receiver's Accept/Deny notification for a request that no longer exists.
    db.query(models.Notification).filter(
        models.Notification.friend_request_id == request_id,
        models.Notification.user_id == friend_request.receiver_id,
    ).delete(synchronize_session=False)
    friend_request.status = "cancelled"
    db.commit()
    
    return friend_request


def expire_friend_requests(db: Session) -> int:
    """Expire friend requests older than 30 days. Returns count of expired requests."""
    expired_count = db.query(models.FriendRequest).filter(
        models.FriendRequest.status == "pending",
        models.FriendRequest.expires_at < datetime.utcnow()
    ).update({"status": "expired"})
    db.commit()
    return expired_count


# ============================================================================
# Friendship CRUD operations
# ============================================================================

def create_friendship(db: Session, user1_id: int, user2_id: int) -> models.Friendship:
    """Create a friendship between two users (user1_id must be < user2_id)."""
    existing = db.query(models.Friendship).filter(
        models.Friendship.user1_id == user1_id,
        models.Friendship.user2_id == user2_id
    ).first()
    
    if existing:
        return existing
    
    friendship = models.Friendship(
        user1_id=user1_id,
        user2_id=user2_id
    )
    db.add(friendship)
    db.commit()
    db.refresh(friendship)
    return friendship


def get_friends(db: Session, user_id: int) -> List[models.User]:
    """Get all friends for a user."""
    friendships = db.query(models.Friendship).filter(
        or_(
            models.Friendship.user1_id == user_id,
            models.Friendship.user2_id == user_id
        )
    ).all()
    
    friend_ids = [friendship.user2_id if friendship.user1_id == user_id else friendship.user1_id
                  for friendship in friendships]
    # One query for every friend instead of one each, in the same order as before.
    users = {user.id: user for user in db.query(models.User).filter(models.User.id.in_(friend_ids))} if friend_ids else {}
    return [users[friend_id] for friend_id in friend_ids if friend_id in users and users[friend_id].is_active]


def are_friends(db: Session, user1_id: int, user2_id: int, include_deactivated: bool = False) -> bool:
    """Check if two users are friends.

    A deactivated member's friendships are kept so reactivating restores them,
    but until then friends can't read their library.
    """
    user1 = min(user1_id, user2_id)
    user2 = max(user1_id, user2_id)
    
    friendship = db.query(models.Friendship).filter(
        models.Friendship.user1_id == user1,
        models.Friendship.user2_id == user2
    ).first()
    if friendship is None:
        return False
    if include_deactivated:
        return True
    active = db.query(func.count(models.User.id)).filter(
        models.User.id.in_((user1, user2)), models.User.is_active.is_(True)
    ).scalar()
    return active == (1 if user1 == user2 else 2)


def remove_friendship(db: Session, user_id: int, friend_id: int) -> bool:
    """Remove a friendship (unfriend)."""
    user1 = min(user_id, friend_id)
    user2 = max(user_id, friend_id)
    
    friendship = db.query(models.Friendship).filter(
        models.Friendship.user1_id == user1,
        models.Friendship.user2_id == user2
    ).first()
    
    if not friendship:
        return False
    
    db.delete(friendship)
    db.commit()
    return True


# ============================================================================
# Notification CRUD operations
# ============================================================================

def create_notification(db: Session, user_id: int, type: str, message: str, friend_request_id: Optional[int] = None,
                        link: Optional[str] = None) -> models.Notification:
    """Create a notification for a user."""
    notification = models.Notification(
        user_id=user_id,
        type=type,
        message=message,
        friend_request_id=friend_request_id,
        link=link,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def get_notifications(db: Session, user_id: int, limit: Optional[int] = None,
                      unread_limit: int = 0) -> List[models.Notification]:
    """Notifications for a user, newest first.

    With a limit: the newest `limit`, plus up to `unread_limit` older unread ones, so a
    long-ignored bell still lists every pending friend request without sending thousands.
    """
    query = db.query(models.Notification).filter(
        models.Notification.user_id == user_id
    ).order_by(desc(models.Notification.created_at), desc(models.Notification.id))
    if limit is None:
        return query.all()
    newest = query.limit(limit).all()
    if len(newest) < limit or unread_limit <= 0:
        return newest
    shown = [notification.id for notification in newest]
    older_unread = query.filter(
        models.Notification.read_at.is_(None), models.Notification.id.notin_(shown)
    ).limit(unread_limit).all()
    return newest + older_unread


def get_unread_notification_count(db: Session, user_id: int) -> int:
    """Get count of unread notifications for a user."""
    return db.query(func.count(models.Notification.id)).filter(
        models.Notification.user_id == user_id,
        models.Notification.read_at.is_(None)
    ).scalar() or 0


def mark_notification_read(db: Session, notification_id: int, user_id: int) -> Optional[models.Notification]:
    """Mark a notification as read."""
    notification = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == user_id
    ).first()
    
    if not notification:
        return None
    
    if notification.read_at is None:
        notification.read_at = datetime.utcnow()
        db.commit()
        db.refresh(notification)
    
    return notification


def delete_notification(db: Session, notification_id: int, user_id: int) -> bool:
    """Delete a notification."""
    notification = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == user_id
    ).first()
    
    if not notification:
        return False
    
    db.delete(notification)
    db.commit()
    return True


# ============================================================================
# Friend Profile CRUD operations
# ============================================================================

def get_friend_profile_summary(db: Session, friend_id: int) -> Optional[schemas.FriendProfileSummary]:
    """Get friend's profile summary (counts only, respects privacy)."""
    friend = get_user_by_id(db, friend_id)
    if friend is None:
        return None
    
    movies_count = None
    tv_shows_count = None
    anime_count = None
    video_games_count = None
    music_count = None
    books_count = None
    manga_count = None
    podcasts_count = None
    audiobooks_count = None
    statistics_available = None
    
    if not friend.movies_private:
        movies_count = db.query(models.Movie).filter(models.Movie.user_id == friend_id).count()
    
    if not friend.tv_shows_private:
        tv_shows_count = db.query(models.TVShow).filter(models.TVShow.user_id == friend_id).count()
    
    if not friend.anime_private:
        anime_count = db.query(models.Anime).filter(models.Anime.user_id == friend_id).count()
    
    if not friend.video_games_private:
        video_games_count = db.query(models.VideoGame).filter(models.VideoGame.user_id == friend_id).count()
    
    if not friend.music_private:
        music_count = db.query(models.Music).filter(models.Music.user_id == friend_id).count()
    
    if not friend.books_private:
        books_count = db.query(models.Book).filter(models.Book.user_id == friend_id).count()

    if not friend.manga_private:
        manga_count = db.query(models.Manga).filter(models.Manga.user_id == friend_id).count()

    if not friend.podcasts_private:
        podcasts_count = db.query(models.Podcast).filter(models.Podcast.user_id == friend_id).count()

    if not friend.audiobooks_private:
        audiobooks_count = db.query(models.Audiobook).filter(models.Audiobook.user_id == friend_id).count()
    
    if not friend.statistics_private:
        statistics_available = True
    
    return schemas.FriendProfileSummary(
        username=friend.username,
        movies_count=movies_count,
        tv_shows_count=tv_shows_count,
        anime_count=anime_count,
        video_games_count=video_games_count,
        music_count=music_count,
        books_count=books_count,
        manga_count=manga_count,
        podcasts_count=podcasts_count,
        audiobooks_count=audiobooks_count,
        statistics_available=statistics_available,
        movies_private=friend.movies_private,
        tv_shows_private=friend.tv_shows_private,
        anime_private=friend.anime_private,
        video_games_private=friend.video_games_private,
        music_private=friend.music_private,
        books_private=friend.books_private,
        manga_private=friend.manga_private,
        podcasts_private=friend.podcasts_private,
        audiobooks_private=friend.audiobooks_private,
        statistics_private=friend.statistics_private
    )


def get_friend_movies(db: Session, friend_id: int) -> Optional[List[models.Movie]]:
    """Get friend's movies list (if not private)."""
    friend = get_user_by_id(db, friend_id)
    if friend is None:
        return None
    
    if friend.movies_private:
        return None  # Data is private
    
    return db.query(models.Movie).filter(models.Movie.user_id == friend_id).all()


def get_friend_tv_shows(db: Session, friend_id: int) -> Optional[List[models.TVShow]]:
    """Get friend's TV shows list (if not private)."""
    friend = get_user_by_id(db, friend_id)
    if friend is None:
        return None
    
    if friend.tv_shows_private:
        return None  # Data is private
    
    return db.query(models.TVShow).filter(models.TVShow.user_id == friend_id).all()


def get_friend_anime(db: Session, friend_id: int) -> Optional[List[models.Anime]]:
    """Get friend's anime list (if not private)."""
    friend = get_user_by_id(db, friend_id)
    if friend is None:
        return None
    
    if friend.anime_private:
        return None  # Data is private
    
    return db.query(models.Anime).filter(models.Anime.user_id == friend_id).all()


def get_friend_video_games(db: Session, friend_id: int) -> Optional[List[models.VideoGame]]:
    """Get friend's video games list (if not private)."""
    friend = get_user_by_id(db, friend_id)
    if friend is None:
        return None
    
    if friend.video_games_private:
        return None  # Data is private
    
    return db.query(models.VideoGame).filter(models.VideoGame.user_id == friend_id).all()


def get_friend_music(db: Session, friend_id: int) -> Optional[List[models.Music]]:
    """Get friend's music list (if not private)."""
    friend = get_user_by_id(db, friend_id)
    if friend is None:
        return None
    
    if friend.music_private:
        return None  # Data is private
    
    return db.query(models.Music).filter(models.Music.user_id == friend_id).all()


def get_friend_books(db: Session, friend_id: int) -> Optional[List[models.Book]]:
    """Get friend's books list (if not private)."""
    friend = get_user_by_id(db, friend_id)
    if friend is None:
        return None
    
    if friend.books_private:
        return None  # Data is private
    
    return db.query(models.Book).filter(models.Book.user_id == friend_id).all()


def get_friend_manga(db: Session, friend_id: int) -> Optional[List[models.Manga]]:
    """Get friend's manga list (if not private)."""
    friend = get_user_by_id(db, friend_id)
    if friend is None:
        return None

    if friend.manga_private:
        return None  # Data is private

    return db.query(models.Manga).filter(models.Manga.user_id == friend_id).all()


def get_friend_podcasts(db: Session, friend_id: int) -> Optional[List[models.Podcast]]:
    """Get friend's podcast list (if not private)."""
    friend = get_user_by_id(db, friend_id)
    if friend is None:
        return None

    if friend.podcasts_private:
        return None  # Data is private

    return db.query(models.Podcast).filter(models.Podcast.user_id == friend_id).all()


def get_friend_audiobooks(db: Session, friend_id: int) -> Optional[List[models.Audiobook]]:
    """Get friend's audiobook list (if not private)."""
    friend = get_user_by_id(db, friend_id)
    if friend is None:
        return None

    if friend.audiobooks_private:
        return None  # Data is private

    return db.query(models.Audiobook).filter(models.Audiobook.user_id == friend_id).all()


def get_friend_statistics(db: Session, friend_id: int) -> Optional[dict]:
    """Get friend's statistics (compact version, if not private)."""
    friend = get_user_by_id(db, friend_id)
    if friend is None:
        return None
    
    if friend.statistics_private:
        return None  # Data is private
    
    # Return compact statistics (watch and rating stats only)
    watch_stats = get_watch_statistics(db, friend_id)
    hidden = [entry for entry in _FRIEND_STAT_CATEGORIES if getattr(friend, entry[0] + "_private", False)]
    if hidden:
        # Private categories must not show up through stats either.
        watch_stats = _without_categories(watch_stats, hidden)
        rating_stats = _visible_rating_statistics(db, friend_id, hidden)
    else:
        rating_stats = get_rating_statistics(db, friend_id)
    
    return {
        "watch_stats": watch_stats,
        "rating_stats": rating_stats
    }



# (privacy prefix, watch-stat suffix, model, finished column, label in rating lists)
_FRIEND_STAT_CATEGORIES = (
    ("movies", "movies", "Movie", "watched", "Movie"),
    ("tv_shows", "tv_shows", "TVShow", "watched", "TV Show"),
    ("anime", "anime", "Anime", "watched", "Anime"),
    ("video_games", "video_games", "VideoGame", "played", "Video Game"),
    ("music", "music", "Music", "listened", "Music"),
    ("books", "books", "Book", "read", "Book"),
    ("manga", "manga", "Manga", "read", "Manga"),
    ("podcasts", "podcasts", "Podcast", "listened", "Podcast"),
    ("audiobooks", "audiobooks", "Audiobook", "listened", "Audiobook"),
)


def _without_categories(watch_stats: dict, hidden) -> dict:
    stats = dict(watch_stats)
    for _, suffix, _, _, _ in hidden:
        for key in [key for key in stats if key.endswith("_" + suffix) and key != "total_items"]:
            stats[key] = 0
    total = sum(stats["total_" + entry[1]] for entry in _FRIEND_STAT_CATEGORIES)
    done = sum(stats[f"{finished}_{suffix}"] for _, suffix, _, finished, _ in _FRIEND_STAT_CATEGORIES)
    stats.update(total_items=total, watched_items=done, unwatched_items=total - done,
                 completion_percentage=round((done / total * 100) if total > 0 else 0, 1))
    return stats


def _visible_rating_statistics(db: Session, user_id: int, hidden) -> dict:
    from .statistics import _rating_bucket
    rated = []
    for entry in _FRIEND_STAT_CATEGORIES:
        if entry in hidden:
            continue
        model = getattr(models, entry[2])
        rows = db.query(model.title, model.rating).filter(model.user_id == user_id, model.rating.isnot(None)).all()
        rated.extend({"title": title, "type": entry[4], "rating": rating} for title, rating in rows)
    if not rated:
        return {"average_rating": 0, "total_rated_items": 0, "rating_distribution": {},
                "highest_rated": [], "lowest_rated": []}
    ratings = [row["rating"] for row in rated]
    distribution = {}
    for bucket in range(0, 11):
        count = sum(1 for rating in ratings if _rating_bucket(rating) == bucket)
        if count:
            distribution[str(bucket)] = count
    highest, lowest = max(ratings), min(ratings)
    return {
        "average_rating": round(sum(ratings) / len(ratings), 1),
        "total_rated_items": len(ratings),
        "rating_distribution": distribution,
        "highest_rated": [row for row in rated if row["rating"] == highest][:5],
        "lowest_rated": [row for row in rated if row["rating"] == lowest][:5],
    }
