"""Share links for a Rankings top ten: /ranked/<token>, its pictures, and keeping a ranking made there."""
import re
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app import auth, models, ranking_shares
from app.site_traffic import RECORDER, mask_private_link

ROOT = Path(__file__).resolve().parents[1]
CHROME = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"}
BOT = {"User-Agent": "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)"}


@pytest.fixture(autouse=True)
def counting(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
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


TITLES = ["Alien", "Arrival", "Brazil", "Casablanca", "Dune", "Fargo", "Heat", "Jaws", "Klute", "Laura", "Memento", "Nope"]


def ranked_films(db, user, titles=TITLES, rating=8.0):
    rows = [models.Movie(title=title, year=1970 + index, director=f"Director {index}", watched=True, rating=rating + index / 10,
                         user_id=user.id, poster_url=f"https://image.tmdb.org/t/p/w342/{index}.jpg")
            for index, title in enumerate(titles)]
    db.add_all(rows)
    db.commit()
    db.add(models.Ranking(user_id=user.id, category="movies", ranked="[" + ",".join(str(row.id) for row in rows) + "]"))
    db.commit()
    return rows


def share_on(client, user, category="movies"):
    return client.post("/api/rankings/share", headers=headers(user), json={"category": category})


def shared(client, db, name="nova", titles=TITLES):
    user = member(db, name)
    ranked_films(db, user, titles)
    response = share_on(client, user)
    assert response.status_code == 200, response.text
    return user, response.json()["share"]["path"]


# ---------------------------------------------------------------- making and ending a link

def test_a_link_needs_three_ranked_titles(client, db_session):
    user = member(db_session)
    ranked_films(db_session, user, ["Alien", "Arrival"])
    response = share_on(client, user)
    assert response.status_code == 409
    assert "at least three" in response.json()["detail"]
    assert db_session.query(models.RankingShare).count() == 0


def test_a_link_is_made_once_per_format_and_counted(client, db_session):
    user, path = shared(client, db_session)
    assert re.fullmatch(r"/ranked/[A-Za-z0-9_-]{16,32}", path)
    again = share_on(client, user).json()["share"]
    assert again["path"] == path
    assert db_session.query(models.RankingShare).count() == 1
    assert counted("rank", "link_on") == 1
    assert counted("funnel", "rank_link_created") == 2  # each press, the second returns the same link
    detail = client.get("/api/rankings?category=movies", headers=headers(user)).json()["detail"]
    assert detail["share"]["path"] == path and detail["share"]["allowed"] is True


def test_no_link_for_a_private_or_hidden_shelf(client, db_session):
    user = member(db_session)
    ranked_films(db_session, user)
    user.movies_private = True
    db_session.commit()
    response = share_on(client, user)
    assert response.status_code == 409 and "private" in response.json()["detail"]
    detail = client.get("/api/rankings?category=movies", headers=headers(user)).json()["detail"]
    assert detail["share"]["allowed"] is False


def test_turning_a_link_off_ends_it(client, db_session):
    user, path = shared(client, db_session)
    response = client.post("/api/rankings/share/off", headers=headers(user), json={"category": "movies"})
    assert response.status_code == 200 and response.json()["share"]["path"] is None
    assert client.get(path, headers=CHROME).status_code == 404
    assert counted("rank", "link_off") == 1


# ---------------------------------------------------------------- the page

def test_the_page_shows_the_top_ten_in_order_without_scores(client, db_session):
    _, path = shared(client, db_session)
    response = client.get(path, headers=CHROME)
    assert response.status_code == 200
    assert "noindex" in response.headers["X-Robots-Tag"]
    assert response.headers["Cache-Control"].startswith("private")
    html = response.text
    places = [int(value) for value in re.findall(r'data-rk-item data-title="[^"]+" data-position="(\d+)"', html)]
    assert places == list(range(1, 11))
    assert html.index('data-title="Alien"') < html.index('data-title="Laura"')
    assert 'data-title="Memento"' not in html and "2 more ranked below these." in html
    assert "8.1" not in html and "scored" not in html  # scores never shown
    assert "My top 10 films" in html  # no public profile, so no name
    assert f'content="https://omnitrackr.xyz{path}/card.png?v=' in html
    assert '<meta name="robots" content="noindex, follow">' in html
    assert 'href="/?next=%2Franked%2F' in html  # sign-up comes back here


def test_the_page_names_a_member_who_shows_a_public_profile(client, db_session):
    user, path = shared(client, db_session)
    db_session.add(models.PublicProfile(user_id=user.id, enabled=True))
    db_session.commit()
    html = client.get(path, headers=CHROME).text
    assert "nova&#x27;s top 10 films" in html or "nova's top 10 films" in html
    assert 'href="/u/nova"' in html


@pytest.mark.parametrize("change", ["private", "hidden", "closed", "too_few"])
def test_the_link_stops_showing_anything_when_it_should(client, db_session, change):
    user, path = shared(client, db_session)
    if change == "private":
        user.movies_private = True
    elif change == "hidden":
        user.movies_visible = False
    elif change == "closed":
        user.is_active = False
    else:
        row = db_session.query(models.Ranking).filter_by(user_id=user.id).one()
        row.ranked = row.ranked.split(",")[0] + "]"
    db_session.commit()
    assert client.get(path, headers=CHROME).status_code == 404
    assert client.get(f"{path}/card.png", headers=CHROME).status_code == 404
    assert client.get(f"{path}/story.png", headers=CHROME).status_code == 404


def test_opens_count_for_people_not_bots_or_the_owner(client, db_session):
    user, path = shared(client, db_session)
    client.get(path, headers=BOT)
    client.get(path, headers={**CHROME, "Sec-Purpose": "prefetch"})
    client.get(path, headers=headers(user))
    share = db_session.query(models.RankingShare).one()
    db_session.refresh(share)
    assert share.opened == 0
    owner_page = client.get(path, headers=headers(user)).text
    assert "This is your link." in owner_page and "data-rk-story" in owner_page
    client.get(path, headers=CHROME)
    db_session.refresh(share)
    assert share.opened == 1
    assert counted("funnel", "rank_link_opened") == 1
    assert counted("rank", "link_opened") == 1
    assert "Opened 1 time so far." in client.get(path, headers=headers(user)).text


def test_an_unknown_or_malformed_token_is_not_found(client):
    assert client.get("/ranked/abcdefghijklmnop", headers=CHROME).status_code == 404
    assert client.get("/ranked/short", headers=CHROME).status_code == 404
    assert client.get("/ranked/abcdefghijklmnop/card.png", headers=CHROME).status_code == 404


# ---------------------------------------------------------------- the pictures

def test_the_card_and_the_story_picture(client, db_session):
    _, path = shared(client, db_session)
    card = client.get(f"{path}/card.png", headers=CHROME)
    assert card.status_code == 200 and card.headers["content-type"] == "image/png"
    assert Image.open(BytesIO(card.content)).size == (1200, 630)
    assert client.get(f"{path}/card.png", headers={**CHROME, "If-None-Match": card.headers["etag"]}).status_code == 304
    story = client.get(f"{path}/story.png", headers=CHROME)
    assert story.status_code == 200 and Image.open(BytesIO(story.content)).size == (1080, 1920)
    assert story.headers["etag"] != card.headers["etag"]


def test_the_pictures_draw_with_posters_and_long_names():
    data = {"category": "books", "label": "Books", "noun": "book", "nouns": "books", "verb": "read", "total": 240,
            "by": "a" * 40, "items": []}
    poster = BytesIO()
    Image.new("RGB", (300, 450), (200, 40, 40)).save(poster, format="JPEG")
    for place in range(1, 11):
        data["items"].append({"position": place, "title": "A very long title that keeps going " * 3, "year": 1990 + place,
                              "creator": "Somebody With A Long Name", "image": "https://img.example/x.jpg"})
    posters = {place: poster.getvalue() for place in range(1, 11, 2)}
    posters[2] = b"not an image"
    assert Image.open(BytesIO(ranking_shares.render_card(data, posters))).size == (1200, 630)
    assert Image.open(BytesIO(ranking_shares.render_story(data, posters))).size == (1080, 1920)
    data["items"] = data["items"][:3]
    assert Image.open(BytesIO(ranking_shares.render_story(data, {}))).size == (1080, 1920)


# ---------------------------------------------------------------- keeping a ranking made on the page

def take(client, user, path, titles):
    return client.post("/api/rankings/take", headers=headers(user), json={"token": path.rsplit("/", 1)[1], "titles": titles})


def test_a_new_member_keeps_their_order_as_a_ranking(client, db_session):
    _, path = shared(client, db_session)
    newcomer = member(db_session, "sam")
    response = take(client, newcomer, path, ["Jaws", "Alien", "Heat"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["added"] == 3 and body["ranked"] is True and body["count"] == 3
    films = db_session.query(models.Movie).filter_by(user_id=newcomer.id).all()
    assert sorted(film.title for film in films) == ["Alien", "Heat", "Jaws"]
    assert all(film.watched for film in films) and all(film.rating is None for film in films)
    alien = next(film for film in films if film.title == "Alien")
    assert alien.year == 1970 and alien.director == "Director 0"
    ranked = client.get("/api/rankings?category=movies", headers=headers(newcomer)).json()["detail"]["ranked"]
    assert [item["title"] for item in ranked] == ["Jaws", "Alien", "Heat"]
    assert counted("funnel", "rank_take_saved") == 1 and counted("rank", "taken") == 1


def test_a_member_with_a_ranking_gets_the_titles_waiting(client, db_session):
    _, path = shared(client, db_session)
    viewer = member(db_session, "kit")
    ranked_films(db_session, viewer, ["Zodiac", "Yojimbo", "Xanadu"])
    db_session.add(models.Movie(title="Fargo", year=1975, watched=False, rating=6.0, review="Not yet.", user_id=viewer.id))
    db_session.commit()
    body = take(client, viewer, path, ["Fargo", "Dune", "Brazil"]).json()
    assert body["ranked"] is False and body["added"] == 2 and body["existing"] == 1 and body["unfinished"] == 1
    assert body["queued"] == 2 and body["already_ranked"] == 0
    fargo = db_session.query(models.Movie).filter_by(user_id=viewer.id, title="Fargo").one()
    assert fargo.watched is False and fargo.rating == 6.0 and fargo.review == "Not yet."  # left exactly as it was
    detail = client.get("/api/rankings?category=movies", headers=headers(viewer)).json()["detail"]
    assert [item["title"] for item in detail["ranked"]] == ["Zodiac", "Yojimbo", "Xanadu"]
    assert {"Dune", "Brazil"} <= {item["title"] for item in detail["waiting"]}
    again = take(client, viewer, path, ["Zodiac", "Dune", "Brazil"]).json()  # Zodiac isn't on the list
    assert again["added"] == 0 and again["existing"] == 2 and again["queued"] == 2


def test_only_titles_on_the_list_count(client, db_session):
    _, path = shared(client, db_session)
    viewer = member(db_session, "kit")
    response = take(client, viewer, path, ["Alien", "Something Else", "Memento"])  # Memento is #11, not on the page
    assert response.status_code == 409
    assert db_session.query(models.Movie).filter_by(user_id=viewer.id).count() == 0
    body = take(client, viewer, path, ["alien ", "Something Else", "ARRIVAL"]).json()
    assert body["added"] == 2


def test_the_owner_cannot_take_their_own_list_and_a_dead_link_says_so(client, db_session):
    user, path = shared(client, db_session)
    assert take(client, user, path, ["Alien", "Arrival"]).status_code == 409
    viewer = member(db_session, "kit")
    client.post("/api/rankings/share/off", headers=headers(user), json={"category": "movies"})
    response = take(client, viewer, path, ["Alien", "Arrival"])
    assert response.status_code == 404 and "anymore" in response.json()["detail"]


def test_take_needs_an_account(client, db_session):
    _, path = shared(client, db_session)
    response = client.post("/api/rankings/take", headers=CHROME, json={"token": path.rsplit("/", 1)[1], "titles": ["Alien", "Arrival"]})
    assert response.status_code == 401


# ---------------------------------------------------------------- the rest of the site

def test_a_title_landing_in_the_top_ten_carries_the_link(client, db_session):
    user, path = shared(client, db_session)
    db_session.add(models.Movie(title="Ran", year=1985, watched=True, user_id=user.id))
    db_session.commit()
    ran = db_session.query(models.Movie).filter_by(user_id=user.id, title="Ran").one()
    response = client.post("/api/rankings/place", headers=headers(user), json={"category": "movies", "item_id": ran.id})
    question = response.json()["question"]
    while True:
        body = client.post("/api/rankings/answer", headers=headers(user), json={
            "category": "movies", "placing_id": question["placing"]["id"], "against_id": question["against"]["id"],
            "choice": "placing"}).json()
        if "placed" in body:
            break
        question = body["question"]
    assert body["placed"]["position"] == 1 and body["placed"]["shared"] == path


def test_share_paths_are_private_links_in_site_stats():
    assert mask_private_link("/ranked/abcdefghijklmnop") == "/ranked/(private link)"


def test_sign_up_can_come_back_to_a_shared_top_ten():
    script = (ROOT / "app/static/auth.js").read_text(encoding="utf-8")
    assert r"/^\/ranked\/[A-Za-z0-9_-]{16,32}$/" in script


def test_every_new_route_is_rate_limited():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    block = main[main.index("from .routers import rankings as rankings_router"):main.index("app.include_router(ranked_share_router.router)")]
    assert '"/api/rankings/take"' in block and '"/api/rankings/share"' in block and '"/api/rankings/share/off"' in block
    assert 'path.endswith(".png")' in block and 'limiter.limit("30/minute")' in block
