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
    password: str = Field(..., min_length=6, description="User password (min 6 characters)")


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
    
    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for updating user information."""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6)


class PasswordChange(BaseModel):
    """Schema for changing password."""
    current_password: str = Field(..., description="Current password for verification")
    new_password: str = Field(..., min_length=6, description="New password (min 6 characters)")


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
    )  # rating is now optional
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


# Export/Import schemas
class ExportData(BaseModel):
    """Schema for exporting all data from OmniTrackr"""
    movies: List[Movie] = Field(..., description="List of all movies")
    tv_shows: List[TVShow] = Field(..., description="List of all TV shows")
    export_metadata: dict = Field(..., description="Export metadata including timestamp and version")
    
    class Config:
        from_attributes = True


class ImportData(BaseModel):
    """Schema for importing data into OmniTrackr"""
    movies: List[MovieCreate] = Field(default=[], description="Movies to import")
    tv_shows: List[TVShowCreate] = Field(default=[], description="TV shows to import")
    
    class Config:
        from_attributes = True


class ImportResult(BaseModel):
    """Schema for import operation results"""
    movies_created: int = Field(..., description="Number of movies created")
    movies_updated: int = Field(..., description="Number of movies updated")
    tv_shows_created: int = Field(..., description="Number of TV shows created")
    tv_shows_updated: int = Field(..., description="Number of TV shows updated")
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
    total_items: int = Field(..., description="Total number of items")
    watched_items: int = Field(..., description="Number of watched items")
    unwatched_items: int = Field(..., description="Number of unwatched items")
    completion_percentage: float = Field(..., description="Percentage of items watched")


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
