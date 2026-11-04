"""Sharing a link or text from another app into the installed OmniTrackr app."""
import json
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import httpx
import pytest

from app import share_intake
from app.main import app


def test_manifest_lists_the_app_as_a_share_target(client):
    data = json.loads(client.get("/manifest.webmanifest").text)
    assert data["share_target"] == {
        "action": "/share", "method": "GET", "params": {"title": "title", "text": "text", "url": "url"},
    }


@pytest.mark.parametrize("fields, query, kind, source, year", [
    # IMDb's app shares a line of text plus the link.
    ({"text": "Dune: Part Two (2024) ⭐ 8.5 | Action, Adventure, Drama\nhttps://www.imdb.com/title/tt15239678/?ref_=ext_shr_lnk"},
     "Dune: Part Two", "screen", "imdb", "2024"),
    ({"title": "Breaking Bad (TV Series 2008–2013) - IMDb", "url": "https://m.imdb.com/title/tt0903747/"},
     "Breaking Bad", "tv-shows", "imdb", "2008"),
    ({"title": "The Dark Side of the Moon - Album by Pink Floyd | Spotify", "url": "https://open.spotify.com/album/4LH4d3"},
     "The Dark Side of the Moon Pink Floyd", "music", "spotify", None),
    ({"text": "Check out The Dark Side of the Moon by Pink Floyd on Spotify https://open.spotify.com/album/4LH4d3"},
     "The Dark Side of the Moon Pink Floyd", "music", "spotify", None),
    ({"title": "Dune by Frank Herbert | Goodreads", "url": "https://www.goodreads.com/book/show/44767458-dune"},
     "Dune Frank Herbert", "books", "goodreads", None),
    # Only a link: the title comes from the address.
    ({"text": "https://www.goodreads.com/book/show/44767458-dune"}, "Dune", "books", "goodreads", None),
    ({"text": "https://myanimelist.net/anime/52991/Sousou_no_Frieren"}, "Sousou no Frieren", "anime", "myanimelist", None),
    ({"title": "Frieren: Beyond Journey's End (Sousou no Frieren) - MyAnimeList.net",
      "url": "https://myanimelist.net/anime/52991/Sousou_no_Frieren"},
     "Frieren: Beyond Journey's End", "anime", "myanimelist", None),
    ({"text": "https://anilist.co/manga/30013/One-Piece/"}, "One Piece", "manga", "anilist", None),
    ({"text": "https://store.steampowered.com/app/1145360/Hades/"}, "Hades", "video-games", "steam", None),
    ({"text": "Hades on Steam https://store.steampowered.com/app/1145360/Hades/"}, "Hades", "video-games", "steam", None),
    ({"text": "https://letterboxd.com/film/past-lives/"}, "Past Lives", "movies", "letterboxd", None),
    ({"text": "https://www.themoviedb.org/tv/1396-breaking-bad"}, "Breaking Bad", "tv-shows", "tmdb", None),
    ({"text": "Watch Stranger Things | Netflix Official Site https://www.netflix.com/title/80057281"},
     "Stranger Things", "screen", "netflix", None),
    ({"text": "https://www.audible.com/pd/Project-Hail-Mary-Audiobook/B08G9PRS1K"},
     "Project Hail Mary", "audiobooks", "audible", None),
    ({"text": "https://podcasts.apple.com/us/podcast/the-daily/id1200361736"}, "The Daily", "podcasts", "applepodcasts", None),
    ({"text": "https://music.apple.com/us/album/folklore/1524801260"}, "Folklore", "music", "applemusic", None),
    # YouTube titles lose the trailer and channel parts.
    ({"title": "Dune: Part Two | Official Trailer 3", "url": "https://youtu.be/Way9Dexny3w"}, "Dune: Part Two", None, "youtube", None),
    ({"text": "The Bear | Season 3 Official Trailer | FX", "url": "https://www.youtube.com/watch?v=x"}, "The Bear", None, "youtube", None),
    # Plain text keeps titles that contain dashes or the word "by".
    ({"text": "Mission: Impossible - Dead Reckoning Part One"}, "Mission: Impossible - Dead Reckoning Part One", None, None, None),
    ({"text": "Stand by Me"}, "Stand by Me", None, None, None),
    ({"text": "Spider-Man: Across the Spider-Verse"}, "Spider-Man: Across the Spider-Verse", None, None, None),
])
def test_read_share_finds_the_title(fields, query, kind, source, year):
    shared = share_intake.read_share(**fields)
    assert (shared.search_query(), shared.kind, shared.source, shared.year) == (query, kind, source, year)


def test_read_share_keeps_the_imdb_id_and_ignores_links_with_no_title():
    assert share_intake.read_share(url="https://www.imdb.com/title/tt15239678/").imdb_id == "tt15239678"
    bare = share_intake.read_share(url="https://open.spotify.com/album/4LH4d3cOWNNsVw41Gqt2kv?si=abc")
    assert (bare.query, bare.kind, bare.link) == ("", "music", "https://open.spotify.com/album/4LH4d3cOWNNsVw41Gqt2kv")
    assert share_intake.needs_name_lookup(bare)
    assert share_intake.read_share(text="Spotify").query == ""
    assert share_intake.read_share().dashboard_path() == "/?share=1"


