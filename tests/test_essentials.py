"""The Essential 100 (/essentials): nine hand-written canon lists of 100 titles, as checklists (Nov 2026)."""
import json
import re
from datetime import datetime, timedelta

import pytest

from app import badges, editorial_index, essentials, guide_links, models, title_pages, title_search
from app.routers import essentials as essentials_router

BANNED = ("testament", "pivotal", "delve", "tapestry", "groundbreaking", "boasts", "seamless", "unparalleled",
          "indelible", "a must-see", "showcasing")


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    essentials._details_cache.update({"index": None, "details": None})
    yield
    title_search.clear_cache()


def first(fmt, **match):
    return next(item for item in essentials.get(fmt)["items"] if all(item.get(k) == v for k, v in match.items()))


def user_of(db_session):
    return db_session.query(models.User).filter_by(username="testuser").one()


# ---------------------------------------------------------------- the writing

def test_nine_lists_of_exactly_one_hundred():
    assert essentials.available() == list(essentials.FORMATS)
    kinds = {"movies": "movie", "tv": "tv", "anime": "anime", "games": "game", "books": "book", "music": "album",
             "manga": "manga", "podcasts": "podcast", "audiobooks": "audiobook"}
    for fmt, data in essentials.lists().items():
        assert data["kind"] == kinds[fmt] and data["format"] == fmt
        assert len(data["items"]) == essentials.SIZE, fmt
        assert sum(1 for item in data["items"] if item.get("starter")) == 10, fmt
        assert 5 <= len(data["sections"]) <= 9, fmt
        assert [item["number"] for item in data["items"]] == list(range(1, 101))
        assert len({item["id"] for item in data["items"]}) == 100, fmt
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["reviewed"])
        assert data["name"] and data["noun"] and data["done_word"] and data["deck"]
        assert len(data["search_title"]) <= 75 and 90 <= len(data["summary"]) <= 175, fmt
        assert len(data["lead"]) >= 2 and len(data["start"]) >= 1 and len(data["left_out"]) >= 5
        assert len(data["faq"]) >= 3 and data["method"] and len(data["sources"]) >= 4
        for label, url in data["sources"]:
            assert label and url.startswith("https://"), (fmt, label)


def test_every_title_has_a_real_blurb():
    for fmt, data in essentials.lists().items():
        words = 0
        for item in data["items"]:
            label = f"{fmt}: {item['title']}"
            assert item["title"] and item["creator"] and item["length"], label
            assert isinstance(item.get("year"), int) or (fmt == "books" and item.get("dated")), label
            assert len(item["why"].split()) >= 35, label
            assert len(item["start"].split()) >= 8, label
            assert "—" not in item["why"] + item["start"], label
            if fmt != "podcasts":
                assert isinstance(item.get("hours"), (int, float)) and item["hours"] > 0, label
            if fmt == "audiobooks":
                assert item["extra"]["narrator"] and item["extra"]["length_hours"] > 0, label
            words += len(item["why"].split()) + len(item["start"].split())
        # Each list is a long read in its own right (AdSense rejected thin pages).
        assert words >= 6000, fmt
        text = " ".join(item["why"] + " " + item["start"] for item in data["items"]).lower()
        for phrase in BANNED:
            assert not re.search(rf"\b{re.escape(phrase)}\b", text), (fmt, phrase)


def test_every_title_saves_to_the_right_place():
    for item in essentials.all_items():
        saved = essentials.find(item["kind"], item["slug"])
        assert saved["title"] == item["title"] and saved["kind"] == item["kind"]
        assert ("browse_kind" in saved) == (item["kind"] in essentials.BROWSE_KINDS)
    assert essentials.find("movie", "not-on-the-list") is None


# ---------------------------------------------------------------- pages

def test_hub_lists_all_nine_and_reads_without_an_account(client):
    response = client.get("/essentials")
    assert response.status_code == 200
    html = response.text
    for fmt in essentials.FORMATS:
        assert f'href="/essentials/{fmt}"' in html
    assert "How many of the 900 have you finished?" in html
    assert '"@type": "CollectionPage"' in html or '"CollectionPage"' in html
    assert "/static/ad-loader.js" not in html
    assert response.headers["Cache-Control"] == "public, max-age=600"


@pytest.mark.parametrize("fmt", essentials.FORMATS)
def test_each_list_page_has_every_title(client, fmt):
    response = client.get(f"/essentials/{fmt}")
    assert response.status_code == 200
    html = response.text
    data = essentials.get(fmt)
    for item in data["items"]:
        assert f'id="{item["anchor"]}"' in html
    assert html.count('class="es-item"') == 100
    assert html.count("data-es-tick") == 100 + 0  # one tick button per title for visitors
    assert 'data-es-starter="1"' in html and "Ten to start with" in html
    assert "/static/essentials.js" in html and "/static/ad-loader.js" in html
    assert '"ItemList"' in html and '"FAQPage"' in html
    assert "index, follow" in html


def test_unknown_list_is_404(client):
    assert client.get("/essentials/comics").status_code == 404


