"""
Tests for statistics endpoints.
"""
import pytest


class TestStatisticsEndpoints:
    """Test statistics API endpoints."""
    
    def test_get_statistics_dashboard(self, authenticated_client, test_movie_data, test_tv_show_data):
        """Test getting comprehensive statistics dashboard."""
        # Create some data
        authenticated_client.post("/movies/", json=test_movie_data)
        authenticated_client.post("/tv-shows/", json=test_tv_show_data)
        
        # Get statistics dashboard
        response = authenticated_client.get("/statistics/")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "watch_stats" in data
        assert "rating_stats" in data
        assert "year_stats" in data
        assert "director_stats" in data
        assert "generated_at" in data
        
        # Check watch stats structure
        watch_stats = data["watch_stats"]
        assert "total_movies" in watch_stats
        assert "total_tv_shows" in watch_stats
        assert "watched_movies" in watch_stats
        assert "watched_tv_shows" in watch_stats
        
        # Check rating stats structure
        rating_stats = data["rating_stats"]
        assert "average_rating" in rating_stats
        assert "total_rated_items" in rating_stats
        assert "rating_distribution" in rating_stats
        
        # Check year stats structure
        year_stats = data["year_stats"]
        assert "movies_by_year" in year_stats
        assert "tv_shows_by_year" in year_stats
        
        # Check director stats structure
        director_stats = data["director_stats"]
        assert "top_directors" in director_stats
        assert "highest_rated_directors" in director_stats
    
    def test_get_watch_statistics(self, authenticated_client, test_movie_data, test_tv_show_data):
        """Test getting watch statistics."""
        # Create watched and unwatched items
        movie_data = test_movie_data.copy()
        movie_data["watched"] = True
        authenticated_client.post("/movies/", json=movie_data)
        
        tv_data = test_tv_show_data.copy()
        tv_data["watched"] = False
        authenticated_client.post("/tv-shows/", json=tv_data)
        
        # Get watch statistics
        response = authenticated_client.get("/statistics/watch/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_movies" in data
        assert "total_tv_shows" in data
        assert "watched_movies" in data
        assert "watched_tv_shows" in data
        assert data["total_movies"] >= 1
        assert data["total_tv_shows"] >= 1
    
    def test_get_rating_statistics(self, authenticated_client, test_movie_data, test_tv_show_data):
        """Test getting rating statistics."""
        # Create items with ratings
        movie_data = test_movie_data.copy()
        movie_data["rating"] = 9
        authenticated_client.post("/movies/", json=movie_data)
        
        tv_data = test_tv_show_data.copy()
        tv_data["rating"] = 8
        authenticated_client.post("/tv-shows/", json=tv_data)
        
        # Get rating statistics
        response = authenticated_client.get("/statistics/ratings/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "average_rating" in data
        assert "total_rated_items" in data
        assert "rating_distribution" in data
        assert "highest_rated" in data
        assert "lowest_rated" in data
        assert data["total_rated_items"] >= 2
        assert isinstance(data["average_rating"], (int, float))
    
    def test_get_year_statistics(self, authenticated_client, test_movie_data, test_tv_show_data):
        """Test getting year-based statistics."""
        # Create items with specific years
        movie_data = test_movie_data.copy()
        movie_data["year"] = 1999
        authenticated_client.post("/movies/", json=movie_data)
        
        tv_data = test_tv_show_data.copy()
        tv_data["year"] = 2020
        authenticated_client.post("/tv-shows/", json=tv_data)
        
        # Get year statistics
        response = authenticated_client.get("/statistics/years/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "movies_by_year" in data
        assert "tv_shows_by_year" in data
        assert "all_years" in data
        assert "decade_stats" in data
        assert isinstance(data["all_years"], list)
    
    def test_get_director_statistics(self, authenticated_client, test_movie_data):
        """Test getting director statistics."""
        # Create movies with directors
        movie1 = test_movie_data.copy()
        movie1["director"] = "Director A"
        movie1["rating"] = 9
        authenticated_client.post("/movies/", json=movie1)
        
        movie2 = test_movie_data.copy()
        movie2["title"] = "Movie 2"
        movie2["director"] = "Director A"
        movie2["rating"] = 8
        authenticated_client.post("/movies/", json=movie2)
        
        # Get director statistics
        response = authenticated_client.get("/statistics/directors/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "top_directors" in data
        assert "highest_rated_directors" in data
        assert isinstance(data["top_directors"], list)
        assert isinstance(data["highest_rated_directors"], list)
        
        # Check that Director A appears in top directors
        top_directors = [d["director"] for d in data["top_directors"]]
        assert "Director A" in top_directors
    
    def test_statistics_empty_data(self, authenticated_client):
        """Test statistics endpoints with no data."""
        # Get statistics with no movies/TV shows
        response = authenticated_client.get("/statistics/")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should still return valid structure
        assert "watch_stats" in data
        assert "rating_stats" in data
        assert "year_stats" in data
        assert "director_stats" in data
        
        # Watch stats should show zeros
        assert data["watch_stats"]["total_movies"] == 0
        assert data["watch_stats"]["total_tv_shows"] == 0
    
    def test_statistics_requires_auth(self, client):
        """Test that statistics endpoints require authentication."""
        endpoints = [
            "/statistics/",
            "/statistics/watch/",
            "/statistics/ratings/",
            "/statistics/years/",
            "/statistics/directors/"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401, f"{endpoint} should require auth"
    
    def test_statistics_data_isolation(self, client, test_user_data, test_movie_data, db_session):
        """Test that statistics are isolated per user."""
        from app import crud, models, schemas, auth
        
        # Create two users using the proper method
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password1 = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password1, "token1")
        
        user2_data = test_user_data.copy()
        user2_data["email"] = "user2@test.com"
        user2_data["username"] = "user2"
        user2_create = schemas.UserCreate(**user2_data)
        hashed_password2 = auth.get_password_hash(user2_data["password"])
        user2 = crud.create_user(db_session, user2_create, hashed_password2, "token2")
        
        # Verify user2
        user2.is_verified = True
        db_session.commit()
        
        # Create movies for user1
        movie1_create = schemas.MovieCreate(**test_movie_data)
        crud.create_movie(db_session, user1.id, movie1_create)
        
        # Create movies for user2
        movie2_data = test_movie_data.copy()
        movie2_data["title"] = "User2 Movie"
        movie2_create = schemas.MovieCreate(**movie2_data)
        crud.create_movie(db_session, user2.id, movie2_create)
        
        # Login as user2
        login_response = client.post(
            "/auth/login",
            data={"username": "user2", "password": test_user_data["password"]},
            headers={"content-type": "application/x-www-form-urlencoded"}
        )
        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}
        
        # Get statistics for user2
        stats_response = client.get("/statistics/")
        assert stats_response.status_code == 200
        
        # User2 should only see their own movie
        watch_stats = stats_response.json()["watch_stats"]
        assert watch_stats["total_movies"] == 1
        
        # The movie should be user2's movie
        movies_response = client.get("/movies/")
        movies = movies_response.json()
        assert len(movies) == 1
        assert movies[0]["title"] == "User2 Movie"

