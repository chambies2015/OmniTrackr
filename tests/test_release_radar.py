"""Release Radar: normalization, caching, public pages, and safe library saves."""
import asyncio
import json
import re
import time
from datetime import date, datetime
from html.parser import HTMLParser

import pytest

from app import models
from app import release_radar as radar
from tests.release_radar_fixtures import FIXTURE_PROVIDERS, install_fixture_providers, load

TODAY = date(2026, 9, 27)


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.scripts = []
        self._in_ld = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elements.append((tag, attrs))
        self._in_ld = tag == "script" and attrs.get("type") == "application/ld+json"

    def handle_data(self, data):
        if self._in_ld:
            self.scripts.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_ld = False


@pytest.fixture
def fixture_radar(monkeypatch):
    return install_fixture_providers(today=TODAY, monkeypatch=monkeypatch)


def window(category, slug):
    found = radar.parse_window(category, slug, TODAY)
    assert found is not None
    return found


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def user_by_name(db_session, name="testuser"):
    return db_session.query(models.User).filter(models.User.username == name).first()


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------

class TestWindows:
    def test_month_and_season_windows(self):
        october = radar.month_window("movies", 2026, 10)
        assert (october.start, october.end, october.label) == (date(2026, 10, 1), date(2026, 11, 1), "October 2026")
        december = radar.month_window("games", 2026, 12)
        assert december.end == date(2027, 1, 1)
        fall = radar.season_window("fall", 2026)
        assert (fall.start, fall.end, fall.label) == (date(2026, 10, 1), date(2027, 1, 1), "Fall 2026")
        assert radar.season_for(date(2027, 2, 14)) == ("winter", 2027)

    def test_allowed_range_is_bounded(self):
        assert [w.slug for w in radar.allowed_windows("tv", TODAY)] == ["2026-08", "2026-09", "2026-10", "2026-11", "2026-12"]
        assert [w.slug for w in radar.allowed_windows("anime", TODAY)] == ["spring-2026", "summer-2026", "fall-2026", "winter-2027"]
        assert radar.parse_window("tv", "2027-06", TODAY) is None
        assert radar.parse_window("tv", "../../etc", TODAY) is None
        assert radar.parse_window("anime", "fall-2030", TODAY) is None

    def test_featured_window_moves_ahead_near_the_end_of_a_period(self):
        assert radar.featured_window("movies", date(2026, 9, 10)).slug == "2026-09"
        assert radar.featured_window("movies", TODAY).slug == "2026-10"
        assert radar.featured_window("anime", date(2026, 8, 1)).slug == "summer-2026"
        assert radar.featured_window("anime", TODAY).slug == "fall-2026"
        assert radar.featured_window("anime", date(2026, 12, 25)).slug == "winter-2027"


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

