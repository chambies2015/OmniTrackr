"""Where to watch / play: sources, caching, the title page section and the library lookup."""
import asyncio
import json
import subprocess
from datetime import datetime, timedelta

from app import models, title_metadata, where_to_watch
from tests.test_title_pages import ESSAY, SAMPLE, FakeClient, add_movie, member, seed_metadata

PROVIDERS = {"results": {
    "US": {"link": "https://www.themoviedb.org/movie/157336-interstellar/watch?locale=US",
           "flatrate": [{"provider_name": "Paramount Plus", "logo_path": "/pp.jpg", "display_priority": 4},
                        {"provider_name": "Netflix", "logo_path": "/nf.jpg", "display_priority": 1}],
           "rent": [{"provider_name": "Apple TV", "logo_path": "/../evil.jpg"}],
           "buy": [{"provider_name": "Apple TV", "logo_path": "/atv.jpg"}]},
    "GB": {"flatrate": [{"provider_name": "Sky Go"}]},
}}
MOVIE_META = {**SAMPLE, "links": SAMPLE["links"] + [{"label": "IMDb", "url": "https://www.imdb.com/title/tt0816692/"}]}


def tmdb_routes():
    return [
        (lambda url, params: url.endswith("/find/tt0816692") and params.get("external_source") == "imdb_id",
         {"movie_results": [{"id": 157336}], "tv_results": []}),
        (lambda url, params: url.endswith("/movie/157336/watch/providers"), PROVIDERS),
    ]


def test_tmdb_providers_grouped_with_justwatch_credit(monkeypatch):
    monkeypatch.setenv("TMDB_API_KEY", "abc123")
    client = FakeClient(tmdb_routes())
    data = asyncio.run(where_to_watch.fetch(client, "movie", "Interstellar", 2014, MOVIE_META))
    assert [g["label"] for g in data["groups"]] == ["Stream", "Rent", "Buy"]
    stream = data["groups"][0]["providers"]
    assert [p["name"] for p in stream] == ["Netflix", "Paramount Plus"]
    assert stream[0]["logo"] == "https://image.tmdb.org/t/p/w92/nf.jpg"
    assert "logo" not in data["groups"][1]["providers"][0], "odd logo paths are dropped"
    assert data["region"] == "US" and data["justwatch"] is True
    assert [c["name"] for c in data["credits"]] == ["JustWatch", "TMDB"]
    assert all(params.get("api_key") == "abc123" for _, params in client.calls)


def test_tmdb_read_token_goes_in_a_header(monkeypatch):
    monkeypatch.setenv("TMDB_API_KEY", "eyJhbGciOi.payload.sig")
    seen = []

    class HeaderClient(FakeClient):
        async def get(self, url, params=None, headers=None, timeout=None, follow_redirects=None):
            seen.append(headers.get("Authorization"))
            return await super().get(url, params, headers, timeout, follow_redirects)

    data = asyncio.run(where_to_watch.fetch(HeaderClient(tmdb_routes()), "movie", "Interstellar", 2014, MOVIE_META))
    assert data["groups"] and set(seen) == {"Bearer eyJhbGciOi.payload.sig"}


def test_region_setting_and_search_fallback(monkeypatch):
    monkeypatch.setenv("TMDB_API_KEY", "k")
    monkeypatch.setenv("WATCH_REGION", "gb")
    client = FakeClient([
        (lambda url, params: url.endswith("/search/movie") and params.get("year") == 2014,
         {"results": [{"id": 1, "title": "Interstellar Wars"}, {"id": 157336, "title": "Interstellar"}]}),
        (lambda url, params: url.endswith("/movie/157336/watch/providers"), PROVIDERS),
    ])
    data = asyncio.run(where_to_watch.fetch(client, "movie", "Interstellar", 2014, SAMPLE))
    assert data["region"] == "GB" and data["groups"][0]["providers"] == [{"name": "Sky Go"}]
    assert where_to_watch.justwatch_search("Spirited Away").startswith("https://www.justwatch.com/gb/search?q=Spirited+Away")


