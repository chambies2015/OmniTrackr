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
    podcasts_private = Column(Boolean, default=False, nullable=False)
    audiobooks_private = Column(Boolean, default=False, nullable=False)
    statistics_private = Column(Boolean, default=False, nullable=False)
    reviews_public = Column(Boolean, default=False, nullable=False)
    
    movies_visible = Column(Boolean, default=True, nullable=False)
    tv_shows_visible = Column(Boolean, default=True, nullable=False)
    anime_visible = Column(Boolean, default=True, nullable=False)
    video_games_visible = Column(Boolean, default=True, nullable=False)
    music_visible = Column(Boolean, default=True, nullable=False)
    books_visible = Column(Boolean, default=True, nullable=False)
    manga_visible = Column(Boolean, default=True, nullable=False)
    podcasts_visible = Column(Boolean, default=True, nullable=False)
    audiobooks_visible = Column(Boolean, default=True, nullable=False)
    
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
    podcasts = relationship("Podcast", back_populates="owner", cascade="all, delete-orphan")
    audiobooks = relationship("Audiobook", back_populates="owner", cascade="all, delete-orphan")
    # Friends relationships
    sent_friend_requests = relationship("FriendRequest", foreign_keys="FriendRequest.sender_id", back_populates="sender", cascade="all, delete-orphan")
    received_friend_requests = relationship("FriendRequest", foreign_keys="FriendRequest.receiver_id", back_populates="receiver", cascade="all, delete-orphan")
    friendships_as_user1 = relationship("Friendship", foreign_keys="Friendship.user1_id", back_populates="user1", cascade="all, delete-orphan")
    friendships_as_user2 = relationship("Friendship", foreign_keys="Friendship.user2_id", back_populates="user2", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    custom_tabs = relationship("CustomTab", back_populates="owner", cascade="all, delete-orphan")
    next_up_items = relationship("NextUpItem", back_populates="owner", cascade="all, delete-orphan")
    progress_checkpoints = relationship("ProgressCheckpoint", back_populates="owner", cascade="all, delete-orphan")
    library_tags = relationship("LibraryTag", back_populates="owner", cascade="all, delete-orphan")
    saved_library_views = relationship("SavedLibraryView", back_populates="owner", cascade="all, delete-orphan")
    title_origins = relationship("TitleOrigin", back_populates="owner", cascade="all, delete-orphan",
                                 foreign_keys="TitleOrigin.user_id")
    game_playtimes = relationship("GamePlaytime", back_populates="owner", cascade="all, delete-orphan")
    episode_notes = relationship("EpisodeNote", back_populates="owner", cascade="all, delete-orphan")
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


class Podcast(Base):
    """Podcast shows with user ownership."""
    __tablename__ = "podcasts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    host = Column(String, index=True, nullable=True)
    year = Column(Integer, nullable=True)
    genre = Column(String, nullable=True)
    episodes = Column(Integer, nullable=True)
    rating = Column(Float, nullable=True)
    listened = Column(Boolean, default=False)
    review = Column(Text, nullable=True)
    review_public = Column(Boolean, default=False, nullable=False)
    cover_art_url = Column(String, nullable=True)
    added_at = Column(DateTime, nullable=True, default=datetime.utcnow)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner = relationship("User", back_populates="podcasts")


class Audiobook(Base):
    """Audiobooks with user ownership. Length is the full runtime in hours."""
    __tablename__ = "audiobooks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    author = Column(String, index=True, nullable=True)
    narrator = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    genre = Column(String, nullable=True)
    length_hours = Column(Float, nullable=True)
    rating = Column(Float, nullable=True)
    listened = Column(Boolean, default=False)
    review = Column(Text, nullable=True)
    review_public = Column(Boolean, default=False, nullable=False)
    cover_art_url = Column(String, nullable=True)
    added_at = Column(DateTime, nullable=True, default=datetime.utcnow)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner = relationship("User", back_populates="audiobooks")


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


class LibraryTag(Base):
    """A private label on one library record, such as "comfort watch" or "with Sam".

    It points at the record the same way NextUpItem does, so the media tables are
    untouched. ``label_key`` is the casefolded label: "Cozy" and "cozy" are one tag.
    """
    __tablename__ = "library_tags"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String(16), nullable=False)
    item_id = Column(Integer, nullable=False)
    label = Column(String(32), nullable=False)
    label_key = Column(String(32), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    owner = relationship("User", back_populates="library_tags")

    __table_args__ = (
        UniqueConstraint("user_id", "category", "item_id", "label_key", name="uq_library_tag_item"),
        Index("ix_library_tags_user_category_key", "user_id", "category", "label_key"),
    )


class SavedLibraryView(Base):
    """A named search, sort and filter combination for one shelf. Private to its owner."""
    __tablename__ = "saved_library_views"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String(16), nullable=False)
    name = Column(String(40), nullable=False)
    name_key = Column(String(40), nullable=False)
    # JSON: search, sort, completion, unrated, has_progress, tag.
    filters = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    owner = relationship("User", back_populates="saved_library_views")

    __table_args__ = (
        UniqueConstraint("user_id", "category", "name_key", name="uq_saved_library_view_name"),
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
    # Set by Start on the queue. NULL means not started yet, which is every row
    # that existed before the column did.
    started_at = Column(DateTime, nullable=True)

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
    # Nov 2026: a list can be shared by an unguessable link before it is ready for the
    # gallery (never indexed), and can be marked as ranked so pages show #1, #2, #3.
    link_token = Column(String(32), nullable=True, unique=True, index=True)
    ranked = Column(Boolean, nullable=False, default=False)

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
    # The member chose to send a taste test: /join/<token> lets visitors rate a few of their
    # rated titles first. Off for every link until the member presses "Send a taste test".
    taste_test = Column(Boolean, nullable=False, default=False)


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


class TitleCredit(Base):
    """One person or company credited on a title, read from its cached public facts.

    Rebuilt from title_metadata whenever a title's facts are stored, so the people
    and studio pages can find every title someone worked on without re-reading
    every cached blob. Never linked to a member.
    """
    __tablename__ = "title_credits"

    id = Column(Integer, primary_key=True, index=True)
    metadata_key = Column(String(300), nullable=False, index=True)
    kind = Column(String(16), nullable=False)
    entity = Column(String(8), nullable=False)  # person, studio
    role = Column(String(32), nullable=False)
    name = Column(String(200), nullable=False)
    slug = Column(String(130), nullable=False)

    __table_args__ = (Index("ix_title_credits_entity_slug", "entity", "slug"),
                      UniqueConstraint("metadata_key", "entity", "role", "slug", name="uq_title_credit"))


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
    # Opt-in "compare tastes with me" link at /u/<name>/match (added Oct 2026, default off).
    show_taste_match = Column(Boolean, nullable=False, default=False)
    # Opt-in "Right now" shelf: what the member started from their Up next queue and what's next (Nov 2026, default off).
    show_now = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProfileWidgetLoad(Base):
    """How many times a member's embedded widgets were loaded on a day, per widget and site (Nov 2026).

    ``host`` is only the host name of the page showing the widget ("myanimelist.net"),
    a known image proxy ("github.com" for GitHub's image cache), "" when the request
    named no page, or "other". No page address, IP address or browser is stored.
    """
    __tablename__ = "profile_widget_loads"
    __table_args__ = (UniqueConstraint("user_id", "day", "kind", "host", name="uq_profile_widget_load"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    day = Column(Date, nullable=False, index=True)
    kind = Column(String(16), nullable=False)
    host = Column(String(64), nullable=False, default="")
    loads = Column(Integer, nullable=False, default=0)


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
    # A line from the member on why this title is pinned (Nov 2026). NULL for every older pin.
    note = Column(String(140), nullable=True)


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
    # Monthly Ko-fi membership (added Oct 28): the tier slug from the latest membership payment and
    # when the membership runs out. NULL for one-time supporters.
    tier = Column(String(24), nullable=True)
    member_until = Column(DateTime, nullable=True)
    # Season Pass and up can let their banner move. Off by default.
    banner_motion = Column(Boolean, nullable=False, default=False)
    # Nov 2026: a color theme for the member's own app and a frame around their profile picture.
    # Both NULL by default, so nothing changes until a supporter picks one.
    app_theme = Column(String(24), nullable=True)
    avatar_frame = Column(String(24), nullable=True)
    # Nov 23 2026: the supporter's number, in the order members first supported (#1 is the first).
    # Given once when the row is made and never changed, so a badge's number stays put. NULL only
    # until the startup migration numbers older rows.
    number = Column(Integer, nullable=True)
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
    # Weekly episodes of unfinished shows (Oct 28). Feeds made before then keep
    # their old contents (the migration adds FALSE); new feeds start with it on.
    include_episodes = Column(Boolean, nullable=False, default=True)


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
    # Ko-fi's tier name on membership payments (added Oct 28). NULL for tips and older rows.
    tier_name = Column(String(40), nullable=True)
    email_hash = Column(String(64), nullable=True, index=True)
    from_name = Column(String(80), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    linked_at = Column(DateTime, nullable=True)
    # Added Oct 30, all nullable or off, so older rows read exactly as before.
    # A second keyed hash of the payer's email with Gmail dots and "+tags" taken out, so
    # j.doe+kofi@gmail.com still finds jdoe@gmail.com.
    email_key = Column(String(64), nullable=True, index=True)
    # Keyed hash of Ko-fi's transaction id (on the payer's receipt), for "I donated but don't see my badge".
    transaction_hash = Column(String(64), nullable=True, index=True)
    # Ko-fi's "Send a test" button. Recorded so the owner can see the webhook works, never linked or counted.
    test = Column(Boolean, nullable=False, default=False)
    # The site owner set it aside (a refund, a duplicate...). It stays recorded but leaves the "to link" list.
    dismissed_at = Column(DateTime, nullable=True)
    # A member who matched this payment's transaction id and asked for it; the owner confirms with one click.
    claimed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    claimed_at = Column(DateTime, nullable=True)


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


class YearPledge(Base):
    """A member who signed up for a New Year challenge, e.g. the 2027 challenge (Nov 2026).

    A new table only. The targets themselves are ordinary ``YearlyGoal`` rows, so
    leaving the challenge keeps the goals. ``share_token`` exists only while the
    member shares their pledge card.
    """
    __tablename__ = "year_pledges"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    share_token = Column(String(32), nullable=True, unique=True, index=True)

    __table_args__ = (UniqueConstraint("user_id", "year", name="uq_year_pledge"),)


class AwardBallot(Base):
    """A member's picks for one awards show, e.g. The Game Awards 2026 (Nov 2026).

    A new table only. ``picks`` is a JSON object of category key to nominee key,
    checked against the show's data (app/awards_data.py) on every save. A row with
    no picks is a member who asked to hear when the nominees are in.
    ``share_token`` exists only while the member shares the ballot.
    """
    __tablename__ = "award_ballots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    show = Column(String(60), nullable=False, index=True)
    picks = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    share_token = Column(String(32), nullable=True, unique=True, index=True)
    # Set once each, when the "nominees are in" and "winners are in" notes go out.
    opened_notice_at = Column(DateTime, nullable=True)
    results_notice_at = Column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "show", name="uq_award_ballot"),)


class AwardResult(Base):
    """The winner of one category of an awards show, entered by a site admin on the night.

    A new table only. A winner written into the show's data wins over a row here.
    """
    __tablename__ = "award_results"

    id = Column(Integer, primary_key=True, index=True)
    show = Column(String(60), nullable=False, index=True)
    category = Column(String(80), nullable=False)
    nominee = Column(String(120), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("show", "category", name="uq_award_result"),)


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


class EpisodeAlert(Base):
    """A new-episode notification already sent: one row per member and episode (Oct 2026).

    A new table only. ``episode_key`` names the episode the way the episode
    calendar cache does (source and id, season and number), so a member is told
    about an episode once even if the air time moves or the app restarts.
    """
    __tablename__ = "episode_alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    episode_key = Column(String(80), nullable=False)
    title = Column(String(200), nullable=False)
    aired_on = Column(Date, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "episode_key", name="uq_episode_alert"),)


class PushNudge(Base):
    """A reminder pushed to a member who had been away for a while (Oct 2026).

    A new table only. Nothing is shown in the bell for these; the rows exist so
    a member gets at most one every couple of weeks and none at all once two
    went unanswered.
    """
    __tablename__ = "push_nudges"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(24), nullable=False)
    sent_at = Column(DateTime, nullable=False, default=datetime.utcnow)


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


