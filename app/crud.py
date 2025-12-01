"""
CRUD utility functions for the OmniTrackr API.
Encapsulates database operations for fetching, creating, updating,
and deleting movie and TV show entries.
"""
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc, func, or_, and_
from . import models
from . import schemas


# ============================================================================
# User CRUD operations
# ============================================================================

def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    """Get user by username."""
    return db.query(models.User).filter(models.User.username == username).first()


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    """Get user by email."""
    return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_username_or_email(db: Session, username_or_email: str) -> Optional[models.User]:
    """Get user by username or email (optimized single query)."""
    return db.query(models.User).filter(
        or_(
            models.User.username == username_or_email,
            models.User.email == username_or_email
        )
    ).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    """Get user by ID."""
    return db.query(models.User).filter(models.User.id == user_id).first()


def create_user(db: Session, user: schemas.UserCreate, hashed_password: str, verification_token: str = None) -> models.User:
    """Create a new user with hashed password."""
    db_user = models.User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password,
        is_verified=False,
        verification_token=verification_token
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: int, user_update: schemas.UserUpdate) -> Optional[models.User]:
    """Update user information."""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    
    update_dict = user_update.dict(exclude_unset=True)
    
    # Check for duplicate username if changing
    if 'username' in update_dict and update_dict['username'] != db_user.username:
        existing_user = get_user_by_username(db, update_dict['username'])
        if existing_user:
            raise ValueError("Username already taken")
        db_user.username = update_dict['username']
    
    # Check for duplicate email if changing
    if 'email' in update_dict and update_dict['email'] != db_user.email:
        existing_user = get_user_by_email(db, update_dict['email'])
        if existing_user:
            raise ValueError("Email already registered")
        db_user.email = update_dict['email']
    
    # Update password if provided (should be hashed before calling this)
    if 'password' in update_dict:
        db_user.hashed_password = update_dict['password']
    
    db.commit()
    db.refresh(db_user)
    return db_user


def deactivate_user(db: Session, user_id: int) -> Optional[models.User]:
    """Deactivate a user account (soft delete)."""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    
    db_user.is_active = False
    db_user.deactivated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_user)
    return db_user


def reactivate_user(db: Session, user_id: int) -> Optional[models.User]:
    """Reactivate a deactivated user account (within 90-day window)."""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    
    # Check if account was deactivated and within 90-day window
    if db_user.deactivated_at is None:
        raise ValueError("Account was not deactivated")
    
    days_since_deactivation = (datetime.utcnow() - db_user.deactivated_at).days
    if days_since_deactivation > 90:
        raise ValueError("Account cannot be reactivated after 90 days")
    
    db_user.is_active = True
    db_user.deactivated_at = None
    db.commit()
    db.refresh(db_user)
    return db_user


def update_privacy_settings(db: Session, user_id: int, privacy_settings: schemas.PrivacySettingsUpdate) -> Optional[models.User]:
    """Update user's privacy settings."""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    
    update_dict = privacy_settings.dict(exclude_unset=True)
    
    if 'movies_private' in update_dict:
        db_user.movies_private = update_dict['movies_private']
    if 'tv_shows_private' in update_dict:
        db_user.tv_shows_private = update_dict['tv_shows_private']
    if 'anime_private' in update_dict:
        db_user.anime_private = update_dict['anime_private']
    if 'statistics_private' in update_dict:
        db_user.statistics_private = update_dict['statistics_private']
    
    db.commit()
    db.refresh(db_user)
    return db_user


def get_privacy_settings(db: Session, user_id: int) -> Optional[schemas.PrivacySettings]:
    """Get user's privacy settings."""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    
    return schemas.PrivacySettings(
        movies_private=db_user.movies_private,
        tv_shows_private=db_user.tv_shows_private,
        anime_private=db_user.anime_private,
        statistics_private=db_user.statistics_private
    )