def test_no_tmdb_key_means_no_tmdb_calls(monkeypatch):
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    client = FakeClient(tmdb_routes())
    assert asyncio.run(where_to_watch.fetch(client, "movie", "Interstellar", 2014, MOVIE_META)) == {}
    assert client.calls == []


def test_tv_made_for_service_from_tvmaze(monkeypatch):
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    meta = {"sources": [{"name": "TVmaze", "url": "https://www.tvmaze.com/shows/44933/severance"}]}
    client = FakeClient([(lambda url, params: url == "https://api.tvmaze.com/shows/44933", {
        "webChannel": {"name": "Apple TV+", "officialSite": "https://tv.apple.com/"},
        "officialSite": "https://tv.apple.com/us/show/severance/umc.cmc.1srk2goyh2q2zdxcx605w8vtx"})])
    data = asyncio.run(where_to_watch.fetch(client, "tv", "Severance", 2022, meta))
    assert data["groups"] == [{"label": "Made for", "providers": [
        {"name": "Apple TV+", "url": "https://tv.apple.com/us/show/severance/umc.cmc.1srk2goyh2q2zdxcx605w8vtx"}]}]
    assert data["region"] is None and [c["name"] for c in data["credits"]] == ["TVmaze"]


def test_tvmaze_service_already_listed_by_tmdb_is_not_repeated(monkeypatch):
    monkeypatch.setenv("TMDB_API_KEY", "k")
    meta = {"links": [{"label": "TVmaze", "url": "https://www.tvmaze.com/shows/7/x"},
                      {"label": "IMDb", "url": "https://www.imdb.com/title/tt11280740/"}]}
    client = FakeClient([
        (lambda url, params: url.endswith("/find/tt11280740"), {"movie_results": [], "tv_results": [{"id": 95396}]}),
        (lambda url, params: url.endswith("/tv/95396/watch/providers"),
         {"results": {"US": {"flatrate": [{"provider_name": "Apple TV+"}]}}}),
        (lambda url, params: url == "https://api.tvmaze.com/shows/7", {"webChannel": {"name": "Apple TV+"}}),
    ])
    data = asyncio.run(where_to_watch.fetch(client, "tv", "Severance", 2022, meta))
    assert [g["label"] for g in data["groups"]] == ["Stream"]


def test_anime_official_streams_from_myanimelist(monkeypatch):
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    meta = {"links": [{"label": "MyAnimeList", "url": "https://myanimelist.net/anime/40748"}]}
    client = FakeClient([(lambda url, params: url.endswith("/anime/40748/streaming"), {"data": [
        {"name": "Crunchyroll", "url": "http://www.crunchyroll.com/series/GRDV0019R"},
        {"name": "Netflix", "url": "javascript:alert(1)"}]})])
    data = asyncio.run(where_to_watch.fetch(client, "anime", "Jujutsu Kaisen", 2020, meta))
    assert data["groups"] == [{"label": "Official streams", "providers": [
        {"name": "Crunchyroll", "url": "https://www.crunchyroll.com/series/GRDV0019R"}]}]


def test_game_stores_from_rawg(monkeypatch):
    monkeypatch.setenv("RAWG_API_KEY", "k")
    meta = {"links": [{"label": "RAWG", "url": "https://rawg.io/games/hades"}]}
    client = FakeClient([
        (lambda url, params: url.endswith("/api/games/hades"), {"id": 3, "stores": [
            {"store": {"id": 1, "name": "Steam", "domain": "store.steampowered.com"}},
            {"store": {"id": 6, "name": "Nintendo Store", "domain": "nintendo.com"}},
            {"store": {"id": 9, "name": "Odd", "domain": "not a domain"}}]}),
        (lambda url, params: url.endswith("/api/games/3/stores"),
         {"results": [{"store_id": 1, "url": "https://store.steampowered.com/app/1145360/"}]}),
    ])
    data = asyncio.run(where_to_watch.fetch(client, "game", "Hades", 2020, meta))
    assert data["groups"][0]["label"] == "Buy or play on"
    assert data["groups"][0]["providers"] == [
        {"name": "Steam", "url": "https://store.steampowered.com/app/1145360/"},
        {"name": "Nintendo Store", "url": "https://nintendo.com"}, {"name": "Odd"}]
    assert data["credits"] == [{"name": "RAWG", "url": "https://rawg.io/games/hades"}]


