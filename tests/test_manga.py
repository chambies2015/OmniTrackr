"""Manga shelf: CRUD, privacy defaults, search normalisation and the public guide."""
from app import models
from app.routers.proxy import normalize_jikan_manga


def test_manga_crud_round_trip(authenticated_client):
    created = authenticated_client.post("/manga/", json={
        "title": "Vagabond", "author": "Takehiko Inoue", "year": 1998, "genre": "Seinen",
        "volumes": 37, "chapters": 327, "rating": 9.5, "read": False,
    })
    assert created.status_code in (200, 201), created.text
    manga_id = created.json()["id"]
    assert created.json()["volumes"] == 37 and created.json()["chapters"] == 327

    listed = authenticated_client.get("/manga/")
    assert listed.status_code == 200
    assert [item["title"] for item in listed.json()] == ["Vagabond"]

    updated = authenticated_client.put(f"/manga/{manga_id}", json={"read": True, "chapters": 327})
    assert updated.status_code == 200 and updated.json()["read"] is True

    assert authenticated_client.delete(f"/manga/{manga_id}").status_code in (200, 204)
    assert authenticated_client.get("/manga/").json() == []


def test_manga_requires_sign_in(client):
    assert client.get("/manga/").status_code == 401
    assert client.get("/api/proxy/jikan-manga", params={"query": "Berserk"}).status_code == 401


def test_new_manga_privacy_flags_default_to_existing_behaviour(db_session):
    user = models.User(email="m@example.test", username="mangareader", hashed_password="x")
    db_session.add(user)
    db_session.commit()
    assert user.manga_private is False and user.manga_visible is True


def test_jikan_manga_results_read_like_a_shelf_entry():
    entry = {
        "mal_id": 2, "title": "Berserk", "title_english": None, "type": "Manga",
        "authors": [{"name": "Miura, Kentarou"}, {"name": "Studio Gaga"}],
        "published": {"prop": {"from": {"year": 1989}}},
        "genres": [{"name": "Action"}, {"name": "Fantasy"}], "demographics": [{"name": "Seinen"}],
        "volumes": None, "chapters": None, "status": "Publishing",
        "images": {"jpg": {"large_image_url": "https://cdn.example.test/berserk.jpg"}},
    }
    result = normalize_jikan_manga(entry)
    assert result["title"] == "Berserk"
    assert result["author"] == "Kentarou Miura, Studio Gaga"
    assert result["year"] == 1989
    assert result["genre"] == "Action, Fantasy, Seinen"
    assert result["volumes"] is None and result["status"] == "Publishing"
    assert result["cover_art_url"] == "https://cdn.example.test/berserk.jpg"


def test_manga_tracker_guide_is_public_and_indexable(client):
    response = client.get("/manga-tracker")
    assert response.status_code == 200
    assert '<link rel="canonical" href="https://omnitrackr.xyz/manga-tracker"' in response.text
    assert "noindex" not in response.text.split("</head>")[0]
    assert "/manga-tracker" in client.get("/sitemap.xml").text
