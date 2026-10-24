""""If you liked" guides (/if-you-liked): hand-written picks for after a well-loved title (Oct 2026)."""
import re

import pytest

from app import funnel, if_you_liked, models, pick, title_pages, title_search
from app.auth import AUTH_COOKIE_NAME
from app.if_you_liked_guides import GUIDES


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


def words(entry):
    texts = entry["lead"] + entry["start"] + [a + " " + b for a, b in entry["threads"]]
    texts += [item["why"] + " " + item["note"] + " " + item["caveat"] for item in entry["picks"]]
    return sum(len(text.split()) for text in texts)


def test_every_guide_is_complete_and_substantial():
    assert len(GUIDES) >= 12
    for slug, entry in GUIDES.items():
        assert re.fullmatch(r"[a-z0-9-]{1,80}", slug)
        anchor = entry["anchor"]
        assert anchor["kind"] in title_pages.KINDS and anchor["title"] and 1900 < anchor["year"] < 2030
        assert len(entry["threads"]) == 3 and len(entry["lead"]) >= 2 and entry["start"]
        assert 6 <= len(entry["picks"]) <= 8
        assert len(if_you_liked.formats(entry)) >= 3, slug
        assert 60 <= len(entry["summary"]) <= 170 and entry["search_title"]
        assert words(entry) >= 600, slug
        seen = set()
        for item in entry["picks"]:
            assert item["kind"] in title_pages.KINDS and item["title"] and item["why"] and item["note"] and item["caveat"]
            assert 0 <= item["match"] < 3
            assert item["year"] is None or 1800 < item["year"] < 2030
            assert (item["kind"], title_pages.slugify(item["title"])) != (anchor["kind"], title_pages.slugify(anchor["title"]))
            key = title_pages.slugify(item["title"]) + item["kind"]
            assert key not in seen
            seen.add(key)


def test_every_pick_joins_pick_for_me_so_it_can_be_saved():
    for _, entry in GUIDES.items():
        for item in entry["picks"]:
            pooled = if_you_liked.pool_entry(item)
            assert pooled is not None, item["title"]
            assert pick.find_id(pooled["id"]) is pooled
    # A pick only these guides recommend keeps the guide as its source.
    planetes = pick.find("anime", "planetes-2003")
    assert planetes["source_label"] == "If you liked Interstellar"
    assert planetes["source_url"] == "/if-you-liked/interstellar"


def test_guide_page_reads_completely_without_an_account(client):
    response = client.get("/if-you-liked/interstellar")
    assert response.status_code == 200
    html = response.text
    assert '<meta name="robots" content="index, follow' in html
    assert '<link rel="canonical" href="https://omnitrackr.xyz/if-you-liked/interstellar">' in html
    assert "<title>Movies like Interstellar" in html
    assert "<h1>If you liked Interstellar</h1>" in html
    assert "Three things Interstellar does well" in html and "Where to start" in html and "How we chose" in html
    for item in GUIDES["interstellar"]["picks"]:
        assert f'id="pick-{title_pages.slugify(item["title"])}"' in html
    assert html.count("Save to my list") == len(GUIDES["interstellar"]["picks"])
    assert 'data-guest-kind="game" data-guest-slug="outer-wilds-2019"' in html
    assert "data-guest-bar" in html and "/static/guest-list.js" in html and "/static/if-you-liked.js" in html
    assert "/static/ad-loader.js" in html
    assert '"@type": "Article"' in html and '"ItemList"' in html
    # Related guides and the hub are linked.
    assert html.count('href="/if-you-liked/') >= 3 and 'href="/if-you-liked"' in html
    assert "Cookie" in response.headers["vary"]


def test_members_get_add_buttons_and_no_ads(client):
    client.cookies.set(AUTH_COOKIE_NAME, "anything")
    html = client.get("/if-you-liked/frieren").text
    assert html.count("data-liked-add=") == len(GUIDES["frieren"]["picks"])
    assert "data-guest-bar" not in html and "/static/guest-list.js" not in html
    assert "/static/ad-loader.js" not in html


def test_unknown_guides_are_not_found(client):
    assert client.get("/if-you-liked/not-a-guide").status_code == 404