def test_unknown_kinds_are_skipped():
    client = FakeClient([])
    assert asyncio.run(where_to_watch.fetch(client, "person", "Dune", 1965, {})) == {}
    assert asyncio.run(where_to_watch.get_or_fetch(None, client, "person", "x", "x", None, {})) is None
    assert client.calls == []


# ---------------------------------------------------------------- where to listen or read

def test_album_lists_apple_music_and_a_matching_deezer_album():
    meta = {"facts": [{"label": "Artist", "value": "Radiohead"}],
            "links": [{"label": "Apple Music", "url": "https://music.apple.com/us/album/ok-computer/1097861387?uo=4"}]}
    client = FakeClient([(lambda url, params: url == "https://api.deezer.com/search/album"
                          and params["q"] == 'album:"OK Computer" artist:"Radiohead"', {"data": [
        {"title": "OK Computer", "link": "https://www.deezer.com/album/1", "artist": {"name": "A Cover Band"}},
        {"title": "OK Computer OKNOTOK 1997 2017", "link": "https://evil.example/album/2", "artist": {"name": "Radiohead"}},
        {"title": "OK Computer", "link": "https://www.deezer.com/album/14879699", "artist": {"name": "Radiohead"}}]})])
    data = asyncio.run(where_to_watch.fetch(client, "album", "OK Computer", 1997, meta))
    assert data["groups"] == [{"label": "Listen on", "providers": [
        {"name": "Apple Music", "url": "https://music.apple.com/us/album/ok-computer/1097861387"},
        {"name": "Deezer", "url": "https://www.deezer.com/album/14879699"}]}]
    assert [c["name"] for c in data["credits"]] == ["Deezer"] and data["region"] is None


def test_album_still_lists_apple_when_deezer_is_down():
    meta = {"links": [{"label": "Apple Music", "url": "https://music.apple.com/us/album/x/1"}]}

    class Broken(FakeClient):
        async def get(self, *args, **kwargs):
            raise RuntimeError("down")

    data = asyncio.run(where_to_watch.fetch(Broken([]), "album", "X", None, meta))
    assert [p["name"] for p in data["groups"][0]["providers"]] == ["Apple Music"]


def test_podcast_apps_come_from_the_apple_id():
    meta = {"links": [{"label": "Apple Podcasts", "url": "https://podcasts.apple.com/us/podcast/the-daily/id1200361736?uo=4"}]}
    client = FakeClient([(lambda url, params: url == "https://itunes.apple.com/lookup" and params == {"id": "1200361736"},
                          {"results": [{"collectionId": 1200361736, "feedUrl": "https://feeds.simplecast.com/Sl5CSM3S"}]})])
    data = asyncio.run(where_to_watch.fetch(client, "podcast", "The Daily", None, meta))
    assert data["groups"] == [
        {"label": "Listen free on", "providers": [
            {"name": "Apple Podcasts", "url": "https://podcasts.apple.com/us/podcast/the-daily/id1200361736"},
            {"name": "Overcast", "url": "https://overcast.fm/itunes1200361736"},
            {"name": "Pocket Casts", "url": "https://pca.st/itunes/1200361736"}]},
        {"label": "Any podcast app", "providers": [{"name": "RSS feed", "url": "https://feeds.simplecast.com/Sl5CSM3S"}]}]


def test_plain_http_podcast_feeds_are_left_out():
    meta = {"links": [{"label": "Apple Podcasts", "url": "https://podcasts.apple.com/us/podcast/x/id123456"}]}
    client = FakeClient([(lambda url, params: url == "https://itunes.apple.com/lookup",
                          {"results": [{"collectionId": 123456, "feedUrl": "http://example.com/feed.xml"}]})])
    data = asyncio.run(where_to_watch.fetch(client, "podcast", "X", None, meta))
    assert [g["label"] for g in data["groups"]] == ["Listen free on"]