class TonightPoll(Base):
    """A "what should we watch tonight?" poll a member shares by link (Oct 2026).

    New tables only. Options copy the title (kind, name, year, art) when the poll is
    made, so nothing here reads or changes anyone's library. Anyone with the link can
    vote, members by account and visitors by their signed browser cookie.
    """
    __tablename__ = "tonight_polls"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(32), nullable=False, unique=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    question = Column(String(120), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    closes_at = Column(DateTime, nullable=False)
    # Set when the poll closes, early by the owner or on the first look after closes_at.
    closed_at = Column(DateTime, nullable=True)
    winner_id = Column(Integer, nullable=True)
    # Nov 2026: the poll this one is another round of. Polls made before then keep NULL.
    previous_id = Column(Integer, nullable=True, index=True)

    options = relationship("TonightPollOption", cascade="all, delete-orphan", order_by="TonightPollOption.position")
    votes = relationship("TonightPollVote", cascade="all, delete-orphan")


class TonightPollOption(Base):
    """One title on a poll, copied in when the poll was made."""
    __tablename__ = "tonight_poll_options"

    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer, ForeignKey("tonight_polls.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False, default=0)
    kind = Column(String(10), nullable=False)
    title = Column(String(200), nullable=False)
    year = Column(Integer, nullable=True)
    slug = Column(String(140), nullable=True)
    image = Column(String(500), nullable=True)


class TonightPollVote(Base):
    """One voter's choice. A member votes by account, a visitor by a keyed hash of their browser cookie."""
    __tablename__ = "tonight_poll_votes"

    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer, ForeignKey("tonight_polls.id", ondelete="CASCADE"), nullable=False, index=True)
    option_id = Column(Integer, ForeignKey("tonight_poll_options.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    visitor = Column(String(64), nullable=True)
    # The name a visitor typed so friends know who voted. Members show their username.
    name = Column(String(30), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("poll_id", "user_id", name="uq_tonight_vote_member"),
                      UniqueConstraint("poll_id", "visitor", name="uq_tonight_vote_visitor"))


class TierListShare(Base):
    """A tier list someone turned into a link (Nov 2026). New table only.

    The board is a copy of what the maker ranked (titles, years, art), so nothing here
    reads or changes anyone's library. A member's links belong to their account; links
    made without an account have no owner, are edited with a key kept in the maker's
    browser and stop working at ``expires_at`` unless a new account claims them.
    """
    __tablename__ = "tier_list_shares"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(32), nullable=False, unique=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    # Keyed hash of the maker's browser cookie, only for capping links made without an account.
    visitor = Column(String(64), nullable=True, index=True)
    # SHA-256 of the edit key the maker's browser holds.
    key_hash = Column(String(64), nullable=False)
    name = Column(String(80), nullable=False)
    board = Column(Text, nullable=False)  # JSON: {"labels": {...}, "tiers": {"S": [item, ...], ...}}
    item_count = Column(Integer, nullable=False, default=0)
    template_key = Column(String(60), nullable=True)
    # The shared list this one ranks the same titles as. No foreign key: deleting the
    # original leaves the copies standing.
    source_id = Column(Integer, nullable=True, index=True)
    views = Column(Integer, nullable=False, default=0)
    remixes = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True, index=True)


class TitleOrigin(Base):
    """Why a member added one library record: who recommended it, or where they heard of it.

    Private to the owner. It points at the record the way LibraryTag does. ``friend_id``
    links a friend's account; ``who`` keeps the name as typed (or the friend's username
    at the time), so the credit survives the friend leaving. ``who_key`` is the
    casefolded ``who`` used to group and filter by recommender.
    """
    __tablename__ = "title_origins"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(16), nullable=False)
    item_id = Column(Integer, nullable=False)
    # friend, person, article, video, browsing or other.
    source = Column(String(16), nullable=False)
    friend_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    who = Column(String(60), nullable=True)
    who_key = Column(String(60), nullable=True)
    note = Column(String(280), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    owner = relationship("User", back_populates="title_origins", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("user_id", "category", "item_id", name="uq_title_origin_item"),
        Index("ix_title_origins_user_who", "user_id", "who_key"),
    )


class GamePlaytime(Base):
    """Minutes a member has really played one library game, as reported by a store.

    Written by the Steam import and refreshed each time the member imports again. It
    points at the record the way LibraryTag does (``item_id`` on the video games shelf).
    ``external_id`` is the store's own id (a Steam app id), used for store links.
    Time spent counts these minutes instead of an estimate.
    """
    __tablename__ = "game_playtimes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(Integer, nullable=False)
    source = Column(String(16), nullable=False, default="steam")
    external_id = Column(String(32), nullable=True)
    minutes = Column(Integer, nullable=False, default=0)
    synced_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    owner = relationship("User", back_populates="game_playtimes")

    __table_args__ = (
        UniqueConstraint("user_id", "item_id", "source", name="uq_game_playtime_item_source"),
    )


class EpisodeNote(Base):
    """A member's private rating and note for one episode of a show or anime (Nov 2026).

    A new table only: the show's own rating, review and progress checkpoint are
    never read or changed by it. It points at the library record the way
    ProgressCheckpoint does. ``episode_key`` names the episode as the episode
    guide numbers it: ``s2e4`` inside a season, ``e12`` for a show numbered
    straight through, ``s0e3`` for a special.
    """
    __tablename__ = "episode_notes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(16), nullable=False)
    item_id = Column(Integer, nullable=False)
    episode_key = Column(String(24), nullable=False)
    season = Column(Integer, nullable=True)
    episode = Column(Integer, nullable=False)
    rating = Column(Integer, nullable=True)
    note = Column(String(1000), nullable=True)
    spoiler = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    owner = relationship("User", back_populates="episode_notes")

    __table_args__ = (
        UniqueConstraint("user_id", "category", "item_id", "episode_key", name="uq_episode_note"),
        Index("ix_episode_notes_item", "user_id", "category", "item_id"),
    )


class MemberFollow(Base):
    """One member following another member's public profile (Oct 2026).

    One-way and separate from friendship. A follower only ever sees what the
    profile already shows anyone (see follows.py), so a row grants no access.
    Rows are kept while either account is deactivated and simply hidden, so a
    member who comes back within the reactivation window keeps their follows.
    """
    __tablename__ = "member_follows"

    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    followed_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("follower_id", "followed_id", name="uq_member_follow"),
    )


class FollowSetting(Base):
    """A member's follower settings. No row means the defaults (followers allowed, email section on)."""
    __tablename__ = "follow_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    allow_followers = Column(Boolean, nullable=False, default=True)
    # The "From people you follow" section of the weekly email.
    email_following = Column(Boolean, nullable=False, default=True)
    # Whether Find people may suggest this profile to members with similar taste (Nov 2026).
    # Only ever matters while the public profile is on and followers are allowed.
    suggest_me = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class FollowBar(Base):
    """A follower the member removed. They can't follow that member again until the member undoes it."""
    __tablename__ = "follow_bars"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    barred_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("owner_id", "barred_id", name="uq_follow_bar"),
    )


