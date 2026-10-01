"""Public title pages: identity, member data, metadata sources, indexing rules."""
import asyncio
import json
from datetime import datetime, timedelta

import pytest

from app import auth, models, title_metadata, title_pages
from app.editorial_collections import EDITOR_EMAIL, EDITOR_USERNAME
from app.routers import titles as titles_router

LONG_REVIEW = (
    "Interstellar works because the science never crowds out the family story at its center. The docking "
    "sequence is one of the most tense scenes I have seen, and the score keeps building pressure without "
    "feeling cheap. Some dialogue is clumsy, yet the time-dilation planet hit me hard on a rewatch and the final "
    "act ties the father and daughter threads together better than I remembered."
)


def member(db, name, active=True):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=True, is_active=active)
    db.add(user)
    db.flush()
    return user


def add_movie(db, user, title="Interstellar", year=2014, **extra):
    movie = models.Movie(user_id=user.id, title=title, director=extra.pop("director", "Christopher Nolan"), year=year, **extra)
    db.add(movie)
    db.flush()
    return movie


# ---------------------------------------------------------------- identity

@pytest.mark.parametrize("title,year,slug", [
    ("Interstellar", 2014, "interstellar-2014"),
    ("Blade Runner 2049", 2017, "blade-runner-2049-2017"),
    ("Pokémon: The First Movie", 1998, "pokemon-the-first-movie-1998"),
    ("2001: A Space Odyssey", None, "2001-a-space-odyssey"),
    ("!!!", 2000, "title-2000"),
])
def test_slugs(title, year, slug):
    assert title_pages.title_slug(title, year) == slug


def test_find_groups_every_members_entry(db_session):
    a, b = member(db_session, "a"), member(db_session, "b")
    add_movie(db_session, a)
    add_movie(db_session, b, title="interstellar")
    add_movie(db_session, b, title="Interstellar", year=1999)  # a different film
    db_session.commit()
    group = title_pages.find(db_session, "movie", "interstellar-2014")
    assert group is not None and len(group.items) == 2 and group.year == 2014
    assert group.path == "/titles/movie/interstellar-2014"
    assert title_pages.find(db_session, "movie", "interstellar-2015") is None
    assert title_pages.find(db_session, "podcast", "interstellar-2014") is None
    assert title_pages.find(db_session, "movie", "../etc") is None


def test_find_handles_numbers_and_accents(db_session):
    a = member(db_session, "a")
    add_movie(db_session, a, title="Blade Runner 2049", year=2017)
    add_movie(db_session, a, title="Pokémon: The First Movie", year=1998)
    db_session.commit()
    assert title_pages.find(db_session, "movie", "blade-runner-2049-2017").title == "Blade Runner 2049"
    assert title_pages.find(db_session, "movie", "pokemon-the-first-movie-1998").title == "Pokémon: The First Movie"


@pytest.mark.parametrize("title,year,slug", [
    ("Film", 2014, "film-2014"),
    ("Blade Runner 2049", None, "blade-runner-2049"),
    ("Film 123", None, "film-123"),
    ("Film 12345", None, "film-12345"),
    ("2014", None, "2014"),
    ("Film 0000", None, "film-0000"),
])
def test_find_preserves_year_suffix_and_yearless_numeric_titles(db_session, title, year, slug):
    add_movie(db_session, member(db_session, "suffix"), title=title, year=year)
    db_session.commit()

    group = title_pages.find(db_session, "movie", slug)

    assert group is not None
    assert (group.title, group.year) == (title, year)


@pytest.mark.parametrize("slug", ["a" * 20_000, "a" * 131, "a-" * 10_000 + "2014", "film-２０１４"])
def test_find_rejects_invalid_slugs_before_database_lookup(slug):
    assert title_pages.find(None, "movie", slug) is None


def test_deactivated_members_do_not_create_pages(db_session):
    gone = member(db_session, "gone", active=False)
    add_movie(db_session, gone)
    db_session.commit()
    assert title_pages.find(db_session, "movie", "interstellar-2014") is None


# ---------------------------------------------------------------- member data

def test_summary_is_aggregate_and_hides_small_rating_groups(db_session):
    users = [member(db_session, f"u{i}") for i in range(3)]
    add_movie(db_session, users[0], rating=9, watched=True)
    add_movie(db_session, users[1], rating=7)
    db_session.commit()
    group = title_pages.find(db_session, "movie", "interstellar-2014")
    summary = title_pages.summarize(db_session, group)
    assert summary["members"] == 2 and summary["finished"] == 1 and summary["rated"] == 2
    assert summary["average_rating"] is None  # fewer than three ratings never reveal anyone's score
    add_movie(db_session, users[2], rating=8)
    db_session.commit()
    summary = title_pages.summarize(db_session, title_pages.find(db_session, "movie", "interstellar-2014"))
    assert summary["average_rating"] == 8.0