def update_profile_picture(
    db: Session, 
    user_id: int, 
    profile_picture_url: str,
    profile_picture_data: bytes = None,
    profile_picture_mime_type: str = None
) -> Optional[models.User]:
    """Update user's profile picture (database storage)."""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    
    db_user.profile_picture_url = profile_picture_url
    if profile_picture_data is not None:
        db_user.profile_picture_data = profile_picture_data
    if profile_picture_mime_type is not None:
        db_user.profile_picture_mime_type = profile_picture_mime_type
    db.commit()
    db.refresh(db_user)
    return db_user


def reset_profile_picture(db: Session, user_id: int) -> Optional[models.User]:
    """Reset user's profile picture (clear all fields)."""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    
    db_user.profile_picture_url = None
    db_user.profile_picture_data = None
    db_user.profile_picture_mime_type = None
    db.commit()
    db.refresh(db_user)
    return db_user


# ============================================================================
# Movie CRUD operations
# ============================================================================

def get_movies(
    db: Session,
    user_id: int,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
) -> List[models.Movie]:
    query = db.query(models.Movie).filter(models.Movie.user_id == user_id)
    if search:
        like_pattern = f"%{search}%"
        query = query.filter(
            models.Movie.title.ilike(like_pattern) |
            models.Movie.director.ilike(like_pattern)
        )
    sort_order = asc  # default
    if order and order.lower() == "desc":
        sort_order = desc
    if sort_by == "rating":
        query = query.order_by(sort_order(models.Movie.rating))
    elif sort_by == "year":
        query = query.order_by(sort_order(models.Movie.year))
    return query.all()


def get_movie_by_id(db: Session, user_id: int, movie_id: int) -> Optional[models.Movie]:
    return db.query(models.Movie).filter(
        models.Movie.id == movie_id,
        models.Movie.user_id == user_id
    ).first()


def create_movie(db: Session, user_id: int, movie: schemas.MovieCreate) -> models.Movie:
    movie_dict = movie.dict()
    # Round rating to one decimal place if provided
    if movie_dict.get('rating') is not None:
        movie_dict['rating'] = round(float(movie_dict['rating']), 1)
    db_movie = models.Movie(**movie_dict, user_id=user_id)
    db.add(db_movie)
    db.commit()
    db.refresh(db_movie)
    return db_movie


def update_movie(db: Session, user_id: int, movie_id: int, movie_update: schemas.MovieUpdate) -> Optional[models.Movie]:
    db_movie = get_movie_by_id(db, user_id, movie_id)
    if db_movie is None:
        return None
    update_dict = movie_update.dict(exclude_unset=True)
    # Round rating to one decimal place if provided
    if 'rating' in update_dict and update_dict['rating'] is not None:
        update_dict['rating'] = round(float(update_dict['rating']), 1)
    for field, value in update_dict.items():
        setattr(db_movie, field, value)
    db.commit()
    db.refresh(db_movie)
    return db_movie


def delete_movie(db: Session, user_id: int, movie_id: int) -> Optional[models.Movie]:
    db_movie = get_movie_by_id(db, user_id, movie_id)
    if db_movie is None:
        return None
    db.delete(db_movie)
    db.commit()
    return db_movie


#  TV Show CRUD operations
def get_tv_shows(
    db: Session,
    user_id: int,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
) -> List[models.TVShow]:
    query = db.query(models.TVShow).filter(models.TVShow.user_id == user_id).filter(models.TVShow.user_id == user_id)
    if search:
        like_pattern = f"%{search}%"
        query = query.filter(
            models.TVShow.title.ilike(like_pattern)
        )
    sort_order = asc  # default
    if order and order.lower() == "desc":
        sort_order = desc
    if sort_by == "rating":
        query = query.order_by(sort_order(models.TVShow.rating))
    elif sort_by == "year":
        query = query.order_by(sort_order(models.TVShow.year))
    return query.all()


def get_tv_show_by_id(db: Session, user_id: int, tv_show_id: int) -> Optional[models.TVShow]:
    return db.query(models.TVShow).filter(models.TVShow.user_id == user_id).filter(
        models.TVShow.id == tv_show_id,
        models.TVShow.user_id == user_id
    ).first()


