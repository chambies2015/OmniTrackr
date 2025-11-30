"""
Tests for API endpoints with special characters (apostrophes, quotes, backslashes, etc.).
These tests ensure that the frontend escaping fixes work correctly with the backend API.
"""
import pytest


class TestSpecialCharactersMovies:
    """Test movie API endpoints with special characters."""
    
    def test_create_movie_with_apostrophe(self, authenticated_client):
        """Test creating a movie with apostrophe in title."""
        movie_data = {
            "title": "It's a Wonderful Life",
            "director": "Frank Capra",
            "year": 1946,
            "rating": 9.0,
            "watched": True,
            "review": "A classic film"
        }
        response = authenticated_client.post("/movies/", json=movie_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "It's a Wonderful Life"
        assert data["director"] == "Frank Capra"
    
    def test_create_movie_with_quotes(self, authenticated_client):
        """Test creating a movie with quotes in title."""
        movie_data = {
            "title": 'The "Matrix"',
            "director": "Wachowski Brothers",
            "year": 1999,
            "rating": 9.0,
            "watched": True
        }
        response = authenticated_client.post("/movies/", json=movie_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == 'The "Matrix"'
    
    def test_create_movie_with_backslash(self, authenticated_client):
        """Test creating a movie with backslash in title."""
        movie_data = {
            "title": "C:\\Movies\\Test",
            "director": "Test Director",
            "year": 2020,
            "rating": 7.0,
            "watched": False
        }
        response = authenticated_client.post("/movies/", json=movie_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "C:\\Movies\\Test"
    
    def test_create_movie_with_apostrophe_in_director(self, authenticated_client):
        """Test creating a movie with apostrophe in director name."""
        movie_data = {
            "title": "Test Movie",
            "director": "O'Connor",
            "year": 2020,
            "rating": 8.0,
            "watched": True
        }
        response = authenticated_client.post("/movies/", json=movie_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["director"] == "O'Connor"
    
    def test_create_movie_with_special_chars_in_review(self, authenticated_client):
        """Test creating a movie with special characters in review."""
        movie_data = {
            "title": "Test Movie",
            "director": "Test Director",
            "year": 2020,
            "rating": 8.0,
            "watched": True,
            "review": "It's a \"great\" movie! Path: C:\\Movies"
        }
        response = authenticated_client.post("/movies/", json=movie_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["review"] == "It's a \"great\" movie! Path: C:\\Movies"
    
    def test_update_movie_with_apostrophe(self, authenticated_client):
        """Test updating a movie title with apostrophe."""
        # Create a movie first
        movie_data = {
            "title": "Original Title",
            "director": "Director",
            "year": 2020,
            "rating": 7.0
        }
        create_response = authenticated_client.post("/movies/", json=movie_data)
        movie_id = create_response.json()["id"]
        
        # Update with apostrophe
        update_data = {"title": "Frieren: Beyond Journey's End"}
        response = authenticated_client.put(f"/movies/{movie_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Frieren: Beyond Journey's End"
    
    def test_update_movie_with_quotes(self, authenticated_client):
        """Test updating a movie with quotes."""
        movie_data = {
            "title": "Original",
            "director": "Director",
            "year": 2020,
            "rating": 7.0
        }
        create_response = authenticated_client.post("/movies/", json=movie_data)
        movie_id = create_response.json()["id"]
        
        update_data = {"title": 'He said "Hello"'}
        response = authenticated_client.put(f"/movies/{movie_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == 'He said "Hello"'
    
    def test_update_movie_with_backslash_and_quote(self, authenticated_client):
        """Test updating a movie with backslash followed by quote."""
        movie_data = {
            "title": "Original",
            "director": "Director",
            "year": 2020,
            "rating": 7.0
        }
        create_response = authenticated_client.post("/movies/", json=movie_data)
        movie_id = create_response.json()["id"]
        
        update_data = {"title": "Test\\'Value"}
        response = authenticated_client.put(f"/movies/{movie_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test\\'Value"


class TestSpecialCharactersTVShows:
    """Test TV show API endpoints with special characters."""
    
    def test_create_tv_show_with_apostrophe(self, authenticated_client):
        """Test creating a TV show with apostrophe in title."""
        tv_data = {
            "title": "It's Always Sunny",
            "year": 2005,
            "seasons": 15,
            "episodes": 170,
            "rating": 9.0,
            "watched": True
        }
        response = authenticated_client.post("/tv-shows/", json=tv_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "It's Always Sunny"
    
    def test_update_tv_show_with_apostrophe(self, authenticated_client, test_tv_show_data):
        """Test updating a TV show title with apostrophe."""
        create_response = authenticated_client.post("/tv-shows/", json=test_tv_show_data)
        tv_id = create_response.json()["id"]
        
        update_data = {"title": "Frieren: Beyond Journey's End"}
        response = authenticated_client.put(f"/tv-shows/{tv_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Frieren: Beyond Journey's End"
    
    def test_create_tv_show_with_special_chars_in_review(self, authenticated_client):
        """Test creating a TV show with special characters in review."""
        tv_data = {
            "title": "Test Show",
            "year": 2020,
            "rating": 8.0,
            "watched": True,
            "review": "It's \"amazing\"! Path: C:\\Shows"
        }
        response = authenticated_client.post("/tv-shows/", json=tv_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["review"] == "It's \"amazing\"! Path: C:\\Shows"


class TestSpecialCharactersAnime:
    """Test anime API endpoints with special characters."""
    
    def test_create_anime_with_apostrophe(self, authenticated_client):
        """Test creating an anime with apostrophe in title."""
        anime_data = {
            "title": "Frieren: Beyond Journey's End",
            "year": 2023,
            "seasons": 1,
            "episodes": 28,
            "rating": 10.0,
            "watched": True
        }
        response = authenticated_client.post("/anime/", json=anime_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Frieren: Beyond Journey's End"
    
    def test_update_anime_with_apostrophe(self, authenticated_client, test_anime_data):
        """Test updating an anime title with apostrophe."""
        create_response = authenticated_client.post("/anime/", json=test_anime_data)
        anime_id = create_response.json()["id"]
        
        update_data = {"title": "Frieren: Beyond Journey's End"}
        response = authenticated_client.put(f"/anime/{anime_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Frieren: Beyond Journey's End"
    
    def test_create_anime_with_title_apostrophe(self, authenticated_client):
        """Test creating an anime with apostrophe in title (the specific bug case)."""
        anime_data = {
            "title": "title's",
            "year": 2025,
            "rating": 8.0,
            "watched": False
        }
        response = authenticated_client.post("/anime/", json=anime_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "title's"
        
        # Verify we can retrieve it
        get_response = authenticated_client.get(f"/anime/{data['id']}")
        assert get_response.status_code == 200
        assert get_response.json()["title"] == "title's"
    
    def test_update_anime_with_title_apostrophe(self, authenticated_client, test_anime_data):
        """Test updating an anime to have apostrophe in title (the specific bug case)."""
        create_response = authenticated_client.post("/anime/", json=test_anime_data)
        anime_id = create_response.json()["id"]
        
        update_data = {"title": "title's"}
        response = authenticated_client.put(f"/anime/{anime_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "title's"
        
        # Verify we can retrieve it after update
        get_response = authenticated_client.get(f"/anime/{anime_id}")
        assert get_response.status_code == 200
        assert get_response.json()["title"] == "title's"
    
    def test_create_anime_with_special_chars_in_review(self, authenticated_client):
        """Test creating an anime with special characters in review."""
        anime_data = {
            "title": "Test Anime",
            "year": 2020,
            "rating": 8.0,
            "watched": True,
            "review": "It's \"great\"! Path: C:\\Anime"
        }
        response = authenticated_client.post("/anime/", json=anime_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["review"] == "It's \"great\"! Path: C:\\Anime"
    
    def test_create_anime_with_control_characters(self, authenticated_client):
        """Test creating an anime with control characters (should be handled safely)."""
        anime_data = {
            "title": "Test\nAnime",
            "year": 2020,
            "rating": 8.0,
            "watched": False
        }
        response = authenticated_client.post("/anime/", json=anime_data)
        
        assert response.status_code == 201
        data = response.json()
        # Control characters should be preserved in the database
        assert "\n" in data["title"]


class TestSpecialCharactersEdgeCases:
    """Test edge cases with special characters."""
    
    def test_movie_with_all_special_chars(self, authenticated_client):
        """Test movie with all types of special characters."""
        movie_data = {
            "title": "It's a \"Great\" Movie (C:\\Path\\To\\File)",
            "director": "O'Connor & O'Brien",
            "year": 2020,
            "rating": 8.5,
            "watched": True,
            "review": "It's \"amazing\"! Path: C:\\Movies\\Test\nNew line here."
        }
        response = authenticated_client.post("/movies/", json=movie_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "It's a \"Great\" Movie (C:\\Path\\To\\File)"
        assert data["director"] == "O'Connor & O'Brien"
        assert data["review"] == "It's \"amazing\"! Path: C:\\Movies\\Test\nNew line here."
        
        # Verify we can retrieve it
        get_response = authenticated_client.get(f"/movies/{data['id']}")
        assert get_response.status_code == 200
        retrieved = get_response.json()
        assert retrieved["title"] == movie_data["title"]
        assert retrieved["director"] == movie_data["director"]
        assert retrieved["review"] == movie_data["review"]
        
        # Verify we can update it
        update_data = {"title": "Updated: It's Still \"Great\""}
        update_response = authenticated_client.put(f"/movies/{data['id']}", json=update_data)
        assert update_response.status_code == 200
        assert update_response.json()["title"] == "Updated: It's Still \"Great\""

