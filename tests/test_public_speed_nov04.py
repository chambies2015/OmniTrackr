"""Nov 4 2026 speed pass on public pages: image sizes, connection hints, small assets, slow radar sources."""
import asyncio
import io
import time
from pathlib import Path

from PIL import Image

from app import models, release_radar as radar
from app.image_sizes import shrink_html, sized
from app.page_hints import add_preconnects, eager_image_origins
from tests.test_release_radar import window
from tests.test_title_charts import _rate

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
APPLE = ("https://is1-ssl.mzstatic.com/image/thumb/Podcasts211/v4/e8/d7/ca/e8d7ca5c-35fa-6e90-42ec-09e168d110cc/"
         "mza_400047353205660386.jpg/600x600bb.png")
IMDB = ("https://m.media-amazon.com/images/M/MV5BNTkwNzJiYTctNzI3NC00NjE1LTlhYjktY2Q5MTdmMWFmNzcxXkEyXkFqcGc@."
        "_V1_QL75_UX380_CR0,0,380,562_.jpg")


# ---------------------------------------------------------------- image sizes

def test_apple_artwork_is_asked_for_as_a_small_webp():
    base = APPLE.rsplit("/", 1)[0]
    assert sized(APPLE) == f"{base}/400x400bb.webp"
    assert sized(APPLE, 640) == f"{base}/600x600bb.webp"
    assert sized(APPLE, display_width=96) == f"{base}/200x200bb.webp"
    # Never larger than what Apple stores.
    assert sized(APPLE.replace("600x600bb.png", "100x100bb.jpg")) == f"{base}/100x100bb.webp"


def test_imdb_and_open_library_covers_shrink_only_for_small_thumbnails():
    assert sized(IMDB) == IMDB
    assert sized(IMDB, display_width=96).endswith("._V1_QL75_UX240_.jpg")
    large = "https://covers.openlibrary.org/b/id/11240448-L.jpg"
    assert sized(large) == large
    assert sized(large, display_width=72) == "https://covers.openlibrary.org/b/id/11240448-M.jpg"


def test_shrink_html_rewrites_img_tags_but_not_links():
    html = (f'<a href="{APPLE}">art</a><img class="yl-pick__art" src="{IMDB}" width="96" height="144">'
            f'<img src="{APPLE}" alt="">')
    out = shrink_html(html)
    assert f'<a href="{APPLE}">' in out
    assert "_V1_QL75_UX240_.jpg" in out and "400x400bb.webp" in out


# ---------------------------------------------------------------- preconnect hints

def test_preconnect_names_the_first_eager_image_hosts():
    page = ('<html><head><meta charset="utf-8"><link rel="stylesheet" href="/static/site.css"></head><body>'
            '<img src="/vortex-mark.webp"><img src="https://m.media-amazon.com/images/M/a.jpg">'
            '<img loading="lazy" src="https://lazy.example.com/b.jpg"><img src="https://m.media-amazon.com/images/M/c.jpg">'
            '<img src="https://upload.wikimedia.org/d.jpg"><img src="https://s4.anilist.co/e.jpg"></body></html>')
    out = add_preconnects(page)
    head = out.split("</head>", 1)[0]
    assert head.index('rel="preconnect" href="https://m.media-amazon.com"') < head.index('rel="stylesheet"')
    assert 'href="https://upload.wikimedia.org"' in head
    assert "lazy.example.com" not in head and "anilist" not in head  # Lazy images and a third host are skipped.
    assert add_preconnects(out) == out  # Never added twice.


def test_preconnect_leaves_pages_without_outside_images_alone():
    page = '<html><head></head><body><img src="/vortex-mark.webp" alt=""></body></html>'
    assert add_preconnects(page) == page


