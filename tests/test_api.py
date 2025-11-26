"""
Tests for API endpoints.
"""
import pytest
import json


class TestMovieEndpoints:
    """Test movie API endpoints."""
    
    def test_create_movie(self, authenticated_client, test_movie_data):
        """Test creating a movie via API."""
        response = authenticated_client.post("/movies/", json=test_movie_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == test_movie_data["title"]
        assert data["director"] == test_movie_data["director"]
        assert data["year"] == test_movie_data["year"]
        assert "id" in data
    
    def test_get_movies(self, authenticated_client, test_movie_data):
        """Test retrieving movies via API."""
        # Create a movie first
        authenticated_client.post("/movies/", json=test_movie_data)
        
        # Get all movies
        response = authenticated_client.get("/movies/")
        
        assert response.status_code == 200
        movies = response.json()
        assert len(movies) >= 1
        assert any(m["title"] == test_movie_data["title"] for m in movies)
    
    def test_get_movie_by_id(self, authenticated_client, test_movie_data):
        """Test retrieving a specific movie."""
        # Create a movie
        create_response = authenticated_client.post("/movies/", json=test_movie_data)
        movie_id = create_response.json()["id"]
        
        # Get the movie
        response = authenticated_client.get(f"/movies/{movie_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == movie_id
        assert data["title"] == test_movie_data["title"]
    
    def test_update_movie(self, authenticated_client, test_movie_data):
        """Test updating a movie."""
        # Create a movie
        create_response = authenticated_client.post("/movies/", json=test_movie_data)
        movie_id = create_response.json()["id"]
        
        # Update the movie
        update_data = {"rating": 10, "watched": False}  # Integer rating
        response = authenticated_client.put(f"/movies/{movie_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 10.0
        assert data["watched"] is False
    
    def test_delete_movie(self, authenticated_client, test_movie_data):
        """Test deleting a movie."""
        # Create a movie
        create_response = authenticated_client.post("/movies/", json=test_movie_data)
        movie_id = create_response.json()["id"]
        
        # Delete the movie
        response = authenticated_client.delete(f"/movies/{movie_id}")
        
        assert response.status_code == 200
        
        # Verify it's deleted
        get_response = authenticated_client.get(f"/movies/{movie_id}")
        assert get_response.status_code == 404
    
    def test_movie_search(self, authenticated_client, test_movie_data):
        """Test searching movies."""
        # Create a movie
        authenticated_client.post("/movies/", json=test_movie_data)
        
        # Search by title
        response = authenticated_client.get("/movies/?search=Matrix")
        assert response.status_code == 200
        movies = response.json()
        assert len(movies) >= 1
        
        # Search by director
        response = authenticated_client.get("/movies/?search=Wachowski")
        assert response.status_code == 200
        movies = response.json()
        assert len(movies) >= 1
    
    def test_movie_sorting(self, authenticated_client, test_movie_data):
        """Test sorting movies."""
        # Create multiple movies with different ratings
        movie1 = test_movie_data.copy()
        movie1["title"] = "Movie A"
        movie1["rating"] = 5  # Integer
        authenticated_client.post("/movies/", json=movie1)
        
        movie2 = test_movie_data.copy()
        movie2["title"] = "Movie B"
        movie2["rating"] = 9  # Integer
        authenticated_client.post("/movies/", json=movie2)
        
        # Sort by rating descending
        response = authenticated_client.get("/movies/?sort_by=rating&order=desc")
        assert response.status_code == 200
        movies = response.json()
        if len(movies) >= 2:
            assert movies[0]["rating"] >= movies[1]["rating"]


class TestTVShowEndpoints:
    """Test TV show API endpoints."""
    
    def test_create_tv_show(self, authenticated_client, test_tv_show_data):
        """Test creating a TV show via API."""
        response = authenticated_client.post("/tv-shows/", json=test_tv_show_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == test_tv_show_data["title"]
        assert data["year"] == test_tv_show_data["year"]
        assert "id" in data
    
    def test_get_tv_shows(self, authenticated_client, test_tv_show_data):
        """Test retrieving TV shows via API."""
        # Create a TV show first
        authenticated_client.post("/tv-shows/", json=test_tv_show_data)
        
        # Get all TV shows
        response = authenticated_client.get("/tv-shows/")
        
        assert response.status_code == 200
        tv_shows = response.json()
        assert len(tv_shows) >= 1
        assert any(tv["title"] == test_tv_show_data["title"] for tv in tv_shows)
    
    def test_update_tv_show(self, authenticated_client, test_tv_show_data):
        """Test updating a TV show."""
        # Create a TV show
        create_response = authenticated_client.post("/tv-shows/", json=test_tv_show_data)
        tv_show_id = create_response.json()["id"]
        
        # Update the TV show
        update_data = {"rating": 10, "seasons": 6}  # Integer rating
        response = authenticated_client.put(f"/tv-shows/{tv_show_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 10.0
        assert data["seasons"] == 6
    
    def test_delete_tv_show(self, authenticated_client, test_tv_show_data):
        """Test deleting a TV show."""
        # Create a TV show
        create_response = authenticated_client.post("/tv-shows/", json=test_tv_show_data)
        tv_show_id = create_response.json()["id"]
        
        # Delete the TV show
        response = authenticated_client.delete(f"/tv-shows/{tv_show_id}")
        
        assert response.status_code == 200
        
        # Verify it's deleted
        get_response = authenticated_client.get(f"/tv-shows/{tv_show_id}")
        assert get_response.status_code == 404


class TestAuthenticationRequired:
    """Test that protected endpoints require authentication."""
    
    def test_movies_endpoint_requires_auth(self, client):
        """Test that movies endpoint requires authentication."""
        response = client.get("/movies/")
        assert response.status_code == 401
    
    def test_create_movie_requires_auth(self, client, test_movie_data):
        """Test that creating a movie requires authentication."""
        response = client.post("/movies/", json=test_movie_data)
        assert response.status_code == 401
    
    def test_tv_shows_endpoint_requires_auth(self, client):
        """Test that TV shows endpoint requires authentication."""
        response = client.get("/tv-shows/")
        assert response.status_code == 401


class TestExportImport:
    """Test export/import functionality."""
    
    def test_export_data(self, authenticated_client, test_movie_data, test_tv_show_data):
        """Test exporting data."""
        # Create some data
        authenticated_client.post("/movies/", json=test_movie_data)
        authenticated_client.post("/tv-shows/", json=test_tv_show_data)
        
        # Export data
        response = authenticated_client.get("/export/")
        
        assert response.status_code == 200
        data = response.json()
        assert "movies" in data
        assert "tv_shows" in data
        assert "export_metadata" in data
        assert len(data["movies"]) >= 1
        assert len(data["tv_shows"]) >= 1
    
    def test_import_data(self, authenticated_client):
        """Test importing data."""
        import_data = {
            "movies": [
                {
                    "title": "Imported Movie",
                    "director": "Test Director",
                    "year": 2020,
                    "rating": 8,  # Integer rating
                    "watched": True
                }
            ],
            "tv_shows": [
                {
                    "title": "Imported Show",
                    "year": 2021,
                    "seasons": 1,
                    "rating": 9  # Integer rating
                }
            ]
        }
        
        response = authenticated_client.post("/import/", json=import_data)
        
        assert response.status_code == 200
        result = response.json()
        assert result["movies_created"] >= 1
        assert result["tv_shows_created"] >= 1