def test_members_see_their_count_from_the_library(authenticated_client, db_session):
    user = user_of(db_session)
    film = essentials.get("movies")["items"][0]
    other = essentials.get("movies")["items"][1]
    db_session.add(models.Movie(user_id=user.id, title=film["title"], director="", year=film["year"], watched=True))
    db_session.add(models.Movie(user_id=user.id, title=other["title"].upper(), director="", year=other["year"], watched=False))
    db_session.commit()
    response = authenticated_client.get("/essentials/movies")
    html = response.text
    assert response.headers["Cache-Control"] == "private, no-store"
    assert 'data-es-done="1"' in html and "You have seen 1 of these 100 films." in html
    assert "In your library" in html and "Open it to mark it finished" in html
    assert "data-es-tick" not in html and 'data-es-save="seen"' in html
    assert "/static/ad-loader.js" not in html
    hub = authenticated_client.get("/essentials").text
    assert "1 of 900 finished" in hub


def test_remakes_with_the_same_name_do_not_count(authenticated_client, db_session):
    user = user_of(db_session)
    film = essentials.get("movies")["items"][0]
    db_session.add(models.Movie(user_id=user.id, title=film["title"], director="", year=film["year"] + 30, watched=True))
    db_session.commit()
    assert essentials.library_states(db_session, user.id, essentials.get("movies")["items"]) == {}


# ---------------------------------------------------------------- saving

