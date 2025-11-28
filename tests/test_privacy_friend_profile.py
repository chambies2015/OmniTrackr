"""
Tests for privacy settings and friend profile features.
"""
import pytest
from app import crud, schemas, auth, models


class TestPrivacySettingsCRUD:
    """Test privacy settings CRUD operations."""
    
    def test_get_privacy_settings_default(self, db_session, test_user_data):
        """Test getting default privacy settings (all False)."""
        # Create user
        user_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user = crud.create_user(db_session, user_create, hashed_password)
        
        # Get privacy settings
        privacy = crud.get_privacy_settings(db_session, user.id)
        
        assert privacy is not None
        assert privacy.movies_private is False
        assert privacy.tv_shows_private is False
        assert privacy.statistics_private is False
    
    def test_update_privacy_settings_movies(self, db_session, test_user_data):
        """Test updating movies privacy setting."""
        # Create user
        user_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user = crud.create_user(db_session, user_create, hashed_password)
        
        # Update movies privacy
        privacy_update = schemas.PrivacySettingsUpdate(movies_private=True)
        updated_user = crud.update_privacy_settings(db_session, user.id, privacy_update)
        
        assert updated_user is not None
        assert updated_user.movies_private is True
        assert updated_user.tv_shows_private is False
        assert updated_user.statistics_private is False
    
    def test_update_privacy_settings_all(self, db_session, test_user_data):
        """Test updating all privacy settings."""
        # Create user
        user_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user = crud.create_user(db_session, user_create, hashed_password)
        
        # Update all privacy settings
        privacy_update = schemas.PrivacySettingsUpdate(
            movies_private=True,
            tv_shows_private=True,
            statistics_private=True
        )
        updated_user = crud.update_privacy_settings(db_session, user.id, privacy_update)
        
        assert updated_user is not None
        assert updated_user.movies_private is True
        assert updated_user.tv_shows_private is True
        assert updated_user.statistics_private is True
    
    def test_update_privacy_settings_partial(self, db_session, test_user_data):
        """Test updating only some privacy settings."""
        # Create user
        user_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user = crud.create_user(db_session, user_create, hashed_password)
        
        # Update only movies privacy
        privacy_update = schemas.PrivacySettingsUpdate(movies_private=True)
        crud.update_privacy_settings(db_session, user.id, privacy_update)
        
        # Update only TV shows privacy
        privacy_update2 = schemas.PrivacySettingsUpdate(tv_shows_private=True)
        updated_user = crud.update_privacy_settings(db_session, user.id, privacy_update2)
        
        assert updated_user.movies_private is True  # Should remain True
        assert updated_user.tv_shows_private is True  # Should be True
        assert updated_user.statistics_private is False  # Should remain False
    
    def test_get_privacy_settings_nonexistent_user(self, db_session):
        """Test getting privacy settings for non-existent user."""
        privacy = crud.get_privacy_settings(db_session, 99999)
        
        assert privacy is None
    
    def test_update_privacy_settings_nonexistent_user(self, db_session):
        """Test updating privacy settings for non-existent user."""
        privacy_update = schemas.PrivacySettingsUpdate(movies_private=True)
        result = crud.update_privacy_settings(db_session, 99999, privacy_update)
        
        assert result is None


