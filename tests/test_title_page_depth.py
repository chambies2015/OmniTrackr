"""Title pages, Oct 31: finding facts for more titles, moved links, overview, quick answers, genre matches."""
import asyncio
import json
import re
from datetime import datetime, timedelta

import pytest

from app import models, title_metadata, title_pages
from tests.test_title_pages import ESSAY, FakeClient, FakeResponse, add_movie, member, seed_metadata


def search_route(results):
    return (lambda url, params: url == "https://www.wikidata.org/w/api.php" and params.get("action") == "wbsearchentities",
            {"search": results})


# ---------------------------------------------------------------- finding the right entry

def test_alias_names_count_as_the_title():
    # Wikidata labels the anime "Dandadan" and lists "Dan Da Dan" as an alias, which is what members type.
    client = FakeClient([search_route([
        {"id": "Q1", "label": "Dandadan", "description": "Japanese manga series", "aliases": ["Dan Da Dan"],
         "match": {"type": "alias", "text": "Dan Da Dan"}},
        {"id": "Q2", "label": "Dandadan", "description": "Japanese anime television series", "aliases": ["Dan Da Dan"],
         "match": {"type": "alias", "text": "Dan Da Dan"}},
    ])])
    assert asyncio.run(title_metadata._wikidata_find(client, "anime", "Dan Da Dan", 2024)) == "Q2"


def test_an_exact_alias_is_enough_when_the_description_has_no_year():
    client = FakeClient([search_route([
        {"id": "Q3", "label": "Frieren", "description": "Japanese anime television series",
         "match": {"type": "alias", "text": "Frieren: Beyond Journey's End"}},
    ])])
    assert asyncio.run(title_metadata._wikidata_find(client, "anime", "Frieren: Beyond Journey's End", 2023)) == "Q3"
    # Without the alias it is only a prefix match, which a year can't confirm.
    client = FakeClient([search_route([{"id": "Q3", "label": "Frieren", "description": "Japanese anime television series"}])])
    assert asyncio.run(title_metadata._wikidata_find(client, "anime", "Frieren: Beyond Journey's End", 2023)) is None


def test_crowded_searches_fall_back_to_the_wikipedia_article():
    crowded = [{"id": f"Q{n}", "label": "Superman", "description": "fictional superhero"} for n in range(12)]
    pages = {
        "Superman_%282025_film%29": {"type": "standard", "title": "Superman (2025 film)", "wikibase_item": "Q116547790",
                                       "description": "DC Studios film by James Gunn"},
    }

    def wiki(url, params):
        return url.startswith("https://en.wikipedia.org/api/rest_v1/page/summary/") and url.rsplit("/", 1)[1] in pages

    class Client(FakeClient):
        async def get(self, url, params=None, headers=None, timeout=None, follow_redirects=None):
            if wiki(url, params):
                self.calls.append((url, {}))
                return FakeResponse(pages[url.rsplit("/", 1)[1]])
            return await super().get(url, params, headers, timeout, follow_redirects)

    client = Client([search_route(crowded)])
    assert asyncio.run(title_metadata._wikidata_find(client, "movie", "Superman", 2025)) is None
    assert asyncio.run(title_metadata._wikipedia_find(client, "movie", "Superman", 2025)) == "Q116547790"
    # The 1978 article is a different film: a year in the description has to agree.
    pages["Superman_%281978_film%29"] = {"type": "standard", "title": "Superman (1978 film)", "wikibase_item": "Q213053",
                                         "description": "1978 film by Richard Donner"}
    pages.pop("Superman_%282025_film%29")
    pages["Superman_%28film%29"] = pages["Superman_%281978_film%29"]
    assert asyncio.run(title_metadata._wikipedia_find(client, "movie", "Superman", 2025)) is None


@pytest.mark.parametrize("wanted,found,expected", [
    ("Pokemon", "Pokémon", True),
    ("Fast & Furious", "Fast and Furious", True),
    ("Dune", "Dune: Part Two", True),
    ("Dune", "Dunkirk", False),
])
def test_title_matching_ignores_accents_and_ampersands(wanted, found, expected):
    assert title_metadata._title_matches(wanted, found) is expected