def test_audiobook_links_apple_books_without_any_request():
    meta = {"links": [{"label": "Apple Books", "url": "https://books.apple.com/us/audiobook/project-hail-mary/id1557519850"}]}
    client = FakeClient([])
    data = asyncio.run(where_to_watch.fetch(client, "audiobook", "Project Hail Mary", 2021, meta))
    assert data["groups"][0] == {"label": "Buy or listen on", "providers": [
        {"name": "Apple Books", "url": "https://books.apple.com/us/audiobook/project-hail-mary/id1557519850"}]}
    assert client.calls == []


def test_open_library_read_free_and_borrow():
    meta = {"facts": [{"label": "Author", "value": "Jane Austen, Someone Else"}],
            "links": [{"label": "Open Library", "url": "https://openlibrary.org/works/OL66554W"}]}
    client = FakeClient([(lambda url, params: url == "https://openlibrary.org/search.json" and params.get("author") == "Jane Austen",
                          {"docs": [{"key": "/works/OL1W", "title": "Pride and Prejudice", "ebook_access": "borrowable"},
                                    {"key": "/works/OL66554W", "title": "Pride and Prejudice", "ebook_access": "public",
                                     "lending_edition_s": "OL50444320M"}]})])
    data = asyncio.run(where_to_watch.fetch(client, "book", "Pride and Prejudice", 1813, meta))
    assert data["groups"] == [{"label": "Read free", "providers": [
        {"name": "Open Library", "url": "https://openlibrary.org/books/OL50444320M"}]}]
    assert [c["name"] for c in data["credits"]] == ["Open Library"]

    client = FakeClient([(lambda url, params: url == "https://openlibrary.org/search.json",
                          {"docs": [{"key": "/works/OL9W", "title": "Dune", "ebook_access": "no_ebook"}]})])
    assert asyncio.run(where_to_watch.fetch(client, "book", "Dune", 1965, {})) == {}


def test_manga_lists_only_official_english_publishers():
    meta = {"links": [{"label": "MyAnimeList", "url": "https://myanimelist.net/manga/116778"}]}
    client = FakeClient([
        (lambda url, params: url == "https://api.mangadex.org/manga", {"data": [
            {"attributes": {"title": {"en": "Chainsaw Man (Official Colored)"}, "links": {"mal": "999", "engtl": "https://www.viz.com/x"}}},
            {"attributes": {"title": {"en": "Chainsaw Man"}, "links": {"mal": "116778", "engtl": "https://www.viz.com/chainsaw-man"}}}]}),
        (lambda url, params: url == "https://api.jikan.moe/v4/manga/116778/external", {"data": [
            {"name": "Wikipedia", "url": "https://en.wikipedia.org/wiki/Chainsaw_Man"},
            {"name": "Some scans", "url": "https://scans.example/chainsaw"},
            {"name": "MANGA Plus", "url": "https://mangaplus.shueisha.co.jp/titles/100037"},
            {"name": "VIZ", "url": "https://www.viz.com/shonenjump/chapters/chainsaw-man"}]}),
    ])
    data = asyncio.run(where_to_watch.fetch(client, "manga", "Chainsaw Man", 2018, meta))
    assert data["groups"] == [{"label": "Read officially on", "providers": [
        {"name": "VIZ", "url": "https://www.viz.com/chainsaw-man"},
        {"name": "MANGA Plus", "url": "https://mangaplus.shueisha.co.jp/titles/100037"}]}]
    assert {"name": "MangaDex"} in data["credits"], "named without a link"


def test_search_links_are_encoded_and_only_for_listen_and_read_kinds():
    links = where_to_watch.searches("album", "Kid A & B", "Radiohead")
    assert links[0] == {"name": "Spotify", "url": "https://open.spotify.com/search/Kid%20A%20%26%20B%20Radiohead"}
    assert links[1]["url"] == "https://music.youtube.com/search?q=Kid+A+%26+B+Radiohead"
    assert where_to_watch.searches("manga", "Berserk", "Kentaro Miura")[0]["url"] == "https://global.bookwalker.jp/search/?word=Berserk"
    assert where_to_watch.searches("movie", "Interstellar") == [] and where_to_watch.searches("book", "  ") == []