def test_editors_account_is_not_counted_as_a_member(db_session):
    editor = models.User(username=EDITOR_USERNAME, email=EDITOR_EMAIL, hashed_password="x", is_verified=True)
    db_session.add(editor)
    db_session.flush()
    add_movie(db_session, editor, rating=10)
    db_session.commit()
    summary = title_pages.summarize(db_session, title_pages.find(db_session, "movie", "interstellar-2014"))
    assert summary["members"] == 0 and summary["rated"] == 0


def test_only_public_safe_reviews_are_shown_once_per_member(db_session):
    a, b, c = member(db_session, "writer"), member(db_session, "private"), member(db_session, "short")
    add_movie(db_session, a, review=LONG_REVIEW, review_public=True, rating=9.5)
    add_movie(db_session, a, review=LONG_REVIEW + " Again.", review_public=True)
    add_movie(db_session, b, review=LONG_REVIEW, review_public=False)
    add_movie(db_session, c, review="Great.", review_public=True)
    db_session.commit()
    summary = title_pages.summarize(db_session, title_pages.find(db_session, "movie", "interstellar-2014"))
    assert [r["username"] for r in summary["reviews"]] == ["writer"]
    assert summary["search_ready_reviews"] == 1


def test_suspended_reviews_stay_hidden(db_session):
    from app.routers.reviews import _review_content_hash
    a = member(db_session, "writer")
    movie = add_movie(db_session, a, review=LONG_REVIEW, review_public=True)
    db_session.add(models.PublicReviewState(user_id=a.id, category="movie", item_id=movie.id, suspended_at=datetime.utcnow(),
                                            content_hash=_review_content_hash("movie", movie.id, LONG_REVIEW)))
    db_session.commit()
    summary = title_pages.summarize(db_session, title_pages.find(db_session, "movie", "interstellar-2014"))
    assert summary["reviews"] == []


@pytest.mark.parametrize("summary,metadata,expected", [
    ({"search_ready_reviews": 1, "reviews": [1], "members": 1, "collections": []}, None, True),
    ({"search_ready_reviews": 0, "reviews": [], "members": 5, "collections": []}, None, False),
    ({"search_ready_reviews": 0, "reviews": [], "members": 3, "collections": []}, {"description": "x"}, True),
    ({"search_ready_reviews": 0, "reviews": [], "members": 1, "collections": []}, {"description": "x"}, False),
    ({"search_ready_reviews": 0, "reviews": [1], "members": 1, "collections": []}, {"description": "x"}, True),
    ({"search_ready_reviews": 0, "reviews": [], "members": 1, "collections": [1]}, {"description": "x"}, True),
])
def test_indexing_needs_real_substance(summary, metadata, expected):
    assert title_pages.is_indexable(summary, metadata) is expected


# ---------------------------------------------------------------- the page

SAMPLE = {
    "category": "movie", "description": "Interstellar is a 2014 epic science fiction film.\nSecond paragraph.",
    "description_source": {"name": "Wikipedia", "url": "https://en.wikipedia.org/wiki/Interstellar_(film)",
                           "license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0/"},
    "short_description": "2014 film by Christopher Nolan", "release_date": "2014-10-26",
    "facts": [{"label": "Running time", "value": "169 min"}], "genres": ["science fiction film"],
    "scores": [{"source": "Rotten Tomatoes", "value": "73%"}], "poster": "https://img.example/p.jpg", "backdrop": None,
    "gallery": [{"url": "https://img.example/s1.jpg", "thumb": "https://img.example/s1-small.jpg"}],
    "trailer": "zSWdZVtXT7E", "tracks": [],
    "links": [{"label": "Wikipedia", "url": "https://en.wikipedia.org/wiki/Interstellar_(film)"}],
    "sources": [{"name": "Wikipedia", "url": "https://en.wikipedia.org/wiki/Interstellar_(film)", "license": "CC BY-SA 4.0"}],
}


def seed_metadata(db, data=SAMPLE, key="movie:interstellar:2014"):
    title_metadata.store(db, key, data, "ok")


