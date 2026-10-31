"""Browse shelves: public pages, live charts, covers from the facts cache, and one-tap adds."""
import asyncio
import json
import time
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

import pytest

from app import browse, models, title_pages
from app.browse_catalog import CATALOG, entries, find


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.scripts = []
        self.text = []
        self._in_ld = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elements.append((tag, attrs))
        self._in_ld = tag == "script" and attrs.get("type") == "application/ld+json"

    def handle_data(self, data):
        if self._in_ld:
            self.scripts.append(data)
        else:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_ld = False


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def offline_charts(monkeypatch):
    """Charts never reach real sources from the test suite, and each test starts with an empty cache."""
    async def offline(client):
        raise browse.SourceUnavailable("network disabled in tests")

    for kind in browse.KINDS:
        monkeypatch.setitem(browse.PROVIDERS, kind, offline)
    monkeypatch.setattr(browse, "CACHE", browse.ChartCache(None))
    monkeypatch.setattr(browse, "COVER_WARM_SPACING", 0)


def user_by_name(db, name="testuser"):
    return db.query(models.User).filter(models.User.username == name).first()


# ---------------------------------------------------------------------------
# The catalog itself


def test_every_shelf_entry_is_complete_and_keys_are_unique():
    seen = set()
    for kind, page in CATALOG.items():
        for item in entries(kind):
            assert item["key"] not in seen, item["key"]
            seen.add(item["key"])
            assert item["title"] and item["creator"] and item["year"] and item["genre"]
            assert len(item["why"].split()) >= 25, item["key"]
            assert len(item["fit"].split()) >= 5, item["key"]
            assert item["key"] == item["key"].lower() and " " not in item["key"]
        assert len(page["shelves"]) >= 4
        assert browse.word_count(kind) >= 1500
    assert find("manga", "death-note")["extra"]["volumes"] == 12
    assert find("audiobooks", "project-hail-mary")["extra"]["narrator"] == "Ray Porter"
    assert find("podcasts", "no-such-show") is None


# ---------------------------------------------------------------------------
# Public pages


def test_hub_links_every_shelf_page(client):
    response = client.get("/browse")
    assert response.status_code == 200
    for kind, page in CATALOG.items():
        assert f'href="/browse/{kind}"' in response.text
        assert page["heading"] in response.text
    assert "/static/ad-loader.js" not in response.text
    assert 'href="/browse" aria-current="page"' in response.text


@pytest.mark.parametrize("kind", list(CATALOG))
def test_shelf_page_reads_in_full_without_scripts_or_an_account(client, kind):
    response = client.get(f"/browse/{kind}")
    assert response.status_code == 200
    assert "noindex" not in response.text.split("</head>")[0]
    assert response.headers.get("X-Robots-Tag") is None
    page = Elements(response.text)
    cards = [attrs for tag, attrs in page.elements if tag == "article" and "data-browse-item" in attrs]
    assert len(cards) == len(entries(kind))
    assert all("hidden" not in card for card in cards)
    # Guests get the save-before-sign-up button; nothing on the page is a member action.
    guest = [attrs for tag, attrs in page.elements if "data-guest-save" in attrs]
    assert len(guest) == len(entries(kind))
    assert all(attrs["data-guest-kind"] == browse.KINDS[kind]["title_kind"] for attrs in guest)
    assert not any("data-browse-add" in attrs for _, attrs in page.elements)
    assert any(attrs.get("src", "").startswith("/static/guest-list.js") for tag, attrs in page.elements if tag == "script")
    # Written text, and not just the names: more than the thin-page bar for the whole page.
    assert len(" ".join(page.text).split()) >= 1500
    for item in entries(kind):
        assert item["why"] in response.text.replace("&#x27;", "'").replace("&amp;", "&")
    # Search filter stays hidden until the script can drive it.
    search = next(attrs for tag, attrs in page.elements if attrs.get("class") == "browse-filter")
    assert "hidden" in search
    # With no chart yet, the section says so instead of showing an empty list.
    assert "The chart is being fetched" in response.text or "did not answer" in response.text
    assert '<ol class="browse-chart__list">' not in response.text
    # Structured data names every pick.
    collection = next(json.loads(script) for script in page.scripts if '"CollectionPage"' in script)
    assert collection["mainEntity"]["numberOfItems"] == len(entries(kind))
    assert collection["mainEntity"]["itemListElement"][0]["name"] == entries(kind)[0]["title"]
    assert "/static/ad-loader.js" not in response.text


