"""
SQLAlchemy models for the OmniTrackr API.
Defines the User, Movie, TV Show, Anime, and Video Game ORM models.
"""
from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, DateTime, UniqueConstraint, LargeBinary
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from .database import Base


class User(Base):
    """User model for authentication and data ownership."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String, nullable=True)
    reset_token = Column(String, nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    deactivated_at = Column(DateTime, nullable=True)
    
    # Privacy settings
    movies_private = Column(Boolean, default=False, nullable=False)
    tv_shows_private = Column(Boolean, default=False, nullable=False)
    anime_private = Column(Boolean, default=False, nullable=False)
    video_games_private = Column(Boolean, default=False, nullable=False)
    statistics_private = Column(Boolean, default=False, nullable=False)
    
    # Tab visibility settings (default to True - all tabs visible)
    movies_visible = Column(Boolean, default=True, nullable=False)
    tv_shows_visible = Column(Boolean, default=True, nullable=False)
    anime_visible = Column(Boolean, default=True, nullable=False)
    video_games_visible = Column(Boolean, default=True, nullable=False)
    
    # Profile picture
    profile_picture_url = Column(String, nullable=True)  # Kept for backward compatibility, now stores virtual URL like /profile-pictures/{user_id}
    profile_picture_data = Column(LargeBinary, nullable=True)  # Binary image data stored in database
    profile_picture_mime_type = Column(String, nullable=True)  # MIME type (image/jpeg, image/png, etc.)
    
    # Relationships - cascade delete ensures user's data is deleted with them
    movies = relationship("Movie", back_populates="owner", cascade="all, delete-orphan")
    tv_shows = relationship("TVShow", back_populates="owner", cascade="all, delete-orphan")
    anime = relationship("Anime", back_populates="owner", cascade="all, delete-orphan")
    video_games = relationship("VideoGame", back_populates="owner", cascade="all, delete-orphan")
    # Friends relationships
    sent_friend_requests = relationship("FriendRequest", foreign_keys="FriendRequest.sender_id", back_populates="sender", cascade="all, delete-orphan")
    received_friend_requests = relationship("FriendRequest", foreign_keys="FriendRequest.receiver_id", back_populates="receiver", cascade="all, delete-orphan")
    friendships_as_user1 = relationship("Friendship", foreign_keys="Friendship.user1_id", back_populates="user1", cascade="all, delete-orphan")
    friendships_as_user2 = relationship("Friendship", foreign_keys="Friendship.user2_id", back_populates="user2", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class Movie(Base):
    """Movie model with user ownership."""
    __tablename__ = "movies"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    director = Column(String, index=True)
    year = Column(Integer)
    rating = Column(Float, nullable=True)
    watched = Column(Boolean, default=False)
    review = Column(String, nullable=True)
    poster_url = Column(String, nullable=True)
    
    # User relationship
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner = relationship("User", back_populates="movies")


class TVShow(Base):
    """TV Show model with user ownership."""
    __tablename__ = "tv_shows"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    year = Column(Integer)
    seasons = Column(Integer, nullable=True)
    episodes = Column(Integer, nullable=True)
    rating = Column(Float, nullable=True)
    watched = Column(Boolean, default=False)
    review = Column(String, nullable=True)
    poster_url = Column(String, nullable=True)
    
    # User relationship
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner = relationship("User", back_populates="tv_shows")


class Anime(Base):
    """Anime model with user ownership."""
    __tablename__ = "anime"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    year = Column(Integer)
    seasons = Column(Integer, nullable=True)
    episodes = Column(Integer, nullable=True)
    rating = Column(Float, nullable=True)
    watched = Column(Boolean, default=False)
    review = Column(String, nullable=True)
    poster_url = Column(String, nullable=True)
    
    # User relationship
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner = relationship("User", back_populates="anime")


class VideoGame(Base):
    """Video Game model with user ownership."""
    __tablename__ = "video_games"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    release_date = Column(DateTime, nullable=True)  # Full date format YYYY-MM-DD
    genres = Column(String, nullable=True)  # Comma-separated genre names
    rating = Column(Float, nullable=True)
    played = Column(Boolean, default=False)
    review = Column(String, nullable=True)
    cover_art_url = Column(String, nullable=True)  # Equivalent to poster_url
    rawg_link = Column(String, nullable=True)  # RAWG game page URL
    
    # User relationship
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner = relationship("User", back_populates="video_games")


class FriendRequest(Base):
    """Friend request model for user friend requests."""
    __tablename__ = "friend_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, default="pending", index=True)  # pending, accepted, denied, expired, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    # Relationships
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_friend_requests")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_friend_requests")
    notifications = relationship("Notification", back_populates="friend_request", cascade="all, delete-orphan")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(days=30)


class Friendship(Base):
    """Friendship model for accepted friend relationships."""
    __tablename__ = "friendships"
    
    id = Column(Integer, primary_key=True, index=True)
    user1_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # Smaller ID
    user2_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # Larger ID
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user1 = relationship("User", foreign_keys=[user1_id], back_populates="friendships_as_user1")
    user2 = relationship("User", foreign_keys=[user2_id], back_populates="friendships_as_user2")
    
    # Unique constraint to prevent duplicate friendships
    __table_args__ = (UniqueConstraint('user1_id', 'user2_id', name='_friendship_uc'),)


class Notification(Base):
    """Notification model for user notifications."""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String, nullable=False)  # friend_request_received, friend_request_accepted, etc.
    message = Column(String, nullable=False)
    friend_request_id = Column(Integer, ForeignKey("friend_requests.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    read_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="notifications")
    friend_request = relationship("FriendRequest", back_populates="notifications")
