""""In order" guides (/in-order): the best order through a franchise, with member progress (Oct 2026)."""
import re
from datetime import datetime

import pytest

from app import funnel, in_order, models, title_pages, title_search
from app.auth import AUTH_COOKIE_NAME
from app.in_order_guides import GUIDES


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


def words(entry):
    texts = entry["lead"] + entry["start"] + [q + " " + a for q, a in entry["faq"]]
    texts += [order["pitch"] for order in entry["orders"]] + [item["note"] for item in entry["entries"]]
    return sum(len(text.split()) for text in texts)


def member(db_session, username="testuser"):
    return db_session.query(models.User).filter_by(username=username).one()


def test_every_guide_is_complete_and_substantial():
    assert len(GUIDES) >= 10
    for slug, entry in GUIDES.items():
        assert re.fullmatch(r"[a-z0-9-]{1,80}", slug)
        assert entry["name"] and entry["search_title"] and len(entry["lead"]) >= 2 and entry["start"]
        assert 60 <= len(entry["summary"]) <= 170, slug
        assert len(entry["faq"]) >= 3 and entry["orders"]
        assert words(entry) >= 600, slug
        ids = [item["id"] for item in entry["entries"]]
        assert len(ids) == len(set(ids)), slug
        saveable = set()
        for item in entry["entries"]:
            assert re.fullmatch(r"[a-z0-9-]{1,60}", item["id"])
            assert item["kind"] in title_pages.KINDS and item["title"] and item["note"]
            assert 1900 < item["year"] < 2030
            fields = in_order.saveable(item)
            assert fields["id"] not in saveable, (slug, item["id"])
            saveable.add(fields["id"])
        for order in entry["orders"]:
            assert order["key"] and order["name"] and order["pitch"]
            assert len(order["ids"]) == len(set(order["ids"])) and set(order["ids"]) <= set(ids), (slug, order["key"])
        # Every entry appears in at least one order and the recommended order covers every main entry.
        assert set(ids) == set().union(*(order["ids"] for order in entry["orders"])), slug
        assert {item["id"] for item in in_order.core(entry)} <= set(entry["orders"][0]["ids"]), slug


def test_release_orders_follow_release_years():
    for slug, entry in GUIDES.items():
        by_id = in_order.entries(entry)
        for order in entry["orders"]:
            if order["key"] != "release":
                continue
            years = [by_id[item_id]["year"] for item_id in order["ids"]]
            assert years == sorted(years), slug


def test_guide_page_reads_completely_without_an_account(client):
    response = client.get("/in-order/star-wars")
    assert response.status_code == 200
    html = response.text
    entry = GUIDES["star-wars"]
    assert '<meta name="robots" content="index, follow' in html
    assert '<link rel="canonical" href="https://omnitrackr.xyz/in-order/star-wars">' in html
    assert "<title>Star Wars in order" in html and "<h1>Star Wars in order</h1>" in html
    for order in entry["orders"]:
        assert f'id="order-{order["key"]}"' in html and order["name"] in html
    for item in entry["entries"]:
        assert f'id="entry-{item["id"]}"' in html
    assert "Where to start" in html and "Questions" in html and "How we chose" in html
    assert html.count("Save to my list") == len(entry["entries"])
    assert 'data-guest-kind="movie" data-guest-slug="rogue-one-a-star-wars-story-2016"' in html
    assert "data-io-guest-all" in html and f"Save all {len(in_order.core(entry))} to my list" in html
    assert "data-guest-bar" in html and "/static/guest-list.js" in html and "/static/in-order.js" in html
    assert "/static/ad-loader.js" in html and "data-io-progress=" not in html
    assert '"@type": "Article"' in html and '"ItemList"' in html
    assert html.count('href="/in-order/') >= 3 and 'href="/in-order"' in html
    assert "Cookie" in response.headers["vary"]
    # Optional entries are labeled and left out of "Save all".
    assert 'class="pick io-entry is-optional" id="entry-solo"' in html