class PeopleSuggestionDismissal(Base):
    """Someone a member pressed "Not for me" on in Find people (Nov 2026). Private to the member.

    A new table only. It hides that person from the member's suggestions and nothing else:
    the other member is never told, and following them from their profile still works.
    """
    __tablename__ = "people_suggestion_dismissals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    dismissed_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "dismissed_id", name="uq_people_suggestion_dismissal"),
    )


class UserTwoFactor(Base):
    """A member's optional two-factor sign-in with an authenticator app (Oct 2026).

    A new table only; members without a row sign in exactly as before. A row with
    no ``enabled_at`` is a setup that was started but not confirmed with a code.
    ``secret_encrypted`` and ``recovery_codes`` (a JSON list of keyed hashes, one
    removed per use) are handled in app/two_factor.py. Bumping ``trusted_epoch``
    makes every remembered browser ask for a code again.
    """
    __tablename__ = "user_two_factor"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    secret_encrypted = Column(Text, nullable=False)
    enabled_at = Column(DateTime, nullable=True)
    last_used_step = Column(Integer, nullable=True)
    recovery_codes = Column(Text, nullable=True)
    recovery_codes_created_at = Column(DateTime, nullable=True)
    trusted_epoch = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class SignupCodeAttempt(Base):
    """Wrong confirmation codes typed for one new account (Nov 2026).

    A new table only; accounts without a row never typed a wrong code. The emailed
    6-digit code (email.signup_code) works until ``failures`` reaches
    routers.auth.SIGNUP_CODE_MAX_FAILURES; after that only the link in the email
    confirms the account. Never reset by a new email, so guesses can't be spread
    over many codes.
    """
    __tablename__ = "signup_code_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    failures = Column(Integer, nullable=False, default=0)
    last_failed_at = Column(DateTime, nullable=True)


