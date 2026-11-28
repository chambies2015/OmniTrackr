"""Top nine (/top-nine, Nov 2026): grids with or without an account, the shared page, pictures, keeping the nine."""
from datetime import date, datetime, timedelta
from io import BytesIO

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import funnel, models, site_traffic, title_pages, top_nine, top_nine_card
from app.main import app

POSTER = "https://m.media-amazon.com/images/poster.jpg"


def grid(count=5, **extra):
    titles = [("Dune", "movie", 2021), ("Heat", "movie", 1995), ("Hades II", "game", 2025), ("The Pitt", "tv", 2025),
              ("Blue Lock", "anime", 2022), ("Mayhem", "album", 2025), ("Intermezzo", "book", 2024),
              ("Frieren", "manga", 2020), ("Up", "movie", 2009)][:count]
    tiles = [{"title": title, "kind": kind, "year": year, "slug": f"{title.lower().replace(' ', '-')}-{year}",
              "image": POSTER if index < 2 else None} for index, (title, kind, year) in enumerate(titles)]
    payload = {"name": "Best of my year", "theme": "berry", "tiles": tiles}
    payload.update(extra)
    return payload


@pytest.fixture(autouse=True)
def fresh_catalog():
    top_nine.clear_cache()
    yield
    top_nine.clear_cache()


@pytest.fixture
def guest(client):
    with TestClient(app) as other:
        yield other


@pytest.fixture
def posters():
    """Poster fetches answer with a small red JPEG and are recorded."""
    poster = BytesIO()
    Image.new("RGB", (100, 150), (200, 30, 30)).save(poster, format="JPEG")
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, content=poster.getvalue(), headers={"content-type": "image/jpeg"})

    previous = getattr(app.state, "external_api_client", None)
    app.state.external_api_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        yield calls
    finally:
        if previous is None:
            del app.state.external_api_client
        else:
            app.state.external_api_client = previous


def test_a_guest_can_make_a_grid_whose_link_expires_and_is_never_indexed(client, db_session):
    made = client.post("/api/top-nine", json=grid())
    assert made.status_code == 200, made.text
    data = made.json()
    assert data["path"] == f"/top-nine/{data['token']}" and top_nine.valid_token(data["token"])
    assert data["key"] and data["member"] is False and data["expires_at"] and data["count"] == 5
    assert made.headers["cache-control"].startswith("private")
    row = db_session.query(models.TopNine).one()
    assert row.owner_id is None and row.visitor and row.key_hash != data["key"] and data["key"] not in row.key_hash
    assert row.expires_at - datetime.utcnow() > timedelta(days=top_nine.GUEST_DAYS - 1)
    assert row.year == top_nine.season_year() and row.theme == "berry"

    page = client.get(data["path"])
    assert page.status_code == 200
    assert "noindex" in page.headers["x-robots-tag"]
    assert '<meta name="robots" content="noindex' in page.text
    assert "Best of my year" in page.text and "Hades II" in page.text and "The Pitt" in page.text
    assert f'href="/top-nine?from={data["token"]}"' in page.text
    assert f'{data["path"]}/card.png?v=' in page.text
    assert "How many have you seen?" in page.text and "0 of 5" in page.text
    # The maker's own browser sees the owner box straight away.
    assert 'data-owner="true"' in page.text and "This is your top nine." in page.text


