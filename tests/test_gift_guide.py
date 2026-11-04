"""Holiday gift guide (/holidays/gifts) and shareable gift lists (/gifts/<token>), Nov 2026."""
import re

import pytest
from fastapi.testclient import TestClient

from app import affiliate, editorial_index, funnel, gift_lists, models, title_pages, title_search
from app.gift_guides import GIFTS, GUIDE, SECTIONS
from app.main import app
from app.routers import gift_guide

TAG = "omnitrackr-20"


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


@pytest.fixture
def tagged(monkeypatch):
    monkeypatch.setenv("AMAZON_ASSOCIATES_TAG", TAG)


@pytest.fixture
def visitor():
    """A second browser with no account, sharing the test database."""
    with TestClient(app) as other:
        yield other


def _user(db_session, username="testuser"):
    return db_session.query(models.User).filter_by(username=username).one()


def _words():
    texts = GUIDE["intro"] + GUIDE["method"] + [q + " " + a for q, a in GUIDE["faq"]]
    for section in SECTIONS:
        texts += section["intro"]
        texts += [gift["why"] + " " + gift["for"] + " " + gift["check"] for gift in section["gifts"]]
    return sum(len(text.split()) for text in texts)


def test_the_guide_covers_every_format_with_four_gifts_each():
    assert [section["kind"] for section in SECTIONS] == list(title_pages.KINDS)
    assert _words() >= 3000
    assert 60 <= len(GUIDE["summary"]) <= 200
    sizes = {key for key, _, _ in GUIDE["sizes"]}
    for section in SECTIONS:
        assert re.fullmatch(r"[a-z0-9-]{1,40}", section["key"]) and section["intro"] and section["tagline"]
        assert len(section["gifts"]) == 4
        assert len({gift["size"] for gift in section["gifts"]}) >= 2, section["key"]
        for gift in section["gifts"]:
            assert re.fullmatch(r"[a-z0-9-]{2,60}", gift["id"])
            assert gift["size"] in sizes and gift["store"] in affiliate.SEARCH_STORES
            assert gift["name"] and gift["search"] and gift["why"] and gift["for"] and gift["check"]
            if gift["kind"] is not None:
                assert gift["kind"] in title_pages.KINDS and gift["title"] and 1900 < gift["year"] < 2030
    assert len(GIFTS) == 36


def test_guide_reads_without_an_account_and_carries_the_disclosure(client, tagged):
    response = client.get("/holidays/gifts")
    assert response.status_code == 200
    html = response.text
    assert "<h1>" in html and GUIDE["headline"] in html.replace("&#x27;", "'")
    assert html.count('class="gg-gift"') == 36
    assert html.count('rel="sponsored noopener noreferrer"') == 36
    assert f"tag={TAG}" in html and "As an Amazon Associate OmniTrackr earns from qualifying purchases" in html
    # The disclosure comes before the first shop link.
    assert html.index("As an Amazon Associate") < html.index("amazon.com/s?")
    assert '"FAQPage"' in html and '"ItemList"' in html
    assert "data-gift-signup" in html and "/?next=%2Fholidays%2Fgifts#signup" in html
    assert "data-gift-panel" not in html and "data-gift-add-guide" not in html
    assert "/static/ad-loader.js" in html and "/static/gift-guide.js" in html
    assert 'href="/holidays"' in html
    assert "Cookie" in response.headers["vary"]


def test_without_a_tag_the_guide_has_no_shop_links(client, monkeypatch):
    monkeypatch.delenv("AMAZON_ASSOCIATES_TAG", raising=False)
    html = client.get("/holidays/gifts").text
    assert "amazon.com" not in html and "As an Amazon Associate" not in html
    assert html.count('class="gg-gift"') == 36


def test_members_get_the_panel_their_formats_first_and_what_they_own(authenticated_client, db_session):
    user = _user(db_session)
    for number in range(3):
        db_session.add(models.Anime(user_id=user.id, title=f"Show {number}", year=2020, watched=False))
    db_session.add(models.Anime(user_id=user.id, title="cowboy bebop", year=1998, watched=True, rating=10))
    db_session.commit()
    html = authenticated_client.get("/holidays/gifts").text
    assert "data-gift-panel" in html and html.count("data-gift-add-guide=") == 36
    assert "/static/ad-loader.js" not in html
    sections = re.findall(r'<section class="sn-shelf gg-section" id="([a-z-]+)"', html)
    assert sections[0] == "anime" and sorted(sections) == sorted(section["key"] for section in SECTIONS)
    assert "Sorted for you" in html
    card = html[html.index('id="gift-cowboy-bebop"'):]
    assert "You’ve finished this one" in card[:card.index("</article>")]


