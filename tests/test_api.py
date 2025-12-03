"""
Tests for API endpoints.
"""
import pytest
import json
from io import BytesIO


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
    
    def test_create_movie_with_decimal_rating(self, authenticated_client):
        """Test creating a movie with decimal rating via API."""
        movie_data = {
            "title": "Test Movie",
            "director": "Test Director",
            "year": 2020,
            "rating": 8.5
        }
        response = authenticated_client.post("/movies/", json=movie_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["rating"] == 8.5
        assert isinstance(data["rating"], (int, float))
    
    def test_update_movie_with_decimal_rating(self, authenticated_client, test_movie_data):
        """Test updating a movie with decimal rating via API."""
        create_response = authenticated_client.post("/movies/", json=test_movie_data)
        movie_id = create_response.json()["id"]
        
        update_data = {"rating": 7.4}
        response = authenticated_client.put(f"/movies/{movie_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 7.4
    
    def test_get_movies(self, authenticated_client, test_movie_data):
        """Test retrieving movies via API."""
        # Create a movie first
        authenticated_client.post("/movies/", json=test_movie_data)
        
        response = authenticated_client.get("/movies/")
        
        assert response.status_code == 200
        movies = response.json()
        assert len(movies) >= 1
        assert any(m["title"] == test_movie_data["title"] for m in movies)
    
    def test_get_movie_by_id(self, authenticated_client, test_movie_data):
        """Test retrieving a specific movie."""
        create_response = authenticated_client.post("/movies/", json=test_movie_data)
        movie_id = create_response.json()["id"]
        
        response = authenticated_client.get(f"/movies/{movie_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == movie_id
        assert data["title"] == test_movie_data["title"]
    
    def test_update_movie(self, authenticated_client, test_movie_data):
        """Test updating a movie."""
        create_response = authenticated_client.post("/movies/", json=test_movie_data)
        movie_id = create_response.json()["id"]
        
        update_data = {"rating": 10, "watched": False}
        response = authenticated_client.put(f"/movies/{movie_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 10.0
        assert data["watched"] is False
    
    def test_delete_movie(self, authenticated_client, test_movie_data):
        """Test deleting a movie."""
        create_response = authenticated_client.post("/movies/", json=test_movie_data)
        movie_id = create_response.json()["id"]
        
        response = authenticated_client.delete(f"/movies/{movie_id}")
        
        assert response.status_code == 200
        
        get_response = authenticated_client.get(f"/movies/{movie_id}")
        assert get_response.status_code == 404
    
    def test_movie_search(self, authenticated_client, test_movie_data):
        """Test searching movies."""
        authenticated_client.post("/movies/", json=test_movie_data)
        
        response = authenticated_client.get("/movies/?search=Matrix")
        assert response.status_code == 200
        movies = response.json()
        assert len(movies) >= 1
        
        response = authenticated_client.get("/movies/?search=Wachowski")
        assert response.status_code == 200
        movies = response.json()
        assert len(movies) >= 1
    
    def test_movie_sorting(self, authenticated_client, test_movie_data):
        """Test sorting movies."""
        movie1 = test_movie_data.copy()
        movie1["title"] = "Movie A"
        movie1["rating"] = 5
        authenticated_client.post("/movies/", json=movie1)
        
        movie2 = test_movie_data.copy()
        movie2["title"] = "Movie B"
        movie2["rating"] = 9
        authenticated_client.post("/movies/", json=movie2)
        
        response = authenticated_client.get("/movies/?sort_by=rating&order=desc")
        assert response.status_code == 200
        movies = response.json()
        if len(movies) >= 2:
            assert movies[0]["rating"] >= movies[1]["rating"]
    
    def test_get_nonexistent_movie(self, authenticated_client):
        """Test getting a non-existent movie returns 404."""
        response = authenticated_client.get("/movies/99999")
        assert response.status_code == 404
    
    def test_update_nonexistent_movie(self, authenticated_client):
        """Test updating a non-existent movie returns 404."""
        response = authenticated_client.put("/movies/99999", json={"rating": 5})
        assert response.status_code == 404
    
    def test_delete_nonexistent_movie(self, authenticated_client):
        """Test deleting a non-existent movie returns 404."""
        response = authenticated_client.delete("/movies/99999")
        assert response.status_code == 404


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
        authenticated_client.post("/tv-shows/", json=test_tv_show_data)
        
        response = authenticated_client.get("/tv-shows/")
        
        assert response.status_code == 200
        tv_shows = response.json()
        assert len(tv_shows) >= 1
        assert any(tv["title"] == test_tv_show_data["title"] for tv in tv_shows)
    
    def test_update_tv_show(self, authenticated_client, test_tv_show_data):
        """Test updating a TV show."""
        create_response = authenticated_client.post("/tv-shows/", json=test_tv_show_data)
        tv_show_id = create_response.json()["id"]
        
        update_data = {"rating": 10, "seasons": 6}
        response = authenticated_client.put(f"/tv-shows/{tv_show_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 10.0
        assert data["seasons"] == 6
    
    def test_create_tv_show_with_decimal_rating(self, authenticated_client):
        """Test creating a TV show with decimal rating via API."""
        tv_show_data = {
            "title": "Test TV Show",
            "year": 2020,
            "rating": 9.2
        }
        response = authenticated_client.post("/tv-shows/", json=tv_show_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["rating"] == 9.2
        assert isinstance(data["rating"], (int, float))
    
    def test_update_tv_show_with_decimal_rating(self, authenticated_client, test_tv_show_data):
        """Test updating a TV show with decimal rating via API."""
        create_response = authenticated_client.post("/tv-shows/", json=test_tv_show_data)
        tv_show_id = create_response.json()["id"]
        
        # Update with decimal rating
        update_data = {"rating": 6.7}
        response = authenticated_client.put(f"/tv-shows/{tv_show_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 6.7
    
    def test_get_tv_show_by_id(self, authenticated_client, test_tv_show_data):
        """Test retrieving a specific TV show."""
        create_response = authenticated_client.post("/tv-shows/", json=test_tv_show_data)
        tv_show_id = create_response.json()["id"]
        
        response = authenticated_client.get(f"/tv-shows/{tv_show_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == tv_show_id
        assert data["title"] == test_tv_show_data["title"]
    
    def test_delete_tv_show(self, authenticated_client, test_tv_show_data):
        """Test deleting a TV show."""
        create_response = authenticated_client.post("/tv-shows/", json=test_tv_show_data)
        tv_show_id = create_response.json()["id"]
        
        response = authenticated_client.delete(f"/tv-shows/{tv_show_id}")
        
        assert response.status_code == 200
        
        # Verify it's deleted
        get_response = authenticated_client.get(f"/tv-shows/{tv_show_id}")
        assert get_response.status_code == 404
    
    def test_tv_show_search(self, authenticated_client, test_tv_show_data):
        """Test searching TV shows."""
        authenticated_client.post("/tv-shows/", json=test_tv_show_data)
        
        response = authenticated_client.get("/tv-shows/?search=Breaking")
        assert response.status_code == 200
        tv_shows = response.json()
        assert len(tv_shows) >= 1
    
    def test_tv_show_sorting(self, authenticated_client, test_tv_show_data):
        """Test sorting TV shows."""
        tv1 = test_tv_show_data.copy()
        tv1["title"] = "TV Show A"
        tv1["rating"] = 5
        authenticated_client.post("/tv-shows/", json=tv1)
        
        tv2 = test_tv_show_data.copy()
        tv2["title"] = "TV Show B"
        tv2["rating"] = 9
        authenticated_client.post("/tv-shows/", json=tv2)
        
        # Sort by rating descending
        response = authenticated_client.get("/tv-shows/?sort_by=rating&order=desc")
        assert response.status_code == 200
        tv_shows = response.json()
        if len(tv_shows) >= 2:
            assert tv_shows[0]["rating"] >= tv_shows[1]["rating"]
    
    def test_get_nonexistent_tv_show(self, authenticated_client):
        """Test getting a non-existent TV show returns 404."""
        response = authenticated_client.get("/tv-shows/99999")
        assert response.status_code == 404
    
    def test_update_nonexistent_tv_show(self, authenticated_client):
        """Test updating a non-existent TV show returns 404."""
        response = authenticated_client.put("/tv-shows/99999", json={"rating": 5})
        assert response.status_code == 404
    
    def test_delete_nonexistent_tv_show(self, authenticated_client):
        """Test deleting a non-existent TV show returns 404."""
        response = authenticated_client.delete("/tv-shows/99999")
        assert response.status_code == 404


class TestAnimeEndpoints:
    """Test anime API endpoints."""
    
    def test_create_anime(self, authenticated_client, test_anime_data):
        """Test creating an anime via API."""
        response = authenticated_client.post("/anime/", json=test_anime_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == test_anime_data["title"]
        assert data["year"] == test_anime_data["year"]
        assert "id" in data
    
    def test_get_anime(self, authenticated_client, test_anime_data):
        """Test retrieving anime via API."""
        # Create an anime first
        authenticated_client.post("/anime/", json=test_anime_data)
        
        response = authenticated_client.get("/anime/")
        
        assert response.status_code == 200
        anime = response.json()
        assert len(anime) >= 1
        assert any(a["title"] == test_anime_data["title"] for a in anime)
    
    def test_update_anime(self, authenticated_client, test_anime_data):
        """Test updating an anime."""
        create_response = authenticated_client.post("/anime/", json=test_anime_data)
        anime_id = create_response.json()["id"]
        
        update_data = {"rating": 10, "seasons": 5}
        response = authenticated_client.put(f"/anime/{anime_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 10.0
        assert data["seasons"] == 5
    
    def test_create_anime_with_decimal_rating(self, authenticated_client):
        """Test creating an anime with decimal rating via API."""
        anime_data = {
            "title": "Test Anime",
            "year": 2020,
            "rating": 8.7  # Decimal rating
        }
        response = authenticated_client.post("/anime/", json=anime_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["rating"] == 8.7
        assert isinstance(data["rating"], (int, float))
    
    def test_update_anime_with_decimal_rating(self, authenticated_client, test_anime_data):
        """Test updating an anime with decimal rating via API."""
        create_response = authenticated_client.post("/anime/", json=test_anime_data)
        anime_id = create_response.json()["id"]
        
        # Update with decimal rating
        update_data = {"rating": 7.3}
        response = authenticated_client.put(f"/anime/{anime_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 7.3
    
    def test_get_anime_by_id(self, authenticated_client, test_anime_data):
        """Test retrieving a specific anime."""
        create_response = authenticated_client.post("/anime/", json=test_anime_data)
        anime_id = create_response.json()["id"]
        
        response = authenticated_client.get(f"/anime/{anime_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == anime_id
        assert data["title"] == test_anime_data["title"]
    
    def test_delete_anime(self, authenticated_client, test_anime_data):
        """Test deleting an anime."""
        create_response = authenticated_client.post("/anime/", json=test_anime_data)
        anime_id = create_response.json()["id"]
        
        response = authenticated_client.delete(f"/anime/{anime_id}")
        
        assert response.status_code == 200
        
        get_response = authenticated_client.get(f"/anime/{anime_id}")
        assert get_response.status_code == 404
    
    def test_anime_search(self, authenticated_client, test_anime_data):
        """Test searching anime."""
        authenticated_client.post("/anime/", json=test_anime_data)
        
        response = authenticated_client.get("/anime/?search=Attack")
        assert response.status_code == 200
        anime = response.json()
        assert len(anime) >= 1
    
    def test_anime_sorting(self, authenticated_client, test_anime_data):
        """Test sorting anime."""
        anime1 = test_anime_data.copy()
        anime1["title"] = "Anime A"
        anime1["rating"] = 5
        authenticated_client.post("/anime/", json=anime1)
        
        anime2 = test_anime_data.copy()
        anime2["title"] = "Anime B"
        anime2["rating"] = 9
        authenticated_client.post("/anime/", json=anime2)
        
        # Sort by rating descending
        response = authenticated_client.get("/anime/?sort_by=rating&order=desc")
        assert response.status_code == 200
        anime = response.json()
        if len(anime) >= 2:
            assert anime[0]["rating"] >= anime[1]["rating"]
    
    def test_get_nonexistent_anime(self, authenticated_client):
        """Test getting a non-existent anime returns 404."""
        response = authenticated_client.get("/anime/99999")
        assert response.status_code == 404
    
    def test_update_nonexistent_anime(self, authenticated_client):
        """Test updating a non-existent anime returns 404."""
        response = authenticated_client.put("/anime/99999", json={"rating": 5})
        assert response.status_code == 404
    
    def test_delete_nonexistent_anime(self, authenticated_client):
        """Test deleting a non-existent anime returns 404."""
        response = authenticated_client.delete("/anime/99999")
        assert response.status_code == 404
    
    def test_anime_endpoint_requires_auth(self, client):
        """Test that anime endpoint requires authentication."""
        response = client.get("/anime/")
        assert response.status_code == 401


class TestVideoGameEndpoints:
    """Test video game API endpoints."""
    
    def test_create_video_game(self, authenticated_client, test_video_game_data):
        """Test creating a video game via API."""
        response = authenticated_client.post("/video-games/", json=test_video_game_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == test_video_game_data["title"]
        assert data["genres"] == test_video_game_data["genres"]
        assert "id" in data
    
    def test_get_video_games(self, authenticated_client, test_video_game_data):
        """Test retrieving video games via API."""
        authenticated_client.post("/video-games/", json=test_video_game_data)
        
        response = authenticated_client.get("/video-games/")
        
        assert response.status_code == 200
        video_games = response.json()
        assert len(video_games) >= 1
        assert any(vg["title"] == test_video_game_data["title"] for vg in video_games)
    
    def test_update_video_game(self, authenticated_client, test_video_game_data):
        """Test updating a video game."""
        create_response = authenticated_client.post("/video-games/", json=test_video_game_data)
        game_id = create_response.json()["id"]
        
        update_data = {"rating": 10.0, "played": False}
        response = authenticated_client.put(f"/video-games/{game_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 10.0
        assert data["played"] is False
    
    def test_create_video_game_with_decimal_rating(self, authenticated_client):
        """Test creating a video game with decimal rating via API."""
        from datetime import datetime
        video_game_data = {
            "title": "Test Game",
            "release_date": datetime(2020, 1, 1).isoformat(),
            "rating": 8.7  # Decimal rating
        }
        response = authenticated_client.post("/video-games/", json=video_game_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["rating"] == 8.7
        assert isinstance(data["rating"], (int, float))
    
    def test_update_video_game_with_decimal_rating(self, authenticated_client, test_video_game_data):
        """Test updating a video game with decimal rating via API."""
        create_response = authenticated_client.post("/video-games/", json=test_video_game_data)
        game_id = create_response.json()["id"]
        
        update_data = {"rating": 7.3}
        response = authenticated_client.put(f"/video-games/{game_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 7.3
    
    def test_get_video_game_by_id(self, authenticated_client, test_video_game_data):
        """Test retrieving a specific video game."""
        create_response = authenticated_client.post("/video-games/", json=test_video_game_data)
        game_id = create_response.json()["id"]
        
        response = authenticated_client.get(f"/video-games/{game_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == game_id
        assert data["title"] == test_video_game_data["title"]
    
    def test_delete_video_game(self, authenticated_client, test_video_game_data):
        """Test deleting a video game."""
        create_response = authenticated_client.post("/video-games/", json=test_video_game_data)
        game_id = create_response.json()["id"]
        
        response = authenticated_client.delete(f"/video-games/{game_id}")
        
        assert response.status_code == 200
        
        get_response = authenticated_client.get(f"/video-games/{game_id}")
        assert get_response.status_code == 404
    
    def test_video_game_search(self, authenticated_client, test_video_game_data):
        """Test searching video games."""
        authenticated_client.post("/video-games/", json=test_video_game_data)
        
        response = authenticated_client.get("/video-games/?search=Zelda")
        assert response.status_code == 200
        video_games = response.json()
        assert len(video_games) >= 1
        
        response = authenticated_client.get("/video-games/?search=Action")
        assert response.status_code == 200
        video_games = response.json()
        assert len(video_games) >= 1
    
    def test_video_game_sorting(self, authenticated_client, test_video_game_data):
        """Test sorting video games."""
        from datetime import datetime
        game1 = test_video_game_data.copy()
        game1["title"] = "Game A"
        game1["rating"] = 5.0
        authenticated_client.post("/video-games/", json=game1)
        
        game2 = test_video_game_data.copy()
        game2["title"] = "Game B"
        game2["rating"] = 9.0
        authenticated_client.post("/video-games/", json=game2)
        
        # Sort by rating descending
        response = authenticated_client.get("/video-games/?sort_by=rating&order=desc")
        assert response.status_code == 200
        video_games = response.json()
        if len(video_games) >= 2:
            assert video_games[0]["rating"] >= video_games[1]["rating"]
        
        response = authenticated_client.get("/video-games/?sort_by=release_date&order=asc")
        assert response.status_code == 200
        video_games = response.json()
        if len(video_games) >= 2:
            dates = [vg.get("release_date") for vg in video_games if vg.get("release_date")]
            if len(dates) >= 2:
                assert dates[0] <= dates[1]
    
    def test_get_nonexistent_video_game(self, authenticated_client):
        """Test getting a non-existent video game returns 404."""
        response = authenticated_client.get("/video-games/99999")
        assert response.status_code == 404
    
    def test_update_nonexistent_video_game(self, authenticated_client):
        """Test updating a non-existent video game returns 404."""
        response = authenticated_client.put("/video-games/99999", json={"rating": 5})
        assert response.status_code == 404
    
    def test_delete_nonexistent_video_game(self, authenticated_client):
        """Test deleting a non-existent video game returns 404."""
        response = authenticated_client.delete("/video-games/99999")
        assert response.status_code == 404
    
    def test_video_game_endpoint_requires_auth(self, client):
        """Test that video game endpoint requires authentication."""
        response = client.get("/video-games/")
        assert response.status_code == 401


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
    
    def test_export_data(self, authenticated_client, test_movie_data, test_tv_show_data, test_video_game_data):
        """Test exporting data."""
        authenticated_client.post("/movies/", json=test_movie_data)
        authenticated_client.post("/tv-shows/", json=test_tv_show_data)
        authenticated_client.post("/video-games/", json=test_video_game_data)
        
        response = authenticated_client.get("/export/")
        
        assert response.status_code == 200
        data = response.json()
        assert "movies" in data
        assert "tv_shows" in data
        assert "anime" in data
        assert "video_games" in data
        assert "export_metadata" in data
        assert len(data["movies"]) >= 1
        assert len(data["tv_shows"]) >= 1
        assert len(data["video_games"]) >= 1
    
    def test_import_data(self, authenticated_client):
        """Test importing data."""
        from datetime import datetime
        import_data = {
            "movies": [
                {
                    "title": "Imported Movie",
                    "director": "Test Director",
                    "year": 2020,
                    "rating": 8,
                    "watched": True
                }
            ],
            "tv_shows": [
                {
                    "title": "Imported Show",
                    "year": 2021,
                    "seasons": 1,
                    "rating": 9
                }
            ],
            "anime": [],
            "video_games": [
                {
                    "title": "Imported Game",
                    "release_date": datetime(2020, 1, 1).isoformat(),
                    "genres": "Action, Adventure",
                    "rating": 8.5,
                    "played": True
                }
            ]
        }
        
        response = authenticated_client.post("/import/", json=import_data)
        
        assert response.status_code == 200
        result = response.json()
        assert result["movies_created"] >= 1
        assert result["tv_shows_created"] >= 1
        assert "anime_created" in result
        assert "anime_updated" in result
        assert "video_games_created" in result
        assert "video_games_updated" in result
        assert result["video_games_created"] >= 1
    
    def test_import_from_file(self, authenticated_client):
        """Test importing data from a JSON file."""
        from datetime import datetime
        import_data = {
            "movies": [
                {
                    "title": "File Imported Movie",
                    "director": "Test Director",
                    "year": 2020,
                    "rating": 8,
                    "watched": True
                }
            ],
            "tv_shows": [
                {
                    "title": "File Imported Show",
                    "year": 2021,
                    "seasons": 1,
                    "rating": 9
                }
            ],
            "anime": [],
            "video_games": [
                {
                    "title": "File Imported Game",
                    "release_date": datetime(2020, 1, 1).isoformat(),
                    "genres": "Action",
                    "rating": 8.0,
                    "played": True
                }
            ]
        }
        
        import json
        file_content = json.dumps(import_data).encode('utf-8')
        
        files = {"file": ("test_import.json", file_content, "application/json")}
        response = authenticated_client.post("/import/file/", files=files)
        
        assert response.status_code == 200
        result = response.json()
        assert result["movies_created"] >= 1
        assert result["tv_shows_created"] >= 1
        assert "anime_created" in result
        assert "anime_updated" in result
        assert "video_games_created" in result
        assert "video_games_updated" in result
        assert result["video_games_created"] >= 1
    
    def test_import_from_file_invalid_format(self, authenticated_client):
        """Test importing from file with invalid format."""
        # Try to upload a non-JSON file
        files = {"file": ("test.txt", b"not json", "text/plain")}
        response = authenticated_client.post("/import/file/", files=files)
        
        assert response.status_code == 400
        assert "JSON file" in response.json()["detail"]
    
    def test_import_from_file_invalid_json(self, authenticated_client):
        """Test importing from file with invalid JSON."""
        # Try to upload invalid JSON
        files = {"file": ("test.json", b"{invalid json}", "application/json")}
        response = authenticated_client.post("/import/file/", files=files)
        
        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]
    
    def test_import_from_file_missing_fields(self, authenticated_client):
        """Test importing from file with missing required fields."""
        import json
        invalid_data = {"movies": []}  # Missing tv_shows (anime is optional for backward compatibility)
        file_content = json.dumps(invalid_data).encode('utf-8')
        
        files = {"file": ("test.json", file_content, "application/json")}
        response = authenticated_client.post("/import/file/", files=files)
        
        assert response.status_code in [400, 500]
        detail = response.json()["detail"]
        assert any(keyword in detail.lower() for keyword in ["movies", "tv_shows", "invalid", "format"])
    
    def test_import_from_file_backward_compatibility_no_anime(self, authenticated_client):
        """Test importing old export files without anime field (backward compatibility)."""
        import json
        old_format_data = {
            "movies": [
                {
                    "title": "Old Movie",
                    "director": "Old Director",
                    "year": 2020,
                    "rating": 8,
                    "watched": True
                }
            ],
            "tv_shows": [
                {
                    "title": "Old Show",
                    "year": 2021,
                    "seasons": 1,
                    "rating": 9
                }
            ]
        }
        
        file_content = json.dumps(old_format_data).encode('utf-8')
        files = {"file": ("old_export.json", file_content, "application/json")}
        response = authenticated_client.post("/import/file/", files=files)
        
        assert response.status_code == 200
        result = response.json()
        assert result["movies_created"] >= 1
        assert result["tv_shows_created"] >= 1
        assert result["anime_created"] == 0
        assert result["anime_updated"] == 0


class TestDataIsolation:
    """Test that users cannot access each other's data."""
    
    def test_users_cannot_see_each_others_movies(self, client, test_user_data, test_movie_data, db_session):
        """Test that users can only see their own movies."""
        from app import crud, models, schemas, auth
        
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password1 = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password1, "token1")
        
        user2_data = test_user_data.copy()
        user2_data["email"] = "user2@test.com"
        user2_data["username"] = "user2"
        user2_create = schemas.UserCreate(**user2_data)
        hashed_password2 = auth.get_password_hash(user2_data["password"])
        user2 = crud.create_user(db_session, user2_create, hashed_password2, "token2")
        
        user1.is_verified = True
        user2.is_verified = True
        db_session.commit()
        
        movie1_create = schemas.MovieCreate(**test_movie_data)
        crud.create_movie(db_session, user1.id, movie1_create)
        
        movie2_data = test_movie_data.copy()
        movie2_data["title"] = "User2 Movie"
        movie2_create = schemas.MovieCreate(**movie2_data)
        crud.create_movie(db_session, user2.id, movie2_create)
        
        login_response = client.post(
            "/auth/login",
            data={"username": "user2", "password": test_user_data["password"]},
            headers={"content-type": "application/x-www-form-urlencoded"}
        )
        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}
        
        movies_response = client.get("/movies/")
        assert movies_response.status_code == 200
        movies = movies_response.json()
        assert len(movies) == 1
        assert movies[0]["title"] == "User2 Movie"
    
    def test_users_cannot_update_each_others_movies(self, client, test_user_data, test_movie_data, db_session):
        """Test that users cannot update each other's movies."""
        from app import crud, models, schemas, auth
        
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password1 = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password1, "token1")
        
        user2_data = test_user_data.copy()
        user2_data["email"] = "user2@test.com"
        user2_data["username"] = "user2"
        user2_create = schemas.UserCreate(**user2_data)
        hashed_password2 = auth.get_password_hash(user2_data["password"])
        user2 = crud.create_user(db_session, user2_create, hashed_password2, "token2")
        
        user1.is_verified = True
        user2.is_verified = True
        db_session.commit()
        
        # Create movie for user1
        movie1_create = schemas.MovieCreate(**test_movie_data)
        created_movie = crud.create_movie(db_session, user1.id, movie1_create)
        movie_id = created_movie.id
        
        login_response = client.post(
            "/auth/login",
            data={"username": "user2", "password": test_user_data["password"]},
            headers={"content-type": "application/x-www-form-urlencoded"}
        )
        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}
        
        response = client.put(f"/movies/{movie_id}", json={"rating": 1})
        assert response.status_code == 404
    
    def test_users_cannot_delete_each_others_movies(self, client, test_user_data, test_movie_data, db_session):
        """Test that users cannot delete each other's movies."""
        from app import crud, models, schemas, auth
        
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password1 = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password1, "token1")
        
        user2_data = test_user_data.copy()
        user2_data["email"] = "user2@test.com"
        user2_data["username"] = "user2"
        user2_create = schemas.UserCreate(**user2_data)
        hashed_password2 = auth.get_password_hash(user2_data["password"])
        user2 = crud.create_user(db_session, user2_create, hashed_password2, "token2")
        
        user1.is_verified = True
        user2.is_verified = True
        db_session.commit()
        
        # Create movie for user1
        movie1_create = schemas.MovieCreate(**test_movie_data)
        created_movie = crud.create_movie(db_session, user1.id, movie1_create)
        movie_id = created_movie.id
        
        login_response = client.post(
            "/auth/login",
            data={"username": "user2", "password": test_user_data["password"]},
            headers={"content-type": "application/x-www-form-urlencoded"}
        )
        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}
        
        response = client.delete(f"/movies/{movie_id}")
        assert response.status_code == 404
    
    def test_users_cannot_see_each_others_tv_shows(self, client, test_user_data, test_tv_show_data, db_session):
        """Test that users can only see their own TV shows."""
        from app import crud, models, schemas, auth
        
        user1_create = schemas.UserCreate(**test_user_data)
        hashed_password1 = auth.get_password_hash(test_user_data["password"])
        user1 = crud.create_user(db_session, user1_create, hashed_password1, "token1")
        
        user2_data = test_user_data.copy()
        user2_data["email"] = "user2@test.com"
        user2_data["username"] = "user2"
        user2_create = schemas.UserCreate(**user2_data)
        hashed_password2 = auth.get_password_hash(user2_data["password"])
        user2 = crud.create_user(db_session, user2_create, hashed_password2, "token2")
        
        user1.is_verified = True
        user2.is_verified = True
        db_session.commit()
        
        tv1_create = schemas.TVShowCreate(**test_tv_show_data)
        crud.create_tv_show(db_session, user1.id, tv1_create)
        
        tv2_data = test_tv_show_data.copy()
        tv2_data["title"] = "User2 TV Show"
        tv2_create = schemas.TVShowCreate(**tv2_data)
        crud.create_tv_show(db_session, user2.id, tv2_create)
        
        login_response = client.post(
            "/auth/login",
            data={"username": "user2", "password": test_user_data["password"]},
            headers={"content-type": "application/x-www-form-urlencoded"}
        )
        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}
        
        tv_shows_response = client.get("/tv-shows/")
        assert tv_shows_response.status_code == 200
        tv_shows = tv_shows_response.json()
        assert len(tv_shows) == 1
        assert tv_shows[0]["title"] == "User2 TV Show"

