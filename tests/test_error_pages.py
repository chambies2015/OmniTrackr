"""Styled error pages for browsers, JSON for API clients, and noindex on all of them."""
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter

from app import error_pages

HTML = {"Accept": "text/html,application/xhtml+xml"}


def make_app():
    app = FastAPI()
    app.state.limiter = Limiter(key_func=lambda: "test")
    error_pages.install(app)

    @app.get("/boom")
    def boom():
        raise RuntimeError("database fell over")

    @app.get("/busy")
    @app.state.limiter.limit("1/minute")
    def busy(request: Request):
        return {"ok": True}

    return TestClient(app, raise_server_exceptions=False)


def test_not_found_page_offers_search_and_places(client):
    page = client.get("/definitely-missing", headers=HTML)
    assert page.status_code == 404 and page.headers["X-Robots-Tag"] == "noindex"
    assert '<meta name="robots" content="noindex, follow">' in page.text
    assert "This page drifted into the void" in page.text
    assert 'data-site-search-open data-search-hint="definitely missing"' in page.text
    assert "Popular places" in page.text and 'href="/release-radar"' in page.text
    assert 'href="/contact"' in page.text


def test_not_found_copy_matches_the_section(client):
    title = client.get("/titles/movie/the-matrixx-1999", headers=HTML)
    assert title.status_code == 404 and "We don&#x27;t have a page for that title yet" in title.text
    assert 'data-search-hint="the matrixx"' in title.text
    profile = client.get("/u/nobody-here", headers=HTML)
    assert profile.status_code == 404 and "This profile isn&#x27;t available" in profile.text
    assert 'data-search-hint=""' in profile.text


def test_search_hint_ignores_ids_and_markup():
    assert error_pages.search_hint("/titles/anime/frieren-42") == "frieren"
    assert error_pages.search_hint("/collections/public/123") == ""
    assert error_pages.search_hint('/x/"><img src=x onerror=alert(1)>') == "img src x onerror alert"
    assert error_pages.search_hint("/") == ""
    assert len(error_pages.search_hint("/" + "a-" * 200)) <= 60


def test_hint_is_escaped_on_the_page(client):
    page = client.get('/x/%22%3E%3Cimg%20src=x%3E', headers=HTML)
    assert page.status_code == 404 and "<img src=x>" not in page.text


def test_api_clients_keep_json_not_found(client):
    assert client.get("/definitely-missing").json() == {"detail": "Not Found"}
    assert client.get("/api/definitely-missing", headers=HTML).json() == {"detail": "Not Found"}


def test_server_error_page_for_browsers():
    test_client = make_app()
    page = test_client.get("/boom", headers=HTML)
    assert page.status_code == 500 and "Something broke on our end" in page.text
    assert "database fell over" not in page.text
    assert page.headers["X-Robots-Tag"] == "noindex" and page.headers["Cache-Control"] == "no-store"
    assert page.headers["X-Frame-Options"] == "DENY" and "Content-Security-Policy" in page.headers
    assert 'href="/contact"' in page.text


def test_server_error_stays_json_for_fetch_calls():
    response = make_app().get("/boom")
    assert response.status_code == 500
    assert response.json() == {"detail": error_pages.SERVER_ERROR_DETAIL}


def test_rate_limited_page_for_browsers_and_json_for_fetch():
    test_client = make_app()
    assert test_client.get("/busy", headers=HTML).status_code == 200
    page = test_client.get("/busy", headers=HTML)
    assert page.status_code == 429 and "Give it a minute" in page.text
    assert page.headers["X-Robots-Tag"] == "noindex"
    response = test_client.get("/busy")
    assert response.status_code == 429 and "Rate limit exceeded" in response.json()["error"]
