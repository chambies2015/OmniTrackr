"""Episode guides: season layouts, one-tap next episode, and progress on lists."""
import pytest

from app import episodes, models


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return self.payload


class TVmazeClient:
    """Breaking Bad-like layout: 7, 13, 13 regular episodes plus an unnumbered special."""
    def __init__(self):
        self.calls = []

    async def get(self, url, params=None, **kwargs):
        self.calls.append(url)
        if url.endswith("/search/shows"):
            return FakeResponse([{"show": {"id": 169, "name": "Breaking Bad", "premiered": "2008-01-20"}}])
        if url.endswith("/shows/169/episodes"):
            regular = [{"season": s, "number": n} for s, count in ((1, 7), (2, 13), (3, 13)) for n in range(1, count + 1)]
            return FakeResponse(regular + [{"season": 2, "number": None}])
        return FakeResponse(None, 404)

    async def aclose(self):
        return None


class OfflineClient:
    async def get(self, *args, **kwargs):
        raise RuntimeError("offline")

    async def aclose(self):
        return None


@pytest.fixture
def show(authenticated_client, test_tv_show_data):
    return authenticated_client.post("/tv-shows/", json={**test_tv_show_data, "watched": False}).json()


def use_client(monkeypatch, fake):
    from app.main import app
    monkeypatch.setattr(app.state, "external_api_client", fake, raising=False)
    return fake


def test_guide_fetches_and_caches_season_layout(authenticated_client, show, monkeypatch, db_session):
    fake = use_client(monkeypatch, TVmazeClient())
    response = authenticated_client.get(f"/progress/tv-shows/{show['id']}/episodes")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    data = response.json()
    assert data["layout"]["seasons"] == [{"number": 1, "episodes": 7}, {"number": 2, "episodes": 13}, {"number": 3, "episodes": 13}]
    assert data["layout"]["source"] == "TVmaze"
    assert data["episodes"] == {"total": 33, "watched": 0, "percent": 0, "season_count": 3, "current": None,
                                "next": {"season": 1, "episode": 1}, "caught_up": False, "revision": 0}
    calls = len(fake.calls)
    authenticated_client.get(f"/progress/tv-shows/{show['id']}/episodes")
    assert len(fake.calls) == calls  # served from the shared cache
    assert db_session.query(models.TitleMetadata).filter(models.TitleMetadata.key.like("episodes:tv:%")).count() == 1
    # The title-page cache key is untouched.
    assert db_session.query(models.TitleMetadata).filter_by(key="tv:breaking bad:2008").count() == 0


def test_offline_guide_falls_back_to_the_members_episode_count(authenticated_client, show, monkeypatch):
    use_client(monkeypatch, OfflineClient())
    data = authenticated_client.get(f"/progress/tv-shows/{show['id']}/episodes").json()
    # Five seasons but only a total: one continuous run of 62.
    assert data["layout"]["seasons"] == [{"number": None, "episodes": 62}]
    assert data["episodes"]["total"] == 62


def test_episode_write_rolls_seasons_keeps_note_and_is_retry_safe(authenticated_client, show, monkeypatch):
    client = authenticated_client
    use_client(monkeypatch, TVmazeClient())
    client.get(f"/progress/tv-shows/{show['id']}/episodes")
    saved = client.put(f"/progress/tv-shows/{show['id']}", json={
        "unit": "episode", "position": 7, "season": 1, "note": "Keep me", "expected_revision": 0}).json()
    assert saved["revision"] == 1

    guide = client.get(f"/progress/tv-shows/{show['id']}/episodes").json()
    assert guide["episodes"]["next"] == {"season": 2, "episode": 1}
    assert guide["episodes"]["percent"] == round(100 * 7 / 33)

    body = {"expected_revision": 1, "season": 2, "episode": 1}
    moved = client.put(f"/progress/tv-shows/{show['id']}/episode", json=body)
    assert moved.status_code == 200
    data = moved.json()
    assert data["checkpoint"]["season"] == 2 and data["checkpoint"]["position"] == 1
    assert data["checkpoint"]["note"] == "Keep me"
    assert data["episodes"]["watched"] == 8 and data["episodes"]["next"] == {"season": 2, "episode": 2}

    # A lost response retried with the same body is answered, not applied twice.
    retry = client.put(f"/progress/tv-shows/{show['id']}/episode", json=body)
    assert retry.status_code == 200 and retry.json()["revision"] == 2
    # A stale tab is refused.
    stale = client.put(f"/progress/tv-shows/{show['id']}/episode", json={**body, "episode": 5})
    assert stale.status_code == 409

    finale = client.put(f"/progress/tv-shows/{show['id']}/episode",
                        json={"expected_revision": 2, "season": 3, "episode": 13}).json()
    assert finale["episodes"]["caught_up"] is True and finale["episodes"]["next"] is None
    assert finale["episodes"]["percent"] == 100
    # The title itself is untouched: watching every episode doesn't mark it finished.
    assert client.get(f"/tv-shows/{show['id']}").json()["watched"] is False