class MemberStart(Base):
    """How a new member used the start page (/start) in their first session (Oct 2026).

    A new table only; members without a row never saw the page. Each timestamp is
    set once, the first time that step happens, so every Site stats counter for
    the page counts a member at most once.
    """
    __tablename__ = "member_starts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    opened_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    quick_add_at = Column(DateTime, nullable=True)
    search_at = Column(DateTime, nullable=True)
    import_at = Column(DateTime, nullable=True)
    quiz_at = Column(DateTime, nullable=True)
    first_saved_at = Column(DateTime, nullable=True)
    reached_five_at = Column(DateTime, nullable=True)
    next_step_at = Column(DateTime, nullable=True)
    skipped_at = Column(DateTime, nullable=True)


class UsedPasskeyChallenge(Base):
    """Successful ceremonies retain a replay marker until their signed cookie expires."""
    __tablename__ = "used_passkey_challenges"

    digest = Column(String(64), primary_key=True)
    used_at = Column(DateTime, nullable=False, index=True)


class UserPasskey(Base):
    """A passkey (WebAuthn credential) a member can log in with (Oct 2026).

    A new table only; members without a row log in exactly as before. We keep the
    public key and credential id the browser handed us, a counter that must only
    go up for hardware keys, and the flags that say whether the passkey is synced
    (backed up) across the member's devices. See app/passkeys.py.
    """
    __tablename__ = "user_passkeys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    credential_id = Column(String(1400), nullable=False, unique=True, index=True)
    public_key = Column(Text, nullable=False)
    sign_count = Column(Integer, nullable=False, default=0)
    name = Column(String(60), nullable=False, default="Passkey")
    transports = Column(Text, nullable=True)
    aaguid = Column(String(36), nullable=True)
    backup_eligible = Column(Boolean, nullable=False, default=False)
    backed_up = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)


class ForYouDismissal(Base):
    """A title a member marked "Not for me" in their For you picks, so it stops coming back.

    Keyed by the pick id ("movie/interstellar-2014"); touches nothing in the library.
    """
    __tablename__ = "for_you_dismissals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title_key = Column(String(160), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "title_key", name="uq_for_you_dismissal"),
    )


class GiftList(Base):
    """A member's holiday gift list, shared with family through one link (Nov 2026).

    New tables only. Items are copies of a title or a typed idea, never library rows,
    so the list never reads or changes the library once an item is on it. ``token``
    is the share link; replacing it retires the old link, and ``shared`` turns it off.
    """
    __tablename__ = "gift_lists"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    token = Column(String(32), unique=True, nullable=False, index=True)
    message = Column(String(200), nullable=True)
    shared = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    items = relationship("GiftListItem", cascade="all, delete-orphan", back_populates="gift_list",
                         order_by="GiftListItem.id")