class TestNormalization:
    def test_anilist_keeps_safe_fields_and_marks_sequels(self):
        items = radar.normalize_anilist(load("release_radar_anilist.json"), window("anime", "fall-2026"))
        by_key = {i["key"]: i for i in items}
        assert "al-900002" not in by_key  # Music videos are not season shows.
        apothecary = by_key["al-195516"]
        assert apothecary["title"] == "The Apothecary Diaries Season 3"
        assert apothecary["alt_title"] == "Kusuriya no Hitorigoto 3rd Season"
        assert "Sequel" in apothecary["badges"] and apothecary["date"] == "2026-10-02"
        assert apothecary["image"].startswith("https://s4.anilist.co/")
        assert apothecary["save"] == {"title": "The Apothecary Diaries Season 3", "year": 2026, "episodes": None,
                                      "poster_url": apothecary["image"]}
        original = by_key["al-900001"]
        assert "New" in original["badges"] and "Original story" in original["details"]
        assert "Made by OLM" in original["details"]
        hostile = by_key["al-900003"]
        assert hostile["image"] is None and hostile["source_url"] is None and hostile["date"] is None
        # Date-less entries sort last.
        assert items[-1]["key"] == "al-900003"

    def test_tvmaze_keeps_only_premieres_worth_listing(self):
        items = radar.normalize_tvmaze(load("release_radar_tvmaze.json"), window("tv", "2026-10"))
        titles = {i["title"] for i in items}
        assert {"War", "East of Eden", "Ask This Old House", "Fixture Returning Drama", "Fixture Animated Series"} <= titles
        assert "Not A Premiere Episode" not in titles  # episode 2
        assert "Late Night Fixture" not in titles  # talk show
        assert "Obscure Fixture" not in titles  # low weight
        assert "Outside The Window" not in titles  # November
        war = next(i for i in items if i["title"] == "War")
        assert war["badges"] == ["New series"] and war["date_note"] == "Series premiere"
        assert war["details"] == ["Airs on HBO"]
        returning = next(i for i in items if i["title"] == "Fixture Returning Drama")
        assert returning["badges"] == ["Season 3"] and returning["save"]["year"] == 2022
        korean = next(i for i in items if i["title"] == "Your Personal Taxi")
        assert "Korean language" in korean["details"] and "Streaming on Netflix" in korean["details"]

    def test_wikidata_prefers_us_dates_and_skips_foreign_premieres(self):
        data = load("release_radar_wikidata.json")
        items = radar.normalize_wikidata(data["candidates"], data["details"], window("movies", "2026-10"))
        by_title = {i["title"]: i for i in items}
        assert "Hope" not in by_title  # only a German date in the window
        assert "Early Festival Film" not in by_title
        assert not any(re.fullmatch(r"Q\d+", t) for t in by_title)
        digger = by_title["Digger"]
        assert digger["date"] == "2026-10-02" and digger["date_note"] == "US release"
        assert digger["genres"] == ["Drama", "Comedy"]
        assert digger["details"] == ["Directed by Alejandro González Iñárritu"]
        assert digger["save"]["director"] == "Alejandro González Iñárritu" and digger["save"]["imdb"] == "tt31450459"
        assert by_title["Whalefall"]["date_note"] == "Release"

    def test_rawg_validates_slugs_and_window(self):
        items = radar.normalize_rawg(load("release_radar_rawg.json")["results"], window("games", "2026-10"))
        keys = [i["key"] for i in items]
        assert "rawg-fixture-next-month" not in keys
        assert not any("Bad" in i["title"] for i in items)
        starfall = next(i for i in items if i["key"] == "rawg-fixture-starfall")
        assert starfall["platforms"] == ["PC", "PlayStation 5", "Xbox Series S/X"]
        assert starfall["save"]["genres"] == "Action, RPG"
        assert starfall["save"]["rawg_link"] == "https://rawg.io/games/fixture-starfall"

    def test_notes_are_calculated_from_the_list(self):
        w = window("tv", "2026-10")
        items = radar.normalize_tvmaze(load("release_radar_tvmaze.json"), w)
        notes = radar.radar_notes("tv", items, w)
        new = sum("New series" in i["badges"] for i in items)
        assert notes[0].startswith(f"{new} brand-new series and {len(items) - new} returning show")
        assert any("Thursday, October 1" in note for note in notes)
        assert radar.radar_notes("tv", [], w) == []

    def test_clean_text_strips_control_characters(self):
        assert radar._clean_text("a\u0000b\n  c") == "ab c"
        assert radar._safe_image("https://media.rawg.io/x.jpg\" onerror=1") is None
        assert radar._safe_image("http://media.rawg.io/x.jpg") is None


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

