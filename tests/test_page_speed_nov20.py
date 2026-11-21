"""Page speed pass (Nov 20 2026): less server work per request, compressed copies of scripts and
stylesheets, a dashboard that holds its cards still on slow phones, and fewer challenge-card queries."""
import gzip
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import event
from starlette.responses import PlainTextResponse

from app import challenges, compression, models
from app.main import app as site_app
from app.middleware import RateLimitMiddleware
from tests.conftest import engine

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
TEMPLATES = ROOT / "app" / "templates"


@contextmanager
def counting():
    seen = []

    def count(_conn, _cursor, statement, *_args, **_kwargs):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", count)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", count)


# ---------------------------------------------------------------- rate limits without the route walk

def _limited_app(**limiter_options):
    limiter = Limiter(key_func=get_remote_address, **limiter_options)
    app = FastAPI()
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def too_many(request, exc):
        return PlainTextResponse("slow down", status_code=429)

    @app.get("/limited")
    @limiter.limit("2/minute")
    def limited(request: Request):
        return {"ok": True}

    @app.get("/open")
    def open_route():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware)
    return app


def test_route_limits_still_apply_without_slowapis_middleware_walk():
    client = TestClient(_limited_app())
    assert [client.get("/limited").status_code for _ in range(3)] == [200, 200, 429]
    assert all(client.get("/open").status_code == 200 for _ in range(5))


def test_default_limits_still_go_through_slowapis_own_middleware():
    client = TestClient(_limited_app(default_limits=["2/minute"]))
    assert [client.get("/open").status_code for _ in range(3)] == [200, 200, 429]


def test_site_sets_no_app_wide_limits_so_the_fast_path_is_taken():
    limiter = site_app.state.limiter
    assert not RateLimitMiddleware.has_global_limits(limiter)
    assert not any(m.cls.__name__ == "SlowAPIMiddleware" for m in site_app.user_middleware)
    assert any(m.cls is RateLimitMiddleware for m in site_app.user_middleware)


# ---------------------------------------------------------------- compressed copies of assets

def test_scripts_and_stylesheets_are_compressed_once_and_reused(client):
    compression.copies.clear()
    path = "/static/site.css?v=test"
    first = client.get(path, headers={"Accept-Encoding": "gzip"})
    assert first.status_code == 200
    assert first.headers["content-encoding"] == "gzip"
    assert "Accept-Encoding" in first.headers["vary"]
    assert first.content == (STATIC / "site.css").read_bytes()  # The client decodes it.
    assert len(compression.copies.entries) == 1
    second = client.get(path, headers={"Accept-Encoding": "gzip"})
    assert second.content == first.content
    assert len(compression.copies.entries) == 1
    # Same caching and security headers as before.
    assert second.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert second.headers["x-content-type-options"] == "nosniff"
    assert "etag" in second.headers


def test_compressed_copy_matches_the_file_and_states_its_length():
    import asyncio

    body = (STATIC / "site.css").read_bytes()
    compressed = asyncio.run(compression.compressed_copy(body))
    assert gzip.decompress(compressed) == body
    assert compression.copies.get(compression.CompressedCopies.key(body)) == compressed


def test_root_scripts_and_the_dashboard_bundle_use_the_cache(client):
    compression.copies.clear()
    for path in ("/auth.js?v=test", "/preauth.js", "/dashboard.css?v=test", "/app.js?v=test"):
        response = client.get(path, headers={"Accept-Encoding": "gzip"})
        assert response.status_code == 200, path
        if len(response.content) >= compression.MINIMUM_SIZE:
            assert response.headers["content-encoding"] == "gzip", path
    assert len(compression.copies.entries) >= 3


def test_images_fonts_and_conditional_requests_pass_through(client):
    font = client.get("/static/fonts/inter-var-latin.woff2", headers={"Accept-Encoding": "gzip"})
    assert font.status_code == 200 and "content-encoding" not in font.headers
    image = client.get("/vortex-mark.webp", headers={"Accept-Encoding": "gzip"})
    assert image.status_code == 200 and "content-encoding" not in image.headers
    first = client.get("/static/site.css", headers={"Accept-Encoding": "gzip"})
    again = client.get("/static/site.css", headers={"Accept-Encoding": "gzip", "If-None-Match": first.headers["etag"]})
    assert again.status_code == 304 and again.content == b""
    partial = client.get("/static/site.css", headers={"Accept-Encoding": "gzip", "Range": "bytes=0-9"})
    assert partial.status_code == 206 and len(partial.content) == 10 and "content-encoding" not in partial.headers


