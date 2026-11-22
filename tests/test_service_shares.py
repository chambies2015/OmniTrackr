"""Share links for "On your services": /on-my-services/<token>, its pictures, and what the page leaves out."""
import json
import re
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app import auth, models, service_shares, streaming_services, title_pages, where_to_watch
from app.site_traffic import RECORDER, mask_private_link

ROOT = Path(__file__).resolve().parents[1]
CHROME = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"}
BOT = {"User-Agent": "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)"}


@pytest.fixture(autouse=True)
def counting(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    monkeypatch.setenv("TMDB_API_KEY", "k")
    monkeypatch.setenv("WATCH_REGION", "US")
    RECORDER._pending.clear()
    yield
    RECORDER._pending.clear()


def counted(kind, key):
    return sum(amount for (_, k, name), amount in RECORDER._pending.items() if k == kind and name == key)


def member(db, name="nova"):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=True, is_active=True, created_at=datetime.utcnow() - timedelta(days=60))
    db.add(user)
    db.commit()
    return user


def headers(user):
    return {"Authorization": f"Bearer {auth.create_user_access_token(user)}", **CHROME}


def where(*streams):
    groups = [{"label": "Stream", "providers": [{"name": name} for name in streams]}] if streams else []
    groups.append({"label": "Rent", "providers": [{"name": "Apple TV"}]})
    return {"v": 1, "groups": groups, "justwatch": True, "region": "US", "fetched": "2026-11-22"}


def cache(db, kind, title, year, data):
    key = where_to_watch.cache_key(kind, title_pages.normalize(title), year)
    db.add(models.TitleMetadata(key=key, status="ok", data=json.dumps(data), fetched_at=datetime.utcnow()))
    db.commit()
    return key


# title, model, year, streams on
SHELF = [
    ("Dune: Part Two", models.Movie, 2024, ("Max",)),
    ("Past Lives", models.Movie, 2023, ("Netflix", "Hulu")),
    ("Severance", models.TVShow, 2022, ("Apple TV Plus",)),
    ("Frieren", models.Anime, 2023, ("Crunchyroll", "Netflix")),
    ("Aftersun", models.Movie, 2022, ("Mubi",)),
]


def stocked(client, db, name="nova", services=("hbomax", "netflix", "crunchyroll", "apple")):
    user = member(db, name)
    added = datetime.utcnow() - timedelta(days=30)
    for index, (title, model, year, streams) in enumerate(SHELF):
        db.add(model(title=title, year=year, watched=False, user_id=user.id, added_at=added + timedelta(minutes=index),
                     poster_url=f"https://m.media-amazon.com/images/M/{index}.jpg"))
        cache(db, {models.Movie: "movie", models.TVShow: "tv", models.Anime: "anime"}[model], title, year, where(*streams))
    db.add(models.Movie(title="Arrival", year=2016, watched=True, user_id=user.id, poster_url=None))
    cache(db, "movie", "Arrival", 2016, where("Netflix"))
    db.commit()
    response = client.put("/api/streaming", json={"services": list(services)}, headers=headers(user))
    assert response.status_code == 200, response.text
    return user


def share_on(client, user):
    return client.post("/api/streaming/share", headers=headers(user))


def shared(client, db, name="nova"):
    user = stocked(client, db, name)
    response = share_on(client, user)
    assert response.status_code == 200, response.text
    return user, response.json()["share"]["path"]


# ---------------------------------------------------------------- making and ending a link

def test_the_home_card_offers_a_link_and_makes_one_once(client, db_session):
    user = stocked(client, db_session)
    card = client.get("/api/streaming", headers=headers(user)).json()["card"]
    assert card["share"] == {"path": None, "opened": 0, "allowed": True, "reason": None, "count": 4, "story": None}
    user_path = share_on(client, user).json()["share"]["path"]
    assert re.fullmatch(r"/on-my-services/[A-Za-z0-9_-]{16,32}", user_path)
    again = share_on(client, user).json()["share"]
    assert again["path"] == user_path and again["story"] == f"{user_path}/story.png"
    assert db_session.query(models.ServiceShare).count() == 1
    assert counted("stream", "link_on") == 1
    assert counted("funnel", "svc_link_created") == 2
    assert client.get("/api/streaming", headers=headers(user)).json()["card"]["share"]["path"] == user_path