class GiftListItem(Base):
    """One wish on a gift list: a title (kind is a title kind) or a typed idea (kind "other").

    ``claim_hash`` is the SHA-256 of a key held by whoever marked it as theirs to buy,
    so they can undo it. The list's owner is never shown claims.
    """
    __tablename__ = "gift_list_items"

    id = Column(Integer, primary_key=True, index=True)
    list_id = Column(Integer, ForeignKey("gift_lists.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(10), nullable=False)
    title = Column(String(200), nullable=False)
    normalized = Column(String(200), nullable=False)
    year = Column(Integer, nullable=True)
    creator = Column(String(120), nullable=True)
    image = Column(String(500), nullable=True)
    # Amazon search words and department for gifts from the guide; None means "use the title".
    search = Column(String(150), nullable=True)
    store = Column(String(20), nullable=True)
    note = Column(String(120), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    claimed_at = Column(DateTime, nullable=True)
    claim_hash = Column(String(64), nullable=True)

    gift_list = relationship("GiftList", back_populates="items")

    __table_args__ = (UniqueConstraint("list_id", "kind", "normalized", name="uq_gift_list_item"),)


class ReviewShareChoice(Base):
    """A member's answer to the "Share your reviews" card for one private review (Nov 2026).

    New table only. The library row changes only when the member presses Share, which sets
    review_public exactly as the library editor's Public switch does. "kept" means the member
    chose to keep that review private, so the card stops asking until the review is rewritten
    (content_hash is the review text the member was shown).
    """
    __tablename__ = "review_share_choices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(16), nullable=False)
    item_id = Column(Integer, nullable=False)
    choice = Column(String(8), nullable=False)  # shared, kept
    content_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (UniqueConstraint("user_id", "category", "item_id", name="uq_review_share_choice_item"),)


class AdventDoor(Base):
    """A door a member opened on the December advent calendar (Nov 2026). A new table only.

    One row per member, year and day. Rows are only ever added, so the Door Opener
    badge counts them straight from here.
    """
    __tablename__ = "advent_doors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    opened_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "year", "day", name="uq_advent_door"),)


class AdventReminder(Base):
    """A member who asked for a morning notification when each advent door opens. A new table only.

    ``last_day`` is the last door they were told about, so each door is announced once.
    Turning the reminder off deletes the row.
    """
    __tablename__ = "advent_reminders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_day = Column(Integer, nullable=False, default=0)

    __table_args__ = (UniqueConstraint("user_id", "year", name="uq_advent_reminder"),)


class DataFix(Base):
    """A one-time repair of stored rows that has already run (Nov 2026). A new table only.

    Startup migrations run on every boot. A repair that must not run twice, such as
    moving badge rows between keys, writes its name here in the same transaction.
    """
    __tablename__ = "data_fixes"

    name = Column(String(64), primary_key=True)
    ran_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class SupportAsk(Base):
    """When a member last saw a "support OmniTrackr" note on the dashboard, and how they answered (Nov 2026).

    A new table only, one row per member, made the first time a note is shown. The ``*_done`` columns
    are the highest milestone already asked about, so the same moment never asks twice. ``kofi_at`` and
    ``kofi_from`` remember a press of a Ko-fi button for two weeks, so Site stats can tell which places
    lead to support. Nothing here is shown to anyone else.
    """
    __tablename__ = "support_asks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    moment = Column(String(24), nullable=True)
    ask_key = Column(String(48), nullable=True)
    shown_at = Column(DateTime, nullable=True)
    shown_count = Column(Integer, nullable=False, default=0)
    answer = Column(String(8), nullable=True)
    answered_at = Column(DateTime, nullable=True)
    snoozed_until = Column(DateTime, nullable=True)
    stopped_at = Column(DateTime, nullable=True)
    titles_done = Column(Integer, nullable=False, default=0)
    days_done = Column(Integer, nullable=False, default=0)
    years_done = Column(Integer, nullable=False, default=0)
    goal_done = Column(Integer, nullable=False, default=0)
    lapse_done = Column(DateTime, nullable=True)
    kofi_at = Column(DateTime, nullable=True)
    kofi_from = Column(String(24), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class StayPostedAsk(Base):
    """When a member was last asked how they'd like to hear about new episodes and releases (Nov 2026).

    A new table only, one row per member, made the first time the home-screen card or the note after
    saving a show reaches their screen. It records the asking and the answer, never a channel itself:
    the weekly email, notifications and the calendar keep their own switches, and nothing is turned on
    unless the member presses that button.
    """
    __tablename__ = "stay_posted_asks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    moment = Column(String(16), nullable=True)
    shown_at = Column(DateTime, nullable=True)
    shown_count = Column(Integer, nullable=False, default=0)
    answer = Column(String(12), nullable=True)
    answered_at = Column(DateTime, nullable=True)
    snoozed_until = Column(DateTime, nullable=True)
    stopped_at = Column(DateTime, nullable=True)
    after_save_at = Column(DateTime, nullable=True)
    after_save_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class WeekOnePlan(Base):
    """A new member's first-week home card (Nov 2026): when they saw it, whether they came back on a later
    day, and the one reminder email they may have asked for.

    A new table only, one row per member, made the first time the card reaches their screen or a button
    on it is pressed. Nothing in a member's library is read from or written to it.
    """
    __tablename__ = "week_one_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    first_seen_on = Column(Date, nullable=True)
    last_seen_on = Column(Date, nullable=True)
    returned_at = Column(DateTime, nullable=True)
    hidden_at = Column(DateTime, nullable=True)
    saved_count = Column(Integer, nullable=False, default=0)
    push_at = Column(DateTime, nullable=True)
    remind_on = Column(Date, nullable=True)
    remind_at = Column(DateTime, nullable=True, index=True)
    reminder_status = Column(String(12), nullable=True, index=True)  # set, sent, dropped, failed
    reminder_set_at = Column(DateTime, nullable=True)
    reminder_sent_at = Column(DateTime, nullable=True)
    back_at = Column(DateTime, nullable=True)
    start_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class InstalledAppOpen(Base):
    """A member who opened OmniTrackr from its home-screen or desktop icon (Nov 2026).

    A new table only, one row per member, made the first time the installed app reports an open and
    touched at most once a day after that. It lets Site stats count members who actually keep the app,
    which the anonymous counters can't. Nothing in a member's library is read from or written to it.
    """
    __tablename__ = "installed_app_opens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    platforms = Column(String(32), nullable=True)  # "ios", "android", "desktop", comma-separated
    first_opened_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_opened_on = Column(Date, nullable=True, index=True)
    open_days = Column(Integer, nullable=False, default=0)


class BacklogDraw(Base):
    """One title a member drew from their own backlog on the home screen and kept (Nov 2026).

    A new table only. One row per kept card: which library title, the night they picked for it, the
    one reminder email they may have asked for, and how it ended (finished, put back, not for me).
    The library row itself is never changed here; finishing and scoring go through the library's own
    rules (check_in.answer). A "not_for_me" row keeps that title out of later deals.
    """
    __tablename__ = "backlog_draws"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(16), nullable=False)
    item_id = Column(Integer, nullable=False)
    # picked (the one on the card now), finished, put_back, not_for_me, replaced, gone (deleted from the library)
    status = Column(String(12), nullable=False, default="picked", index=True)
    deal = Column(Integer, nullable=False, default=0)  # which deal of the day it came from (0 = the first)
    night = Column(Date, nullable=True)  # the member's own date they picked for it
    tz_minutes = Column(Integer, nullable=False, default=0)  # minutes east of UTC, from the browser
    remind_at = Column(DateTime, nullable=True, index=True)
    reminder_status = Column(String(12), nullable=True, index=True)  # set, sent, dropped, failed
    reminder_set_at = Column(DateTime, nullable=True)
    reminder_sent_at = Column(DateTime, nullable=True)
    calendar_at = Column(DateTime, nullable=True)
    back_at = Column(DateTime, nullable=True)  # first home screen visit after the night
    picked_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_backlog_draws_user_status", "user_id", "status"),
    )


class YourWeekPlan(Base):
    """A member's "Your week" home card (Nov 2026): the weekly pace they picked and the Sunday nudge.

    A new table only, one row per member, made the first time the card reaches their screen or a
    button on it is pressed. ``goal`` is a key from your_week.GOALS, empty until they pick one (or
    after "Stop keeping count"). Nothing in a member's library is read from or written to it.
    """
    __tablename__ = "your_week_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    goal = Column(String(8), nullable=True)
    goal_set_at = Column(DateTime, nullable=True)
    started_week = Column(Date, nullable=True)  # the Monday of the week they first picked a pace
    tz_minutes = Column(Integer, nullable=False, default=0)  # minutes east of UTC, from the browser
    remind_email = Column(Boolean, nullable=False, default=False)
    remind_push = Column(Boolean, nullable=False, default=False)
    remind_set_at = Column(DateTime, nullable=True)
    next_remind_at = Column(DateTime, nullable=True, index=True)
    first_seen_on = Column(Date, nullable=True)
    last_seen_on = Column(Date, nullable=True)
    hidden_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class YourWeekWeek(Base):
    """One week of a member's "Your week" card, Monday to Sunday in their time zone (Nov 2026).

    A new table only. Days and finishes are counted from the member's own activity and only ever
    grow, so a kept week stays kept even if a title is later deleted. A week is ``final`` once it has
    ended and been counted after the fact; it never changes after that.
    """
    __tablename__ = "your_week_weeks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    week_start = Column(Date, nullable=False)
    goal = Column(String(8), nullable=True)  # the pace that week was counted against
    day_mask = Column(Integer, nullable=False, default=0)  # bit 0 = Monday ... bit 6 = Sunday
    finishes = Column(Integer, nullable=False, default=0)
    kept_at = Column(DateTime, nullable=True)
    rest_at = Column(DateTime, nullable=True)
    final = Column(Boolean, nullable=False, default=False)
    recap_seen_at = Column(DateTime, nullable=True)
    nudged_at = Column(DateTime, nullable=True)
    back_at = Column(DateTime, nullable=True)  # first home screen visit after that week's nudge
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "week_start", name="uq_your_week_weeks_user_week"),
    )


