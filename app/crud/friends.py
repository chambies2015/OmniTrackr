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
    if are_friends(db, sender_id, receiver_id):
        raise ValueError("Users are already friends")
    
    existing = db.query(models.FriendRequest).filter(
        or_(
            and_(models.FriendRequest.sender_id == sender_id, models.FriendRequest.receiver_id == receiver_id),
            and_(models.FriendRequest.sender_id == receiver_id, models.FriendRequest.receiver_id == sender_id)
        ),
        models.FriendRequest.status == "pending"
    ).first()
    
    if existing:
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
    
    friends = []
    for friendship in friendships:
        if friendship.user1_id == user_id:
            friend = get_user_by_id(db, friendship.user2_id)
        else:
            friend = get_user_by_id(db, friendship.user1_id)
        if friend:
            friends.append(friend)
    
    return friends


def are_friends(db: Session, user1_id: int, user2_id: int) -> bool:
    """Check if two users are friends."""
    user1 = min(user1_id, user2_id)
    user2 = max(user1_id, user2_id)
    
    friendship = db.query(models.Friendship).filter(
        models.Friendship.user1_id == user1,
        models.Friendship.user2_id == user2
    ).first()
    
    return friendship is not None


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

def create_notification(db: Session, user_id: int, type: str, message: str, friend_request_id: Optional[int] = None) -> models.Notification:
    """Create a notification for a user."""
    notification = models.Notification(
        user_id=user_id,
        type=type,
        message=message,
        friend_request_id=friend_request_id
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def get_notifications(db: Session, user_id: int) -> List[models.Notification]:
    """Get all notifications for a user (newest first)."""
    return db.query(models.Notification).filter(
        models.Notification.user_id == user_id
    ).order_by(desc(models.Notification.created_at), desc(models.Notification.id)).all()


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
        statistics_available=statistics_available,
        movies_private=friend.movies_private,
        tv_shows_private=friend.tv_shows_private,
        anime_private=friend.anime_private,
        video_games_private=friend.video_games_private,
        music_private=friend.music_private,
        books_private=friend.books_private,
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


def get_friend_statistics(db: Session, friend_id: int) -> Optional[dict]:
    """Get friend's statistics (compact version, if not private)."""
    friend = get_user_by_id(db, friend_id)
    if friend is None:
        return None
    
    if friend.statistics_private:
        return None  # Data is private
    
    # Return compact statistics (watch and rating stats only)
    watch_stats = get_watch_statistics(db, friend_id)
    rating_stats = get_rating_statistics(db, friend_id)
    
    return {
        "watch_stats": watch_stats,
        "rating_stats": rating_stats
    }

