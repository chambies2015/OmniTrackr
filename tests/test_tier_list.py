"""Tier list maker (/tier-list): starting sets, ranking a member's library, and the poster proxy (Oct 2026)."""
import httpx
import pytest

from app import funnel, models, tier_list, title_search
from app.auth import AUTH_COOKIE_NAME
from app.main import app


@pytest.fixture(autouse=True)
def fresh_caches():
    tier_list.clear_cache()
    title_search.clear_cache()
    yield
    tier_list.clear_cache()
    title_search.clear_cache()


@pytest.fixture
def upstream(monkeypatch):
    """Replace the shared outbound client with a scripted one; records every URL requested."""
    calls = []
    routes = {}

    def handler(request):
        calls.append(str(request.url))
        return routes.get(str(request.url), httpx.Response(404))

    previous = getattr(app.state, "external_api_client", None)
    app.state.external_api_client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
    yield routes, calls
    if previous is None:
        del app.state.external_api_client
    else:
        app.state.external_api_client = previous


def test_ratings_map_to_tiers():
    assert tier_list.tier_for_rating(10) == "S" and tier_list.tier_for_rating(9.0) == "S"
    assert tier_list.tier_for_rating(8.9) == "A" and tier_list.tier_for_rating(7) == "B"
    assert tier_list.tier_for_rating(5.5) == "C" and tier_list.tier_for_rating(5.4) == "D"
    assert tier_list.tier_for_rating(0) == "D"
    assert tier_list.tier_for_rating(None) is None and tier_list.tier_for_rating("x") is None


def test_public_page_is_indexable_with_guide_text_and_a_template_link_is_not(client):
    response = client.get("/tier-list")
    assert response.status_code == 200
    html = response.text
    assert '<meta name="robots" content="index, follow' in html
    assert '<link rel="canonical" href="https://omnitrackr.xyz/tier-list">' in html
    assert "Rank anything from S to D" in html
    assert "How to make a tier list that says something" in html and "What the tiers usually mean" in html
    assert 'id="tierTool"' in html and 'data-tier-row="S"' in html and 'data-tier-row="D"' in html
    assert 'data-tier-template="editors-movie"' in html and 'href="/tier-list?template=editors-movie"' in html
    assert "/static/tier-list.js?v=" in html and "/static/guest-list.js?v=" in html
    assert "Log in</a> to turn your own" in html and "data-tier-library>" not in html
    shared = client.get("/tier-list?template=editors-movie")
    assert '<meta name="robots" content="noindex' in shared.text
    assert 'data-template="editors-movie"' in shared.text


def test_template_value_is_escaped(client):
    html = client.get('/tier-list?template="><script>alert(1)</script>').text
    assert "<script>alert(1)</script>" not in html


def test_signed_in_visitors_get_the_library_form(client):
    client.cookies.set(AUTH_COOKIE_NAME, "anything")
    html = client.get("/tier-list").text
    assert "data-tier-library>" in html and "Use my ratings" in html
    assert "/static/guest-list.js" not in html


def test_templates_come_from_editorial_picks_and_popular_titles_without_member_details(client, db_session):
    for index in range(6):
        user = models.User(username=f"member{index}", email=f"m{index}@example.com", hashed_password="x",
                           is_active=True, is_verified=True)
        db_session.add(user)
        db_session.flush()
        for title in ("Dune", "Arrival", "Heat", "Alien", "Up", "Jaws"):
            db_session.add(models.Movie(title=title, year=1990, user_id=user.id, rating=7, review="secret note",
                                        poster_url="https://m.media-amazon.com/images/x.jpg"))
    db_session.commit()
    data = client.get("/api/tier-list/templates").json()["templates"]
    keys = [template["key"] for template in data]
    assert "popular-movie" in keys and "editors-movie" in keys and "editors-book" in keys
    popular = next(template for template in data if template["key"] == "popular-movie")
    assert {item["title"] for item in popular["items"]} == {"Dune", "Arrival", "Heat", "Alien", "Up", "Jaws"}
    assert all(set(item) == {"kind", "title", "year", "image", "slug"} for item in popular["items"])
    assert "secret note" not in str(data) and "member0" not in str(data)
    dune = next(item for item in popular["items"] if item["title"] == "Dune")
    assert dune["slug"] == "dune-1990" and dune["image"] == "https://m.media-amazon.com/images/x.jpg"