class TestCache:
    def test_serves_stale_copy_when_refresh_fails(self, monkeypatch):
        cache = radar.RadarCache(None)
        w = window("games", "2026-10")
        calls = {"n": 0}

        async def flaky(client, window):
            calls["n"] += 1
            if calls["n"] > 1:
                raise RuntimeError("down")
            return [radar.make_item(category="games", key="rawg-a", title="A", release_date="2026-10-02", source_url=None)]

        monkeypatch.setitem(radar.PROVIDERS, "games", flaky)

        async def scenario():
            first = await cache.get(None, w)
            assert first["items"][0]["title"] == "A" and first["items"][0]["window"] == "2026-10"
            cache.entries[w.cache_key]["fetched_at"] -= radar.FRESH_SECONDS + 1
            stale = await cache.get(None, w)  # returns immediately, refresh in background
            assert stale["items"][0]["title"] == "A"
            await asyncio.sleep(0.01)
            after = cache.peek(w)
            assert after["items"][0]["title"] == "A" and after["error"] == "error"

        run(scenario())
        assert calls["n"] == 2

    def test_cold_failure_and_unavailable_provider(self, monkeypatch):
        cache = radar.RadarCache(None)
        monkeypatch.delenv("RAWG_API_KEY", raising=False)
        monkeypatch.setitem(radar.PROVIDERS, "games", radar.fetch_games)
        entry = run(cache.get(None, window("games", "2026-10")))
        assert entry["items"] == [] and entry["error"] == "unavailable"

    def test_slow_cold_fetch_returns_none_without_blocking(self, monkeypatch):
        cache = radar.RadarCache(None)

        async def slow(client, window):
            await asyncio.sleep(5)
            return []

        monkeypatch.setitem(radar.PROVIDERS, "movies", slow)
        started = time.time()
        assert run(cache.get(None, window("movies", "2026-10"), wait=0.05)) is None
        assert time.time() - started < 2

    def test_disk_cache_round_trip(self, tmp_path, monkeypatch):
        w = window("anime", "fall-2026")
        monkeypatch.setitem(radar.PROVIDERS, "anime", FIXTURE_PROVIDERS["anime"])
        first = radar.RadarCache(tmp_path)
        run(first.get(None, w))
        saved = list(tmp_path.glob("*.json"))
        assert len(saved) == 1 and saved[0].name == "anime_fall-2026.json"

        async def never(client, window):
            raise AssertionError("should use disk copy")

        monkeypatch.setitem(radar.PROVIDERS, "anime", never)
        second = radar.RadarCache(tmp_path)
        entry = run(second.get(None, w))
        assert any(i["key"] == "al-195516" for i in entry["items"])

    def test_corrupt_disk_cache_is_ignored(self, tmp_path):
        w = window("tv", "2026-10")
        (tmp_path / "tv_2026-10.json").write_text("{not json", encoding="utf-8")
        assert radar.RadarCache(tmp_path).peek(w) is None


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------