class TestPrivacySettingsEndpoints:
    """Test privacy settings API endpoints."""
    
    def test_get_privacy_settings_success(self, authenticated_client):
        """Test getting privacy settings."""
        response = authenticated_client.get("/account/privacy")
        
        assert response.status_code == 200
        data = response.json()
        assert "movies_private" in data
        assert "tv_shows_private" in data
        assert "statistics_private" in data
        assert data["movies_private"] is False
        assert data["tv_shows_private"] is False
        assert data["statistics_private"] is False
    
    def test_get_privacy_settings_unauthenticated(self, client):
        """Test getting privacy settings without authentication."""
        response = client.get("/account/privacy")
        
        assert response.status_code == 401
    
    def test_update_privacy_settings_success(self, authenticated_client):
        """Test updating privacy settings."""
        response = authenticated_client.put(
            "/account/privacy",
            json={
                "movies_private": True,
                "tv_shows_private": False,
                "statistics_private": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["movies_private"] is True
        assert data["tv_shows_private"] is False
        assert data["statistics_private"] is True
    
    def test_update_privacy_settings_partial(self, authenticated_client):
        """Test updating only some privacy settings."""
        # First, set all to True
        authenticated_client.put(
            "/account/privacy",
            json={
                "movies_private": True,
                "tv_shows_private": True,
                "statistics_private": True
            }
        )
        
        # Then update only movies to False
        response = authenticated_client.put(
            "/account/privacy",
            json={
                "movies_private": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["movies_private"] is False
        assert data["tv_shows_private"] is True  # Should remain True
        assert data["statistics_private"] is True  # Should remain True
    
    def test_update_privacy_settings_unauthenticated(self, client):
        """Test updating privacy settings without authentication."""
        response = client.put(
            "/account/privacy",
            json={
                "movies_private": True
            }
        )
        
        assert response.status_code == 401


class TestFriendProfileCRUD:
    """Test friend profile CRUD operations."""
    
    def test_get_friend_profile_summary_public(self, db_session, test_user_data):
        """Test getting friend profile summary when data is public."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Create friendship
        crud.create_friendship(db_session, user1.id, user2.id)
        
        # Add some movies and TV shows to user2
        movie = models.Movie(
            title="Test Movie",
            director="Test Director",
            year=2020,
            user_id=user2.id
        )
        db_session.add(movie)
        tv_show = models.TVShow(
            title="Test TV Show",
            year=2020,
            user_id=user2.id
        )
        db_session.add(tv_show)
        db_session.commit()
        
        # Get profile summary
        profile = crud.get_friend_profile_summary(db_session, user2.id)
        
        assert profile is not None
        assert profile.username == "user2"
        assert profile.movies_count == 1
        assert profile.tv_shows_count == 1
        assert profile.statistics_available is True
        assert profile.movies_private is False
        assert profile.tv_shows_private is False
        assert profile.statistics_private is False
    
    def test_get_friend_profile_summary_private_movies(self, db_session, test_user_data):
        """Test getting friend profile summary when movies are private."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Set movies to private
        privacy_update = schemas.PrivacySettingsUpdate(movies_private=True)
        crud.update_privacy_settings(db_session, user2.id, privacy_update)
        
        # Create friendship
        crud.create_friendship(db_session, user1.id, user2.id)
        
        # Get profile summary
        profile = crud.get_friend_profile_summary(db_session, user2.id)
        
        assert profile is not None
        assert profile.movies_count is None  # Should be None when private
        assert profile.movies_private is True
    
    def test_get_friend_movies_public(self, db_session, test_user_data):
        """Test getting friend's movies when public."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Create friendship
        crud.create_friendship(db_session, user1.id, user2.id)
        
        # Add movies to user2
        movie1 = models.Movie(
            title="Movie 1",
            director="Director 1",
            year=2020,
            user_id=user2.id
        )
        movie2 = models.Movie(
            title="Movie 2",
            director="Director 2",
            year=2021,
            user_id=user2.id
        )
        db_session.add(movie1)
        db_session.add(movie2)
        db_session.commit()
        
        # Get friend movies
        movies = crud.get_friend_movies(db_session, user2.id)
        
        assert movies is not None
        assert len(movies) == 2
        assert movies[0].title in ["Movie 1", "Movie 2"]
        assert movies[1].title in ["Movie 1", "Movie 2"]
    
    def test_get_friend_movies_private(self, db_session, test_user_data):
        """Test getting friend's movies when private (should return None)."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Set movies to private
        privacy_update = schemas.PrivacySettingsUpdate(movies_private=True)
        crud.update_privacy_settings(db_session, user2.id, privacy_update)
        
        # Create friendship
        crud.create_friendship(db_session, user1.id, user2.id)
        
        # Get friend movies (should return None when private)
        movies = crud.get_friend_movies(db_session, user2.id)
        
        assert movies is None
    
    def test_get_friend_tv_shows_public(self, db_session, test_user_data):
        """Test getting friend's TV shows when public."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Create friendship
        crud.create_friendship(db_session, user1.id, user2.id)
        
        # Add TV shows to user2
        tv_show1 = models.TVShow(
            title="TV Show 1",
            year=2020,
            user_id=user2.id
        )
        tv_show2 = models.TVShow(
            title="TV Show 2",
            year=2021,
            user_id=user2.id
        )
        db_session.add(tv_show1)
        db_session.add(tv_show2)
        db_session.commit()
        
        # Get friend TV shows
        tv_shows = crud.get_friend_tv_shows(db_session, user2.id)
        
        assert tv_shows is not None
        assert len(tv_shows) == 2
        assert tv_shows[0].title in ["TV Show 1", "TV Show 2"]
        assert tv_shows[1].title in ["TV Show 1", "TV Show 2"]
    
    def test_get_friend_tv_shows_private(self, db_session, test_user_data):
        """Test getting friend's TV shows when private (should return None)."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Set TV shows to private
        privacy_update = schemas.PrivacySettingsUpdate(tv_shows_private=True)
        crud.update_privacy_settings(db_session, user2.id, privacy_update)
        
        # Create friendship
        crud.create_friendship(db_session, user1.id, user2.id)
        
        # Get friend TV shows (should return None when private)
        tv_shows = crud.get_friend_tv_shows(db_session, user2.id)
        
        assert tv_shows is None
    
    def test_get_friend_statistics_public(self, db_session, test_user_data):
        """Test getting friend's statistics when public."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Create friendship
        crud.create_friendship(db_session, user1.id, user2.id)
        
        # Add some movies with ratings to user2
        movie1 = models.Movie(
            title="Movie 1",
            director="Director 1",
            year=2020,
            rating=8.5,
            watched=True,
            user_id=user2.id
        )
        movie2 = models.Movie(
            title="Movie 2",
            director="Director 2",
            year=2021,
            rating=7.0,
            watched=True,
            user_id=user2.id
        )
        db_session.add(movie1)
        db_session.add(movie2)
        db_session.commit()
        
        # Get friend statistics
        stats = crud.get_friend_statistics(db_session, user2.id)
        
        assert stats is not None
        assert "watch_stats" in stats
        assert "rating_stats" in stats
        assert stats["watch_stats"]["total_movies"] == 2
        assert stats["watch_stats"]["watched_movies"] == 2
        assert stats["rating_stats"]["total_rated_items"] == 2
    
    def test_get_friend_statistics_private(self, db_session, test_user_data):
        """Test getting friend's statistics when private (should return None)."""
        # Create two users
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password)
        
        user_data2 = test_user_data.copy()
        user_data2["email"] = "user2@example.com"
        user_data2["username"] = "user2"
        user2_create = schemas.UserCreate(**user_data2)
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Set statistics to private
        privacy_update = schemas.PrivacySettingsUpdate(statistics_private=True)
        crud.update_privacy_settings(db_session, user2.id, privacy_update)
        
        # Create friendship
        crud.create_friendship(db_session, user1.id, user2.id)
        
        # Get friend statistics (should return None when private)
        stats = crud.get_friend_statistics(db_session, user2.id)
        
        assert stats is None
    
    def test_get_friend_profile_summary_nonexistent(self, db_session):
        """Test getting friend profile summary for non-existent user."""
        profile = crud.get_friend_profile_summary(db_session, 99999)
        
        assert profile is None


class TestFriendProfileEndpoints:
    """Test friend profile API endpoints."""
    
    def test_get_friend_profile_success(self, authenticated_client, db_session, test_user_data):
        """Test getting friend profile successfully."""
        # Create friend user
        user_data2 = {
            "email": "friend@example.com",
            "username": "friend",
            "password": "password123"
        }
        from app import crud, schemas, auth
        user2_create = schemas.UserCreate(**user_data2)
        hashed_password = auth.get_password_hash(user_data2["password"])
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Get current user ID
        account_response = authenticated_client.get("/account/me")
        user1_id = account_response.json()["id"]
        
        # Create friendship
        crud.create_friendship(db_session, user1_id, user2.id)
        
        # Get friend profile
        response = authenticated_client.get(f"/friends/{user2.id}/profile")
        
        assert response.status_code == 200
        data = response.json()
        assert "username" in data
        assert data["username"] == "friend"
        assert "movies_count" in data
        assert "tv_shows_count" in data
        assert "statistics_available" in data
    
    def test_get_friend_profile_not_friends(self, authenticated_client, db_session, test_user_data):
        """Test getting friend profile when not friends."""
        # Create non-friend user
        user_data2 = {
            "email": "stranger@example.com",
            "username": "stranger",
            "password": "password123"
        }
        from app import crud, schemas, auth
        user2_create = schemas.UserCreate(**user_data2)
        hashed_password = auth.get_password_hash(user_data2["password"])
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Try to get profile (should fail - not friends)
        response = authenticated_client.get(f"/friends/{user2.id}/profile")
        
        assert response.status_code == 403
        assert "not friends" in response.json()["detail"].lower()
    
    def test_get_friend_movies_success(self, authenticated_client, db_session, test_user_data):
        """Test getting friend's movies successfully."""
        # Create friend user
        user_data2 = {
            "email": "friend@example.com",
            "username": "friend",
            "password": "password123"
        }
        from app import crud, schemas, auth, models
        user2_create = schemas.UserCreate(**user_data2)
        hashed_password = auth.get_password_hash(user_data2["password"])
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Get current user ID
        account_response = authenticated_client.get("/account/me")
        user1_id = account_response.json()["id"]
        
        # Create friendship
        crud.create_friendship(db_session, user1_id, user2.id)
        
        # Add movies to friend
        movie = models.Movie(
            title="Friend Movie",
            director="Friend Director",
            year=2020,
            user_id=user2.id
        )
        db_session.add(movie)
        db_session.commit()
        
        # Get friend movies
        response = authenticated_client.get(f"/friends/{user2.id}/movies")
        
        assert response.status_code == 200
        data = response.json()
        assert "movies" in data
        assert "count" in data
        assert data["count"] == 1
        assert len(data["movies"]) == 1
        assert data["movies"][0]["title"] == "Friend Movie"
    
    def test_get_friend_movies_private(self, authenticated_client, db_session, test_user_data):
        """Test getting friend's movies when private."""
        # Create friend user
        user_data2 = {
            "email": "friend@example.com",
            "username": "friend",
            "password": "password123"
        }
        from app import crud, schemas, auth
        user2_create = schemas.UserCreate(**user_data2)
        hashed_password = auth.get_password_hash(user_data2["password"])
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Get current user ID
        account_response = authenticated_client.get("/account/me")
        user1_id = account_response.json()["id"]
        
        # Create friendship
        crud.create_friendship(db_session, user1_id, user2.id)
        
        # Set movies to private
        privacy_update = schemas.PrivacySettingsUpdate(movies_private=True)
        crud.update_privacy_settings(db_session, user2.id, privacy_update)
        
        # Try to get friend movies (should fail - private)
        response = authenticated_client.get(f"/friends/{user2.id}/movies")
        
        assert response.status_code == 403
        assert "private" in response.json()["detail"].lower()
    
    def test_get_friend_tv_shows_success(self, authenticated_client, db_session, test_user_data):
        """Test getting friend's TV shows successfully."""
        # Create friend user
        user_data2 = {
            "email": "friend@example.com",
            "username": "friend",
            "password": "password123"
        }
        from app import crud, schemas, auth, models
        user2_create = schemas.UserCreate(**user_data2)
        hashed_password = auth.get_password_hash(user_data2["password"])
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Get current user ID
        account_response = authenticated_client.get("/account/me")
        user1_id = account_response.json()["id"]
        
        # Create friendship
        crud.create_friendship(db_session, user1_id, user2.id)
        
        # Add TV shows to friend
        tv_show = models.TVShow(
            title="Friend TV Show",
            year=2020,
            user_id=user2.id
        )
        db_session.add(tv_show)
        db_session.commit()
        
        # Get friend TV shows
        response = authenticated_client.get(f"/friends/{user2.id}/tv-shows")
        
        assert response.status_code == 200
        data = response.json()
        assert "tv_shows" in data
        assert "count" in data
        assert data["count"] == 1
        assert len(data["tv_shows"]) == 1
        assert data["tv_shows"][0]["title"] == "Friend TV Show"
    
    def test_get_friend_tv_shows_private(self, authenticated_client, db_session, test_user_data):
        """Test getting friend's TV shows when private."""
        # Create friend user
        user_data2 = {
            "email": "friend@example.com",
            "username": "friend",
            "password": "password123"
        }
        from app import crud, schemas, auth
        user2_create = schemas.UserCreate(**user_data2)
        hashed_password = auth.get_password_hash(user_data2["password"])
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Get current user ID
        account_response = authenticated_client.get("/account/me")
        user1_id = account_response.json()["id"]
        
        # Create friendship
        crud.create_friendship(db_session, user1_id, user2.id)
        
        # Set TV shows to private
        privacy_update = schemas.PrivacySettingsUpdate(tv_shows_private=True)
        crud.update_privacy_settings(db_session, user2.id, privacy_update)
        
        # Try to get friend TV shows (should fail - private)
        response = authenticated_client.get(f"/friends/{user2.id}/tv-shows")
        
        assert response.status_code == 403
        assert "private" in response.json()["detail"].lower()
    
    def test_get_friend_statistics_success(self, authenticated_client, db_session, test_user_data):
        """Test getting friend's statistics successfully."""
        # Create friend user
        user_data2 = {
            "email": "friend@example.com",
            "username": "friend",
            "password": "password123"
        }
        from app import crud, schemas, auth, models
        user2_create = schemas.UserCreate(**user_data2)
        hashed_password = auth.get_password_hash(user_data2["password"])
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Get current user ID
        account_response = authenticated_client.get("/account/me")
        user1_id = account_response.json()["id"]
        
        # Create friendship
        crud.create_friendship(db_session, user1_id, user2.id)
        
        # Add movies with ratings to friend
        movie = models.Movie(
            title="Friend Movie",
            director="Friend Director",
            year=2020,
            rating=8.5,
            watched=True,
            user_id=user2.id
        )
        db_session.add(movie)
        db_session.commit()
        
        # Get friend statistics
        response = authenticated_client.get(f"/friends/{user2.id}/statistics")
        
        assert response.status_code == 200
        data = response.json()
        assert "watch_stats" in data
        assert "rating_stats" in data
        assert "generated_at" in data
        assert data["watch_stats"]["total_movies"] == 1
        assert data["rating_stats"]["total_rated_items"] == 1
    
    def test_get_friend_statistics_private(self, authenticated_client, db_session, test_user_data):
        """Test getting friend's statistics when private."""
        # Create friend user
        user_data2 = {
            "email": "friend@example.com",
            "username": "friend",
            "password": "password123"
        }
        from app import crud, schemas, auth
        user2_create = schemas.UserCreate(**user_data2)
        hashed_password = auth.get_password_hash(user_data2["password"])
        user2 = crud.create_user(db_session, user2_create, hashed_password)
        
        # Get current user ID
        account_response = authenticated_client.get("/account/me")
        user1_id = account_response.json()["id"]
        
        # Create friendship
        crud.create_friendship(db_session, user1_id, user2.id)
        
        # Set statistics to private
        privacy_update = schemas.PrivacySettingsUpdate(statistics_private=True)
        crud.update_privacy_settings(db_session, user2.id, privacy_update)
        
        # Try to get friend statistics (should fail - private)
        response = authenticated_client.get(f"/friends/{user2.id}/statistics")
        
        assert response.status_code == 403
        assert "private" in response.json()["detail"].lower()
    
    def test_get_friend_profile_nonexistent(self, authenticated_client):
        """Test getting friend profile for non-existent user."""
        # Non-existent user is also not a friend, so returns 403
        response = authenticated_client.get("/friends/99999/profile")
        
        assert response.status_code == 403
        assert "not friends" in response.json()["detail"].lower()
    
    def test_friend_profile_endpoints_require_authentication(self, client):
        """Test that friend profile endpoints require authentication."""
        endpoints = [
            ("GET", "/friends/1/profile"),
            ("GET", "/friends/1/movies"),
            ("GET", "/friends/1/tv-shows"),
            ("GET", "/friends/1/statistics"),
        ]
        
        for method, endpoint in endpoints:
            if method == "GET":
                response = client.get(endpoint)
            assert response.status_code == 401, f"{method} {endpoint} should require authentication"

