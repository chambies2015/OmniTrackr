"""
SQLAlchemy models for the OmniTrackr API.
Defines the User, Movie, TV Show, Anime, and Video Game ORM models.
"""
from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, DateTime, UniqueConstraint, LargeBinary, Text
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
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    deactivated_at = Column(DateTime, nullable=True)
    
    # Privacy settings
    movies_private = Column(Boolean, default=False, nullable=False)
    tv_shows_private = Column(Boolean, default=False, nullable=False)
    anime_private = Column(Boolean, default=False, nullable=False)
    video_games_private = Column(Boolean, default=False, nullable=False)
    music_private = Column(Boolean, default=False, nullable=False)
    books_private = Column(Boolean, default=False, nullable=False)
    statistics_private = Column(Boolean, default=False, nullable=False)
    reviews_public = Column(Boolean, default=False, nullable=False)
    
    movies_visible = Column(Boolean, default=True, nullable=False)
    tv_shows_visible = Column(Boolean, default=True, nullable=False)
    anime_visible = Column(Boolean, default=True, nullable=False)
    video_games_visible = Column(Boolean, default=True, nullable=False)
    music_visible = Column(Boolean, default=True, nullable=False)
    books_visible = Column(Boolean, default=True, nullable=False)
    
    # Profile picture
    profile_picture_url = Column(String, nullable=True)
    profile_picture_data = Column(LargeBinary, nullable=True)
    profile_picture_mime_type = Column(String, nullable=True)
    
    movies = relationship("Movie", back_populates="owner", cascade="all, delete-orphan")
    tv_shows = relationship("TVShow", back_populates="owner", cascade="all, delete-orphan")
    anime = relationship("Anime", back_populates="owner", cascade="all, delete-orphan")
    video_games = relationship("VideoGame", back_populates="owner", cascade="all, delete-orphan")
    music = relationship("Music", back_populates="owner", cascade="all, delete-orphan")
    books = relationship("Book", back_populates="owner", cascade="all, delete-orphan")
    # Friends relationships
    sent_friend_requests = relationship("FriendRequest", foreign_keys="FriendRequest.sender_id", back_populates="sender", cascade="all, delete-orphan")
    received_friend_requests = relationship("FriendRequest", foreign_keys="FriendRequest.receiver_id", back_populates="receiver", cascade="all, delete-orphan")
    friendships_as_user1 = relationship("Friendship", foreign_keys="Friendship.user1_id", back_populates="user1", cascade="all, delete-orphan")
    friendships_as_user2 = relationship("Friendship", foreign_keys="Friendship.user2_id", back_populates="user2", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    custom_tabs = relationship("CustomTab", back_populates="owner", cascade="all, delete-orphan")
    next_up_items = relationship("NextUpItem", back_populates="owner", cascade="all, delete-orphan")
    completion_moments = relationship("CompletionMoment", back_populates="owner", cascade="all, delete-orphan")
    collections = relationship("Collection", back_populates="owner", cascade="all, delete-orphan")


class Movie(Base):
    """Movie model with user ownership."""
    __tablename__ = "movies"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    director = Column(String, index=True)
    year = Column(Integer)
    rating = Column(Float, nullable=True)
    watched = Column(Boolean, default=False)
    review = Column(Text, nullable=True)
    review_public = Column(Boolean, default=False, nullable=False)
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
    review = Column(Text, nullable=True)
    review_public = Column(Boolean, default=False, nullable=False)
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
    review = Column(Text, nullable=True)
    review_public = Column(Boolean, default=False, nullable=False)
    poster_url = Column(String, nullable=True)
    
    # User relationship
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner = relationship("User", back_populates="anime")


class VideoGame(Base):
    """Video Game model with user ownership."""
    __tablename__ = "video_games"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    release_date = Column(DateTime, nullable=True)
    genres = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    played = Column(Boolean, default=False)
    review = Column(String, nullable=True)
    review_public = Column(Boolean, default=False, nullable=False)
    cover_art_url = Column(String, nullable=True)
    rawg_link = Column(String, nullable=True)
    
    # User relationship
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner = relationship("User", back_populates="video_games")


class Music(Base):
    """Music model with user ownership."""
    __tablename__ = "music"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    artist = Column(String, index=True)
    year = Column(Integer)
    genre = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    listened = Column(Boolean, default=False)
    review = Column(Text, nullable=True)
    review_public = Column(Boolean, default=False, nullable=False)
    cover_art_url = Column(String, nullable=True)
    
    # User relationship
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner = relationship("User", back_populates="music")


class Book(Base):
    """Book model with user ownership."""
    __tablename__ = "books"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    author = Column(String, index=True)
    year = Column(Integer)
    genre = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    read = Column(Boolean, default=False)
    review = Column(Text, nullable=True)
    review_public = Column(Boolean, default=False, nullable=False)
    cover_art_url = Column(String, nullable=True)
    
    # User relationship
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner = relationship("User", back_populates="books")


class NextUpItem(Base):
    """A user's ordered, private queue of existing library records.

    ``category`` plus ``item_id`` deliberately form a polymorphic reference: media
    records retain their existing tables and a queue entry never owns the media it
    points to. This makes the feature additive and safe for established libraries.
    """
    __tablename__ = "next_up_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String, nullable=False)
    item_id = Column(Integer, nullable=False)
    position = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="next_up_items")

    __table_args__ = (
        UniqueConstraint("user_id", "category", "item_id", name="uq_next_up_item"),
    )