def test_tiles_are_cleaned_and_links_or_contacts_are_refused(client):
    payload = grid(3)
    payload["tiles"] += [
        {"title": "<script>x</script>", "kind": "movie", "year": 1999, "slug": "../etc",
         "image": "https://evil.example/pixel.gif"},
        {"title": "dune", "kind": "movie", "year": 2021},  # the same title twice keeps the first
        {"title": "Something", "kind": "nope"},
        None,
    ]
    data = client.post("/api/top-nine", json=payload).json()
    assert data["count"] == 4
    state = client.get(f"/api/top-nine/{data['token']}").json()
    tiles = state["tiles"]
    assert len(tiles) == top_nine.SLOTS
    odd = tiles[3]
    assert odd["title"] == "<script>x</script>" and odd["slug"] is None and odd["image"] is None
    assert tiles[4] is None and tiles[5] is None
    assert tiles[0]["image"] == POSTER
    html = client.get(data["path"]).text
    assert "<script>x</script>" not in html and "&lt;script&gt;x&lt;/script&gt;" in html

    for spam in ("Visit cheap-pills.ru", "https://spam.example", "mail me@example.com", "call 555 123 4567 89"):
        refused = client.post("/api/top-nine", json=grid(name=spam))
        assert refused.status_code == 400 and "can't go on a top nine" in refused.json()["detail"]
    sneaky = grid()
    sneaky["tiles"][2]["creator"] = "find me at cheap-pills.ru"
    assert client.post("/api/top-nine", json=sneaky).status_code == 400
    too_few = client.post("/api/top-nine", json=grid(2))
    assert too_few.status_code == 400 and "at least 3" in too_few.json()["detail"]
    too_many = grid(9)
    too_many["tiles"].append({"title": "Ten", "kind": "movie"})
    assert client.post("/api/top-nine", json=too_many).status_code == 422
    long_name = client.post("/api/top-nine", json=grid(name="x" * 100)).json()
    assert client.get(f"/api/top-nine/{long_name['token']}").json()["name"] == "x" * top_nine.MAX_NAME
    unnamed = client.post("/api/top-nine", json=grid(name="  ", theme="neon")).json()
    state = client.get(f"/api/top-nine/{unnamed['token']}").json()
    assert state["name"] == f"My {top_nine.season_year()}" and state["theme"] == "night"


def test_only_the_key_or_owner_can_change_or_delete_a_grid(client, guest):
    made = client.post("/api/top-nine", json=grid()).json()
    token, key = made["token"], made["key"]
    assert guest.put(f"/api/top-nine/{token}", json=grid(name="Hijacked")).status_code == 403
    assert guest.put(f"/api/top-nine/{token}", json=grid(name="Hijacked", key="x" * 32)).status_code == 403
    assert guest.request("DELETE", f"/api/top-nine/{token}", json={"key": "y" * 32}).status_code == 403
    before = client.get(f"/api/top-nine/{token}").json()["version"]
    updated = guest.put(f"/api/top-nine/{token}", json=grid(7, name="Renamed", key=key))
    assert updated.status_code == 200 and "key" not in updated.json() and updated.json()["count"] == 7
    state = client.get(f"/api/top-nine/{token}").json()
    assert state["name"] == "Renamed" and state["version"] != before
    assert guest.request("DELETE", f"/api/top-nine/{token}", json={"key": key}).status_code == 204
    gone = client.get(f"/top-nine/{token}")
    assert gone.status_code == 404 and "This top nine isn" in gone.text
    assert client.get(f"/api/top-nine/{token}").status_code == 404
    assert client.get("/api/top-nine/not-a-token").status_code == 404


def test_expired_guest_grids_and_closed_accounts_stop_working(client, authenticated_client, db_session):
    made = client.post("/api/top-nine", json=grid()).json()
    row = db_session.query(models.TopNine).filter_by(token=made["token"]).one()
    row.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()
    assert client.get(made["path"]).status_code == 404
    assert client.get(f"{made['path']}/post.jpg").status_code == 404
    assert client.get(f"/api/top-nine/{made['token']}").status_code == 404

    mine = authenticated_client.post("/api/top-nine", json=grid()).json()
    assert mine["member"] is True and mine["expires_at"] is None
    user = db_session.query(models.User).filter_by(username="testuser").one()
    user.is_active = False
    db_session.commit()
    assert authenticated_client.get(f"/api/top-nine/{mine['token']}").status_code == 404


