"""
Tests for CRUD operations.
"""
import pytest
from app import crud, models, schemas
from datetime import datetime


class TestUserCRUD:
    """Test user CRUD operations."""
    
    def test_create_user(self, db_session, test_user_data):
        """Test creating a user."""
        user_create = schemas.UserCreate(**test_user_data)
        hashed_password = "hashed_password_here"
        verification_token = "test_token"
        
        user = crud.create_user(db_session, user_create, hashed_password, verification_token)
        
        assert user is not None
        assert user.email == test_user_data["email"]
        assert user.username == test_user_data["username"]
        assert user.hashed_password == hashed_password
        assert user.is_verified is False
        assert user.verification_token == verification_token
    
    def test_get_user_by_email(self, db_session, test_user_data):
        """Test retrieving user by email."""
        user_create = schemas.UserCreate(**test_user_data)
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        found_user = crud.get_user_by_email(db_session, test_user_data["email"])
        
        assert found_user is not None
        assert found_user.email == test_user_data["email"]
    
    def test_get_user_by_username(self, db_session, test_user_data):
        """Test retrieving user by username."""
        user_create = schemas.UserCreate(**test_user_data)
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        found_user = crud.get_user_by_username(db_session, test_user_data["username"])
        
        assert found_user is not None
        assert found_user.username == test_user_data["username"]
    
    def test_get_user_by_id(self, db_session, test_user_data):
        """Test retrieving user by ID."""
        user_create = schemas.UserCreate(**test_user_data)
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        found_user = crud.get_user_by_id(db_session, user.id)
        
        assert found_user is not None
        assert found_user.id == user.id
    
    def test_update_user(self, db_session, test_user_data):
        """Test updating user information."""
        from app import auth
        user_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user = crud.create_user(db_session, user_create, hashed_password)
        
        # Update username
        user_update = schemas.UserUpdate(username="updateduser")
        updated_user = crud.update_user(db_session, user.id, user_update)
        
        assert updated_user is not None
        assert updated_user.username == "updateduser"
        assert updated_user.email == test_user_data["email"]
    
    def test_deactivate_user(self, db_session, test_user_data):
        """Test deactivating a user."""
        from app import auth
        user_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user = crud.create_user(db_session, user_create, hashed_password)
        
        assert user.is_active is True
        
        deactivated_user = crud.deactivate_user(db_session, user.id)
        
        assert deactivated_user is not None
        assert deactivated_user.is_active is False
        assert deactivated_user.deactivated_at is not None
    
    def test_reactivate_user(self, db_session, test_user_data):
        """Test reactivating a deactivated user."""
        from app import auth
        user_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user = crud.create_user(db_session, user_create, hashed_password)
        
        # Deactivate first
        crud.deactivate_user(db_session, user.id)
        db_session.refresh(user)
        
        # Reactivate
        reactivated_user = crud.reactivate_user(db_session, user.id)
        
        assert reactivated_user is not None
        assert reactivated_user.is_active is True
        assert reactivated_user.deactivated_at is None


