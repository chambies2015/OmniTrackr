"""Seasonal hubs (/halloween): hand-written picks by fright level, member progress and the dashboard card (Oct 2026)."""
import re
from datetime import date
from pathlib import Path

import pytest

from app import funnel, models, pick, seasonal, title_pages, title_search
from app.auth import AUTH_COOKIE_NAME
from app.seasonal_guides import SEASONS

HALLOWEEN = SEASONS["halloween"]


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


@pytest.fixture
def in_season(monkeypatch):
    monkeypatch.setattr(seasonal, "current", lambda today=None: "halloween")


def words(entry):
    texts = entry["intro"] + entry["method"] + [night["plan"] for night in entry["nights"]]
    texts += [question + " " + answer for question, answer in entry["faq"]]
    for shelf in entry["shelves"]:
        texts += shelf["intro"]
        texts += [item["why"] + " " + item["note"] + " " + item["caveat"] for item in shelf["picks"]]
    return sum(len(text.split()) for text in texts)


def test_every_season_is_complete_and_substantial():
    for slug, entry in SEASONS.items():
        assert re.fullmatch(r"/[a-z0-9-]{1,40}", entry["path"]) and entry["theme"]
        assert 60 <= len(entry["summary"]) <= 200 and entry["search_title"] and entry["card"]
        assert words(entry) >= 3000, slug
        for value in entry["window"]:
            date(2026, *map(int, value.split("-")))
        assert [value for value, _, _ in entry["scale"]] == [1, 2, 3, 4, 5]
        assert len(entry["faq"]) >= 4 and len(entry["nights"]) >= 4
        seen = set()
        for shelf in entry["shelves"]:
            assert re.fullmatch(r"[a-z0-9-]{1,40}", shelf["key"])
            # One pick in every format OmniTrackr tracks, per shelf.
            assert sorted(item["kind"] for item in shelf["picks"]) == sorted(title_pages.KINDS)
            for item in shelf["picks"]:
                assert 1 <= item["fright"] <= 5 and 1800 < item["year"] < 2030
                assert item["title"] and item["time"] and item["why"] and item["note"] and item["caveat"]
                key = (item["kind"], title_pages.slugify(item["title"]))
                assert key not in seen
                seen.add(key)


def test_halloween_does_not_repeat_the_october_edition():
    from app.discover_catalog import MONTHLY_EDITIONS
    october = {title_pages.slugify(item["title"]) for item in MONTHLY_EDITIONS["october-2026"]["items"]}
    assert not october & {title_pages.slugify(item["title"]) for item in seasonal.picks(HALLOWEEN)}


def test_every_pick_joins_pick_for_me_so_it_can_be_saved():
    for item in seasonal.picks(HALLOWEEN):
        pooled = seasonal.pool_entry(item)
        assert pooled is not None, item["title"]
        assert pick.find_id(pooled["id"]) is pooled
    phasmo = pick.find("game", "phasmophobia-2020")
    assert phasmo["source_label"] == "Halloween picks" and phasmo["source_url"] == "/halloween#with-friends"


def test_the_window_runs_through_halloween_only():
    assert seasonal.in_window(HALLOWEEN, date(2026, 10, 1)) and seasonal.in_window(HALLOWEEN, date(2026, 11, 2))
    assert not seasonal.in_window(HALLOWEEN, date(2026, 9, 30)) and not seasonal.in_window(HALLOWEEN, date(2026, 11, 3))
    assert seasonal.current(date(2027, 10, 31)) == "halloween" and seasonal.current(date(2026, 7, 4)) is None
    assert seasonal.days_left(HALLOWEEN, date(2026, 10, 19)) == 14


def test_hub_reads_completely_without_an_account(client):
    response = client.get("/halloween")
    assert response.status_code == 200
    html = response.text
    assert '<meta name="robots" content="index, follow' in html
    assert '<link rel="canonical" href="https://omnitrackr.xyz/halloween">' in html
    assert "<h1>Halloween, at your own fright level</h1>" in html
    for shelf in HALLOWEEN["shelves"]:
        assert f'id="{shelf["key"]}"' in html
    for item in seasonal.picks(HALLOWEEN):
        assert f'id="{seasonal.anchor_id(item)}"' in html
    assert html.count("Save to my list") == 24 and "data-season-add" not in html
    assert 'data-guest-kind="game" data-guest-slug="alien-isolation-2014"' in html
    assert "Fright 5 of 5 · Lights on afterwards" in html
    assert "Five kinds of Halloween night" in html and "How we chose" in html
    assert '"FAQPage"' in html and '"ItemList"' in html
    assert "/static/ad-loader.js" in html and "/static/guest-list.js" in html and "/static/seasonal.js" in html
    assert 'href="/discover/monthly/october-2026"' in html
    assert "data-season-progress" not in html
    assert "Cookie" in response.headers["vary"]


