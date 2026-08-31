"""
Tests for public review endpoints.
"""
import json
import re
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
            "review": (
                "This is a detailed review of the movie with substantial content, "
                "including pacing, audience fit, and why the rating is useful."
            ),
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

    def test_get_public_reviews_min_chars_filters_short_notes(self, client, db_session, authenticated_client, test_user_data):
        """Public review feeds can request substantial reviews for crawlable pages."""
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        assert user is not None
        user.reviews_public = True
        db_session.commit()

        short_movie = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Short Public Note",
                director="Director",
                year=2026,
                review="Good movie.",
                review_public=True,
            ),
        )
        substantial_movie = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Substantial Public Review",
                director="Director",
                year=2026,
                review=(
                    "This public review gives enough context about pacing, tone, "
                    "audience fit, and rewatch value to be useful for another reader."
                ),
                review_public=True,
            ),
        )
        db_session.commit()

        default_response = client.get("/api/public/reviews?category=movie&limit=100")
        legacy_response = client.get("/api/public/reviews?category=movie&limit=100&min_chars=1")
        quality_response = client.get("/api/public/reviews?category=movie&limit=100&min_chars=80")

        assert default_response.status_code == 200
        assert legacy_response.status_code == 200
        assert quality_response.status_code == 200
        default_ids = [review["id"] for review in default_response.json()]
        legacy_ids = [review["id"] for review in legacy_response.json()]
        quality_ids = [review["id"] for review in quality_response.json()]
        assert short_movie.id not in default_ids
        assert substantial_movie.id in default_ids
        assert short_movie.id in legacy_ids
        assert substantial_movie.id in legacy_ids
        assert short_movie.id not in quality_ids
        assert substantial_movie.id in quality_ids

    def test_public_reviews_exclude_promotional_or_contact_text(self, client, db_session, authenticated_client, test_user_data):
        """Public discovery should filter obvious promotional UGC without deleting saved reviews."""
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        assert user is not None
        user.reviews_public = True
        db_session.commit()

        spammy_movie = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Promotional Review Movie",
                director="Spam Director",
                year=2026,
                review=(
                    "This review has enough words to pass a length check, but it tells readers to visit "
                    "https://spam.example for a free download and contact me at spam@example.com instead "
                    "of offering useful media criticism or personal context."
                ),
                review_public=True,
            ),
        )
        safe_movie = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Safe Public Review Movie",
                director="Safe Director",
                year=2026,
                review=(
                    "This public review explains the movie's pacing, tone, audience fit, strongest scene, "
                    "and why the rating would help another visitor decide whether to add it to a watchlist."
                ),
                review_public=True,
            ),
        )
        db_session.commit()

        api_response = client.get("/api/public/reviews?category=movie&limit=100&min_chars=1")
        category_response = client.get("/reviews?category=movie")
        spam_detail_response = client.get(f"/reviews/{spammy_movie.id}?category=movie")

        assert api_response.status_code == 200
        ids = [review["id"] for review in api_response.json()]
        assert spammy_movie.id not in ids
        assert safe_movie.id in ids
        assert db_session.query(models.Movie).filter(models.Movie.id == spammy_movie.id).first() is not None
        assert "Promotional Review Movie" not in category_response.text
        assert "Safe Public Review Movie" in category_response.text
        assert spam_detail_response.status_code == 404
        assert '<meta name="robots" content="noindex, follow">' in spam_detail_response.text

    def test_reviews_index_renders_clean_server_metadata(self, client, db_session, authenticated_client, test_user_data):
        """Server-rendered public review cards should avoid mojibake separators."""
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        assert user is not None
        user.reviews_public = True
        db_session.commit()

        movie = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Server Rendered Review",
                director="Clean Director",
                year=2026,
                rating=9,
                review=(
                    "This review has enough detail for the server-rendered public review index to include it as "
                    "useful public content for visitors. It explains why the rating is high, what kind of pacing and "
                    "tone the movie offers, who would probably enjoy it, and why the recommendation still makes sense "
                    "outside the private library. That makes it suitable for a standalone detail page too."
                ),
                review_public=True,
            ),
        )
        db_session.commit()

        response = client.get("/reviews")

        assert response.status_code == 200
        assert f"/reviews/{movie.id}?category=movie" in response.text
        assert "Clean Director - 2026" in response.text
        assert "\u00c2\u00b7" not in response.text
    
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
        
        response = client.get("/api/public/reviews?min_chars=1")
        
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
        
        response = client.get("/api/public/reviews?min_chars=1")
        
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
        
        response = client.get("/api/public/reviews?min_chars=1")
        
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
        
        response = client.get("/api/public/reviews?min_chars=1")
        
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
        
        response = client.get("/api/public/reviews?category=movie&limit=100&min_chars=1")
        
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
        
        response = client.get("/api/public/reviews?category=tv_show&min_chars=1")
        
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
        
        response = client.get("/api/public/reviews?category=anime&min_chars=1")
        
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
        
        response = client.get("/api/public/reviews?category=video_game&min_chars=1")
        
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
        
        response1 = client.get("/api/public/reviews?limit=2&offset=0&min_chars=1")
        assert response1.status_code == 200
        data1 = response1.json()
        assert len(data1) <= 2
        
        response2 = client.get("/api/public/reviews?limit=2&offset=2&min_chars=1")
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
        
        response = client.get("/api/public/reviews?min_chars=1")
        
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

        response = client.get("/api/public/reviews?limit=20&offset=0&min_chars=1")
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

        response = client.get("/api/public/reviews?category=music&min_chars=1")
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

        response = client.get("/api/public/reviews?category=book&min_chars=1")
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

        response = client.get("/api/public/reviews?category=movie&limit=100&min_chars=1")
        assert response.status_code == 200
        ids = [r["id"] for r in response.json()]
        assert public_entry.id in ids
        assert private_entry.id not in ids
    
    def test_reviews_page_accessible(self, client):
        """Test that the reviews index page is accessible."""
        response = client.get("/reviews")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "What Makes These Reviews Useful?" in response.text
        assert "How to Browse Public Reviews" in response.text
        assert "Editorial Review Examples" in response.text
        assert "Review Writing Tips" in response.text
        assert "first-party guidance, not user submissions" in response.text
        assert "Movie example" in response.text
        assert "Game example" in response.text
        assert "Book, album, or show example" in response.text
        assert 'href="/review-guidelines"' in response.text
        assert 'href="/media-tracker-checklist"' in response.text
        assert "Generic review helper links without a category are intentionally not indexed" in response.text
        assert "Public review quality also protects the site experience" in response.text
        assert 'href="/reviews?category=movie"' in response.text
        assert 'href="/reviews?category=video_game"' in response.text

    def test_empty_review_category_page_is_noindexed_and_ad_free(self, client):
        """Empty user-generated category pages should not look like ad inventory."""
        response = client.get("/reviews?category=music")

        assert response.status_code == 200
        assert "<title>Music Reviews - OmniTrackr</title>" in response.text
        assert '<meta name="robots" content="noindex, follow">' in response.text
        assert "/static/ad-loader.js" not in response.text
        assert "Community reviews are being curated" in response.text

    def test_invalid_review_category_page_is_noindexed_404(self, client):
        """Unsupported category queries should not duplicate the indexable reviews page."""
        response = client.get("/reviews?category=unknown")

        assert response.status_code == 404
        assert '<meta name="robots" content="noindex, follow">' in response.text
        assert "Review category not found" in response.text

    def test_reviews_category_page_renders_crawlable_server_content(self, client, db_session, authenticated_client, test_user_data):
        """Category review views should be crawlable without relying on client-side filtering."""
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        assert user is not None
        user.reviews_public = True
        db_session.commit()

        movie = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Crawlable Category Movie",
                director="Category Director",
                year=2026,
                rating=8,
                review=(
                    "This category-specific review has enough detail to appear in server-rendered movie review "
                    "inventory for search and AdSense review. It explains pacing, tone, audience fit, the reason "
                    "behind the rating, and whether another visitor should add it to a watchlist. Because it is long "
                    "enough to stand alone, the category page can safely link to a dedicated review detail URL."
                ),
                review_public=True,
            ),
        )
        book = crud.create_book(
            db_session,
            user.id,
            BookCreate(
                title="Hidden From Movie Category",
                author="Category Author",
                year=2025,
                rating=7,
                review=(
                    "This book review is also substantial, but it should not render "
                    "inside the movie category review page."
                ),
                review_public=True,
            ),
        )
        db_session.commit()

        response = client.get("/reviews?category=movie")

        assert response.status_code == 200
        assert "<title>Movie Reviews - OmniTrackr</title>" in response.text
        assert '<link rel="canonical" href="https://omnitrackr.xyz/reviews?category=movie">' in response.text
        assert '<meta name="robots" content="index, follow, max-image-preview:large">' in response.text
        assert "<h1>Movie Reviews</h1>" in response.text
        assert '<option value="movie" selected>' in response.text
        assert f"/reviews/{movie.id}?category=movie" in response.text
        assert "Crawlable Category Movie" in response.text
        assert "Category Director - 2026" in response.text
        assert f"/reviews/{book.id}?category=book" not in response.text
        assert "Hidden From Movie Category" not in response.text
        match = re.search(
            r'<script type="application/ld\+json" id="server-review-item-list"[^>]*>(.*?)</script>',
            response.text,
        )
        assert match is not None
        structured_data = json.loads(match.group(1))
        assert structured_data["@type"] == "CollectionPage"
        assert structured_data["name"] == "Movie Reviews - OmniTrackr"
        assert structured_data["url"] == "https://omnitrackr.xyz/reviews?category=movie"
        assert structured_data["dateModified"] == datetime.utcnow().strftime("%Y-%m-%d")
        assert structured_data["mainEntity"]["numberOfItems"] == 1
        items = structured_data["mainEntity"]["itemListElement"]
        assert items[0]["item"]["name"] == "Crawlable Category Movie Movie Review"
        assert items[0]["item"]["itemReviewed"]["@type"] == "Movie"
        assert items[0]["item"]["itemReviewed"]["director"]["name"] == "Category Director"
        assert f"https://omnitrackr.xyz/reviews/{movie.id}?category=movie" == items[0]["item"]["url"]
        assert "Hidden From Movie Category" not in json.dumps(structured_data)
    
    def test_review_detail_page_accessible(self, client):
        """Test that the review detail page is accessible."""
        response = client.get("/reviews/1")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert '<meta name="robots" content="noindex, follow">' in response.text
        assert "Review Link Helper - OmniTrackr" in response.text

    def test_review_detail_page_includes_adsense_publisher_signal(self, client, db_session, test_user_data):
        """Indexable server-rendered review details should expose the AdSense publisher meta."""
        user = models.User(
            email=test_user_data["email"],
            username=test_user_data["username"],
            hashed_password="hashed-password",
            is_active=True,
            is_verified=True,
            reviews_public=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        user.reviews_public = True
        db_session.commit()

        movie = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Publisher Signal Detail",
                director="Signal Director",
                year=2026,
                rating=9,
                review=(
                    "This public review is substantial enough for the generated detail page because it explains the "
                    "movie's tone, pacing, audience fit, standout scenes, and rewatch value in a way that can help "
                    "another reader decide whether it belongs on their own watchlist. It is intentionally longer than "
                    "a quick note so the standalone page has useful context for search visitors."
                ),
                review_public=True,
            ),
        )
        db_session.commit()

        response = client.get(f"/reviews/{movie.id}?category=movie")

        assert response.status_code == 200
        assert '<meta name="robots" content="index, follow, max-image-preview:large">' in response.text
        assert '<meta name="google-adsense-account" content="ca-pub-7271682066779719">' in response.text
        assert "/static/ad-loader.js" in response.text
        assert "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" not in response.text
        assert "Publisher Signal Detail Movie Review" in response.text

        client.cookies.set("omnitrackr_session", "test-session")
        authenticated_response = client.get(f"/reviews/{movie.id}?category=movie")
        assert authenticated_response.status_code == 200
        assert "/static/ad-loader.js" not in authenticated_response.text

    def test_review_detail_requires_standalone_review_text(self, client, db_session, authenticated_client, test_user_data):
        """Directory-quality reviews should not become thin indexed ad pages."""
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        assert user is not None
        user.reviews_public = True
        db_session.commit()

        movie = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Directory Quality Only",
                director="Helpful Director",
                year=2026,
                rating=8,
                review=(
                    "This public review has enough context for a directory preview, with notes about pacing, tone, "
                    "and audience fit, but it is not long enough to stand alone as a full search landing page."
                ),
                review_public=True,
            ),
        )
        db_session.commit()

        category_response = client.get("/reviews?category=movie")
        detail_response = client.get(f"/reviews/{movie.id}?category=movie")

        assert category_response.status_code == 200
        assert "Directory Quality Only" in category_response.text
        assert 'class="review-card review-card--summary"' in category_response.text
        assert f"/reviews/{movie.id}?category=movie" not in category_response.text
        match = re.search(
            r'<script type="application/ld\+json" id="server-review-item-list"[^>]*>(.*?)</script>',
            category_response.text,
        )
        assert match is not None
        structured_data = json.loads(match.group(1))
        structured_json = json.dumps(structured_data)
        assert "Directory Quality Only Movie Review" in structured_json
        assert f"https://omnitrackr.xyz/reviews/{movie.id}?category=movie" not in structured_json
        assert detail_response.status_code == 404
        assert '<meta name="robots" content="noindex, follow">' in detail_response.text
        assert "/static/ad-loader.js" not in detail_response.text