class CompletionMoment(Base):
    """A private snapshot of when a user completed a library item.

    Media tables intentionally remain unchanged. The snapshot preserves the title
    and rating at the moment of completion so monthly replays stay meaningful even
    when the item is edited later.
    """
    __tablename__ = "completion_moments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String, nullable=False)
    item_id = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    rating = Column(Float, nullable=True)
    takeaway = Column(Text, nullable=True)
    favorite = Column(Boolean, nullable=False, default=False)
    completed_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    owner = relationship("User", back_populates="completion_moments")

    __table_args__ = (
        UniqueConstraint("user_id", "category", "item_id", name="uq_completion_moment_item"),
    )


class Collection(Base):
    """A private, cross-media shelf owned by one user."""
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    owner = relationship("User", back_populates="collections")
    items = relationship("CollectionItem", back_populates="collection", cascade="all, delete-orphan", order_by="CollectionItem.position")


class CollectionItem(Base):
    """An ordered polymorphic reference to an existing library item."""
    __tablename__ = "collection_items"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=False, index=True)
    category = Column(String, nullable=False)
    item_id = Column(Integer, nullable=False)
    position = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    collection = relationship("Collection", back_populates="items")

    __table_args__ = (
        UniqueConstraint("collection_id", "category", "item_id", name="uq_collection_item"),
    )


class FriendRequest(Base):
    """Friend request model for user friend requests."""
    __tablename__ = "friend_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String, default="pending", index=True)
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
    user1_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user2_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user1 = relationship("User", foreign_keys=[user1_id], back_populates="friendships_as_user1")
    user2 = relationship("User", foreign_keys=[user2_id], back_populates="friendships_as_user2")
    
    __table_args__ = (UniqueConstraint('user1_id', 'user2_id', name='_friendship_uc'),)


class Notification(Base):
    """Notification model for user notifications."""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String, nullable=False)
    message = Column(String, nullable=False)
    friend_request_id = Column(Integer, ForeignKey("friend_requests.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    read_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="notifications")
    friend_request = relationship("FriendRequest", back_populates="notifications")


class CustomTab(Base):
    __tablename__ = "custom_tabs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, index=True)
    source_type = Column(String, nullable=False, default="none")
    allow_uploads = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    owner = relationship("User", back_populates="custom_tabs")
    fields = relationship("CustomTabField", back_populates="tab", cascade="all, delete-orphan", order_by="CustomTabField.order")
    items = relationship("CustomTabItem", back_populates="tab", cascade="all, delete-orphan")


class CustomTabField(Base):
    __tablename__ = "custom_tab_fields"
    
    id = Column(Integer, primary_key=True, index=True)
    tab_id = Column(Integer, ForeignKey("custom_tabs.id"), nullable=False, index=True)
    key = Column(String, nullable=False)
    label = Column(String, nullable=False)
    field_type = Column(String, nullable=False)
    required = Column(Boolean, default=False, nullable=False)
    order = Column(Integer, nullable=False, default=0)
    
    tab = relationship("CustomTab", back_populates="fields")


class CustomTabItem(Base):
    __tablename__ = "custom_tab_items"
    
    id = Column(Integer, primary_key=True, index=True)
    tab_id = Column(Integer, ForeignKey("custom_tabs.id"), nullable=False, index=True)
    title = Column(String, nullable=False, index=True)
    field_values = Column(Text, nullable=True)
    poster_url = Column(String, nullable=True)
    poster_data = Column(LargeBinary, nullable=True)
    poster_mime_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tab = relationship("CustomTab", back_populates="items")