class TestPages:
    def test_hub_is_complete_indexable_and_escaped(self, client, fixture_radar):
        response = client.get("/release-radar")
        assert response.status_code == 200
        html = response.text
        assert '<meta name="robots" content="index, follow, max-image-preview:large">' in html
        assert "Out in the next two weeks" in html
        for label in ("Movies", "TV premieres", "Anime", "Video games"):
            assert label in html
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
        # Indexed (overview with its own guide text) but never monetized: release lists
        # are mostly third-party data (AdSense "low value content", Oct 2026).
        assert "/static/ad-loader.js" not in html
        assert "evil.example" not in html and "javascript:" not in html
        parsed = Elements(html)
        data = json.loads(parsed.scripts[0])
        assert data["@graph"][1]["@type"] == "ItemList" and data["@graph"][1]["itemListElement"]
        # Guests get plain sign-in links that return to this page.
        tracks = [a for tag, a in parsed.elements if tag == "a" and "data-radar-add" in a]
        assert tracks and all(a["href"] == "/?next=/release-radar#landing-auth" for a in tracks)
        assert response.headers["content-security-policy"]

    def test_category_pages_render_each_source(self, client, fixture_radar):
        expectations = {
            "movies": ("New movie releases in October 2026", "Digger"),
            "tv": ("TV premieres and new seasons in October 2026", "East of Eden"),
            "anime": ("Fall 2026 anime season: every new show", "Cyberpunk: Edgerunners 2"),
            "games": ("Video game releases in October 2026", "Fixture: Starfall Odyssey"),
        }
        for category, (heading, title) in expectations.items():
            response = client.get(f"/release-radar/{category}")
            assert response.status_code == 200, category
            assert heading in response.text and title in response.text
            assert f'<link rel="canonical" href="https://omnitrackr.xyz/release-radar/{category}">' in response.text
            assert "Radar notes" in response.text
            cards = [a for tag, a in Elements(response.text).elements if tag == "article" and "data-key" in a]
            assert cards and all(card["data-window"] for card in cards)

    def test_small_lists_are_not_indexed_or_monetized(self, client, fixture_radar):
        response = client.get("/release-radar/movies")  # 5 fixture films
        assert '<meta name="robots" content="noindex, follow">' in response.text
        assert response.headers["x-robots-tag"] == "noindex, follow"
        assert "/static/ad-loader.js" not in response.text

    def test_window_pages_and_navigation(self, client, fixture_radar):
        response = client.get("/release-radar/tv/2026-11")
        assert response.status_code == 200
        assert "October 2026" in response.text and "December 2026" in response.text
        assert '<link rel="canonical" href="https://omnitrackr.xyz/release-radar/tv/2026-11">' in response.text
        # November has no fixture premieres in window except one; keep it out of the index.
        assert "noindex" in response.text
        assert client.get("/release-radar/tv/2031-01").status_code == 404
        assert client.get("/release-radar/podcasts").status_code == 404
        assert client.get("/release-radar/anime/winter-2027").status_code == 200

    def test_jump_only_redirects_to_radar_paths(self, client, fixture_radar):
        ok = client.get("/release-radar/jump?to=/release-radar/games/2026-11", follow_redirects=False)
        assert ok.status_code == 303 and ok.headers["location"] == "/release-radar/games/2026-11"
        for hostile in ("https://evil.example", "//evil.example", "/release-radar/games/2099-01", "/admin"):
            response = client.get("/release-radar/jump", params={"to": hostile}, follow_redirects=False)
            assert response.headers["location"] in ("/release-radar", "/release-radar/games")

    def test_warming_state_is_noindex_and_refreshes(self, client, monkeypatch):
        cache = radar.RadarCache(None)
        monkeypatch.setattr(radar, "CACHE", cache)
        monkeypatch.setattr(radar, "today_utc", lambda: TODAY)
        monkeypatch.setattr(radar, "FIRST_LOAD_WAIT_SECONDS", 0.01)

        async def slow(client, window):
            await asyncio.sleep(3)
            return []

        monkeypatch.setitem(radar.PROVIDERS, "tv", slow)
        response = client.get("/release-radar/tv")
        assert response.status_code == 200
        assert "Gathering tv premieres right now" in response.text
        assert '<meta http-equiv="refresh" content="45">' in response.text
        assert "noindex" in response.headers["x-robots-tag"]

    def test_provider_error_message(self, client, monkeypatch):
        monkeypatch.setattr(radar, "CACHE", radar.RadarCache(None))
        monkeypatch.setattr(radar, "today_utc", lambda: TODAY)

        async def broken(client, window):
            raise RuntimeError("boom")

        monkeypatch.setitem(radar.PROVIDERS, "anime", broken)
        response = client.get("/release-radar/anime")
        assert response.status_code == 200
        assert "We could not reach the AniList schedule" in response.text
        assert "boom" not in response.text

    def test_community_counts_show_aggregates_only(self, client, db_session, fixture_radar, authenticated_client):
        user = user_by_name(db_session)
        db_session.add(models.TVShow(user_id=user.id, title="  war ", year=2026, watched=True, rating=9))
        inactive = models.User(username="gone", email="gone@example.com", hashed_password="x", is_active=False)
        db_session.add(inactive)
        db_session.flush()
        db_session.add(models.TVShow(user_id=inactive.id, title="East of Eden", year=2026))
        db_session.commit()
        client.headers = {}
        html = client.get("/release-radar/tv").text
        war = html[html.index('id="item-tvm-86587-s1"'):]
        assert "In 1 OmniTrackr library" in war[: war.index("</article>")]
        eden = html[html.index('id="item-tvm-90001-s1"'):]
        assert "OmniTrackr library" not in eden[: eden.index("</article>")]
        assert "testuser" not in html
        assert "Already on OmniTrackr shelves" in client.get("/release-radar").text

    def test_navigation_links_to_the_radar(self, client):
        for path in ("/", "/discover", "/reviews", "/guides", "/about"):
            assert 'href="/release-radar"' in client.get(path).text, path


# ---------------------------------------------------------------------------
# Library integration (no schema changes; existing records are never altered)
# ---------------------------------------------------------------------------