def test_unknown_kind_is_a_404(client):
    assert client.get("/browse/movies").status_code == 404
    assert client.get("/api/browse/movies/mine").status_code in (401, 404)


def test_shelves_are_in_the_sitemap_and_linked_from_the_guides(client):
    sitemap = client.get("/sitemap.xml").text
    assert "https://omnitrackr.xyz/browse</loc>" in sitemap
    for kind in CATALOG:
        assert f"https://omnitrackr.xyz/browse/{kind}</loc>" in sitemap
    assert 'href="/browse/manga"' in client.get("/manga-tracker").text
    assert 'href="/browse/podcasts"' in client.get("/podcast-tracker").text
    assert 'href="/browse/audiobooks"' in client.get("/audiobook-tracker").text
    assert 'href="/browse/manga"' in client.get("/titles").text
    assert 'href="/browse"' in client.get("/site-map").text


def test_dashboard_empty_shelves_point_at_the_browse_pages():
    core = Path("app/static/dashboard/core.js").read_text(encoding="utf-8")
    assert "library-empty__browse" in core
    for path in ("/browse/manga", "/browse/podcasts", "/browse/audiobooks"):
        assert path in core
    guest = Path("app/static/guest-list.js").read_text(encoding="utf-8")
    assert "'manga', 'podcast', 'audiobook'" in guest


def test_a_tracked_title_links_to_its_title_page(authenticated_client, db_session):
    user = user_by_name(db_session)
    db_session.add(models.Manga(user_id=user.id, title="Death Note", year=2003, author="Tsugumi Ohba"))
    db_session.commit()
    title_pages.SLUG_INDEX.clear()
    html = authenticated_client.get("/browse/manga").text
    assert 'href="/titles/manga/death-note-2003"' in html
    assert 'href="/titles/manga/monster-1994"' not in html


# ---------------------------------------------------------------------------
# Charts


JIKAN = {"data": [
    {"mal_id": 2, "url": "https://myanimelist.net/manga/2/Berserk", "title": "Berserk", "title_english": "Berserk", "type": "Manga",
     "volumes": None, "chapters": None, "status": "Publishing", "published": {"prop": {"from": {"year": 1989}}},
     "images": {"jpg": {"image_url": "https://cdn.myanimelist.net/images/manga/1/157897.jpg", "large_image_url": "https://cdn.myanimelist.net/images/manga/1/157897l.jpg"}},
     "authors": [{"name": "Miura, Kentarou"}], "genres": [{"name": "Action"}, {"name": "Adventure"}], "demographics": [{"name": "Seinen"}]},
    {"mal_id": 13, "url": "https://myanimelist.net/manga/13/One_Piece", "title": "One Piece", "type": "Manga",
     "published": {"prop": {"from": {"year": 1997}}}, "images": {"jpg": {"image_url": "http://cdn.myanimelist.net/x.jpg"}},
     "authors": [{"name": "Oda, Eiichiro"}], "genres": [{"name": "Adventure"}]},
    {"mal_id": 99, "title": "<script>alert(1)</script>", "url": "javascript:alert(1)", "images": {"jpg": {"image_url": "https://evil.example/x.jpg"}}},
    "not a dict",
]}

APPLE_PODCASTS = {"feed": {"results": [
    {"artistName": "The New York Times", "id": "1200361736", "name": "The Daily", "kind": "podcasts",
     "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/Podcasts221/v4/ab/64/66/x.jpg/100x100bb.png",
     "genres": [{"genreId": "1489", "name": "News"}, {"name": "Podcasts"}], "url": "https://podcasts.apple.com/us/podcast/the-daily/id1200361736"},
    {"artistName": "Nobody", "id": "abc", "name": "Bad id"},
]}}

