"""Site search (Nov 2026): /api/search, the /search page, guides and people in results, Ctrl+K extras."""
from pathlib import Path

import pytest

from app import models, site_search, title_search
from app.auth import AUTH_COOKIE_NAME


def member(db, name, **extra):
    fields = {"is_active": True, "is_verified": True, **extra}
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", **fields)
    db.add(user)
    db.flush()
    return user


@pytest.fixture(autouse=True)
def fresh_caches():
    title_search.clear_cache()
    site_search.clear_cache()
    yield
    title_search.clear_cache()
    site_search.clear_cache()


@pytest.fixture
def library(db_session):
    ann, ben, cal = member(db_session, "ann"), member(db_session, "ben"), member(db_session, "cal")
    hidden = member(db_session, "hid", movies_private=True)
    db_session.add_all([
        models.Movie(user_id=ann.id, title="Interstellar", director="Nolan", year=2014,
                     poster_url="https://img.example/inter.jpg", review="my private notes"),
        models.Movie(user_id=ben.id, title="Interstellar", director="Nolan", year=2014),
        models.Movie(user_id=cal.id, title="Inside Out", director="Docter", year=2015),
        models.Movie(user_id=hidden.id, title="Secret Diary Film", director="X", year=2020),
        models.Anime(user_id=ann.id, title="Frieren: Beyond Journey's End", year=2023),
        models.Anime(user_id=ben.id, title="Frieren: Beyond Journey's End", year=2023),
        models.TVShow(user_id=cal.id, title="Interview with the Vampire", year=2022),
    ])
    db_session.commit()
    return db_session


def titles(items):
    return [item["title"] for item in items]


# ---------------------------------------------------------------- guides and pages

def test_every_guide_family_and_hub_is_in_the_index():
    sections = {entry["section"] for entry in site_search.guide_entries()}
    assert {"In order", "How long it takes", "If you liked", "Best of", "Switch trackers", "Discover", "Page"} <= sections
    urls = [entry["url"] for entry in site_search.guide_entries()]
    assert len(urls) == len(set(urls))
    assert "/in-order/star-wars" in urls and "/switch/letterboxd" in urls and "/daily" in urls


def test_every_indexed_guide_and_page_opens(client):
    for entry in site_search.guide_entries():
        response = client.get(entry["url"], follow_redirects=True)
        assert response.status_code == 200, entry["url"]


def test_guides_match_on_their_subject_and_on_what_they_cover():
    assert site_search.search_guides("star wars")[0]["url"] == "/in-order/star-wars"
    assert site_search.search_guides("how long breaking bad")[0]["url"] == "/binge-calculator/breaking-bad"
    assert site_search.search_guides("letterboxd")[0]["url"] == "/switch/letterboxd"
    # A film inside a guide finds the guide, after guides named for it.
    assert "/in-order/star-wars" in [g["url"] for g in site_search.search_guides("mandalorian", limit=10)]
    assert site_search.search_guides("daily puzzle")[0] == {
        "title": "Daily puzzle", "url": "/daily", "section": "Page", "detail": "One new guessing game every day"}
    assert site_search.search_guides("x") == [] and site_search.search_guides("!!") == []


def test_release_guides_appear_only_once_published():
    from datetime import date

    from app import new_releases

    live = set(new_releases.published(date(2026, 11, 14)))
    urls = {entry["url"] for entry in site_search._guide_sources(date(2026, 11, 14))}
    assert {new_releases.path(slug) for slug in live} <= urls
    early = {entry["url"] for entry in site_search._guide_sources(date(2020, 1, 1))}
    assert not any(url.startswith(new_releases.BASE_PATH + "/") for url in early)


# ---------------------------------------------------------------- people