def test_assets_without_gzip_and_pages_are_unchanged(client):
    plain = client.get("/static/site.css", headers={"Accept-Encoding": "identity"})
    assert plain.status_code == 200 and "content-encoding" not in plain.headers
    assert plain.content == (STATIC / "site.css").read_bytes()
    page = client.get("/about", headers={"Accept-Encoding": "gzip"})
    assert page.status_code == 200 and page.headers["content-encoding"] == "gzip"
    assert "<html" in page.text
    head = client.head("/static/site.css", headers={"Accept-Encoding": "gzip"})
    assert head.status_code in (200, 405)


def test_only_files_served_as_they_are_count_as_assets():
    assert compression.is_asset_path("/static/site.css")
    assert compression.is_asset_path("/app.js")
    assert compression.is_asset_path("/dashboard.css")
    assert not compression.is_asset_path("/static/profile_pictures/1_a.png")
    assert not compression.is_asset_path("/api/home/today")
    assert not compression.is_asset_path("/titles/movie/inception-2010")
    assert not compression.is_asset_path("/u/someone/card.png")


def test_the_cache_stays_inside_its_size_limit():
    copies = compression.CompressedCopies(max_bytes=100)
    copies.put(b"a", b"x" * 60)
    copies.put(b"b", b"y" * 60)
    assert list(copies.entries) == [b"b"] and copies.size == 60
    copies.put(b"c", b"z" * 500)  # Bigger than the whole cache: never kept.
    assert list(copies.entries) == [b"b"]


# ---------------------------------------------------------------- middlewares still do their jobs

def test_security_headers_csrf_and_bot_filter_still_apply(client):
    page = client.get("/about")
    assert page.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" in page.headers
    assert client.get("/auth/me").headers["cache-control"].startswith("no-store")
    assert client.get("/.env").status_code == 404
    rejected = client.post("/movies/", json={"title": "x"}, headers={"Origin": "https://evil.example"})
    assert rejected.status_code == 403
    assert rejected.json() == {"detail": "Cross-site request rejected"}


# ---------------------------------------------------------------- challenge card queries

def test_before_step_reads_release_years_in_one_query_per_format(db_session, monkeypatch):
    month = challenges.month_key()
    monkeypatch.setitem(challenges.CHALLENGES, month, {
        "name": "Old things", "tagline": "t", "intro": [], "reflection": "r",
        "steps": [{"kind": "before", "year": 2000, "label": "Old", "detail": "d"}],
    })
    user = models.User(username="oldtimer", email="oldtimer@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.commit()
    now = datetime.utcnow()
    for index in range(30):
        movie = models.Movie(user_id=user.id, title=f"Film {index}", year=1990 + index, watched=True)
        db_session.add(movie)
        db_session.flush()
        db_session.add(models.CompletionMoment(user_id=user.id, category="movies", item_id=movie.id,
                                               title=movie.title, completed_at=now))
    old_game = models.VideoGame(user_id=user.id, title="Old Game", release_date=datetime(1998, 5, 1), played=True)
    new_game = models.VideoGame(user_id=user.id, title="New Game", release_date=None, played=True)
    db_session.add_all([old_game, new_game])
    db_session.flush()
    for game in (old_game, new_game):
        db_session.add(models.CompletionMoment(user_id=user.id, category="video-games", item_id=game.id,
                                               title=game.title, completed_at=now))
    db_session.commit()
    db_session.expire_all()

    with counting() as queries:
        steps = challenges.progress(db_session, user.id, month)
    # Films from 1990 to 1999 plus the 1998 game; the step needs one.
    assert steps[0]["done"] is True
    finishes = challenges._finishes(db_session, user.id, month)
    years = challenges._release_years(db_session, finishes)
    assert sum(1 for year in years.values() if year and year < 2000) == 11
    assert years[("game", new_game.id)] is None
    # Finish reads plus one per format, not one per title (32 finishes here).
    assert len([sql for sql in queries if "FROM movies" in sql]) == 1
    assert len([sql for sql in queries if "FROM video_games" in sql]) == 1
    assert len(queries) <= 6, queries


# ---------------------------------------------------------------- dashboard reveal

def test_dashboard_wait_starts_when_the_page_has_parsed():
    preauth = (STATIC / "preauth.js").read_text(encoding="utf-8")
    assert "document.addEventListener('DOMContentLoaded', () => setTimeout(reveal, 3000), { once: true });" in preauth
    assert "setTimeout(reveal, 10000);" in preauth
    index = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    # Every card that can sit above the library waits with it.
    for card in ("#homeHero", "#friendRecs", "#yearInReviewBanner", "#libraryLaunchpad", "#returnDeck"):
        assert card in index.split("{visibility:hidden}")[0].rsplit("html.dashboard-settling", 1)[1]