APPLE_AUDIOBOOKS = {"feed": {"entry": [
    {"im:name": {"label": "Project Hail Mary (Unabridged)"}, "im:artist": {"label": "Andy Weir"},
     "im:image": [{"label": "https://is1-ssl.mzstatic.com/image/thumb/Music/a.jpg/55x55bb.png"}, {"label": "https://is1-ssl.mzstatic.com/image/thumb/Music/a.jpg/170x170bb.png"}],
     "link": [{"attributes": {"rel": "alternate", "type": "text/html", "href": "https://books.apple.com/us/audiobook/project-hail-mary/id1"}},
              {"attributes": {"rel": "enclosure", "href": "https://audio-ssl.itunes.apple.com/preview.m4a"}}],
     "id": {"label": "https://books.apple.com/us/audiobook/x/id1", "attributes": {"im:id": "1"}},
     "category": {"attributes": {"label": "Sci-Fi & Fantasy"}}, "im:releaseDate": {"label": "2021-05-04T00:00:00-07:00"}},
]}}


def test_chart_normalizers_keep_only_safe_fields():
    manga = browse.normalize_manga_chart(JIKAN)
    assert [item["id"] for item in manga] == ["mal-2", "mal-13", "mal-99"]
    assert manga[0]["creator"] == "Kentarou Miura" and manga[0]["year"] == 1989 and manga[0]["genre"] == "Action, Adventure, Seinen"
    assert manga[0]["image"] == "https://cdn.myanimelist.net/images/manga/1/157897l.jpg"
    assert manga[1]["image"] is None  # plain http
    assert manga[2]["image"] is None and manga[2]["url"] is None  # wrong host, javascript: link

    podcasts = browse.normalize_podcast_chart(APPLE_PODCASTS)
    assert len(podcasts) == 1
    assert podcasts[0]["id"] == "apple-1200361736" and podcasts[0]["creator"] == "The New York Times"
    assert podcasts[0]["genre"] == "News" and podcasts[0]["image"].endswith("/600x600bb.png")

    audiobooks = browse.normalize_audiobook_chart(APPLE_AUDIOBOOKS)
    assert audiobooks[0]["title"] == "Project Hail Mary" and audiobooks[0]["year"] == 2021
    assert audiobooks[0]["url"] == "https://books.apple.com/us/audiobook/project-hail-mary/id1"
    assert audiobooks[0]["image"].endswith("/600x600bb.png") and audiobooks[0]["genre"] == "Sci-Fi & Fantasy"


def test_chart_cache_serves_the_last_copy_while_a_source_is_down(monkeypatch):
    calls = []

    async def good(client):
        calls.append("good")
        return browse.normalize_manga_chart(JIKAN)

    async def down(client):
        calls.append("down")
        raise browse.SourceUnavailable("503")

    cache = browse.ChartCache(None)
    monkeypatch.setitem(browse.PROVIDERS, "manga", good)
    entry = run(cache.get(object(), "manga", wait=2))
    assert entry["error"] is None and [item["id"] for item in browse.chart_items(entry)] == ["mal-2", "mal-13", "mal-99"]
    # Stale: the old copy is returned at once and a refresh is started; a failure keeps the items.
    cache.entries["manga"]["fetched_at"] = time.time() - browse.FRESH_SECONDS - 1
    monkeypatch.setitem(browse.PROVIDERS, "manga", down)

    async def stale_then_failed():
        stale = await cache.get(object(), "manga", wait=2)
        assert stale["items"]
        await cache.tasks["manga"]
        return cache.peek("manga")

    after = run(stale_then_failed())
    assert after["error"] == "unavailable" and len(after["items"]) == 3
    assert calls == ["good", "down"]
    # A cold cache with a dead source renders nothing and does not hammer the source.
    cold = browse.ChartCache(None)
    assert run(cold.get(object(), "manga", wait=2))["items"] == []
    assert run(cold.get(object(), "manga", wait=2))["items"] == []
    assert calls == ["good", "down", "down"]
    assert cold.get is not None and run(cold.get(None, "manga")) is not None  # no client: whatever is cached, no fetch


def test_chart_is_rendered_with_add_buttons_once_cached(client, monkeypatch):
    browse.CACHE.entries["manga"] = {"items": browse.normalize_manga_chart(JIKAN), "fetched_at": time.time(), "error": None}
    html = client.get("/browse/manga").text
    assert '<ol class="browse-chart__list">' in html
    assert "Most popular on MyAnimeList" in html and "Berserk" in html
    assert 'href="https://myanimelist.net/manga/2/Berserk"' in html
    assert "javascript:" not in html and "<script>alert" not in html
    assert 'href="#popular"' in html
    page = Elements(html)
    guest = [attrs for tag, attrs in page.elements if "data-guest-save" in attrs]
    assert len(guest) == len(entries("manga")) + 3