def create_tv_show(db: Session, user_id: int, tv_show: schemas.TVShowCreate) -> models.TVShow:
    tv_show_dict = tv_show.dict()
    # Round rating to one decimal place if provided
    if tv_show_dict.get('rating') is not None:
        tv_show_dict['rating'] = round(float(tv_show_dict['rating']), 1)
    db_tv_show = models.TVShow(**tv_show_dict, user_id=user_id)
    db.add(db_tv_show)
    db.commit()
    db.refresh(db_tv_show)
    return db_tv_show


def update_tv_show(db: Session, user_id: int, tv_show_id: int, tv_show_update: schemas.TVShowUpdate) -> Optional[models.TVShow]:
    db_tv_show = get_tv_show_by_id(db, user_id, tv_show_id)
    if db_tv_show is None:
        return None
    update_dict = tv_show_update.dict(exclude_unset=True)
    # Round rating to one decimal place if provided
    if 'rating' in update_dict and update_dict['rating'] is not None:
        update_dict['rating'] = round(float(update_dict['rating']), 1)
    for field, value in update_dict.items():
        setattr(db_tv_show, field, value)
    db.commit()
    db.refresh(db_tv_show)
    return db_tv_show


def delete_tv_show(db: Session, user_id: int, tv_show_id: int) -> Optional[models.TVShow]:
    db_tv_show = get_tv_show_by_id(db, user_id, tv_show_id)
    if db_tv_show is None:
        return None
    db.delete(db_tv_show)
    db.commit()
    return db_tv_show


# Anime functions
def get_anime(
    db: Session,
    user_id: int,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = None,
) -> List[models.Anime]:
    query = db.query(models.Anime).filter(models.Anime.user_id == user_id).filter(models.Anime.user_id == user_id)
    if search:
        like_pattern = f"%{search}%"
        query = query.filter(
            models.Anime.title.ilike(like_pattern)
        )
    sort_order = asc  # default
    if order and order.lower() == "desc":
        sort_order = desc
    if sort_by == "rating":
        query = query.order_by(sort_order(models.Anime.rating))
    elif sort_by == "year":
        query = query.order_by(sort_order(models.Anime.year))
    return query.all()


def get_anime_by_id(db: Session, user_id: int, anime_id: int) -> Optional[models.Anime]:
    return db.query(models.Anime).filter(models.Anime.user_id == user_id).filter(
        models.Anime.id == anime_id,
        models.Anime.user_id == user_id
    ).first()


def create_anime(db: Session, user_id: int, anime: schemas.AnimeCreate) -> models.Anime:
    anime_dict = anime.dict()
    # Round rating to one decimal place if provided
    if anime_dict.get('rating') is not None:
        anime_dict['rating'] = round(float(anime_dict['rating']), 1)
    db_anime = models.Anime(**anime_dict, user_id=user_id)
    db.add(db_anime)
    db.commit()
    db.refresh(db_anime)
    return db_anime


def update_anime(db: Session, user_id: int, anime_id: int, anime_update: schemas.AnimeUpdate) -> Optional[models.Anime]:
    db_anime = get_anime_by_id(db, user_id, anime_id)
    if db_anime is None:
        return None
    update_dict = anime_update.dict(exclude_unset=True)
    # Round rating to one decimal place if provided
    if 'rating' in update_dict and update_dict['rating'] is not None:
        update_dict['rating'] = round(float(update_dict['rating']), 1)
    for field, value in update_dict.items():
        setattr(db_anime, field, value)
    db.commit()
    db.refresh(db_anime)
    return db_anime


def delete_anime(db: Session, user_id: int, anime_id: int) -> Optional[models.Anime]:
    db_anime = get_anime_by_id(db, user_id, anime_id)
    if db_anime is None:
        return None
    db.delete(db_anime)
    db.commit()
    return db_anime


# Export/Import functions
def get_all_movies(db: Session, user_id: int) -> List[models.Movie]:
    """Get all movies for export"""
    return db.query(models.Movie).filter(models.Movie.user_id == user_id).all()


def get_all_tv_shows(db: Session, user_id: int) -> List[models.TVShow]:
    """Get all TV shows for export"""
    return db.query(models.TVShow).filter(models.TVShow.user_id == user_id).all()


