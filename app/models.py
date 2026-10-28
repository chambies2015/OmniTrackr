"""
SQLAlchemy models for the OmniTrackr API.
Defines the User, Movie, TV Show, Anime, and Video Game ORM models.
"""
from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, Date, DateTime, UniqueConstraint, LargeBinary, Text, Index
from sqlalchemy.orm import deferred, relationship
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
    # The last day (UTC) the member opened OmniTrackr while signed in, and how many
    # different days they have. Sessions last 30 days, so a log-in alone misses most
    # returns. Older rows are empty until the member's next visit.
    last_seen_on = Column(Date, nullable=True)
    visit_days = Column(Integer, default=0, nullable=False)
    deactivated_at = Column(DateTime, nullable=True)
    # Google account id ("sub") for Sign in with Google; empty for password-only accounts.
    google_sub = Column(String, unique=True, index=True, nullable=True)
    # False only for accounts made with Google that have not chosen a password yet.
    # Older rows are empty (NULL), which means a password was chosen at sign-up.
    password_set = Column(Boolean, nullable=True)
    
    # Privacy settings
    movies_private = Column(Boolean, default=False, nullable=False)
    tv_shows_private = Column(Boolean, default=False, nullable=False)
    anime_private = Column(Boolean, default=False, nullable=False)
    video_games_private = Column(Boolean, default=False, nullable=False)
    music_private = Column(Boolean, default=False, nullable=False)
    books_private = Column(Boolean, default=False, nullable=False)
    manga_private = Column(Boolean, default=False, nullable=False)
    statistics_private = Column(Boolean, default=False, nullable=False)
    reviews_public = Column(Boolean, default=False, nullable=False)
    
    movies_visible = Column(Boolean, default=True, nullable=False)
    tv_shows_visible = Column(Boolean, default=True, nullable=False)
    anime_visible = Column(Boolean, default=True, nullable=False)
    video_games_visible = Column(Boolean, default=True, nullable=False)
    music_visible = Column(Boolean, default=True, nullable=False)
    books_visible = Column(Boolean, default=True, nullable=False)
    manga_visible = Column(Boolean, default=True, nullable=False)
    
    # Profile picture
    profile_picture_url = Column(String, nullable=True)
    # Deferred: up to a few hundred KB, read only when the picture itself is served.
    # Every signed-in request loads the member's row, and friend lists load many.
    profile_picture_data = deferred(Column(LargeBinary, nullable=True))
    profile_picture_mime_type = Column(String, nullable=True)
    
    movies = relationship("Movie", back_populates="owner", cascade="all, delete-orphan")
    tv_shows = relationship("TVShow", back_populates="owner", cascade="all, delete-orphan")
    anime = relationship("Anime", back_populates="owner", cascade="all, delete-orphan")
    video_games = relationship("VideoGame", back_populates="owner", cascade="all, delete-orphan")
    music = relationship("Music", back_populates="owner", cascade="all, delete-orphan")
    books = relationship("Book", back_populates="owner", cascade="all, delete-orphan")
    manga = relationship("Manga", back_populates="owner", cascade="all, delete-orphan")
    # Friends relationships
    sent_friend_requests = relationship("FriendRequest", foreign_keys="FriendRequest.sender_id", back_populates="sender", cascade="all, delete-orphan")
    received_friend_requests = relationship("FriendRequest", foreign_keys="FriendRequest.receiver_id", back_populates="receiver", cascade="all, delete-orphan")
    friendships_as_user1 = relationship("Friendship", foreign_keys="Friendship.user1_id", back_populates="user1", cascade="all, delete-orphan")
    friendships_as_user2 = relationship("Friendship", foreign_keys="Friendship.user2_id", back_populates="user2", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    custom_tabs = relationship("CustomTab", back_populates="owner", cascade="all, delete-orphan")
    next_up_items = relationship("NextUpItem", back_populates="owner", cascade="all, delete-orphan")
    progress_checkpoints = relationship("ProgressCheckpoint", back_populates="owner", cascade="all, delete-orphan")
    completion_moments = relationship("CompletionMoment", back_populates="owner", cascade="all, delete-orphan")
    activity_entries = relationship("ActivityEntry", back_populates="owner", cascade="all, delete-orphan")
    collections = relationship("Collection", back_populates="owner", cascade="all, delete-orphan")
    recommendation_requests = relationship("RecommendationRequest", back_populates="owner", cascade="all, delete-orphan")
    recommendation_invitations = relationship("RecommendationInvitation", back_populates="recipient", cascade="all, delete-orphan")

    @property
    def has_password(self) -> bool:
        """Whether the member knows a password for this account (see password_set)."""
        return self.password_set is not False


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
    # When the item entered the library. NULL means it predates add-date tracking.
    added_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    
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
    # When the item entered the library. NULL means it predates add-date tracking.
    added_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    
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
    # When the item entered the library. NULL means it predates add-date tracking.
    added_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    
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
    review = Column(Text, nullable=True)
    review_public = Column(Boolean, default=False, nullable=False)
    cover_art_url = Column(String, nullable=True)
    rawg_link = Column(String, nullable=True)
    # When the item entered the library. NULL means it predates add-date tracking.
    added_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    
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
    # When the item entered the library. NULL means it predates add-date tracking.
    added_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    
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
    # When the item entered the library. NULL means it predates add-date tracking.
    added_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    
    # User relationship
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner = relationship("User", back_populates="books")


class Manga(Base):
    """Manga, manhwa and manhua series with user ownership."""
    __tablename__ = "manga"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    author = Column(String, index=True, nullable=True)
    year = Column(Integer, nullable=True)
    genre = Column(String, nullable=True)
    volumes = Column(Integer, nullable=True)
    chapters = Column(Integer, nullable=True)
    rating = Column(Float, nullable=True)
    read = Column(Boolean, default=False)
    review = Column(Text, nullable=True)
    review_public = Column(Boolean, default=False, nullable=False)
    cover_art_url = Column(String, nullable=True)
    added_at = Column(DateTime, nullable=True, default=datetime.utcnow)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner = relationship("User", back_populates="manga")


class ProgressCheckpoint(Base):
    """Private stopping points, separate from all shareable media fields.

    Clearing a checkpoint retains a revision-only tombstone so another open tab
    cannot unknowingly recreate an outdated checkpoint after it was cleared.
    """
    __tablename__ = "progress_checkpoints"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String(16), nullable=False)
    item_id = Column(Integer, nullable=False)
    unit = Column(String(8), nullable=True)
    position = Column(Integer, nullable=True)
    season = Column(Integer, nullable=True)
    note = Column(String(300), nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    owner = relationship("User", back_populates="progress_checkpoints")

    __table_args__ = (
        UniqueConstraint("user_id", "category", "item_id", name="uq_progress_checkpoint_item"),
    )


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


class ReturnPromptDailyMetric(Base):
    """Anonymous daily totals for the optional Welcome Back Deck.

    These counters intentionally have no user, session, media, or page-history
    relationship. They answer whether the return experience is useful without
    creating another behavioral event stream.
    """
    __tablename__ = "return_prompt_daily_metrics"

    id = Column(Integer, primary_key=True, index=True)
    metric_date = Column(Date, nullable=False, unique=True, index=True)
    shown_count = Column(Integer, nullable=False, default=0)
    opened_count = Column(Integer, nullable=False, default=0)
    dismissed_count = Column(Integer, nullable=False, default=0)


class ReturnPromptEngagementReceipt(Base):
    """Anonymous, short-lived deduplication state for one return prompt.

    The digest is derived from a random signed token and cannot be joined to an
    account or media record. One token may record one impression and one terminal
    outcome (opened or dismissed).
    """
    __tablename__ = "return_prompt_engagement_receipts"

    id = Column(Integer, primary_key=True, index=True)
    token_digest = Column(String(64), nullable=False, index=True)
    event_kind = Column(String(16), nullable=False)
    action = Column(String(16), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("token_digest", "event_kind", name="uq_return_prompt_receipt_kind"),
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

    __table_args__ = (
        Index("ix_activity_entries_user_occurred_at", "user_id", "occurred_at"),
    )


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
    report_content_hash = Column(String, nullable=True)
    suspended_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    owner = relationship("User", back_populates="collections")
    items = relationship("CollectionItem", back_populates="collection", cascade="all, delete-orphan", order_by="CollectionItem.position")
    reactions = relationship("CollectionReaction", cascade="all, delete-orphan")
    reports = relationship("CollectionReport", cascade="all, delete-orphan")
    views = relationship("CollectionView", cascade="all, delete-orphan")
    save_receipts = relationship("CollectionSaveReceipt", cascade="all, delete-orphan")


class CollectionSaveReceipt(Base):
    """Remember an explicitly saved selection without coupling it to its source."""
    __tablename__ = "collection_save_receipts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # A source can be removed without removing or rewriting a reader's copy.
    source_collection_id = Column(Integer, nullable=False)
    selection_key = Column(String(64), nullable=False)
    collection_id = Column(Integer, ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "source_collection_id", "selection_key", name="uq_collection_save_selection"),
    )


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


class ReviewReaction(Base):
    """One "helpful" mark per browser for a public review (Oct 2026).

    A new table only: library tables are untouched. Like collection reactions, it
    stores a keyed hash of a signed browser cookie, never an IP address or user id.
    """
    __tablename__ = "review_reactions"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False)
    item_id = Column(Integer, nullable=False)
    visitor_hash = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("category", "item_id", "visitor_hash", name="uq_review_reaction_visitor"),
        Index("ix_review_reactions_item", "category", "item_id"),
    )


