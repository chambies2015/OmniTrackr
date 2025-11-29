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
from app.main import app, get_db
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

