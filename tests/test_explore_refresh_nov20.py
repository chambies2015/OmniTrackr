"""Discover, trending and the browse shelves after the Nov 20 2026 refresh: covers, format colours, guest saving."""
import re
from datetime import datetime, timedelta
from html import unescape

from app import explore_art, models, title_metadata, title_pages
from app.browse_catalog import CATALOG
from app.discover_catalog import TRAILS, published_editions


def _member(db, name):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True, is_active=True)
    db.add(user)
    db.flush()
    return user


def _cache_poster(db, kind, title, year, url):
    title_metadata.store(db, title_metadata.cache_key(kind, title_pages.normalize(title), year), {"poster": url}, "ok")
    db.commit()


def test_cover_draws_the_title_when_there_is_no_art_and_keeps_it_under_real_art():
    drawn = explore_art.cover("Kiki's Delivery Service", "anime")
    assert 'class="x-art"' in drawn and 'data-kind="anime"' in drawn and 'aria-hidden="true"' in drawn
    assert "Kiki&#x27;s Delivery Service" in drawn and "<img" not in drawn
    hue = explore_art.hue("Kiki's Delivery Service")
    assert f"--cover-hue:{hue}" in drawn
    art = explore_art.cover("Monster", "manga", "https://cdn.myanimelist.net/images/manga/3/258224l.jpg", width=56)
    # The drawn cover stays underneath, so a slow or broken image still shows something.
    assert art.index('class="x-cover"') < art.index("<img")
    assert 'width="56" height="84"' in art and 'loading="lazy"' in art
    square = explore_art.cover("Serial", "podcast", "https://example.com/a.jpg", square=True, width=40)
    assert "x-art--square" in square and 'width="40" height="40"' in square
    assert 'x-cover__kind' not in explore_art.cover("Akira", "manga", label=False)
    assert 'loading="lazy"' not in explore_art.cover("Akira", "manga", "https://example.com/a.jpg", eager=True)


def test_cached_posters_reads_only_good_rows(db_session):
    _cache_poster(db_session, "movie", "Knives Out", 2019, "https://example.com/knives.jpg")
    title_metadata.store(db_session, title_metadata.cache_key("game", "outer wilds", 2019), {"poster": "https://example.com/o.jpg"}, "miss")
    db_session.commit()
    found = explore_art.cached_posters(db_session, [("movie", "Knives Out", 2019), ("game", "Outer Wilds", 2019), ("book", "Piranesi", 2020)])
    assert found == {("movie", "Knives Out", 2019): "https://example.com/knives.jpg"}
    assert explore_art.cached_posters(db_session, []) == {}


def test_discover_hub_shows_covers_format_chips_and_every_trail(client, db_session):
    _cache_poster(db_session, "movie", "Knives Out", 2019, "https://example.com/knives.jpg")
    html = client.get("/discover").text
    assert 'class="dark-mode discover-page site explore discover-hub"' in html
    assert f'/static/explore.css?v={explore_art.CSS_VERSION}' in html
    assert 'src="https://example.com/knives.jpg"' in html
    # Each trail opens with its four covers and lists its picks with their format colour.
    for slug, trail in TRAILS.items():
        card = re.search(rf'<article class="trail"[^>]*>.*?href="/discover/{slug}" tabindex="-1" aria-hidden="true">(.*?)</a>', html, re.S)
        assert card and card.group(1).count('class="x-art') == len(trail["items"])
    assert html.count('<button type="button" class="dx-chip"') == 1 + len({i["category"] for t in TRAILS.values() for i in t["items"]})
    assert 'data-format="" aria-pressed="true">Any format</button>' in html
    # The current edition's picks link into the edition.
    slug, edition = next(reversed(published_editions().items()))
    assert html.count(f'href="/discover/monthly/{slug}#picks"') == len(edition["items"])
    # Trails come before the seasonal and challenge tiles, so phones reach them sooner.
    assert html.index('id="trails"') < html.index('id="more-heading"')