class ReviewSpoiler(Base):
    """A member marked their review of one library entry as containing spoilers (Oct 2026).

    A new table only: library tables are untouched. user_id guards against a reused
    item id inheriting someone else's flag.
    """
    __tablename__ = "review_spoilers"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False)
    item_id = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("category", "item_id", name="uq_review_spoiler_item"),
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
    # Optional same-site path the notification opens (e.g. a title page). NULL for older rows.
    link = Column(String, nullable=True)
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


class TakeRequest(Base):
    """A member's shareable "what did you think of this title?" link (title page ?take=<token>)."""
    __tablename__ = "take_requests"

    id = Column(Integer, primary_key=True, index=True)
    asker_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    title = Column(String, nullable=False)
    token = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)

    __table_args__ = (Index("ix_take_requests_asker_title", "asker_id", "kind", "slug"),)


class TakeResponse(Base):
    """One friend answered a take request with a public review (the asker is told once)."""
    __tablename__ = "take_responses"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("take_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    responder_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("request_id", "responder_id", name="uq_take_response_responder"),)


class FriendRecommendation(Base):
    """"You'd love this": one member recommends a title to a friend, or through a share link.

    A row with a recipient sits in that friend's inbox. A row without one is a share link
    (/r/<token>) for someone not on OmniTrackr yet; whoever opens it while signed in gets a
    copy in their own inbox (``source_id`` points back at the link). ``details`` holds only
    public facts about the title (never the sender's rating, review or notes).
    """
    __tablename__ = "friend_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    token = Column(String(48), unique=True, nullable=True, index=True)
    source_id = Column(Integer, ForeignKey("friend_recommendations.id", ondelete="SET NULL"), nullable=True, index=True)
    category = Column(String, nullable=False)
    title = Column(String, nullable=False)
    details = Column(Text, nullable=False, default="{}")
    image = Column(String, nullable=True)
    title_path = Column(String, nullable=True)
    note = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending", index=True)
    item_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    acted_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_friend_recommendations_inbox", "recipient_id", "status", "created_at"),
        UniqueConstraint("source_id", "recipient_id", name="uq_friend_recommendation_claim"),
    )