def test_signing_up_claims_grids_made_in_this_browser(guest, authenticated_client, db_session, monkeypatch):
    recorded = []
    monkeypatch.setattr(funnel, "record", lambda event, request=None: recorded.append(event) or True)
    made = guest.post("/api/top-nine", json=grid()).json()
    other = guest.post("/api/top-nine", json=grid(name="Not mine")).json()
    claimed = authenticated_client.post("/api/top-nine/claim", json={"links": [
        {"token": made["token"], "key": made["key"]},
        {"token": other["token"], "key": "wrong-key-wrong-key-wrong"},
    ]})
    assert claimed.status_code == 200 and claimed.json() == {"claimed": [made["token"]]}
    assert "top_nine_claimed" in recorded
    user = db_session.query(models.User).filter_by(username="testuser").one()
    row = db_session.query(models.TopNine).filter_by(token=made["token"]).one()
    db_session.refresh(row)
    assert row.owner_id == user.id and row.expires_at is None and row.visitor is None
    mine = authenticated_client.get("/api/top-nine/mine").json()["grids"]
    assert [entry["token"] for entry in mine] == [made["token"]]
    assert mine[0]["images"] == [POSTER, POSTER] and mine[0]["count"] == 5
    # Claiming again does nothing, and the member can now edit without the key.
    again = authenticated_client.post("/api/top-nine/claim", json={"links": [{"token": made["token"], "key": made["key"]}]})
    assert again.json() == {"claimed": []}
    assert authenticated_client.put(f"/api/top-nine/{made['token']}", json=grid(name="Mine now")).status_code == 200
    # The old key no longer edits a grid that belongs to an account.
    assert guest.put(f"/api/top-nine/{made['token']}", json=grid(key=made["key"])).status_code == 403
    assert guest.post("/api/top-nine/claim", json={"links": []}).status_code == 401
    assert guest.get("/api/top-nine/mine").status_code == 401


def test_member_grids_credit_only_a_public_profile(authenticated_client, guest, db_session):
    made = authenticated_client.post("/api/top-nine", json=grid()).json()
    page = guest.get(made["path"]).text
    assert "By an OmniTrackr member" in page and "testuser" not in page
    assert 'data-owner="false"' in page and "Create a free account" in page
    user = db_session.query(models.User).filter_by(username="testuser").one()
    db_session.add(models.PublicProfile(user_id=user.id, enabled=True))
    db_session.commit()
    assert "testuser" in guest.get(made["path"]).text
    assert guest.get(f"/api/top-nine/{made['token']}").json()["by"] == "testuser"


def test_views_answers_and_remixes_are_counted_but_not_the_makers_own(client, guest, db_session, monkeypatch):
    recorded = []
    monkeypatch.setattr(funnel, "record", lambda event, request=None: recorded.append(event) or True)
    made = client.post("/api/top-nine", json=grid()).json()
    client.get(made["path"])  # the maker's own browser: not a view
    guest.get(made["path"])
    guest.get(made["path"])
    row = db_session.query(models.TopNine).one()
    db_session.refresh(row)
    assert row.views == 2
    assert recorded.count("top_nine_link_opened") == 2 and "top_nine_made" in recorded

    assert client.post(f"/api/top-nine/{made['token']}/answer", json={"seen": 3}).json() == {"answers": 0}
    assert guest.post(f"/api/top-nine/{made['token']}/answer", json={"seen": 3}).json() == {"answers": 1}
    assert guest.post(f"/api/top-nine/{made['token']}/answer", json={"seen": 12}).status_code == 422
    db_session.refresh(row)
    assert row.answers == 1 and recorded.count("top_nine_answered") == 1

    copy = guest.post("/api/top-nine", json=grid(name="My take", source=made["token"])).json()
    db_session.refresh(row)
    assert row.remixes == 1 and "top_nine_remixed" in recorded
    remixed = db_session.query(models.TopNine).filter_by(token=copy["token"]).one()
    assert remixed.source_id == row.id
    # A source that isn't a live grid is ignored.
    plain = guest.post("/api/top-nine", json=grid(source="AAAAAAAAAAAAAAAA")).json()
    assert db_session.query(models.TopNine).filter_by(token=plain["token"]).one().source_id is None
    third = guest.get(made["path"]).text
    assert "opened 3 times" in third and "1 made their own from it" in third