def test_headings_and_verbs():
    assert where_to_watch.heading("album", "Kid A") == "Where to listen to Kid A"
    assert where_to_watch.heading("manga", "Berserk") == "Where to read Berserk"
    assert where_to_watch.heading("game") == "Where to play"
    assert where_to_watch.heading("movie", "Heat") == "Where to watch Heat"


def test_cache_refreshes_weekly_without_touching_the_facts_cache(db_session):
    key = where_to_watch.cache_key("movie", "interstellar", 2014)
    assert key == "where:movie:interstellar:2014"
    title_metadata.store(db_session, key, {"groups": []}, "ok")
    row = db_session.query(models.TitleMetadata).filter_by(key=key).one()
    row.fetched_at = datetime.utcnow() - timedelta(days=8)
    db_session.commit()
    assert where_to_watch.cached(db_session, key)[1] is False
    assert title_metadata.cached(db_session, key)[1] is True, "facts keep their 30-day window"


# ---------------------------------------------------------------- pages and API

WHERE = {"v": 1, "kind": "movie", "region": "US", "fetched": "2026-10-26", "justwatch": True,
         "link": "https://www.themoviedb.org/movie/157336/watch?locale=US",
         "groups": [{"label": "Stream", "providers": [{"name": "Netflix", "url": "https://www.themoviedb.org/movie/157336/watch?locale=US",
                                                       "logo": "https://image.tmdb.org/t/p/w92/nf.jpg"}]},
                    {"label": "Buy", "providers": [{"name": "Apple <TV>"}]}],
         "credits": [{"name": "JustWatch", "url": "https://www.justwatch.com/"}, {"name": "TMDB", "url": "https://www.themoviedb.org/"}]}


def test_title_page_shows_where_to_watch_with_credits(client, db_session):
    writer = member(db_session, "writer")
    add_movie(db_session, writer, review=ESSAY, review_public=True, rating=9.5, watched=True)
    db_session.commit()
    seed_metadata(db_session)
    title_metadata.store(db_session, "where:movie:interstellar:2014", WHERE, "ok")
    html = client.get("/titles/movie/interstellar-2014").text
    assert 'id="where-title">Where to watch Interstellar</h2>' in html
    assert 'href="#where-title">Where to watch</a>' in html
    assert "https://image.tmdb.org/t/p/w92/nf.jpg" in html and "Apple &lt;TV&gt;" in html
    assert "Showing US availability, checked October 26, 2026." in html
    assert "not endorsed or certified by TMDB" in html and ">JustWatch</a>" in html
    assert "where to watch it (Netflix)" in html


def test_title_page_without_watch_data_has_no_section(client, db_session):
    writer = member(db_session, "writer")
    add_movie(db_session, writer, review=ESSAY, review_public=True, rating=9.5, watched=True)
    db_session.commit()
    seed_metadata(db_session)
    title_metadata.store(db_session, "where:movie:interstellar:2014", None, "miss")
    html = client.get("/titles/movie/interstellar-2014").text
    assert "where-title" not in html


def test_library_lookup_needs_an_account(client):
    assert client.get("/api/where-to-watch", params={"kind": "movie", "title": "Interstellar"}).status_code == 401


def test_library_lookup_returns_cached_services(authenticated_client, db_session):
    title_metadata.store(db_session, "movie:interstellar:2014", MOVIE_META, "ok")
    title_metadata.store(db_session, "where:movie:interstellar:2014", WHERE, "ok")
    response = authenticated_client.get("/api/where-to-watch", params={"kind": "movie", "title": "  Interstellar ", "year": 2014})
    assert response.status_code == 200
    body = response.json()
    assert body["groups"][0]["providers"][0]["name"] == "Netflix"
    assert body["more"] == WHERE["link"] and body["tmdb_notice"] is True
    assert response.headers["Cache-Control"] == "private, no-store"
    assert authenticated_client.get("/api/where-to-watch", params={"kind": "person", "title": "Dune"}).status_code == 404