class ProgressMark(Base):
    """When a member moved a saved place forward (Nov 2026), so "Your week" can count the day.

    A new table only. A progress checkpoint keeps just its latest time, so an episode marked on
    Monday and the next one on Thursday would leave only Thursday behind. One row per member at
    most every half hour; it holds a time and nothing about the title.
    """
    __tablename__ = "progress_marks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_progress_marks_user_at", "user_id", "at"),
    )


class StreamingChoice(Base):
    """The streaming services one member says they have (Nov 2026), for the "On your services" card.

    A new table only, one row per member. ``services`` is JSON: {service id: when it was picked},
    so an arrival on a service picked later than the arrival isn't news. ``alerts`` is the member's
    "tell me when something arrives" switch. The choice is private: nothing shows it to anyone else.
    Before anything is picked, ``hidden_until`` is "Not now" and ``stopped_at`` is "No thanks";
    after, ``hidden_until`` is "Hide this card".
    """
    __tablename__ = "streaming_choices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    services = Column(Text, nullable=True)
    alerts = Column(Boolean, nullable=False, default=True)
    hidden_until = Column(DateTime, nullable=True)
    stopped_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ServiceSighting(Base):
    """One title seen streaming on one service, shared by every member (Nov 2026).

    Never linked to a member. ``title_key`` is the title's where-to-watch cache key. ``baseline``
    rows were already there the first time the title was checked, so they are not news;
    ``first_seen_at`` on any other row is when the title arrived. ``gone_at`` is set while the
    title is no longer listed there.
    """
    __tablename__ = "service_sightings"

    id = Column(Integer, primary_key=True, index=True)
    title_key = Column(String(300), nullable=False, index=True)
    service = Column(String(24), nullable=False)
    first_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    gone_at = Column(DateTime, nullable=True)
    baseline = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("title_key", "service", name="uq_service_sightings_title_service"),
    )


class ServiceTitleCheck(Base):
    """When the streaming check last read one title's where-to-watch cache row (Nov 2026).

    ``source_fetched_at`` is that row's ``fetched_at``, so a title is only compared again after its
    cache row was refreshed. Never linked to a member.
    """
    __tablename__ = "service_title_checks"

    id = Column(Integer, primary_key=True, index=True)
    title_key = Column(String(300), nullable=False, unique=True, index=True)
    first_checked_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    checked_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    source_fetched_at = Column(DateTime, nullable=True)


class ServiceAlert(Base):
    """A member was told that a title on their list arrived on one of their services (Nov 2026).

    One row per member, title and service, so nobody hears about the same arrival twice. If the
    title leaves and comes back weeks later, the row's ``created_at`` moves forward instead.
    """
    __tablename__ = "service_alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title_key = Column(String(300), nullable=False)
    service = Column(String(24), nullable=False)
    title = Column(String(200), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "title_key", "service", name="uq_service_alerts_member_title_service"),
    )