def test_guests_and_members_have_a_cap_on_grids(client, monkeypatch):
    monkeypatch.setattr(top_nine, "GUEST_MAX_LIVE", 2)
    assert client.post("/api/top-nine", json=grid()).status_code == 200
    assert client.post("/api/top-nine", json=grid()).status_code == 200
    capped = client.post("/api/top-nine", json=grid())
    assert capped.status_code == 409 and "free account" in capped.json()["detail"]


def test_member_cap(authenticated_client, monkeypatch):
    monkeypatch.setattr(top_nine, "MEMBER_MAX", 1)
    assert authenticated_client.post("/api/top-nine", json=grid()).status_code == 200
    capped = authenticated_client.post("/api/top-nine", json=grid())
    assert capped.status_code == 409 and "Delete one" in capped.json()["detail"]


def test_keeping_the_nine_adds_new_titles_finished_and_leaves_existing_ones(authenticated_client, guest, db_session,
                                                                            monkeypatch):
    recorded = []
    monkeypatch.setattr(funnel, "record", lambda event, request=None: recorded.append(event) or True)
    user = db_session.query(models.User).filter_by(username="testuser").one()
    db_session.add(models.Movie(user_id=user.id, title="Dune", year=2021, watched=False, rating=6))
    db_session.commit()
    made = authenticated_client.post("/api/top-nine", json=grid(6)).json()
    kept = authenticated_client.post(f"/api/top-nine/{made['token']}/keep")
    assert kept.status_code == 200, kept.text
    result = kept.json()
    assert [entry["title"] for entry in result["existing"]] == ["Dune"]
    assert {entry["title"] for entry in result["added"]} == {"Heat", "Hades II", "The Pitt", "Blue Lock", "Mayhem"}
    assert "top_nine_kept" in recorded
    dune = db_session.query(models.Movie).filter_by(user_id=user.id, title="Dune").one()
    assert dune.watched is False and dune.rating == 6
    for title, kind in (("Heat", "movie"), ("Hades II", "game"), ("The Pitt", "tv"), ("Mayhem", "album")):
        model = title_pages.KINDS[kind][0]
        record = db_session.query(model).filter_by(user_id=user.id, title=title).one()
        assert getattr(record, title_pages.COMPLETE_FIELD[kind]) is True
    heat = db_session.query(models.Movie).filter_by(user_id=user.id, title="Heat").one()
    assert heat.poster_url == POSTER or getattr(heat, "cover_art_url", None) == POSTER
    # Pressing it again adds nothing.
    again = authenticated_client.post(f"/api/top-nine/{made['token']}/keep").json()
    assert again["added"] == [] and len(again["existing"]) == 6

    stranger = guest.post("/api/top-nine", json=grid()).json()
    assert authenticated_client.post(f"/api/top-nine/{stranger['token']}/keep").status_code == 403
    assert guest.post(f"/api/top-nine/{made['token']}/keep").status_code == 401


def test_pictures_draw_posters_through_the_allowlist(client, posters):
    made = client.post("/api/top-nine", json=grid(9)).json()
    sizes = {"post.jpg": ((1080, 1440), "image/jpeg"), "story.jpg": ((1080, 1920), "image/jpeg"),
             "card.png": ((1200, 630), "image/png")}
    for name, (size, media) in sizes.items():
        picture = client.get(f"{made['path']}/{name}")
        assert picture.status_code == 200, name
        assert picture.headers["content-type"] == media and picture.headers["x-robots-tag"] == "noindex"
        assert Image.open(BytesIO(picture.content)).size == size
        etag = picture.headers["etag"]
        assert client.get(f"{made['path']}/{name}", headers={"If-None-Match": etag}).status_code == 304
    assert posters and all(call.startswith("https://m.media-amazon.com/") for call in posters)
    download = client.get(f"{made['path']}/post.jpg?download=1")
    assert download.headers["content-disposition"] == f'attachment; filename="top-nine-{top_nine.season_year()}-post.jpg"'
    assert client.get("/top-nine/AAAAAAAAAAAAAAAA/post.jpg").status_code == 404