class FriendInvite(Base):
    """A member's reusable invite link (/join/<token>): whoever joins or accepts through it becomes their friend."""
    __tablename__ = "friend_invites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    token = Column(String(32), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class FriendInviteSignup(Base):
    """A new account created through an invite link; the friendship is made once the email is verified."""
    __tablename__ = "friend_invite_signups"

    id = Column(Integer, primary_key=True, index=True)
    inviter_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    invitee_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


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
    # Deferred like profile pictures: a tab's list can hold thousands of items and never shows the bytes.
    poster_data = deferred(Column(LargeBinary, nullable=True))
    poster_mime_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tab = relationship("CustomTab", back_populates="items")


class SiteTrafficDaily(Base):
    """Anonymous daily traffic totals for the owner's Site stats page.

    One row per (day, kind, key): kind is "total" (key "views" or "visitors"),
    "page" (a URL path), "source" (referring site), "device" or "audience".
    No user id, IP address, cookie or per-visit row is ever stored.
    """
    __tablename__ = "site_traffic_daily"
    __table_args__ = (UniqueConstraint("day", "kind", "key", name="uq_site_traffic_daily_day_kind_key"),)

    id = Column(Integer, primary_key=True, index=True)
    day = Column(Date, nullable=False, index=True)
    kind = Column(String(16), nullable=False)
    key = Column(String(200), nullable=False)
    count = Column(Integer, nullable=False, default=0)


