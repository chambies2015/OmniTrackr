"""
Tests for statistics endpoints.
"""
import pytest


class TestStatisticsEndpoints:
    """Test statistics API endpoints."""
    
    def test_get_statistics_dashboard(self, authenticated_client, test_movie_data, test_tv_show_data, test_anime_data, test_video_game_data):
        """Test getting comprehensive statistics dashboard."""
        # Create some data
        authenticated_client.post("/movies/", json=test_movie_data)
        authenticated_client.post("/tv-shows/", json=test_tv_show_data)
        authenticated_client.post("/anime/", json=test_anime_data)
        authenticated_client.post("/video-games/", json=test_video_game_data)
        
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
        assert "total_anime" in watch_stats
        assert "total_video_games" in watch_stats
        assert "watched_movies" in watch_stats
        assert "watched_tv_shows" in watch_stats
        assert "watched_anime" in watch_stats
        assert "played_video_games" in watch_stats
        
        # Check rating stats structure
        rating_stats = data["rating_stats"]
        assert "average_rating" in rating_stats
        assert "total_rated_items" in rating_stats
        assert "rating_distribution" in rating_stats
        
        # Check year stats structure
        year_stats = data["year_stats"]
        assert "movies_by_year" in year_stats
        assert "tv_shows_by_year" in year_stats
        assert "anime_by_year" in year_stats
        assert "video_games_by_year" in year_stats
        
        # Check director stats structure
        director_stats = data["director_stats"]
        assert "top_directors" in director_stats
        assert "highest_rated_directors" in director_stats
    
    def test_get_watch_statistics(self, authenticated_client, test_movie_data, test_tv_show_data, test_anime_data, test_video_game_data):
        """Test getting watch statistics."""
        # Create watched and unwatched items
        movie_data = test_movie_data.copy()
        movie_data["watched"] = True
        authenticated_client.post("/movies/", json=movie_data)
        
        tv_data = test_tv_show_data.copy()
        tv_data["watched"] = False
        authenticated_client.post("/tv-shows/", json=tv_data)
        
        anime_data = test_anime_data.copy()
        anime_data["watched"] = True
        authenticated_client.post("/anime/", json=anime_data)
        
        video_game_data = test_video_game_data.copy()
        video_game_data["played"] = True
        authenticated_client.post("/video-games/", json=video_game_data)
        
        # Get watch statistics
        response = authenticated_client.get("/statistics/watch/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_movies" in data
        assert "total_tv_shows" in data
        assert "total_anime" in data
        assert "total_video_games" in data
        assert "watched_movies" in data
        assert "watched_tv_shows" in data
        assert "watched_anime" in data
        assert "played_video_games" in data
        assert "unplayed_video_games" in data
        assert data["total_movies"] >= 1
        assert data["total_tv_shows"] >= 1
        assert data["total_anime"] >= 1
        assert data["total_video_games"] >= 1
    
    def test_get_rating_statistics(self, authenticated_client, test_movie_data, test_tv_show_data, test_anime_data, test_video_game_data):
        """Test getting rating statistics."""
        # Create items with ratings
        movie_data = test_movie_data.copy()
        movie_data["rating"] = 9
        authenticated_client.post("/movies/", json=movie_data)
        
        tv_data = test_tv_show_data.copy()
        tv_data["rating"] = 8
        authenticated_client.post("/tv-shows/", json=tv_data)
        
        anime_data = test_anime_data.copy()
        anime_data["rating"] = 9.5
        authenticated_client.post("/anime/", json=anime_data)
        
        video_game_data = test_video_game_data.copy()
        video_game_data["rating"] = 9.5
        authenticated_client.post("/video-games/", json=video_game_data)
        
        # Get rating statistics
        response = authenticated_client.get("/statistics/ratings/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "average_rating" in data
        assert "total_rated_items" in data
        assert "rating_distribution" in data
        assert "highest_rated" in data
        assert "lowest_rated" in data
        assert data["total_rated_items"] >= 4
        assert isinstance(data["average_rating"], (int, float))
    
    def test_get_year_statistics(self, authenticated_client, test_movie_data, test_tv_show_data, test_anime_data, test_video_game_data):
        """Test getting year-based statistics."""
        from datetime import datetime
        # Create items with specific years
        movie_data = test_movie_data.copy()
        movie_data["year"] = 1999
        authenticated_client.post("/movies/", json=movie_data)
        
        tv_data = test_tv_show_data.copy()
        tv_data["year"] = 2020
        authenticated_client.post("/tv-shows/", json=tv_data)
        
        anime_data = test_anime_data.copy()
        anime_data["year"] = 2013
        authenticated_client.post("/anime/", json=anime_data)
        
        video_game_data = test_video_game_data.copy()
        video_game_data["release_date"] = datetime(2017, 3, 3).isoformat()
        authenticated_client.post("/video-games/", json=video_game_data)
        
        # Get year statistics
        response = authenticated_client.get("/statistics/years/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "movies_by_year" in data
        assert "tv_shows_by_year" in data
        assert "anime_by_year" in data
        assert "video_games_by_year" in data
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
        assert data["watch_stats"]["total_anime"] == 0
        assert data["watch_stats"]["total_video_games"] == 0
    
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
    
    def test_get_movie_statistics(self, authenticated_client, test_movie_data):
        """Test getting movie-specific statistics."""
        # Create movies with various data
        movie1 = test_movie_data.copy()
        movie1["watched"] = True
        movie1["rating"] = 9.0
        movie1["year"] = 2020
        movie1["director"] = "Director A"
        authenticated_client.post("/movies/", json=movie1)
        
        movie2 = test_movie_data.copy()
        movie2["title"] = "Movie 2"
        movie2["watched"] = False
        movie2["rating"] = 8.5
        movie2["year"] = 2021
        movie2["director"] = "Director A"
        authenticated_client.post("/movies/", json=movie2)
        
        # Get movie statistics
        response = authenticated_client.get("/statistics/movies/")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "watch_stats" in data
        assert "rating_stats" in data
        assert "year_stats" in data
        assert "director_stats" in data
        
        # Check watch stats
        watch_stats = data["watch_stats"]
        assert watch_stats["total_items"] == 2
        assert watch_stats["watched_items"] == 1
        assert watch_stats["unwatched_items"] == 1
        assert watch_stats["completion_percentage"] == 50.0
        
        # Check rating stats
        rating_stats = data["rating_stats"]
        assert rating_stats["total_rated_items"] == 2
        assert abs(rating_stats["average_rating"] - 8.75) < 0.1
        assert "rating_distribution" in rating_stats
        assert len(rating_stats["highest_rated"]) > 0
        
        # Check year stats
        year_stats = data["year_stats"]
        assert "items_by_year" in year_stats
        assert year_stats["oldest_year"] == 2020
        assert year_stats["newest_year"] == 2021
        
        # Check director stats
        director_stats = data["director_stats"]
        assert "top_directors" in director_stats
        assert "highest_rated_directors" in director_stats
        top_directors = [d["director"] for d in director_stats["top_directors"]]
        assert "Director A" in top_directors
    
    def test_get_tv_show_statistics(self, authenticated_client, test_tv_show_data):
        """Test getting TV show-specific statistics."""
        # Create TV shows with seasons/episodes
        tv1 = test_tv_show_data.copy()
        tv1["watched"] = True
        tv1["rating"] = 9.0
        tv1["year"] = 2020
        tv1["seasons"] = 5
        tv1["episodes"] = 50
        authenticated_client.post("/tv-shows/", json=tv1)
        
        tv2 = test_tv_show_data.copy()
        tv2["title"] = "TV Show 2"
        tv2["watched"] = False
        tv2["rating"] = 8.0
        tv2["year"] = 2021
        tv2["seasons"] = 3
        tv2["episodes"] = 30
        authenticated_client.post("/tv-shows/", json=tv2)
        
        # Get TV show statistics
        response = authenticated_client.get("/statistics/tv-shows/")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "watch_stats" in data
        assert "rating_stats" in data
        assert "year_stats" in data
        assert "seasons_episodes_stats" in data
        
        # Check watch stats
        watch_stats = data["watch_stats"]
        assert watch_stats["total_items"] == 2
        assert watch_stats["watched_items"] == 1
        assert watch_stats["unwatched_items"] == 1
        
        # Check seasons/episodes stats
        seasons_episodes = data["seasons_episodes_stats"]
        assert seasons_episodes["total_seasons"] == 8
        assert seasons_episodes["total_episodes"] == 80
        assert seasons_episodes["average_seasons"] == 4.0
        assert seasons_episodes["average_episodes"] == 40.0
        assert len(seasons_episodes["shows_with_most_seasons"]) > 0
        assert len(seasons_episodes["shows_with_most_episodes"]) > 0
    
    def test_get_anime_statistics(self, authenticated_client, test_anime_data):
        """Test getting anime-specific statistics."""
        # Create anime with seasons/episodes
        anime1 = test_anime_data.copy()
        anime1["watched"] = True
        anime1["rating"] = 9.5
        anime1["year"] = 2020
        anime1["seasons"] = 2
        anime1["episodes"] = 24
        authenticated_client.post("/anime/", json=anime1)
        
        anime2 = test_anime_data.copy()
        anime2["title"] = "Anime 2"
        anime2["watched"] = False
        anime2["rating"] = 8.5
        anime2["year"] = 2021
        anime2["seasons"] = 1
        anime2["episodes"] = 12
        authenticated_client.post("/anime/", json=anime2)
        
        # Get anime statistics
        response = authenticated_client.get("/statistics/anime/")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "watch_stats" in data
        assert "rating_stats" in data
        assert "year_stats" in data
        assert "seasons_episodes_stats" in data
        
        # Check seasons/episodes stats
        seasons_episodes = data["seasons_episodes_stats"]
        assert seasons_episodes["total_seasons"] == 3
        assert seasons_episodes["total_episodes"] == 36
        assert seasons_episodes["average_seasons"] == 1.5
        assert seasons_episodes["average_episodes"] == 18.0
    
    def test_get_video_game_statistics(self, authenticated_client, test_video_game_data):
        """Test getting video game-specific statistics."""
        from datetime import datetime
        
        # Create video games with genres
        game1 = test_video_game_data.copy()
        game1["played"] = True
        game1["rating"] = 9.0
        game1["release_date"] = datetime(2020, 1, 1).isoformat()
        game1["genres"] = "Action, Adventure"
        authenticated_client.post("/video-games/", json=game1)
        
        game2 = test_video_game_data.copy()
        game2["title"] = "Game 2"
        game2["played"] = False
        game2["rating"] = 8.0
        game2["release_date"] = datetime(2021, 1, 1).isoformat()
        game2["genres"] = "Action, RPG"
        authenticated_client.post("/video-games/", json=game2)
        
        # Get video game statistics
        response = authenticated_client.get("/statistics/video-games/")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "watch_stats" in data
        assert "rating_stats" in data
        assert "year_stats" in data
        assert "genre_stats" in data
        
        # Check watch stats (should use "played" terminology)
        watch_stats = data["watch_stats"]
        assert watch_stats["total_items"] == 2
        assert watch_stats["watched_items"] == 1
        assert watch_stats["unwatched_items"] == 1
        
        # Check genre stats
        genre_stats = data["genre_stats"]
        assert "genre_distribution" in genre_stats
        assert "top_genres" in genre_stats
        assert "most_played_genres" in genre_stats
        assert len(genre_stats["top_genres"]) > 0
        # Action should appear in top genres (appears in both games)
        top_genres = [g["genre"] for g in genre_stats["top_genres"]]
        assert "Action" in top_genres
    
    def test_category_statistics_empty_data(self, authenticated_client):
        """Test category statistics endpoints with no data."""
        categories = ["movies", "tv-shows", "anime", "video-games"]
        
        for category in categories:
            response = authenticated_client.get(f"/statistics/{category}/")
            
            assert response.status_code == 200
            data = response.json()
            
            # Should still return valid structure
            assert "watch_stats" in data
            assert "rating_stats" in data
            assert "year_stats" in data
            
            # Watch stats should show zeros
            assert data["watch_stats"]["total_items"] == 0
            assert data["watch_stats"]["watched_items"] == 0
            assert data["watch_stats"]["unwatched_items"] == 0
            assert data["watch_stats"]["completion_percentage"] == 0.0
            
            # Rating stats should handle empty data
            assert data["rating_stats"]["total_rated_items"] == 0
            assert data["rating_stats"]["average_rating"] == 0
    
    def test_category_statistics_requires_auth(self, client):
        """Test that category statistics endpoints require authentication."""
        endpoints = [
            "/statistics/movies/",
            "/statistics/tv-shows/",
            "/statistics/anime/",
            "/statistics/video-games/"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401, f"{endpoint} should require auth"
    
    def test_category_statistics_data_isolation(self, client, test_user_data, test_movie_data, db_session):
        """Test that category statistics are isolated per user."""
        from app import crud, models, schemas, auth
        
        # Create two users
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
        
        # Get movie statistics for user2
        stats_response = client.get("/statistics/movies/")
        assert stats_response.status_code == 200
        
        # User2 should only see their own movie
        watch_stats = stats_response.json()["watch_stats"]
        assert watch_stats["total_items"] == 1
    
    def test_movie_statistics_director_analysis(self, authenticated_client, test_movie_data):
        """Test that movie statistics include director analysis."""
        # Create multiple movies with same director
        for i in range(3):
            movie = test_movie_data.copy()
            movie["title"] = f"Movie {i+1}"
            movie["director"] = "Test Director"
            movie["rating"] = 8.0 + i
            authenticated_client.post("/movies/", json=movie)
        
        response = authenticated_client.get("/statistics/movies/")
        assert response.status_code == 200
        
        data = response.json()
        director_stats = data["director_stats"]
        
        # Should have top directors
        assert len(director_stats["top_directors"]) > 0
        top_directors = [d["director"] for d in director_stats["top_directors"]]
        assert "Test Director" in top_directors
        
        # Should have highest rated directors
        assert len(director_stats["highest_rated_directors"]) > 0
    
    def test_tv_show_statistics_seasons_episodes(self, authenticated_client, test_tv_show_data):
        """Test that TV show statistics include seasons/episodes analysis."""
        # Create TV shows with different seasons/episodes
        tv1 = test_tv_show_data.copy()
        tv1["seasons"] = 10
        tv1["episodes"] = 100
        authenticated_client.post("/tv-shows/", json=tv1)
        
        tv2 = test_tv_show_data.copy()
        tv2["title"] = "TV Show 2"
        tv2["seasons"] = 5
        tv2["episodes"] = 50
        authenticated_client.post("/tv-shows/", json=tv2)
        
        response = authenticated_client.get("/statistics/tv-shows/")
        assert response.status_code == 200
        
        data = response.json()
        seasons_episodes = data["seasons_episodes_stats"]
        
        # Check totals
        assert seasons_episodes["total_seasons"] == 15
        assert seasons_episodes["total_episodes"] == 150
        
        # Check shows with most seasons/episodes
        most_seasons = seasons_episodes["shows_with_most_seasons"]
        assert len(most_seasons) > 0
        assert most_seasons[0]["seasons"] == 10
        
        most_episodes = seasons_episodes["shows_with_most_episodes"]
        assert len(most_episodes) > 0
        assert most_episodes[0]["episodes"] == 100
    
    def test_video_game_statistics_genres(self, authenticated_client, test_video_game_data):
        """Test that video game statistics include genre analysis."""
        from datetime import datetime
        
        # Create games with various genres
        game1 = test_video_game_data.copy()
        game1["genres"] = "Action, Adventure"
        game1["played"] = True
        authenticated_client.post("/video-games/", json=game1)
        
        game2 = test_video_game_data.copy()
        game2["title"] = "Game 2"
        game2["genres"] = "Action, RPG"
        game2["played"] = True
        authenticated_client.post("/video-games/", json=game2)
        
        game3 = test_video_game_data.copy()
        game3["title"] = "Game 3"
        game3["genres"] = "Adventure"
        game3["played"] = False
        authenticated_client.post("/video-games/", json=game3)
        
        response = authenticated_client.get("/statistics/video-games/")
        assert response.status_code == 200
        
        data = response.json()
        genre_stats = data["genre_stats"]
        
        # Check genre distribution
        assert "Action" in genre_stats["genre_distribution"]
        assert genre_stats["genre_distribution"]["Action"] == 2
        assert genre_stats["genre_distribution"]["Adventure"] == 2
        assert genre_stats["genre_distribution"]["RPG"] == 1
        
        # Check top genres
        assert len(genre_stats["top_genres"]) > 0
        top_genres = [g["genre"] for g in genre_stats["top_genres"]]
        assert "Action" in top_genres
        
        # Check most played genres (only played games)
        assert len(genre_stats["most_played_genres"]) > 0
        most_played = [g["genre"] for g in genre_stats["most_played_genres"]]
        assert "Action" in most_played
        # Adventure should be in most played (appears in game1 which is played)
        assert "Adventure" in most_played

