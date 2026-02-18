"""
Tests for public review endpoints.
"""
import pytest
from datetime import datetime
from app import models, crud
from app.schemas import MovieCreate, TVShowCreate, AnimeCreate, VideoGameCreate, MusicCreate, BookCreate


class TestPublicReviews:
    """Test public review API endpoints."""
    
    def test_get_public_reviews_empty(self, client, db_session):
        """Test getting public reviews when none exist."""
        response = client.get("/api/public/reviews")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_get_public_reviews_with_movie_review(self, client, db_session, authenticated_client, test_user_data):
        """Test getting public reviews includes movie reviews."""
        from app import crud
        
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        assert user is not None
        user.reviews_public = True
        db_session.commit()
        
        movie_data = {
            "title": "Test Movie",
            "director": "Test Director",
            "year": 2020,
            "rating": 8.5,
            "review": "This is a detailed review of the movie with substantial content.",
            "review_public": True,
        }
        
        movie = crud.create_movie(db_session, user.id, MovieCreate(**movie_data))
        db_session.commit()
        
        response = client.get("/api/public/reviews")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        movie_review = next((r for r in data if r["category"] == "movie" and r["id"] == movie.id), None)
        assert movie_review is not None
        assert movie_review["title"] == movie_data["title"]
        assert movie_review["review"] == movie_data["review"]
        assert movie_review["rating"] == 8.5
        assert movie_review["director"] == movie_data["director"]
        assert movie_review["year"] == movie_data["year"]
        assert "username" in movie_review
        assert "user_id" in movie_review
    
    def test_get_public_reviews_excludes_empty_reviews(self, client, db_session, authenticated_client, test_user_data):
        """Test that reviews without text are not included."""
        from app import crud
        
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        user.reviews_public = True
        db_session.commit()
        
        movie_with_review = crud.create_movie(
            db_session, 
            user.id, 
            MovieCreate(
                title="Movie With Review",
                director="Director",
                year=2020,
                review="This has a review",
                review_public=True
            )
        )
        
        movie_without_review = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Movie Without Review",
                director="Director",
                year=2020,
                review=None,
                review_public=True
            )
        )
        
        movie_with_empty_review = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Movie With Empty Review",
                director="Director",
                year=2020,
                review="",
                review_public=True
            )
        )
        
        db_session.commit()
        
        response = client.get("/api/public/reviews")
        
        assert response.status_code == 200
        data = response.json()
        review_ids = [r["id"] for r in data]
        assert movie_with_review.id in review_ids
        assert movie_without_review.id not in review_ids
        assert movie_with_empty_review.id not in review_ids
    
    def test_get_public_reviews_excludes_inactive_users(self, client, db_session, test_user_data):
        """Test that reviews from inactive users are not included."""
        from app import crud
        
        active_user = models.User(
            email="active@example.com",
            username="activeuser",
            hashed_password="hashed",
            is_active=True,
            is_verified=True,
            reviews_public=True
        )
        db_session.add(active_user)
        
        inactive_user = models.User(
            email="inactive@example.com",
            username="inactiveuser",
            hashed_password="hashed",
            is_active=False,
            is_verified=True,
            reviews_public=True
        )
        db_session.add(inactive_user)
        db_session.commit()
        
        active_movie = crud.create_movie(
            db_session,
            active_user.id,
            MovieCreate(
                title="Active User Movie",
                director="Director",
                year=2020,
                review="Review from active user",
                review_public=True
            )
        )
        
        inactive_movie = crud.create_movie(
            db_session,
            inactive_user.id,
            MovieCreate(
                title="Inactive User Movie",
                director="Director",
                year=2020,
                review="Review from inactive user",
                review_public=True
            )
        )
        
        db_session.commit()
        
        response = client.get("/api/public/reviews")
        
        assert response.status_code == 200
        data = response.json()
        review_ids = [r["id"] for r in data]
        assert active_movie.id in review_ids
        assert inactive_movie.id not in review_ids
    
    def test_get_public_reviews_excludes_entries_not_marked_public(self, client, db_session, authenticated_client, test_user_data):
        """Test that entries not marked as public are not included."""
        from app import crud
        
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        user.reviews_public = False
        db_session.commit()
        
        movie = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Private Review Movie",
                director="Director",
                year=2020,
                review="This review should not appear publicly",
                review_public=False
            )
        )
        
        db_session.commit()
        
        response = client.get("/api/public/reviews")
        
        assert response.status_code == 200
        data = response.json()
        review_ids = [r["id"] for r in data]
        assert movie.id not in review_ids
    
    def test_get_public_reviews_includes_entries_marked_public(self, client, db_session, authenticated_client, test_user_data):
        """Test that entries marked as public are included."""
        from app import crud
        
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        user.reviews_public = True
        db_session.commit()
        
        movie = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Public Review Movie",
                director="Director",
                year=2020,
                review="This review should appear publicly",
                review_public=True
            )
        )
        
        db_session.commit()
        
        response = client.get("/api/public/reviews")
        
        assert response.status_code == 200
        data = response.json()
        review_ids = [r["id"] for r in data]
        assert movie.id in review_ids
    
    def test_get_public_reviews_filter_by_category_movie(self, client, db_session, authenticated_client, test_user_data):
        """Test filtering public reviews by movie category."""
        from app import crud
        
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        user.reviews_public = True
        db_session.commit()
        
        movie = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Test Movie Filter Unique",
                director="Director",
                year=2020,
                review="Movie review for filter test unique",
                review_public=True
            )
        )
        
        tv_show = crud.create_tv_show(
            db_session,
            user.id,
            TVShowCreate(
                title="Test TV Show Filter Unique",
                year=2020,
                review="TV show review for filter test unique",
                review_public=True
            )
        )
        
        db_session.commit()
        db_session.refresh(movie)
        db_session.refresh(tv_show)
        
        response = client.get("/api/public/reviews?category=movie&limit=100")
        
        assert response.status_code == 200
        data = response.json()
        
        movie_ids = [r["id"] for r in data if r["category"] == "movie"]
        tv_show_ids = [r["id"] for r in data if r["category"] == "tv_show"]
        
        assert movie.id in movie_ids, f"Created movie (id={movie.id}) should be in results. Got movie IDs: {movie_ids}"
        assert tv_show.id not in tv_show_ids, f"TV show (id={tv_show.id}) should not appear when filtering by movie. Got TV show IDs: {tv_show_ids}"
        assert len(tv_show_ids) == 0, f"No TV shows should appear when filtering by movie category. Found: {tv_show_ids}"
        assert all(r["category"] == "movie" for r in data), f"All results should be movies, but found categories: {set(r['category'] for r in data)}"
    
    def test_get_public_reviews_filter_by_category_tv_show(self, client, db_session, authenticated_client, test_user_data):
        """Test filtering public reviews by TV show category."""
        from app import crud
        
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        user.reviews_public = True
        db_session.commit()
        
        tv_show = crud.create_tv_show(
            db_session,
            user.id,
            TVShowCreate(
                title="Test TV Show",
                year=2020,
                review="TV show review",
                review_public=True
            )
        )
        
        response = client.get("/api/public/reviews?category=tv_show")
        
        assert response.status_code == 200
        data = response.json()
        assert all(r["category"] == "tv_show" for r in data)
        assert any(r["id"] == tv_show.id for r in data)
    
    def test_get_public_reviews_filter_by_category_anime(self, client, db_session, authenticated_client, test_user_data):
        """Test filtering public reviews by anime category."""
        from app import crud
        
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        user.reviews_public = True
        db_session.commit()
        
        anime = crud.create_anime(
            db_session,
            user.id,
            AnimeCreate(
                title="Test Anime",
                year=2020,
                review="Anime review",
                review_public=True
            )
        )
        
        response = client.get("/api/public/reviews?category=anime")
        
        assert response.status_code == 200
        data = response.json()
        assert all(r["category"] == "anime" for r in data)
        assert any(r["id"] == anime.id for r in data)
    
    def test_get_public_reviews_filter_by_category_video_game(self, client, db_session, authenticated_client, test_user_data):
        """Test filtering public reviews by video game category."""
        from app import crud
        
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        user.reviews_public = True
        db_session.commit()
        
        video_game = crud.create_video_game(
            db_session,
            user.id,
            VideoGameCreate(
                title="Test Game",
                release_date=datetime(2020, 1, 1),
                genres="Action, Adventure",
                review="Game review",
                review_public=True
            )
        )
        
        response = client.get("/api/public/reviews?category=video_game")
        
        assert response.status_code == 200
        data = response.json()
        assert all(r["category"] == "video_game" for r in data)
        assert any(r["id"] == video_game.id for r in data)
    
    def test_get_public_reviews_pagination(self, client, db_session, authenticated_client, test_user_data):
        """Test pagination with limit and offset."""
        from app import crud
        
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        user.reviews_public = True
        db_session.commit()
        
        for i in range(5):
            crud.create_movie(
                db_session,
                user.id,
                MovieCreate(
                    title=f"Movie {i}",
                    director="Director",
                    year=2020,
                    review=f"Review {i}",
                    review_public=True
                )
            )
        
        db_session.commit()
        
        response1 = client.get("/api/public/reviews?limit=2&offset=0")
        assert response1.status_code == 200
        data1 = response1.json()
        assert len(data1) <= 2
        
        response2 = client.get("/api/public/reviews?limit=2&offset=2")
        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2) <= 2
        
        if len(data1) == 2 and len(data2) == 2:
            assert data1[0]["id"] != data2[0]["id"]
    
    def test_get_public_reviews_limit_validation(self, client):
        """Test that limit parameter is validated."""
        response = client.get("/api/public/reviews?limit=0")
        assert response.status_code == 422
        
        response = client.get("/api/public/reviews?limit=101")
        assert response.status_code == 422
    
    def test_get_public_review_by_id_movie(self, client, db_session, authenticated_client, test_user_data):
        """Test getting a specific public review by ID for a movie."""
        from app import crud
        
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        user.reviews_public = True
        db_session.commit()
        
        movie = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Specific Movie",
                director="Director",
                year=2020,
                rating=9.0,
                review="This is a specific movie review",
                review_public=True
            )
        )
        
        db_session.commit()
        
        response = client.get(f"/api/public/reviews/{movie.id}?category=movie")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == movie.id
        assert data["category"] == "movie"
        assert data["title"] == "Specific Movie"
        assert data["review"] == "This is a specific movie review"
        assert data["rating"] == 9.0
        assert data["director"] == "Director"
        assert data["year"] == 2020
        assert "username" in data
        assert "user_id" in data
    
    def test_get_public_review_by_id_tv_show(self, client, db_session, authenticated_client, test_user_data):
        """Test getting a specific public review by ID for a TV show."""
        from app import crud
        
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        user.reviews_public = True
        db_session.commit()
        
        tv_show = crud.create_tv_show(
            db_session,
            user.id,
            TVShowCreate(
                title="Specific TV Show",
                year=2020,
                seasons=3,
                episodes=30,
                review="This is a specific TV show review",
                review_public=True
            )
        )
        
        db_session.commit()
        
        response = client.get(f"/api/public/reviews/{tv_show.id}?category=tv_show")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == tv_show.id
        assert data["category"] == "tv_show"
        assert data["title"] == "Specific TV Show"
        assert data["review"] == "This is a specific TV show review"
        assert "seasons" in data
        assert "episodes" in data
    
    def test_get_public_review_by_id_not_found(self, client):
        """Test getting a non-existent review returns 404."""
        response = client.get("/api/public/reviews/99999?category=movie")
        assert response.status_code == 404
    
    def test_get_public_review_by_id_invalid_category(self, client):
        """Test getting a review with invalid category returns 400."""
        response = client.get("/api/public/reviews/1?category=invalid")
        assert response.status_code == 400
    
    def test_get_public_review_by_id_missing_category(self, client):
        """Test getting a review without category parameter returns 422."""
        response = client.get("/api/public/reviews/1")
        assert response.status_code == 422
    
    def test_get_public_review_excludes_empty_review(self, client, db_session, authenticated_client, test_user_data):
        """Test that getting a review without text returns 404."""
        from app import crud
        
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        user.reviews_public = True
        db_session.commit()
        
        movie = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="No Review Movie",
                director="Director",
                year=2020,
                review=None,
                review_public=True
            )
        )
        
        db_session.commit()
        
        response = client.get(f"/api/public/reviews/{movie.id}?category=movie")
        assert response.status_code == 404
    
    def test_get_public_review_long_text(self, client, db_session, authenticated_client, test_user_data):
        """Test that reviews with long text (Text field) work correctly."""
        from app import crud
        
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        user.reviews_public = True
        db_session.commit()
        
        long_review = "This is a very long review. " * 100
        movie = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Long Review Movie",
                director="Director",
                year=2020,
                review=long_review,
                review_public=True
            )
        )
        
        db_session.commit()
        
        response = client.get(f"/api/public/reviews/{movie.id}?category=movie")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["review"]) == len(long_review)
        assert data["review"] == long_review
    
    def test_get_public_reviews_mixed_categories(self, client, db_session, authenticated_client, test_user_data):
        """Test getting reviews from all categories when no filter is applied."""
        from app import crud
        
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        user.reviews_public = True
        db_session.commit()
        
        movie = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(title="Movie", director="D", year=2020, review="Movie review", review_public=True)
        )
        
        tv_show = crud.create_tv_show(
            db_session,
            user.id,
            TVShowCreate(title="TV Show", year=2020, review="TV review", review_public=True)
        )
        
        anime = crud.create_anime(
            db_session,
            user.id,
            AnimeCreate(title="Anime", year=2020, review="Anime review", review_public=True)
        )
        
        video_game = crud.create_video_game(
            db_session,
            user.id,
            VideoGameCreate(
                title="Game",
                release_date=datetime(2020, 1, 1),
                genres="Action",
                review="Game review",
                review_public=True
            )
        )
        
        db_session.commit()
        
        response = client.get("/api/public/reviews")
        
        assert response.status_code == 200
        data = response.json()
        categories = {r["category"] for r in data}
        assert "movie" in categories or any(r["id"] == movie.id for r in data)
        assert "tv_show" in categories or any(r["id"] == tv_show.id for r in data)
        assert "anime" in categories or any(r["id"] == anime.id for r in data)
        assert "video_game" in categories or any(r["id"] == video_game.id for r in data)

    def test_get_public_reviews_all_categories_includes_newest_movie_reviews(self, client, db_session, authenticated_client, test_user_data):
        """All categories should include newest public movie reviews."""
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        newest_movie = None
        for i in range(8):
            newest_movie = crud.create_movie(
                db_session,
                user.id,
                MovieCreate(
                    title=f"Newest Inclusion Movie {i}",
                    director="Director",
                    year=2020,
                    review=f"Review {i}",
                    review_public=True,
                )
            )
        db_session.commit()

        response = client.get("/api/public/reviews?limit=20&offset=0")
        assert response.status_code == 200
        data = response.json()
        movie_ids = [r["id"] for r in data if r["category"] == "movie"]
        assert newest_movie is not None
        assert newest_movie.id in movie_ids

    def test_get_public_reviews_filter_by_category_music(self, client, db_session, authenticated_client, test_user_data):
        """Test filtering public reviews by music category."""
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()

        music = crud.create_music(
            db_session,
            user.id,
            MusicCreate(
                title="Test Album",
                artist="Artist",
                year=2020,
                review="Music review",
                review_public=True,
            )
        )
        db_session.commit()

        response = client.get("/api/public/reviews?category=music")
        assert response.status_code == 200
        data = response.json()
        assert all(r["category"] == "music" for r in data)
        assert any(r["id"] == music.id for r in data)

    def test_get_public_reviews_filter_by_category_book(self, client, db_session, authenticated_client, test_user_data):
        """Test filtering public reviews by book category."""
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()

        book = crud.create_book(
            db_session,
            user.id,
            BookCreate(
                title="Test Book",
                author="Author",
                year=2020,
                review="Book review",
                review_public=True,
            )
        )
        db_session.commit()

        response = client.get("/api/public/reviews?category=book")
        assert response.status_code == 200
        data = response.json()
        assert all(r["category"] == "book" for r in data)
        assert any(r["id"] == book.id for r in data)

    def test_get_public_reviews_ignores_profile_reviews_public_flag(self, client, db_session, authenticated_client, test_user_data):
        """Test that per-entry public flag controls visibility, not profile-level reviews_public."""
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        user.reviews_public = True
        db_session.commit()

        private_entry = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Legacy Public User Private Entry",
                director="Director",
                year=2020,
                review="Should not be public",
                review_public=False,
            )
        )
        public_entry = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Legacy Public User Public Entry",
                director="Director",
                year=2020,
                review="Should be public",
                review_public=True,
            )
        )
        db_session.commit()

        response = client.get("/api/public/reviews?category=movie&limit=100")
        assert response.status_code == 200
        ids = [r["id"] for r in response.json()]
        assert public_entry.id in ids
        assert private_entry.id not in ids
    
    def test_reviews_page_accessible(self, client):
        """Test that the reviews index page is accessible."""
        response = client.get("/reviews")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    
    def test_review_detail_page_accessible(self, client):
        """Test that the review detail page is accessible."""
        response = client.get("/reviews/1")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