class EmailDigestSubscription(Base):
    """A member's opt-in to the weekly "Coming up for you" email.

    A row exists only while the member is opted in; unsubscribing deletes it.
    The token powers the one-click unsubscribe link in every email.
    """
    __tablename__ = "email_digest_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    token = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_checked_at = Column(DateTime, nullable=True)
    last_sent_at = Column(DateTime, nullable=True)


class TitleMetadata(Base):
    """Cached public facts about a title (from Wikipedia/Wikidata, TVmaze, RAWG...).

    Keyed by "<category>:<normalized title>:<year>". Shared by every title page
    and never linked to a member.
    """
    __tablename__ = "title_metadata"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(300), nullable=False, unique=True, index=True)
    status = Column(String(16), nullable=False, default="ok")
    data = Column(Text, nullable=True)
    fetched_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PublicProfile(Base):
    """A member's opt-in public profile at /u/<username>.

    A row exists once the member has opened the settings; nothing is public
    unless ``enabled`` is true. Each section can be hidden separately, and the
    per-category privacy flags on the user always win.
    """
    __tablename__ = "public_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    enabled = Column(Boolean, nullable=False, default=False, index=True)
    bio = Column(String(280), nullable=True)
    show_stats = Column(Boolean, nullable=False, default=True)
    show_favorites = Column(Boolean, nullable=False, default=True)
    show_reviews = Column(Boolean, nullable=False, default=True)
    show_collections = Column(Boolean, nullable=False, default=True)
    # Opt-in diary of recent finishes and revisits (added Oct 2026, default off).
    show_diary = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmailCampaign(Base):
    """A one-time product update email (e.g. "What's new"), started by the site owner."""
    __tablename__ = "email_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(80), nullable=False, unique=True, index=True)
    status = Column(String(16), nullable=False, default="draft")  # draft, sending, paused, done
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class EmailCampaignSend(Base):
    """Who has been sent (or skipped for) a campaign, so nobody gets it twice."""
    __tablename__ = "email_campaign_sends"
    __table_args__ = (UniqueConstraint("campaign_key", "user_id", name="uq_email_campaign_send"),)

    id = Column(Integer, primary_key=True, index=True)
    campaign_key = Column(String(80), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(16), nullable=False, default="sent")  # sent, failed, test
    sent_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class EmailOptOut(Base):
    """A member who asked not to receive product update emails (account emails still go out)."""
    __tablename__ = "email_opt_outs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ProfileShowcaseItem(Base):
    """A library title a member pinned to the top of their public profile (Oct 2026). A new table only.

    ``category`` is a library category key ("movies", "books", ...) and ``item_id`` the row in
    that category's table. A pin whose title was deleted or whose category went private is
    skipped when the profile is shown, so nothing here can expose a hidden shelf.
    """
    __tablename__ = "profile_showcase_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(16), nullable=False)
    item_id = Column(Integer, nullable=False)
    position = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Supporter(Base):
    """A member who has supported OmniTrackr on Ko-fi (Oct 2026).

    A new table only: the users table is untouched. Perks are cosmetic and last
    while ``active_until`` is in the future; ``since`` is kept after a lapse so a
    returning supporter keeps their original date.
    """
    __tablename__ = "supporters"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    since = Column(DateTime, nullable=False, default=datetime.utcnow)
    active_until = Column(DateTime, nullable=False, default=datetime.utcnow)
    monthly = Column(Boolean, nullable=False, default=False)
    show_badge = Column(Boolean, nullable=False, default=True)
    accent = Column(String(16), nullable=True)
    # Opt-in: thanked by username on the public /supporters wall (added Oct 2026, default off).
    on_wall = Column(Boolean, nullable=False, default=False)
    # Optional banner art across the top of the public profile (added Oct 2026, default none).
    banner = Column(String(24), nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CalendarFeed(Base):
    """A member's private release calendar address (Oct 2026). A new table only.

    A row exists only while the feed is on; turning it off deletes the row, and a
    reset replaces the token so the old address stops working.
    """
    __tablename__ = "calendar_feeds"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    token = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_fetched_at = Column(DateTime, nullable=True)


class KofiPayment(Base):
    """One Ko-fi webhook delivery, kept so a retried delivery is never counted twice.

    The payer's email is stored only as a keyed hash so a payment made before the
    matching OmniTrackr account existed can still be linked later.
    """
    __tablename__ = "kofi_payments"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(80), nullable=False, unique=True, index=True)
    kind = Column(String(24), nullable=False)
    amount = Column(String(16), nullable=True)
    currency = Column(String(8), nullable=True)
    monthly = Column(Boolean, nullable=False, default=False)
    email_hash = Column(String(64), nullable=True, index=True)
    from_name = Column(String(80), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    linked_at = Column(DateTime, nullable=True)


class YearlyGoal(Base):
    """A member's private target for one year, e.g. finish 24 books in 2027 (Oct 2026).

    A new table only. Progress is never stored: it is counted from the same
    finishes Year in Review uses, so editing the library keeps it right.
    """
    __tablename__ = "yearly_goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    category = Column(String(16), nullable=False)
    target = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "year", "category", name="uq_yearly_goal"),)


