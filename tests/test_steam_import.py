"""Steam library import: profile parsing, the Steam calls (mocked), the Import Studio path and playtime."""
import io
import json
import zipfile
from datetime import date
from pathlib import Path

import httpx
import pytest

from app import game_playtime, models, steam, time_spent
from app.main import app

STEAM_ID = "76561198000000001"
GAMES = [
    {"appid": 620, "name": "Portal 2", "playtime_forever": 900, "rtime_last_played": 1700000000},
    {"appid": 1145360, "name": "Hades", "playtime_forever": 30},
    {"appid": 413150, "name": "Stardew Valley", "playtime_forever": 0},
]


@pytest.fixture
def steam_key(monkeypatch):
    monkeypatch.setenv("STEAM_WEB_API_KEY", "test-key")


class FakeSteam:
    """Answers the three Steam endpoints and records every request made."""

    def __init__(self, games=GAMES, vanity_ok=True, owned=None, status=200):
        self.games, self.vanity_ok, self.owned, self.status = games, vanity_ok, owned, status
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status, json={})
        path = request.url.path
        if path == steam.PATHS["resolve"]:
            body = {"response": {"success": 1, "steamid": STEAM_ID}} if self.vanity_ok else {"response": {"success": 42}}
        elif path == steam.PATHS["owned"]:
            body = self.owned if self.owned is not None else {"response": {"game_count": len(self.games), "games": self.games}}
        elif path == steam.PATHS["summary"]:
            body = {"response": {"players": [{"personaname": "  Glados   Fan "}]}}
        else:
            return httpx.Response(404)
        return httpx.Response(200, json=body)


@pytest.fixture
def fake_steam(authenticated_client):
    """Swap the app's outbound client for one that never leaves the test."""
    fake = FakeSteam()
    original = app.state.external_api_client
    app.state.external_api_client = httpx.AsyncClient(transport=httpx.MockTransport(fake))
    yield fake
    app.state.external_api_client = original


def _fetch(client, profile="https://steamcommunity.com/id/gladosfan/"):
    return client.post("/import-studio/steam/library/", json={"profile": profile})


def _upload(document, threshold=60):
    payload = json.dumps({**document, "played_after_minutes": threshold}).encode()
    return {"file": (f"steam-{document.get('steam_id', 'x')}.json", payload, "application/json")}


def _preview_and_apply(client, document, threshold=60):
    preview = client.post("/import-studio/preview/", files=_upload(document, threshold), data={"source": "steam"})
    assert preview.status_code == 200, preview.text
    applied = client.post("/import-studio/apply/", files=_upload(document, threshold),
                          data={"source": "steam", "fingerprint_confirmation": preview.json()["fingerprint"]})
    assert applied.status_code == 200, applied.text
    return preview.json(), applied.json()


# ---------------------------------------------------------------- profile parsing

@pytest.mark.parametrize("text, expected", [
    (STEAM_ID, ("id", STEAM_ID)),
    (f"https://steamcommunity.com/profiles/{STEAM_ID}/", ("id", STEAM_ID)),
    (f"steamcommunity.com/profiles/{STEAM_ID}", ("id", STEAM_ID)),
    ("https://steamcommunity.com/id/gladosfan/", ("vanity", "gladosfan")),
    ("http://www.steamcommunity.com/id/Glados_Fan-2?l=english", ("vanity", "Glados_Fan-2")),
    ("  gladosfan  ", ("vanity", "gladosfan")),
])
def test_profiles_are_read_from_links_ids_and_names(text, expected):
    assert steam.parse_profile(text) == expected


@pytest.mark.parametrize("text", [
    "https://evil.example/id/gladosfan/",
    "https://steamcommunity.com.evil.example/id/gladosfan/",
    "https://steamcommunity.com/id/../../admin/",
    "https://steamcommunity.com/profiles/12345/",
    "https://steamcommunity.com/groups/somegroup/",
    "glados fan",
    "a",
    "x" * 300,
    "file:///etc/passwd",
])
def test_anything_else_is_refused_before_steam_is_called(text):
    with pytest.raises(steam.SteamError) as error:
        steam.parse_profile(text)
    assert error.value.status == 400


# ---------------------------------------------------------------- the Steam calls

def test_steam_is_hidden_without_a_key(authenticated_client, monkeypatch):
    monkeypatch.delenv("STEAM_WEB_API_KEY", raising=False)
    assert authenticated_client.get("/import-studio/steam/").json() == {"enabled": False}
    response = _fetch(authenticated_client)
    assert response.status_code == 503
    assert "isn't set up" in response.json()["detail"]


def test_status_and_library_need_sign_in(client, steam_key):
    assert client.get("/import-studio/steam/").status_code == 401
    assert _fetch(client).status_code == 401


