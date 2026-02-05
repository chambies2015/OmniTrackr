"""
Pydantic models (schemas) for the OmniTrackr API.
These define the shape of data accepted/returned by the API.
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

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
    id: int
    is_active: bool
    is_verified: bool = False
    created_at: Optional[datetime] = None
    profile_picture_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for updating user information."""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6, max_length=128)


class PasswordChange(BaseModel):
    """Schema for changing password."""
    current_password: str = Field(..., description="Current password for verification")
    new_password: str = Field(..., min_length=6, max_length=128, description="New password (min 6 characters)")


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
    movies_private: bool = Field(False, description="Make movies private")
    tv_shows_private: bool = Field(False, description="Make TV shows private")
    anime_private: bool = Field(False, description="Make anime private")
    video_games_private: bool = Field(False, description="Make video games private")
    music_private: bool = Field(False, description="Make music private")
    books_private: bool = Field(False, description="Make books private")
    statistics_private: bool = Field(False, description="Make statistics private")
    reviews_public: bool = Field(False, description="Allow reviews to appear on public reviews page")
    
    class Config:
        from_attributes = True


class PrivacySettingsUpdate(BaseModel):
    """Schema for updating privacy settings."""
    movies_private: Optional[bool] = None
    tv_shows_private: Optional[bool] = None
    anime_private: Optional[bool] = None
    video_games_private: Optional[bool] = None
    music_private: Optional[bool] = None
    books_private: Optional[bool] = None
    statistics_private: Optional[bool] = None
    reviews_public: Optional[bool] = None


class TabVisibility(BaseModel):
    """Schema for tab visibility settings."""
    movies_visible: bool = Field(True, description="Show Movies tab")
    tv_shows_visible: bool = Field(True, description="Show TV Shows tab")
    anime_visible: bool = Field(True, description="Show Anime tab")
    video_games_visible: bool = Field(True, description="Show Video Games tab")
    music_visible: bool = Field(True, description="Show Music tab")
    books_visible: bool = Field(True, description="Show Books tab")
    
    class Config:
        from_attributes = True


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
    id: int
    sender_id: int
    receiver_id: int
    sender: Optional[User] = None
    receiver: Optional[User] = None
    status: str
    created_at: datetime
    expires_at: datetime
    
    class Config:
        from_attributes = True


class FriendRequestAction(BaseModel):
    """Schema for friend request actions (accept/deny)."""
    action: str = Field(..., description="Action to take: 'accept' or 'deny'")


class FriendshipResponse(BaseModel):
    """Schema for friendship responses."""
    id: int
    friend: User
    created_at: datetime
    
    class Config:
        from_attributes = True


class NotificationResponse(BaseModel):
    """Schema for notification responses."""
    id: int
    type: str
    message: str
    friend_request_id: Optional[int] = None
    created_at: datetime
    read_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


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
    poster_url: Optional[str] = Field(None, description="URL of the movie poster")


class MovieCreate(MovieBase):
    pass


class MovieUpdate(BaseModel):
    title: Optional[str] = None
    director: Optional[str] = None
    year: Optional[int] = Field(None, ge=0)
    rating: Optional[float] = Field(None, ge=0, le=10)
    watched: Optional[bool] = None
    review: Optional[str] = None
    poster_url: Optional[str] = None


class Movie(MovieBase):
    id: int

    class Config:
        from_attributes = True


class TVShowBase(BaseModel):
    title: str = Field(..., description="Title of the TV show")
    year: int = Field(..., ge=0, description="Year of the TV show")
    seasons: Optional[int] = Field(None, ge=0, description="Number of seasons")
    episodes: Optional[int] = Field(None, ge=0, description="Total number of episodes")
    rating: Optional[float] = Field(None, ge=0, le=10, description="Rating out of 10 (0-10.0, one decimal place)")
    watched: Optional[bool] = Field(False, description="Whether it has been watched")
    review: Optional[str] = Field(None, description="Optional review/notes for the entry")
    poster_url: Optional[str] = Field(None, description="URL of the TV show poster")


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
    poster_url: Optional[str] = None


class TVShow(TVShowBase):
    id: int

    class Config:
        from_attributes = True


class AnimeBase(BaseModel):
    title: str = Field(..., description="Title of the anime")
    year: int = Field(..., ge=0, description="Year of the anime")
    seasons: Optional[int] = Field(None, ge=0, description="Number of seasons")
    episodes: Optional[int] = Field(None, ge=0, description="Total number of episodes")
    rating: Optional[float] = Field(None, ge=0, le=10, description="Rating out of 10 (0-10.0, one decimal place)")
    watched: Optional[bool] = Field(False, description="Whether it has been watched")
    review: Optional[str] = Field(None, description="Optional review/notes for the entry")
    poster_url: Optional[str] = Field(None, description="URL of the anime poster")


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
    poster_url: Optional[str] = None


class Anime(AnimeBase):
    id: int

    class Config:
        from_attributes = True