def test_building_and_sharing_a_list(authenticated_client, db_session, visitor, tagged, monkeypatch):
    recorded = []
    monkeypatch.setattr(funnel, "record", lambda event, request=None: recorded.append(event))
    user = _user(db_session)
    waiting = models.Book(user_id=user.id, title="Piranesi", author="Susanna Clarke", year=2020, read=False,
                          cover_art_url="https://covers.openlibrary.org/b/id/1-L.jpg")
    loved = models.Movie(user_id=user.id, title="Arrival", director="Denis Villeneuve", year=2016, watched=True, rating=9.5)
    meh = models.Movie(user_id=user.id, title="Meh", director="Someone", year=2010, watched=True, rating=5)
    podcast = models.Podcast(user_id=user.id, title="Free Show", listened=False)
    db_session.add_all([waiting, loved, meh, podcast])
    db_session.commit()

    first = authenticated_client.get("/api/gift-list").json()
    assert first["list"]["exists"] is False
    assert [entry["title"] for entry in first["suggestions"]["waiting"]] == ["Piranesi"]
    assert [entry["title"] for entry in first["suggestions"]["favourites"]] == ["Arrival"]

    added = authenticated_client.post("/api/gift-list/items", json={"source": "library", "kind": "book", "item_id": waiting.id})
    assert added.status_code == 200 and added.json()["state"] == "created"
    assert recorded == ["gift_list_started"]
    body = added.json()
    assert body["list"]["count"] == 1 and body["suggestions"]["waiting"] == []
    item = body["item"]
    assert item["title"] == "Piranesi" and item["creator"] == "Susanna Clarke" and item["year"] == 2020

    again = authenticated_client.post("/api/gift-list/items", json={"source": "library", "kind": "book", "item_id": waiting.id})
    assert again.json()["state"] == "existing" and again.json()["list"]["count"] == 1
    guide = authenticated_client.post("/api/gift-list/items", json={"source": "guide", "gift_id": "audio-technica-lp60x"}).json()
    assert guide["item"]["title"] == "An Audio-Technica AT-LP60X turntable" and guide["item"]["kind"] == "other"
    typed = authenticated_client.post("/api/gift-list/items", json={"source": "text", "text": "  A   warm   scarf "}).json()
    assert typed["item"]["title"] == "A warm scarf"
    note = authenticated_client.patch(f"/api/gift-list/items/{item['id']}", json={"note": "Hardback if you can"})
    assert note.json()["item"]["note"] == "Hardback if you can"
    assert recorded == ["gift_list_started"]

    # The library itself is untouched.
    db_session.expire_all()
    assert db_session.query(models.Book).filter_by(user_id=user.id).count() == 1
    assert db_session.get(models.Book, waiting.id).read is False

    owner = authenticated_client.get("/api/gift-list").json()["list"]
    assert owner["count"] == 3 and owner["shared"] is True
    path = owner["path"]
    assert re.fullmatch(r"/gifts/[A-Za-z0-9_-]{16,32}", path) and owner["url"].endswith(path)

    page = visitor.get(path)
    assert page.status_code == 200
    html = page.text
    assert "testuser’s gift list" in html and "Hardback if you can" in html
    assert "noindex" in page.headers["x-robots-tag"] and "no-store" in page.headers["cache-control"]
    assert html.count('rel="sponsored noopener noreferrer"') == 3 and "As an Amazon Associate" in html
    assert "Audio-Technica+AT-LP60X+turntable" in html and "i=electronics" in html
    assert "A+warm+scarf" in html
    assert html.count("data-gift-claim=") == 3 and "/static/ad-loader.js" not in html
    assert "gift_list_link_opened" in recorded


def test_claims_are_hidden_from_the_owner_and_undone_only_by_their_key(authenticated_client, db_session, visitor):
    authenticated_client.post("/api/gift-list/items", json={"source": "text", "text": "Dune on 4K"})
    owner = authenticated_client.get("/api/gift-list").json()["list"]
    token = owner["path"].rsplit("/", 1)[1]
    item_id = owner["items"][0]["id"]
    claim_url = f"/api/gifts/{token}/items/{item_id}/claim"

    assert authenticated_client.post(claim_url).status_code == 403
    claimed = visitor.post(claim_url)
    assert claimed.status_code == 200
    key = claimed.json()["key"]
    assert visitor.post(claim_url).status_code == 409

    stored = db_session.query(models.GiftListItem).get(item_id)
    db_session.refresh(stored)
    assert stored.claimed_at is not None and stored.claim_hash != key and len(stored.claim_hash) == 64

    # The visitor sees it taken; the owner sees nothing about it, on the page or in the API.
    assert "Someone’s getting this" in visitor.get(owner["path"]).text
    owner_page = authenticated_client.get(owner["path"]).text
    assert "Someone’s getting this" not in owner_page and "data-gift-claim=" not in owner_page
    assert "how your list looks" in owner_page
    assert "claimed" not in authenticated_client.get("/api/gift-list").json()["list"]["items"][0]

    unclaim_url = f"/api/gifts/{token}/items/{item_id}/unclaim"
    assert visitor.post(unclaim_url, json={"key": "x" * 32}).status_code == 403
    assert visitor.post(unclaim_url, json={"key": key}).status_code == 200
    db_session.refresh(stored)
    assert stored.claimed_at is None and stored.claim_hash is None


