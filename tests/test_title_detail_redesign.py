"""Title pages, Nov 9 2026 redesign: wide TMDB backdrops, the hero's where-to-watch line, the sticky save bar."""
import asyncio

from app import title_metadata, where_to_watch
from app.routers import titles
from tests.test_title_pages import SAMPLE, FakeClient, add_movie, member, seed_metadata
from tests.test_where_to_watch import MOVIE_META, PROVIDERS

WHERE = {
    "v": 1, "kind": "movie", "region": "US", "justwatch": True, "fetched": "2026-11-09", "backdrop": "/wide.jpg",
    "groups": [{"label": "Stream", "providers": [{"name": "Netflix", "logo": "https://image.tmdb.org/t/p/w92/nf.jpg"},
                                                {"name": "Max"}]},
               {"label": "Rent", "providers": [{"name": "Apple TV"}, {"name": "YouTube"}]}],
    "credits": [{"name": "JustWatch", "url": "https://www.justwatch.com/"}],
}


def page(client, db_session, where=WHERE, data=SAMPLE, poster=None):
    writer = member(db_session, "writer")
    add_movie(db_session, writer, rating=9, watched=True, poster_url=poster)
    db_session.commit()
    seed_metadata(db_session, data)
    if where is not None:
        title_metadata.store(db_session, "where:movie:interstellar:2014", where, "ok")
    response = client.get("/titles/movie/interstellar-2014")
    assert response.status_code == 200
    return response.text


def test_tmdb_backdrop_is_kept_with_the_providers(monkeypatch):
    monkeypatch.setenv("TMDB_API_KEY", "k")
    client = FakeClient([
        (lambda url, params: url.endswith("/find/tt0816692"),
         {"movie_results": [{"id": 157336, "backdrop_path": "/xJHokMbljvjADYdit5fK5VQsXEG.jpg"}], "tv_results": []}),
        (lambda url, params: url.endswith("/movie/157336/watch/providers"), PROVIDERS),
    ])
    data = asyncio.run(where_to_watch.fetch(client, "movie", "Interstellar", 2014, MOVIE_META))
    assert data["backdrop"] == "/xJHokMbljvjADYdit5fK5VQsXEG.jpg"
    assert where_to_watch.backdrop_urls(data) == {
        "w780": "https://image.tmdb.org/t/p/w780/xJHokMbljvjADYdit5fK5VQsXEG.jpg",
        "w1280": "https://image.tmdb.org/t/p/w1280/xJHokMbljvjADYdit5fK5VQsXEG.jpg"}


def test_odd_backdrop_paths_are_dropped():
    assert where_to_watch.backdrop_urls({"backdrop": "/../evil.jpg"}) == {}
    assert where_to_watch.backdrop_urls({"backdrop": "/logo.svg"}) == {}
    assert where_to_watch.backdrop_urls({}) == where_to_watch.backdrop_urls(None) == {}
    assert where_to_watch._backdrop_path({"backdrop_path": "javascript:x"}) is None


def test_hero_uses_the_wide_still_and_says_where_to_watch(client, db_session):
    html = page(client, db_session)
    assert 'class="site title-page title-detail"' in html and "/static/title-detail.css?v=" in html
    assert 'class="title-hero title-hero--wide"' in html
    assert ('srcset="https://image.tmdb.org/t/p/w780/wide.jpg 780w, https://image.tmdb.org/t/p/w1280/wide.jpg 1280w"' in html)
    # The poster stays the page's priority image.
    assert 'class="title-hero__poster" src="https://img.example/p.jpg"' in html and 'fetchpriority="high"' in html
    teaser = html.split('class="title-hero__where"', 1)[1].split("</a>", 1)[0]
    assert 'href="#where-title"' in html and "Netflix and Max" in teaser and "Where to watch · Stream" in teaser
    assert "+2 more" in teaser


def test_without_a_wide_still_the_poster_becomes_a_wash(client, db_session):
    html = page(client, db_session, where=None)
    assert 'class="title-hero title-hero--wash"' in html and "srcset=" not in html.split("</section>", 1)[0]
    assert 'class="title-hero__where"' not in html


def test_kicker_and_repeated_lead(client, db_session):
    html = page(client, db_session)
    hero = html.split('class="title-hero ', 1)[1].split("</section>", 1)[0]
    assert '<span class="title-hero__kind">Movie</span><span>October 26, 2014</span><span>169 min</span>' in hero
    assert '<span class="title-hero__credit">Christopher Nolan</span>' in hero
    # "2014 film by Christopher Nolan" only repeats the line above; it stays in the description.
    assert 'class="title-hero__lead"' not in hero
    assert "2014 film by Christopher Nolan" in html


def test_a_lead_that_adds_something_stays(client, db_session):
    html = page(client, db_session, data={**SAMPLE, "short_description": "space epic about a farmer turned pilot"})
    assert '<p class="title-hero__lead">Space epic about a farmer turned pilot</p>' in html


def test_guest_save_bar_and_join_link(client, db_session):
    html = page(client, db_session)
    assert 'class="title-tabs"' in html and 'aria-label="On this page"' in html
    dock = html.split("data-title-dock", 1)[1].split("</div>", 1)[0]
    assert "data-dock-save>Save to my list</button>" in dock and 'href="/#signup" data-dock-join hidden>Join free</a>' in dock
    assert 'class="title-hero__join"' in html and '<a href="/#signup">Create free account</a>' in html
    # One save button does the saving; the bar only presses it.
    assert html.count("data-guest-save") == 1


def test_members_get_an_add_button_in_the_bar(client, db_session):
    client.cookies.set("omnitrackr_session", "anything")
    html = page(client, db_session)
    assert "data-dock-save>Add to my library</button>" in html and "data-dock-join" not in html
    assert 'class="title-hero__join"' not in html


def test_logo_posters_give_way_to_a_member_cover(client, db_session):
    logo = {**SAMPLE, "poster": "https://upload.wikimedia.org/wikipedia/commons/d/d5/Interstellar_logo.png?utm_source=x"}
    html = page(client, db_session, data=logo, poster="https://image.tmdb.org/t/p/w500/cover.jpg")
    assert 'class="title-hero__poster" src="https://image.tmdb.org/t/p/w500/cover.jpg"' in html
    assert titles._poster_image({"poster": "https://x/Interstellar_poster.jpg"}, {"image": "https://y/c.jpg"}) == "https://x/Interstellar_poster.jpg"
    # With nothing better, the logo still shows.
    assert titles._poster_image({"poster": "https://x/Show_logo.png"}, {}) == "https://x/Show_logo.png"
