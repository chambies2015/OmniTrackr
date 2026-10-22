"""Pick for me (/pick): one curated suggestion at a time, saved to a guest list or a library (Oct 2026)."""
import random
import re
from datetime import date

import pytest

from app import funnel, models, pick, title_pages, title_search
from app.auth import AUTH_COOKIE_NAME


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


def test_pool_is_built_from_the_editorial_writing_with_one_entry_per_title():
    entries = pick.pool()
    assert len(entries) >= 80
    ids = [entry["id"] for entry in entries]
    assert len(ids) == len(set(ids))
    assert len({(e["kind"], title_pages.slugify(e["title"])) for e in entries}) == len(entries)
    assert {entry["kind"] for entry in entries} == set(pick.KIND_ORDER)
    for entry in entries:
        assert entry["why"].strip() and entry["source_label"].strip()
        assert entry["id"] == f"{entry['kind']}/{entry['slug']}"
        assert entry["slug"] == title_pages.title_slug(entry["title"], entry["year"])
        assert entry["source_url"] is None or entry["source_url"].startswith(("/discover/", "/if-you-liked/", "/halloween#", "/holidays#", "/best-of/"))
    arrival = pick.find("movie", "arrival-2016")
    assert arrival and arrival["creator"] == "Denis Villeneuve" and arrival["source_url"] == "/discover/distant-futures"
    assert pick.find_id("movie/arrival-2016") is arrival
    assert pick.find_id("nope/arrival-2016") is None and pick.find_id("") is None


def test_choose_respects_the_format_and_skips_recent_picks():
    rng = random.Random(7)
    books = pick.candidates("book")
    for _ in range(20):
        assert pick.choose("book", rng=rng)["kind"] == "book"
    recent = [entry["id"] for entry in books[:-1]]
    assert pick.choose("book", exclude=recent, rng=rng) is books[-1]
    # Once everything was shown recently, any pick in the format is fine again.
    assert pick.choose("book", exclude=[entry["id"] for entry in books], rng=rng)["kind"] == "book"
    assert pick.of_the_day(date(2026, 10, 12)) is pick.of_the_day(date(2026, 10, 12))


def test_public_page_is_indexable_and_complete_without_scripts(client):
    response = client.get("/pick")
    assert response.status_code == 200
    html = response.text
    assert '<meta name="robots" content="index, follow' in html
    assert '<link rel="canonical" href="https://omnitrackr.xyz/pick">' in html
    assert "Can't decide what to start?" in html or "Can&#x27;t decide what to start?" in html
    assert 'action="/pick" method="get"' in html and 'name="format"' in html
    assert 'id="pickCard"' in html and "Save to my list" in html and "data-guest-bar" in html
    assert "How to choose when everything sounds good" in html and "Where these picks come from" in html
    assert f"Every title we might pick ({len(pick.pool())})" in html
    assert "/static/pick-for-me.js?v=" in html and "/static/guest-list.js?v=" in html
    assert "Cookie" in response.headers["vary"]


def test_format_and_shared_links_choose_the_card_and_stay_out_of_search(client):
    html = client.get("/pick", params={"format": "game"}).text
    card = html[html.index('id="pickCard"'):html.index("</article>", html.index('id="pickCard"'))]
    assert re.search(r'data-pick-id="game/', card)
    assert "noindex" in html
    shared = client.get("/pick", params={"pick": "book/piranesi-2020"}).text
    assert 'data-pick-id="book/piranesi-2020"' in shared and "Piranesi" in shared
    # Unknown values fall back to a normal pick instead of an error.
    assert client.get("/pick", params={"format": "<x>", "pick": "movie/does-not-exist"}).status_code == 200


def test_pool_endpoint_serves_every_pick_with_public_details_only(client):
    response = client.get("/api/pick/pool")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=600"
    picks = response.json()["picks"]
    assert len(picks) == len(pick.pool())
    arrival = next(row for row in picks if row["id"] == "movie/arrival-2016")
    assert set(arrival) == {"id", "kind", "slug", "label", "title", "year", "creator", "why", "caveat", "source",
                            "sourceUrl", "url", "image"}
    assert arrival["sourceUrl"] == "/discover/distant-futures" and arrival["url"] is None


def test_signed_in_visitors_get_an_add_button_instead_of_the_guest_list(client):
    client.cookies.set(AUTH_COOKIE_NAME, "anything")
    html = client.get("/pick").text
    assert "data-pick-add=" in html and "Add to my library" in html
    assert "data-guest-bar" not in html and "/static/guest-list.js" not in html