def test_seen_it_adds_a_finished_title_and_undo_takes_it_back(authenticated_client, db_session):
    item = essentials.get("games")["items"][3]
    response = authenticated_client.post("/api/essentials/save", json={"id": item["id"], "answer": "seen"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "created" and body["done"] is True
    record = db_session.query(models.VideoGame).filter_by(title=item["title"]).one()
    assert record.played is True
    again = authenticated_client.post("/api/essentials/save", json={"id": item["id"], "answer": "want"}).json()
    assert again["state"] == "existing" and again["done"] is True
    undo = authenticated_client.post("/api/essentials/undo", json={"category": "video-games", "item_id": body["item_id"]})
    assert undo.status_code == 200
    assert db_session.query(models.VideoGame).filter_by(title=item["title"]).count() == 0


def test_want_to_adds_an_unfinished_title_with_details(authenticated_client, db_session):
    item = essentials.get("audiobooks")["items"][0]
    body = authenticated_client.post("/api/essentials/save", json={"id": item["id"], "answer": "want"}).json()
    assert body["state"] == "created" and body["done"] is False
    record = db_session.query(models.Audiobook).filter_by(title=item["title"]).one()
    assert record.listened is False and record.narrator == item["extra"]["narrator"]
    manga = essentials.get("manga")["items"][0]
    authenticated_client.post("/api/essentials/save", json={"id": manga["id"], "answer": "seen"})
    saved = db_session.query(models.Manga).filter_by(title=manga["title"]).one()
    assert saved.read is True and saved.author == manga["creator"]


def test_existing_library_titles_are_never_changed(authenticated_client, db_session):
    user = user_of(db_session)
    book = essentials.get("books")["items"][10]
    db_session.add(models.Book(user_id=user.id, title=book["title"], author="Someone", read=False, rating=6.5))
    db_session.commit()
    body = authenticated_client.post("/api/essentials/save", json={"id": book["id"], "answer": "seen"}).json()
    assert body["state"] == "existing" and body["done"] is False
    record = db_session.query(models.Book).filter_by(title=book["title"]).one()
    assert record.read is False and record.rating == 6.5 and record.author == "Someone"


def test_undo_refuses_older_titles_and_other_peoples(authenticated_client, db_session):
    user = user_of(db_session)
    old = models.Movie(user_id=user.id, title="Something old", director="", year=1990, watched=True,
                       added_at=datetime.utcnow() - timedelta(days=3))
    db_session.add(old)
    db_session.commit()
    response = authenticated_client.post("/api/essentials/undo", json={"category": "movies", "item_id": old.id})
    assert response.status_code == 409
    assert authenticated_client.post("/api/essentials/undo", json={"category": "movies", "item_id": 999999}).status_code == 404


def test_save_rejects_unknown_titles_and_guests(client, authenticated_client):
    assert authenticated_client.post("/api/essentials/save", json={"id": "movie/nope-1999", "answer": "seen"}).status_code == 404
    assert authenticated_client.post("/api/essentials/save", json={"id": "movie/x", "answer": "loved"}).status_code == 422


def test_save_needs_an_account(client):
    item = essentials.get("movies")["items"][0]
    assert client.post("/api/essentials/save", json={"id": item["id"], "answer": "seen"}).status_code == 401
    assert client.post("/api/essentials/import", json={"ids": [item["id"]]}).status_code == 401


def test_ticks_from_before_sign_up_import_as_finished(authenticated_client, db_session):
    user = user_of(db_session)
    films = essentials.get("movies")["items"][:3]
    album = essentials.get("music")["items"][5]
    db_session.add(models.Movie(user_id=user.id, title=films[0]["title"], director="", year=films[0]["year"], watched=False))
    db_session.commit()
    ids = [item["id"] for item in films] + [album["id"], "movie/not-a-title", films[1]["id"]]
    body = authenticated_client.post("/api/essentials/import", json={"ids": ids}).json()
    assert body == {"added": 3, "existing": 1, "missing": 1}
    assert db_session.query(models.Movie).filter_by(title=films[0]["title"]).one().watched is False
    assert db_session.query(models.Movie).filter_by(title=films[1]["title"]).one().watched is True
    assert db_session.query(models.Music).filter_by(title=album["title"]).one().listened is True


def test_want_to_from_the_guest_list_imports_after_sign_up(authenticated_client, db_session):
    podcast = essentials.get("podcasts")["items"][0]
    film = essentials.get("movies")["items"][50]
    items = [{"kind": podcast["kind"], "slug": podcast["slug"]}, {"kind": film["kind"], "slug": film["slug"]}]
    response = authenticated_client.post("/api/guest-list/import", json={"items": items})
    assert response.status_code == 200, response.text
    assert len(response.json()["added"]) == 2
    assert db_session.query(models.Podcast).filter_by(title=podcast["title"]).one().listened is False


# ---------------------------------------------------------------- sharing

def test_shared_counts_are_noindex_pages_with_a_card(client):
    response = client.get("/essentials/anime/score/37")
    assert response.status_code == 200
    assert response.headers["X-Robots-Tag"] == "noindex, follow"
    assert "37 of the essential 100 anime" in response.text
    assert 'content="https://omnitrackr.xyz/essentials/anime/score/37/card.png"' in response.text
    card = client.get("/essentials/anime/score/37/card.png")
    assert card.status_code == 200 and card.headers["content-type"] == "image/png" and card.content[:4] == b"\x89PNG"
    assert client.get("/essentials/anime/score/101").status_code == 404
    assert client.get("/essentials/anime/score/101/card.png").status_code == 404


def test_shared_count_across_all_nine(client):
    response = client.get("/essentials/score/1-2-3-4-5-6-7-8-9")
    assert response.status_code == 200 and "45 of the essential 900" in response.text
    assert client.get("/essentials/score/1-2-3-4-5-6-7-8-9/card.png").content[:4] == b"\x89PNG"
    for bad in ("1-2-3", "1-2-3-4-5-6-7-8-101", "a-b-c-d-e-f-g-h-i", "1-2-3-4-5-6-7-8-9-10"):
        assert client.get(f"/essentials/score/{bad}").status_code == 404


# ---------------------------------------------------------------- around the site

def test_lists_are_in_the_sitemap_guides_and_search(client):
    sitemap = client.get("/sitemap.xml").text
    for fmt in essentials.FORMATS:
        assert f"https://omnitrackr.xyz/essentials/{fmt}</loc>" in sitemap or f"/essentials/{fmt}</loc>" in sitemap
    assert "/essentials/movies/score" not in sitemap
    hrefs = {piece["href"] for piece in editorial_index.entries()}
    assert {f"/essentials/{fmt}" for fmt in essentials.FORMATS} <= hrefs
    assert "The Essential 100" in editorial_index.directory_html()


def test_header_links_to_the_hub(client):
    assert 'href="/essentials"' in client.get("/discover").text


def test_title_pages_say_when_a_title_is_on_a_list():
    film = essentials.get("movies")["items"][0]
    assert essentials.for_title("movie", film["title"], film["year"]) is film
    assert essentials.for_title("movie", film["title"].upper(), None) is film
    assert essentials.for_title("movie", film["title"], film["year"] + 40) is None
    as_book = essentials.for_title("book", film["title"], film["year"])
    assert as_book is None or as_book["kind"] == "book"


def test_anime_films_count_when_filed_under_movies(db_session):
    films = [item for item in essentials.get("anime")["items"] if (item.get("extra") or {}).get("film")]
    assert films, "the anime list includes films"
    user = models.User(username="ghibli", email="g@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.commit()
    db_session.add(models.Movie(user_id=user.id, title=films[0]["title"], director="", year=films[0]["year"], watched=True))
    db_session.commit()
    states = essentials.library_states(db_session, user.id, essentials.get("anime")["items"])
    assert states[films[0]["id"]]["state"] == "done"


def test_essentials_badge_counts_finished_titles(db_session):
    user = models.User(username="canon", email="c@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.commit()
    for item in essentials.get("books")["items"][:12]:
        db_session.add(models.Book(user_id=user.id, title=item["title"], author=item["creator"], year=item.get("year"), read=True))
    db_session.commit()
    assert badges.counts(db_session, user)["essentials"] == 12
    track = badges.BY_KEY["essentials"]
    assert badges.tier_for(track, 12) == 1


def test_cross_links_know_the_lists():
    index = guide_links._index_for("test")
    entry = index["/essentials/movies"]
    assert entry["kind"] == "movie" and len(entry["titles"]) >= 100
