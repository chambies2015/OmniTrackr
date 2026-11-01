"""Homepage hero search: titles members track, saved to a guest list before sign-up (Oct 2026)."""
from datetime import date

import pytest

from app import funnel, models, title_pages, title_search


def member(db, name, **extra):
    fields = {"is_active": True, "is_verified": True, **extra}
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", **fields)
    db.add(user)
    db.flush()
    return user


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


@pytest.fixture
def library(db_session):
    ann, ben, cal = member(db_session, "ann"), member(db_session, "ben"), member(db_session, "cal")
    hidden = member(db_session, "hid", movies_private=True)
    gone = member(db_session, "gone", is_active=False)
    db_session.add_all([
        models.Movie(user_id=ann.id, title="Interstellar", director="Nolan", year=2014, rating=9.5,
                     review="private notes", poster_url="https://img.example/inter.jpg"),
        models.Movie(user_id=ben.id, title="interstellar", director="Nolan", year=2014),
        models.Movie(user_id=cal.id, title="Inside Out", director="Docter", year=2015),
        models.Movie(user_id=hidden.id, title="Secret Diary Film", director="X", year=2020),
        models.Movie(user_id=gone.id, title="Departed Member Movie", director="X", year=2001),
        models.Anime(user_id=ann.id, title="Frieren: Beyond Journey's End", year=2023),
        models.VideoGame(user_id=ben.id, title="Hades", release_date=date(2020, 9, 17)),
        models.Book(user_id=cal.id, title="Piranesi", author="Clarke", year=2020, cover_art_url="javascript:alert(1)"),
    ])
    db_session.commit()
    return db_session


def titles(results):
    return [item["title"] for item in results]


def test_matches_word_prefixes_and_ranks_closest_first(library):
    entries = title_search.build_index(library)
    assert titles(title_search.search(entries, "inter")) == ["Interstellar"]
    assert titles(title_search.search(entries, "in")) == ["Interstellar", "Inside Out"]  # more members first
    assert titles(title_search.search(entries, "journey frier")) == ["Frieren: Beyond Journey's End"]
    assert titles(title_search.search(entries, "HADES")) == ["Hades"]
    assert title_search.search(entries, "stellar") == []  # words must start with the query
    assert title_search.search(entries, "i") == [] and title_search.search(entries, "!!") == []


def test_private_categories_and_inactive_members_never_show(library):
    entries = title_search.build_index(library)
    assert title_search.search(entries, "secret") == []
    assert title_search.search(entries, "departed") == []


def test_results_carry_public_details_only_and_round_trip_to_title_pages(library):
    entries = title_search.build_index(library)
    movie = title_search.search(entries, "interstellar")[0]
    assert movie == {"kind": "movie", "label": "Movie", "title": "Interstellar", "year": 2014,
                     "slug": "interstellar-2014", "url": "/titles/movie/interstellar-2014",
                     "image": "https://img.example/inter.jpg"}
    book = title_search.search(entries, "piranesi")[0]
    assert book["image"] is None  # unsafe image URLs are dropped
    game = title_search.search(entries, "hades")[0]
    assert game["slug"] == "hades-2020"
    for item in (movie, book, game, title_search.search(entries, "frieren")[0]):
        group = title_pages.find(library, item["kind"], item["slug"])
        assert group is not None and group.title == item["title"]


def test_search_endpoint_is_public_and_cacheable(client, library):
    response = client.get("/api/titles/search", params={"q": "inter"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300"
    results = response.json()["results"]
    assert titles(results) == ["Interstellar"]
    assert "members" not in results[0] and "user_id" not in str(results)
    assert client.get("/api/titles/search", params={"q": "x"}).json() == {"results": []}
    assert client.get("/api/titles/search").json() == {"results": []}
    assert client.get("/api/titles/search", params={"q": "a" * 201}).status_code == 422


def test_a_searched_title_moves_into_a_new_library(authenticated_client, library):
    found = authenticated_client.get("/api/titles/search", params={"q": "frieren"}).json()["results"][0]
    response = authenticated_client.post("/api/guest-list/import",
                                         json={"items": [{"kind": found["kind"], "slug": found["slug"]}]})
    assert response.status_code == 200
    assert [item["title"] for item in response.json()["added"]] == ["Frieren: Beyond Journey's End"]


def test_homepage_hero_has_the_search(client):
    html = client.get("/").text
    start = html.index('class="landing-hero')
    hero = html[start:html.index("</section>", start)]
    assert "data-title-search" in hero and 'id="lpSearchInput"' in hero and 'action="/titles"' in hero
    assert 'class="lp-search__go"' in hero and 'data-action="show-register-form"' in hero
    # Saving opens the page-wide save bar, which carries sign-up.
    assert 'class="lp-savebar" data-guest-bar hidden' in html
    assert '/static/title-search.js?v=' in html and '/static/guest-list.js?v=' in html


def test_search_is_a_counted_guest_moment():
    assert "title_search_used" in funnel.CLIENT_EVENTS
    assert "title_search_used" in {item["event"] for item in funnel.summary({})["guest"]}
