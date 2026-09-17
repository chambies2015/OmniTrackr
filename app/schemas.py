"""
Pydantic models (schemas) for the OmniTrackr API.
These define the shape of data accepted/returned by the API.
"""
from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


def validate_public_url(value: Optional[str]) -> Optional[str]:
    """Allow only http(s) URLs or same-origin absolute paths for image/link fields."""
    if value is None:
        return value
    stripped = value.strip()
    if stripped == "":
        return None
    lowered = stripped.lower()
    if lowered.startswith(("http://", "https://", "/")) and not lowered.startswith("//"):
        return stripped
    raise ValueError("URL must start with http://, https://, or /")

# ============================================================================
# Authentication & User Schemas
# ============================================================================

class UserBase(BaseModel):
    """Base user schema with common fields."""
    email: str = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=50, description="Username")


class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(..., min_length=6, max_length=128, description="User password (min 6 characters)")


class UserLogin(BaseModel):
    """Schema for user login."""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")


class User(UserBase):
    """Schema for user responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    is_verified: bool = False
    created_at: Optional[datetime] = None
    profile_picture_url: Optional[str] = None
    
class UserUpdate(BaseModel):
    """Schema for updating user information."""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6, max_length=128)


class PasswordChange(BaseModel):
    """Schema for changing password."""
    current_password: str = Field(..., description="Current password for verification")
    new_password: str = Field(..., min_length=6, max_length=128, description="New password (min 6 characters)")


class PasswordReset(BaseModel):
    """One-time reset credential and replacement password, carried in the request body."""
    token: str = Field(..., min_length=1, max_length=2048)
    new_password: str = Field(..., min_length=6, max_length=128)


class EmailChange(BaseModel):
    """Schema for changing email address."""
    new_email: str = Field(..., description="New email address")
    password: str = Field(..., description="Current password for verification")


class UsernameChange(BaseModel):
    """Schema for changing username."""
    new_username: str = Field(..., min_length=3, max_length=50, description="New username")
    password: str = Field(..., description="Current password for verification")


class AccountDeactivate(BaseModel):
    """Schema for deactivating account."""
    password: str = Field(..., description="Current password for confirmation")


class PrivacySettings(BaseModel):
    """Schema for privacy settings."""
    model_config = ConfigDict(from_attributes=True)

    movies_private: bool = Field(False, description="Make movies private")
    tv_shows_private: bool = Field(False, description="Make TV shows private")
    anime_private: bool = Field(False, description="Make anime private")
    video_games_private: bool = Field(False, description="Make video games private")
    music_private: bool = Field(False, description="Make music private")
    books_private: bool = Field(False, description="Make books private")
    statistics_private: bool = Field(False, description="Make statistics private")
    
class PrivacySettingsUpdate(BaseModel):
    """Schema for updating privacy settings."""
    movies_private: Optional[bool] = None
    tv_shows_private: Optional[bool] = None
    anime_private: Optional[bool] = None
    video_games_private: Optional[bool] = None
    music_private: Optional[bool] = None
    books_private: Optional[bool] = None
    statistics_private: Optional[bool] = None


class TabVisibility(BaseModel):
    """Schema for tab visibility settings."""
    model_config = ConfigDict(from_attributes=True)

    movies_visible: bool = Field(True, description="Show Movies tab")
    tv_shows_visible: bool = Field(True, description="Show TV Shows tab")
    anime_visible: bool = Field(True, description="Show Anime tab")
    video_games_visible: bool = Field(True, description="Show Video Games tab")
    music_visible: bool = Field(True, description="Show Music tab")
    books_visible: bool = Field(True, description="Show Books tab")
    
class TabVisibilityUpdate(BaseModel):
    """Schema for updating tab visibility settings."""
    movies_visible: Optional[bool] = None
    tv_shows_visible: Optional[bool] = None
    anime_visible: Optional[bool] = None
    video_games_visible: Optional[bool] = None
    music_visible: Optional[bool] = None
    books_visible: Optional[bool] = None


# ============================================================================
# Friends & Notifications Schemas
# ============================================================================

class FriendRequestCreate(BaseModel):
    """Schema for creating a friend request."""
    receiver_username: str = Field(..., min_length=3, max_length=50, description="Username of the user to send friend request to")


class FriendRequestResponse(BaseModel):
    """Schema for friend request responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender_id: int
    receiver_id: int
    sender: Optional[User] = None
    receiver: Optional[User] = None
    status: str
    created_at: datetime
    expires_at: datetime
    
class FriendRequestAction(BaseModel):
    """Schema for friend request actions (accept/deny)."""
    action: str = Field(..., description="Action to take: 'accept' or 'deny'")


