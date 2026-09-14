"""Private activity journal coverage across media, recap, and portability."""
from datetime import datetime, timedelta

from app import models


class TestActivityJournal:
    def test_authenticated_dashboard_exposes_private_journal_ui(self, authenticated_client):
        page = authenticated_client.get("/")
        assert page.status_code == 200
        assert 'data-switch-tab="activity"' in page.text
        assert 'id="activity-tab"' in page.text
        assert 'data-submit-action="create-activity"' in page.text
        assert "No public profile · No ads" in page.text
        assert "/activity" not in authenticated_client.get("/sitemap.xml").text

    def test_manual_entry_weekly_recap_and_delete_preserve_library(
        self, authenticated_client, db_session, test_movie_data
    ):
        movie = authenticated_client.post("/movies/", json=test_movie_data).json()
        created = authenticated_client.post(
            "/activity/",
            json={
                "category": "movies",
                "item_id": movie["id"],
                "action": "started",
                "note": "The opening image immediately set the mood.",
            },
        )
        assert created.status_code == 201
        entry = created.json()
        assert entry["title"] == movie["title"]
        assert entry["category_label"] == "Movie"
        assert entry["action_label"] == "Started"
        assert entry["source"] == "manual"
        assert created.headers["x-robots-tag"] == "noindex, nofollow"
        assert created.headers["cache-control"] == "private, no-store"

        listed = authenticated_client.get("/activity/")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [entry["id"]]

        recap = authenticated_client.get("/activity/weekly/").json()
        assert recap["entry_count"] == 1
        assert recap["reflection_count"] == 1
        assert recap["category_counts"] == [{"category": "movies", "label": "Movie", "count": 1}]

        updated = authenticated_client.patch(
            f"/activity/{entry['id']}",
            json={"action": "progressed", "note": "Halfway through; the pacing still works."},
        )
        assert updated.status_code == 200
        assert updated.json()["action_label"] == "Made progress"

        assert authenticated_client.delete(f"/activity/{entry['id']}").status_code == 204
        assert authenticated_client.get("/movies/").json()[0]["id"] == movie["id"]
        assert authenticated_client.get("/activity/").json() == []

    def test_completion_ritual_adds_one_automatic_journal_entry(
        self, authenticated_client, test_book_data
    ):
        test_book_data = {**test_book_data, "read": True}
        book = authenticated_client.post("/books/", json=test_book_data).json()

        first = authenticated_client.post(
            "/completion-moments/", json={"category": "books", "item_id": book["id"]}
        )
        second = authenticated_client.post(
            "/completion-moments/", json={"category": "books", "item_id": book["id"]}
        )

        assert first.status_code == 200
        assert second.status_code == 200
        activity = authenticated_client.get("/activity/").json()
        assert len(activity) == 1
        assert activity[0]["action"] == "completed"
        assert activity[0]["source"] == "automatic"

    def test_snapshot_survives_media_rename_and_delete(self, authenticated_client, test_anime_data):
        anime = authenticated_client.post("/anime/", json=test_anime_data).json()
        entry = authenticated_client.post(
            "/activity/",
            json={"category": "anime", "item_id": anime["id"], "action": "noted"},
        ).json()

        authenticated_client.put(f"/anime/{anime['id']}", json={"title": "A renamed title"})
        authenticated_client.delete(f"/anime/{anime['id']}")

        snapshot = authenticated_client.get("/activity/").json()[0]
        assert snapshot["id"] == entry["id"]
        assert snapshot["title"] == test_anime_data["title"]

    def test_filters_validation_auth_and_ownership(
        self, authenticated_client, db_session, test_movie_data
    ):
        movie = authenticated_client.post("/movies/", json=test_movie_data).json()
        assert authenticated_client.post(
            "/activity/", json={"category": "books", "item_id": movie["id"], "action": "started"}
        ).status_code == 404
        assert authenticated_client.post(
            "/activity/",
            json={
                "category": "movies",
                "item_id": movie["id"],
                "action": "started",
                "occurred_at": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            },
        ).status_code == 422
        assert authenticated_client.get("/activity/?category=podcasts").status_code == 422
        assert db_session.query(models.ActivityEntry).count() == 0

    def test_journal_requires_authentication(self, client):
        assert client.get("/activity/").status_code == 401
        assert client.get("/activity/weekly/").status_code == 401
        assert client.post(
            "/activity/", json={"category": "movies", "item_id": 1, "action": "started"}
        ).status_code == 401

    def test_export_is_versioned_and_old_imports_remain_valid(
        self, authenticated_client, test_movie_data
    ):
        movie = authenticated_client.post("/movies/", json=test_movie_data).json()
        authenticated_client.post(
            "/activity/",
            json={"category": "movies", "item_id": movie["id"], "action": "revisited"},
        )

        exported = authenticated_client.get("/export/")
        assert exported.status_code == 200
        payload = exported.json()
        assert payload["export_metadata"]["version"] == "1.1"
        assert payload["export_metadata"]["total_activities"] == 1
        assert payload["activities"][0]["title"] == movie["title"]

        legacy_payload = {"movies": [], "tv_shows": []}
        legacy_import = authenticated_client.post("/import/", json=legacy_payload)
        assert legacy_import.status_code == 200
        assert legacy_import.json()["activities_created"] == 0

        repeated_import = authenticated_client.post("/import/", json=payload)
        assert repeated_import.status_code == 200
        assert repeated_import.json()["activities_created"] == 0
        assert repeated_import.json()["activities_skipped"] == 1