def test_pictures_work_without_posters_or_with_long_titles():
    tiles = [{"title": f"A very long title number {n} " * 4, "kind": kind, "year": 2026, "creator": "Someone"}
             for n, kind in enumerate(top_nine.KIND_ORDER)]
    data = {"year": 2026, "name": "W" * 40, "theme": "paper", "tiles": tiles}
    for which, size in (("post", (1080, 1440)), ("story", (1080, 1920)), ("card", (1200, 630))):
        body = top_nine_card.RENDERERS[which](data, {})
        assert Image.open(BytesIO(body)).size == size
    sparse = {"year": 2026, "name": "Three", "theme": "night", "tiles": tiles[:3] + [None] * 6}
    assert top_nine_card.RENDERERS["post"](sparse, {})


def test_maker_page_is_indexable_and_links_with_state_are_not(client):
    page = client.get("/top-nine")
    assert page.status_code == 200
    assert '<meta name="robots" content="noindex' not in page.text
    assert 'id="topNine"' in page.text and f'data-year="{top_nine.season_year()}"' in page.text
    assert 'href="/?next=%2Ftop-nine#signup" data-tn-signup' in page.text
    assert "data-tn-mine" not in page.text and "How to pick nine" in page.text
    assert '"@type": "WebApplication"' in page.text or '"@type":"WebApplication"' in page.text
    remix = client.get("/top-nine?from=AAAAAAAAAAAAAAAA&have=0,4,99,x")
    assert 'data-from="AAAAAAAAAAAAAAAA"' in remix.text and 'data-have="0,4"' in remix.text
    assert '<meta name="robots" content="noindex' in remix.text
    assert 'data-from=""' in client.get('/top-nine?from="><b>').text
    assert '<meta name="robots" content="noindex' in client.get("/top-nine?edit=AAAAAAAAAAAAAAAA").text


def test_signed_in_maker_offers_your_grids_and_your_own_titles(authenticated_client, db_session):
    page = authenticated_client.get("/top-nine").text
    assert "data-tn-mine" in page and "data-tn-keep" in page and "data-tn-cta hidden" not in page
    user = db_session.query(models.User).filter_by(username="testuser").one()
    db_session.add(models.Movie(user_id=user.id, title="Sinners", director="Ryan Coogler", year=2025, rating=9.5,
                                watched=True))
    db_session.add(models.Movie(user_id=user.id, title="Meh", year=2025, rating=4, watched=True))
    db_session.commit()
    suggested = authenticated_client.get("/api/top-nine/suggest").json()
    shown = [row["title"] for group in suggested["mine"].values() for row in group]
    assert "Sinners" in shown and "Meh" not in shown
    films = authenticated_client.get("/api/top-nine/suggest?kind=game").json()
    assert all(row["kind"] == "game" for group in films["mine"].values() for row in group)
    assert all(row["kind"] == "game" for row in films["big"])


def test_search_and_suggestions_need_no_account(client):
    results = client.get("/api/top-nine/search?q=dune").json()["results"]
    assert results and results[0]["title"] == "Dune" and results[0]["kind"] == "movie"
    games = client.get("/api/top-nine/search?q=the&kind=game").json()["results"]
    assert games and all(row["kind"] == "game" for row in games)
    suggested = client.get("/api/top-nine/suggest").json()
    assert suggested["year"] == top_nine.season_year() and suggested["mine"] == {"year": [], "loved": []}
    assert len(suggested["big"]) <= top_nine.SUGGEST_LIMIT
    assert client.get("/api/top-nine/art?kind=movie&title=visit%20spam.ru").status_code == 422
    assert client.get("/api/top-nine/art?kind=nope&title=Dune").status_code == 404


