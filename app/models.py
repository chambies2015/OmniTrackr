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
    last_login_at = Column(DateTime, nullable=True)
    login_count = Column(Integer, default=0, nullable=False)
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
    activity_entries = relationship("ActivityEntry", back_populates="owner", cascade="all, delete-orphan")
    collections = relationship("Collection", back_populates="owner", cascade="all, delete-orphan")
    recommendation_requests = relationship("RecommendationRequest", back_populates="owner", cascade="all, delete-orphan")
    recommendation_invitations = relationship("RecommendationInvitation", back_populates="recipient", cascade="all, delete-orphan")


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


class ActivityEntry(Base):
    """A private, append-only snapshot in a user's cross-media journal.

    The polymorphic media reference is deliberately not a foreign key. Journal
    history keeps its title snapshot even when the underlying library item is
    renamed or removed, and existing media tables do not need to change.
    """
    __tablename__ = "activity_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String, nullable=False, index=True)
    item_id = Column(Integer, nullable=True)
    title = Column(String, nullable=False)
    action = Column(String, nullable=False, index=True)
    note = Column(Text, nullable=True)
    rating = Column(Float, nullable=True)
    source = Column(String, nullable=False, default="manual")
    occurred_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    owner = relationship("User", back_populates="activity_entries")


class Collection(Base):
    """A private-by-default, cross-media shelf owned by one user."""
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    cover_url = Column(String, nullable=True)
    is_public = Column(Boolean, nullable=False, default=False, index=True)
    moderation_status = Column(String, nullable=False, default="pending", index=True)
    approved_at = Column(DateTime, nullable=True)
    approved_content_hash = Column(String, nullable=True)
    published_at = Column(DateTime, nullable=True)
    view_count = Column(Integer, nullable=False, default=0)
    helpful_count = Column(Integer, nullable=False, default=0)
    report_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    owner = relationship("User", back_populates="collections")
    items = relationship("CollectionItem", back_populates="collection", cascade="all, delete-orphan", order_by="CollectionItem.position")
    reactions = relationship("CollectionReaction", cascade="all, delete-orphan")
    reports = relationship("CollectionReport", cascade="all, delete-orphan")
    views = relationship("CollectionView", cascade="all, delete-orphan")


class CollectionItem(Base):
    """An ordered polymorphic reference to an existing library item."""
    __tablename__ = "collection_items"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=False, index=True)
    category = Column(String, nullable=False)
    item_id = Column(Integer, nullable=False)
    position = Column(Integer, nullable=False, default=0)
    curator_note = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    collection = relationship("Collection", back_populates="items")

    __table_args__ = (
        UniqueConstraint("collection_id", "category", "item_id", name="uq_collection_item"),
    )


class CollectionReaction(Base):
    """Privacy-preserving, one-per-browser helpful feedback."""
    __tablename__ = "collection_reactions"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=False, index=True)
    visitor_hash = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("collection_id", "visitor_hash", name="uq_collection_reaction_visitor"),
    )


class CollectionView(Base):
    """Deduplicated public collection view without storing an IP address."""
    __tablename__ = "collection_views"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=False, index=True)
    visitor_hash = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("collection_id", "visitor_hash", name="uq_collection_view_visitor"),
    )


class CollectionReport(Base):
    """A bounded abuse report for a deliberately public collection."""
    __tablename__ = "collection_reports"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=False, index=True)
    visitor_hash = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("collection_id", "visitor_hash", name="uq_collection_report_visitor"),
    )


class PublicReviewState(Base):
    """Automated report state for one exact version of an opt-in public review."""
    __tablename__ = "public_review_states"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String, nullable=False, index=True)
    item_id = Column(Integer, nullable=False, index=True)
    content_hash = Column(String, nullable=False)
    report_count = Column(Integer, nullable=False, default=0)
    suspended_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    reports = relationship("PublicReviewReport", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("category", "item_id", name="uq_public_review_state_item"),
    )


class PublicReviewReport(Base):
    """One bounded report per signed browser for a public review version."""
    __tablename__ = "public_review_reports"

    id = Column(Integer, primary_key=True, index=True)
    state_id = Column(Integer, ForeignKey("public_review_states.id", ondelete="CASCADE"), nullable=False, index=True)
    visitor_hash = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("state_id", "visitor_hash", name="uq_public_review_report_visitor"),
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


class RecommendationRequest(Base):
    """An owner's expiring prompt for tightly scoped media recommendations."""
    __tablename__ = "recommendation_requests"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    public_token = Column(String, unique=True, nullable=False, index=True)
    prompt = Column(String, nullable=False)
    allowed_categories = Column(String, nullable=False)
    max_responses = Column(Integer, nullable=False, default=10)
    status = Column(String, nullable=False, default="open", index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    owner = relationship("User", back_populates="recommendation_requests")
    submissions = relationship("RecommendationSubmission", back_populates="request", cascade="all, delete-orphan")
    invitations = relationship("RecommendationInvitation", back_populates="request", cascade="all, delete-orphan")


class RecommendationSubmission(Base):
    """A suggestion awaiting an explicit owner decision."""
    __tablename__ = "recommendation_submissions"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("recommendation_requests.id"), nullable=False, index=True)
    recommender_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    guest_name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    title = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending", index=True)
    accepted_item_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    request = relationship("RecommendationRequest", back_populates="submissions")


class RecommendationInvitation(Base):
    """Private delivery of a postcard prompt to an existing friend."""
    __tablename__ = "recommendation_invitations"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("recommendation_requests.id"), nullable=False, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    request = relationship("RecommendationRequest", back_populates="invitations")
    recipient = relationship("User", back_populates="recommendation_invitations")

    __table_args__ = (
        UniqueConstraint("request_id", "recipient_id", name="uq_recommendation_invitation"),
    )


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
