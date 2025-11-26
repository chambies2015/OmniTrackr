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