class VideoGameBase(BaseModel):
    title: str = Field(..., description="Title of the video game")
    release_date: Optional[datetime] = Field(None, description="Release date of the video game (YYYY-MM-DD)")
    genres: Optional[str] = Field(None, description="Comma-separated genre names")
    rating: Optional[float] = Field(None, ge=0, le=10, description="Rating out of 10 (0-10.0, one decimal place)")
    played: Optional[bool] = Field(False, description="Whether it has been played")
    review: Optional[str] = Field(None, description="Optional review/notes for the entry")
    cover_art_url: Optional[str] = Field(None, description="URL of the video game cover art")
    rawg_link: Optional[str] = Field(None, description="RAWG game page URL")


class VideoGameCreate(VideoGameBase):
    pass


class VideoGameUpdate(BaseModel):
    title: Optional[str] = None
    release_date: Optional[datetime] = None
    genres: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=10)
    played: Optional[bool] = None
    review: Optional[str] = None
    cover_art_url: Optional[str] = None
    rawg_link: Optional[str] = None


class VideoGame(VideoGameBase):
    id: int

    class Config:
        from_attributes = True


class MusicBase(BaseModel):
    title: str = Field(..., description="Title of the album or track")
    artist: str = Field(..., description="Artist name")
    year: int = Field(..., ge=0, description="Year of release")
    genre: Optional[str] = Field(None, description="Music genre")
    rating: Optional[float] = Field(None, ge=0, le=10, description="Rating out of 10 (0-10.0, one decimal place)")
    listened: Optional[bool] = Field(False, description="Whether it has been listened to")
    review: Optional[str] = Field(None, description="Optional review/notes for the entry")
    cover_art_url: Optional[str] = Field(None, description="URL of the album cover art")


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
    cover_art_url: Optional[str] = None


class Music(MusicBase):
    id: int

    class Config:
        from_attributes = True


class BookBase(BaseModel):
    title: str = Field(..., description="Title of the book")
    author: str = Field(..., description="Author name")
    year: int = Field(..., ge=0, description="Year of publication")
    genre: Optional[str] = Field(None, description="Book genre")
    rating: Optional[float] = Field(None, ge=0, le=10, description="Rating out of 10 (0-10.0, one decimal place)")
    read: Optional[bool] = Field(False, description="Whether it has been read")
    review: Optional[str] = Field(None, description="Optional review/notes for the entry")
    cover_art_url: Optional[str] = Field(None, description="URL of the book cover art")


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
    cover_art_url: Optional[str] = None


class Book(BookBase):
    id: int

    class Config:
        from_attributes = True


# Export/Import schemas
class ExportData(BaseModel):
    """Schema for exporting all data from OmniTrackr"""
    movies: List[Movie] = Field(..., description="List of all movies")
    tv_shows: List[TVShow] = Field(..., description="List of all TV shows")
    anime: List[Anime] = Field(..., description="List of all anime")
    video_games: List[VideoGame] = Field(..., description="List of all video games")
    music: List[Music] = Field(..., description="List of all music")
    books: List[Book] = Field(..., description="List of all books")
    custom_tabs: List[dict] = Field(default=[], description="List of all custom tabs with their items")
    export_metadata: dict = Field(..., description="Export metadata including timestamp and version")
    
    class Config:
        from_attributes = True


class ImportData(BaseModel):
    """Schema for importing data into OmniTrackr"""
    movies: List[MovieCreate] = Field(default=[], description="Movies to import")
    tv_shows: List[TVShowCreate] = Field(default=[], description="TV shows to import")
    anime: List[AnimeCreate] = Field(default=[], description="Anime to import")
    video_games: List[VideoGameCreate] = Field(default=[], description="Video games to import")
    music: List[MusicCreate] = Field(default=[], description="Music to import")
    books: List[BookCreate] = Field(default=[], description="Books to import")
    custom_tabs: List[dict] = Field(default=[], description="Custom tabs to import (optional for backward compatibility)")
    
    class Config:
        from_attributes = True


class ImportResult(BaseModel):
    """Schema for import operation results"""
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
    errors: List[str] = Field(default=[], description="List of errors encountered during import")
    
    class Config:
        from_attributes = True


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
    id: int
    tab_id: int
    
    class Config:
        from_attributes = True


class CustomTabCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Tab name")
    source_type: str = Field("none", description="Metadata source: omdb, jikan, rawg, or none")
    allow_uploads: bool = Field(True, description="Allow poster uploads")
    fields: List[CustomTabFieldCreate] = Field(default=[], max_items=30, description="Field definitions")


class CustomTabUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    source_type: Optional[str] = None
    allow_uploads: Optional[bool] = None
    fields: Optional[List[CustomTabFieldCreate]] = None


class CustomTab(BaseModel):
    id: int
    user_id: int
    name: str
    slug: str
    source_type: str
    allow_uploads: bool
    created_at: Optional[datetime] = None
    fields: List[CustomTabField] = Field(default=[])
    
    class Config:
        from_attributes = True


class CustomTabItemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500, description="Item title")
    field_values: dict = Field(default={}, description="Field values as key-value pairs")
    poster_url: Optional[str] = Field(None, max_length=2000, description="Poster image URL")


class CustomTabItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    field_values: Optional[dict] = None
    poster_url: Optional[str] = Field(None, max_length=2000)


class CustomTabItem(BaseModel):
    id: int
    tab_id: int
    title: str
    field_values: Optional[dict] = None
    poster_url: Optional[str] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