def test_no_link_without_services_or_with_fewer_than_three_titles(client, db_session):
    user = stocked(client, db_session, services=("hbomax", "apple"))
    response = share_on(client, user)
    assert response.status_code == 409 and "at least three" in response.json()["detail"]
    client.put("/api/streaming", json={"services": []}, headers=headers(user))
    response = share_on(client, user)
    assert response.status_code == 409 and "Pick your streaming services" in response.json()["detail"]
    assert db_session.query(models.ServiceShare).count() == 0


def test_turning_a_link_off_ends_it(client, db_session):
    user, path = shared(client, db_session)
    response = client.post("/api/streaming/share/off", headers=headers(user))
    assert response.status_code == 200 and response.json()["share"]["path"] is None
    assert client.get(path, headers=CHROME).status_code == 404
    assert client.get(f"{path}/card.png", headers=CHROME).status_code == 404
    assert counted("stream", "link_off") == 1


def test_signed_out_share_calls_are_refused(client):
    assert client.post("/api/streaming/share").status_code in (401, 403)
    assert client.post("/api/streaming/share/off").status_code in (401, 403)


# ---------------------------------------------------------------- the page

def test_the_page_lists_unfinished_titles_on_the_members_services(client, db_session):
    _, path = shared(client, db_session)
    response = client.get(path, headers=CHROME)
    assert response.status_code == 200
    assert "noindex" in response.headers["X-Robots-Tag"]
    assert response.headers["Cache-Control"].startswith("private")
    html = response.text
    titles = re.findall(r'<h3 class="svc-tile__name"><a href="[^"]+">([^<]+)</a>', html)
    # Aftersun is only on MUBI, which they don't have; Arrival is finished.
    assert sorted(titles) == ["Dune: Part Two", "Frieren", "Past Lives", "Severance"]
    assert "Arrival" not in html and "Aftersun" not in html
    # Every service a title is on, for matching a visitor's own, but only the member's as pills.
    assert 'data-mine="netflix" data-all="netflix hulu"' in html
    assert '<span class="svc-pill" data-service="hulu">' not in html
    # Hulu shows in the visitor's chips because Past Lives streams there; MUBI too, from nothing shown.
    assert 'value="hulu"' in html and 'value="mubi"' not in html
    assert "My watchlist, streaming now" in html
    assert 'og:image" content="https://omnitrackr.xyz/on-my-services/' in html
    # Guests save into the browser list that moves into a new account.
    assert 'data-guest-kind="movie" data-guest-slug="past-lives-2023"' in html
    assert "/static/guest-list.js" in html and "data-guest-bar" in html
    assert counted("stream", "link_opened") == 1
    assert counted("funnel", "svc_link_opened") == 1


def test_scores_notes_and_private_shelves_stay_off_the_page(client, db_session):
    user = stocked(client, db_session)
    movie = db_session.query(models.Movie).filter_by(user_id=user.id, title="Past Lives").first()
    movie.rating = 9.5
    movie.review = "My secret thoughts on this one"
    user.tv_shows_private = True
    db_session.commit()
    path = share_on(client, user).json()["share"]["path"]
    html = client.get(path, headers=CHROME).text
    assert "Severance" not in html
    assert "My secret thoughts" not in html and "9.5" not in html
    # Making two shelves private leaves two titles, under the minimum, so the link pauses.
    user.anime_private = True
    db_session.commit()
    assert client.get(path, headers=CHROME).status_code == 404
    share = client.get("/api/streaming", headers=headers(user)).json()["card"]["share"]
    assert share["path"] == path and share["allowed"] is False and share["reason"] == "few"


def test_the_byline_needs_a_public_profile(client, db_session):
    user, path = shared(client, db_session)
    db_session.add(models.PublicProfile(user_id=user.id, enabled=True))
    db_session.commit()
    html = client.get(path, headers=CHROME).text
    assert "nova&#x27;s watchlist, streaming now" in html or "nova's watchlist, streaming now" in html