def test_library_dialog_renders_text_only_and_https_links():
    script = r"""
const { renderWhere, safeUrl } = require('./app/static/title-links.js');
class Node {
  constructor(tag) { this.tagName = tag; this.children = []; this.textContent = ''; this.className = ''; }
  appendChild(child) { this.children.push(child); return child; }
  append(...kids) { kids.forEach(k => this.appendChild(k)); }
  replaceChildren(...kids) { this.children = kids; }
}
global.document = { createElement: tag => new Node(tag) };
const body = new Node('div');
renderWhere(body, { groups: [{ label: 'Stream', providers: [
  { name: '<b>Netflix</b>', url: 'javascript:alert(1)', logo: 'http://x/y.png' },
  { name: 'Max', url: 'https://www.max.com/' }] }], more: 'https://www.justwatch.com/us/search?q=x',
  region: 'US', fetched: '2026-10-26', credits: [{ name: 'JustWatch' }], tmdb_notice: true }, 'movie');
const chips = body.children[0].children[1].children.map(li => li.children[0]);
console.log(JSON.stringify({
  firstTag: chips[0].tagName, firstText: chips[0].children[0].textContent, firstHref: chips[0].href || null,
  secondHref: chips[1].href, more: body.children[1].href, note: body.children[2].textContent,
  safe: [safeUrl('https://a.b'), safeUrl('http://a.b'), safeUrl(null)],
}));
"""
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, cwd=".")
    out = json.loads(result.stdout)
    assert out["firstTag"] == "span" and out["firstText"] == "<b>Netflix</b>" and out["firstHref"] is None
    assert out["secondHref"] == "https://www.max.com/"
    assert out["more"].startswith("https://www.justwatch.com/")
    assert "Data from JustWatch." in out["note"] and "not endorsed or certified by TMDB" in out["note"]
    assert out["safe"] == ["https://a.b", "", ""]


# ---------------------------------------------------------------- listen / read on pages, Amazon links

def add_book(db, user, title="Pride and Prejudice", author="Jane Austen", year=1813):
    book = models.Book(user_id=user.id, title=title, author=author, year=year, review=ESSAY, review_public=True, rating=9.0, read=True)
    db.add(book)
    db.flush()
    return book


BOOK_WHERE = {"v": 1, "kind": "book", "region": None, "fetched": "2026-11-02", "justwatch": False, "link": None,
              "groups": [{"label": "Read free", "providers": [{"name": "Open Library", "url": "https://openlibrary.org/books/OL50444320M"}]}],
              "credits": [{"name": "Open Library", "url": "https://openlibrary.org/"}]}


def test_book_page_shows_where_to_read_and_searches(client, db_session, monkeypatch):
    monkeypatch.delenv("AMAZON_ASSOCIATES_TAG", raising=False)
    add_book(db_session, member(db_session, "reader"))
    db_session.commit()
    title_metadata.store(db_session, "book:pride and prejudice:1813", {"links": [], "sources": []}, "ok")
    title_metadata.store(db_session, "where:book:pride and prejudice:1813", BOOK_WHERE, "ok")
    html = client.get("/titles/book/pride-and-prejudice-1813").text
    assert 'id="where-title">Where to read Pride and Prejudice</h2>' in html
    assert 'href="#where-title">Where to read</a>' in html
    assert "https://openlibrary.org/books/OL50444320M" in html and "Checked November 2, 2026." in html
    assert "Search other services" in html and "https://bookshop.org/search?keywords=Pride+and+Prejudice+Jane+Austen" in html
    assert "amazon.com" not in html and 'rel="sponsored' not in html