def test_library_ranks_the_members_own_titles_by_rating(authenticated_client, db_session):
    user = db_session.query(models.User).filter_by(username="testuser").one()
    other = models.User(username="someone", email="s@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add(other)
    db_session.flush()
    db_session.add_all([
        models.Movie(title="Top", year=2001, rating=9.5, user_id=user.id),
        models.Movie(title="Fine", year=2002, rating=7.2, user_id=user.id),
        models.Movie(title="Meh", year=2003, rating=3, user_id=user.id),
        models.Movie(title="Unrated", year=2004, user_id=user.id),
        models.Movie(title="Not mine", year=2005, rating=10, user_id=other.id),
    ])
    db_session.commit()
    before = [(m.id, m.title, m.rating) for m in db_session.query(models.Movie).order_by(models.Movie.id)]
    response = authenticated_client.get("/api/tier-list/library?kind=movie")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    items = {item["title"]: item["tier"] for item in response.json()["items"]}
    assert items == {"Top": "S", "Fine": "B", "Meh": "D", "Unrated": None}
    assert [item["title"] for item in response.json()["items"]][-1] == "Unrated"
    # Reading the library never changes it.
    assert [(m.id, m.title, m.rating) for m in db_session.query(models.Movie).order_by(models.Movie.id)] == before
    assert authenticated_client.get("/api/tier-list/library?kind=nope").status_code == 400


def test_library_requires_an_account(client):
    assert client.get("/api/tier-list/library?kind=movie").status_code == 401


@pytest.mark.parametrize("url", [
    "https://evil.example/poster.jpg",
    "https://m.media-amazon.com.evil.example/x.jpg",
    "file:///etc/passwd",
    "https://user:pass@m.media-amazon.com/x.jpg",
    "https://m.media-amazon.com:8443/x.jpg",
    "http://169.254.169.254/latest/meta-data",
    "javascript:alert(1)",
])
def test_image_proxy_refuses_anything_off_the_allowlist(client, upstream, url):
    _, calls = upstream
    assert client.get("/api/tier-list/image", params={"url": url}).status_code == 400
    assert calls == []


def test_image_proxy_serves_allowlisted_posters(client, upstream):
    routes, _ = upstream
    routes["https://m.media-amazon.com/images/a.jpg"] = httpx.Response(
        200, content=b"\xff\xd8jpeg", headers={"content-type": "image/jpeg"})
    response = client.get("/api/tier-list/image", params={"url": "https://m.media-amazon.com/images/a.jpg"})
    assert response.status_code == 200 and response.content == b"\xff\xd8jpeg"
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "max-age=86400" in response.headers["cache-control"]


def test_image_proxy_rechecks_every_redirect_and_rejects_non_images(client, upstream):
    routes, calls = upstream
    routes["https://covers.openlibrary.org/b/id/1-M.jpg"] = httpx.Response(
        302, headers={"location": "https://ia800100.us.archive.org/view/1.jpg"})
    routes["https://ia800100.us.archive.org/view/1.jpg"] = httpx.Response(
        200, content=b"png", headers={"content-type": "image/png"})
    ok = client.get("/api/tier-list/image", params={"url": "https://covers.openlibrary.org/b/id/1-M.jpg"})
    assert ok.status_code == 200 and ok.content == b"png"

    routes["https://media.rawg.io/a.jpg"] = httpx.Response(302, headers={"location": "http://10.0.0.1/admin"})
    assert client.get("/api/tier-list/image", params={"url": "https://media.rawg.io/a.jpg"}).status_code == 400
    assert "http://10.0.0.1/admin" not in calls

    routes["https://media.rawg.io/b.svg"] = httpx.Response(200, content=b"<svg/>", headers={"content-type": "image/svg+xml"})
    assert client.get("/api/tier-list/image", params={"url": "https://media.rawg.io/b.svg"}).status_code == 415
    routes["https://media.rawg.io/c.html"] = httpx.Response(200, content=b"<html>", headers={"content-type": "text/html"})
    assert client.get("/api/tier-list/image", params={"url": "https://media.rawg.io/c.html"}).status_code == 415


def test_image_proxy_caps_the_size(client, upstream):
    routes, _ = upstream
    routes["https://media.rawg.io/big.jpg"] = httpx.Response(
        200, content=b"x" * (tier_list.IMAGE_MAX_BYTES + 1), headers={"content-type": "image/jpeg"})
    assert client.get("/api/tier-list/image", params={"url": "https://media.rawg.io/big.jpg"}).status_code == 413


def test_tier_list_is_linked_counted_and_in_the_sitemap(client):
    from app.site_chrome import FOOTER_GROUPS
    assert ("Tier list maker", "/tier-list") in dict(FOOTER_GROUPS)["Explore"]
    assert {"tier_list_started", "tier_list_exported"} <= funnel.CLIENT_EVENTS
    assert {"tier_list_started", "tier_list_exported"} <= {item["event"] for item in funnel.summary({})["guest"]}
    assert "https://omnitrackr.xyz/tier-list</loc>" in client.get("/sitemap.xml").text
    assert client.post("/api/funnel", json={"event": "tier_list_exported"}).status_code in (200, 202, 204)