class Ranking(Base):
    """One member's ranking of the titles they finished in one format (Nov 2026), for "Rankings".

    A new table only, one row per member and format. ``ranked`` is a JSON list of that format's
    library ids, best first. A title is placed by answering "which did you like more?" a few times:
    ``placing_id`` is the title being placed and ``low``/``high`` the stretch of the list it can still
    land in (a binary search, so a list of 100 takes about seven answers). ``left_out`` holds titles the
    member asked never to be offered, ``later`` the ones skipped for now. Library rows are never
    changed here. ``public`` puts the top ten on the member's public profile (off until they say so).
    """
    __tablename__ = "rankings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(16), nullable=False)
    ranked = Column(Text, nullable=False, default="[]")
    left_out = Column(Text, nullable=True)
    later = Column(Text, nullable=True)
    placing_id = Column(Integer, nullable=True)
    low = Column(Integer, nullable=False, default=0)
    high = Column(Integer, nullable=False, default=0)
    steps = Column(Integer, nullable=False, default=0)
    public = Column(Boolean, nullable=False, default=False)
    placed_total = Column(Integer, nullable=False, default=0)  # placements ever made, re-placements included
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_rankings_member_category"),
    )


class RankingShare(Base):
    """A member's share link for the top ten of one ranking (Nov 2026): /ranked/<token>.

    A new table only. The link shows the ranking as it is when someone opens it, never the
    scores, and only while the format stays visible and not private. Deleting the row ends the
    link. ``opened`` counts opens by people other than the member (not bots or prefetches).
    """
    __tablename__ = "ranking_shares"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(16), nullable=False)
    token = Column(String(32), nullable=False, unique=True, index=True)
    opened = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_ranking_shares_member_category"),
    )


class ServiceShare(Base):
    """A member's share link for their "On your services" list (Nov 2026): /on-my-services/<token>.

    A new table only, one row per member. The page reads the list when someone opens it: films,
    shows and anime the member hasn't finished that stream on the services they picked, from
    shelves that aren't hidden or private. It never shows scores, notes or the rest of the
    library. Deleting the row ends the link. ``opened`` counts opens by other people (not bots
    or prefetches).
    """
    __tablename__ = "service_shares"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    token = Column(String(32), nullable=False, unique=True, index=True)
    opened = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class TogetherPlan(Base):
    """Watch or read one title together at a weekly pace (Nov 2026): /together/<id>.

    New tables only. A plan covers one run of parts of one title: a season of a show, an
    anime, a book or manga by chapter, a podcast or audiobook. The title is copied in when
    the plan starts, so nobody's library is read for it later. ``token`` is the invite link
    (/together/join/<token>); a new link retires the old one. ``week_sent`` is the last week
    whose "this week" notice went out, so each week is announced once.
    """
    __tablename__ = "together_plans"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(32), nullable=False, unique=True, index=True)
    category = Column(String(16), nullable=False)
    kind = Column(String(10), nullable=False)
    title = Column(String(200), nullable=False)
    year = Column(Integer, nullable=True)
    image = Column(String(500), nullable=True)
    unit = Column(String(8), nullable=False)  # episode, chapter
    season = Column(Integer, nullable=True)
    total = Column(Integer, nullable=False)
    pace = Column(Integer, nullable=False)  # parts a week
    starts_on = Column(Date, nullable=False)
    week_sent = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    members = relationship("TogetherMember", cascade="all, delete-orphan", back_populates="plan")
    notes = relationship("TogetherNote", cascade="all, delete-orphan")
    removals = relationship("TogetherRemoval", cascade="all, delete-orphan")