def test_title_chart_page_preconnects_to_its_posters(client, db_session):
    _rate(db_session, "Preconnect Proof", 2031, [9, 9, 8], "p")
    db_session.query(models.Movie).update({"poster_url": "https://m.media-amazon.com/images/M/poster._V1_SX300.jpg"})
    db_session.commit()
    html = client.get("/titles/movie/preconnect-proof-2031").text
    head = html.split("</head>", 1)[0]
    origins = eager_image_origins(html)
    assert origins, html[html.find("<body"):][:2000]
    for origin in origins:
        assert f'<link rel="preconnect" href="{origin}">' in head


# ---------------------------------------------------------------- small assets

def test_header_logo_uses_the_small_mark(client):
    response = client.get("/vortex-mark.webp")
    assert response.status_code == 200 and response.headers["content-type"] == "image/webp"
    assert len(response.content) < 2_000
    assert Image.open(io.BytesIO(response.content)).size == (84, 84)
    assert '<img src="/vortex-mark.webp" alt="" width="28" height="28">' in client.get("/about").text


def test_favicon_keeps_its_sizes_but_not_the_256_pixel_frame():
    icon = STATIC / "omnitrackr_favicon.ico"
    assert icon.stat().st_size < 16_000
    assert {(16, 16), (32, 32), (48, 48)} <= set(Image.open(icon).info["sizes"])


def test_homepage_no_longer_waits_on_the_empty_credentials_script(client):
    html = client.get("/").text
    assert "/credentials.js" not in html


def test_google_analytics_loads_after_the_page():
    loader = (STATIC / "analytics.js").read_text(encoding="utf-8")
    assert "addEventListener('load'" in loader and "requestIdleCallback" in loader
    # The queued config still runs before gtag.js arrives, so the visit is recorded.
    assert loader.index("window.gtag('config'") < loader.index("function load()")


# ---------------------------------------------------------------- broken links

def test_chart_quote_from_a_short_review_links_to_the_title_not_a_missing_page(client, db_session):
    users = _rate(db_session, "Interstellar", 2014, [9, 9, 8], "q")
    short = "Interstellar is the one I rewatch most, mostly for the docking scene and the score that carries it."
    db_session.query(models.Movie).filter_by(user_id=users[0].id).update({"review": short, "review_public": True})
    db_session.commit()
    html = client.get("/titles/movie").text
    assert "the docking scene" in html
    review_id = db_session.query(models.Movie).filter_by(user_id=users[0].id).one().id
    assert f"/reviews/{review_id}?category=movie" not in html
    assert 'href="/titles/movie/interstellar-2014#community-title">more reviews</a>' in html
    assert client.get(f"/reviews/{review_id}?category=movie").status_code == 404


# ---------------------------------------------------------------- slow radar sources

def test_page_views_share_one_wait_on_a_slow_radar_source(monkeypatch):
    cache = radar.RadarCache(None)

    async def slow(client, window):
        await asyncio.sleep(5)
        return []

    monkeypatch.setitem(radar.PROVIDERS, "games", slow)
    w = window("games", "2026-10")

    async def scenario():
        started = time.time()
        assert await cache.get(None, w, wait=0.3) is None  # The first visitor waits...
        assert time.time() - started >= 0.25
        again = time.time()
        assert await cache.get(None, w, wait=0.3) is None  # ...the next one does not wait again.
        assert time.time() - again < 0.1
        cache.tasks[w.cache_key].cancel()

    asyncio.new_event_loop().run_until_complete(scenario())


def test_background_jobs_still_wait_in_full(monkeypatch):
    cache = radar.RadarCache(None)
    calls = []

    async def slowish(client, window):
        calls.append(1)
        await asyncio.sleep(0.4)
        return [radar.make_item(category="games", key="rawg-a", title="A", release_date="2026-10-02", source_url=None)]

    monkeypatch.setitem(radar.PROVIDERS, "games", slowish)
    w = window("games", "2026-10")

    async def scenario():
        assert await cache.get(None, w, wait=0.05) is None
        await asyncio.sleep(0.1)
        entry = await cache.get(None, w, wait=radar.FIRST_LOAD_WAIT_SECONDS + 1)
        assert entry["items"][0]["title"] == "A"

    asyncio.new_event_loop().run_until_complete(scenario())
    assert len(calls) == 1
