"""Private ratings and notes on single episodes, kept beside the episode guide."""
import pytest

from app import episode_notes, models
from tests.test_episode_tracking import TVmazeClient, use_client


@pytest.fixture
def show(authenticated_client, test_tv_show_data):
    return authenticated_client.post("/tv-shows/", json={**test_tv_show_data, "watched": False}).json()


def note(client, show_id, category="tv-shows", **body):
    return client.put(f"/progress/{category}/{show_id}/episode-notes", json=body)


def test_rate_and_note_an_episode_then_change_and_clear_it(authenticated_client, show, monkeypatch):
    client = authenticated_client
    use_client(monkeypatch, TVmazeClient())
    client.get(f"/progress/tv-shows/{show['id']}/episodes")

    saved = note(client, show["id"], season=1, episode=3, rating=9, note="  The bathtub.\n\nWow.  ", spoiler=True)
    assert saved.status_code == 200, saved.text
    assert saved.headers["Cache-Control"] == "private, no-store"
    data = saved.json()
    # The answer is the whole guide, so the dialog redraws from one response.
    assert data["layout"]["seasons"][0] == {"number": 1, "episodes": 7}
    assert data["episode_notes"] == [{"season": 1, "episode": 3, "rating": 9, "note": "The bathtub.\n\nWow.",
                                      "spoiler": True, "updated_at": data["episode_notes"][0]["updated_at"]}]
    assert data["episode_note_summary"] == {"rated": 1, "noted": 1, "average": 9.0}

    note(client, show["id"], season=2, episode=1, rating=6)
    note(client, show["id"], season=1, episode=1, note="Pilot, slow start")
    listed = client.get(f"/progress/tv-shows/{show['id']}/episodes").json()
    assert [(e["season"], e["episode"]) for e in listed["episode_notes"]] == [(1, 1), (1, 3), (2, 1)]
    assert listed["episode_note_summary"] == {"rated": 2, "noted": 2, "average": 7.5}
    pilot = listed["episode_notes"][0]
    assert pilot["rating"] is None and pilot["spoiler"] is False

    # Saving again replaces that episode's entry; a spoiler flag needs a note.
    changed = note(client, show["id"], season=1, episode=3, rating=10, spoiler=True).json()
    entry = next(e for e in changed["episode_notes"] if e["episode"] == 3 and e["season"] == 1)
    assert entry["rating"] == 10 and entry["note"] is None and entry["spoiler"] is False

    # Empty rating and note removes it, and so does DELETE.
    cleared = note(client, show["id"], season=1, episode=3, note="   ").json()
    assert [(e["season"], e["episode"]) for e in cleared["episode_notes"]] == [(1, 1), (2, 1)]
    removed = client.request("DELETE", f"/progress/tv-shows/{show['id']}/episode-notes", json={"season": 2, "episode": 1})
    assert removed.status_code == 200 and len(removed.json()["episode_notes"]) == 1
    assert client.request("DELETE", f"/progress/tv-shows/{show['id']}/episode-notes",
                          json={"season": 2, "episode": 1}).status_code == 200


def test_episode_notes_never_touch_the_show_or_its_progress(authenticated_client, show):
    client = authenticated_client
    client.put(f"/progress/tv-shows/{show['id']}/episode", json={"expected_revision": 0, "season": 1, "episode": 2})
    before = client.get(f"/tv-shows/{show['id']}").json()
    note(client, show["id"], season=1, episode=2, rating=3, note="meh")
    after = client.get(f"/tv-shows/{show['id']}").json()
    assert after == before
    guide = client.get(f"/progress/tv-shows/{show['id']}/episodes").json()
    assert guide["revision"] == 1 and guide["checkpoint"]["position"] == 2


def test_continuous_anime_numbering_and_specials_are_separate_episodes(authenticated_client):
    client = authenticated_client
    anime = client.post("/anime/", json={"title": "Frieren", "year": 2023, "episodes": 28}).json()
    note(client, anime["id"], category="anime", episode=10, rating=10)
    note(client, anime["id"], category="anime", season=1, episode=10, rating=7)
    note(client, anime["id"], category="anime", season=0, episode=1, rating=8)
    entries = client.get(f"/progress/anime/{anime['id']}/episodes").json()["episode_notes"]
    assert [(e["season"], e["episode"], e["rating"]) for e in entries] == [(0, 1, 8), (1, 10, 7), (None, 10, 10)]


@pytest.mark.parametrize("body", [
    {"episode": 0, "rating": 5},
    {"episode": 1, "rating": 0},
    {"episode": 1, "rating": 11},
    {"episode": 1, "rating": 7.5},
    {"episode": 1, "rating": "8"},
    {"episode": "1", "rating": 8},
    {"season": -1, "episode": 1, "rating": 8},
    {"episode": 1, "note": "x" * 1001},
    {"episode": 1, "rating": 8, "owner": 2},
])
def test_bad_episode_notes_are_refused(authenticated_client, show, body):
    assert note(authenticated_client, show["id"], **body).status_code == 422