def test_discover_trail_pages_carry_covers_and_the_save_dock(client, db_session):
    slug, trail = next(iter(TRAILS.items()))
    html = client.get(f"/discover/{slug}").text
    assert "discover-trail" in html.split("<body", 1)[1].split(">", 1)[0]
    picks = re.findall(r'<article (?:id="pick-[^"]+" )?class="pick dx-pick" data-kind="([a-z]+)">', html)
    assert len(picks) == len(trail["items"])
    assert html.count('class="pick-save x-save"') == len(trail["items"])
    assert 'class="x-dock" data-guest-bar data-guest-only hidden' in html and 'href="/#signup">Keep my list</a>' in html
    edition_slug, edition = next(reversed(published_editions().items()))
    monthly = client.get(f"/discover/monthly/{edition_slug}").text
    assert monthly.count('class="pick dx-pick"') == len(edition["items"]) and "x-dock" in monthly


def test_trending_rows_have_covers_and_guest_saves(client, db_session):
    now = datetime.utcnow()
    for index in range(3):
        user = _member(db_session, f"tr{index}")
        db_session.add(models.Movie(user_id=user.id, title="Row Film", year=2024, added_at=now - timedelta(days=1)))
        db_session.add(models.Anime(user_id=user.id, title="Row Show", year=2023, added_at=now - timedelta(days=2),
                                    poster_url="https://cdn.myanimelist.net/images/anime/4/19644l.jpg"))
    db_session.commit()
    html = client.get("/trending").text
    assert "trending-page explore" in html
    assert re.search(r'<li class="title-chart__entry trend-entry" id="rank-\d" data-kind="anime">', html)
    assert 'data-guest-kind="movie" data-guest-slug="row-film-2024" data-guest-title="Row Film"' in html
    assert 'data-guest-kind="anime" data-guest-slug="row-show-2023"' in html
    assert "/static/guest-list.js" in html and 'class="x-dock"' in html
    assert '<span class="x-kind" data-kind="anime">Anime</span>' in html
    # Members see no guest buttons and no dock.
    client.cookies.set("omnitrackr_session", "anything")
    member = client.get("/trending").text
    client.cookies.clear()
    assert "data-guest-save" not in member and 'class="x-dock"' not in member


def test_a_quiet_week_shows_the_months_leaders(client, db_session):
    now = datetime.utcnow()
    for index in range(2):
        user = _member(db_session, f"mo{index}")
        db_session.add(models.Book(user_id=user.id, title="Month Book", year=2021, added_at=now - timedelta(days=20)))
    db_session.commit()
    html = unescape(client.get("/trending/book").text)
    assert "Nothing is trending this week yet" in html
    assert "here is what led the last 30 days" in html and "Month Book" in html
    assert 'href="/trending/book/month"' in html
    # A month with nothing either keeps the old empty note.
    empty = unescape(client.get("/trending/audiobook").text)
    assert "Nothing is trending this week yet" in empty and "led the last 30 days" not in empty


def test_browse_pages_have_cover_fans_sticky_shelves_and_the_dock(client, db_session):
    hub = client.get("/browse").text
    assert hub.count('class="browse-hub__fan"') == len(CATALOG)
    assert 'class="browse-hub__card" href="/browse/manga" data-kind="manga"' in hub
    page = client.get("/browse/podcasts").text
    assert 'data-kind="podcast"' in page.split("<body", 1)[1].split(">", 1)[0]
    assert '<nav class="x-jump browse-jump" aria-label="On this page">' in page
    assert "x-art--square" in page and 'class="x-dock"' in page
    for shelf in CATALOG["podcasts"]["shelves"]:
        assert f'<a href="#{shelf["slug"]}">' in page
    client.cookies.set("omnitrackr_session", "anything")
    member = client.get("/browse/podcasts").text
    client.cookies.clear()
    assert 'class="x-dock"' not in member and "data-browse-add" in member