def test_season_dates():
    assert top_nine.season_year(date(2026, 12, 31)) == 2026
    assert top_nine.season_year(date(2027, 1, 20)) == 2026
    assert top_nine.season_year(date(2027, 2, 1)) == 2027
    assert not top_nine.promo_season(date(2026, 11, 24))
    assert top_nine.promo_season(date(2026, 11, 25))
    assert top_nine.promo_season(date(2027, 1, 31))
    assert not top_nine.promo_season(date(2027, 2, 1))
    assert not top_nine.promo_season(date(2027, 7, 4))
    assert top_nine.hero_link_html(date(2027, 3, 1)) == "" and top_nine.tools_tile_html(date(2027, 3, 1)) == ""
    assert "Make your 2026 top nine" in top_nine.hero_link_html(date(2027, 1, 5))
    assert "Your 2026 top nine" in top_nine.tools_tile_html(date(2026, 12, 2))


def test_homepage_points_at_the_maker_only_in_season(client, monkeypatch):
    from app import friend_tools
    monkeypatch.setattr(friend_tools, "swap_season", lambda today=None: True)
    monkeypatch.setattr(top_nine, "promo_season", lambda today=None: True)
    home = client.get("/").text
    assert home.count('data-home-tool="top-nine"') == 2
    news = home[home.index('<p class="lp-hero__news">'):]
    news = news[:news.index("</p>")]
    assert 'href="/top-nine"' in news and 'href="/swap"' in news
    monkeypatch.setattr(top_nine, "promo_season", lambda today=None: False)
    home = client.get("/").text
    assert 'data-home-tool="top-nine"' not in home and 'data-home-tool="swap"' in home


def test_year_in_review_points_at_the_maker_for_its_own_year(monkeypatch):
    from app.routers import year_in_review as recap
    monkeypatch.setattr(top_nine, "promo_season", lambda today=None: True)
    monkeypatch.setattr(top_nine, "season_year", lambda today=None: 2026)
    box = recap._top_nine_box(2026)
    assert "Post your 2026 top nine" in box and 'href="/top-nine"' in box
    assert recap._top_nine_box(2025) == ""
    monkeypatch.setattr(top_nine, "promo_season", lambda today=None: False)
    assert recap._top_nine_box(2026) == ""


def test_events_links_and_site_chrome(client):
    names = {name for name, _ in funnel.GUEST}
    server = {"top_nine_made", "top_nine_link_opened", "top_nine_answered", "top_nine_remixed", "top_nine_claimed",
              "top_nine_kept"}
    browser = {"top_nine_started", "top_nine_saved", "top_nine_shared", "top_nine_start_clicked",
               "top_nine_signup_clicked"}
    assert server | browser <= names
    assert browser <= funnel.CLIENT_EVENTS and not server & funnel.CLIENT_EVENTS
    assert site_traffic.clean_path("/top-nine/AbCdEfGhIjKlMnOp") == "/top-nine/(private link)"
    assert "AbCdEfGhIjKlMnOp" not in site_traffic.clean_path("/top-nine/AbCdEfGhIjKlMnOp/post.jpg")
    assert site_traffic.clean_path("/top-nine") == "/top-nine"
    assert "<loc>https://omnitrackr.xyz/top-nine</loc>" in client.get("/sitemap.xml").text
    assert "/top-nine" in client.get("/llms.txt").text
    page = client.get("/tier-list").text
    assert 'href="/top-nine"' in page
    with open("app/static/auth.js", encoding="utf-8") as handle:
        assert "|\\/top-nine|" in handle.read()
