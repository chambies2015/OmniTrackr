"""Nov 28 2026 sweep of the top nine maker (PR #349)."""
import unicodedata
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app import models, top_nine, top_nine_card
from app.main import app
from app.routers import top_nine as top_nine_router
from tests.test_top_nine import grid

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
ZALGO = "Z" + "\u0336\u0321\u031b\u0316\u0317\u0318\u0300\u0301\u0302\u0303" * 3


def test_control_characters_direction_overrides_and_stacked_marks_are_cleaned(client, db_session):
    payload = grid(name="\u202eevil\x00 " + ZALGO)
    payload["tiles"][0]["title"] = "Du\u2066ne\x07"
    made = client.post("/api/top-nine", json=payload)
    assert made.status_code == 200, made.text
    row = db_session.query(models.TopNine).one()
    assert row.name.startswith("evil Z")
    assert not any(char in row.name for char in "\u202e\x00")
    assert sum(1 for char in row.name if unicodedata.category(char) == "Mn") == top_nine.MAX_MARKS
    assert top_nine.tiles_of(row)[0]["title"] == "Dune"
    # Real accents and tone marks stay.
    assert top_nine.tidy("Pok\u00e9mon Ti\u1ebfng Vi\u1ec7t \u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35") == "Pok\u00e9mon Ti\u1ebfng Vi\u1ec7t \u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35"


def test_ad_phrases_are_refused_but_song_titles_are_not(client):
    refused = client.post("/api/top-nine", json=grid(name="Best online casino bonus"))
    assert refused.status_code == 400 and "ad" in refused.json()["detail"]
    payload = grid()
    payload["tiles"][1]["title"] = "Telegram channel for free films"
    assert client.post("/api/top-nine", json=payload).status_code == 400
    payload = grid()
    payload["tiles"][1] = {"title": "Work from Home", "kind": "album", "year": 2016}
    assert client.post("/api/top-nine", json=payload).status_code == 200


def test_pictures_leave_out_characters_the_font_cannot_draw():
    assert top_nine_card._ink("My 2026 \U0001f3ac\U0001f37f") == "My 2026"
    assert top_nine_card._ink("\u202eevil") == "evil"
    assert top_nine_card._ink("Pok\u00e9mon \u2605") == "Pok\u00e9mon \u2605"
    assert top_nine_card._name({"name": "\U0001f525\U0001f525", "year": 2026}) == "My 2026"
    tiles = [{"title": title, "kind": "movie", "year": 2020} for title in
             ("\u6771\u4eac\u7269\u8a9e", ZALGO, "\U0001f3ac", "Heat")]
    data = {"year": 2026, "name": ZALGO, "theme": "paper", "tiles": tiles + [None] * 5}
    for render in top_nine_card.RENDERERS.values():
        Image.open(BytesIO(render(data, {}))).verify()


def test_only_a_members_own_grid_opens_for_changes(authenticated_client, db_session):
    made = authenticated_client.post("/api/top-nine", json=grid()).json()
    assert authenticated_client.get(f"/api/top-nine/{made['token']}").json()["yours"] is True
    with TestClient(app) as other:
        assert other.get(f"/api/top-nine/{made['token']}").json()["yours"] is False
        guest_made = other.post("/api/top-nine", json=grid()).json()
    assert authenticated_client.get(f"/api/top-nine/{guest_made['token']}").json()["yours"] is False
    script = (STATIC / "top-nine.js").read_text(encoding="utf-8")
    assert "grid.yours || (key && !grid.member)" in script
    assert "if (grid && (signedIn || key))" not in script


def test_long_names_wrap_on_the_shared_page():
    css = (STATIC / "top-nine.css").read_text(encoding="utf-8")
    assert ".tn-shared__head h1, .tn-list__items strong, .tn-list__items span, .tn-mine__text strong { overflow-wrap: anywhere; }" in css


def test_the_maker_no_longer_promises_year_in_review_counts(client):
    page = client.get("/top-nine").text
    assert "Year in Review counts them" not in page
    assert "go into your library as finished" in page
    assert f"top-nine.css?v={top_nine_router.CSS_VERSION}" in page and top_nine_router.CSS_VERSION >= "20261128-top-nine-sweep-1"
    assert f"top-nine.js?v={top_nine_router.JS_VERSION}" in page and top_nine_router.JS_VERSION >= "20261128-top-nine-sweep-1"


def test_pictures_stay_in_shared_caches_for_ten_minutes(client):
    made = client.post("/api/top-nine", json=grid()).json()
    picture = client.get(f"{made['path']}/card.png")
    assert picture.status_code == 200 and picture.headers["cache-control"] == "public, max-age=600"