def test_read_share_survives_hostile_input():
    junk = share_intake.read_share(title="x" * 50_000, text="javascript:alert(1) <script>", url="ftp://example.com/a")
    assert len(junk.query) <= share_intake.MAX_QUERY and junk.source is None
    long_japanese = share_intake.read_share(text="葬送のフリーレン" * 30)
    path = long_japanese.dashboard_path()
    assert len(parse_qs(urlsplit(path).query)["q"][0]) >= 10
    assert len(path.split("q=")[1].split("&")[0]) <= share_intake.MAX_ENCODED_QUERY


def test_dashboard_path_has_a_fixed_shape():
    shared = share_intake.SharedTitle(query="Dune: Part Two", kind="movies", source="imdb", year="2024")
    assert shared.dashboard_path() == "/?share=1&q=Dune%3A%20Part%20Two&kind=movies&year=2024&via=imdb"


def test_signed_out_share_waits_for_the_log_in_form(client):
    response = client.get("/share", params={"text": "https://letterboxd.com/film/past-lives/"}, follow_redirects=False)
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/?next=") and location.endswith("#login")
    assert unquote(location[len("/?next="):-len("#login")]) == "/?share=1&q=Past%20Lives&kind=movies&via=letterboxd"
    assert response.headers["cache-control"] == "private, no-store"


def test_signed_in_share_opens_add_anything(authenticated_client):
    response = authenticated_client.get("/share", params={"title": "Hades on Steam", "url": "https://store.steampowered.com/app/1145360/Hades/"},
                                        follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/?share=1&q=Hades&kind=video-games&via=steam"
    # The dashboard itself loads with the share in the address.
    assert authenticated_client.get(response.headers["location"]).status_code == 200


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        status, body = self.responses.get(url, (500, {}))
        if isinstance(body, Exception):
            raise body
        return httpx.Response(status, json=body)

    async def aclose(self):
        pass


def test_signed_in_share_looks_up_imdb_and_spotify_names(authenticated_client, monkeypatch):
    fake = FakeClient({
        "https://www.omdbapi.com/": (200, {"Response": "True", "Title": "Dune: Part Two", "Year": "2024", "Type": "movie"}),
        "https://open.spotify.com/oembed": (200, {"title": "Abbey Road (Remastered)"}),
    })
    monkeypatch.setattr(app.state, "external_api_client", fake)
    monkeypatch.setenv("OMDB_API_KEY", "test-key")
    imdb = authenticated_client.get("/share", params={"url": "https://www.imdb.com/title/tt15239678/"}, follow_redirects=False)
    assert imdb.headers["location"] == "/?share=1&q=Dune%3A%20Part%20Two&kind=movies&year=2024&via=imdb"
    assert fake.calls[0][1]["i"] == "tt15239678"
    spotify = authenticated_client.get("/share", params={"text": "https://open.spotify.com/album/0ETFjACtuP2ADo6LFhL6HN?si=x"},
                                       follow_redirects=False)
    assert spotify.headers["location"] == "/?share=1&q=Abbey%20Road&kind=music&via=spotify"
    # Only the clean address goes to Spotify, never the tracking bits.
    assert fake.calls[1][1]["url"] == "https://open.spotify.com/album/0ETFjACtuP2ADo6LFhL6HN"


def test_lookups_fall_back_quietly_and_never_run_signed_out(client, monkeypatch):
    fake = FakeClient({"https://www.youtube.com/oembed": (200, {"title": "x"}),
                       "https://www.omdbapi.com/": (0, httpx.ConnectTimeout("slow"))})
    monkeypatch.setattr(app.state, "external_api_client", fake)
    monkeypatch.setenv("OMDB_API_KEY", "test-key")
    client.get("/share", params={"url": "https://youtu.be/abc"}, follow_redirects=False)
    assert fake.calls == []

    import asyncio
    shared = share_intake.read_share(text="Dune (2021) https://www.imdb.com/title/tt1160419/")
    kept = asyncio.run(share_intake.lookup_extras(shared, fake, signed_in=True))
    assert (kept.query, kept.kind, kept.year) == ("Dune", "screen", "2021")


def test_share_is_kept_out_of_search_engines(client):
    assert "Disallow: /share\n" in client.get("/robots.txt").text


def test_dashboard_has_the_share_note_and_styles():
    html = Path("app/templates/index.html").read_text(encoding="utf-8")
    assert '<p id="quickCaptureShared" class="quick-capture-shared" tabindex="-1" hidden></p>' in html
    assert '/static/share-intake.css?v=' in html
    assert Path("app/static/share-intake.css").exists()