class GoalAchievement(Base):
    """A yearly goal the member reached: the "goal reached" moment and its optional share link.

    A new table only. ``seen_at`` is set once the dashboard celebration is dismissed;
    ``share_token`` exists only while the member shares the achievement.
    """
    __tablename__ = "goal_achievements"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    category = Column(String(16), nullable=False)
    target = Column(Integer, nullable=False)
    reached_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    seen_at = Column(DateTime, nullable=True)
    share_token = Column(String(32), nullable=True, unique=True, index=True)

    __table_args__ = (UniqueConstraint("user_id", "year", "category", name="uq_goal_achievement"),)


class MonthlyChallengeEntry(Base):
    """A member who took a monthly challenge (Oct 2026), e.g. month "2026-10".

    A new table only. Progress is never stored: it is counted from the month's
    finishes. ``completed_at`` is set the first time every step is done,
    ``seen_at`` once the dashboard celebration is dismissed, and ``share_token``
    exists only while the member shares the completion.
    """
    __tablename__ = "monthly_challenge_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month = Column(String(7), nullable=False, index=True)
    joined_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    seen_at = Column(DateTime, nullable=True)
    share_token = Column(String(32), nullable=True, unique=True, index=True)

    __table_args__ = (UniqueConstraint("user_id", "month", name="uq_monthly_challenge_entry"),)


class YearInReviewShare(Base):
    """A member's opt-in public Year in Review link: a frozen snapshot at /recap/<token>.

    Nothing is public until the member shares, the snapshot leaves out private
    categories and all notes and reviews, and deleting the row ends the link.
    """
    __tablename__ = "year_in_review_shares"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    token = Column(String(32), nullable=False, unique=True, index=True)
    snapshot = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    owner = relationship("User")

    __table_args__ = (
        UniqueConstraint("user_id", "year", name="uq_year_in_review_share_year"),
    )


class ReleaseAlert(Base):
    """A release-day alert already sent: one row per member and Release Radar title (Oct 2026).

    A new table only. It keeps a member from being told twice about the same
    release, even after they dismiss the notification or the app restarts.
    """
    __tablename__ = "release_alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(16), nullable=False)
    item_key = Column(String(80), nullable=False)
    title = Column(String(200), nullable=False)
    release_date = Column(Date, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "category", "item_key", name="uq_release_alert"),)


class PushSubscription(Base):
    """A browser or installed app that asked for notifications on this device (Oct 2026).

    A new table only. Each row is one device's Web Push subscription; the
    endpoint is the push service URL the browser handed out. Removing a row
    just stops pushes to that device; the in-app bell is unaffected.
    """
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint = Column(String(1024), nullable=False, unique=True)
    p256dh = Column(String(128), nullable=False)
    auth = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_success_at = Column(DateTime, nullable=True)
    failure_count = Column(Integer, nullable=False, default=0)