class FriendshipResponse(BaseModel):
    """Schema for friendship responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    friend: User
    created_at: datetime
    
class NotificationResponse(BaseModel):
    """Schema for notification responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    message: str
    friend_request_id: Optional[int] = None
    created_at: datetime
    read_at: Optional[datetime] = None
    
class UserCount(BaseModel):
    """Schema for user count response."""
    count: int = Field(..., description="Total number of active users")


class NotificationCount(BaseModel):
    """Schema for notification count."""
    count: int


class AccountReactivate(BaseModel):
    """Schema for reactivating account via public endpoint."""
    username: Optional[str] = Field(None, description="Username or email")
    email: Optional[str] = Field(None, description="Email address")
    password: str = Field(..., description="Account password for verification")


class Token(BaseModel):
    """JWT token response schema."""
    access_token: str
    token_type: str = "bearer"
    user: User


class TokenData(BaseModel):
    """Schema for decoded token data."""
    username: Optional[str] = None


# ============================================================================
# Movie & TV Show Schemas
# ============================================================================

class MovieBase(BaseModel):
    title: str = Field(..., description="Title of the movie or book")
    director: str = Field(..., description="Director or author")
    year: int = Field(..., ge=0, description="Year of release or publication")
    rating: Optional[float] = Field(
        None, ge=0, le=10, description="Rating out of 10 (0-10.0, one decimal place)"
    )
    watched: Optional[bool] = Field(False, description="Whether it has been watched/read")
    review: Optional[str] = Field(None, description="Optional review/notes for the entry")
    review_public: Optional[bool] = Field(False, description="Show this review on the public reviews page")
    poster_url: Optional[str] = Field(None, description="URL of the movie poster")

    _validate_poster_url = field_validator("poster_url")(validate_public_url)


class MovieCreate(MovieBase):
    pass


class MovieUpdate(BaseModel):
    title: Optional[str] = None
    director: Optional[str] = None
    year: Optional[int] = Field(None, ge=0)
    rating: Optional[float] = Field(None, ge=0, le=10)
    watched: Optional[bool] = None
    review: Optional[str] = None
    review_public: Optional[bool] = None
    poster_url: Optional[str] = None

    _validate_poster_url = field_validator("poster_url")(validate_public_url)