def test_library_resolves_a_vanity_name_and_only_calls_fixed_steam_paths(authenticated_client, steam_key, fake_steam):
    response = _fetch(authenticated_client)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["source"] == "steam" and data["steam_id"] == STEAM_ID and data["persona"] == "Glados Fan"
    assert [game["name"] for game in data["games"]] == ["Portal 2", "Hades", "Stardew Valley"]  # most played first
    assert data["games"][0] == {"appid": 620, "name": "Portal 2", "minutes": 900, "last_played": "2023-11-14"}
    assert data["truncated"] is False
    for request in fake_steam.requests:
        assert request.url.scheme == "https" and request.url.host == "api.steampowered.com"
        assert request.url.path in steam.PATHS.values()
        assert request.url.params["key"] == "test-key"
    assert "test-key" not in response.text


def test_a_steam_id_skips_the_vanity_lookup(authenticated_client, steam_key, fake_steam):
    assert _fetch(authenticated_client, STEAM_ID).status_code == 200
    assert steam.PATHS["resolve"] not in [request.url.path for request in fake_steam.requests]


def test_unknown_vanity_name_says_so(authenticated_client, steam_key, fake_steam):
    fake_steam.vanity_ok = False
    response = _fetch(authenticated_client)
    assert response.status_code == 404
    assert "no profile" in response.json()["detail"]


def test_private_game_details_explain_the_setting(authenticated_client, steam_key, fake_steam):
    fake_steam.owned = {"response": {}}
    response = _fetch(authenticated_client)
    assert response.status_code == 404
    assert "Game details to Public" in response.json()["detail"]


def test_steam_errors_become_plain_messages(authenticated_client, steam_key, fake_steam):
    fake_steam.status = 403
    response = _fetch(authenticated_client)
    assert response.status_code == 503 and "isn't working" in response.json()["detail"]
    fake_steam.status = 500
    assert _fetch(authenticated_client).status_code == 502


def test_bad_game_entries_are_dropped_and_minutes_capped():
    games = steam._games({"response": {"games": [
        {"appid": 1, "name": "Fine", "playtime_forever": 10 ** 9},
        {"appid": "2", "name": "String id"}, {"appid": 3, "name": "   "}, {"appid": 1, "name": "Repeat"},
        "nonsense",
    ]}})
    assert games == [{"appid": 1, "name": "Fine", "minutes": steam.MAX_MINUTES, "last_played": None}]


# ---------------------------------------------------------------- the Import Studio path

DOCUMENT = {"source": "steam", "steam_id": STEAM_ID, "persona": "Glados Fan", "games": [
    {"appid": 620, "name": "Portal 2", "minutes": 900},
    {"appid": 1145360, "name": "Hades", "minutes": 30},
    {"appid": 413150, "name": "Stardew Valley", "minutes": 0},
]}


def test_import_adds_games_with_covers_played_state_and_hours(authenticated_client, db_session):
    preview, applied = _preview_and_apply(authenticated_client, DOCUMENT)
    assert preview["detected_source"] == "steam" and preview["ready_count"] == 3
    portal = next(row for row in preview["preview"] if row["title"] == "Portal 2")
    assert portal["values"]["playtime_minutes"] == 900
    assert portal["values"]["store_url"] == "https://store.steampowered.com/app/620/"
    assert applied["created_count"] == 3 and applied["playtime_count"] == 3

    games = {game.title: game for game in db_session.query(models.VideoGame).all()}
    assert games["Portal 2"].played is True
    assert games["Hades"].played is False  # 30 minutes is under the one hour default
    assert games["Portal 2"].cover_art_url == "https://cdn.akamai.steamstatic.com/steam/apps/620/header.jpg"
    hours = {row.item_id: (row.minutes, row.external_id) for row in db_session.query(models.GamePlaytime)}
    assert hours[games["Portal 2"].id] == (900, "620")


def test_threshold_choices_change_what_counts_as_played(authenticated_client, db_session):
    _preview_and_apply(authenticated_client, DOCUMENT, threshold=1)
    assert {game.title for game in db_session.query(models.VideoGame).filter_by(played=True)} == {"Portal 2", "Hades"}


def test_never_marks_nothing_as_played(authenticated_client, db_session):
    _preview_and_apply(authenticated_client, DOCUMENT, threshold=None)
    assert db_session.query(models.VideoGame).filter_by(played=True).count() == 0


def test_reimport_keeps_entries_and_refreshes_hours(authenticated_client, db_session):
    user = db_session.query(models.User).first()
    mine = models.VideoGame(user_id=user.id, title="Portal 2", rating=9.5, review="Wheatley!", played=True)
    db_session.add(mine)
    db_session.commit()

    preview, applied = _preview_and_apply(authenticated_client, DOCUMENT)
    assert preview["duplicate_count"] == 1 and preview["playtime_refresh_count"] == 1
    assert applied["created_count"] == 2
    db_session.refresh(mine)
    assert (mine.rating, mine.review) == (9.5, "Wheatley!")
    assert game_playtime.minutes_by_game(db_session, user.id)[mine.id] == 900

    # Every row is a duplicate now, but the preview still reports work so the member can refresh hours.
    later = {**DOCUMENT, "games": [{"appid": 620, "name": "Portal 2", "minutes": 1200}]}
    preview_again, again = _preview_and_apply(authenticated_client, later)
    assert preview_again["ready_count"] == 0 and preview_again["playtime_refresh_count"] == 1
    assert again["created_count"] == 0 and again["playtime_count"] == 1
    assert game_playtime.minutes_by_game(db_session, user.id)[mine.id] == 1200
    assert db_session.query(models.GamePlaytime).count() == 3