def test_episode_write_rules(authenticated_client, show, test_user_data, db_session):
    client = authenticated_client
    assert client.put("/progress/books/1/episode", json={"expected_revision": 0, "episode": 1}).status_code == 422
    assert client.put(f"/progress/tv-shows/{show['id']}/episode", json={"expected_revision": 0, "episode": 0}).status_code == 422
    assert client.put(f"/progress/tv-shows/{show['id']}/episode", json={"expected_revision": 0, "episode": "2"}).status_code == 422
    assert client.put(f"/progress/tv-shows/999999/episode", json={"expected_revision": 0, "episode": 1}).status_code == 404
    assert client.get("/progress/movies/1/episodes").status_code == 422


def test_other_members_cannot_read_or_move_a_show(authenticated_client, show, client, db_session):
    other = client.post("/auth/register", json={"email": "o@example.com", "username": "otheruser", "password": "testpassword123"})
    user = db_session.get(models.User, other.json()["id"])
    user.is_verified = True
    db_session.commit()
    token = client.post("/auth/login", data={"username": "otheruser", "password": "testpassword123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/progress/tv-shows/{show['id']}/episodes", headers=headers).status_code == 404
    assert client.put(f"/progress/tv-shows/{show['id']}/episode", headers=headers,
                      json={"expected_revision": 0, "episode": 1}).status_code == 404


def test_library_page_and_dashboard_carry_episode_progress(authenticated_client, show, monkeypatch):
    client = authenticated_client
    use_client(monkeypatch, TVmazeClient())
    client.get(f"/progress/tv-shows/{show['id']}/episodes")
    client.put(f"/progress/tv-shows/{show['id']}/episode", json={"expected_revision": 0, "season": 2, "episode": 3})

    page = client.get("/library/page/tv-shows").json()
    row = page["items"][0]
    assert row["episode_progress"]["watched"] == 10
    assert row["episode_progress"]["next"] == {"season": 2, "episode": 4}
    assert row["episode_progress"]["revision"] == 1

    pulse = client.get("/statistics/pulse/").json()
    item = next(entry for entry in pulse["continue_items"] if entry["category"] == "tv-shows")
    assert item["episode_progress"]["percent"] == round(100 * 10 / 33)

    client.post("/next-up/", json={"category": "tv-shows", "item_id": show["id"]})
    queue = client.get("/next-up/").json()
    assert queue[0]["episode_progress"]["next"] == {"season": 2, "episode": 4}

    # Movies and other categories keep their exact shape.
    client.post("/movies/", json={"title": "Heat", "director": "Michael Mann", "year": 1995})
    assert "episode_progress" not in client.get("/library/page/movies").json()["items"][0]


def test_cleared_checkpoint_reports_its_revision(authenticated_client, show):
    client = authenticated_client
    client.put(f"/progress/tv-shows/{show['id']}/episode", json={"expected_revision": 0, "episode": 3})
    client.request("DELETE", f"/progress/tv-shows/{show['id']}", json={"expected_revision": 1})
    row = client.get("/library/page/tv-shows").json()["items"][0]["episode_progress"]
    assert row["current"] is None and row["revision"] == 2
    assert client.put(f"/progress/tv-shows/{show['id']}/episode",
                      json={"expected_revision": 2, "episode": 1}).status_code == 200


@pytest.mark.parametrize("seasons,season,position,expected", [
    ([], None, None, (None, 1)),
    ([], 2, 4, (2, 5)),
    ([{"number": None, "episodes": 12}], None, 11, (None, 12)),
    ([{"number": None, "episodes": 12}], None, 12, None),
    ([{"number": 1, "episodes": 3}, {"number": 2, "episodes": 3}], None, 4, (2, 2)),
    ([{"number": 1, "episodes": 3}, {"number": 2, "episodes": 3}], 1, 3, (2, 1)),
    ([{"number": 1, "episodes": 3}, {"number": 2, "episodes": 3}], 2, 3, None),
    ([{"number": 1, "episodes": 3}], 4, 2, (4, 3)),
    ([{"number": 1, "episodes": 3}], 0, 2, (0, 3)),
])
def test_next_episode(seasons, season, position, expected):
    assert episodes.next_episode(seasons, season, position) == expected


def test_layout_cleaning_rejects_bad_upstream_data():
    assert episodes._clean([{"number": 1, "episodes": 8}, {"number": 1, "episodes": 9}, {"number": "2", "episodes": 3},
                            {"number": 3, "episodes": 0}, {"number": 4, "episodes": True}, None]) == [{"number": 1, "episodes": 8}]
    assert episodes.absolute([{"number": 1, "episodes": 8}, {"number": 3, "episodes": 5}], 3, 2) == 10
    assert episodes.absolute([], 0, 4) is None
