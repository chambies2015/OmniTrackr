"""Shared tier lists (/tier-list/s/<token>, Nov 2026): links with or without an account, claiming, the card."""
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import funnel, models, site_traffic, tier_list, tier_list_shares
from app.main import app

POSTER = "https://m.media-amazon.com/images/poster.jpg"


def board(count=4, **extra):
    titles = ["Dune", "Heat", "Alien", "Arrival", "Up", "Jaws"][:count]
    tiers = {"S": [], "A": [], "B": [], "C": [], "D": []}
    for index, title in enumerate(titles):
        tiers["SABCD"[index % 5]].append({"title": title, "kind": "movie", "year": 1990 + index,
                                          "slug": f"{title.lower()}-{1990 + index}", "image": POSTER})
    payload = {"name": "My movie tiers", "labels": {"S": "Rewatch yearly"}, "tiers": tiers}
    payload.update(extra)
    return payload


@pytest.fixture(autouse=True)
def fresh_caches():
    tier_list.clear_cache()
    yield
    tier_list.clear_cache()


@pytest.fixture
def guest(client):
    with TestClient(app) as other:
        yield other


def test_a_guest_can_make_a_link_that_expires_and_is_never_indexed(client, db_session):
    made = client.post("/api/tier-list/shares", json=board())
    assert made.status_code == 200, made.text
    data = made.json()
    assert data["path"] == f"/tier-list/s/{data['token']}" and tier_list_shares.valid_token(data["token"])
    assert data["key"] and data["member"] is False and data["expires_at"]
    share = db_session.query(models.TierListShare).one()
    assert share.owner_id is None and share.visitor and share.key_hash != data["key"]
    assert share.expires_at - datetime.utcnow() > timedelta(days=tier_list_shares.GUEST_DAYS - 1)

    page = client.get(data["path"])
    assert page.status_code == 200
    assert "noindex" in page.headers["x-robots-tag"]
    assert '<meta name="robots" content="noindex' in page.text
    assert "My movie tiers" in page.text and "Rewatch yearly" in page.text and "Dune" in page.text
    assert f'href="/tier-list?remix={data["token"]}"' in page.text
    assert f'/tier-list/s/{data["token"]}/card.png?v=' in page.text
    assert 'href="/titles/movie/dune-1990"' in page.text


def test_board_text_is_cleaned_and_links_or_contacts_are_refused(client):
    payload = board()
    payload["tiers"]["S"].append({"title": "<script>x</script>", "kind": "nope", "year": "1999",
                                  "slug": "../etc", "image": "https://evil.example/pixel.gif"})
    data = client.post("/api/tier-list/shares", json=payload).json()
    state = client.get(f"/api/tier-list/shares/{data['token']}").json()
    odd = next(item for item in state["tiers"]["S"] if item["title"] == "<script>x</script>")
    assert odd == {"title": "<script>x</script>", "kind": None, "year": None, "slug": None, "image": None}
    assert "<script>x</script>" not in client.get(data["path"]).text

    for spam in ("Visit cheap-pills.ru", "https://spam.example", "mail me@example.com", "call 555 123 4567 89"):
        refused = client.post("/api/tier-list/shares", json=board(name=spam))
        assert refused.status_code == 400 and "can't go on a shared tier list" in refused.json()["detail"]
    too_few = client.post("/api/tier-list/shares", json=board(count=2))
    assert too_few.status_code == 400 and "at least 3" in too_few.json()["detail"]


