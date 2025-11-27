"""
CRUD utility functions for the OmniTrackr API.
Encapsulates database operations for fetching, creating, updating,
and deleting movie and TV show entries.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc, func
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


# Export/Import functions
def get_all_movies(db: Session, user_id: int) -> List[models.Movie]:
    """Get all movies for export"""
    return db.query(models.Movie).filter(models.Movie.user_id == user_id).all()


def get_all_tv_shows(db: Session, user_id: int) -> List[models.TVShow]:
    """Get all TV shows for export"""
    return db.query(models.TVShow).filter(models.TVShow.user_id == user_id).all()


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


# Statistics functions
def get_watch_statistics(db: Session, user_id: int) -> dict:
    """Get overall watch statistics"""
    total_movies = db.query(models.Movie).filter(models.Movie.user_id == user_id).count()
    watched_movies = db.query(models.Movie).filter(models.Movie.user_id == user_id).filter(models.Movie.watched == True).count()
    total_tv_shows = db.query(models.TVShow).filter(models.TVShow.user_id == user_id).count()
    watched_tv_shows = db.query(models.TVShow).filter(models.TVShow.user_id == user_id).filter(models.TVShow.watched == True).count()
    
    total_items = total_movies + total_tv_shows
    watched_items = watched_movies + watched_tv_shows
    
    return {
        "total_movies": total_movies,
        "watched_movies": watched_movies,
        "unwatched_movies": total_movies - watched_movies,
        "total_tv_shows": total_tv_shows,
        "watched_tv_shows": watched_tv_shows,
        "unwatched_tv_shows": total_tv_shows - watched_tv_shows,
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
    
    all_ratings = movie_ratings + tv_ratings
    
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
    highest_rated = [
        {"title": m.title, "type": "Movie", "rating": m.rating} for m in highest_movies
    ] + [
        {"title": t.title, "type": "TV Show", "rating": t.rating} for t in highest_tv
    ]
    
    # Find items with lowest rating
    lowest_movies = db.query(models.Movie).filter(models.Movie.user_id == user_id).filter(models.Movie.rating == lowest_rating).limit(5).all()
    lowest_tv = db.query(models.TVShow).filter(models.TVShow.user_id == user_id).filter(models.TVShow.rating == lowest_rating).limit(5).all()
    lowest_rated = [
        {"title": m.title, "type": "Movie", "rating": m.rating} for m in lowest_movies
    ] + [
        {"title": t.title, "type": "TV Show", "rating": t.rating} for t in lowest_tv
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
    
    # Get all years
    all_years = set(movie_data.keys()) | set(tv_data.keys())
    all_years = sorted([int(year) for year in all_years])
    
    # Decade analysis
    decade_stats = {}
    for year in all_years:
        decade = (year // 10) * 10
        decade_key = f"{decade}s"
        if decade_key not in decade_stats:
            decade_stats[decade_key] = {"movies": 0, "tv_shows": 0}
        decade_stats[decade_key]["movies"] += movie_data.get(str(year), 0)
        decade_stats[decade_key]["tv_shows"] += tv_data.get(str(year), 0)
    
    return {
        "movies_by_year": movie_data,
        "tv_shows_by_year": tv_data,
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