def test_the_owner_can_switch_off_or_replace_the_link(authenticated_client, visitor):
    authenticated_client.post("/api/gift-list/items", json={"source": "text", "text": "Socks, honestly"})
    old = authenticated_client.get("/api/gift-list").json()["list"]["path"]
    assert visitor.get(old).status_code == 200

    off = authenticated_client.patch("/api/gift-list", json={"shared": False, "message": "No socks this year!"}).json()["list"]
    assert off["shared"] is False and off["message"] == "No socks this year!"
    gone = visitor.get(old)
    assert gone.status_code == 404 and "noindex" in gone.headers["x-robots-tag"]
    token = old.rsplit("/", 1)[1]
    assert visitor.post(f"/api/gifts/{token}/items/1/claim").status_code == 404

    authenticated_client.patch("/api/gift-list", json={"shared": True})
    assert "No socks this year!" in visitor.get(old).text
    new = authenticated_client.post("/api/gift-list/link").json()["list"]["path"]
    assert new != old and visitor.get(old).status_code == 404 and visitor.get(new).status_code == 200


def test_list_limits_and_ownership(authenticated_client, db_session, visitor, monkeypatch):
    monkeypatch.setattr(gift_lists, "ITEMS_MAX", 2)
    assert authenticated_client.post("/api/gift-list/items", json={"source": "text", "text": "One"}).status_code == 200
    assert authenticated_client.post("/api/gift-list/items", json={"source": "text", "text": "Two"}).status_code == 200
    full = authenticated_client.post("/api/gift-list/items", json={"source": "text", "text": "Three"})
    assert full.status_code == 400 and "most it can hold" in full.json()["detail"]
    assert authenticated_client.post("/api/gift-list/items", json={"source": "text", "text": "x"}).status_code == 400
    assert authenticated_client.post("/api/gift-list/items", json={"source": "guide", "gift_id": "nope"}).status_code == 404
    assert authenticated_client.post("/api/gift-list/items",
                                     json={"source": "library", "kind": "podcast", "item_id": 1}).status_code == 400
    # Another member's library row can't be copied, and another member's item can't be edited.
    other = models.User(username="someoneelse", email="else@example.com", hashed_password="x", is_verified=True)
    db_session.add(other)
    db_session.flush()
    row = models.Movie(user_id=other.id, title="Private", year=2020, watched=False)
    other_list = models.GiftList(owner_id=other.id, token="T" * 22)
    db_session.add_all([row, other_list])
    db_session.flush()
    other_item = models.GiftListItem(list_id=other_list.id, kind="other", title="Theirs", normalized="theirs")
    db_session.add(other_item)
    db_session.commit()
    assert authenticated_client.post("/api/gift-list/items",
                                     json={"source": "library", "kind": "movie", "item_id": row.id}).status_code == 404
    assert authenticated_client.delete(f"/api/gift-list/items/{other_item.id}").status_code == 404
    assert authenticated_client.patch(f"/api/gift-list/items/{other_item.id}", json={"note": "hi"}).status_code == 404
    # A deactivated member's list stops working.
    assert visitor.get("/gifts/" + "T" * 22).status_code == 200
    other.is_active = False
    db_session.commit()
    assert visitor.get("/gifts/" + "T" * 22).status_code == 404
    assert visitor.get("/gifts/short").status_code == 404


def test_member_api_needs_an_account(client):
    assert client.get("/api/gift-list").status_code == 401
    assert client.post("/api/gift-list/items", json={"source": "text", "text": "Hi there"}).status_code == 401
    assert client.patch("/api/gift-list", json={"shared": False}).status_code == 401
    assert client.post("/api/gift-list/link").status_code == 401


def test_gift_list_text_is_escaped(authenticated_client, visitor):
    authenticated_client.post("/api/gift-list/items", json={"source": "text", "text": "<script>alert(1)</script> {{TITLE}}"})
    authenticated_client.patch("/api/gift-list", json={"message": "<img src=x onerror=alert(1)>"})
    html = visitor.get(authenticated_client.get("/api/gift-list").json()["list"]["path"]).text
    assert "<script>alert(1)" not in html and "<img src=x" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_the_guide_is_linked_from_the_hub_sitemap_and_guide_index(client, authenticated_client, monkeypatch):
    from app import seasonal
    assert 'href="/holidays/gifts"' in client.get("/holidays").text
    assert "/holidays/gifts" in client.get("/sitemap.xml").text
    assert any(piece["href"] == "/holidays/gifts" for piece in editorial_index.entries())
    monkeypatch.setattr(seasonal, "current", lambda today=None: "holidays")
    card = authenticated_client.get("/api/seasonal/current").json()
    assert card["links"][0]["path"] == "/holidays/gifts"
    assert "gift_buy_clicked" in funnel.CLIENT_EVENTS and "gift_list_signup_clicked" in funnel.CLIENT_EVENTS


def test_search_links_keep_the_tag_and_a_known_store(tagged):
    link = affiliate.search_links("Kindle Paperwhite", "electronics")[0]
    assert link["url"].startswith("https://www.amazon.com/s?") and f"tag={TAG}" in link["url"] and "i=electronics" in link["url"]
    assert "i=aps" in affiliate.search_links("Anything", "not-a-store")[0]["url"]
    assert affiliate.search_links("   ") == []
    assert gift_guide.ordered_sections(None) == SECTIONS