class TestTracking:
    def prime(self, client, path="/release-radar/tv"):
        assert client.get(path).status_code == 200

    def test_status_requires_sign_in(self, client, fixture_radar):
        self.prime(client)
        assert client.get("/api/release-radar/tv/2026-10/library").status_code == 401
        assert client.post("/api/release-radar/save", json={"category": "tv", "window": "2026-10", "key": "tvm-86587-s1"}).status_code == 401

    def test_save_creates_unfinished_entry_and_private_collection(self, authenticated_client, db_session, fixture_radar):
        client = authenticated_client
        self.prime(client)
        response = client.post("/api/release-radar/save", json={"category": "tv", "window": "2026-10", "key": "tvm-86587-s1"})
        assert response.status_code == 200
        body = response.json()
        assert body["state"] == "created" and body["title"] == "War"
        assert response.headers["cache-control"] == "private, no-store"
        user = user_by_name(db_session)
        show = db_session.query(models.TVShow).filter_by(user_id=user.id, title="War").one()
        assert show.watched is False and show.rating is None and show.review is None and show.review_public is False
        assert show.year == 2026 and show.poster_url.startswith("https://static.tvmaze.com/")
        collection = db_session.get(models.Collection, body["collection_id"])
        assert collection.name == "Release Radar" and collection.is_public is False
        items = db_session.query(models.CollectionItem).filter_by(collection_id=collection.id).all()
        assert [(i.category, i.item_id) for i in items] == [("tv-shows", show.id)]

        status = client.get("/api/release-radar/tv/2026-10/library").json()
        assert status == {"keys": ["tvm-86587-s1"]}

    def test_repeat_save_is_idempotent(self, authenticated_client, db_session, fixture_radar):
        client = authenticated_client
        self.prime(client, "/release-radar/games")
        payload = {"category": "games", "window": "2026-10", "key": "rawg-fixture-starfall"}
        first = client.post("/api/release-radar/save", json=payload).json()
        second = client.post("/api/release-radar/save", json=payload).json()
        assert first["state"] == "created" and second["state"] == "existing"
        assert first["collection_id"] == second["collection_id"]
        user = user_by_name(db_session)
        games = db_session.query(models.VideoGame).filter_by(user_id=user.id).all()
        assert len(games) == 1
        game = games[0]
        assert game.release_date == datetime(2026, 10, 6) and game.genres == "Action, RPG" and game.played is False
        assert game.rawg_link == "https://rawg.io/games/fixture-starfall"
        assert db_session.query(models.CollectionItem).count() == 1

    def test_existing_entries_are_reused_not_modified(self, authenticated_client, db_session, fixture_radar):
        client = authenticated_client
        user = user_by_name(db_session)
        mine = models.Anime(user_id=user.id, title="the apothecary diaries season 3", year=2026, watched=True,
                            rating=9.5, review="Loved it", review_public=True, episodes=24)
        db_session.add(mine)
        db_session.commit()
        self.prime(client, "/release-radar/anime")
        body = client.post("/api/release-radar/save", json={"category": "anime", "window": "fall-2026", "key": "al-195516"}).json()
        assert body["state"] == "existing"
        db_session.refresh(mine)
        assert (mine.title, mine.watched, mine.rating, mine.review, mine.review_public, mine.episodes) == (
            "the apothecary diaries season 3", True, 9.5, "Loved it", True, 24)
        assert db_session.query(models.Anime).filter_by(user_id=user.id).count() == 1

    def test_movie_save_uses_wikidata_fields(self, authenticated_client, db_session, fixture_radar):
        client = authenticated_client
        self.prime(client, "/release-radar/movies")
        body = client.post("/api/release-radar/save", json={"category": "movies", "window": "2026-10", "key": "wd-Q1001"}).json()
        assert body["state"] == "created"
        movie = db_session.query(models.Movie).filter_by(title="Digger").one()
        assert movie.director == "Alejandro González Iñárritu" and movie.year == 2026 and movie.watched is False

    def test_existing_collection_is_reused_and_other_users_untouched(self, authenticated_client, db_session, fixture_radar):
        client = authenticated_client
        user = user_by_name(db_session)
        other = models.User(username="other", email="other@example.com", hashed_password="x", is_active=True)
        db_session.add(other)
        db_session.flush()
        db_session.add(models.TVShow(user_id=other.id, title="War", year=2026, watched=True))
        existing = models.Collection(user_id=user.id, name="Release Radar", description="Mine")
        db_session.add(existing)
        db_session.commit()
        self.prime(client)
        for key in ("tvm-86587-s1", "tvm-90001-s1"):
            body = client.post("/api/release-radar/save", json={"category": "tv", "window": "2026-10", "key": key}).json()
            assert body["collection_id"] == existing.id
        positions = [i.position for i in db_session.query(models.CollectionItem).filter_by(collection_id=existing.id).order_by(models.CollectionItem.position)]
        assert positions == [0, 1]
        assert db_session.get(models.Collection, existing.id).description == "Mine"
        assert db_session.query(models.TVShow).filter_by(user_id=other.id).count() == 1
        assert db_session.query(models.Collection).filter_by(user_id=other.id).count() == 0

    @pytest.mark.parametrize("payload, status", [
        ({"category": "tv", "window": "2026-10", "key": "tvm-does-not-exist"}, 404),
        ({"category": "tv", "window": "2031-01", "key": "tvm-86587-s1"}, 404),
        ({"category": "books", "window": "2026-10", "key": "x"}, 404),
        ({"category": "games", "window": "2026-10", "key": "tvm-86587-s1"}, 404),
        ({"category": "tv", "window": "2026-10", "key": ""}, 422),
        ({"category": "tv", "window": "2026-10", "key": "x" * 81}, 422),
    ])
    def test_rejects_unknown_or_forged_items(self, authenticated_client, db_session, fixture_radar, payload, status):
        self.prime(authenticated_client)
        assert authenticated_client.post("/api/release-radar/save", json=payload).status_code == status
        assert db_session.query(models.TVShow).count() == 0

    def test_save_before_list_is_cached_asks_for_reload(self, authenticated_client, fixture_radar):
        response = authenticated_client.post("/api/release-radar/save", json={"category": "tv", "window": "2026-10", "key": "tvm-86587-s1"})
        assert response.status_code == 404
        assert "Reload the page" in response.json()["detail"]