def test_only_shows_and_anime_take_episode_notes(authenticated_client, show):
    client = authenticated_client
    book = client.post("/books/", json={"title": "Dune", "author": "Frank Herbert", "year": 1965}).json()
    assert note(client, book["id"], category="books", episode=1, rating=5).status_code == 422
    assert note(client, 999999, episode=1, rating=5).status_code == 404


def test_other_members_cannot_read_or_write_episode_notes(authenticated_client, show, client, db_session):
    note(authenticated_client, show["id"], season=1, episode=1, rating=9, note="mine")
    other = client.post("/auth/register", json={"email": "o@example.com", "username": "otheruser", "password": "testpassword123"})
    user = db_session.get(models.User, other.json()["id"])
    user.is_verified = True
    db_session.commit()
    token = client.post("/auth/login", data={"username": "otheruser", "password": "testpassword123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.put(f"/progress/tv-shows/{show['id']}/episode-notes", headers=headers,
                      json={"season": 1, "episode": 1, "rating": 1}).status_code == 404
    assert client.request("DELETE", f"/progress/tv-shows/{show['id']}/episode-notes", headers=headers,
                          json={"season": 1, "episode": 1}).status_code == 404
    assert client.get(f"/progress/tv-shows/{show['id']}/episodes", headers=headers).status_code == 404
    row = db_session.query(models.EpisodeNote).one()
    assert row.rating == 9 and row.note == "mine"


def test_signed_out_requests_are_refused(show):
    from fastapi.testclient import TestClient
    from app.main import app
    guest = TestClient(app)
    assert guest.put(f"/progress/tv-shows/{show['id']}/episode-notes", json={"episode": 1, "rating": 1}).status_code in (401, 403)


def test_deleting_the_show_removes_its_episode_notes(authenticated_client, show, db_session):
    client = authenticated_client
    note(client, show["id"], season=1, episode=1, rating=9)
    note(client, show["id"], season=1, episode=2, note="keep?")
    assert db_session.query(models.EpisodeNote).count() == 2
    assert client.delete(f"/tv-shows/{show['id']}").status_code in (200, 204)
    assert db_session.query(models.EpisodeNote).count() == 0


def test_per_show_limit(authenticated_client, show, monkeypatch):
    monkeypatch.setattr(episode_notes, "MAX_PER_SHOW", 2)
    client = authenticated_client
    assert note(client, show["id"], episode=1, rating=5).status_code == 200
    assert note(client, show["id"], episode=2, rating=5).status_code == 200
    refused = note(client, show["id"], episode=3, rating=5)
    assert refused.status_code == 422 and "as many episode notes" in refused.json()["detail"]
    # Changing an episode that already has an entry still works at the limit.
    assert note(client, show["id"], episode=2, rating=6).status_code == 200


def test_backup_round_trip_keeps_existing_entries(authenticated_client, show, db_session):
    client = authenticated_client
    note(client, show["id"], season=1, episode=1, rating=8, note="Strong open")
    note(client, show["id"], season=2, episode=13, note="That ending", spoiler=True)
    backup = client.get("/export/").json()
    assert backup["export_metadata"]["total_episode_notes"] == 2
    [row] = backup["episode_notes"]
    assert row["category"] == "tv-shows" and row["title"] == "Breaking Bad" and row["year"] == 2008
    assert [(e["season"], e["episode"]) for e in row["episodes"]] == [(1, 1), (2, 13)]

    db_session.query(models.EpisodeNote).delete()
    db_session.commit()
    note(client, show["id"], season=1, episode=1, rating=3)  # written since the backup: kept

    result = client.post("/import/", json=backup).json()
    assert (result["episode_notes_created"], result["episode_notes_skipped"]) == (1, 1)
    entries = client.get(f"/progress/tv-shows/{show['id']}/episodes").json()["episode_notes"]
    assert [(e["season"], e["episode"], e["rating"], e["spoiler"]) for e in entries] == [(1, 1, 3, False), (2, 13, None, True)]

    again = client.post("/import/", json=backup).json()
    assert (again["episode_notes_created"], again["episode_notes_skipped"]) == (0, 2)


def test_import_skips_bad_episode_note_rows(authenticated_client, show, db_session):
    result = authenticated_client.post("/import/", json={"episode_notes": [
        {"category": "tv-shows", "title": "Breaking Bad", "year": 2008, "episodes": [
            {"season": 1, "episode": 4, "rating": 7},
            {"season": 1, "episode": 5, "rating": 70},
            {"season": 1, "episode": 6},
            "nonsense",
        ]},
        {"category": "movies", "title": "Breaking Bad", "episodes": [{"episode": 1, "rating": 5}]},
        {"category": "tv-shows", "title": "Missing show", "episodes": [{"episode": 1, "rating": 5}, {"episode": 2, "rating": 5}]},
        {"category": "tv-shows", "title": "Breaking Bad", "episodes": "not a list"},
    ]}).json()
    assert result["episode_notes_created"] == 1
    assert result["episode_notes_skipped"] == 3 + 1 + 2 + 1
    assert db_session.query(models.EpisodeNote).one().episode == 4


def test_older_backups_without_episode_notes_still_import(authenticated_client):
    result = authenticated_client.post("/import/", json={"movies": [], "tv_shows": []})
    assert result.status_code == 200
    assert result.json()["episode_notes_created"] == 0
