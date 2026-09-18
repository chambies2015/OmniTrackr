from datetime import datetime, timedelta

from app import models


def add_tasteprint_library(db, user_id: int):
    for index in range(5):
        db.add(models.Movie(
            user_id=user_id, title=f"Private Movie {index}", director="Ava Example",
            year=1990 + index, rating=8 + (index % 3) * 0.5, watched=index < 4,
            review=f"Private movie note {index}", review_public=False,
        ))
    for index in range(3):
        db.add(models.Music(
            user_id=user_id, title=f"Private Album {index}", artist="The Examples",
            year=1992 + index, genre="Ambient", rating=9, listened=True,
            review=f"Private album note {index}", review_public=False,
        ))
    for index in range(2):
        db.add(models.Book(
            user_id=user_id, title=f"Private Book {index}", author="Writer Example",
            year=2000 + index, genre="Fiction", rating=7.5, read=index == 0,
            review=f"Private book note {index}", review_public=False,
        ))
    db.commit()


class TestTasteprint:
    def test_tasteprint_requires_authentication(self, client):
        assert client.get("/statistics/tasteprint/").status_code == 401

    def test_sparse_library_reports_progress_without_fabricating_a_card(self, authenticated_client):
        response = authenticated_client.get("/statistics/tasteprint/")
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is False
        assert data["needed_items"] == 10
        assert data["needed_ratings"] == 5
        assert data["insights"] == []
        assert data["privacy"].startswith("Private aggregate")
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["x-robots-tag"] == "noindex, nofollow"

    def test_ready_tasteprint_uses_aggregates_without_titles_or_reviews(self, authenticated_client, db_session):
        user = db_session.query(models.User).one()
        add_tasteprint_library(db_session, user.id)
        db_session.add_all([
            models.ActivityEntry(
                user_id=user.id, category="movies", item_id=None, title="Never expose this title",
                action="revisited", note="Never expose this journal note", rating=9,
                source="manual", occurred_at=datetime.utcnow() - timedelta(days=3),
            ),
            models.ActivityEntry(
                user_id=user.id, category="music", item_id=None, title="Also private",
                action="completed", note=None, rating=9, source="manual",
                occurred_at=datetime.utcnow() - timedelta(days=10),
            ),
        ])
        db_session.commit()

        response = authenticated_client.get("/statistics/tasteprint/")
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True
        assert data["total_items"] == 10
        assert data["rated_items"] == 10
        keys = {insight["key"] for insight in data["insights"]}
        assert {"breadth", "anchor", "completion", "rating", "era", "creator", "momentum"}.issubset(keys)
        creator = next(insight for insight in data["insights"] if insight["key"] == "creator")
        assert creator["value"] == "Ava Example"
        serialized = response.text
        assert "Private Movie" not in serialized
        assert "Private Album" not in serialized
        assert "Private Book" not in serialized
        assert "Never expose this" not in serialized
        assert "journal note" not in serialized

    def test_private_and_hidden_categories_are_excluded_by_default_but_owner_can_select_them(self, authenticated_client, db_session):
        user = db_session.query(models.User).one()
        user.movies_private = True
        user.books_visible = False
        db_session.add(models.Movie(user_id=user.id, title="Private", director="Director", year=2000, watched=True))
        db_session.add(models.Book(user_id=user.id, title="Hidden", author="Author", year=2001, read=True))
        db_session.add(models.Music(user_id=user.id, title="Visible", artist="Artist", year=2002, listened=True))
        db_session.commit()

        default = authenticated_client.get("/statistics/tasteprint/").json()
        assert "movies" not in default["selected_categories"]
        assert "books" not in default["selected_categories"]
        assert "music" in default["selected_categories"]
        assert default["total_items"] == 1
        movies = next(item for item in default["available_categories"] if item["key"] == "movies")
        books = next(item for item in default["available_categories"] if item["key"] == "books")
        assert movies["private"] is True
        assert movies["default_included"] is False
        assert books["hidden"] is True
        assert books["default_included"] is False

        explicit = authenticated_client.get("/statistics/tasteprint/?categories=movies,books").json()
        assert explicit["selected_categories"] == ["movies", "books"]
        assert explicit["total_items"] == 2

    def test_category_validation_and_empty_explicit_selection(self, authenticated_client, db_session):
        user = db_session.query(models.User).one()
        db_session.add(models.Movie(user_id=user.id, title="A", director="B", year=2000, watched=True))
        db_session.commit()

        invalid = authenticated_client.get("/statistics/tasteprint/?categories=movies,podcasts")
        assert invalid.status_code == 400
        assert "podcasts" in invalid.json()["detail"]

        empty = authenticated_client.get("/statistics/tasteprint/?categories=")
        assert empty.status_code == 200
        assert empty.json()["selected_categories"] == []
        assert empty.json()["total_items"] == 0

    def test_dashboard_exposes_private_local_share_workflow(self, authenticated_client):
        page = authenticated_client.get("/")
        assert page.status_code == 200
        assert 'id="tasteprint"' in page.text
        assert "OmniTrackr Tasteprint" in page.text
        assert "Private calculation · No public profile" in page.text
        assert "The image is rendered on this device" in page.text
        assert 'data-action="tasteprint-download"' in page.text