def test_members_get_add_buttons_progress_and_no_ads(client):
    client.cookies.set(AUTH_COOKIE_NAME, "anything")
    html = client.get("/in-order/dune").text
    assert html.count("data-io-add=") == len(GUIDES["dune"]["entries"])
    assert 'data-io-progress="dune"' in html
    assert "data-guest-bar" not in html and "/static/guest-list.js" not in html
    assert "/static/ad-loader.js" not in html


def test_unknown_guides_are_not_found(client, authenticated_client):
    assert client.get("/in-order/not-a-guide").status_code == 404
    assert authenticated_client.get("/api/in-order/not-a-guide/progress").status_code == 404


def test_hub_lists_every_guide(client):
    response = client.get("/in-order")
    assert response.status_code == 200
    for slug in GUIDES:
        assert f'href="/in-order/{slug}"' in response.text
    assert "public" in response.headers["cache-control"]


def test_progress_needs_an_account(client):
    assert client.get("/api/in-order/star-wars/progress").status_code == 401
    assert client.post("/api/in-order/star-wars/add", json={"ids": ["andor"]}).status_code == 401


def test_progress_is_read_from_the_members_library(authenticated_client, db_session):
    user = member(db_session)
    db_session.add_all([
        # Saved under a short title, finished.
        models.Movie(user_id=user.id, title="Star Wars", director="George Lucas", year=1977, watched=True),
        models.Movie(user_id=user.id, title="the empire strikes back ", year=1980, watched=True),
        models.Movie(user_id=user.id, title="Star Wars: Episode VI - Return of the Jedi", year=1983, watched=False),
        models.TVShow(user_id=user.id, title="Andor", year=2022, watched=True),
    ])
    db_session.commit()
    progress = authenticated_client.get("/api/in-order/star-wars/progress").json()
    assert progress["entries"]["a-new-hope"]["state"] == "done"
    assert progress["entries"]["empire-strikes-back"]["state"] == "done"
    assert progress["entries"]["return-of-the-jedi"]["state"] == "tracked"
    assert progress["entries"]["return-of-the-jedi"]["library_url"].startswith("/?library_category=movies&library_item=")
    total = len(in_order.core(GUIDES["star-wars"]))
    # Andor is optional, so it shows as finished but does not count toward the total.
    assert progress["entries"]["andor"]["state"] == "done"
    assert progress["done"] == 2 and progress["total"] == total and progress["tracked"] == 3
    assert progress["next"] == {"id": "return-of-the-jedi", "title": "Star Wars: Episode VI - Return of the Jedi"}
    assert "a-new-hope" not in progress["missing"] and "return-of-the-jedi" not in progress["missing"]
    assert "andor" not in progress["missing"] and "solo" not in progress["missing"]


def test_a_remake_with_the_same_title_is_not_counted(authenticated_client, db_session):
    user = member(db_session)
    db_session.add(models.Movie(user_id=user.id, title="Dune", director="David Lynch", year=1984, watched=True))
    db_session.add(models.VideoGame(user_id=user.id, title="The Witcher 3: Wild Hunt", release_date=datetime(2015, 5, 19), played=True))
    db_session.commit()
    dune = authenticated_client.get("/api/in-order/dune/progress").json()
    assert "part-one" not in dune["entries"] and dune["entries"]["lynch"]["state"] == "done"
    witcher = authenticated_client.get("/api/in-order/the-witcher/progress").json()
    assert witcher["entries"]["witcher-3"]["state"] == "done"