def get_all_anime(db: Session, user_id: int) -> List[models.Anime]:
    """Get all anime for export"""
    return db.query(models.Anime).filter(models.Anime.user_id == user_id).all()


def find_movie_by_title_and_director(db: Session, user_id: int, title: str, director: str) -> Optional[models.Movie]:
    """Find a movie by title and director for import conflict resolution"""
    return db.query(models.Movie).filter(models.Movie.user_id == user_id).filter(
        models.Movie.user_id == user_id,
        models.Movie.title == title,
        models.Movie.director == director
    ).first()


def find_tv_show_by_title_and_year(db: Session, user_id: int, title: str, year: int) -> Optional[models.TVShow]:
    """Find a TV show by title and year for import conflict resolution"""
    return db.query(models.TVShow).filter(models.TVShow.user_id == user_id).filter(
        models.TVShow.user_id == user_id,
        models.TVShow.title == title,
        models.TVShow.year == year
    ).first()


def find_anime_by_title_and_year(db: Session, user_id: int, title: str, year: int) -> Optional[models.Anime]:
    """Find an anime by title and year for import conflict resolution"""
    return db.query(models.Anime).filter(models.Anime.user_id == user_id).filter(
        models.Anime.user_id == user_id,
        models.Anime.title == title,
        models.Anime.year == year
    ).first()


def import_movies(db: Session, user_id: int, movies: List[schemas.MovieCreate]) -> tuple[int, int, List[str]]:
    """Import movies, returning (created_count, updated_count, errors)"""
    created = 0
    updated = 0
    errors = []
    
    for movie_data in movies:
        try:
            # Check if movie already exists
            existing_movie = find_movie_by_title_and_director(
                db, user_id, movie_data.title, movie_data.director
            )
            
            if existing_movie:
                # Update existing movie
                for field, value in movie_data.dict(exclude_unset=True).items():
                    setattr(existing_movie, field, value)
                updated += 1
            else:
                # Create new movie
                db_movie = models.Movie(**movie_data.dict(), user_id=user_id)
                db.add(db_movie)
                created += 1
        except Exception as e:
            errors.append(f"Error importing movie '{movie_data.title}': {str(e)}")
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append(f"Database error during movie import: {str(e)}")
        return 0, 0, errors
    
    return created, updated, errors


def import_tv_shows(db: Session, user_id: int, tv_shows: List[schemas.TVShowCreate]) -> tuple[int, int, List[str]]:
    """Import TV shows, returning (created_count, updated_count, errors)"""
    created = 0
    updated = 0
    errors = []
    
    for tv_show_data in tv_shows:
        try:
            # Check if TV show already exists
            existing_tv_show = find_tv_show_by_title_and_year(
                db, user_id, tv_show_data.title, tv_show_data.year
            )
            
            if existing_tv_show:
                # Update existing TV show
                for field, value in tv_show_data.dict(exclude_unset=True).items():
                    setattr(existing_tv_show, field, value)
                updated += 1
            else:
                # Create new TV show
                db_tv_show = models.TVShow(**tv_show_data.dict(), user_id=user_id)
                db.add(db_tv_show)
                created += 1
        except Exception as e:
            errors.append(f"Error importing TV show '{tv_show_data.title}': {str(e)}")
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append(f"Database error during TV show import: {str(e)}")
        return 0, 0, errors
    
    return created, updated, errors


def import_anime(db: Session, user_id: int, anime: List[schemas.AnimeCreate]) -> tuple[int, int, List[str]]:
    """Import anime, returning (created_count, updated_count, errors)"""
    created = 0
    updated = 0
    errors = []
    
    for anime_data in anime:
        try:
            # Check if anime already exists
            existing_anime = find_anime_by_title_and_year(
                db, user_id, anime_data.title, anime_data.year
            )
            
            if existing_anime:
                # Update existing anime
                for field, value in anime_data.dict(exclude_unset=True).items():
                    setattr(existing_anime, field, value)
                updated += 1
            else:
                # Create new anime
                db_anime = models.Anime(**anime_data.dict(), user_id=user_id)
                db.add(db_anime)
                created += 1
        except Exception as e:
            errors.append(f"Error importing anime '{anime_data.title}': {str(e)}")
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append(f"Database error during anime import: {str(e)}")
        return 0, 0, errors
    
    return created, updated, errors


