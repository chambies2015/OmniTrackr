"""Share links, ranked lists, one-tap adds and share cards for collections (Nov 2026)."""
import json
import re
from types import SimpleNamespace

import pytest

from app import auth, models, site_traffic
from app.routers import collections

INTRO = (
    "These are the stories I return to when I need a little room to think. Each one rewards attention in a "
    "different way, but together they remind me that a memorable experience can be quiet, curious, and kind. "
    "I keep them close because they make a strong case for taking art at its own pace instead of treating every "
    "watch, read, or play session as something to optimize. They are companions for a reflective weekend."
)


def sign_in(client, user):
    client.headers["Authorization"] = "Bearer " + auth.create_access_token({"sub": user.username})


def sign_out(client):
    client.headers.pop("Authorization", None)


@pytest.fixture
def shelf(db_session):
    owner = models.User(username="list_owner", email="owner@example.test", hashed_password="unused",
                        is_active=True, is_verified=True)
    reader = models.User(username="list_reader", email="reader@example.test", hashed_password="unused",
                         is_active=True, is_verified=True)
    db_session.add_all([owner, reader])
    db_session.flush()
    collection = models.Collection(user_id=owner.id, name="My top 3 cozy anime")
    db_session.add(collection)
    db_session.flush()
    titles = ["Frieren", "Yuru Camp", "Natsume's Book of Friends"]
    media = []
    for position, title in enumerate(titles):
        anime = models.Anime(user_id=owner.id, title=title, year=2020 + position, rating=9,
                             review="The owner's private review", watched=True)
        db_session.add(anime)
        db_session.flush()
        db_session.add(models.CollectionItem(collection_id=collection.id, category="anime", item_id=anime.id,
                                             position=position, curator_note=f"Why {title} is cozy."))
        media.append(anime)
    db_session.commit()
    return SimpleNamespace(owner=owner, reader=reader, collection=collection, media=media)


def make_link(client, shelf):
    sign_in(client, shelf.owner)
    response = client.post(f"/collections/{shelf.collection.id}/link")
    assert response.status_code == 200, response.text
    sign_out(client)
    return response.json()["link_url"]


def test_link_needs_three_titles_but_no_introduction(client, db_session, shelf):
    sign_in(client, shelf.owner)
    listing = client.get("/collections/").json()[0]
    assert listing["link_url"] is None
    assert listing["ranked"] is False
    assert listing["readiness"]["link_ready"] is True
    assert listing["readiness"]["share_ready"] is False

    removed = shelf.collection.items[0]
    client.delete(f"/collections/{shelf.collection.id}/items/{removed.id}")
    refused = client.post(f"/collections/{shelf.collection.id}/link")
    assert refused.status_code == 422
    assert "3 titles" in refused.json()["detail"]
    db_session.refresh(shelf.collection)
    assert shelf.collection.link_token is None


def test_link_page_shows_the_list_and_stays_out_of_search(client, db_session, shelf):
    link = make_link(client, shelf)
    assert re.fullmatch(r"/collections/link/[A-Za-z0-9_-]{16,32}", link)
    page = client.get(link)
    assert page.status_code == 200
    assert page.headers["x-robots-tag"] == "noindex, follow"
    assert '<meta name="robots" content="noindex, follow">' in page.text
    # The site-wide policy sends other sites only the origin, never the link's path.
    assert page.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    for anime in shelf.media:
        assert anime.title.replace("'", "&#x27;") in page.text
    assert "Why Frieren is cozy." in page.text
    assert "private review" not in page.text
    assert 'data-collection-action="helpful"' not in page.text
    assert f"{link}/card.png" in page.text
    # A visitor without an account gets a sign-up link for each title.
    assert page.text.count("data-entry-signup") >= 3

    # Never in the gallery.
    gallery = client.get("/collections/explore")
    assert "My top 3 cozy anime" not in gallery.text

    # The owner can make the same link again without changing it.
    sign_in(client, shelf.owner)
    again = client.post(f"/collections/{shelf.collection.id}/link").json()
    assert again == {"link_url": link, "created": False}


def test_turning_the_link_off_or_deactivating_hides_the_page(client, db_session, shelf):
    link = make_link(client, shelf)
    sign_in(client, shelf.owner)
    assert client.delete(f"/collections/{shelf.collection.id}/link").status_code == 204
    sign_out(client)
    gone = client.get(link)
    assert gone.status_code == 404
    assert "shared anymore" in gone.text
    assert gone.headers["x-robots-tag"].startswith("noindex")

    link = make_link(client, shelf)
    shelf.owner.is_active = False
    db_session.commit()
    assert client.get(link).status_code == 404
    assert client.get("/collections/link/not-a-token").status_code == 404


def test_unsafe_wording_blocks_the_link(client, db_session, shelf):
    link = make_link(client, shelf)
    shelf.collection.description = "Watch online free at my telegram channel"
    db_session.commit()
    assert client.get(link).status_code == 404
    sign_in(client, shelf.owner)
    refused = client.post(f"/collections/{shelf.collection.id}/link")
    # The link already exists, but a fresh request still explains what to fix.
    assert refused.status_code == 422
    assert "Reword" in refused.json()["detail"]