def test_people_match_every_word_and_most_credited_come_first(db_session):
    entries = [
        {"name": "Christopher Nolan", "url": "/people/christopher-nolan", "role": "Director", "kind": "Person",
         "titles": 6, "words": {"christopher", "nolan"}},
        {"name": "Jonathan Nolan", "url": "/people/jonathan-nolan", "role": "Writer", "kind": "Person",
         "titles": 3, "words": {"jonathan", "nolan"}},
    ]
    assert titles([{"title": p["name"]} for p in site_search.search_people(db_session, "nolan", entries=entries)]) == [
        "Christopher Nolan", "Jonathan Nolan"]
    assert [p["name"] for p in site_search.search_people(db_session, "chris nol", entries=entries)] == ["Christopher Nolan"]
    assert site_search.search_people(db_session, "no", entries=entries) == []  # too short to be worth a lookup


# ---------------------------------------------------------------- API

def test_api_returns_titles_guides_and_member_counts(client, library):
    response = client.get("/api/search", params={"q": "inter"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300"
    data = response.json()
    assert titles(data["titles"]) == ["Interstellar", "Interview with the Vampire"]
    first = data["titles"][0]
    assert first == {"kind": "movie", "label": "Movie", "title": "Interstellar", "year": 2014, "slug": "interstellar-2014",
                     "url": "/titles/movie/interstellar-2014", "image": "https://img.example/inter.jpg", "members": 2}
    # One member is never shown as a count: it would point at a person.
    assert data["titles"][1]["members"] == 0
    assert "private notes" not in response.text and "ann" not in response.text
    assert any(g["url"] == "/if-you-liked/interstellar" for g in data["guides"])


def test_api_filters_by_format_and_skips_guides_then(client, library):
    data = client.get("/api/search", params={"q": "inter", "kind": "tv"}).json()
    assert titles(data["titles"]) == ["Interview with the Vampire"] and data["kind"] == "tv"
    assert data["guides"] == [] and data["people"] == []
    # An unknown kind is ignored rather than an error.
    assert client.get("/api/search", params={"q": "inter", "kind": "nope"}).json()["kind"] is None


def test_api_hides_private_libraries(client, library):
    assert client.get("/api/search", params={"q": "secret diary"}).json()["titles"] == []


def test_empty_search_returns_popular_titles_across_formats(client, library):
    data = client.get("/api/search").json()
    assert titles(data["popular"]) == ["Frieren: Beyond Journey's End", "Interstellar"]  # two or more members only
    assert titles(client.get("/api/search", params={"kind": "anime"}).json()["popular"]) == ["Frieren: Beyond Journey's End"]


def test_misspelling_gets_a_suggestion(client, library):
    data = client.get("/api/search", params={"q": "interstelar"}).json()
    assert data["titles"] == [] and data["suggestion"] == "Interstellar"
    assert client.get("/api/search", params={"q": "frirein"}).json()["suggestion"] == "Frieren: Beyond Journey's End"
    assert client.get("/api/search", params={"q": "qqqqqqzz"}).json()["suggestion"] is None


def test_more_flag_and_limit(client, library):
    data = client.get("/api/search", params={"q": "in", "limit": 1}).json()
    assert len(data["titles"]) == 1 and data["more"] is True and data["total"] == 3
    assert client.get("/api/search", params={"q": "in", "limit": 99}).status_code == 422


# ---------------------------------------------------------------- /search page

def test_page_is_noindex_and_lets_guests_save(client, library):
    response = client.get("/search", params={"q": "inter"})
    assert response.status_code == 200
    assert response.headers["x-robots-tag"] == "noindex, follow"
    html = response.text
    assert '<meta name="robots" content="noindex, follow">' in html
    assert "Results for “inter”" in html
    assert 'data-guest-kind="movie" data-guest-slug="interstellar-2014" data-guest-title="Interstellar"' in html
    assert "/static/guest-list.js" in html and "data-guest-bar" in html
    assert 'href="/titles/movie/interstellar-2014"' in html and "2 members track it" in html
    # Format chips only list formats with results, with their counts.
    assert 'href="/search?q=inter&amp;kind=movie">Movies <span>1</span>' in html
    assert 'href="/search?q=inter&amp;kind=tv">TV <span>1</span>' in html
    assert "kind=game" not in html
    assert "If you liked Interstellar" in html


def test_page_for_members_adds_to_the_library(client, library):
    client.cookies.set(AUTH_COOKIE_NAME, "anything")
    response = client.get("/search", params={"q": "inter"})
    assert response.headers["cache-control"] == "private, no-store"
    assert 'data-site-add data-kind="movie" data-slug="interstellar-2014"' in response.text
    assert "/static/guest-list.js" not in response.text and "data-guest-kind" not in response.text


def test_page_with_nothing_found_points_somewhere_useful(client, library):
    html = client.get("/search", params={"q": "zzqx"}).text
    assert "Nothing called “zzqx” yet" in html and 'href="/#signup"' in html
    client.cookies.set(AUTH_COOKIE_NAME, "anything")
    assert 'href="/?find=zzqx"' in client.get("/search", params={"q": "zzqx"}).text
    filtered = client.get("/search", params={"q": "frieren", "kind": "game"}).text
    assert "among games" in filtered and 'href="/search?q=frieren">Search every format instead' in filtered


def test_page_shows_a_suggestion(client, library):
    html = client.get("/search", params={"q": "interstelar"}).text
    assert 'Did you mean <a href="/search?q=Interstellar">Interstellar</a>?' in html


def test_page_without_a_search_shows_popular_titles_and_guides(client, library):
    html = client.get("/search").text
    assert "Popular with members" in html and "Frieren" in html
    assert "Good places to start" in html
    assert "<title>Search OmniTrackr</title>" in html


def test_page_escapes_the_search(client, library):
    html = client.get("/search", params={"q": '<script>alert("x")</script>'}).text
    assert '<script>alert("x")</script>' not in html
    assert "&lt;script&gt;" in html


# ---------------------------------------------------------------- around the site

def test_header_search_falls_back_to_the_page_and_browsers_can_add_it(client):
    html = client.get("/discover").text
    assert '<a class="site-search" href="/search" data-site-search' in html
    assert '<link rel="search" type="application/opensearchdescription+xml" title="OmniTrackr" href="/opensearch.xml">' in html
    xml = client.get("/opensearch.xml")
    assert xml.headers["content-type"].startswith("application/opensearchdescription+xml")
    assert 'template="https://omnitrackr.xyz/search?q={searchTerms}"' in xml.text


def test_not_found_search_link_works_without_scripts(client):
    html = client.get("/definitely-missing", headers={"Accept": "text/html"}).text
    assert 'href="/search?q=definitely+missing" data-site-search-open' in html


def test_library_search_returns_covers(authenticated_client, db_session):
    user = db_session.query(models.User).filter_by(username="testuser").one()
    db_session.add_all([
        models.Movie(user_id=user.id, title="Arrival", year=2016, poster_url="https://img.example/arrival.jpg"),
        models.Book(user_id=user.id, title="Arrival Stories", author="Chiang", cover_art_url="javascript:alert(1)"),
    ])
    db_session.commit()
    results = authenticated_client.get("/library/search", params={"q": "arrival"}).json()
    assert {item["title"]: item["image"] for item in results} == {
        "Arrival": "https://img.example/arrival.jpg", "Arrival Stories": None}


def test_scripts_draw_results_as_text_only():
    site_nav = Path("app/static/site-nav.js").read_text(encoding="utf-8")
    core = Path("app/static/dashboard/core.js").read_text(encoding="utf-8")
    assert "innerHTML" not in site_nav
    assert "/api/search?" in site_nav and "omnitrackr_recent_searches" in site_nav
    assert "String(event.key).toLowerCase() === 'k'" in site_nav
    start = core.index("const LIBRARY_RECENT_KEY")
    end = core.index("// Universal quick capture")
    assert "innerHTML" not in core[start:end]
    assert "/api/search?q=" in core[start:end] and "openQuickCaptureSearch" in core[start:end]