# ---------------------------------------------------------------------------
# SEO and assets
# ---------------------------------------------------------------------------

def test_sitemap_lists_only_indexable_radar_pages(client, fixture_radar):
    cold = client.get("/sitemap.xml").text
    assert "/release-radar" not in cold  # nothing cached yet; the crawl warms it
    for path in ("/release-radar", "/release-radar/tv", "/release-radar/anime", "/release-radar/tv/2026-11"):
        client.get(path)
    body = client.get("/sitemap.xml").text
    listed = re.findall(r"<loc>https://omnitrackr.xyz(/release-radar[^<]*)</loc>", body)
    assert listed == ["/release-radar"]  # fixture sections are below the indexable size
    for path in listed:
        response = client.get(path)
        assert "noindex" not in response.text and "noindex" not in response.headers.get("x-robots-tag", "")


def _plenty_of_tv(monkeypatch):
    install_fixture_providers(today=TODAY, monkeypatch=monkeypatch)
    many = [radar.make_item(category="tv", key=f"tvm-{n}-s1", title=f"Show {n}", release_date="2026-10-0%d" % (n % 9 + 1),
                            source_url=None, popularity=90 - n) for n in range(14)]

    async def plenty(client, window):
        return list(many) if window.slug == "2026-10" else []

    monkeypatch.setitem(radar.PROVIDERS, "tv", plenty)


def test_large_category_pages_stay_out_of_index_and_ads(client, monkeypatch):
    _plenty_of_tv(monkeypatch)
    page = client.get("/release-radar/tv")
    assert '<meta name="robots" content="noindex, follow">' in page.text
    assert page.headers["x-robots-tag"] == "noindex, follow"
    assert "/static/ad-loader.js" not in page.text
    body = client.get("/sitemap.xml").text
    assert "/release-radar/tv</loc>" not in body
    assert "https://omnitrackr.xyz/release-radar</loc>" in body


def test_category_indexing_switch_still_works(client, monkeypatch):
    _plenty_of_tv(monkeypatch)
    monkeypatch.setattr(radar, "INDEX_CATEGORY_PAGES", True)
    monkeypatch.setattr(radar, "RADAR_ADS", True)
    page = client.get("/release-radar/tv")
    assert '<meta name="robots" content="index, follow, max-image-preview:large">' in page.text
    assert "/static/ad-loader.js" in page.text  # 14 items: above the ad threshold
    assert "https://omnitrackr.xyz/release-radar/tv</loc>" in client.get("/sitemap.xml").text


def test_llms_txt_describes_radar(client):
    assert "/release-radar" in client.get("/llms.txt").text


def test_radar_assets_are_served(client):
    for path, kind in (("/static/release-radar.js", "javascript"), ("/static/release-radar.css", "css")):
        response = client.get(path)
        assert response.status_code == 200 and kind in response.headers["content-type"]


# ---------------------------------------------------------------------------
# Provider HTTP contracts (mocked transport; the suite never uses the network)
# ---------------------------------------------------------------------------