def test_members_get_add_buttons_progress_and_no_ads(client):
    client.cookies.set(AUTH_COOKIE_NAME, "anything")
    html = client.get("/halloween").text
    assert html.count("data-season-add=") == 24 and html.count("data-season-add-shelf=") == 4
    assert 'data-season-progress="halloween"' in html
    assert "/static/ad-loader.js" not in html and "/static/guest-list.js" not in html


def test_member_adds_a_shelf_and_sees_progress(authenticated_client, db_session, monkeypatch):
    recorded = []
    monkeypatch.setattr(funnel, "record", lambda event, request=None: recorded.append(event))
    user = db_session.query(models.User).filter_by(username="testuser").one()
    # An existing copy, finished and rated, stays exactly as it is.
    db_session.add(models.Movie(user_id=user.id, title="the others", director="Someone", year=2001, watched=True, rating=9))
    db_session.commit()
    shelf = HALLOWEEN["shelves"][0]
    ids = [seasonal.pool_entry(item)["id"] for item in shelf["picks"]]

    before = authenticated_client.get("/api/seasonal/halloween/progress").json()
    assert before["total"] == 24 and before["tracked"] == 1 and before["done"] == 1
    assert before["entries"]["movie/the-others-2001"]["state"] == "done"

    body = authenticated_client.post("/api/seasonal/halloween/add", json={"ids": ids}).json()
    assert [item["title"] for item in body["existing"]] == ["The Others"]
    assert len(body["added"]) == 5 and body["progress"]["tracked"] == 6
    assert recorded == ["seasonal_saved"]
    others = db_session.query(models.Movie).filter_by(user_id=user.id).all()
    assert len(others) == 1 and others[0].title == "the others" and others[0].rating == 9
    book = db_session.query(models.Book).filter_by(title="Mexican Gothic").one()
    assert book.author == "Silvia Moreno-Garcia" and book.year == 2020 and not book.read

    # Adding again changes nothing.
    again = authenticated_client.post("/api/seasonal/halloween/add", json={"ids": ids[:2]}).json()
    assert again["added"] == [] and len(again["existing"]) == 2
    assert authenticated_client.post("/api/seasonal/halloween/add", json={"ids": ["movie/not-a-pick"]}).status_code == 404
    assert authenticated_client.post("/api/seasonal/winter/add", json={"ids": ids}).status_code == 404
    assert authenticated_client.post("/api/seasonal/halloween/add", json={"ids": []}).status_code == 422


def test_seasonal_api_needs_an_account(client):
    assert client.get("/api/seasonal/current").status_code == 401
    assert client.get("/api/seasonal/halloween/progress").status_code == 401
    assert client.post("/api/seasonal/halloween/add", json={"ids": ["movie/the-others-2001"]}).status_code == 401


def test_dashboard_card_appears_only_in_season(authenticated_client, monkeypatch):
    monkeypatch.setattr(seasonal, "current", lambda today=None: None)
    assert authenticated_client.get("/api/seasonal/current").json() == {"season": None}
    monkeypatch.setattr(seasonal, "current", lambda today=None: "halloween")
    body = authenticated_client.get("/api/seasonal/current").json()
    assert body["season"] == "halloween" and body["path"] == "/halloween" and body["theme"] == "halloween"
    assert body["total"] == 24 and body["tracked"] == 0 and len(body["shelves"]) == 4
    assert "no-store" in authenticated_client.get("/api/seasonal/current").headers["cache-control"]


def test_pick_for_me_counts_seasonal_saves_separately(authenticated_client, monkeypatch):
    recorded = []
    monkeypatch.setattr(funnel, "record", lambda event, request=None: recorded.append(event))
    body = authenticated_client.post("/api/pick/add", json={"id": "album/thriller-1982", "source": "seasonal"}).json()
    assert body["state"] == "created" and recorded == ["seasonal_saved"]
    assert "seasonal_saved" in funnel.CLIENT_EVENTS


def test_a_guest_saved_seasonal_pick_moves_into_the_new_library(authenticated_client, db_session):
    response = authenticated_client.post("/api/guest-list/import", json={"items": [
        {"kind": "game", "slug": "luigi-s-mansion-3-2019"}]})
    assert [item["title"] for item in response.json()["added"]] == ["Luigi's Mansion 3"]


def test_hub_is_linked_from_the_sitemap_guides_and_discover(client, in_season):
    assert "https://omnitrackr.xyz/halloween</loc>" in client.get("/sitemap.xml").text
    assert 'href="/halloween"' in client.get("/site-map").text
    assert 'href="/halloween"' in client.get("/discover").text
    assert "/halloween" in client.get("/llms.txt").text
    loader = (Path(__file__).parents[1] / "app" / "static" / "ad-loader.js").read_text(encoding="utf-8")
    assert "'/halloween'" in loader


def test_dashboard_has_the_season_card_and_hooks():
    root = Path(__file__).parents[1] / "app"
    index = (root / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'id="seasonCard"' in index and "/static/seasonal-card.js" in index and "/static/seasonal-card.css" in index
    auth = (root / "static" / "auth.js").read_text(encoding="utf-8")
    assert "window.refreshSeasonCard?.()" in auth and auth.count("window.resetSeasonCard?.()") == 2