def test_forged_minutes_are_capped_and_bad_rows_skipped(authenticated_client, db_session):
    document = {"source": "steam", "steam_id": STEAM_ID, "games": [
        {"appid": 9, "name": "Forever", "minutes": 10 ** 12}, {"appid": -1, "name": "Negative"},
        {"appid": 10, "name": ""}, {"appid": 11, "name": "Text minutes", "minutes": "lots"},
    ]}
    preview, _ = _preview_and_apply(authenticated_client, document)
    assert preview["ready_count"] == 2
    assert max(row.minutes for row in db_session.query(models.GamePlaytime)) == game_playtime.MAX_MINUTES


def test_a_steam_file_is_refused_under_another_source(authenticated_client):
    response = authenticated_client.post("/import-studio/preview/", files=_upload(DOCUMENT), data={"source": "trakt"})
    assert response.status_code == 400 and "Steam" in response.json()["detail"]


def test_one_member_cannot_touch_anothers_hours(authenticated_client, db_session):
    other = models.User(username="other", email="other@example.com", hashed_password="x", is_verified=True)
    db_session.add(other)
    db_session.commit()
    theirs = models.VideoGame(user_id=other.id, title="Portal 2", played=True)
    db_session.add(theirs)
    db_session.commit()
    preview, _ = _preview_and_apply(authenticated_client, DOCUMENT)
    assert preview["playtime_refresh_count"] == 0
    assert game_playtime.minutes_by_game(db_session, other.id) == {}


# ---------------------------------------------------------------- time spent, deletion, exports

def test_time_spent_uses_steam_hours_even_for_unplayed_games(authenticated_client, db_session):
    _preview_and_apply(authenticated_client, DOCUMENT)
    user = db_session.query(models.User).first()
    row = next(row for row in time_spent.estimate(db_session, user, today=date(2026, 10, 30))["categories"]
               if row["category"] == "video-games")
    assert row["minutes"] == 930 and row["measured"] == 2 and row["typical"] == 0
    assert row["finished"] == 1


def test_deleting_a_game_deletes_its_hours(authenticated_client, db_session):
    _preview_and_apply(authenticated_client, DOCUMENT)
    portal = db_session.query(models.VideoGame).filter_by(title="Portal 2").one()
    assert authenticated_client.delete(f"/video-games/{portal.id}").status_code == 200
    assert db_session.query(models.GamePlaytime).filter_by(item_id=portal.id).count() == 0


def test_backup_round_trip_restores_hours(authenticated_client, db_session):
    _preview_and_apply(authenticated_client, DOCUMENT)
    backup = authenticated_client.get("/export/").json()
    assert backup["export_metadata"]["total_game_playtimes"] == 3
    portal = next(row for row in backup["game_playtimes"] if row["title"] == "Portal 2")
    assert (portal["source"], portal["external_id"], portal["minutes"]) == ("steam", "620", 900)

    db_session.query(models.GamePlaytime).delete()
    db_session.commit()
    result = authenticated_client.post("/import/", json=backup).json()
    assert (result["playtimes_created"], result["playtimes_skipped"]) == (3, 0)
    again = authenticated_client.post("/import/", json=backup).json()
    assert (again["playtimes_created"], again["playtimes_skipped"]) == (0, 3)


def test_backup_import_ignores_bad_playtime_rows(authenticated_client, db_session):
    result = authenticated_client.post("/import/", json={"game_playtimes": [
        {"title": "Nope", "source": "steam", "minutes": 5}, {"title": "Portal 2", "source": "xbox", "minutes": 5},
        {"title": "Portal 2", "source": "steam", "minutes": -1}, {"title": "Portal 2", "minutes": "5"},
    ]}).json()
    assert (result["playtimes_created"], result["playtimes_skipped"]) == (0, 4)


def test_spreadsheet_export_has_a_playtime_file(authenticated_client):
    _preview_and_apply(authenticated_client, DOCUMENT)
    response = authenticated_client.get("/export/spreadsheet/")
    assert response.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    text = archive.read("playtime.csv").decode("utf-8-sig")
    assert "title,source,hours_played,synced_at" in text and "Portal 2,steam,15.0," in text
    assert "playtime.csv" in archive.read("README.txt").decode("utf-8-sig")


def test_switch_guide_explains_steam_and_the_studio_hides_it_until_checked(client):
    page = client.get("/switch").text
    assert 'id="steam-heading"' in page and 'href="#steam-heading"' in page
    markup = (Path(__file__).resolve().parents[1] / "app" / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'id="importStudioSteam" hidden' in markup and 'id="importStudioSteamOption" hidden disabled' in markup