def test_owner_sees_their_tools_and_opens_are_not_counted(client, db_session):
    user, path = shared(client, db_session)
    html = client.get(path, headers=headers(user)).text
    assert "data-svc-owner" in html and "data-svc-story" in html
    assert "svcMatch" not in html and "data-guest-kind" not in html
    client.get(path, headers=BOT)
    assert counted("stream", "link_opened") == 0
    assert db_session.query(models.ServiceShare).first().opened == 0


def test_members_get_an_add_button_instead_of_the_guest_list(client, db_session):
    _, path = shared(client, db_session)
    friend = member(db_session, "ruth")
    html = client.get(path, headers=headers(friend)).text
    assert 'data-svc-add data-kind="movie" data-slug="past-lives-2023"' in html
    assert "data-guest-kind" not in html and "/static/guest-list.js" not in html
    # The add button's call finds the title through the sharer's shelf.
    response = client.post("/api/titles/movie/past-lives-2023/add", headers=headers(friend))
    assert response.status_code == 200 and response.json()["state"] == "created"


def test_a_closed_account_or_a_bad_token_is_not_found(client, db_session):
    user, path = shared(client, db_session)
    assert client.get("/on-my-services/short", headers=CHROME).status_code == 404
    assert client.get("/on-my-services/" + "x" * 20, headers=CHROME).status_code == 404
    user.is_active = False
    db_session.commit()
    assert client.get(path, headers=CHROME).status_code == 404


def test_member_text_cannot_break_out_of_the_page(client, db_session):
    user = stocked(client, db_session)
    title = '<script>alert(1)</script> {{CONTENT}}'
    db_session.add(models.Movie(title=title, year=2020, watched=False, user_id=user.id,
                                poster_url='https://image.tmdb.org/t/p/w342/x.jpg" onerror="alert(1)'))
    cache(db_session, "movie", title, 2020, where("Netflix"))
    db_session.commit()
    path = share_on(client, user).json()["share"]["path"]
    html = client.get(path, headers=CHROME).text
    assert "<script>alert(1)</script>" not in html
    assert 'onerror="alert(1)' not in html
    assert html.count("<article") == 1


def test_new_arrivals_come_first_with_a_badge(client, db_session):
    user = stocked(client, db_session)
    key = where_to_watch.cache_key("tv", title_pages.normalize("Severance"), 2022)
    row = db_session.query(models.ServiceSighting).filter_by(title_key=key, service="apple").first()
    row.baseline = False
    row.first_seen_at = datetime.utcnow() - timedelta(days=2)
    db_session.commit()
    path = share_on(client, user).json()["share"]["path"]
    html = client.get(path, headers=CHROME).text
    titles = re.findall(r'<h3 class="svc-tile__name"><a href="[^"]+">([^<]+)</a>', html)
    assert titles[0] == "Severance"
    assert '<span class="svc-pill svc-pill--new" data-service="apple">New on Apple TV</span>' in html
    assert "1 arrived in the last two weeks" in html


def test_site_traffic_masks_the_link():
    assert mask_private_link("/on-my-services/abcdefghijklmnop") == mask_private_link("/on-my-services/zyxwvutsrqponmlk")


# ---------------------------------------------------------------- the pictures

def test_card_and_story_pictures(client, db_session):
    _, path = shared(client, db_session)
    card = client.get(f"{path}/card.png", headers=CHROME)
    assert card.status_code == 200 and card.headers["content-type"] == "image/png"
    assert Image.open(BytesIO(card.content)).size == (1200, 630)
    assert card.headers["Cache-Control"] == "public, max-age=600"
    again = client.get(f"{path}/card.png", headers={**CHROME, "If-None-Match": card.headers["ETag"]})
    assert again.status_code == 304
    story = client.get(f"{path}/story.png", headers=CHROME)
    assert story.status_code == 200 and Image.open(BytesIO(story.content)).size == (1080, 1920)