# Statistics functions
def get_watch_statistics(db: Session, user_id: int) -> dict:
    """Get overall watch statistics"""
    total_movies = db.query(models.Movie).filter(models.Movie.user_id == user_id).count()
    watched_movies = db.query(models.Movie).filter(models.Movie.user_id == user_id).filter(models.Movie.watched == True).count()
    total_tv_shows = db.query(models.TVShow).filter(models.TVShow.user_id == user_id).count()
    watched_tv_shows = db.query(models.TVShow).filter(models.TVShow.user_id == user_id).filter(models.TVShow.watched == True).count()
    total_anime = db.query(models.Anime).filter(models.Anime.user_id == user_id).count()
    watched_anime = db.query(models.Anime).filter(models.Anime.user_id == user_id).filter(models.Anime.watched == True).count()
    
    total_items = total_movies + total_tv_shows + total_anime
    watched_items = watched_movies + watched_tv_shows + watched_anime
    
    return {
        "total_movies": total_movies,
        "watched_movies": watched_movies,
        "unwatched_movies": total_movies - watched_movies,
        "total_tv_shows": total_tv_shows,
        "watched_tv_shows": watched_tv_shows,
        "unwatched_tv_shows": total_tv_shows - watched_tv_shows,
        "total_anime": total_anime,
        "watched_anime": watched_anime,
        "unwatched_anime": total_anime - watched_anime,
        "total_items": total_items,
        "watched_items": watched_items,
        "unwatched_items": total_items - watched_items,
        "completion_percentage": round((watched_items / total_items * 100) if total_items > 0 else 0, 1)
    }


def get_rating_statistics(db: Session, user_id: int) -> dict:
    """Get rating distribution statistics"""
    # Movies rating stats
    movie_ratings = db.query(models.Movie.rating).filter(
        models.Movie.user_id == user_id
    ).filter(models.Movie.rating.isnot(None)).all()
    movie_ratings = [r[0] for r in movie_ratings]
    
    # TV shows rating stats
    tv_ratings = db.query(models.TVShow.rating).filter(
        models.TVShow.user_id == user_id
    ).filter(models.TVShow.rating.isnot(None)).all()
    tv_ratings = [r[0] for r in tv_ratings]
    
    # Anime rating stats
    anime_ratings = db.query(models.Anime.rating).filter(
        models.Anime.user_id == user_id
    ).filter(models.Anime.rating.isnot(None)).all()
    anime_ratings = [r[0] for r in anime_ratings]
    
    all_ratings = movie_ratings + tv_ratings + anime_ratings
    
    if not all_ratings:
        return {
            "average_rating": 0,
            "total_rated_items": 0,
            "rating_distribution": {},
            "highest_rated": [],
            "lowest_rated": []
        }
    
    # Calculate average
    avg_rating = round(sum(all_ratings) / len(all_ratings), 1)
    
    # Rating distribution (1-10) - round decimal ratings to nearest integer
    distribution = {}
    for i in range(1, 11):
        # Round ratings to nearest integer for distribution buckets
        count = sum(1 for rating in all_ratings if round(rating) == i)
        if count > 0:
            distribution[str(i)] = count
    
    # Get highest and lowest rated items
    highest_rating = max(all_ratings)
    lowest_rating = min(all_ratings)
    
    # Find items with highest rating
    highest_movies = db.query(models.Movie).filter(models.Movie.user_id == user_id).filter(models.Movie.rating == highest_rating).limit(5).all()
    highest_tv = db.query(models.TVShow).filter(models.TVShow.user_id == user_id).filter(models.TVShow.rating == highest_rating).limit(5).all()
    highest_anime = db.query(models.Anime).filter(models.Anime.user_id == user_id).filter(models.Anime.rating == highest_rating).limit(5).all()
    highest_rated = [
        {"title": m.title, "type": "Movie", "rating": m.rating} for m in highest_movies
    ] + [
        {"title": t.title, "type": "TV Show", "rating": t.rating} for t in highest_tv
    ] + [
        {"title": a.title, "type": "Anime", "rating": a.rating} for a in highest_anime
    ]
    
    # Find items with lowest rating
    lowest_movies = db.query(models.Movie).filter(models.Movie.user_id == user_id).filter(models.Movie.rating == lowest_rating).limit(5).all()
    lowest_tv = db.query(models.TVShow).filter(models.TVShow.user_id == user_id).filter(models.TVShow.rating == lowest_rating).limit(5).all()
    lowest_anime = db.query(models.Anime).filter(models.Anime.user_id == user_id).filter(models.Anime.rating == lowest_rating).limit(5).all()
    lowest_rated = [
        {"title": m.title, "type": "Movie", "rating": m.rating} for m in lowest_movies
    ] + [
        {"title": t.title, "type": "TV Show", "rating": t.rating} for t in lowest_tv
    ] + [
        {"title": a.title, "type": "Anime", "rating": a.rating} for a in lowest_anime
    ]
    
    return {
        "average_rating": avg_rating,
        "total_rated_items": len(all_ratings),
        "rating_distribution": distribution,
        "highest_rated": highest_rated[:5],
        "lowest_rated": lowest_rated[:5]
    }