def test_published_list_link_goes_to_the_public_page(client, db_session, shelf):
    link = make_link(client, shelf)
    shelf.collection.description = INTRO
    shelf.collection.is_public = True
    db_session.commit()
    response = client.get(link, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == f"/collections/public/{shelf.collection.id}"


def test_ranked_lists_number_the_titles(client, db_session, shelf):
    sign_in(client, shelf.owner)
    updated = client.patch(f"/collections/{shelf.collection.id}", json={"ranked": True})
    assert updated.status_code == 200
    assert updated.json()["ranked"] is True
    link = make_link(client, shelf)
    page = client.get(link).text
    assert "Ranked list · 3 titles" in page
    assert ">#1<" in page and ">#3<" in page
    data = json.loads(re.search(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', page).group(1))
    assert data["itemListOrder"] == "https://schema.org/ItemListOrderAscending"
    assert [entry["position"] for entry in data["itemListElement"]] == [1, 2, 3]


def test_ranked_can_be_set_when_creating(client, db_session, shelf):
    sign_in(client, shelf.owner)
    created = client.post("/collections/", json={"name": "My all-time top 10", "ranked": True})
    assert created.status_code == 201
    assert created.json()["ranked"] is True
    plain = client.post("/collections/", json={"name": "Comfort rewatches"})
    assert plain.json()["ranked"] is False


def test_saving_without_an_introduction_is_allowed_while_private(client, db_session, shelf):
    sign_in(client, shelf.owner)
    response = client.patch(f"/collections/{shelf.collection.id}",
                            json={"name": "Cozy anime", "description": "", "is_public": False, "ranked": True})
    assert response.status_code == 200
    still_refused = client.patch(f"/collections/{shelf.collection.id}", json={"is_public": True})
    assert still_refused.status_code == 422


def test_adding_one_title_from_a_list(client, db_session, shelf):
    link = make_link(client, shelf)
    entry = shelf.collection.items[0]
    path = f"{link}/entries/{entry.id}/library"
    assert client.post(path).status_code == 401

    sign_in(client, shelf.reader)
    page = client.get(link).text
    assert page.count("data-entry-save=") == 3
    first = client.post(path)
    assert first.status_code == 200
    assert first.json() == {"added": True, "already": False, "title": "Frieren"}
    copies = db_session.query(models.Anime).filter_by(user_id=shelf.reader.id).all()
    assert [(copy.title, copy.watched, copy.rating, copy.review) for copy in copies] == [("Frieren", False, None, None)]
    again = client.post(path).json()
    assert again["added"] is False and again["already"] is True
    assert db_session.query(models.Anime).filter_by(user_id=shelf.reader.id).count() == 1
    page = client.get(link).text
    assert "In your library" in page
    assert page.count("data-entry-save=") == 2

    # The owner's own list never copies anything.
    sign_in(client, shelf.owner)
    mine = client.post(path).json()
    assert mine["added"] is False
    assert "data-entry-save=" not in client.get(link).text

    missing = client.post(f"{link}/entries/999999/library")
    assert missing.status_code == 404


def test_one_tap_add_works_on_public_pages(client, db_session, shelf):
    shelf.collection.description = INTRO
    shelf.collection.is_public = True
    db_session.commit()
    entry = shelf.collection.items[1]
    sign_in(client, shelf.reader)
    page = client.get(f"/collections/public/{shelf.collection.id}")
    assert page.status_code == 200
    assert 'data-collection-action="helpful"' in page.text
    response = client.post(f"/collections/public/{shelf.collection.id}/entries/{entry.id}/library")
    assert response.json()["title"] == "Yuru Camp"


def test_share_card_is_a_png(client, db_session, shelf):
    link = make_link(client, shelf)
    card = client.get(f"{link}/card.png")
    assert card.status_code == 200
    assert card.headers["content-type"] == "image/png"
    assert card.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert card.headers["cache-control"].startswith("private")
    assert client.get(f"/collections/public/{shelf.collection.id}/card.png").status_code == 404


def test_reports_through_a_link_hide_it(client, db_session, shelf, monkeypatch):
    link = make_link(client, shelf)
    monkeypatch.setattr(collections, "PUBLIC_COLLECTION_REPORT_THRESHOLD", 2)
    for visitor in range(2):
        client.cookies.clear()
        response = client.post(f"{link}/report", json={"reason": "spam"},
                               headers={"User-Agent": f"visitor-{visitor}"})
        assert response.status_code == 201
    if db_session.query(models.CollectionReport).count() < 2:
        pytest.skip("visitor identity is shared in this test client")
    client.cookies.clear()
    assert client.get(link).status_code == 404
    note = db_session.query(models.Notification).filter_by(user_id=shelf.owner.id).one()
    assert "share link" in note.message


def test_link_addresses_stay_out_of_site_stats():
    assert site_traffic.mask_private_link("/collections/link/AbCdEfGhIjKlMnOpQr") == "/collections/link/(private link)"
    assert site_traffic.mask_private_link("/collections/public/12") == "/collections/public/12"


def test_export_keeps_ranked_but_never_the_link(client, db_session, shelf):
    make_link(client, shelf)
    shelf.collection.ranked = True
    db_session.commit()
    from app.routers import export_import
    exported = export_import._export_collections(db_session, shelf.owner.id)
    assert exported[0]["ranked"] is True
    assert "link" not in json.dumps(exported)
    db_session.delete(shelf.collection)
    db_session.commit()
    created, skipped = export_import._import_collections(db_session, shelf.owner.id, exported)
    assert (created, skipped) == (1, 0)
    restored = db_session.query(models.Collection).filter_by(user_id=shelf.owner.id).one()
    assert restored.ranked is True and restored.link_token is None and restored.is_public is False