class Movie(MovieBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class TVShowBase(BaseModel):
    title: str = Field(..., description="Title of the TV show")
    year: int = Field(..., ge=0, description="Year of the TV show")
    seasons: Optional[int] = Field(None, ge=0, description="Number of seasons")
    episodes: Optional[int] = Field(None, ge=0, description="Total number of episodes")
    rating: Optional[float] = Field(None, ge=0, le=10, description="Rating out of 10 (0-10.0, one decimal place)")
    watched: Optional[bool] = Field(False, description="Whether it has been watched")
    review: Optional[str] = Field(None, description="Optional review/notes for the entry")
    review_public: Optional[bool] = Field(False, description="Show this review on the public reviews page")
    poster_url: Optional[str] = Field(None, description="URL of the TV show poster")

    _validate_poster_url = field_validator("poster_url")(validate_public_url)


class TVShowCreate(TVShowBase):
    pass


class TVShowUpdate(BaseModel):
    title: Optional[str] = None
    year: Optional[int] = Field(None, ge=0)
    seasons: Optional[int] = Field(None, ge=0)
    episodes: Optional[int] = Field(None, ge=0)
    rating: Optional[float] = Field(None, ge=0, le=10)
    watched: Optional[bool] = None
    review: Optional[str] = None
    review_public: Optional[bool] = None
    poster_url: Optional[str] = None

    _validate_poster_url = field_validator("poster_url")(validate_public_url)


class TVShow(TVShowBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class AnimeBase(BaseModel):
    title: str = Field(..., description="Title of the anime")
    year: int = Field(..., ge=0, description="Year of the anime")
    seasons: Optional[int] = Field(None, ge=0, description="Number of seasons")
    episodes: Optional[int] = Field(None, ge=0, description="Total number of episodes")
    rating: Optional[float] = Field(None, ge=0, le=10, description="Rating out of 10 (0-10.0, one decimal place)")
    watched: Optional[bool] = Field(False, description="Whether it has been watched")
    review: Optional[str] = Field(None, description="Optional review/notes for the entry")
    review_public: Optional[bool] = Field(False, description="Show this review on the public reviews page")
    poster_url: Optional[str] = Field(None, description="URL of the anime poster")

    _validate_poster_url = field_validator("poster_url")(validate_public_url)


class AnimeCreate(AnimeBase):
    pass


class AnimeUpdate(BaseModel):
    title: Optional[str] = None
    year: Optional[int] = Field(None, ge=0)
    seasons: Optional[int] = Field(None, ge=0)
    episodes: Optional[int] = Field(None, ge=0)
    rating: Optional[float] = Field(None, ge=0, le=10)
    watched: Optional[bool] = None
    review: Optional[str] = None
    review_public: Optional[bool] = None
    poster_url: Optional[str] = None

    _validate_poster_url = field_validator("poster_url")(validate_public_url)


class Anime(AnimeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class VideoGameBase(BaseModel):
    title: str = Field(..., description="Title of the video game")
    release_date: Optional[datetime] = Field(None, description="Release date of the video game (YYYY-MM-DD)")
    genres: Optional[str] = Field(None, description="Comma-separated genre names")
    rating: Optional[float] = Field(None, ge=0, le=10, description="Rating out of 10 (0-10.0, one decimal place)")
    played: Optional[bool] = Field(False, description="Whether it has been played")
    review: Optional[str] = Field(None, description="Optional review/notes for the entry")
    review_public: Optional[bool] = Field(False, description="Show this review on the public reviews page")
    cover_art_url: Optional[str] = Field(None, description="URL of the video game cover art")
    rawg_link: Optional[str] = Field(None, description="RAWG game page URL")

    _validate_cover_art_url = field_validator("cover_art_url")(validate_public_url)
    _validate_rawg_link = field_validator("rawg_link")(validate_public_url)


class VideoGameCreate(VideoGameBase):
    pass


class VideoGameUpdate(BaseModel):
    title: Optional[str] = None
    release_date: Optional[datetime] = None
    genres: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=10)
    played: Optional[bool] = None
    review: Optional[str] = None
    review_public: Optional[bool] = None
    cover_art_url: Optional[str] = None
    rawg_link: Optional[str] = None

    _validate_cover_art_url = field_validator("cover_art_url")(validate_public_url)
    _validate_rawg_link = field_validator("rawg_link")(validate_public_url)


class VideoGame(VideoGameBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class MusicBase(BaseModel):
    title: str = Field(..., description="Title of the album or track")
    artist: str = Field(..., description="Artist name")
    year: int = Field(..., ge=0, description="Year of release")
    genre: Optional[str] = Field(None, description="Music genre")
    rating: Optional[float] = Field(None, ge=0, le=10, description="Rating out of 10 (0-10.0, one decimal place)")
    listened: Optional[bool] = Field(False, description="Whether it has been listened to")
    review: Optional[str] = Field(None, description="Optional review/notes for the entry")
    review_public: Optional[bool] = Field(False, description="Show this review on the public reviews page")
    cover_art_url: Optional[str] = Field(None, description="URL of the album cover art")

    _validate_cover_art_url = field_validator("cover_art_url")(validate_public_url)


class MusicCreate(MusicBase):
    pass


class MusicUpdate(BaseModel):
    title: Optional[str] = None
    artist: Optional[str] = None
    year: Optional[int] = Field(None, ge=0)
    genre: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=10)
    listened: Optional[bool] = None
    review: Optional[str] = None
    review_public: Optional[bool] = None
    cover_art_url: Optional[str] = None

    _validate_cover_art_url = field_validator("cover_art_url")(validate_public_url)


class Music(MusicBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class BookBase(BaseModel):
    title: str = Field(..., description="Title of the book")
    author: str = Field(..., description="Author name")
    year: int = Field(..., ge=0, description="Year of publication")
    genre: Optional[str] = Field(None, description="Book genre")
    rating: Optional[float] = Field(None, ge=0, le=10, description="Rating out of 10 (0-10.0, one decimal place)")
    read: Optional[bool] = Field(False, description="Whether it has been read")
    review: Optional[str] = Field(None, description="Optional review/notes for the entry")
    review_public: Optional[bool] = Field(False, description="Show this review on the public reviews page")
    cover_art_url: Optional[str] = Field(None, description="URL of the book cover art")

    _validate_cover_art_url = field_validator("cover_art_url")(validate_public_url)


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    year: Optional[int] = Field(None, ge=0)
    genre: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=10)
    read: Optional[bool] = None
    review: Optional[str] = None
    review_public: Optional[bool] = None
    cover_art_url: Optional[str] = None

    _validate_cover_art_url = field_validator("cover_art_url")(validate_public_url)


class Book(BookBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ============================================================================
# Private Activity Journal Schemas
# ============================================================================

ACTIVITY_CATEGORIES = {"movies", "tv-shows", "anime", "video-games", "music", "books"}
ACTIVITY_ACTIONS = {"started", "progressed", "completed", "revisited", "noted"}


class ActivityEntryCreate(BaseModel):
    category: str
    item_id: int = Field(..., ge=1)
    action: str = "noted"
    note: Optional[str] = Field(None, max_length=500)
    occurred_at: Optional[datetime] = None

    @field_validator("category")
    @classmethod
    def validate_activity_category(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ACTIVITY_CATEGORIES:
            raise ValueError("Category must be a supported library category")
        return normalized

    @field_validator("action")
    @classmethod
    def validate_activity_action(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ACTIVITY_ACTIONS:
            raise ValueError("Action must be started, progressed, completed, revisited, or noted")
        return normalized

    @field_validator("note")
    @classmethod
    def normalize_activity_note(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() or None if value else None


class ActivityEntryUpdate(BaseModel):
    action: Optional[str] = None
    note: Optional[str] = Field(None, max_length=500)
    occurred_at: Optional[datetime] = None

    @field_validator("action")
    @classmethod
    def validate_activity_update_action(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in ACTIVITY_ACTIONS:
            raise ValueError("Action must be started, progressed, completed, revisited, or noted")
        return normalized

    @field_validator("note")
    @classmethod
    def normalize_activity_update_note(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() or None if value else None


class ActivityEntry(BaseModel):
    id: int
    category: str
    category_label: str
    item_id: Optional[int] = None
    title: str
    action: str
    action_label: str
    note: Optional[str] = None
    rating: Optional[float] = None
    source: str
    occurred_at: datetime


class ActivityEntryImport(BaseModel):
    category: str
    item_id: Optional[int] = Field(None, ge=1)
    title: str = Field(..., min_length=1, max_length=500)
    action: str
    note: Optional[str] = Field(None, max_length=500)
    rating: Optional[float] = Field(None, ge=0, le=10)
    occurred_at: datetime

    _validate_category = field_validator("category")(ActivityEntryCreate.validate_activity_category.__func__)
    _validate_action = field_validator("action")(ActivityEntryCreate.validate_activity_action.__func__)
    _normalize_note = field_validator("note")(ActivityEntryCreate.normalize_activity_note.__func__)


# Export/Import schemas
class ExportData(BaseModel):
    """Schema for exporting all data from OmniTrackr"""
    model_config = ConfigDict(from_attributes=True)

    movies: List[Movie] = Field(..., description="List of all movies")
    tv_shows: List[TVShow] = Field(..., description="List of all TV shows")
    anime: List[Anime] = Field(..., description="List of all anime")
    video_games: List[VideoGame] = Field(..., description="List of all video games")
    music: List[Music] = Field(..., description="List of all music")
    books: List[Book] = Field(..., description="List of all books")
    custom_tabs: List[dict] = Field(default=[], description="List of all custom tabs with their items")
    activities: List[ActivityEntry] = Field(default=[], description="Private activity journal entries")
    collections: List[dict] = Field(default=[], description="Private cross-media collections and curator notes")
    export_metadata: dict = Field(..., description="Export metadata including timestamp and version")
    
class ImportData(BaseModel):
    """Schema for importing data into OmniTrackr"""
    model_config = ConfigDict(from_attributes=True)

    movies: List[MovieCreate] = Field(default=[], description="Movies to import")
    tv_shows: List[TVShowCreate] = Field(default=[], description="TV shows to import")
    anime: List[AnimeCreate] = Field(default=[], description="Anime to import")
    video_games: List[VideoGameCreate] = Field(default=[], description="Video games to import")
    music: List[MusicCreate] = Field(default=[], description="Music to import")
    books: List[BookCreate] = Field(default=[], description="Books to import")
    custom_tabs: List[dict] = Field(default=[], description="Custom tabs to import (optional for backward compatibility)")
    activities: List[ActivityEntryImport] = Field(default=[], description="Activity journal entries (optional for backward compatibility)")
    collections: List[dict] = Field(default=[], description="Collections to restore privately (optional for backward compatibility)")
    
class ImportResult(BaseModel):
    """Schema for import operation results"""
    model_config = ConfigDict(from_attributes=True)

    movies_created: int = Field(..., description="Number of movies created")
    movies_updated: int = Field(..., description="Number of movies updated")
    tv_shows_created: int = Field(..., description="Number of TV shows created")
    tv_shows_updated: int = Field(..., description="Number of TV shows updated")
    anime_created: int = Field(..., description="Number of anime created")
    anime_updated: int = Field(..., description="Number of anime updated")
    video_games_created: int = Field(..., description="Number of video games created")
    video_games_updated: int = Field(..., description="Number of video games updated")
    music_created: int = Field(..., description="Number of music created")
    music_updated: int = Field(..., description="Number of music updated")
    books_created: int = Field(..., description="Number of books created")
    books_updated: int = Field(..., description="Number of books updated")
    custom_tabs_created: int = Field(default=0, description="Number of custom tabs created")
    custom_tabs_updated: int = Field(default=0, description="Number of custom tabs updated")
    activities_created: int = Field(default=0, description="Number of journal entries created")
    activities_skipped: int = Field(default=0, description="Number of duplicate journal entries skipped")
    collections_created: int = Field(default=0, description="Number of private collections restored")
    collections_skipped: int = Field(default=0, description="Number of existing or invalid collections skipped")
    errors: List[str] = Field(default=[], description="List of errors encountered during import")
    
# Statistics schemas
class WatchStatistics(BaseModel):
    """Schema for watch statistics"""
    total_movies: int = Field(..., description="Total number of movies")
    watched_movies: int = Field(..., description="Number of watched movies")
    unwatched_movies: int = Field(..., description="Number of unwatched movies")
    total_tv_shows: int = Field(..., description="Total number of TV shows")
    watched_tv_shows: int = Field(..., description="Number of watched TV shows")
    unwatched_tv_shows: int = Field(..., description="Number of unwatched TV shows")
    total_anime: int = Field(..., description="Total number of anime")
    watched_anime: int = Field(..., description="Number of watched anime")
    unwatched_anime: int = Field(..., description="Number of unwatched anime")
    total_video_games: int = Field(..., description="Total number of video games")
    played_video_games: int = Field(..., description="Number of played video games")
    unplayed_video_games: int = Field(..., description="Number of unplayed video games")
    total_music: int = Field(..., description="Total number of music")
    listened_music: int = Field(..., description="Number of listened music")
    unlistened_music: int = Field(..., description="Number of unlistened music")
    total_books: int = Field(..., description="Total number of books")
    read_books: int = Field(..., description="Number of read books")
    unread_books: int = Field(..., description="Number of unread books")
    total_items: int = Field(..., description="Total number of items")
    watched_items: int = Field(..., description="Number of watched/played/listened/read items")
    unwatched_items: int = Field(..., description="Number of unwatched/unplayed/unlistened/unread items")
    completion_percentage: float = Field(..., description="Percentage of items watched/played/listened/read")


class RatingItem(BaseModel):
    """Schema for rated items in statistics"""
    title: str = Field(..., description="Title of the item")
    type: str = Field(..., description="Type (Movie or TV Show)")
    rating: float = Field(..., description="Rating of the item")


class RatingStatistics(BaseModel):
    """Schema for rating statistics"""
    average_rating: float = Field(..., description="Average rating across all items")
    total_rated_items: int = Field(..., description="Total number of rated items")
    rating_distribution: dict = Field(..., description="Distribution of ratings 1-10")
    highest_rated: List[RatingItem] = Field(..., description="Highest rated items")
    lowest_rated: List[RatingItem] = Field(..., description="Lowest rated items")


class YearStatistics(BaseModel):
    """Schema for year-based statistics"""
    movies_by_year: dict = Field(..., description="Movies count by year")
    tv_shows_by_year: dict = Field(..., description="TV shows count by year")
    anime_by_year: dict = Field(..., description="Anime count by year")
    video_games_by_year: dict = Field(..., description="Video games count by year")
    music_by_year: dict = Field(..., description="Music count by year")
    books_by_year: dict = Field(..., description="Books count by year")
    all_years: List[int] = Field(..., description="All years in the collection")
    decade_stats: dict = Field(..., description="Statistics by decade")
    oldest_year: Optional[int] = Field(None, description="Oldest year in collection")
    newest_year: Optional[int] = Field(None, description="Newest year in collection")


class DirectorItem(BaseModel):
    """Schema for director statistics"""
    director: str = Field(..., description="Director name")
    count: int = Field(..., description="Number of movies")
    avg_rating: Optional[float] = Field(None, description="Average rating (for rated directors)")


class DirectorStatistics(BaseModel):
    """Schema for director statistics"""
    top_directors: List[DirectorItem] = Field(..., description="Directors with most movies")
    highest_rated_directors: List[DirectorItem] = Field(..., description="Directors with highest average ratings")


class StatisticsDashboard(BaseModel):
    """Complete statistics dashboard schema"""
    watch_stats: WatchStatistics = Field(..., description="Watch statistics")
    rating_stats: RatingStatistics = Field(..., description="Rating statistics")
    year_stats: YearStatistics = Field(..., description="Year-based statistics")
    director_stats: DirectorStatistics = Field(..., description="Director statistics")
    generated_at: str = Field(..., description="Timestamp when statistics were generated")


class CategoryWatchStatistics(BaseModel):
    """Schema for category-specific watch statistics"""
    total_items: int = Field(..., description="Total number of items")
    watched_items: int = Field(..., description="Number of watched/played items")
    unwatched_items: int = Field(..., description="Number of unwatched/unplayed items")
    completion_percentage: float = Field(..., description="Percentage of items watched/played")


class CategoryRatingStatistics(BaseModel):
    """Schema for category-specific rating statistics"""
    average_rating: float = Field(..., description="Average rating")
    total_rated_items: int = Field(..., description="Total number of rated items")
    rating_distribution: dict = Field(..., description="Distribution of ratings 1-10")
    highest_rated: List[RatingItem] = Field(..., description="Highest rated items")
    lowest_rated: List[RatingItem] = Field(..., description="Lowest rated items")


class CategoryYearStatistics(BaseModel):
    """Schema for category-specific year statistics"""
    items_by_year: dict = Field(..., description="Items count by year")
    all_years: List[int] = Field(..., description="All years in the collection")
    decade_stats: dict = Field(..., description="Statistics by decade")
    oldest_year: Optional[int] = Field(None, description="Oldest year in collection")
    newest_year: Optional[int] = Field(None, description="Newest year in collection")


class SeasonsEpisodesItem(BaseModel):
    """Schema for show with seasons/episodes"""
    title: str = Field(..., description="Title of the show")
    seasons: Optional[int] = Field(None, description="Number of seasons")
    episodes: Optional[int] = Field(None, description="Number of episodes")


class SeasonsEpisodesStatistics(BaseModel):
    """Schema for seasons/episodes statistics"""
    total_seasons: int = Field(..., description="Total seasons across all shows")
    total_episodes: int = Field(..., description="Total episodes across all shows")
    average_seasons: float = Field(..., description="Average seasons per show")
    average_episodes: float = Field(..., description="Average episodes per show")
    shows_with_most_seasons: List[SeasonsEpisodesItem] = Field(..., description="Shows with most seasons")
    shows_with_most_episodes: List[SeasonsEpisodesItem] = Field(..., description="Shows with most episodes")


class GenreItem(BaseModel):
    """Schema for genre statistics"""
    genre: str = Field(..., description="Genre name")
    count: int = Field(..., description="Number of games with this genre")


class GenreStatistics(BaseModel):
    """Schema for genre statistics"""
    genre_distribution: dict = Field(..., description="Distribution of genres (genre: count)")
    top_genres: List[GenreItem] = Field(..., description="Top genres by count")
    most_played_genres: List[GenreItem] = Field(..., description="Most played genres")


class MovieStatistics(BaseModel):
    """Schema for movie-specific statistics"""
    watch_stats: CategoryWatchStatistics = Field(..., description="Watch statistics")
    rating_stats: CategoryRatingStatistics = Field(..., description="Rating statistics")
    year_stats: CategoryYearStatistics = Field(..., description="Year-based statistics")
    director_stats: DirectorStatistics = Field(..., description="Director statistics")


class TVShowStatistics(BaseModel):
    """Schema for TV show-specific statistics"""
    watch_stats: CategoryWatchStatistics = Field(..., description="Watch statistics")
    rating_stats: CategoryRatingStatistics = Field(..., description="Rating statistics")
    year_stats: CategoryYearStatistics = Field(..., description="Year-based statistics")
    seasons_episodes_stats: SeasonsEpisodesStatistics = Field(..., description="Seasons/episodes statistics")


class AnimeStatistics(BaseModel):
    """Schema for anime-specific statistics"""
    watch_stats: CategoryWatchStatistics = Field(..., description="Watch statistics")
    rating_stats: CategoryRatingStatistics = Field(..., description="Rating statistics")
    year_stats: CategoryYearStatistics = Field(..., description="Year-based statistics")
    seasons_episodes_stats: SeasonsEpisodesStatistics = Field(..., description="Seasons/episodes statistics")


class VideoGameStatistics(BaseModel):
    """Schema for video game-specific statistics"""
    watch_stats: CategoryWatchStatistics = Field(..., description="Watch statistics")
    rating_stats: CategoryRatingStatistics = Field(..., description="Rating statistics")
    year_stats: CategoryYearStatistics = Field(..., description="Year-based statistics")
    genre_stats: GenreStatistics = Field(..., description="Genre statistics")


class MusicStatistics(BaseModel):
    """Schema for music-specific statistics"""
    watch_stats: CategoryWatchStatistics = Field(..., description="Watch statistics")
    rating_stats: CategoryRatingStatistics = Field(..., description="Rating statistics")
    year_stats: CategoryYearStatistics = Field(..., description="Year-based statistics")


class BookStatistics(BaseModel):
    """Schema for book-specific statistics"""
    watch_stats: CategoryWatchStatistics = Field(..., description="Watch statistics")
    rating_stats: CategoryRatingStatistics = Field(..., description="Rating statistics")
    year_stats: CategoryYearStatistics = Field(..., description="Year-based statistics")


# ============================================================================
# Friend Profile Schemas
# ============================================================================

class FriendProfileSummary(BaseModel):
    """Schema for friend profile summary (counts only)."""
    username: str = Field(..., description="Friend's username")
    movies_count: Optional[int] = Field(None, description="Number of movies (if not private)")
    tv_shows_count: Optional[int] = Field(None, description="Number of TV shows (if not private)")
    anime_count: Optional[int] = Field(None, description="Number of anime (if not private)")
    video_games_count: Optional[int] = Field(None, description="Number of video games (if not private)")
    music_count: Optional[int] = Field(None, description="Number of music (if not private)")
    books_count: Optional[int] = Field(None, description="Number of books (if not private)")
    statistics_available: Optional[bool] = Field(None, description="Whether statistics are available (if not private)")
    movies_private: bool = Field(..., description="Whether movies are private")
    tv_shows_private: bool = Field(..., description="Whether TV shows are private")
    anime_private: bool = Field(..., description="Whether anime are private")
    video_games_private: bool = Field(..., description="Whether video games are private")
    music_private: bool = Field(..., description="Whether music are private")
    books_private: bool = Field(..., description="Whether books are private")
    statistics_private: bool = Field(..., description="Whether statistics are private")


class FriendMoviesResponse(BaseModel):
    """Schema for friend's movies list."""
    movies: List[Movie] = Field(..., description="List of friend's movies")
    count: int = Field(..., description="Total number of movies")


class FriendTVShowsResponse(BaseModel):
    """Schema for friend's TV shows list."""
    tv_shows: List[TVShow] = Field(..., description="List of friend's TV shows")
    count: int = Field(..., description="Total number of TV shows")


class FriendAnimeResponse(BaseModel):
    """Schema for friend's anime list."""
    anime: List[Anime] = Field(..., description="List of friend's anime")
    count: int = Field(..., description="Total number of anime")


class FriendVideoGamesResponse(BaseModel):
    """Schema for friend's video games list."""
    video_games: List[VideoGame] = Field(..., description="List of friend's video games")
    count: int = Field(..., description="Total number of video games")


class FriendMusicResponse(BaseModel):
    """Schema for friend's music list."""
    music: List[Music] = Field(..., description="List of friend's music")
    count: int = Field(..., description="Total number of music")


class FriendBooksResponse(BaseModel):
    """Schema for friend's books list."""
    books: List[Book] = Field(..., description="List of friend's books")
    count: int = Field(..., description="Total number of books")


class FriendStatisticsResponse(BaseModel):
    """Schema for friend's statistics (compact version)."""
    watch_stats: WatchStatistics = Field(..., description="Watch statistics")
    rating_stats: RatingStatistics = Field(..., description="Rating statistics")
    generated_at: str = Field(..., description="Timestamp when statistics were generated")


class CustomTabFieldCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=50, description="Field key (e.g., 'year', 'director')")
    label: str = Field(..., min_length=1, max_length=100, description="Field label for display")
    field_type: str = Field(..., description="Field type: text, number, date, boolean, rating, review, status")
    required: bool = Field(False, description="Whether field is required")
    order: int = Field(0, ge=0, description="Display order")


class CustomTabField(CustomTabFieldCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tab_id: int


class CustomTabCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Tab name")
    source_type: str = Field("none", description="Metadata source: omdb, jikan, rawg, or none")
    allow_uploads: bool = Field(True, description="Allow poster uploads")
    fields: List[CustomTabFieldCreate] = Field(default=[], max_length=30, description="Field definitions")


class CustomTabUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    source_type: Optional[str] = None
    allow_uploads: Optional[bool] = None
    fields: Optional[List[CustomTabFieldCreate]] = None


class CustomTab(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    slug: str
    source_type: str
    allow_uploads: bool
    created_at: Optional[datetime] = None
    fields: List[CustomTabField] = Field(default=[])
    
class CustomTabItemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500, description="Item title")
    field_values: dict = Field(default={}, description="Field values as key-value pairs")
    poster_url: Optional[str] = Field(None, max_length=2000, description="Poster image URL")

    _validate_poster_url = field_validator("poster_url")(validate_public_url)


class CustomTabItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    field_values: Optional[dict] = None
    poster_url: Optional[str] = Field(None, max_length=2000)

    _validate_poster_url = field_validator("poster_url")(validate_public_url)


class CustomTabItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tab_id: int
    title: str
    field_values: Optional[dict] = None
    poster_url: Optional[str] = None
    created_at: Optional[datetime] = None
    
# ============================================================================
# Next Up Queue Schemas
# ============================================================================

NEXT_UP_CATEGORIES = {"movies", "tv-shows", "anime", "video-games", "music", "books"}


class NextUpItemCreate(BaseModel):
    category: str = Field(..., description="Library category for the queued item")
    item_id: int = Field(..., ge=1, description="ID of the existing library item")

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in NEXT_UP_CATEGORIES:
            raise ValueError("Category must be a supported library category")
        return normalized


class NextUpItemMove(BaseModel):
    position: int = Field(..., ge=0, description="Zero-based queue position")


class NextUpItem(BaseModel):
    id: int
    category: str
    item_id: int
    title: str
    category_label: str
    position: int
    available: bool = True


# ============================================================================
# Recommendation Postcard Schemas
# ============================================================================

RECOMMENDATION_CATEGORIES = {"movies", "tv-shows", "anime", "video-games", "music", "books"}


class RecommendationRequestCreate(BaseModel):
    prompt: str = Field(..., min_length=10, max_length=280)
    categories: List[str] = Field(..., min_length=1, max_length=6)
    expires_in_days: int = Field(7, ge=1, le=30)
    max_responses: int = Field(10, ge=3, le=20)

    @field_validator("prompt")
    @classmethod
    def clean_prompt(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, value: List[str]) -> List[str]:
        normalized = list(dict.fromkeys(category.strip().lower() for category in value))
        if any(category not in RECOMMENDATION_CATEGORIES for category in normalized):
            raise ValueError("Categories must use built-in media types")
        return normalized


class RecommendationSubmissionCreate(BaseModel):
    guest_name: str = Field(..., min_length=1, max_length=50)
    category: str
    title: str = Field(..., min_length=1, max_length=200)
    reason: str = Field(..., min_length=20, max_length=500)
    website: Optional[str] = Field(None, max_length=200, description="Spam-trap field; leave blank")

    @field_validator("guest_name", "title", "reason")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in RECOMMENDATION_CATEGORIES:
            raise ValueError("Category must be a supported media type")
        return normalized


class RecommendationFriendSubmissionCreate(BaseModel):
    category: str
    title: str = Field(..., min_length=1, max_length=200)
    reason: str = Field(..., min_length=20, max_length=500)

    _clean_title = field_validator("title")(RecommendationSubmissionCreate.clean_text.__func__)
    _clean_reason = field_validator("reason")(RecommendationSubmissionCreate.clean_text.__func__)
    _validate_category = field_validator("category")(RecommendationSubmissionCreate.validate_category.__func__)


class RecommendationInviteCreate(BaseModel):
    friend_id: int = Field(..., ge=1)


class RecommendationTriage(BaseModel):
    action: Literal["save", "library", "next-up", "dismiss"]


# ============================================================================
# Completion Moment Schemas
# ============================================================================

class CompletionMomentCreate(NextUpItemCreate):
    """Reference an already-finished library item for a private reflection."""


class CompletionMomentUpdate(BaseModel):
    takeaway: Optional[str] = Field(None, max_length=500, description="A short private takeaway")
    favorite: Optional[bool] = Field(None, description="Whether this was a personal favorite")

    @field_validator("takeaway")
    @classmethod
    def normalize_takeaway(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip() or None


class CompletionMoment(BaseModel):
    id: int
    category: str
    category_label: str
    item_id: int
    title: str
    rating: Optional[float] = None
    takeaway: Optional[str] = None
    favorite: bool = False
    completed_at: datetime


# ============================================================================
# Cross-media Collection Schemas
# ============================================================================

class CollectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80, description="Collection name")
    description: Optional[str] = Field(None, max_length=500, description="Optional private collection note")
    cover_url: Optional[str] = Field(None, max_length=1000, description="Optional public collection artwork URL")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Collection name cannot be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() or None if value else None

    _validate_cover_url = field_validator("cover_url")(validate_public_url)


class CollectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    description: Optional[str] = Field(None, max_length=500)
    cover_url: Optional[str] = Field(None, max_length=1000)
    is_public: Optional[bool] = None

    _validate_cover_url = field_validator("cover_url")(validate_public_url)


class CollectionItemCreate(NextUpItemCreate):
    """Add one existing media record to a collection."""


class CollectionItemMove(BaseModel):
    position: int = Field(..., ge=0)


class CollectionItemUpdate(BaseModel):
    curator_note: Optional[str] = Field(None, max_length=500)

    @field_validator("curator_note")
    @classmethod
    def normalize_curator_note(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() or None if value else None


class CollectionModerationUpdate(BaseModel):
    status: str = Field(..., pattern="^(pending|approved|rejected)$")


class CollectionReportCreate(BaseModel):
    reason: str = Field(..., pattern="^(spam|harassment|copyright|unsafe|other)$")
    details: Optional[str] = Field(None, max_length=500)


class PublicReviewReportCreate(BaseModel):
    reason: str = Field(..., pattern="^(spam|harassment|personal_information|copied_content|other)$")


class CollectionItem(BaseModel):
    id: int
    category: str
    category_label: str
    item_id: int
    title: str
    position: int
    available: bool = True
    curator_note: Optional[str] = None
    artwork_url: Optional[str] = None


class Collection(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    is_public: bool = False
    moderation_status: str = "pending"
    public_url: Optional[str] = None
    view_count: int = 0
    helpful_count: int = 0
    report_count: int = 0
    created_at: datetime
    items: List[CollectionItem] = Field(default=[])