class TestMovieCRUD:
    """Test movie CRUD operations."""
    
    def test_create_movie(self, db_session, authenticated_client, test_movie_data):
        """Test creating a movie."""
        # Get user from authenticated client
        user_response = authenticated_client.get("/auth/login")
        # Actually, we need the user_id - let's get it from the token
        # For now, create a user directly
        from app import crud, schemas
        user_create = schemas.UserCreate(
            email="movietest@example.com",
            username="movietest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        movie_create = schemas.MovieCreate(**test_movie_data)
        movie = crud.create_movie(db_session, user.id, movie_create)
        
        assert movie is not None
        assert movie.title == test_movie_data["title"]
        assert movie.director == test_movie_data["director"]
        assert movie.year == test_movie_data["year"]
        assert movie.rating == test_movie_data["rating"]
        assert movie.user_id == user.id
    
    def test_get_movies(self, db_session, test_movie_data):
        """Test retrieving movies for a user."""
        # Create user and movie
        user_create = schemas.UserCreate(
            email="movietest2@example.com",
            username="movietest2",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        movie_create = schemas.MovieCreate(**test_movie_data)
        crud.create_movie(db_session, user.id, movie_create)
        
        movies = crud.get_movies(db_session, user.id)
        
        assert len(movies) == 1
        assert movies[0].title == test_movie_data["title"]
    
    def test_get_movies_with_search(self, db_session, test_movie_data):
        """Test searching movies."""
        user_create = schemas.UserCreate(
            email="searchtest@example.com",
            username="searchtest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        movie_create = schemas.MovieCreate(**test_movie_data)
        crud.create_movie(db_session, user.id, movie_create)
        
        # Search by title
        movies = crud.get_movies(db_session, user.id, search="Matrix")
        assert len(movies) == 1
        
        # Search by director
        movies = crud.get_movies(db_session, user.id, search="Wachowski")
        assert len(movies) == 1
        
        # Search with no results
        movies = crud.get_movies(db_session, user.id, search="Nonexistent")
        assert len(movies) == 0
    
    def test_update_movie(self, db_session, test_movie_data):
        """Test updating a movie."""
        user_create = schemas.UserCreate(
            email="updatetest@example.com",
            username="updatetest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        movie_create = schemas.MovieCreate(**test_movie_data)
        movie = crud.create_movie(db_session, user.id, movie_create)
        
        # Update movie
        movie_update = schemas.MovieUpdate(rating=10, watched=False)  # Integer rating
        updated_movie = crud.update_movie(db_session, user.id, movie.id, movie_update)
        
        assert updated_movie.rating == 10.0
        assert updated_movie.watched is False
        assert updated_movie.title == test_movie_data["title"]  # Unchanged
    
    def test_create_movie_with_decimal_rating(self, db_session):
        """Test creating a movie with decimal rating."""
        user_create = schemas.UserCreate(
            email="decimaltest@example.com",
            username="decimaltest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        movie_data = {
            "title": "Test Movie",
            "director": "Test Director",
            "year": 2020,
            "rating": 8.5  # Decimal rating
        }
        movie_create = schemas.MovieCreate(**movie_data)
        movie = crud.create_movie(db_session, user.id, movie_create)
        
        assert movie.rating == 8.5
        assert isinstance(movie.rating, float)
    
    def test_update_movie_with_decimal_rating(self, db_session, test_movie_data):
        """Test updating a movie with decimal rating."""
        user_create = schemas.UserCreate(
            email="decimalupdatetest@example.com",
            username="decimalupdatetest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        movie_create = schemas.MovieCreate(**test_movie_data)
        movie = crud.create_movie(db_session, user.id, movie_create)
        
        # Update with decimal rating
        movie_update = schemas.MovieUpdate(rating=7.4)
        updated_movie = crud.update_movie(db_session, user.id, movie.id, movie_update)
        
        assert updated_movie.rating == 7.4
        assert isinstance(updated_movie.rating, float)
    
    def test_rating_rounding(self, db_session):
        """Test that ratings are rounded to one decimal place."""
        user_create = schemas.UserCreate(
            email="roundtest@example.com",
            username="roundtest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        # Test with rating that needs rounding
        movie_data = {
            "title": "Test Movie",
            "director": "Test Director",
            "year": 2020,
            "rating": 8.456  # Should round to 8.5
        }
        movie_create = schemas.MovieCreate(**movie_data)
        movie = crud.create_movie(db_session, user.id, movie_create)
        
        assert movie.rating == 8.5
    
    def test_delete_movie(self, db_session, test_movie_data):
        """Test deleting a movie."""
        user_create = schemas.UserCreate(
            email="deletetest@example.com",
            username="deletetest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        movie_create = schemas.MovieCreate(**test_movie_data)
        movie = crud.create_movie(db_session, user.id, movie_create)
        
        deleted_movie = crud.delete_movie(db_session, user.id, movie.id)
        
        assert deleted_movie is not None
        assert deleted_movie.id == movie.id
        
        # Verify it's deleted
        found_movie = crud.get_movie_by_id(db_session, user.id, movie.id)
        assert found_movie is None


class TestTVShowCRUD:
    """Test TV show CRUD operations."""
    
    def test_create_tv_show(self, db_session, test_tv_show_data):
        """Test creating a TV show."""
        user_create = schemas.UserCreate(
            email="tvtest@example.com",
            username="tvtest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        tv_show_create = schemas.TVShowCreate(**test_tv_show_data)
        tv_show = crud.create_tv_show(db_session, user.id, tv_show_create)
        
        assert tv_show is not None
        assert tv_show.title == test_tv_show_data["title"]
        assert tv_show.year == test_tv_show_data["year"]
        assert tv_show.seasons == test_tv_show_data["seasons"]
        assert tv_show.user_id == user.id
    
    def test_get_tv_shows(self, db_session, test_tv_show_data):
        """Test retrieving TV shows for a user."""
        user_create = schemas.UserCreate(
            email="tvtest2@example.com",
            username="tvtest2",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        tv_show_create = schemas.TVShowCreate(**test_tv_show_data)
        crud.create_tv_show(db_session, user.id, tv_show_create)
        
        tv_shows = crud.get_tv_shows(db_session, user.id)
        
        assert len(tv_shows) == 1
        assert tv_shows[0].title == test_tv_show_data["title"]
    
    def test_update_tv_show(self, db_session, test_tv_show_data):
        """Test updating a TV show."""
        user_create = schemas.UserCreate(
            email="tvupdatetest@example.com",
            username="tvupdatetest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        tv_show_create = schemas.TVShowCreate(**test_tv_show_data)
        tv_show = crud.create_tv_show(db_session, user.id, tv_show_create)
        
        # Update TV show
        tv_show_update = schemas.TVShowUpdate(rating=10, seasons=6)  # Integer rating
        updated_tv_show = crud.update_tv_show(db_session, user.id, tv_show.id, tv_show_update)
        
        assert updated_tv_show.rating == 10.0
        assert updated_tv_show.seasons == 6
        assert updated_tv_show.title == test_tv_show_data["title"]  # Unchanged
    
    def test_create_tv_show_with_decimal_rating(self, db_session):
        """Test creating a TV show with decimal rating."""
        user_create = schemas.UserCreate(
            email="tvdecimaltest@example.com",
            username="tvdecimaltest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        tv_show_data = {
            "title": "Test TV Show",
            "year": 2020,
            "rating": 9.2  # Decimal rating
        }
        tv_show_create = schemas.TVShowCreate(**tv_show_data)
        tv_show = crud.create_tv_show(db_session, user.id, tv_show_create)
        
        assert tv_show.rating == 9.2
        assert isinstance(tv_show.rating, float)
    
    def test_update_tv_show_with_decimal_rating(self, db_session, test_tv_show_data):
        """Test updating a TV show with decimal rating."""
        user_create = schemas.UserCreate(
            email="tvdecimalupdatetest@example.com",
            username="tvdecimalupdatetest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        tv_show_create = schemas.TVShowCreate(**test_tv_show_data)
        tv_show = crud.create_tv_show(db_session, user.id, tv_show_create)
        
        # Update with decimal rating
        tv_show_update = schemas.TVShowUpdate(rating=6.7)
        updated_tv_show = crud.update_tv_show(db_session, user.id, tv_show.id, tv_show_update)
        
        assert updated_tv_show.rating == 6.7
        assert isinstance(updated_tv_show.rating, float)
    
    def test_delete_tv_show(self, db_session, test_tv_show_data):
        """Test deleting a TV show."""
        user_create = schemas.UserCreate(
            email="tvdeletetest@example.com",
            username="tvdeletetest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        tv_show_create = schemas.TVShowCreate(**test_tv_show_data)
        tv_show = crud.create_tv_show(db_session, user.id, tv_show_create)
        
        deleted_tv_show = crud.delete_tv_show(db_session, user.id, tv_show.id)
        
        assert deleted_tv_show is not None
        assert deleted_tv_show.id == tv_show.id
        
        # Verify it's deleted
        found_tv_show = crud.get_tv_show_by_id(db_session, user.id, tv_show.id)
        assert found_tv_show is None


class TestAnimeCRUD:
    """Test anime CRUD operations."""
    
    def test_create_anime(self, db_session, test_anime_data):
        """Test creating an anime."""
        user_create = schemas.UserCreate(
            email="animetest@example.com",
            username="animetest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        anime_create = schemas.AnimeCreate(**test_anime_data)
        anime = crud.create_anime(db_session, user.id, anime_create)
        
        assert anime is not None
        assert anime.title == test_anime_data["title"]
        assert anime.year == test_anime_data["year"]
        assert anime.seasons == test_anime_data["seasons"]
        assert anime.user_id == user.id
    
    def test_get_anime(self, db_session, test_anime_data):
        """Test retrieving anime for a user."""
        user_create = schemas.UserCreate(
            email="animetest2@example.com",
            username="animetest2",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        anime_create = schemas.AnimeCreate(**test_anime_data)
        crud.create_anime(db_session, user.id, anime_create)
        
        anime = crud.get_anime(db_session, user.id)
        
        assert len(anime) == 1
        assert anime[0].title == test_anime_data["title"]
    
    def test_update_anime(self, db_session, test_anime_data):
        """Test updating an anime."""
        user_create = schemas.UserCreate(
            email="animeupdatetest@example.com",
            username="animeupdatetest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        anime_create = schemas.AnimeCreate(**test_anime_data)
        anime = crud.create_anime(db_session, user.id, anime_create)
        
        # Update the anime
        anime_update = schemas.AnimeUpdate(rating=10, seasons=6)  # Integer rating
        updated_anime = crud.update_anime(db_session, user.id, anime.id, anime_update)
        
        assert updated_anime.rating == 10.0
        assert updated_anime.seasons == 6
    
    def test_create_anime_with_decimal_rating(self, db_session):
        """Test creating an anime with decimal rating."""
        user_create = schemas.UserCreate(
            email="animedecimaltest@example.com",
            username="animedecimaltest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        anime_data = {
            "title": "Test Anime",
            "year": 2020,
            "rating": 8.7  # Decimal rating
        }
        anime_create = schemas.AnimeCreate(**anime_data)
        anime = crud.create_anime(db_session, user.id, anime_create)
        
        assert anime.rating == 8.7
        assert isinstance(anime.rating, float)
    
    def test_update_anime_with_decimal_rating(self, db_session, test_anime_data):
        """Test updating an anime with decimal rating."""
        user_create = schemas.UserCreate(
            email="animedecimalupdatetest@example.com",
            username="animedecimalupdatetest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        anime_create = schemas.AnimeCreate(**test_anime_data)
        anime = crud.create_anime(db_session, user.id, anime_create)
        
        # Update with decimal rating
        anime_update = schemas.AnimeUpdate(rating=7.3)
        updated_anime = crud.update_anime(db_session, user.id, anime.id, anime_update)
        
        assert updated_anime.rating == 7.3
        assert isinstance(updated_anime.rating, float)
    
    def test_delete_anime(self, db_session, test_anime_data):
        """Test deleting an anime."""
        user_create = schemas.UserCreate(
            email="animedeletetest@example.com",
            username="animedeletetest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        anime_create = schemas.AnimeCreate(**test_anime_data)
        anime = crud.create_anime(db_session, user.id, anime_create)
        
        deleted_anime = crud.delete_anime(db_session, user.id, anime.id)
        
        assert deleted_anime is not None
        assert deleted_anime.id == anime.id
        
        # Verify it's deleted
        found_anime = crud.get_anime_by_id(db_session, user.id, anime.id)
        assert found_anime is None
    
    def test_get_anime_by_id(self, db_session, test_anime_data):
        """Test retrieving a specific anime by ID."""
        user_create = schemas.UserCreate(
            email="animegetbyidtest@example.com",
            username="animegetbyidtest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        anime_create = schemas.AnimeCreate(**test_anime_data)
        anime = crud.create_anime(db_session, user.id, anime_create)
        
        found_anime = crud.get_anime_by_id(db_session, user.id, anime.id)
        
        assert found_anime is not None
        assert found_anime.id == anime.id
        assert found_anime.title == test_anime_data["title"]
    
    def test_anime_search(self, db_session, test_anime_data):
        """Test searching anime."""
        user_create = schemas.UserCreate(
            email="animesearchtest@example.com",
            username="animesearchtest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        anime_create = schemas.AnimeCreate(**test_anime_data)
        crud.create_anime(db_session, user.id, anime_create)
        
        # Search by title
        anime = crud.get_anime(db_session, user.id, search="Attack")
        
        assert len(anime) == 1
        assert "Attack" in anime[0].title
    
    def test_anime_sorting(self, db_session, test_anime_data):
        """Test sorting anime."""
        user_create = schemas.UserCreate(
            email="animesorttest@example.com",
            username="animesorttest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        # Create multiple anime with different ratings
        anime1_data = test_anime_data.copy()
        anime1_data["title"] = "Anime A"
        anime1_data["rating"] = 5
        anime1 = crud.create_anime(db_session, user.id, schemas.AnimeCreate(**anime1_data))
        
        anime2_data = test_anime_data.copy()
        anime2_data["title"] = "Anime B"
        anime2_data["rating"] = 9
        anime2 = crud.create_anime(db_session, user.id, schemas.AnimeCreate(**anime2_data))
        
        # Sort by rating descending
        anime = crud.get_anime(db_session, user.id, sort_by="rating", order="desc")
        
        assert len(anime) >= 2
        assert anime[0].rating >= anime[1].rating


class TestVideoGameCRUD:
    """Test video game CRUD operations."""
    
    def test_create_video_game(self, db_session, test_video_game_data):
        """Test creating a video game."""
        from datetime import datetime
        user_create = schemas.UserCreate(
            email="vgtest@example.com",
            username="vgtest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        # Parse release_date string to datetime
        game_data = test_video_game_data.copy()
        if isinstance(game_data["release_date"], str):
            game_data["release_date"] = datetime.fromisoformat(game_data["release_date"])
        
        video_game_create = schemas.VideoGameCreate(**game_data)
        video_game = crud.create_video_game(db_session, user.id, video_game_create)
        
        assert video_game is not None
        assert video_game.title == test_video_game_data["title"]
        assert video_game.genres == test_video_game_data["genres"]
        assert video_game.rating == test_video_game_data["rating"]
        assert video_game.played == test_video_game_data["played"]
        assert video_game.user_id == user.id
    
    def test_get_video_games(self, db_session, test_video_game_data):
        """Test retrieving video games for a user."""
        from datetime import datetime
        user_create = schemas.UserCreate(
            email="vgtest2@example.com",
            username="vgtest2",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        # Parse release_date string to datetime
        game_data = test_video_game_data.copy()
        if isinstance(game_data["release_date"], str):
            game_data["release_date"] = datetime.fromisoformat(game_data["release_date"])
        
        video_game_create = schemas.VideoGameCreate(**game_data)
        crud.create_video_game(db_session, user.id, video_game_create)
        
        video_games = crud.get_video_games(db_session, user.id)
        
        assert len(video_games) == 1
        assert video_games[0].title == test_video_game_data["title"]
    
    def test_update_video_game(self, db_session, test_video_game_data):
        """Test updating a video game."""
        from datetime import datetime
        user_create = schemas.UserCreate(
            email="vgupdatetest@example.com",
            username="vgupdatetest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        # Parse release_date string to datetime
        game_data = test_video_game_data.copy()
        if isinstance(game_data["release_date"], str):
            game_data["release_date"] = datetime.fromisoformat(game_data["release_date"])
        
        video_game_create = schemas.VideoGameCreate(**game_data)
        video_game = crud.create_video_game(db_session, user.id, video_game_create)
        
        # Update video game
        video_game_update = schemas.VideoGameUpdate(rating=10.0, played=False)
        updated_video_game = crud.update_video_game(db_session, user.id, video_game.id, video_game_update)
        
        assert updated_video_game.rating == 10.0
        assert updated_video_game.played is False
        assert updated_video_game.title == test_video_game_data["title"]  # Unchanged
    
    def test_create_video_game_with_decimal_rating(self, db_session):
        """Test creating a video game with decimal rating."""
        from datetime import datetime
        user_create = schemas.UserCreate(
            email="vgdecimaltest@example.com",
            username="vgdecimaltest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        video_game_data = {
            "title": "Test Game",
            "release_date": datetime(2020, 1, 1),
            "rating": 8.7  # Decimal rating
        }
        video_game_create = schemas.VideoGameCreate(**video_game_data)
        video_game = crud.create_video_game(db_session, user.id, video_game_create)
        
        assert video_game.rating == 8.7
        assert isinstance(video_game.rating, float)
    
    def test_update_video_game_with_decimal_rating(self, db_session, test_video_game_data):
        """Test updating a video game with decimal rating."""
        from datetime import datetime
        user_create = schemas.UserCreate(
            email="vgdecimalupdatetest@example.com",
            username="vgdecimalupdatetest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        # Parse release_date string to datetime
        game_data = test_video_game_data.copy()
        if isinstance(game_data["release_date"], str):
            game_data["release_date"] = datetime.fromisoformat(game_data["release_date"])
        
        video_game_create = schemas.VideoGameCreate(**game_data)
        video_game = crud.create_video_game(db_session, user.id, video_game_create)
        
        # Update with decimal rating
        video_game_update = schemas.VideoGameUpdate(rating=7.3)
        updated_video_game = crud.update_video_game(db_session, user.id, video_game.id, video_game_update)
        
        assert updated_video_game.rating == 7.3
        assert isinstance(updated_video_game.rating, float)
    
    def test_rating_rounding(self, db_session):
        """Test that ratings are rounded to one decimal place."""
        from datetime import datetime
        user_create = schemas.UserCreate(
            email="vgroundtest@example.com",
            username="vgroundtest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        # Test with rating that needs rounding
        video_game_data = {
            "title": "Test Game",
            "release_date": datetime(2020, 1, 1),
            "rating": 8.456  # Should round to 8.5
        }
        video_game_create = schemas.VideoGameCreate(**video_game_data)
        video_game = crud.create_video_game(db_session, user.id, video_game_create)
        
        assert video_game.rating == 8.5
    
    def test_delete_video_game(self, db_session, test_video_game_data):
        """Test deleting a video game."""
        from datetime import datetime
        user_create = schemas.UserCreate(
            email="vgdeletetest@example.com",
            username="vgdeletetest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        # Parse release_date string to datetime
        game_data = test_video_game_data.copy()
        if isinstance(game_data["release_date"], str):
            game_data["release_date"] = datetime.fromisoformat(game_data["release_date"])
        
        video_game_create = schemas.VideoGameCreate(**game_data)
        video_game = crud.create_video_game(db_session, user.id, video_game_create)
        
        deleted_video_game = crud.delete_video_game(db_session, user.id, video_game.id)
        
        assert deleted_video_game is not None
        assert deleted_video_game.id == video_game.id
        
        # Verify it's deleted
        found_video_game = crud.get_video_game_by_id(db_session, user.id, video_game.id)
        assert found_video_game is None
    
    def test_get_video_game_by_id(self, db_session, test_video_game_data):
        """Test retrieving a specific video game by ID."""
        from datetime import datetime
        user_create = schemas.UserCreate(
            email="vggetbyidtest@example.com",
            username="vggetbyidtest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        # Parse release_date string to datetime
        game_data = test_video_game_data.copy()
        if isinstance(game_data["release_date"], str):
            game_data["release_date"] = datetime.fromisoformat(game_data["release_date"])
        
        video_game_create = schemas.VideoGameCreate(**game_data)
        video_game = crud.create_video_game(db_session, user.id, video_game_create)
        
        found_video_game = crud.get_video_game_by_id(db_session, user.id, video_game.id)
        
        assert found_video_game is not None
        assert found_video_game.id == video_game.id
        assert found_video_game.title == test_video_game_data["title"]
    
    def test_video_game_search(self, db_session, test_video_game_data):
        """Test searching video games."""
        from datetime import datetime
        user_create = schemas.UserCreate(
            email="vgsearchtest@example.com",
            username="vgsearchtest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        # Parse release_date string to datetime
        game_data = test_video_game_data.copy()
        if isinstance(game_data["release_date"], str):
            game_data["release_date"] = datetime.fromisoformat(game_data["release_date"])
        
        video_game_create = schemas.VideoGameCreate(**game_data)
        crud.create_video_game(db_session, user.id, video_game_create)
        
        # Search by title
        video_games = crud.get_video_games(db_session, user.id, search="Zelda")
        
        assert len(video_games) == 1
        assert "Zelda" in video_games[0].title
        
        # Search by genre
        video_games = crud.get_video_games(db_session, user.id, search="Action")
        
        assert len(video_games) == 1
        assert "Action" in video_games[0].genres
    
    def test_video_game_sorting(self, db_session, test_video_game_data):
        """Test sorting video games."""
        from datetime import datetime
        user_create = schemas.UserCreate(
            email="vgsorttest@example.com",
            username="vgsorttest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        # Create multiple video games with different ratings
        game1_data = test_video_game_data.copy()
        game1_data["title"] = "Game A"
        if isinstance(game1_data["release_date"], str):
            game1_data["release_date"] = datetime.fromisoformat(game1_data["release_date"])
        game1_data["rating"] = 5.0
        game1 = crud.create_video_game(db_session, user.id, schemas.VideoGameCreate(**game1_data))
        
        game2_data = test_video_game_data.copy()
        game2_data["title"] = "Game B"
        if isinstance(game2_data["release_date"], str):
            game2_data["release_date"] = datetime.fromisoformat(game2_data["release_date"])
        game2_data["rating"] = 9.0
        game2 = crud.create_video_game(db_session, user.id, schemas.VideoGameCreate(**game2_data))
        
        # Sort by rating descending
        video_games = crud.get_video_games(db_session, user.id, sort_by="rating", order="desc")
        
        assert len(video_games) >= 2
        assert video_games[0].rating >= video_games[1].rating
        
        # Sort by release_date ascending
        video_games = crud.get_video_games(db_session, user.id, sort_by="release_date", order="asc")
        
        assert len(video_games) >= 2


class TestMusicCRUD:
    """Test music CRUD operations."""
    
    def test_create_music(self, db_session, test_music_data):
        """Test creating music."""
        user_create = schemas.UserCreate(
            email="musictest@example.com",
            username="musictest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        music_create = schemas.MusicCreate(**test_music_data)
        music = crud.create_music(db_session, user.id, music_create)
        
        assert music is not None
        assert music.title == test_music_data["title"]
        assert music.artist == test_music_data["artist"]
        assert music.year == test_music_data["year"]
        assert music.user_id == user.id
    
    def test_get_music(self, db_session, test_music_data):
        """Test retrieving music."""
        user_create = schemas.UserCreate(
            email="musicget@example.com",
            username="musicget",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        music_create = schemas.MusicCreate(**test_music_data)
        crud.create_music(db_session, user.id, music_create)
        
        music_list = crud.get_music(db_session, user.id)
        
        assert len(music_list) >= 1
        assert any(m.title == test_music_data["title"] for m in music_list)
    
    def test_get_music_with_search(self, db_session, test_music_data):
        """Test searching music."""
        user_create = schemas.UserCreate(
            email="musicsearch@example.com",
            username="musicsearch",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        music_create = schemas.MusicCreate(**test_music_data)
        crud.create_music(db_session, user.id, music_create)
        
        music_list = crud.get_music(db_session, user.id, search="Beatles")
        
        assert len(music_list) >= 1
        assert any("Beatles" in m.artist for m in music_list)
    
    def test_update_music(self, db_session, test_music_data):
        """Test updating music."""
        user_create = schemas.UserCreate(
            email="musicupdate@example.com",
            username="musicupdate",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        music_create = schemas.MusicCreate(**test_music_data)
        music = crud.create_music(db_session, user.id, music_create)
        
        update_data = schemas.MusicUpdate(rating=10.0, listened=False)
        updated_music = crud.update_music(db_session, user.id, music.id, update_data)
        
        assert updated_music is not None
        assert updated_music.rating == 10.0
        assert updated_music.listened is False
    
    def test_create_music_with_decimal_rating(self, db_session):
        """Test creating music with decimal rating."""
        user_create = schemas.UserCreate(
            email="musicdecimal@example.com",
            username="musicdecimal",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        music_data = {
            "title": "Test Album",
            "artist": "Test Artist",
            "year": 2020,
            "rating": 8.7
        }
        music_create = schemas.MusicCreate(**music_data)
        music = crud.create_music(db_session, user.id, music_create)
        
        assert music.rating == 8.7
        assert isinstance(music.rating, (int, float))
    
    def test_update_music_with_decimal_rating(self, db_session, test_music_data):
        """Test updating music with decimal rating."""
        user_create = schemas.UserCreate(
            email="musicupdecimal@example.com",
            username="musicupdecimal",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        music_create = schemas.MusicCreate(**test_music_data)
        music = crud.create_music(db_session, user.id, music_create)
        
        update_data = schemas.MusicUpdate(rating=7.3)
        updated_music = crud.update_music(db_session, user.id, music.id, update_data)
        
        assert updated_music.rating == 7.3
    
    def test_delete_music(self, db_session, test_music_data):
        """Test deleting music."""
        user_create = schemas.UserCreate(
            email="musicdelete@example.com",
            username="musicdelete",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        music_create = schemas.MusicCreate(**test_music_data)
        music = crud.create_music(db_session, user.id, music_create)
        music_id = music.id
        
        deleted_music = crud.delete_music(db_session, user.id, music_id)
        
        assert deleted_music is not None
        assert deleted_music.id == music_id
        
        retrieved_music = crud.get_music_by_id(db_session, user.id, music_id)
        assert retrieved_music is None
    
    def test_get_music_by_id(self, db_session, test_music_data):
        """Test retrieving music by ID."""
        user_create = schemas.UserCreate(
            email="musicbyid@example.com",
            username="musicbyid",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        music_create = schemas.MusicCreate(**test_music_data)
        music = crud.create_music(db_session, user.id, music_create)
        
        retrieved_music = crud.get_music_by_id(db_session, user.id, music.id)
        
        assert retrieved_music is not None
        assert retrieved_music.id == music.id
        assert retrieved_music.title == test_music_data["title"]
    
    def test_music_search(self, db_session, test_music_data):
        """Test searching music by title, artist, or genre."""
        user_create = schemas.UserCreate(
            email="musicsearch2@example.com",
            username="musicsearch2",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        music_create = schemas.MusicCreate(**test_music_data)
        crud.create_music(db_session, user.id, music_create)
        
        music_list = crud.get_music(db_session, user.id, search="Abbey")
        assert len(music_list) >= 1
        
        music_list = crud.get_music(db_session, user.id, search="Beatles")
        assert len(music_list) >= 1
        
        music_list = crud.get_music(db_session, user.id, search="Rock")
        assert len(music_list) >= 1
    
    def test_music_sorting(self, db_session, test_music_data):
        """Test sorting music."""
        user_create = schemas.UserCreate(
            email="musicsort@example.com",
            username="musicsort",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        music1_data = test_music_data.copy()
        music1_data["title"] = "Album A"
        music1_data["rating"] = 5.0
        music1 = crud.create_music(db_session, user.id, schemas.MusicCreate(**music1_data))
        
        music2_data = test_music_data.copy()
        music2_data["title"] = "Album B"
        music2_data["rating"] = 9.0
        music2 = crud.create_music(db_session, user.id, schemas.MusicCreate(**music2_data))
        
        music_list = crud.get_music(db_session, user.id, sort_by="rating", order="desc")
        
        assert len(music_list) >= 2
        assert music_list[0].rating >= music_list[1].rating


class TestBookCRUD:
    """Test book CRUD operations."""
    
    def test_create_book(self, db_session, test_book_data):
        """Test creating a book."""
        user_create = schemas.UserCreate(
            email="booktest@example.com",
            username="booktest",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        book_create = schemas.BookCreate(**test_book_data)
        book = crud.create_book(db_session, user.id, book_create)
        
        assert book is not None
        assert book.title == test_book_data["title"]
        assert book.author == test_book_data["author"]
        assert book.year == test_book_data["year"]
        assert book.user_id == user.id
    
    def test_get_books(self, db_session, test_book_data):
        """Test retrieving books."""
        user_create = schemas.UserCreate(
            email="bookget@example.com",
            username="bookget",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        book_create = schemas.BookCreate(**test_book_data)
        crud.create_book(db_session, user.id, book_create)
        
        books_list = crud.get_books(db_session, user.id)
        
        assert len(books_list) >= 1
        assert any(b.title == test_book_data["title"] for b in books_list)
    
    def test_get_books_with_search(self, db_session, test_book_data):
        """Test searching books."""
        user_create = schemas.UserCreate(
            email="booksearch@example.com",
            username="booksearch",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        book_create = schemas.BookCreate(**test_book_data)
        crud.create_book(db_session, user.id, book_create)
        
        books_list = crud.get_books(db_session, user.id, search="Orwell")
        
        assert len(books_list) >= 1
        assert any("Orwell" in b.author for b in books_list)
    
    def test_update_book(self, db_session, test_book_data):
        """Test updating a book."""
        user_create = schemas.UserCreate(
            email="bookupdate@example.com",
            username="bookupdate",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        book_create = schemas.BookCreate(**test_book_data)
        book = crud.create_book(db_session, user.id, book_create)
        
        update_data = schemas.BookUpdate(rating=10.0, read=False)
        updated_book = crud.update_book(db_session, user.id, book.id, update_data)
        
        assert updated_book is not None
        assert updated_book.rating == 10.0
        assert updated_book.read is False
    
    def test_create_book_with_decimal_rating(self, db_session):
        """Test creating a book with decimal rating."""
        user_create = schemas.UserCreate(
            email="bookdecimal@example.com",
            username="bookdecimal",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        book_data = {
            "title": "Test Book",
            "author": "Test Author",
            "year": 2020,
            "rating": 8.7
        }
        book_create = schemas.BookCreate(**book_data)
        book = crud.create_book(db_session, user.id, book_create)
        
        assert book.rating == 8.7
        assert isinstance(book.rating, (int, float))
    
    def test_update_book_with_decimal_rating(self, db_session, test_book_data):
        """Test updating a book with decimal rating."""
        user_create = schemas.UserCreate(
            email="bookupdecimal@example.com",
            username="bookupdecimal",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        book_create = schemas.BookCreate(**test_book_data)
        book = crud.create_book(db_session, user.id, book_create)
        
        update_data = schemas.BookUpdate(rating=7.3)
        updated_book = crud.update_book(db_session, user.id, book.id, update_data)
        
        assert updated_book.rating == 7.3
    
    def test_delete_book(self, db_session, test_book_data):
        """Test deleting a book."""
        user_create = schemas.UserCreate(
            email="bookdelete@example.com",
            username="bookdelete",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        book_create = schemas.BookCreate(**test_book_data)
        book = crud.create_book(db_session, user.id, book_create)
        book_id = book.id
        
        deleted_book = crud.delete_book(db_session, user.id, book_id)
        
        assert deleted_book is not None
        assert deleted_book.id == book_id
        
        retrieved_book = crud.get_book_by_id(db_session, user.id, book_id)
        assert retrieved_book is None
    
    def test_get_book_by_id(self, db_session, test_book_data):
        """Test retrieving a book by ID."""
        user_create = schemas.UserCreate(
            email="bookbyid@example.com",
            username="bookbyid",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        book_create = schemas.BookCreate(**test_book_data)
        book = crud.create_book(db_session, user.id, book_create)
        
        retrieved_book = crud.get_book_by_id(db_session, user.id, book.id)
        
        assert retrieved_book is not None
        assert retrieved_book.id == book.id
        assert retrieved_book.title == test_book_data["title"]
    
    def test_book_search(self, db_session, test_book_data):
        """Test searching books by title, author, or genre."""
        user_create = schemas.UserCreate(
            email="booksearch2@example.com",
            username="booksearch2",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        book_create = schemas.BookCreate(**test_book_data)
        crud.create_book(db_session, user.id, book_create)
        
        books_list = crud.get_books(db_session, user.id, search="1984")
        assert len(books_list) >= 1
        
        books_list = crud.get_books(db_session, user.id, search="Orwell")
        assert len(books_list) >= 1
        
        books_list = crud.get_books(db_session, user.id, search="Fiction")
        assert len(books_list) >= 1
    
    def test_book_sorting(self, db_session, test_book_data):
        """Test sorting books."""
        user_create = schemas.UserCreate(
            email="booksort@example.com",
            username="booksort",
            password="password123"
        )
        user = crud.create_user(db_session, user_create, "hashed", "token")
        
        book1_data = test_book_data.copy()
        book1_data["title"] = "Book A"
        book1_data["rating"] = 5.0
        book1 = crud.create_book(db_session, user.id, schemas.BookCreate(**book1_data))
        
        book2_data = test_book_data.copy()
        book2_data["title"] = "Book B"
        book2_data["rating"] = 9.0
        book2 = crud.create_book(db_session, user.id, schemas.BookCreate(**book2_data))
        
        books_list = crud.get_books(db_session, user.id, sort_by="rating", order="desc")
        
        assert len(books_list) >= 2
        assert books_list[0].rating >= books_list[1].rating