def get_year_statistics(db: Session, user_id: int) -> dict:
    """Get statistics by year"""
    # Movies by year
    movie_years = db.query(models.Movie.year, func.count(models.Movie.id)).filter(
        models.Movie.user_id == user_id
    ).group_by(models.Movie.year).all()
    movie_data = {str(year): count for year, count in movie_years}
    
    # TV shows by year
    tv_years = db.query(models.TVShow.year, func.count(models.TVShow.id)).filter(
        models.TVShow.user_id == user_id
    ).group_by(models.TVShow.year).all()
    tv_data = {str(year): count for year, count in tv_years}
    
    # Anime by year
    anime_years = db.query(models.Anime.year, func.count(models.Anime.id)).filter(
        models.Anime.user_id == user_id
    ).group_by(models.Anime.year).all()
    anime_data = {str(year): count for year, count in anime_years}
    
    # Get all years
    all_years = set(movie_data.keys()) | set(tv_data.keys()) | set(anime_data.keys())
    all_years = sorted([int(year) for year in all_years])
    
    # Decade analysis
    decade_stats = {}
    for year in all_years:
        decade = (year // 10) * 10
        decade_key = f"{decade}s"
        if decade_key not in decade_stats:
            decade_stats[decade_key] = {"movies": 0, "tv_shows": 0, "anime": 0}
        decade_stats[decade_key]["movies"] += movie_data.get(str(year), 0)
        decade_stats[decade_key]["tv_shows"] += tv_data.get(str(year), 0)
        decade_stats[decade_key]["anime"] += anime_data.get(str(year), 0)
    
    return {
        "movies_by_year": movie_data,
        "tv_shows_by_year": tv_data,
        "anime_by_year": anime_data,
        "all_years": all_years,
        "decade_stats": decade_stats,
        "oldest_year": min(all_years) if all_years else None,
        "newest_year": max(all_years) if all_years else None
    }


def get_director_statistics(db: Session, user_id: int) -> dict:
    """Get statistics by director/creator"""
    # Top directors
    director_counts = db.query(
        models.Movie.director, 
        func.count(models.Movie.id).label('count')
    ).filter(
        models.Movie.user_id == user_id
    ).group_by(models.Movie.director).order_by(func.count(models.Movie.id).desc()).limit(10).all()
    
    # Directors with highest average ratings
    director_ratings = db.query(
        models.Movie.director,
        func.avg(models.Movie.rating).label('avg_rating'),
        func.count(models.Movie.id).label('count')
    ).filter(
        models.Movie.user_id == user_id
    ).filter(
        models.Movie.rating.isnot(None)
    ).group_by(models.Movie.director).order_by(
        func.avg(models.Movie.rating).desc(),
        func.count(models.Movie.id).desc()  # Secondary sort by movie count for ties
    ).limit(10).all()
    
    return {
        "top_directors": [{"director": d[0], "count": d[1]} for d in director_counts],
        "highest_rated_directors": [
            {"director": d[0], "avg_rating": round(d[1], 1), "count": d[2]} 
            for d in director_ratings
        ]
    }


# ============================================================================
# Friend Request CRUD operations
# ============================================================================

def create_friend_request(db: Session, sender_id: int, receiver_id: int) -> Optional[models.FriendRequest]:
    """Create a new friend request."""
    # Check if users are already friends
    if are_friends(db, sender_id, receiver_id):
        raise ValueError("Users are already friends")
    
    # Check if there's already a pending request
    existing = db.query(models.FriendRequest).filter(
        or_(
            and_(models.FriendRequest.sender_id == sender_id, models.FriendRequest.receiver_id == receiver_id),
            and_(models.FriendRequest.sender_id == receiver_id, models.FriendRequest.receiver_id == sender_id)
        ),
        models.FriendRequest.status == "pending"
    ).first()
    
    if existing:
        raise ValueError("Friend request already exists")
    
    # Create the request
    friend_request = models.FriendRequest(
        sender_id=sender_id,
        receiver_id=receiver_id,
        status="pending",
        expires_at=datetime.utcnow() + timedelta(days=30)
    )
    db.add(friend_request)
    db.commit()
    db.refresh(friend_request)
    
    # Create notification for receiver
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
    
    # Check if request is expired
    if friend_request.expires_at < datetime.utcnow():
        friend_request.status = "expired"
        db.commit()
        raise ValueError("Friend request has expired")
    
    # Delete the notification for the receiver (the one who received the friend request)
    notification = db.query(models.Notification).filter(
        models.Notification.friend_request_id == request_id,
        models.Notification.user_id == user_id
    ).first()
    if notification:
        db.delete(notification)
    
    # Update request status
    friend_request.status = "accepted"
    db.commit()
    
    # Create friendship (ensure user1_id < user2_id)
    user1_id = min(friend_request.sender_id, friend_request.receiver_id)
    user2_id = max(friend_request.sender_id, friend_request.receiver_id)
    create_friendship(db, user1_id, user2_id)
    
    # Create notifications
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
    
    # Verify user is the receiver
    if friend_request.receiver_id != user_id:
        raise ValueError("You can only deny friend requests sent to you")
    
    if friend_request.status != "pending":
        raise ValueError("Friend request is not pending")
    
    # Delete the notification for the receiver (the one who received the friend request)
    notification = db.query(models.Notification).filter(
        models.Notification.friend_request_id == request_id,
        models.Notification.user_id == user_id
    ).first()
    if notification:
        db.delete(notification)
    
    # Update request status
    friend_request.status = "denied"
    db.commit()
    
    return friend_request


def cancel_friend_request(db: Session, request_id: int, user_id: int) -> Optional[models.FriendRequest]:
    """Cancel a sent friend request."""
    friend_request = get_friend_request(db, request_id)
    if not friend_request:
        return None
    
    # Verify user is the sender
    if friend_request.sender_id != user_id:
        raise ValueError("You can only cancel friend requests you sent")
    
    if friend_request.status != "pending":
        raise ValueError("Friend request is not pending")
    
    # Update request status
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
    # Check if friendship already exists
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
    return db.query(models.Notification).filter(
        models.Notification.user_id == user_id,
        models.Notification.read_at.is_(None)
    ).count()


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
    statistics_available = None
    
    if not friend.movies_private:
        movies_count = db.query(models.Movie).filter(models.Movie.user_id == friend_id).count()
    
    if not friend.tv_shows_private:
        tv_shows_count = db.query(models.TVShow).filter(models.TVShow.user_id == friend_id).count()
    
    if not friend.anime_private:
        anime_count = db.query(models.Anime).filter(models.Anime.user_id == friend_id).count()
    
    if not friend.statistics_private:
        statistics_available = True
    
    return schemas.FriendProfileSummary(
        username=friend.username,
        movies_count=movies_count,
        tv_shows_count=tv_shows_count,
        anime_count=anime_count,
        statistics_available=statistics_available,
        movies_private=friend.movies_private,
        tv_shows_private=friend.tv_shows_private,
        anime_private=friend.anime_private,
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