# ---------------------------------------------------------------------------
# Covers from the shared facts cache


def test_covers_come_from_title_metadata_and_missing_ones_are_queued(db_session):
    items = entries("manga")[:3]
    key = browse.metadata_key("manga", items[0])
    db_session.add(models.TitleMetadata(key=key, status="ok", data=json.dumps({"poster": "https://cdn.myanimelist.net/a.jpg"}), fetched_at=datetime.utcnow()))
    stale_key = browse.metadata_key("manga", items[1])
    db_session.add(models.TitleMetadata(key=stale_key, status="miss", data=None, fetched_at=datetime.utcnow() - timedelta(days=4)))
    db_session.commit()
    covers, pending = browse.cached_covers(db_session, "manga", items)
    assert covers == {items[0]["key"]: "https://cdn.myanimelist.net/a.jpg"}
    assert [item["key"] for item in pending] == [items[1]["key"], items[2]["key"]]


def test_warming_looks_up_a_few_covers_through_get_or_fetch(monkeypatch):
    looked_up = []

    async def fake(db, client, category, normalized, display, year, creator=None, wait=8.0):
        looked_up.append((category, display, year, creator))
        return {"poster": "https://cdn.myanimelist.net/x.jpg"}

    monkeypatch.setattr(browse.title_metadata, "get_or_fetch", fake)
    monkeypatch.setattr(browse, "COVER_WARM_BATCH", 2)
    done = run(browse.warm_covers(object(), "manga", entries("manga")[:5]))
    assert done == 2
    assert looked_up[0] == ("manga", "Death Note", 2003, "Tsugumi Ohba, Takeshi Obata")
    looked_up.clear()
    run(browse.warm_covers(object(), "podcasts", entries("podcasts")[:1]))
    assert looked_up == [("podcast", "Serial", 2014, None)]


def test_shelf_page_shows_the_cover_it_has(client, db_session):
    item = find("podcasts", "radiolab")
    db_session.add(models.TitleMetadata(key=browse.metadata_key("podcasts", item), status="ok",
                                        data=json.dumps({"poster": "https://is1-ssl.mzstatic.com/radiolab/600x600bb.jpg"}), fetched_at=datetime.utcnow()))
    db_session.commit()
    html = client.get("/browse/podcasts").text
    assert 'src="https://is1-ssl.mzstatic.com/radiolab/600x600bb.jpg"' in html


# ---------------------------------------------------------------------------
# Members: one-tap add


def test_member_page_has_add_buttons_and_private_caching(authenticated_client):
    response = authenticated_client.get("/browse/audiobooks")
    assert response.headers["Cache-Control"] == "private, no-store"
    page = Elements(response.text)
    adds = [attrs for tag, attrs in page.elements if "data-browse-add" in attrs]
    assert len(adds) == len(entries("audiobooks"))
    assert not any("data-guest-save" in attrs for _, attrs in page.elements)
    assert not any(attrs.get("src", "").startswith("/static/guest-list.js") for tag, attrs in page.elements if tag == "script")
    assert 'href="/"' in response.text  # Open my library


def test_add_copies_public_details_only_and_never_duplicates(authenticated_client, db_session):
    user = user_by_name(db_session)
    first = authenticated_client.post("/api/browse/audiobooks/add", json={"key": "project-hail-mary"})
    assert first.status_code == 200, first.text
    assert first.json()["state"] == "created" and first.json()["category"] == "audiobooks"
    assert first.json()["url"] == "/titles/audiobook/project-hail-mary-2021"
    row = db_session.query(models.Audiobook).filter_by(user_id=user.id).one()
    assert (row.title, row.author, row.narrator, row.year, row.genre, row.length_hours) == ("Project Hail Mary", "Andy Weir", "Ray Porter", 2021, "Science fiction", 16.2)
    assert row.listened is False and row.rating is None and row.review is None
    again = authenticated_client.post("/api/browse/audiobooks/add", json={"key": "project-hail-mary"})
    assert again.json()["state"] == "existing"
    assert db_session.query(models.Audiobook).filter_by(user_id=user.id).count() == 1
    assert authenticated_client.get("/api/browse/audiobooks/mine").json()["keys"] == ["project-hail-mary"]

    manga = authenticated_client.post("/api/browse/manga/add", json={"key": "death-note"}).json()
    assert manga["state"] == "created"
    manga_row = db_session.query(models.Manga).filter_by(user_id=user.id).one()
    assert (manga_row.author, manga_row.volumes, manga_row.chapters, manga_row.read) == ("Tsugumi Ohba, Takeshi Obata", 12, 108, False)

    podcast = authenticated_client.post("/api/browse/podcasts/add", json={"key": "radiolab"}).json()
    podcast_row = db_session.query(models.Podcast).filter_by(user_id=user.id).one()
    assert podcast["state"] == "created" and podcast_row.host == "Latif Nasser, Lulu Miller" and podcast_row.year == 2002