def test_pictures_only_fetch_posters_from_the_usual_hosts(client, db_session, monkeypatch):
    user = stocked(client, db_session)
    movie = db_session.query(models.Movie).filter_by(user_id=user.id, title="Past Lives").first()
    movie.poster_url = "https://127.0.0.1:8080/internal.png"
    db_session.commit()
    path = share_on(client, user).json()["share"]["path"]
    fetched = []

    async def fake(client_, url):
        fetched.append(url)
        return None

    from app.routers import services_share, tier_list
    monkeypatch.setattr(tier_list, "_poster_bytes", fake)
    monkeypatch.setattr(services_share, "_CARDS", None)
    if getattr(client.app.state, "external_api_client", None) is None:
        monkeypatch.setattr(client.app.state, "external_api_client", _NoNetwork(), raising=False)
    response = client.get(f"{path}/card.png", headers=CHROME)
    assert response.status_code == 200
    assert fetched and all("127.0.0.1" not in url for url in fetched)
    assert any(url.startswith("https://m.media-amazon.com/") for url in fetched)


class _NoNetwork:
    async def aclose(self):
        return None


def test_render_handles_letters_long_names_and_many_services():
    data = {
        "items": [{"category": "movies", "title": "A" * 300, "services": [{"id": "netflix", "name": "Netflix", "new": True}]}]
        + [{"category": "anime", "title": f"Show {n}", "services": [{"id": "hulu", "name": "Hulu", "new": False},
                                                                    {"id": "crunchyroll", "name": "Crunchyroll", "new": False}]}
           for n in range(8)],
        "total": 40, "new": 1, "by": "someone-with-a-very-long-name-indeed", "kinds": ["movies", "anime"],
        "services": [{"id": s, "name": streaming_services.NAMES[s], "count": 1} for s in ("netflix", "hulu", "crunchyroll", "prime")],
    }
    assert Image.open(BytesIO(service_shares.render_card(data, {}))).size == (1200, 630)
    assert Image.open(BytesIO(service_shares.render_story(data, {1: b"not an image"}))).size == (1080, 1920)
    assert service_shares.service_names(data) == "Netflix, Hulu and 2 more"


# ---------------------------------------------------------------- wiring

def test_page_and_home_card_assets_are_wired():
    index = (ROOT / "app/templates/index.html").read_text()
    assert 'id="onYourServicesShare"' in index and 'id="onYourServicesPrivacy"' in index
    script = (ROOT / "app/static/streaming.js").read_text()
    assert "/api/streaming/share" in script and "/api/streaming/share/off" in script
    assert (ROOT / "app/static/services-share.js").exists() and (ROOT / "app/static/services-share.css").exists()
    from app.routers import discover
    assert ("/on-my-services", "") in discover.NAV_SECTIONS
    from app import funnel
    for name in ("svc_link_shared", "svc_services_ticked", "svc_title_saved", "svc_signup_clicked"):
        assert name in funnel.CLIENT_EVENTS
    assert {"svc_link_created", "svc_link_opened"} <= funnel.SERVER_EVENTS


def test_account_removal_takes_the_link(client, db_session):
    _, path = shared(client, db_session)
    table = models.ServiceShare.__table__
    assert any(fk.column.table is models.User.__table__ and fk.ondelete == "CASCADE" for fk in table.foreign_keys)


def test_tmdb_posters_are_allowed_on_this_exact_host_over_https_only():
    from app import tier_list
    assert tier_list.image_allowed("https://image.tmdb.org/t/p/w342/abc.jpg")
    assert not tier_list.image_allowed("http://image.tmdb.org/t/p/w342/abc.jpg")
    assert not tier_list.image_allowed("https://evil.image.tmdb.org/t/p/w342/abc.jpg")
    assert not tier_list.image_allowed("https://image.tmdb.org.evil.com/abc.jpg")
    assert not tier_list.image_allowed("https://tmdb.org/abc.jpg")
    assert not tier_list.image_allowed("https://image.tmdb.org:8443/abc.jpg")
    assert not tier_list.image_allowed("https://user@image.tmdb.org/abc.jpg")