class PushPreference(Base):
    """Which notifications a member wants pushed to their devices, and their quiet hours (Oct 2026).

    A new table only. Members without a row get the defaults in web_push.TOPICS.
    ``topics`` holds only the switches the member changed (JSON); ``held_since`` marks
    pushes held back during quiet hours, sent as one catch-up when the hours end.
    The bell is unaffected by anything here.
    """
    __tablename__ = "push_preferences"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    topics = Column(String(400), nullable=True)
    quiet_hours = Column(Boolean, nullable=False, default=True)
    quiet_start = Column(Integer, nullable=False, default=22)
    quiet_end = Column(Integer, nullable=False, default=8)
    time_zone = Column(String(64), nullable=True)
    held_since = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class WebPushKey(Base):
    """The site's own Web Push signing key (VAPID), created once on first use (Oct 2026).

    A single row (id 1). Browsers tie each subscription to this public key, so
    it must stay the same; the VAPID_PRIVATE_KEY environment variable, when set,
    is used instead.
    """
    __tablename__ = "web_push_keys"

    id = Column(Integer, primary_key=True)
    private_pem = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class UserBadge(Base):
    """The highest tier a member has reached on one badge track, e.g. Bookworm silver (Oct 2026).

    A new table only. Counts are never stored: they come from the library, so a
    badge always matches it. A tier only ever goes up; ``seen_at`` is set once the
    dashboard celebration is dismissed.
    """
    __tablename__ = "user_badges"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    badge = Column(String(24), nullable=False)
    tier = Column(Integer, nullable=False)
    earned_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    seen_at = Column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "badge", name="uq_user_badge"),)