def test_full_page_renders_everything(client, db_session):
    a = member(db_session, "writer")
    add_movie(db_session, a, review=LONG_REVIEW, review_public=True, rating=9.5, watched=True)
    db_session.commit()
    seed_metadata(db_session)
    response = client.get("/titles/movie/interstellar-2014")
    assert response.status_code == 200
    html = response.text
    for expected in ("<h1>Interstellar", "2014 film by Christopher Nolan", "Science fiction", "73%", "Rotten Tomatoes",
                     'data-youtube-id="zSWdZVtXT7E"', "Description from <a", "CC BY-SA 4.0", "169 min",
                     "https://img.example/s1-small.jpg", "member tracking it", "Read the full review",
                     "/reviews/", "Track it free", '"@type": "Movie"', "BreadcrumbList"):
        assert expected in html, expected
    assert '<meta name="robots" content="index, follow' in html
    assert "/static/ad-loader.js" in html
    directives = {
        tokens[0]: tokens[1:]
        for directive in response.headers["content-security-policy"].split(";")
        if (tokens := directive.split())
    }
    assert "https://www.youtube-nocookie.com" in directives["frame-src"]
    assert "<iframe" not in html  # trailers load only when played


def test_thin_pages_are_noindex_and_have_no_ads(client, db_session):
    add_movie(db_session, member(db_session, "solo"))
    db_session.commit()
    response = client.get("/titles/movie/interstellar-2014")
    assert response.status_code == 200
    assert response.headers["x-robots-tag"] == "noindex, follow"
    assert "noindex" in response.text and "/static/ad-loader.js" not in response.text


def test_unknown_titles_404(client, db_session):
    assert client.get("/titles/movie/never-tracked-1999").status_code == 404
    assert client.get("/titles/podcast/anything").status_code == 404


def test_member_ratings_only_become_structured_data_with_three_or_more(client, db_session):
    for index, rating in enumerate((9, 8, 7)):
        add_movie(db_session, member(db_session, f"r{index}"), rating=rating)
    db_session.commit()
    seed_metadata(db_session)
    html = client.get("/titles/movie/interstellar-2014").text
    assert '"aggregateRating"' in html and '"ratingValue": 8.0' in html
    assert "average member rating" in html


def test_page_text_is_escaped(client, db_session):
    add_movie(db_session, member(db_session, "x"), title="<script>alert(1)</script>", year=2001)
    db_session.commit()
    html = client.get("/titles/movie/script-alert-1-script-2001").text
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_signed_in_members_can_add_the_title(authenticated_client, db_session):
    other = member(db_session, "other")
    add_movie(db_session, other, rating=10, review="private notes", poster_url="https://img.example/p.jpg")
    db_session.commit()
    page = authenticated_client.get("/titles/movie/interstellar-2014")
    assert "data-title-add" in page.text and page.headers["cache-control"] == "private, no-store"
    response = authenticated_client.post("/api/titles/movie/interstellar-2014/add")
    assert response.status_code == 200 and response.json()["state"] == "created"
    mine = db_session.query(models.User).filter_by(username="testuser").one()
    copy = db_session.query(models.Movie).filter_by(user_id=mine.id).one()
    assert (copy.title, copy.year, copy.director, copy.poster_url) == ("Interstellar", 2014, "Christopher Nolan", "https://img.example/p.jpg")
    assert copy.rating is None and copy.review is None
    assert authenticated_client.post("/api/titles/movie/interstellar-2014/add").json()["state"] == "existing"


def test_adding_requires_login(client):
    assert client.post("/api/titles/movie/interstellar-2014/add").status_code == 401


def test_titles_directory(client, db_session):
    response = client.get("/titles")
    assert response.status_code == 200 and response.headers["x-robots-tag"] == "noindex, follow"
    for index in range(2):
        user = member(db_session, f"d{index}")
        for number in range(8):
            add_movie(db_session, user, title=f"Film {number}", year=2000 + number)
    db_session.commit()
    response = client.get("/titles")
    assert "x-robots-tag" not in response.headers
    assert "/titles/movie/film-0-2000" in response.text


def test_sitemap_lists_only_indexable_titles(client, db_session):
    add_movie(db_session, member(db_session, "writer"), review=LONG_REVIEW, review_public=True)
    add_movie(db_session, member(db_session, "lonely"), title="Obscure", year=1990)
    db_session.commit()
    sitemap = client.get("/sitemap.xml").text
    assert "/titles/movie/interstellar-2014" in sitemap
    assert "/titles/movie/obscure-1990" not in sitemap


