"""
Pytest configuration and fixtures for OmniTrackr tests.
"""
import os
os.environ["TESTING"] = "true"  # Disable rate limiting in tests

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import app
from app.dependencies import get_db
from app import models


# Use in-memory SQLite database for testing
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user_data():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "username": "testuser",
        "password": "testpassword123"
    }


@pytest.fixture
def authenticated_client(client, test_user_data, db_session):
    """Create a client with an authenticated and verified user."""
    # Register user
    response = client.post("/auth/register", json=test_user_data)
    assert response.status_code == 201
    user_id = response.json()["id"]
    
    # Get user and verify them (bypass email verification for tests)
    from app import crud
    user = crud.get_user_by_id(db_session, user_id)
    user.is_verified = True
    user.verification_token = None
    db_session.commit()
    
    # Login to get token
    login_response = client.post(
        "/auth/login",
        data={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        }
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    
    # Set authorization header for all requests
    client.headers = {"Authorization": f"Bearer {token}"}
    
    return client


@pytest.fixture
def test_movie_data():
    """Sample movie data for testing."""
    return {
        "title": "The Matrix",
        "director": "Wachowski Brothers",
        "year": 1999,
        "rating": 9,  # Integer rating (0-10)
        "watched": True,
        "review": "A classic sci-fi film"
    }


@pytest.fixture
def test_tv_show_data():
    """Sample TV show data for testing."""
    return {
        "title": "Breaking Bad",
        "year": 2008,
        "seasons": 5,
        "episodes": 62,
        "rating": 10,  # Integer rating (0-10)
        "watched": True,
        "review": "One of the best TV shows ever"
    }


@pytest.fixture
def test_anime_data():
    """Sample anime data for testing."""
    return {
        "title": "Attack on Titan",
        "year": 2013,
        "seasons": 4,
        "episodes": 75,
        "rating": 9.0,
        "watched": True,
        "review": "Amazing anime"
    }


@pytest.fixture
def test_video_game_data():
    """Sample video game data for testing."""
    from datetime import datetime
    return {
        "title": "The Legend of Zelda: Breath of the Wild",
        "release_date": datetime(2017, 3, 3).isoformat(),
        "genres": "Action, Adventure, RPG",
        "rating": 9.5,
        "played": True,
        "review": "An amazing open-world adventure",
        "cover_art_url": "https://example.com/zelda.jpg",
        "rawg_link": "https://rawg.io/games/the-legend-of-zelda-breath-of-the-wild"
    }


@pytest.fixture
def test_music_data():
    """Sample music data for testing."""
    return {
        "title": "Abbey Road",
        "artist": "The Beatles",
        "year": 1969,
        "genre": "Rock",
        "rating": 9.8,
        "listened": True,
        "review": "A masterpiece album"
    }


@pytest.fixture
def test_book_data():
    """Sample book data for testing."""
    return {
        "title": "1984",
        "author": "George Orwell",
        "year": 1949,
        "genre": "Dystopian Fiction",
        "rating": 9.5,
        "read": True,
        "review": "A classic dystopian novel"
    }