@pytest.mark.parametrize("category,title,expected", [
    ("tv", "Arcane (Season 2)", "Arcane"),
    ("tv", "Breaking Bad Season 1", "Breaking Bad"),
    ("anime", "Jujutsu Kaisen - Season 2", "Jujutsu Kaisen"),
    ("album", "In Rainbows [Deluxe Edition]", "In Rainbows"),
    ("movie", "Interstellar", None),
    ("movie", "Fast Five", None),
    ("movie", "Season 2", None),
])
def test_simpler_titles_for_a_second_try(category, title, expected):
    assert title_metadata.simpler_title(category, title) == expected


def test_a_second_try_with_the_simpler_title():
    client = FakeClient([search_route([{"id": "Q5", "label": "Arcane", "description": "2021 animated television series"}])])
    seen = []
    original = title_metadata._wikidata_find

    async def spy(client, category, title, year):
        seen.append(title)
        return None

    title_metadata._wikidata_find = spy
    try:
        asyncio.run(title_metadata.fetch(client, "tv", "Arcane (Season 2)", 2021))
    finally:
        title_metadata._wikidata_find = original
    assert seen == ["Arcane (Season 2)", "Arcane"]


def test_rate_limits_are_errors_not_misses(db_session):
    class Limited:
        async def get(self, *args, **kwargs):
            return FakeResponse({}, 429)

    assert asyncio.run(title_metadata.get_or_fetch(db_session, Limited(), "movie", "dune", "Dune", 2021)) is None
    assert db_session.query(models.TitleMetadata).filter_by(key="movie:dune:2021").one().status == "error"


def test_partial_results_are_checked_again_sooner(db_session):
    title_metadata.store(db_session, "anime:x:2020", {"description": "x", "partial": True}, "ok")
    title_metadata.store(db_session, "anime:y:2020", {"description": "y"}, "ok")
    for key in ("anime:x:2020", "anime:y:2020"):
        row = db_session.query(models.TitleMetadata).filter_by(key=key).one()
        row.fetched_at = datetime.utcnow() - timedelta(days=2)
    db_session.commit()
    assert title_metadata.cached(db_session, "anime:x:2020")[1] is False
    assert title_metadata.cached(db_session, "anime:y:2020")[1] is True


def test_misses_from_the_old_matcher_get_one_more_look(db_session):
    title_metadata.store(db_session, "anime:dan da dan:2024", None, "miss")
    title_metadata.store(db_session, "where:movie:dune:2021", None, "miss")
    for row in db_session.query(models.TitleMetadata):
        row.fetched_at = title_metadata.MATCHER_UPDATED - timedelta(hours=1)
    db_session.commit()
    assert title_metadata.cached(db_session, "anime:dan da dan:2024")[1] is False
    # Where-to-watch answers didn't change; they keep their own schedule.
    assert title_metadata.cached(db_session, "where:movie:dune:2021", {"miss": timedelta(days=3), "error": timedelta(hours=6)})[1] is True


def test_site_stats_counts_title_facts_without_where_to_watch(authenticated_client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "testuser")
    title_metadata.store(db_session, "movie:a:2000", {"description": "x"}, "ok")
    title_metadata.store(db_session, "where:movie:a:2000", None, "miss")
    title_metadata.store(db_session, "where:movie:b:2000", None, "miss")
    details = authenticated_client.get("/api/site-stats/overview").json()["system"]["title_details"]
    assert details == {"found": 1, "not_found": 0, "errors": 0}


# ---------------------------------------------------------------- moved links