def test_reviews_and_collections_link_to_title_pages(client, db_session):
    a = member(db_session, "writer")
    movie = add_movie(db_session, a, review=LONG_REVIEW, review_public=True)
    db_session.commit()
    detail = client.get(f"/reviews/{movie.id}?category=movie")
    assert 'href="/titles/movie/interstellar-2014"' in detail.text


# ---------------------------------------------------------------- metadata sources

class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    async def get(self, url, params=None, headers=None, timeout=None, follow_redirects=None):
        self.calls.append((url, params or {}))
        assert headers and "OmniTrackr" in headers["User-Agent"]
        for match, payload in self.routes:
            if match(url, params or {}):
                return FakeResponse(payload)
        return FakeResponse({}, 404)


def wikidata_routes(qid, label, description, claims, sitelink, labels):
    def search(url, params):
        return url == "https://www.wikidata.org/w/api.php" and params.get("action") == "wbsearchentities"

    def entity(url, params):
        return url == "https://www.wikidata.org/w/api.php" and params.get("action") == "wbgetentities" and params.get("ids") == qid

    def label_lookup(url, params):
        return url == "https://www.wikidata.org/w/api.php" and params.get("action") == "wbgetentities" and params.get("props") == "labels"

    return [
        (search, {"search": [{"id": "Q1", "label": label, "description": "1999 film"},
                             {"id": qid, "label": label, "description": description}]}),
        (entity, {"entities": {qid: {"claims": claims, "sitelinks": {"enwiki": {"title": sitelink}}}}}),
        (label_lookup, {"entities": {key: {"labels": {"en": {"value": value}}} for key, value in labels.items()}}),
        (lambda url, params: "en.wikipedia.org/api/rest_v1/page/summary" in url,
         {"type": "standard", "extract": f"{label} is a work.", "description": description,
          "thumbnail": {"source": "https://upload.wikimedia.org/x.jpg"},
          "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/X"}}}),
    ]


@pytest.mark.parametrize("url,expected", [
    ("https://www.wikidata.org/w/api.php", True),
    ("https://www.wikidata.org.attacker.example/w/api.php", False),
    ("https://www.wikidata.org@attacker.example/w/api.php", False),
    ("https://attacker.example/w/api.php?source=wikidata.org", False),
    ("http://www.wikidata.org/w/api.php", False),
])
def test_wikidata_fake_routes_require_exact_endpoint(url, expected):
    routes = wikidata_routes("Q1", "Film", "A film", {}, "Film", {})
    parameters = [
        {"action": "wbsearchentities"},
        {"action": "wbgetentities", "ids": "Q1"},
        {"action": "wbgetentities", "props": "labels"},
    ]
    for (matches, _), params in zip(routes[:3], parameters):
        assert matches(url, params) is expected


def item(qid):
    return {"mainsnak": {"snaktype": "value", "datavalue": {"value": {"id": qid}}}, "rank": "normal"}


def string(value, qualifiers=None):
    claim = {"mainsnak": {"snaktype": "value", "datavalue": {"value": value}}, "rank": "normal"}
    if qualifiers:
        claim["qualifiers"] = qualifiers
    return claim


def test_movie_metadata_from_wikidata_and_wikipedia():
    claims = {
        "P577": [string({"time": "+2014-11-07T00:00:00Z", "precision": 11}), string({"time": "+2014-10-26T00:00:00Z", "precision": 11})],
        "P57": [item("Q25191")],
        "P2047": [string({"amount": "+169", "unit": "minute"})],
        "P136": [item("Q471839")],
        "P1651": [string("zSWdZVtXT7E"), string("not a video id!")],
        "P345": [string("tt0816692")],
        "P444": [string("73%", {"P447": [{"datavalue": {"value": {"id": "Q105584"}}}]}),
                 string("74/100", {"P447": [{"datavalue": {"value": {"id": "Q150248"}}}]}),
                 string("junk", {"P447": [{"datavalue": {"value": {"id": "Q150248"}}}]})],
    }
    client = FakeClient(wikidata_routes("Q13417189", "Interstellar", "2014 film directed by Christopher Nolan", claims,
                                        "Interstellar (film)", {"Q25191": "Christopher Nolan", "Q471839": "science fiction film"}))
    data = asyncio.run(title_metadata.fetch(client, "movie", "Interstellar", 2014))
    assert data["release_date"] == "2014-10-26"
    assert {"label": "Director", "value": "Christopher Nolan"} in data["facts"]
    assert {"label": "Running time", "value": "169 min"} in data["facts"]
    assert data["trailer"] == "zSWdZVtXT7E"
    assert data["scores"] == [{"source": "Metacritic", "value": "74/100"}, {"source": "Rotten Tomatoes", "value": "73%"}]
    assert data["description"] == "Interstellar is a work."
    assert data["description_source"]["license"] == "CC BY-SA 4.0"
    assert {"label": "IMDb", "url": "https://www.imdb.com/title/tt0816692/"} in data["links"]
    assert not any("omdbapi" in url for url, _ in client.calls)