def test_member_adds_the_missing_entries_without_touching_existing_ones(authenticated_client, db_session, monkeypatch):
    recorded = []
    monkeypatch.setattr(funnel, "record", lambda event, request=None: recorded.append(event))
    user = member(db_session)
    db_session.add(models.Movie(user_id=user.id, title="Alien", director="Ridley Scott", year=1979, watched=True, rating=9.5))
    db_session.commit()
    missing = authenticated_client.get("/api/in-order/alien/progress").json()["missing"]
    assert "alien" not in missing and "aliens" in missing and "isolation" not in missing
    body = authenticated_client.post("/api/in-order/alien/add", json={"ids": missing + ["alien"]}).json()
    assert {item["id"] for item in body["added"]} == set(missing)
    assert [item["id"] for item in body["existing"]] == ["alien"]
    assert body["progress"]["missing"] == [] and body["progress"]["tracked"] == body["progress"]["total"]
    assert recorded == ["order_saved"]
    original = db_session.query(models.Movie).filter_by(user_id=user.id, title="Alien").one()
    assert original.watched and original.rating == 9.5
    added = db_session.query(models.Movie).filter_by(user_id=user.id, title="Aliens").one()
    assert not added.watched and added.rating is None and added.director == "James Cameron" and added.year == 1986
    # Adding again creates nothing.
    again = authenticated_client.post("/api/in-order/alien/add", json={"ids": ["aliens"]}).json()
    assert again["added"] == [] and recorded == ["order_saved"]
    assert db_session.query(models.Movie).filter_by(user_id=user.id, title="Aliens").count() == 1


def test_add_rejects_unknown_or_too_many_entries(authenticated_client):
    assert authenticated_client.post("/api/in-order/alien/add", json={"ids": ["not-an-entry"]}).status_code == 404
    assert authenticated_client.post("/api/in-order/alien/add", json={"ids": []}).status_code == 422
    assert authenticated_client.post("/api/in-order/alien/add", json={"ids": ["alien"] * 41}).status_code == 422


def test_a_guest_saved_entry_moves_into_the_new_library(authenticated_client, db_session):
    response = authenticated_client.post("/api/guest-list/import", json={"items": [
        {"kind": "book", "slug": "the-last-wish-1993"}, {"kind": "anime", "slug": "bakemonogatari-2009"}]})
    assert sorted(item["title"] for item in response.json()["added"]) == ["Bakemonogatari", "The Last Wish"]
    book = db_session.query(models.Book).filter_by(title="The Last Wish").one()
    assert book.author == "Andrzej Sapkowski" and book.year == 1993 and not book.read
    assert in_order.find("book", "not-a-book") is None


def test_title_pages_link_to_the_guides_that_include_them():
    from app.routers.titles import _in_order_html

    class Group:
        kind, title, year = "movie", "Rogue One: A Star Wars Story", 2016

    section = _in_order_html(Group())
    assert 'href="/in-order/star-wars#entry-rogue-one"' in section and "#9 of 14 in the order we recommend" in section

    class Remake:
        kind, title, year = "movie", "Dune", 2021

    assert 'href="/in-order/dune#entry-part-one"' in _in_order_html(Remake())

    class Other:
        kind, title, year = "book", "Rogue One: A Star Wars Story", 2016

    assert _in_order_html(Other()) == ""


def test_guides_are_in_the_sitemap_navigation_and_ad_allowlist(client):
    from pathlib import Path
    from app.site_chrome import FOOTER_GROUPS
    sitemap = client.get("/sitemap.xml").text
    assert "https://omnitrackr.xyz/in-order</loc>" in sitemap
    for slug in GUIDES:
        assert f"https://omnitrackr.xyz/in-order/{slug}</loc>" in sitemap
    assert ("Franchises in order", "/in-order") in dict(FOOTER_GROUPS)["Explore"]
    static = Path(__file__).parents[1] / "app" / "static"
    assert "in-order" in (static / "ad-loader.js").read_text(encoding="utf-8")
    assert "\\/in-order\\/" in (static / "auth.js").read_text(encoding="utf-8")
    assert "/in-order" in client.get("/llms.txt").text
    assert 'href="/in-order"' in client.get("/site-map").text
    assert "order_saved" in funnel.CLIENT_EVENTS and "order_saved" in funnel.SERVER_EVENTS