class TogetherMember(Base):
    """One person in a together plan and how far they've got.

    ``position`` is the last part they finished (0 before the first). It follows their own
    library checkpoint while ``follow_library`` is on and ``item_id`` points at their copy of
    the title, but only checkpoints saved after ``moved_at`` count, so joining with an old
    checkpoint (a rewatch) never jumps anyone ahead. ``done_week`` and ``emailed_week`` keep
    the "done for the week" notice and the reminder email to once a week each. ``seen_at`` and
    ``seen_position`` are when and where the member last had the plan open, so a note counts as
    new when it was written since then or sits past the place they had reached.
    """
    __tablename__ = "together_members"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("together_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    joined_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    position = Column(Integer, nullable=False, default=0)
    moved_at = Column(DateTime, nullable=True)
    item_id = Column(Integer, nullable=True)
    follow_library = Column(Boolean, nullable=False, default=True)
    done_week = Column(Integer, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    seen_at = Column(DateTime, nullable=True)
    seen_position = Column(Integer, nullable=True)
    remind_email = Column(Boolean, nullable=False, default=True)
    emailed_week = Column(Integer, nullable=True)

    plan = relationship("TogetherPlan", back_populates="members")

    __table_args__ = (UniqueConstraint("plan_id", "user_id", name="uq_together_member"),)


class TogetherNote(Base):
    """A note left at one part of a together plan. Others read it once they reach that part.

    Part 0 means "before we start" and everyone can read it.
    """
    __tablename__ = "together_notes"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("together_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    part = Column(Integer, nullable=False)
    body = Column(String(500), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (Index("ix_together_notes_plan_part", "plan_id", "part"),)


class TogetherRemoval(Base):
    """Someone the person running a together plan took out of it (Nov 22 2026 sweep).

    The invite link would otherwise let them straight back in. The row goes when the person
    running the plan asks them in again from their friends list. New table only.
    """
    __tablename__ = "together_removals"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("together_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("plan_id", "user_id", name="uq_together_removal"),)


class PickSwap(Base):
    """A pick swap (Nov 2026): Secret Santa where everyone gives one recommendation. /swap/<id>.

    New tables only. People join with the invite link (/swap/join/<token>) until names are
    drawn, by the host or on ``draw_on``. Each person then picks one title for the person
    they drew, and everything opens on ``reveal_on``. ``draw_at`` and ``reveal_at`` are those
    days at 8 a.m. in the host's time zone (``tz``, minutes east of UTC), stored in UTC.
    ``kinds`` is a comma-separated list of title kinds a pick may be (empty means any).
    """
    __tablename__ = "pick_swaps"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(32), nullable=False, unique=True, index=True)
    name = Column(String(60), nullable=False)
    note = Column(String(300), nullable=True)
    kinds = Column(String(120), nullable=False, default="")
    tz = Column(Integer, nullable=False, default=0)
    draw_on = Column(Date, nullable=True)
    draw_at = Column(DateTime, nullable=True)
    reveal_on = Column(Date, nullable=False)
    reveal_at = Column(DateTime, nullable=False)
    drawn_at = Column(DateTime, nullable=True)
    revealed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    reminded_at = Column(DateTime, nullable=True)
    short_at = Column(DateTime, nullable=True)  # the host was told there weren't enough people to draw
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    members = relationship("PickSwapMember", cascade="all, delete-orphan", back_populates="swap")
    removals = relationship("PickSwapRemoval", cascade="all, delete-orphan")


class PickSwapMember(Base):
    """One person in a pick swap, who they drew, and the pick they wrapped for them.

    ``gives_to`` is the user id of the person they drew (set at the draw, never shown to anyone
    else before unwrap day). The ``gift_*`` columns are the pick itself, copied in as public
    title facts. ``gift_opened_at``, ``gift_added_at`` and ``gift_thanks`` record what the
    person who received it did with it.
    """
    __tablename__ = "pick_swap_members"

    id = Column(Integer, primary_key=True, index=True)
    swap_id = Column(Integer, ForeignKey("pick_swaps.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    joined_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    wish = Column(String(160), nullable=True)
    gives_to = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    gift_kind = Column(String(10), nullable=True)
    gift_title = Column(String(200), nullable=True)
    gift_year = Column(Integer, nullable=True)
    gift_image = Column(String(500), nullable=True)
    gift_slug = Column(String(140), nullable=True)
    gift_creator = Column(String(200), nullable=True)
    gift_note = Column(String(500), nullable=True)
    picked_at = Column(DateTime, nullable=True)
    gift_opened_at = Column(DateTime, nullable=True)
    gift_added_at = Column(DateTime, nullable=True)
    gift_thanks = Column(String(12), nullable=True)
    thanked_at = Column(DateTime, nullable=True)

    swap = relationship("PickSwap", back_populates="members")

    __table_args__ = (UniqueConstraint("swap_id", "user_id", name="uq_pick_swap_member"),)


class PickSwapRemoval(Base):
    """Someone the host took out of a pick swap, so the invite link can't add them back."""
    __tablename__ = "pick_swap_removals"

    id = Column(Integer, primary_key=True, index=True)
    swap_id = Column(Integer, ForeignKey("pick_swaps.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("swap_id", "user_id", name="uq_pick_swap_removal"),)


class BreakPlan(Base):
    """A member's plan for a stretch of days off, filled from their own library (Nov 2026): /break.

    New tables only. ``day_minutes`` is JSON ({"2026-11-26": 60, ...}): the time the member says
    they have on each day of the break, 0 for a busy day. ``seed`` changes with "Try another mix"
    so the same plan always fills the same way until then. ``left_out`` is JSON, a list of
    "category:id" titles the member took off this break. Library rows are never changed here
    except through the library's own rules (check_in.answer, progress._write_progress) when the
    member ticks something off.
    """
    __tablename__ = "break_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(60), nullable=False)
    preset = Column(String(32), nullable=True)
    starts_on = Column(Date, nullable=False)
    ends_on = Column(Date, nullable=False)
    tz_minutes = Column(Integer, nullable=False, default=0)  # minutes east of UTC, from the browser
    day_minutes = Column(Text, nullable=False, default="{}")
    games = Column(Boolean, nullable=False, default=True)  # fill with a game too
    seed = Column(Integer, nullable=False, default=0)
    left_out = Column(Text, nullable=False, default="[]")
    status = Column(String(12), nullable=False, default="active", index=True)  # active, cancelled, replaced (a newer plan took over; its link still works)
    share_token = Column(String(32), nullable=True, unique=True, index=True)
    share_opened = Column(Integer, nullable=False, default=0)
    emails = Column(Boolean, nullable=False, default=False)  # the morning it starts and the day after it ends
    start_email = Column(String(12), nullable=True)  # sent, skipped, dropped, failed
    wrap_email = Column(String(12), nullable=True)
    last_seen_on = Column(Date, nullable=True)  # the member's last day of the break that they opened it
    days_opened = Column(Integer, nullable=False, default=0)
    wrap_hidden_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    items = relationship("BreakPlanItem", cascade="all, delete-orphan", back_populates="plan")

    __table_args__ = (Index("ix_break_plans_user_status", "user_id", "status"),)


class BreakPlanItem(Base):
    """One stretch of one library title on one day of a break plan: "Episodes 4-7", "Pages 1-120".

    ``unit`` is whole (a film or album), episode, page, chapter or block (half hours, for games,
    audiobooks and books without a page count). ``first``/``last`` count units from the start of
    the title, ``total`` is how many it has, so the last stretch is the one with last == total.
    The title, cover and label are copied in so a share page never reads the library.
    """
    __tablename__ = "break_plan_items"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("break_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    day = Column(Date, nullable=False)
    position = Column(Integer, nullable=False, default=0)
    category = Column(String(16), nullable=False)
    item_id = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    year = Column(Integer, nullable=True)
    image = Column(String(500), nullable=True)
    unit = Column(String(8), nullable=False)
    first = Column(Integer, nullable=False, default=1)
    last = Column(Integer, nullable=False, default=1)
    total = Column(Integer, nullable=False, default=1)
    minutes = Column(Integer, nullable=False, default=0)
    label = Column(String(80), nullable=False, default="")
    guessed = Column(Boolean, nullable=False, default=False)
    added = Column(Boolean, nullable=False, default=False)  # the member put it here themselves
    done_at = Column(DateTime, nullable=True)
    finished_title = Column(Boolean, nullable=False, default=False)  # ticking this finished the title
    # JSON: the library checkpoint before this tick moved it, and the revision the tick wrote, so an
    # untick can put it back while nobody has changed it since. Empty when the tick didn't move it.
    undo_progress = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    plan = relationship("BreakPlan", back_populates="items")

    __table_args__ = (Index("ix_break_plan_items_plan_day", "plan_id", "day"),)
