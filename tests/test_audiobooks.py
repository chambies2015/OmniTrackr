"""Audiobook shelf: CRUD, chapter progress, privacy defaults, search normalisation and the public guide."""
from types import SimpleNamespace

from app import models, time_spent
from app.import_studio import _optional_hours
from app.routers.proxy import normalize_itunes_audiobook


def test_audiobook_crud_round_trip(authenticated_client):
    created = authenticated_client.post("/audiobooks/", json={
        "title": "Project Hail Mary", "author": "Andy Weir", "narrator": "Ray Porter", "year": 2021,
        "genre": "Sci-Fi & Fantasy", "length_hours": 16.17, "rating": 9.5, "listened": False,
    })
    assert created.status_code in (200, 201), created.text
    audiobook_id = created.json()["id"]
    assert created.json()["narrator"] == "Ray Porter" and created.json()["length_hours"] == 16.17

    # Search covers the narrator as well as title and author.
    found = authenticated_client.get("/audiobooks/", params={"search": "Porter"})
    assert [item["title"] for item in found.json()] == ["Project Hail Mary"]

    updated = authenticated_client.put(f"/audiobooks/{audiobook_id}", json={"listened": True})
    assert updated.status_code == 200 and updated.json()["listened"] is True

    stats = authenticated_client.get("/statistics/audiobooks/")
    assert stats.status_code == 200
    assert stats.json()["watch_stats"]["watched_items"] == 1
    assert stats.json()["hours_listened"] == 16.2 and stats.json()["total_hours"] == 16.2

    watch = authenticated_client.get("/statistics/watch/").json()
    assert watch["total_audiobooks"] == 1 and watch["listened_audiobooks"] == 1

    assert authenticated_client.delete(f"/audiobooks/{audiobook_id}").status_code in (200, 204)
    assert authenticated_client.get("/audiobooks/").json() == []


def test_audiobook_sorts_by_length(authenticated_client):
    for title, hours in (("Long", 40.5), ("Short", 3), ("Unknown", None)):
        authenticated_client.post("/audiobooks/", json={"title": title, "length_hours": hours})
    longest_first = authenticated_client.get("/audiobooks/", params={"sort_by": "length", "order": "desc"}).json()
    assert [item["title"] for item in longest_first if item["length_hours"]] == ["Long", "Short"]


def test_audiobook_rejects_impossible_length(authenticated_client):
    assert authenticated_client.post("/audiobooks/", json={"title": "Bad", "length_hours": -1}).status_code == 422
    assert authenticated_client.post("/audiobooks/", json={"title": "Bad", "length_hours": 5000}).status_code == 422


def test_audiobook_uses_chapter_checkpoints_only(authenticated_client):
    audiobook_id = authenticated_client.post("/audiobooks/", json={"title": "Dune"}).json()["id"]
    saved = authenticated_client.put(f"/progress/audiobooks/{audiobook_id}", json={
        "unit": "chapter", "position": 7, "season": None, "note": "", "expected_revision": 0,
    })
    assert saved.status_code == 200, saved.text
    assert authenticated_client.get(f"/progress/audiobooks/{audiobook_id}").json()["checkpoint"]["position"] == 7

    rejected = authenticated_client.put(f"/progress/audiobooks/{audiobook_id}", json={
        "unit": "episode", "position": 3, "season": None, "note": "", "expected_revision": 1,
    })
    assert rejected.status_code == 422


def test_audiobooks_require_sign_in(client):
    assert client.get("/audiobooks/").status_code == 401
    assert client.get("/api/proxy/itunes-audiobooks", params={"query": "Dune"}).status_code == 401


def test_new_audiobook_privacy_flags_default_to_existing_behaviour(db_session):
    user = models.User(email="a@example.test", username="earful", hashed_password="x")
    db_session.add(user)
    db_session.commit()
    assert user.audiobooks_private is False and user.audiobooks_visible is True


def test_audiobooks_round_trip_through_json_backup(authenticated_client):
    authenticated_client.post("/audiobooks/", json={"title": "Circe", "author": "Madeline Miller",
                                                    "narrator": "Perdita Weeks", "length_hours": 12})
    backup = authenticated_client.get("/export/").json()
    assert backup["export_metadata"]["total_audiobooks"] == 1
    assert backup["audiobooks"][0]["narrator"] == "Perdita Weeks"

    # Restoring the same backup updates the existing row instead of duplicating it.
    result = authenticated_client.post("/import/", json=backup)
    assert result.status_code == 200, result.text
    assert result.json()["audiobooks_updated"] == 1 and result.json()["audiobooks_created"] == 0
    assert len(authenticated_client.get("/audiobooks/").json()) == 1


def test_older_backups_without_audiobooks_still_import(authenticated_client):
    result = authenticated_client.post("/import/", json={"movies": [], "tv_shows": []})
    assert result.status_code == 200, result.text
    assert result.json()["audiobooks_created"] == 0


def test_itunes_audiobook_results_read_like_a_shelf_entry():
    entry = {
        "collectionId": 1565808256, "collectionName": "Project Hail Mary (Unabridged)", "artistName": "Andy Weir",
        "primaryGenreName": "Sci-Fi & Fantasy", "releaseDate": "2021-05-04T07:00:00Z",
        "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/x/rm_image.jpg/100x100bb.jpg",
        "collectionViewUrl": "https://books.apple.com/us/audiobook/project-hail-mary-unabridged/id1565808256",
    }
    result = normalize_itunes_audiobook(entry)
    assert result["title"] == "Project Hail Mary"
    assert result["author"] == "Andy Weir"
    assert result["year"] == 2021
    assert result["genre"] == "Sci-Fi & Fantasy"
    assert result["cover_art_url"].endswith("/600x600bb.jpg")


def test_csv_length_accepts_hours_or_a_runtime():
    assert _optional_hours("11.5") == 11.5
    assert _optional_hours("11:30") == 11.5
    assert _optional_hours("11h 30m") == 11.5
    assert _optional_hours("") is None


def test_time_spent_uses_the_real_runtime():
    item = SimpleNamespace(length_hours=8.5)
    assert time_spent.full_minutes("audiobooks", item, {}) == (510, False)
    assert time_spent.full_minutes("audiobooks", SimpleNamespace(length_hours=None), {})[1] is True


def test_audiobook_tracker_guide_is_public_and_indexable(client):
    response = client.get("/audiobook-tracker")
    assert response.status_code == 200
    assert '<link rel="canonical" href="https://omnitrackr.xyz/audiobook-tracker"' in response.text
    assert "noindex" not in response.text.split("</head>")[0]
    assert "/audiobook-tracker" in client.get("/sitemap.xml").text
