"""Podcast shelf: CRUD, privacy defaults, search normalisation and the public guide."""
from app import models
from app.routers.proxy import normalize_itunes_podcast


def test_podcast_crud_round_trip(authenticated_client):
    created = authenticated_client.post("/podcasts/", json={
        "title": "Serial", "host": "Sarah Koenig", "year": 2014, "genre": "True Crime",
        "episodes": 12, "rating": 8.5, "listened": False,
    })
    assert created.status_code in (200, 201), created.text
    podcast_id = created.json()["id"]
    assert created.json()["episodes"] == 12 and created.json()["host"] == "Sarah Koenig"

    listed = authenticated_client.get("/podcasts/")
    assert listed.status_code == 200
    assert [item["title"] for item in listed.json()] == ["Serial"]

    updated = authenticated_client.put(f"/podcasts/{podcast_id}", json={"listened": True})
    assert updated.status_code == 200 and updated.json()["listened"] is True

    stats = authenticated_client.get("/statistics/podcasts/")
    assert stats.status_code == 200
    assert stats.json()["watch_stats"]["watched_items"] == 1 and stats.json()["episodes_listened"] == 12

    assert authenticated_client.delete(f"/podcasts/{podcast_id}").status_code in (200, 204)
    assert authenticated_client.get("/podcasts/").json() == []


def test_podcast_episode_checkpoint(authenticated_client):
    podcast_id = authenticated_client.post("/podcasts/", json={"title": "Hardcore History"}).json()["id"]
    saved = authenticated_client.put(f"/progress/podcasts/{podcast_id}", json={
        "unit": "episode", "position": 42, "season": None, "note": "", "expected_revision": 0,
    })
    assert saved.status_code == 200, saved.text
    assert authenticated_client.get(f"/progress/podcasts/{podcast_id}").json()["checkpoint"]["position"] == 42


def test_podcasts_require_sign_in(client):
    assert client.get("/podcasts/").status_code == 401
    assert client.get("/api/proxy/itunes-podcasts", params={"query": "Serial"}).status_code == 401


def test_new_podcast_privacy_flags_default_to_existing_behaviour(db_session):
    user = models.User(email="p@example.test", username="listener", hashed_password="x")
    db_session.add(user)
    db_session.commit()
    assert user.podcasts_private is False and user.podcasts_visible is True


def test_itunes_podcast_results_read_like_a_shelf_entry():
    entry = {
        "collectionId": 917918570, "collectionName": "Serial", "artistName": "Serial Productions & The New York Times",
        "genres": ["News", "Podcasts", "True Crime"], "primaryGenreName": "News", "trackCount": 98,
        "releaseDate": "2026-10-01T10:00:00Z", "artworkUrl600": "https://is1-ssl.mzstatic.com/serial.jpg",
        "collectionViewUrl": "https://podcasts.apple.com/podcast/serial/id917918570",
    }
    result = normalize_itunes_podcast(entry)
    assert result["title"] == "Serial"
    assert result["host"] == "Serial Productions & The New York Times"
    assert result["genre"] == "News, True Crime"
    assert result["episodes"] == 98
    assert result["latest_episode"] == "2026-10-01"
    assert result["cover_art_url"] == "https://is1-ssl.mzstatic.com/serial.jpg"


def test_podcast_tracker_guide_is_public_and_indexable(client):
    response = client.get("/podcast-tracker")
    assert response.status_code == 200
    assert '<link rel="canonical" href="https://omnitrackr.xyz/podcast-tracker"' in response.text
    assert "noindex" not in response.text.split("</head>")[0]
    assert "/podcast-tracker" in client.get("/sitemap.xml").text