def test_only_the_key_or_owner_can_change_or_delete_a_link(client, guest):
    made = client.post("/api/tier-list/shares", json=board()).json()
    token, key = made["token"], made["key"]
    assert guest.put(f"/api/tier-list/shares/{token}", json=board(name="Hijacked")).status_code == 403
    assert guest.put(f"/api/tier-list/shares/{token}", json=board(name="Hijacked", key="x" * 32)).status_code == 403
    assert guest.request("DELETE", f"/api/tier-list/shares/{token}", json={"key": "y" * 32}).status_code == 403
    updated = guest.put(f"/api/tier-list/shares/{token}", json=board(name="Renamed", key=key))
    assert updated.status_code == 200 and "key" not in updated.json()
    assert client.get(f"/api/tier-list/shares/{token}").json()["name"] == "Renamed"
    assert guest.request("DELETE", f"/api/tier-list/shares/{token}", json={"key": key}).status_code == 204
    gone = client.get(f"/tier-list/s/{token}")
    assert gone.status_code == 404 and "This tier list link isn" in gone.text
    assert client.get(f"/api/tier-list/shares/{token}").status_code == 404


def test_expired_guest_links_stop_working(client, db_session):
    made = client.post("/api/tier-list/shares", json=board()).json()
    share = db_session.query(models.TierListShare).one()
    share.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()
    assert client.get(made["path"]).status_code == 404
    assert client.get(f"{made['path']}/card.png").status_code == 404


def test_signing_up_claims_links_made_in_this_browser(guest, authenticated_client, db_session):
    made = guest.post("/api/tier-list/shares", json=board()).json()
    other = guest.post("/api/tier-list/shares", json=board(name="Not mine")).json()
    claimed = authenticated_client.post("/api/tier-list/shares/claim", json={"links": [
        {"token": made["token"], "key": made["key"]},
        {"token": other["token"], "key": "wrong-key-wrong-key-wrong"},
    ]})
    assert claimed.status_code == 200 and claimed.json() == {"claimed": 1}
    user = db_session.query(models.User).filter_by(username="testuser").one()
    share = db_session.query(models.TierListShare).filter_by(token=made["token"]).one()
    db_session.refresh(share)
    assert share.owner_id == user.id and share.expires_at is None and share.visitor is None
    mine = authenticated_client.get("/api/tier-list/shares/mine").json()["links"]
    assert [link["token"] for link in mine] == [made["token"]]
    # Claiming again does nothing, and the member can now edit without the key.
    assert authenticated_client.post("/api/tier-list/shares/claim", json={"links": [made]}).json() == {"claimed": 0}
    assert authenticated_client.put(f"/api/tier-list/shares/{made['token']}", json=board(name="Mine now")).status_code == 200
    assert guest.get("/api/tier-list/shares/claim").status_code in (404, 405)
    assert guest.post("/api/tier-list/shares/claim", json={"links": []}).status_code == 401


def test_member_links_never_expire_and_credit_only_a_public_profile(authenticated_client, guest, db_session):
    made = authenticated_client.post("/api/tier-list/shares", json=board()).json()
    assert made["member"] is True and made["expires_at"] is None
    page = guest.get(made["path"]).text
    assert "By an OmniTrackr member" in page and "testuser" not in page
    user = db_session.query(models.User).filter_by(username="testuser").one()
    db_session.add(models.PublicProfile(user_id=user.id, enabled=True))
    db_session.commit()
    assert "testuser" in guest.get(made["path"]).text


def test_views_and_ranking_it_yourself_are_counted(client, guest, db_session, monkeypatch):
    recorded = []
    monkeypatch.setattr(funnel, "record", lambda event, request=None: recorded.append(event) or True)
    made = client.post("/api/tier-list/shares", json=board(template="franchise-star-wars")).json()
    client.get(made["path"])  # the maker's own browser: not a view
    guest.get(made["path"])
    guest.get(made["path"])
    share = db_session.query(models.TierListShare).one()
    db_session.refresh(share)
    assert share.views == 2
    assert recorded.count("tier_list_link_opened") == 2 and "tier_list_link_created" in recorded

    copy = guest.post("/api/tier-list/shares", json=board(name="My take", source=made["token"])).json()
    db_session.refresh(share)
    assert share.remixes == 1
    state = guest.get(f"/api/tier-list/shares/{copy['token']}").json()
    assert state["source"] == {"name": "My movie tiers", "path": made["path"]}
    assert state["template"] == "franchise-star-wars"
    assert f'A take on <a href="{made["path"]}">' in guest.get(copy["path"]).text


