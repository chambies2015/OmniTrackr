"""
Statistics CRUD operations for the OmniTrackr API.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func

from .. import models


def get_watch_statistics(db: Session, user_id: int) -> dict:
    """Get overall watch statistics"""
    total_movies = db.query(models.Movie).filter(models.Movie.user_id == user_id).count()
    watched_movies = db.query(models.Movie).filter(models.Movie.user_id == user_id).filter(models.Movie.watched == True).count()
    total_tv_shows = db.query(models.TVShow).filter(models.TVShow.user_id == user_id).count()
    watched_tv_shows = db.query(models.TVShow).filter(models.TVShow.user_id == user_id).filter(models.TVShow.watched == True).count()
    total_anime = db.query(models.Anime).filter(models.Anime.user_id == user_id).count()
    watched_anime = db.query(models.Anime).filter(models.Anime.user_id == user_id).filter(models.Anime.watched == True).count()
    total_video_games = db.query(models.VideoGame).filter(models.VideoGame.user_id == user_id).count()
    played_video_games = db.query(models.VideoGame).filter(models.VideoGame.user_id == user_id).filter(models.VideoGame.played == True).count()
    total_music = db.query(models.Music).filter(models.Music.user_id == user_id).count()
    listened_music = db.query(models.Music).filter(models.Music.user_id == user_id).filter(models.Music.listened == True).count()
    total_books = db.query(models.Book).filter(models.Book.user_id == user_id).count()
    read_books = db.query(models.Book).filter(models.Book.user_id == user_id).filter(models.Book.read == True).count()
    
    total_items = total_movies + total_tv_shows + total_anime + total_video_games + total_music + total_books
    watched_items = watched_movies + watched_tv_shows + watched_anime + played_video_games + listened_music + read_books
    
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
        "total_video_games": total_video_games,
        "played_video_games": played_video_games,
        "unplayed_video_games": total_video_games - played_video_games,
        "total_music": total_music,
        "listened_music": listened_music,
        "unlistened_music": total_music - listened_music,
        "total_books": total_books,
        "read_books": read_books,
        "unread_books": total_books - read_books,
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
    
    # Video games rating stats
    video_game_ratings = db.query(models.VideoGame.rating).filter(
        models.VideoGame.user_id == user_id
    ).filter(models.VideoGame.rating.isnot(None)).all()
    video_game_ratings = [r[0] for r in video_game_ratings]
    
    # Music rating stats
    music_ratings = db.query(models.Music.rating).filter(
        models.Music.user_id == user_id
    ).filter(models.Music.rating.isnot(None)).all()
    music_ratings = [r[0] for r in music_ratings]
    
    # Books rating stats
    book_ratings = db.query(models.Book.rating).filter(
        models.Book.user_id == user_id
    ).filter(models.Book.rating.isnot(None)).all()
    book_ratings = [r[0] for r in book_ratings]
    
    all_ratings = movie_ratings + tv_ratings + anime_ratings + video_game_ratings + music_ratings + book_ratings
    
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
    
    distribution = {}
    for i in range(1, 11):
        count = sum(1 for rating in all_ratings if round(rating) == i)
        if count > 0:
            distribution[str(i)] = count
    
    highest_rating = max(all_ratings)
    lowest_rating = min(all_ratings)
    
    # Find items with highest rating
    highest_movies = db.query(models.Movie).filter(models.Movie.user_id == user_id).filter(models.Movie.rating == highest_rating).limit(5).all()
    highest_tv = db.query(models.TVShow).filter(models.TVShow.user_id == user_id).filter(models.TVShow.rating == highest_rating).limit(5).all()
    highest_anime = db.query(models.Anime).filter(models.Anime.user_id == user_id).filter(models.Anime.rating == highest_rating).limit(5).all()
    highest_video_games = db.query(models.VideoGame).filter(models.VideoGame.user_id == user_id).filter(models.VideoGame.rating == highest_rating).limit(5).all()
    highest_music = db.query(models.Music).filter(models.Music.user_id == user_id).filter(models.Music.rating == highest_rating).limit(5).all()
    highest_books = db.query(models.Book).filter(models.Book.user_id == user_id).filter(models.Book.rating == highest_rating).limit(5).all()
    highest_rated = [
        {"title": m.title, "type": "Movie", "rating": m.rating} for m in highest_movies
    ] + [
        {"title": t.title, "type": "TV Show", "rating": t.rating} for t in highest_tv
    ] + [
        {"title": a.title, "type": "Anime", "rating": a.rating} for a in highest_anime
    ] + [
        {"title": v.title, "type": "Video Game", "rating": v.rating} for v in highest_video_games
    ] + [
        {"title": m.title, "type": "Music", "rating": m.rating} for m in highest_music
    ] + [
        {"title": b.title, "type": "Book", "rating": b.rating} for b in highest_books
    ]
    
    # Find items with lowest rating
    lowest_movies = db.query(models.Movie).filter(models.Movie.user_id == user_id).filter(models.Movie.rating == lowest_rating).limit(5).all()
    lowest_tv = db.query(models.TVShow).filter(models.TVShow.user_id == user_id).filter(models.TVShow.rating == lowest_rating).limit(5).all()
    lowest_anime = db.query(models.Anime).filter(models.Anime.user_id == user_id).filter(models.Anime.rating == lowest_rating).limit(5).all()
    lowest_video_games = db.query(models.VideoGame).filter(models.VideoGame.user_id == user_id).filter(models.VideoGame.rating == lowest_rating).limit(5).all()
    lowest_music = db.query(models.Music).filter(models.Music.user_id == user_id).filter(models.Music.rating == lowest_rating).limit(5).all()
    lowest_books = db.query(models.Book).filter(models.Book.user_id == user_id).filter(models.Book.rating == lowest_rating).limit(5).all()
    lowest_rated = [
        {"title": m.title, "type": "Movie", "rating": m.rating} for m in lowest_movies
    ] + [
        {"title": t.title, "type": "TV Show", "rating": t.rating} for t in lowest_tv
    ] + [
        {"title": a.title, "type": "Anime", "rating": a.rating} for a in lowest_anime
    ] + [
        {"title": v.title, "type": "Video Game", "rating": v.rating} for v in lowest_video_games
    ] + [
        {"title": m.title, "type": "Music", "rating": m.rating} for m in lowest_music
    ] + [
        {"title": b.title, "type": "Book", "rating": b.rating} for b in lowest_books
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
    
    # Video games by year (extract year from release_date)
    video_games = db.query(models.VideoGame).filter(
        models.VideoGame.user_id == user_id,
        models.VideoGame.release_date.isnot(None)
    ).all()
    video_game_data = {}
    for vg in video_games:
        if vg.release_date:
            year = vg.release_date.year
            year_str = str(year)
            video_game_data[year_str] = video_game_data.get(year_str, 0) + 1
    
    # Music by year
    music_years = db.query(models.Music.year, func.count(models.Music.id)).filter(
        models.Music.user_id == user_id
    ).group_by(models.Music.year).all()
    music_data = {str(year): count for year, count in music_years}
    
    # Books by year
    book_years = db.query(models.Book.year, func.count(models.Book.id)).filter(
        models.Book.user_id == user_id
    ).group_by(models.Book.year).all()
    book_data = {str(year): count for year, count in book_years}
    
    all_years = set(movie_data.keys()) | set(tv_data.keys()) | set(anime_data.keys()) | set(video_game_data.keys()) | set(music_data.keys()) | set(book_data.keys())
    all_years = sorted([int(year) for year in all_years])
    
    # Decade analysis
    decade_stats = {}
    for year in all_years:
        decade = (year // 10) * 10
        decade_key = f"{decade}s"
        if decade_key not in decade_stats:
            decade_stats[decade_key] = {"movies": 0, "tv_shows": 0, "anime": 0, "video_games": 0, "music": 0, "books": 0}
        decade_stats[decade_key]["movies"] += movie_data.get(str(year), 0)
        decade_stats[decade_key]["tv_shows"] += tv_data.get(str(year), 0)
        decade_stats[decade_key]["anime"] += anime_data.get(str(year), 0)
        decade_stats[decade_key]["video_games"] += video_game_data.get(str(year), 0)
        decade_stats[decade_key]["music"] += music_data.get(str(year), 0)
        decade_stats[decade_key]["books"] += book_data.get(str(year), 0)
    
    return {
        "movies_by_year": movie_data,
        "tv_shows_by_year": tv_data,
        "anime_by_year": anime_data,
        "video_games_by_year": video_game_data,
        "music_by_year": music_data,
        "books_by_year": book_data,
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


def get_movie_statistics(db: Session, user_id: int) -> dict:
    """Get movie-specific statistics"""
    total_movies = db.query(models.Movie).filter(models.Movie.user_id == user_id).count()
    watched_movies = db.query(models.Movie).filter(models.Movie.user_id == user_id).filter(models.Movie.watched == True).count()
    
    movie_ratings = db.query(models.Movie.rating).filter(
        models.Movie.user_id == user_id
    ).filter(models.Movie.rating.isnot(None)).all()
    movie_ratings = [r[0] for r in movie_ratings]
    
    movie_years = db.query(models.Movie.year, func.count(models.Movie.id)).filter(
        models.Movie.user_id == user_id
    ).group_by(models.Movie.year).all()
    movie_data = {str(year): count for year, count in movie_years}
    
    all_years = sorted([int(year) for year in movie_data.keys()]) if movie_data else []
    
    decade_stats = {}
    for year in all_years:
        decade = (year // 10) * 10
        decade_key = f"{decade}s"
        if decade_key not in decade_stats:
            decade_stats[decade_key] = 0
        decade_stats[decade_key] += movie_data.get(str(year), 0)
    
    if not movie_ratings:
        avg_rating = 0
        distribution = {}
        highest_rated = []
        lowest_rated = []
    else:
        avg_rating = round(sum(movie_ratings) / len(movie_ratings), 1)
        distribution = {}
        for i in range(1, 11):
            count = sum(1 for rating in movie_ratings if round(rating) == i)
            if count > 0:
                distribution[str(i)] = count
        
        highest_rating = max(movie_ratings)
        lowest_rating = min(movie_ratings)
        
        highest_movies = db.query(models.Movie).filter(
            models.Movie.user_id == user_id
        ).filter(models.Movie.rating == highest_rating).limit(5).all()
        highest_rated = [{"title": m.title, "type": "Movie", "rating": m.rating} for m in highest_movies]
        
        lowest_movies = db.query(models.Movie).filter(
            models.Movie.user_id == user_id
        ).filter(models.Movie.rating == lowest_rating).limit(5).all()
        lowest_rated = [{"title": m.title, "type": "Movie", "rating": m.rating} for m in lowest_movies]
    
    director_stats = get_director_statistics(db, user_id)
    
    return {
        "watch_stats": {
            "total_items": total_movies,
            "watched_items": watched_movies,
            "unwatched_items": total_movies - watched_movies,
            "completion_percentage": round((watched_movies / total_movies * 100) if total_movies > 0 else 0, 1)
        },
        "rating_stats": {
            "average_rating": avg_rating,
            "total_rated_items": len(movie_ratings),
            "rating_distribution": distribution,
            "highest_rated": highest_rated[:5],
            "lowest_rated": lowest_rated[:5]
        },
        "year_stats": {
            "items_by_year": movie_data,
            "all_years": all_years,
            "decade_stats": decade_stats,
            "oldest_year": min(all_years) if all_years else None,
            "newest_year": max(all_years) if all_years else None
        },
        "director_stats": director_stats
    }


def get_tv_show_statistics(db: Session, user_id: int) -> dict:
    """Get TV show-specific statistics"""
    total_tv_shows = db.query(models.TVShow).filter(models.TVShow.user_id == user_id).count()
    watched_tv_shows = db.query(models.TVShow).filter(models.TVShow.user_id == user_id).filter(models.TVShow.watched == True).count()
    
    tv_ratings = db.query(models.TVShow.rating).filter(
        models.TVShow.user_id == user_id
    ).filter(models.TVShow.rating.isnot(None)).all()
    tv_ratings = [r[0] for r in tv_ratings]
    
    tv_years = db.query(models.TVShow.year, func.count(models.TVShow.id)).filter(
        models.TVShow.user_id == user_id
    ).group_by(models.TVShow.year).all()
    tv_data = {str(year): count for year, count in tv_years}
    
    all_years = sorted([int(year) for year in tv_data.keys()]) if tv_data else []
    
    decade_stats = {}
    for year in all_years:
        decade = (year // 10) * 10
        decade_key = f"{decade}s"
        if decade_key not in decade_stats:
            decade_stats[decade_key] = 0
        decade_stats[decade_key] += tv_data.get(str(year), 0)
    
    if not tv_ratings:
        avg_rating = 0
        distribution = {}
        highest_rated = []
        lowest_rated = []
    else:
        avg_rating = round(sum(tv_ratings) / len(tv_ratings), 1)
        distribution = {}
        for i in range(1, 11):
            count = sum(1 for rating in tv_ratings if round(rating) == i)
            if count > 0:
                distribution[str(i)] = count
        
        highest_rating = max(tv_ratings)
        lowest_rating = min(tv_ratings)
        
        highest_tv = db.query(models.TVShow).filter(
            models.TVShow.user_id == user_id
        ).filter(models.TVShow.rating == highest_rating).limit(5).all()
        highest_rated = [{"title": t.title, "type": "TV Show", "rating": t.rating} for t in highest_tv]
        
        lowest_tv = db.query(models.TVShow).filter(
            models.TVShow.user_id == user_id
        ).filter(models.TVShow.rating == lowest_rating).limit(5).all()
        lowest_rated = [{"title": t.title, "type": "TV Show", "rating": t.rating} for t in lowest_tv]
    
    seasons_episodes = db.query(
        func.sum(models.TVShow.seasons).label('total_seasons'),
        func.sum(models.TVShow.episodes).label('total_episodes'),
        func.avg(models.TVShow.seasons).label('avg_seasons'),
        func.avg(models.TVShow.episodes).label('avg_episodes')
    ).filter(
        models.TVShow.user_id == user_id
    ).first()
    
    total_seasons = int(seasons_episodes[0] or 0)
    total_episodes = int(seasons_episodes[1] or 0)
    avg_seasons = round(float(seasons_episodes[2] or 0), 1)
    avg_episodes = round(float(seasons_episodes[3] or 0), 1)
    
    most_seasons = db.query(models.TVShow).filter(
        models.TVShow.user_id == user_id,
        models.TVShow.seasons.isnot(None)
    ).order_by(models.TVShow.seasons.desc()).limit(5).all()
    
    most_episodes = db.query(models.TVShow).filter(
        models.TVShow.user_id == user_id,
        models.TVShow.episodes.isnot(None)
    ).order_by(models.TVShow.episodes.desc()).limit(5).all()
    
    return {
        "watch_stats": {
            "total_items": total_tv_shows,
            "watched_items": watched_tv_shows,
            "unwatched_items": total_tv_shows - watched_tv_shows,
            "completion_percentage": round((watched_tv_shows / total_tv_shows * 100) if total_tv_shows > 0 else 0, 1)
        },
        "rating_stats": {
            "average_rating": avg_rating,
            "total_rated_items": len(tv_ratings),
            "rating_distribution": distribution,
            "highest_rated": highest_rated[:5],
            "lowest_rated": lowest_rated[:5]
        },
        "year_stats": {
            "items_by_year": tv_data,
            "all_years": all_years,
            "decade_stats": decade_stats,
            "oldest_year": min(all_years) if all_years else None,
            "newest_year": max(all_years) if all_years else None
        },
        "seasons_episodes_stats": {
            "total_seasons": total_seasons,
            "total_episodes": total_episodes,
            "average_seasons": avg_seasons,
            "average_episodes": avg_episodes,
            "shows_with_most_seasons": [{"title": s.title, "seasons": s.seasons} for s in most_seasons],
            "shows_with_most_episodes": [{"title": s.title, "episodes": s.episodes} for s in most_episodes]
        }
    }


def get_anime_statistics(db: Session, user_id: int) -> dict:
    """Get anime-specific statistics"""
    total_anime = db.query(models.Anime).filter(models.Anime.user_id == user_id).count()
    watched_anime = db.query(models.Anime).filter(models.Anime.user_id == user_id).filter(models.Anime.watched == True).count()
    
    anime_ratings = db.query(models.Anime.rating).filter(
        models.Anime.user_id == user_id
    ).filter(models.Anime.rating.isnot(None)).all()
    anime_ratings = [r[0] for r in anime_ratings]
    
    anime_years = db.query(models.Anime.year, func.count(models.Anime.id)).filter(
        models.Anime.user_id == user_id
    ).group_by(models.Anime.year).all()
    anime_data = {str(year): count for year, count in anime_years}
    
    all_years = sorted([int(year) for year in anime_data.keys()]) if anime_data else []
    
    decade_stats = {}
    for year in all_years:
        decade = (year // 10) * 10
        decade_key = f"{decade}s"
        if decade_key not in decade_stats:
            decade_stats[decade_key] = 0
        decade_stats[decade_key] += anime_data.get(str(year), 0)
    
    if not anime_ratings:
        avg_rating = 0
        distribution = {}
        highest_rated = []
        lowest_rated = []
    else:
        avg_rating = round(sum(anime_ratings) / len(anime_ratings), 1)
        distribution = {}
        for i in range(1, 11):
            count = sum(1 for rating in anime_ratings if round(rating) == i)
            if count > 0:
                distribution[str(i)] = count
        
        highest_rating = max(anime_ratings)
        lowest_rating = min(anime_ratings)
        
        highest_anime = db.query(models.Anime).filter(
            models.Anime.user_id == user_id
        ).filter(models.Anime.rating == highest_rating).limit(5).all()
        highest_rated = [{"title": a.title, "type": "Anime", "rating": a.rating} for a in highest_anime]
        
        lowest_anime = db.query(models.Anime).filter(
            models.Anime.user_id == user_id
        ).filter(models.Anime.rating == lowest_rating).limit(5).all()
        lowest_rated = [{"title": a.title, "type": "Anime", "rating": a.rating} for a in lowest_anime]
    
    seasons_episodes = db.query(
        func.sum(models.Anime.seasons).label('total_seasons'),
        func.sum(models.Anime.episodes).label('total_episodes'),
        func.avg(models.Anime.seasons).label('avg_seasons'),
        func.avg(models.Anime.episodes).label('avg_episodes')
    ).filter(
        models.Anime.user_id == user_id
    ).first()
    
    total_seasons = int(seasons_episodes[0] or 0)
    total_episodes = int(seasons_episodes[1] or 0)
    avg_seasons = round(float(seasons_episodes[2] or 0), 1)
    avg_episodes = round(float(seasons_episodes[3] or 0), 1)
    
    most_seasons = db.query(models.Anime).filter(
        models.Anime.user_id == user_id,
        models.Anime.seasons.isnot(None)
    ).order_by(models.Anime.seasons.desc()).limit(5).all()
    
    most_episodes = db.query(models.Anime).filter(
        models.Anime.user_id == user_id,
        models.Anime.episodes.isnot(None)
    ).order_by(models.Anime.episodes.desc()).limit(5).all()
    
    return {
        "watch_stats": {
            "total_items": total_anime,
            "watched_items": watched_anime,
            "unwatched_items": total_anime - watched_anime,
            "completion_percentage": round((watched_anime / total_anime * 100) if total_anime > 0 else 0, 1)
        },
        "rating_stats": {
            "average_rating": avg_rating,
            "total_rated_items": len(anime_ratings),
            "rating_distribution": distribution,
            "highest_rated": highest_rated[:5],
            "lowest_rated": lowest_rated[:5]
        },
        "year_stats": {
            "items_by_year": anime_data,
            "all_years": all_years,
            "decade_stats": decade_stats,
            "oldest_year": min(all_years) if all_years else None,
            "newest_year": max(all_years) if all_years else None
        },
        "seasons_episodes_stats": {
            "total_seasons": total_seasons,
            "total_episodes": total_episodes,
            "average_seasons": avg_seasons,
            "average_episodes": avg_episodes,
            "shows_with_most_seasons": [{"title": s.title, "seasons": s.seasons} for s in most_seasons],
            "shows_with_most_episodes": [{"title": s.title, "episodes": s.episodes} for s in most_episodes]
        }
    }


def get_video_game_statistics(db: Session, user_id: int) -> dict:
    """Get video game-specific statistics"""
    total_video_games = db.query(models.VideoGame).filter(models.VideoGame.user_id == user_id).count()
    played_video_games = db.query(models.VideoGame).filter(models.VideoGame.user_id == user_id).filter(models.VideoGame.played == True).count()
    
    video_game_ratings = db.query(models.VideoGame.rating).filter(
        models.VideoGame.user_id == user_id
    ).filter(models.VideoGame.rating.isnot(None)).all()
    video_game_ratings = [r[0] for r in video_game_ratings]
    
    video_games = db.query(models.VideoGame).filter(
        models.VideoGame.user_id == user_id,
        models.VideoGame.release_date.isnot(None)
    ).all()
    video_game_data = {}
    for vg in video_games:
        if vg.release_date:
            year = vg.release_date.year
            year_str = str(year)
            video_game_data[year_str] = video_game_data.get(year_str, 0) + 1
    
    all_years = sorted([int(year) for year in video_game_data.keys()]) if video_game_data else []
    
    decade_stats = {}
    for year in all_years:
        decade = (year // 10) * 10
        decade_key = f"{decade}s"
        if decade_key not in decade_stats:
            decade_stats[decade_key] = 0
        decade_stats[decade_key] += video_game_data.get(str(year), 0)
    
    if not video_game_ratings:
        avg_rating = 0
        distribution = {}
        highest_rated = []
        lowest_rated = []
    else:
        avg_rating = round(sum(video_game_ratings) / len(video_game_ratings), 1)
        distribution = {}
        for i in range(1, 11):
            count = sum(1 for rating in video_game_ratings if round(rating) == i)
            if count > 0:
                distribution[str(i)] = count
        
        highest_rating = max(video_game_ratings)
        lowest_rating = min(video_game_ratings)
        
        highest_video_games = db.query(models.VideoGame).filter(
            models.VideoGame.user_id == user_id
        ).filter(models.VideoGame.rating == highest_rating).limit(5).all()
        highest_rated = [{"title": v.title, "type": "Video Game", "rating": v.rating} for v in highest_video_games]
        
        lowest_video_games = db.query(models.VideoGame).filter(
            models.VideoGame.user_id == user_id
        ).filter(models.VideoGame.rating == lowest_rating).limit(5).all()
        lowest_rated = [{"title": v.title, "type": "Video Game", "rating": v.rating} for v in lowest_video_games]
    
    all_games = db.query(models.VideoGame).filter(models.VideoGame.user_id == user_id).all()
    genre_counts = {}
    played_genre_counts = {}
    
    for game in all_games:
        if game.genres:
            genres = [g.strip() for g in game.genres.split(',')]
            for genre in genres:
                if genre:
                    genre_counts[genre] = genre_counts.get(genre, 0) + 1
                    if game.played:
                        played_genre_counts[genre] = played_genre_counts.get(genre, 0) + 1
    
    sorted_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)
    top_genres = [{"genre": genre, "count": count} for genre, count in sorted_genres[:10]]
    
    sorted_played_genres = sorted(played_genre_counts.items(), key=lambda x: x[1], reverse=True)
    most_played_genres = [{"genre": genre, "count": count} for genre, count in sorted_played_genres[:10]]
    
    return {
        "watch_stats": {
            "total_items": total_video_games,
            "watched_items": played_video_games,
            "unwatched_items": total_video_games - played_video_games,
            "completion_percentage": round((played_video_games / total_video_games * 100) if total_video_games > 0 else 0, 1)
        },
        "rating_stats": {
            "average_rating": avg_rating,
            "total_rated_items": len(video_game_ratings),
            "rating_distribution": distribution,
            "highest_rated": highest_rated[:5],
            "lowest_rated": lowest_rated[:5]
        },
        "year_stats": {
            "items_by_year": video_game_data,
            "all_years": all_years,
            "decade_stats": decade_stats,
            "oldest_year": min(all_years) if all_years else None,
            "newest_year": max(all_years) if all_years else None
        },
        "genre_stats": {
            "genre_distribution": genre_counts,
            "top_genres": top_genres,
            "most_played_genres": most_played_genres
        }
    }


def get_music_statistics(db: Session, user_id: int) -> dict:
    """Get music-specific statistics"""
    total_music = db.query(models.Music).filter(models.Music.user_id == user_id).count()
    listened_music = db.query(models.Music).filter(models.Music.user_id == user_id).filter(models.Music.listened == True).count()
    
    music_ratings = db.query(models.Music.rating).filter(
        models.Music.user_id == user_id
    ).filter(models.Music.rating.isnot(None)).all()
    music_ratings = [r[0] for r in music_ratings]
    
    music_items = db.query(models.Music).filter(
        models.Music.user_id == user_id,
        models.Music.year.isnot(None)
    ).all()
    music_data = {}
    for m in music_items:
        if m.year:
            year_str = str(m.year)
            music_data[year_str] = music_data.get(year_str, 0) + 1
    
    all_years = sorted([int(year) for year in music_data.keys()]) if music_data else []
    
    decade_stats = {}
    for year in all_years:
        decade = (year // 10) * 10
        decade_key = f"{decade}s"
        if decade_key not in decade_stats:
            decade_stats[decade_key] = 0
        decade_stats[decade_key] += music_data.get(str(year), 0)
    
    if not music_ratings:
        avg_rating = 0
        distribution = {}
        highest_rated = []
        lowest_rated = []
    else:
        avg_rating = round(sum(music_ratings) / len(music_ratings), 1)
        distribution = {}
        for i in range(1, 11):
            count = sum(1 for rating in music_ratings if round(rating) == i)
            if count > 0:
                distribution[str(i)] = count
        
        highest_rating = max(music_ratings)
        lowest_rating = min(music_ratings)
        
        highest_music = db.query(models.Music).filter(
            models.Music.user_id == user_id
        ).filter(models.Music.rating == highest_rating).limit(5).all()
        highest_rated = [{"title": m.title, "type": "Music", "rating": m.rating} for m in highest_music]
        
        lowest_music = db.query(models.Music).filter(
            models.Music.user_id == user_id
        ).filter(models.Music.rating == lowest_rating).limit(5).all()
        lowest_rated = [{"title": m.title, "type": "Music", "rating": m.rating} for m in lowest_music]
    
    return {
        "watch_stats": {
            "total_items": total_music,
            "watched_items": listened_music,
            "unwatched_items": total_music - listened_music,
            "completion_percentage": round((listened_music / total_music * 100) if total_music > 0 else 0, 1)
        },
        "rating_stats": {
            "average_rating": avg_rating,
            "total_rated_items": len(music_ratings),
            "rating_distribution": distribution,
            "highest_rated": highest_rated[:5],
            "lowest_rated": lowest_rated[:5]
        },
        "year_stats": {
            "items_by_year": music_data,
            "all_years": all_years,
            "decade_stats": decade_stats,
            "oldest_year": min(all_years) if all_years else None,
            "newest_year": max(all_years) if all_years else None
        }
    }


def get_books_statistics(db: Session, user_id: int) -> dict:
    """Get book-specific statistics"""
    total_books = db.query(models.Book).filter(models.Book.user_id == user_id).count()
    read_books = db.query(models.Book).filter(models.Book.user_id == user_id).filter(models.Book.read == True).count()
    
    book_ratings = db.query(models.Book.rating).filter(
        models.Book.user_id == user_id
    ).filter(models.Book.rating.isnot(None)).all()
    book_ratings = [r[0] for r in book_ratings]
    
    book_items = db.query(models.Book).filter(
        models.Book.user_id == user_id,
        models.Book.year.isnot(None)
    ).all()
    book_data = {}
    for b in book_items:
        if b.year:
            year_str = str(b.year)
            book_data[year_str] = book_data.get(year_str, 0) + 1
    
    all_years = sorted([int(year) for year in book_data.keys()]) if book_data else []
    
    decade_stats = {}
    for year in all_years:
        decade = (year // 10) * 10
        decade_key = f"{decade}s"
        if decade_key not in decade_stats:
            decade_stats[decade_key] = 0
        decade_stats[decade_key] += book_data.get(str(year), 0)
    
    if not book_ratings:
        avg_rating = 0
        distribution = {}
        highest_rated = []
        lowest_rated = []
    else:
        avg_rating = round(sum(book_ratings) / len(book_ratings), 1)
        distribution = {}
        for i in range(1, 11):
            count = sum(1 for rating in book_ratings if round(rating) == i)
            if count > 0:
                distribution[str(i)] = count
        
        highest_rating = max(book_ratings)
        lowest_rating = min(book_ratings)
        
        highest_books = db.query(models.Book).filter(
            models.Book.user_id == user_id
        ).filter(models.Book.rating == highest_rating).limit(5).all()
        highest_rated = [{"title": b.title, "type": "Book", "rating": b.rating} for b in highest_books]
        
        lowest_books = db.query(models.Book).filter(
            models.Book.user_id == user_id
        ).filter(models.Book.rating == lowest_rating).limit(5).all()
        lowest_rated = [{"title": b.title, "type": "Book", "rating": b.rating} for b in lowest_books]
    
    return {
        "watch_stats": {
            "total_items": total_books,
            "watched_items": read_books,
            "unwatched_items": total_books - read_books,
            "completion_percentage": round((read_books / total_books * 100) if total_books > 0 else 0, 1)
        },
        "rating_stats": {
            "average_rating": avg_rating,
            "total_rated_items": len(book_ratings),
            "rating_distribution": distribution,
            "highest_rated": highest_rated[:5],
            "lowest_rated": lowest_rated[:5]
        },
        "year_stats": {
            "items_by_year": book_data,
            "all_years": all_years,
            "decade_stats": decade_stats,
            "oldest_year": min(all_years) if all_years else None,
            "newest_year": max(all_years) if all_years else None
        }
    }