def test_quick_answer_wording_for_listen_and_read():
    from types import SimpleNamespace
    from app.routers import titles
    question, text, _ = titles._where_answer(SimpleNamespace(kind="book", title="Emma"), {"where": BOOK_WHERE})
    assert question == "Where can I read Emma?" and text.startswith("You can read it free on Open Library.")
    podcast = {"groups": [{"label": "Listen free on", "providers": [{"name": "Apple Podcasts"}, {"name": "Overcast"}]},
                          {"label": "Any podcast app", "providers": [{"name": "RSS feed"}]}]}
    question, text, _ = titles._where_answer(SimpleNamespace(kind="podcast", title="The Daily"), {"where": podcast})
    assert question == "Where can I listen to The Daily?"
    assert "listen free on Apple Podcasts and Overcast" in text and "RSS feed to any podcast app" in text


def test_amazon_link_needs_the_tag_and_is_marked_sponsored(client, db_session, monkeypatch):
    monkeypatch.setenv("AMAZON_ASSOCIATES_TAG", "omnitrackr-20")
    add_book(db_session, member(db_session, "reader"))
    db_session.commit()
    title_metadata.store(db_session, "book:pride and prejudice:1813", {"links": [], "sources": []}, "ok")
    title_metadata.store(db_session, "where:book:pride and prejudice:1813", None, "miss")
    html = client.get("/titles/book/pride-and-prejudice-1813").text
    assert "Buy a copy" in html and "tag=omnitrackr-20" in html and "i=stripbooks" in html
    assert 'rel="sponsored noopener"' in html and "As an Amazon Associate" in html


def test_audiobook_amazon_link_searches_audible(monkeypatch):
    from app import affiliate
    monkeypatch.setenv("AMAZON_ASSOCIATES_TAG", "omnitrackr-20")
    link = affiliate.links_for("audiobook", "Project Hail Mary", "Andy Weir")[0]
    assert "i=audible" in link["url"] and link["label"] == "Find the audiobook on Audible"
    assert affiliate.links_for("podcast", "The Daily") == []


def test_library_lookup_covers_books_with_searches(authenticated_client, db_session, monkeypatch):
    monkeypatch.delenv("AMAZON_ASSOCIATES_TAG", raising=False)
    title_metadata.store(db_session, "book:dune:1965", {"links": []}, "ok")
    title_metadata.store(db_session, "where:book:dune:1965", None, "miss")
    body = authenticated_client.get("/api/where-to-watch", params={"kind": "book", "title": "Dune", "year": 1965}).json()
    assert body["groups"] == [] and body["buy"] == [] and body["heading"] == "Where to read"
    assert [s["name"] for s in body["searches"]][1] == "Bookshop.org"


def test_library_dialog_renders_amazon_and_searches():
    script = r"""
const { renderWhere } = require('./app/static/title-links.js');
class Node {
  constructor(tag) { this.tagName = tag; this.children = []; this.textContent = ''; this.className = ''; }
  appendChild(child) { this.children.push(child); return child; }
  append(...kids) { kids.forEach(k => this.appendChild(k)); }
  replaceChildren(...kids) { this.children = kids; }
}
global.document = { createElement: tag => new Node(tag) };
const body = new Node('div');
renderWhere(body, { groups: [], buy: [{ name: 'Amazon', url: 'https://www.amazon.com/s?k=x&tag=t' }, { name: 'Bad', url: 'javascript:1' }],
  disclosure: 'As an Amazon Associate we earn.', searches: [{ name: 'Libro.fm', url: 'https://libro.fm/search?q=x' }] }, 'audiobook');
const buy = body.children[1];
const search = body.children[2];
console.log(JSON.stringify({
  empty: body.children[0].textContent, buyLabel: buy.children[0].textContent, buyCount: buy.children[1].children.length,
  rel: buy.children[1].children[0].children[0].rel, search: search.children[1].children[0].children[0].href,
  note: body.children[3].textContent,
}));
"""
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, cwd=".").stdout)
    assert out["empty"] == "We could not find listening services for this title yet."
    assert out["buyLabel"] == "Buy a copy" and out["buyCount"] == 1 and out["rel"] == "sponsored noopener"
    assert out["search"] == "https://libro.fm/search?q=x" and "Amazon Associate" in out["note"]