def test_guests_have_a_cap_on_live_links(client, monkeypatch):
    monkeypatch.setattr(tier_list_shares, "GUEST_MAX_LINKS", 2)
    assert client.post("/api/tier-list/shares", json=board()).status_code == 200
    assert client.post("/api/tier-list/shares", json=board()).status_code == 200
    capped = client.post("/api/tier-list/shares", json=board())
    assert capped.status_code == 409 and "free account" in capped.json()["detail"]


def test_share_card_draws_posters_through_the_allowlist(client):
    from io import BytesIO
    from PIL import Image
    poster = BytesIO()
    Image.new("RGB", (100, 150), (200, 30, 30)).save(poster, format="JPEG")
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=poster.getvalue(), headers={"content-type": "image/jpeg"})

    previous = getattr(app.state, "external_api_client", None)
    app.state.external_api_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        made = client.post("/api/tier-list/shares", json=board()).json()
        card = client.get(f"{made['path']}/card.png")
    finally:
        if previous is None:
            del app.state.external_api_client
        else:
            app.state.external_api_client = previous
    assert card.status_code == 200 and card.headers["content-type"] == "image/png"
    assert card.headers["x-robots-tag"] == "noindex"
    image = Image.open(BytesIO(card.content))
    assert image.size == (1200, 630)
    assert calls and set(calls) == {POSTER}


def test_card_works_without_posters():
    data = {"labels": {tier: tier for tier in tier_list.TIERS},
            "tiers": {tier: [{"title": f"Title {tier} {n}", "kind": "movie"} for n in range(25)] for tier in tier_list.TIERS}}
    png = tier_list_shares.render_card("A long list", data, "someone on OmniTrackr", {})
    assert png.startswith(b"\x89PNG")
    shown = tier_list_shares.card_items(data)
    assert len(shown) == (tier_list_shares.card_per_row() - 1) * 5


def test_maker_page_offers_links_franchise_sets_and_a_remix_start(client):
    html = client.get("/tier-list").text
    assert "data-tier-link>" in html and "Get a share link" in html
    assert 'data-tier-template="franchise-star-wars"' in html and "Browse all" in html
    assert 'href="/?next=%2Ftier-list#signup" data-tier-signup' in html
    remix = client.get("/tier-list?remix=AAAAAAAAAAAAAAAA")
    assert 'data-remix="AAAAAAAAAAAAAAAA"' in remix.text and '<meta name="robots" content="noindex' in remix.text
    assert 'data-remix=""' in client.get('/tier-list?remix="><b>').text
    one = client.get("/api/tier-list/templates?key=franchise-zelda").json()["templates"]
    assert len(one) == 1 and one[0]["board"] == "The Legend of Zelda tier list" and len(one[0]["items"]) >= 6
    assert client.get("/api/tier-list/templates?key=nope").json() == {"templates": []}


def test_share_events_are_counted_and_links_are_masked_in_site_stats():
    names = {name for name, _ in funnel.GUEST}
    assert {"tier_list_link_created", "tier_list_link_opened", "tier_list_remix_started",
            "tier_list_signup_clicked", "tier_list_link_claimed", "tier_list_template_started"} <= names
    assert {"tier_list_remix_started", "tier_list_signup_clicked", "tier_list_template_started"} <= funnel.CLIENT_EVENTS
    assert "tier_list_link_created" not in funnel.CLIENT_EVENTS
    assert site_traffic.clean_path("/tier-list/s/AbCdEfGhIjKlMnOp") == "/tier-list/s/(private link)"
    assert site_traffic.clean_path("/tier-list") == "/tier-list"