def test_a_fixed_year_redirects_the_old_link(client, db_session):
    add_movie(db_session, member(db_session, "a"), year=2015)  # someone fixes it to 2014 later
    db_session.commit()
    movie = db_session.query(models.Movie).one()
    movie.year = 2014
    db_session.commit()
    title_pages.SLUG_INDEX.clear()
    response = client.get("/titles/movie/interstellar-2015?take=abcdefghijklmnop1234", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["location"] == "/titles/movie/interstellar-2014?take=abcdefghijklmnop1234"
    assert client.get("/titles/movie/interstellar", follow_redirects=False).headers["location"] == "/titles/movie/interstellar-2014"


def test_titles_with_a_number_at_the_end_keep_it(client, db_session):
    add_movie(db_session, member(db_session, "a"), title="Blade Runner 2049", year=2017)
    add_movie(db_session, member(db_session, "b"), title="Blade Runner", year=1982)
    db_session.commit()
    response = client.get("/titles/movie/blade-runner-2049", follow_redirects=False)
    assert response.headers["location"] == "/titles/movie/blade-runner-2049-2017"


def test_ambiguous_or_distant_links_still_404(client, db_session):
    add_movie(db_session, member(db_session, "a"), title="Dune", year=1984)
    add_movie(db_session, member(db_session, "b"), title="Dune", year=2021)
    db_session.commit()
    assert client.get("/titles/movie/dune", follow_redirects=False).status_code == 404
    assert client.get("/titles/movie/dune-2000", follow_redirects=False).status_code == 404
    assert client.get("/titles/movie/dune-2022", follow_redirects=False).headers["location"] == "/titles/movie/dune-2021"


def test_private_titles_are_not_found_through_a_redirect(client, db_session):
    user = member(db_session, "a")
    user.movies_private = True
    add_movie(db_session, user, year=2014)
    db_session.commit()
    assert client.get("/titles/movie/interstellar-2015", follow_redirects=False).status_code == 404


# ---------------------------------------------------------------- overview, quick answers, genre matches

FULL = {
    "category": "movie", "description": "Interstellar is a 2014 epic science fiction film.",
    "short_description": "2014 film by Christopher Nolan", "release_date": "2014-10-26",
    "facts": [{"label": "Director", "value": "Christopher Nolan"},
              {"label": "Starring", "value": "Matthew McConaughey, Anne Hathaway, Jessica Chastain, Michael Caine"},
              {"label": "Running time", "value": "169 min"}],
    "genres": ["science fiction film", "drama film", "adventure film"], "scores": [], "gallery": [], "links": [], "sources": [],
}


def ld_blocks(html):
    return [json.loads(block) for block in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)]


def test_overview_and_quick_answers(client, db_session):
    for index, rating in enumerate((9, 8, 7, 9)):
        add_movie(db_session, member(db_session, f"m{index}"), rating=rating, watched=index < 3)
    db_session.commit()
    seed_metadata(db_session, FULL)
    title_metadata.store(db_session, "where:movie:interstellar:2014", {
        "groups": [{"label": "Stream", "providers": [{"name": "Paramount+", "url": None}]},
                   {"label": "Rent", "providers": [{"name": "Apple TV", "url": None}, {"name": "Amazon", "url": None}]}],
        "region": "US", "fetched": "2026-10-30"}, "ok")
    html = client.get("/titles/movie/interstellar-2014").text
    overview = ("Interstellar is a 2014 science fiction movie directed by Christopher Nolan and starring "
                "Matthew McConaughey, Anne Hathaway and Jessica Chastain.")
    assert overview not in html  # Wikipedia's lead already says it
    seed_metadata(db_session, {**FULL, "description": None})
    html = client.get("/titles/movie/interstellar-2014").text
    assert overview in html
    for expected in ("Where can I watch Interstellar?",
                     "You can stream it on Paramount+ and rent it from Apple TV and Amazon in the US.",
                     "How long is Interstellar?", "Interstellar runs 169 minutes (2 hours 49 minutes).",
                     "Is Interstellar worth watching?", "OmniTrackr members rate Interstellar 8.2 out of 10 on average, from 4 ratings.",
                     "3 of the 4 members tracking it have watched it.",
                     "When did Interstellar come out?", "Interstellar first came out on October 26, 2014."):
        assert expected in html, expected
    faq = next(block for block in ld_blocks(html) if block["@type"] == "FAQPage")
    assert [q["name"] for q in faq["mainEntity"]][:2] == ["Where can I watch Interstellar?", "How long is Interstellar?"]
    assert all("<" not in q["acceptedAnswer"]["text"] for q in faq["mainEntity"])
    assert 'href="#faq-title">Quick answers</a>' in html