class SharedList(Base):
    """A list a few members build together, e.g. a couple's watchlist (Oct 2026).

    New tables only. Items are title references (kind, title, year, art), not
    library rows, so nobody's library is read or changed by the list itself.
    ``token`` is the join link; resetting it retires the old link.
    """
    __tablename__ = "shared_lists"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    description = Column(String(300), nullable=True)
    token = Column(String(32), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    members = relationship("SharedListMember", cascade="all, delete-orphan", back_populates="shared_list")
    items = relationship("SharedListItem", cascade="all, delete-orphan", back_populates="shared_list")
    rounds = relationship("ClubRound", cascade="all, delete-orphan")


class SharedListMember(Base):
    """Someone who can see and add to a shared list. The owner has a row too."""
    __tablename__ = "shared_list_members"

    id = Column(Integer, primary_key=True, index=True)
    list_id = Column(Integer, ForeignKey("shared_lists.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    joined_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    # When the member last opened the list; titles added after it count as new for them.
    seen_at = Column(DateTime, nullable=True)

    shared_list = relationship("SharedList", back_populates="members")

    __table_args__ = (UniqueConstraint("list_id", "user_id", name="uq_shared_list_member"),)


class SharedListItem(Base):
    """One title on a shared list, with who added it and, once done, who marked it."""
    __tablename__ = "shared_list_items"

    id = Column(Integer, primary_key=True, index=True)
    list_id = Column(Integer, ForeignKey("shared_lists.id", ondelete="CASCADE"), nullable=False, index=True)
    added_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    kind = Column(String(10), nullable=False)
    title = Column(String(200), nullable=False)
    normalized = Column(String(200), nullable=False)
    year = Column(Integer, nullable=True)
    slug = Column(String(140), nullable=True)
    image = Column(String(500), nullable=True)
    note = Column(String(200), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    done_at = Column(DateTime, nullable=True)
    done_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    shared_list = relationship("SharedList", back_populates="items")
    votes = relationship("SharedListVote", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("list_id", "kind", "normalized", name="uq_shared_list_title"),)


class SharedListVote(Base):
    """A member saying "I'm in" for a title, so the list can put the most wanted first."""
    __tablename__ = "shared_list_votes"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("shared_list_items.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("item_id", "user_id", name="uq_shared_list_vote"),)


class ClubRound(Base):
    """One club pick on a shared list: everyone gets to a title by a date, then talks it over (Oct 2026).

    New tables only. The title is copied from the list item when the pick starts,
    so taking the item off the list later leaves the club's history readable.
    A list has at most one round with no ``ended_at`` at a time.
    """
    __tablename__ = "club_rounds"

    id = Column(Integer, primary_key=True, index=True)
    list_id = Column(Integer, ForeignKey("shared_lists.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("shared_list_items.id", ondelete="SET NULL"), nullable=True)
    started_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    kind = Column(String(10), nullable=False)
    title = Column(String(200), nullable=False)
    year = Column(Integer, nullable=True)
    slug = Column(String(140), nullable=True)
    image = Column(String(500), nullable=True)
    ends_on = Column(Date, nullable=False)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    progress = relationship("ClubProgress", cascade="all, delete-orphan")
    posts = relationship("ClubPost", cascade="all, delete-orphan")


class ClubProgress(Base):
    """Where one member is with a club pick: started or finished, with an optional 1-10 score."""
    __tablename__ = "club_progress"

    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey("club_rounds.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(10), nullable=False)  # started, finished
    score = Column(Integer, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("round_id", "user_id", name="uq_club_progress"),)


class ClubPost(Base):
    """A message in a club pick's discussion. Spoiler posts stay folded until the reader finishes."""
    __tablename__ = "club_posts"

    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey("club_rounds.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    body = Column(String(1000), nullable=False)
    spoiler = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ClubReminder(Base):
    """A finish-by nudge already sent to one member for one club pick (Oct 2026).

    New table only; it just keeps the nudge to once per member per pick.
    """
    __tablename__ = "club_reminders"

    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey("club_rounds.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    sent_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("round_id", "user_id", name="uq_club_reminder"),)


class FriendFeedEvent(Base):
    """A member finished, rated or reviewed a title already in their library (Oct 2026).

    New table only: library tables are untouched. Rows are written as the change is
    saved (see friend_feed.py) and only ever shown to friends while the library entry
    still says so and its category isn't private. Adds need no row: they come from
    each entry's added_at.
    """
    __tablename__ = "friend_feed_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(16), nullable=False)
    item_id = Column(Integer, nullable=False)
    kind = Column(String(10), nullable=False)  # finished, rated, reviewed
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (Index("ix_friend_feed_events_item", "user_id", "category", "item_id"),)


class FriendFeedCheer(Base):
    """A friend cheered one title on a member's feed. One per friend and title, and it stays."""
    __tablename__ = "friend_feed_cheers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(16), nullable=False)
    item_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "category", "item_id", name="uq_friend_feed_cheer"),
        Index("ix_friend_feed_cheers_item", "owner_id", "category", "item_id"),
    )


class FriendFeedSetting(Base):
    """Whether a member's updates appear in their friends' feeds. No row means they do.

    ``changed_at`` is when sharing was last switched; after switching back on, only
    updates from then on are shown, so nothing done while it was off resurfaces.
    """
    __tablename__ = "friend_feed_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    sharing = Column(Boolean, nullable=False, default=True)
    changed_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class WeeklyRoundup(Base):
    """A saved "New this week" roundup: one row per week, keyed by its Monday (Oct 2026).

    A new table only. ``payload`` is JSON: the week's Release Radar releases and
    anonymous member totals for that week, never a member's name or review. A row is
    rebuilt while its week is live and marked ``final`` a couple of days after, so
    the archive keeps each week as it was even after Release Radar moves on.
    """
    __tablename__ = "weekly_roundups"

    id = Column(Integer, primary_key=True, index=True)
    week_start = Column(Date, nullable=False, unique=True, index=True)
    payload = Column(Text, nullable=False)
    final = Column(Boolean, nullable=False, default=False)
    built_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class TitleDiscussion(Base):
    """A discussion thread on a public title page (/titles/<kind>/<slug>/discussions/<id>), Oct 2026.

    New tables only. ``kind`` and ``slug`` are the title page's address; the title
    itself is copied in so the thread stays readable if the page later changes or
    goes away. ``hidden_at`` is set by enough member reports or by a moderator;
    ``deleted_at`` when the author removes a thread that already has replies.
    """
    __tablename__ = "title_discussions"

    id = Column(Integer, primary_key=True, index=True)
    kind = Column(String(10), nullable=False)
    slug = Column(String(140), nullable=False)
    title = Column(String(200), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject = Column(String(140), nullable=False)
    body = Column(Text, nullable=False)
    spoiler = Column(Boolean, nullable=False, default=False)
    reply_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_activity_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    edited_at = Column(DateTime, nullable=True)
    locked_at = Column(DateTime, nullable=True)
    hidden_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    replies = relationship("TitleDiscussionReply", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_title_discussions_page", "kind", "slug", "last_activity_at"),)


class TitleDiscussionReply(Base):
    """A reply in a title discussion. Spoiler replies stay folded until the reader opens them."""
    __tablename__ = "title_discussion_replies"

    id = Column(Integer, primary_key=True, index=True)
    discussion_id = Column(Integer, ForeignKey("title_discussions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    body = Column(Text, nullable=False)
    spoiler = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    edited_at = Column(DateTime, nullable=True)
    hidden_at = Column(DateTime, nullable=True)


class TitleDiscussionReport(Base):
    """One member's report of a discussion thread or reply. One report per member per post."""
    __tablename__ = "title_discussion_reports"

    id = Column(Integer, primary_key=True, index=True)
    target = Column(String(10), nullable=False)  # thread, reply
    target_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reason = Column(String(20), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("target", "target_id", "user_id", name="uq_title_discussion_report"),)