class TestProviderRequests:
    def client(self, handler):
        import httpx
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    def test_wikidata_two_step_query_with_user_agent(self):
        import httpx
        data = load("release_radar_wikidata.json")
        seen = []

        def handler(request):
            seen.append(request)
            query = request.url.params["query"]
            rows = data["details"] if "VALUES ?film" in query else data["candidates"]
            return httpx.Response(200, json={"results": {"bindings": rows}})

        items = run(radar.fetch_movies(self.client(handler), window("movies", "2026-10")))
        assert [r.url.host for r in seen] == ["query.wikidata.org", "query.wikidata.org"]
        assert all("OmniTrackr" in r.headers["user-agent"] for r in seen)
        assert '"2026-10-01T00:00:00Z"' in seen[0].url.params["query"]
        assert "wd:Q1001" in seen[1].url.params["query"]
        assert {i["title"] for i in items} >= {"Digger", "Verity"}

    def test_wikidata_errors_propagate(self):
        import httpx
        with pytest.raises(httpx.HTTPStatusError):
            run(radar.fetch_movies(self.client(lambda r: httpx.Response(503)), window("movies", "2026-10")))

    def test_tvmaze_requests_every_day_and_retries_rate_limits(self, monkeypatch):
        import httpx
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(radar.asyncio, "sleep", fake_sleep)
        fixture = load("release_radar_tvmaze.json")
        calls = []

        def handler(request):
            calls.append((request.url.path, request.url.params.get("date"), request.url.params.get("country")))
            if request.url.params.get("date") == "2026-10-02" and len([c for c in calls if c[1] == "2026-10-02"]) == 1:
                return httpx.Response(429)
            day = request.url.params.get("date")
            return httpx.Response(200, json=[e for e in fixture if e["airdate"] == day])

        items = run(radar.fetch_tv(self.client(handler), window("tv", "2026-10")))
        days = {c[1] for c in calls}
        assert len(days) == 31 and ("/schedule", "2026-10-01", "US") in calls and ("/schedule/web", "2026-10-01", None) in calls
        assert 2.5 in sleeps  # backed off after the 429
        assert any(i["title"] == "War" for i in items)

    def test_tvmaze_mostly_failing_raises(self, monkeypatch):
        import httpx

        async def fake_sleep(seconds):
            return None

        monkeypatch.setattr(radar.asyncio, "sleep", fake_sleep)
        with pytest.raises(httpx.HTTPStatusError):
            run(radar.fetch_tv(self.client(lambda r: httpx.Response(500)), window("tv", "2026-10")))

    def test_anilist_graphql_paginates(self, monkeypatch):
        import httpx

        async def fake_sleep(seconds):
            return None

        monkeypatch.setattr(radar.asyncio, "sleep", fake_sleep)
        media = load("release_radar_anilist.json")
        bodies = []

        def handler(request):
            body = json.loads(request.content)
            bodies.append(body)
            page = body["variables"]["page"]
            chunk = media[:4] if page == 1 else media[4:]
            return httpx.Response(200, json={"data": {"Page": {"pageInfo": {"hasNextPage": page == 1}, "media": chunk}}})

        items = run(radar.fetch_anime(self.client(handler), window("anime", "winter-2027")))
        assert [b["variables"] for b in bodies] == [
            {"season": "WINTER", "year": 2027, "page": 1}, {"season": "WINTER", "year": 2027, "page": 2}]
        assert "isAdult: false" in bodies[0]["query"]
        assert len(items) == 6

    def test_rawg_uses_key_dates_and_pages(self, monkeypatch):
        import httpx
        monkeypatch.setenv("RAWG_API_KEY", "k123")
        results = load("release_radar_rawg.json")["results"]
        seen = []

        def handler(request):
            seen.append(dict(request.url.params))
            page = int(request.url.params["page"])
            return httpx.Response(200, json={"results": results[:3] if page == 1 else results[3:],
                                             "next": "more" if page == 1 else None})

        items = run(radar.fetch_games(self.client(handler), window("games", "2026-10")))
        assert seen[0]["key"] == "k123" and seen[0]["dates"] == "2026-10-01,2026-10-31" and seen[0]["ordering"] == "-added"
        assert [s["page"] for s in seen] == ["1", "2"]
        assert len(items) == 5