def test_title_page_link_and_artwork_come_from_titles_members_track(client, db_session):
    user = models.User(username="ann", email="ann@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(models.Movie(user_id=user.id, title="Arrival", director="Denis Villeneuve", year=2016,
                                poster_url="https://img.example/arrival.jpg"))
    db_session.commit()
    details = pick.title_details(title_search.build_index(db_session))
    assert details["movie/arrival-2016"] == {"url": "/titles/movie/arrival-2016", "image": "https://img.example/arrival.jpg"}
    html = client.get("/pick", params={"pick": "movie/arrival-2016"}).text
    assert 'href="/titles/movie/arrival-2016"' in html and "https://img.example/arrival.jpg" in html
    # Picks nobody tracks get no title page link (it would be a 404).
    assert "/titles/book/piranesi-2020" not in client.get("/pick", params={"pick": "book/piranesi-2020"}).text


def test_member_adds_a_pick_to_their_library_once(authenticated_client, db_session):
    response = authenticated_client.post("/api/pick/add", json={"id": "movie/arrival-2016"})
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "created" and body["title"] == "Arrival" and body["category"] == "movies"
    movie = db_session.query(models.Movie).filter_by(title="Arrival").one()
    assert movie.director == "Denis Villeneuve" and movie.year == 2016 and not movie.watched and movie.rating is None
    assert body["library_url"] == f"/?library_category=movies&library_item={movie.id}"
    again = authenticated_client.post("/api/pick/add", json={"id": "movie/arrival-2016"}).json()
    assert again["state"] == "existing"
    assert db_session.query(models.Movie).filter_by(title="Arrival").count() == 1
    assert authenticated_client.post("/api/pick/add", json={"id": "movie/nope"}).status_code == 404


def test_adding_never_changes_a_title_the_member_already_has(authenticated_client, db_session):
    user = db_session.query(models.User).filter_by(username="testuser").one()
    db_session.add(models.Book(user_id=user.id, title="piranesi", author="S. Clarke", year=2020, rating=9.0,
                               read=True, review="Loved it"))
    db_session.commit()
    body = authenticated_client.post("/api/pick/add", json={"id": "book/piranesi-2020"}).json()
    assert body["state"] == "existing"
    book = db_session.query(models.Book).filter_by(user_id=user.id).one()
    assert (book.title, book.author, book.rating, book.read, book.review) == ("piranesi", "S. Clarke", 9.0, True, "Loved it")


def test_games_without_a_year_are_added_without_a_release_date(authenticated_client, db_session):
    game = next(entry for entry in pick.candidates("game") if entry["year"] is None)
    assert authenticated_client.post("/api/pick/add", json={"id": game["id"]}).json()["state"] == "created"
    saved = db_session.query(models.VideoGame).filter_by(title=game["title"]).one()
    assert saved.release_date is None and not saved.played


def test_adding_requires_an_account(client):
    assert client.post("/api/pick/add", json={"id": "movie/arrival-2016"}).status_code == 401


def test_a_guest_saved_pick_moves_into_the_new_library_even_if_nobody_tracks_it(authenticated_client, db_session):
    assert title_pages.find(db_session, "book", "piranesi-2020") is None
    response = authenticated_client.post("/api/guest-list/import", json={"items": [
        {"kind": "book", "slug": "piranesi-2020"}, {"kind": "movie", "slug": "not-a-real-pick"}]})
    assert response.status_code == 200
    body = response.json()
    assert [item["title"] for item in body["added"]] == ["Piranesi"] and body["missing"] == 1
    book = db_session.query(models.Book).filter_by(title="Piranesi").one()
    assert book.author == "Susanna Clarke" and not book.read


def test_pick_is_linked_from_the_site_and_counted():
    from app.site_chrome import FOOTER_GROUPS
    assert ("Pick for me", "/pick") in dict(FOOTER_GROUPS)["Explore"]
    assert {"pick_used", "pick_saved"} <= funnel.CLIENT_EVENTS
    assert {"pick_used", "pick_saved"} <= {item["event"] for item in funnel.summary({})["guest"]}


def test_sitemap_lists_the_page(client):
    assert "https://omnitrackr.xyz/pick</loc>" in client.get("/sitemap.xml").text


def test_dashboard_todays_pick_links_to_something_new(client):
    from pathlib import Path
    index = (Path(__file__).parents[1] / "app" / "templates" / "index.html").read_text(encoding="utf-8")
    start = index.index('id="todaysPick"')
    assert 'href="/pick"' in index[start:index.index("</section>", start)]