def test_wrong_kind_or_year_is_not_matched():
    client = FakeClient([(lambda url, params: params.get("action") == "wbsearchentities",
                          {"search": [{"id": "Q9", "label": "Dune", "description": "1965 novel by Frank Herbert"},
                                      {"id": "Q8", "label": "Dune", "description": "1984 film by David Lynch"}]})])
    assert asyncio.run(title_metadata._wikidata_find(client, "movie", "Dune", 2021)) is None
    assert asyncio.run(title_metadata._wikidata_find(client, "movie", "Dune", 1984)) == "Q8"
    assert asyncio.run(title_metadata._wikidata_find(client, "book", "Dune", 1965)) == "Q9"


def test_tv_metadata_uses_tvmaze_images_and_summary():
    show = {"id": 7, "name": "Severance", "premiered": "2022-02-18", "status": "Running", "network": None,
            "webChannel": {"name": "Apple TV+"}, "genres": ["Drama", "Thriller"], "rating": {"average": 8.4},
            "image": {"original": "https://static.tvmaze.com/p.jpg"}, "summary": "<p>Mark leads a team.</p>",
            "officialSite": "https://tv.apple.com/severance", "averageRuntime": 50, "url": "https://www.tvmaze.com/shows/7"}
    client = FakeClient([
        (lambda url, params: url.endswith("/search/shows"), [{"show": show}]),
        (lambda url, params: url.endswith("/shows/7/images"), [
            {"type": "background", "resolutions": {"original": {"url": "https://static.tvmaze.com/bg.jpg"}, "medium": {"url": "https://static.tvmaze.com/bg-m.jpg"}}},
            {"type": "poster", "resolutions": {"original": {"url": "https://static.tvmaze.com/poster.jpg"}}},
        ]),
        (lambda url, params: url.endswith("/shows/7/seasons"), [{}, {}]),
    ])
    data = asyncio.run(title_metadata.fetch(client, "tv", "Severance", 2022))
    assert data["description"] == "Mark leads a team."
    assert data["description_source"]["name"] == "TVmaze"
    assert data["gallery"] == [{"url": "https://static.tvmaze.com/bg.jpg", "thumb": "https://static.tvmaze.com/bg-m.jpg"}]
    assert {"label": "Network", "value": "Apple TV+"} in data["facts"] and {"label": "Seasons", "value": "2"} in data["facts"]
    assert {"source": "TVmaze members", "value": "8.4/10"} in data["scores"]


def test_game_metadata_uses_rawg_with_attribution(monkeypatch):
    monkeypatch.setenv("RAWG_API_KEY", "k")
    client = FakeClient([
        (lambda url, params: url.endswith("/api/games") and params.get("search"), {"results": [{"id": 3, "slug": "hades", "name": "Hades", "released": "2020-09-17"}]}),
        (lambda url, params: url.endswith("/api/games/3"), {"slug": "hades", "description_raw": "Defy the god of the dead.", "metacritic": 93,
                                                            "platforms": [{"platform": {"name": "PC"}}], "developers": [{"name": "Supergiant Games"}],
                                                            "genres": [{"name": "Action"}], "background_image": "https://media.rawg.io/media/games/h.jpg"}),
        (lambda url, params: url.endswith("/api/games/3/screenshots"), {"results": [{"image": "https://media.rawg.io/media/screenshots/s.jpg"}]}),
    ])
    data = asyncio.run(title_metadata.fetch(client, "game", "Hades", 2020))
    assert data["description_source"]["name"] == "RAWG"
    assert {"source": "Metacritic", "value": "93/100"} in data["scores"]
    assert data["gallery"][0]["thumb"] == "https://media.rawg.io/media/resize/640/-/screenshots/s.jpg"
    assert any(link["url"] == "https://rawg.io/games/hades" for link in data["links"])