def test_add_uses_the_cover_the_facts_cache_found(authenticated_client, db_session):
    user = user_by_name(db_session)
    item = find("manga", "monster")
    db_session.add(models.TitleMetadata(key=browse.metadata_key("manga", item), status="ok",
                                        data=json.dumps({"poster": "https://cdn.myanimelist.net/monster.jpg"}), fetched_at=datetime.utcnow()))
    db_session.commit()
    assert authenticated_client.post("/api/browse/manga/add", json={"key": "monster"}).json()["state"] == "created"
    assert db_session.query(models.Manga).filter_by(user_id=user.id).one().cover_art_url == "https://cdn.myanimelist.net/monster.jpg"


def test_add_from_the_chart_and_unknown_keys(authenticated_client, db_session):
    user = user_by_name(db_session)
    assert authenticated_client.post("/api/browse/manga/add", json={"key": "mal-2"}).status_code == 404
    browse.CACHE.entries["manga"] = {"items": browse.normalize_manga_chart(JIKAN), "fetched_at": time.time(), "error": None}
    added = authenticated_client.post("/api/browse/manga/add", json={"key": "mal-2"}).json()
    assert added["state"] == "created" and added["title"] == "Berserk"
    row = db_session.query(models.Manga).filter_by(user_id=user.id).one()
    assert row.author == "Kentarou Miura" and row.cover_art_url == "https://cdn.myanimelist.net/images/manga/1/157897l.jpg" and row.year == 1989
    assert "mal-2" in authenticated_client.get("/api/browse/manga/mine").json()["keys"]
    assert authenticated_client.post("/api/browse/manga/add", json={"key": "Not A Key"}).status_code == 422
    assert authenticated_client.post("/api/browse/manga/add", json={"key": "nope-nope"}).status_code == 404


def test_existing_title_is_recognised_whatever_its_case(authenticated_client, db_session):
    user = user_by_name(db_session)
    db_session.add(models.Podcast(user_id=user.id, title="  RADIOLAB ", host="me", rating=9.0, listened=True))
    db_session.commit()
    assert authenticated_client.get("/api/browse/podcasts/mine").json()["keys"] == ["radiolab"]
    result = authenticated_client.post("/api/browse/podcasts/add", json={"key": "radiolab"}).json()
    assert result["state"] == "existing"
    row = db_session.query(models.Podcast).filter_by(user_id=user.id).one()
    assert row.rating == 9.0 and row.listened is True and row.host == "me"


def test_adds_need_an_account(client):
    assert client.post("/api/browse/manga/add", json={"key": "death-note"}).status_code == 401
    assert client.get("/api/browse/manga/mine").status_code == 401


# ---------------------------------------------------------------------------
# Guests: the saved-before-sign-up list moves shelf picks into a new library


def test_guest_list_import_finds_shelf_picks(authenticated_client, db_session):
    user = user_by_name(db_session)
    item = find("manga", "fullmetal-alchemist")
    payload = {"items": [{"kind": "manga", "slug": browse.guest_slug(item)}, {"kind": "podcast", "slug": "99-percent-invisible"},
                         {"kind": "audiobook", "slug": "not-on-any-shelf"}]}
    result = authenticated_client.post("/api/guest-list/import", json=payload).json()
    assert [entry["title"] for entry in result["added"]] == ["Fullmetal Alchemist", "99% Invisible"]
    assert result["missing"] == 1
    assert db_session.query(models.Manga).filter_by(user_id=user.id).one().volumes == 27
    assert db_session.query(models.Podcast).filter_by(user_id=user.id).one().host == "Roman Mars"
    assert browse.find("podcast", "99-percent-invisible")[1]["key"] == "99-percent-invisible"
    assert browse.find("movie", "death-note-2003") is None