def test_hub_lists_every_guide(client):
    response = client.get("/if-you-liked")
    assert response.status_code == 200
    for slug, entry in GUIDES.items():
        assert f'href="/if-you-liked/{slug}"' in response.text
    assert "public" in response.headers["cache-control"]


def test_title_pages_and_artwork_link_up_when_members_track_them(client, db_session):
    user = models.User(username="ann", email="ann@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(models.Movie(user_id=user.id, title="Arrival", director="Denis Villeneuve", year=2016,
                                poster_url="https://img.example/arrival.jpg"))
    db_session.add(models.Movie(user_id=user.id, title="Interstellar", director="Christopher Nolan", year=2014,
                                poster_url="https://img.example/interstellar.jpg"))
    db_session.commit()
    html = client.get("/if-you-liked/interstellar").text
    assert 'href="/titles/movie/arrival-2016"' in html and "https://img.example/arrival.jpg" in html
    assert 'href="/titles/movie/interstellar-2014"' in html
    # Picks nobody tracks get no title page link.
    assert "/titles/game/outer-wilds" not in html
    assert "https://img.example/interstellar.jpg" in client.get("/if-you-liked").text


def test_the_anchor_title_page_links_to_its_guide(client, db_session):
    from app.routers.titles import _if_you_liked_html

    class Group:
        kind, title = "anime", "Frieren: Beyond Journey's End"

    section = _if_you_liked_html(Group())
    assert 'href="/if-you-liked/frieren"' in section and "Loved it?" in section

    class Other:
        kind, title = "movie", "Frieren: Beyond Journey's End"

    assert _if_you_liked_html(Other()) == ""
    assert if_you_liked.for_title("tv", "stranger things") == "stranger-things"


def test_member_saves_a_guide_pick_and_it_is_counted_separately(authenticated_client, db_session, monkeypatch):
    recorded = []
    monkeypatch.setattr(funnel, "record", lambda event, request=None: recorded.append(event))
    entry = if_you_liked.pool_entry(GUIDES["interstellar"]["picks"][4])
    body = authenticated_client.post("/api/pick/add", json={"id": entry["id"], "source": "if-you-liked"}).json()
    assert body["state"] == "created" and body["title"] == "Outer Wilds" and body["category"] == "video-games"
    assert recorded == ["liked_saved"]
    game = db_session.query(models.VideoGame).filter_by(title="Outer Wilds").one()
    assert not game.played and game.rating is None
    assert authenticated_client.post("/api/pick/add", json={"id": entry["id"], "source": "elsewhere"}).status_code == 422
    assert {"liked_saved"} <= funnel.CLIENT_EVENTS
    assert "liked_saved" in {item["event"] for item in funnel.summary({})["guest"]}


def test_a_guest_saved_guide_pick_moves_into_the_new_library(authenticated_client, db_session):
    response = authenticated_client.post("/api/guest-list/import", json={"items": [
        {"kind": "book", "slug": "the-remains-of-the-day-1989"}]})
    assert [item["title"] for item in response.json()["added"]] == ["The Remains of the Day"]
    book = db_session.query(models.Book).filter_by(title="The Remains of the Day").one()
    assert book.author == "Kazuo Ishiguro" and book.year == 1989 and not book.read


def test_guides_are_in_the_sitemap_navigation_and_ad_allowlist(client):
    from pathlib import Path
    from app.site_chrome import FOOTER_GROUPS
    sitemap = client.get("/sitemap.xml").text
    assert "https://omnitrackr.xyz/if-you-liked</loc>" in sitemap
    for slug in GUIDES:
        assert f"https://omnitrackr.xyz/if-you-liked/{slug}</loc>" in sitemap
    assert dict(FOOTER_GROUPS)["Explore"] and ("If you liked…", "/if-you-liked") in dict(FOOTER_GROUPS)["Explore"]
    loader = (Path(__file__).parents[1] / "app" / "static" / "ad-loader.js").read_text(encoding="utf-8")
    assert "if-you-liked" in loader
    assert 'href="/if-you-liked/interstellar"' in client.get("/discover").text
    assert "/if-you-liked" in client.get("/llms.txt").text