def test_anime_metadata_never_copies_the_synopsis():
    client = FakeClient([(lambda url, params: "jikan" in url, {"data": [{
        "title": "Jujutsu Kaisen", "titles": [], "url": "https://myanimelist.net/anime/40748", "synopsis": "COPYRIGHTED TEXT",
        "aired": {"from": "2020-10-03T00:00:00+00:00"}, "episodes": 24, "studios": [{"name": "MAPPA"}], "score": 8.6,
        "trailer": {"youtube_id": "pkKu9hLT-t8"}, "images": {"jpg": {"large_image_url": "https://cdn.myanimelist.net/x.jpg"}}}]})])
    data = asyncio.run(title_metadata.fetch(client, "anime", "Jujutsu Kaisen", 2020))
    assert "COPYRIGHTED" not in json.dumps(data)
    assert data["trailer"] == "pkKu9hLT-t8" and {"label": "Studio", "value": "MAPPA"} in data["facts"]


def test_album_track_list_from_itunes():
    client = FakeClient([
        (lambda url, params: url.endswith("/search"), {"results": [{"collectionId": 9, "collectionName": "In Rainbows", "artistName": "Radiohead",
                                                                   "artworkUrl100": "https://is1.mzstatic.com/a/100x100bb.jpg", "trackCount": 10,
                                                                   "releaseDate": "2007-10-10T07:00:00Z", "collectionViewUrl": "https://music.apple.com/x"}]}),
        (lambda url, params: url.endswith("/lookup"), {"results": [{"wrapperType": "collection"},
                                                                   {"wrapperType": "track", "trackName": "15 Step", "trackTimeMillis": 237000}]}),
    ])
    data = asyncio.run(title_metadata.fetch(client, "album", "In Rainbows", 2007, "Radiohead"))
    assert data["tracks"] == [{"name": "15 Step", "duration": "3:57"}]
    assert data["poster"] == "https://is1.mzstatic.com/a/600x600bb.jpg"


def test_slow_or_broken_sources_just_mean_less_information():
    class Broken:
        async def get(self, *args, **kwargs):
            raise RuntimeError("down")
    assert asyncio.run(title_metadata.fetch(Broken(), "movie", "Interstellar", 2014)) == {}


# ---------------------------------------------------------------- cache

def test_cache_freshness_and_keeping_the_last_good_copy(db_session):
    key = "movie:interstellar:2014"
    assert title_metadata.cached(db_session, key) == (None, False)
    title_metadata.store(db_session, key, {"description": "good"}, "ok")
    assert title_metadata.cached(db_session, key) == ({"description": "good"}, True)
    title_metadata.store(db_session, key, None, "error")  # a failed refresh keeps the old copy
    data, fresh = title_metadata.cached(db_session, key)
    assert data == {"description": "good"}
    row = db_session.query(models.TitleMetadata).filter_by(key=key).one()
    row.fetched_at = datetime.utcnow() - timedelta(days=31)
    db_session.commit()
    assert title_metadata.cached(db_session, key) == ({"description": "good"}, False)


def test_get_or_fetch_without_network_uses_the_cache(db_session):
    title_metadata.store(db_session, "movie:interstellar:2014", {"description": "cached"}, "ok")
    data = asyncio.run(title_metadata.get_or_fetch(db_session, None, "movie", "interstellar", "Interstellar", 2014))
    assert data == {"description": "cached"}


def test_warm_up_fetches_uncached_titles(db_session, monkeypatch):
    from tests.conftest import TestingSessionLocal
    add_movie(db_session, member(db_session, "writer"), review=LONG_REVIEW, review_public=True)
    db_session.commit()
    fetched = []

    async def fake_fetch(client, category, title, year, creator=None):
        fetched.append((category, title, year, creator))
        return {"description": "x"}

    monkeypatch.setattr(title_metadata, "fetch", fake_fetch)
    real_sleep = asyncio.sleep
    monkeypatch.setattr(titles_router.asyncio, "sleep", lambda *_: real_sleep(0))
    count = asyncio.run(titles_router.warm_metadata(TestingSessionLocal, object()))
    assert count == 1 and fetched == [("movie", "Interstellar", 2014, "Christopher Nolan")]
    assert asyncio.run(titles_router.warm_metadata(TestingSessionLocal, object())) == 0  # now cached


def test_site_stats_reports_title_detail_coverage(authenticated_client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "testuser")
    title_metadata.store(db_session, "movie:a:2000", {"description": "x"}, "ok")
    title_metadata.store(db_session, "movie:b:2000", None, "miss")
    details = authenticated_client.get("/api/site-stats/overview").json()["system"]["title_details"]
    assert details == {"found": 1, "not_found": 1, "errors": 0}