def test_no_quick_answers_without_enough_to_say(client, db_session):
    add_movie(db_session, member(db_session, "solo"))
    db_session.commit()
    seed_metadata(db_session, {**FULL, "facts": [], "release_date": None})
    html = client.get("/titles/movie/interstellar-2014").text
    assert "faq-title" not in html and "FAQPage" not in html


@pytest.mark.parametrize("kind,metadata,creator,expected", [
    ("tv", {"release_date": "2008-01-20", "end_date": "2013-09-29", "genres": ["crime drama"],
            "facts": [{"label": "Created by", "value": "Vince Gilligan"}, {"label": "Original network", "value": "AMC"}]},
     None, "Breaking Bad is a 2008 crime drama TV series created by Vince Gilligan. It ran on AMC from 2008 to 2013."),
    ("game", {"release_date": "2020-09-17", "genres": ["RPG"],
              "facts": [{"label": "Developer", "value": "Supergiant Games"}]},
     None, "Breaking Bad is a 2020 RPG video game developed by Supergiant Games."),
    ("album", {"release_date": "2007-10-10", "genres": ["Alternative"], "facts": []},
     "Radiohead", "Breaking Bad is a 2007 alternative album by Radiohead."),
    ("anime", {"genres": [], "facts": [{"label": "Studio", "value": "MAPPA"}]}, None, "Breaking Bad is an anime series animated by MAPPA."),
])
def test_overview_sentences(kind, metadata, creator, expected):
    from app.routers import titles
    group = title_pages.TitleGroup(kind, "Breaking Bad", None, "breaking bad")
    text, _ = titles._overview(group, {"creator": creator}, metadata)
    assert text == expected


def similar_meta(genres):
    return {**FULL, "genres": genres, "facts": [], "description": "x"}


def test_similar_titles_share_genres(client, db_session):
    a, b = member(db_session, "a"), member(db_session, "b")
    secret = member(db_session, "secret")
    secret.movies_private = True
    add_movie(db_session, a, review=ESSAY, review_public=True)
    for user in (a, b):
        add_movie(db_session, user, title="Arrival", year=2016, director="Denis Villeneuve",
                  poster_url="https://img.example/arrival.jpg")
    add_movie(db_session, a, title="Gravity", year=2013, director="Alfonso Cuarón")
    add_movie(db_session, a, title="Notting Hill", year=1999, director="Roger Michell")
    add_movie(db_session, secret, title="Hidden Gem", year=2010, director="Someone Else")
    db_session.commit()
    seed_metadata(db_session, similar_meta(["science fiction film", "drama film", "adventure film"]))
    seed_metadata(db_session, similar_meta(["Science fiction", "Drama"]), "movie:arrival:2016")
    seed_metadata(db_session, similar_meta(["science fiction film", "thriller film"]), "movie:gravity:2013")
    seed_metadata(db_session, similar_meta(["romantic comedy", "drama film"]), "movie:notting hill:1999")
    seed_metadata(db_session, similar_meta(["science fiction film", "drama film"]), "movie:hidden gem:2010")
    html = client.get("/titles/movie/interstellar-2014").text
    section = html.split('id="similar-title"', 1)[1].split("</section>", 1)[0]
    assert "Movies like Interstellar" in html
    assert 'href="/titles/movie/arrival-2016"' in section and "https://img.example/arrival.jpg" in section
    assert "Science fiction, Drama" in section
    assert "gravity" not in section and "notting-hill" not in section  # one shared genre is not enough
    assert "hidden-gem" not in section  # a private library never feeds public pages
    assert 'href="/titles/movie/interstellar-2014"' not in section


def test_new_sections_do_not_make_a_thin_page_indexable(client, db_session):
    for index in range(4):
        add_movie(db_session, member(db_session, f"m{index}"), rating=8)
    db_session.commit()
    seed_metadata(db_session, FULL)
    response = client.get("/titles/movie/interstellar-2014")
    assert "FAQPage" in response.text
    assert response.headers["x-robots-tag"] == "noindex, follow"
    assert '<meta name="robots" content="noindex, follow">' in response.text
    assert "/static/ad-loader.js" not in response.text
