"""Break plan share links (/break/s/<token>): what a link shows and to whom, its two pictures, the
month it lasts, and planning the same days from it (/break?from=<token>)."""
import io
from datetime import date, datetime

import pytest
from PIL import Image

from app import auth, break_plan, break_share, funnel, models
from app.progress import ProgressWrite, save_progress

CHROME = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"}
BOT = {"User-Agent": "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)"}
THANKSGIVING = {"2026-11-26": 60, "2026-11-27": 180, "2026-11-28": 180, "2026-11-29": 180}


def make_user(db, name):
    user = models.User(username=name, email=f"{name}@example.test", hashed_password="unused", is_active=True,
                       is_verified=True)
    db.add(user)
    db.commit()
    return user


def sign_in(client, user):
    client.headers["Authorization"] = "Bearer " + auth.create_access_token({"sub": user.username, "uid": user.id})


def sign_out(client):
    client.headers.pop("Authorization", None)
    client.cookies.clear()


def library(db, user):
    show = models.TVShow(user_id=user.id, title="Severance", year=2022, seasons=1, episodes=9, watched=False,
                         poster_url="https://image.tmdb.org/t/p/w342/severance.jpg")
    film = models.Movie(user_id=user.id, title="The Holdovers", year=2023, watched=False, rating=9.5,
                        review="Cried at the end, a private note", poster_url="https://127.0.0.1:8080/internal.png")
    film2 = models.Movie(user_id=user.id, title="Paddington 2", year=2017, watched=False)
    album = models.Music(user_id=user.id, title="Rumours", artist="Fleetwood Mac", year=1977, listened=False)
    book = models.Book(user_id=user.id, title="Piranesi", author="Susanna Clarke", year=2020, read=False)
    db.add_all([show, film, film2, album, book])
    db.commit()
    save_progress(db, user.id, "tv-shows", show.id, ProgressWrite(unit="episode", position=3, expected_revision=0))
    return {"show": show, "film": film, "film2": film2, "album": album, "book": book}


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(break_plan, "_now", lambda: datetime(2026, 11, 24, 15, 0))


@pytest.fixture
def shared(client, db_session, clock):
    """nova's Thanksgiving plan with its share link on. Returns (owner, rows, plan, path)."""
    owner = make_user(db_session, "nova")
    rows = library(db_session, owner)
    sign_in(client, owner)
    response = client.post("/api/break", json={"starts_on": "2026-11-26", "ends_on": "2026-11-29",
                                               "minutes": THANKSGIVING, "today": "2026-11-24",
                                               "preset": "thanksgiving-2026"})
    assert response.status_code == 201, response.text
    plan = response.json()["plan"]
    path = client.post(f"/api/break/{plan['id']}/share", json={"today": "2026-11-24"}).json()["path"]
    sign_out(client)
    return owner, rows, plan, path


def titles_on(plan):
    return {entry["title"] for day in plan["days"] for entry in day["items"]}


# ---------------------------------------------------------------- the page

def test_the_page_names_nobody_without_a_public_profile_and_never_shows_scores_or_time(client, db_session, shared):
    owner, _rows, _plan, path = shared
    page = client.get(path, headers=CHROME)
    assert page.status_code == 200
    assert "MY BREAK PLAN" in page.text
    assert "nova" not in page.text
    assert "Cried at the end" not in page.text and "9.5" not in page.text
    assert "planned of" not in page.text and "3 hours" not in page.text  # the owner's time per day stays theirs
    assert page.headers["x-robots-tag"].startswith("noindex")
    assert page.headers["cache-control"] == "private, no-store"
    db_session.add(models.PublicProfile(user_id=owner.id, enabled=True))
    db_session.commit()
    named = client.get(path, headers=CHROME).text
    assert "NOVA&#x27;S BREAK PLAN" in named or "NOVA'S BREAK PLAN" in named
    assert 'href="/u/nova"' in named


def test_visitors_get_save_buttons_and_a_way_back_after_signing_up(client, shared):
    _owner, _rows, _plan, path = shared
    page = client.get(path, headers=CHROME).text
    assert 'data-guest-kind="tv" data-guest-slug="severance-2022"' in page
    assert "Plan these days with my list" in page
    assert "next=%2Fbreak%2Fs%2F" in page  # sign-up comes back to this page, which carries on to the planner
    assert "/static/guest-list.js" in page and "data-guest-bar" in page
    assert 'og:image" content="' in page and "/card.png?v=" in page
    # A poster from an address that isn't a poster host stays off the page too.
    assert "127.0.0.1" not in page


def test_opens_count_people_only_and_never_the_owner(client, db_session, shared):
    owner, _rows, plan, path = shared
    client.get(path, headers=BOT)
    client.get(path, headers=CHROME)
    client.get(path, headers=CHROME)
    sign_in(client, owner)
    own = client.get(path, headers=CHROME).text
    assert "This is your link." in own and "Opened 2 times so far." in own
    assert "data-bs-off" in own and "story.png" in own
    assert "data-guest-kind" not in own  # nothing to save from your own plan
    state = client.get("/api/break?today=2026-11-24").json()["plan"]
    assert state["share_opened"] == 2
    assert state["share_story"] == path + "/story.png" and state["share_card"] == path + "/card.png"
    assert state["share_until"] == "2026-12-29"


def test_a_member_with_no_plan_gets_plan_the_same_days(client, db_session, shared):
    _owner, _rows, _plan, path = shared
    remy = make_user(db_session, "remy")
    sign_in(client, remy)
    page = client.get(path, headers=CHROME).text
    assert "Plan my Thanksgiving weekend" in page
    assert f'href="/break?from={path.rsplit("/", 1)[-1]}"' in page
    assert "data-bs-add" in page and 'data-has-plan="false"' in page


def test_a_link_lasts_a_month_after_the_break(client, db_session, shared, monkeypatch):
    _owner, _rows, _plan, path = shared
    monkeypatch.setattr(break_plan, "_now", lambda: datetime(2026, 12, 29, 12, 0))
    assert client.get(path, headers=CHROME).status_code == 200
    monkeypatch.setattr(break_plan, "_now", lambda: datetime(2026, 12, 30, 12, 0))
    assert client.get(path, headers=CHROME).status_code == 404
    assert client.get(f"{path}/card.png").status_code == 404
    assert client.get(f"{path}/story.png").status_code == 404


def test_turning_it_off_and_on_makes_a_new_link(client, db_session, shared):
    owner, _rows, plan, path = shared
    sign_in(client, owner)
    client.delete(f"/api/break/{plan['id']}/share?today=2026-11-24")
    again = client.post(f"/api/break/{plan['id']}/share", json={"today": "2026-11-24"}).json()["path"]
    assert again != path
    sign_out(client)
    assert client.get(path).status_code == 404
    assert client.get(again, headers=CHROME).status_code == 200
    assert client.get("/break/s/<script>").status_code == 404


# ---------------------------------------------------------------- the pictures

class _NoNetwork:
    async def aclose(self):
        return None


@pytest.fixture
def poster_fetches(client, monkeypatch):
    asked = []

    async def fake(_client, url):
        asked.append(url)
        return None

    from app.routers import break_plan as break_router
    from app.routers import tier_list as tier_list_router
    monkeypatch.setattr(tier_list_router, "_poster_bytes", fake)
    monkeypatch.setattr(break_router, "_CARDS", None)
    if getattr(client.app.state, "external_api_client", None) is None:
        monkeypatch.setattr(client.app.state, "external_api_client", _NoNetwork(), raising=False)
    return asked


def test_both_pictures_draw_and_only_ask_for_poster_hosts(client, shared, poster_fetches):
    _owner, _rows, _plan, path = shared
    card = client.get(f"{path}/card.png")
    assert card.status_code == 200 and card.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(card.content)).size == (1200, 630)
    story = client.get(f"{path}/story.png")
    assert story.status_code == 200
    assert Image.open(io.BytesIO(story.content)).size == (1080, 1920)
    assert "omnitrackr-break-plan.png" in story.headers["content-disposition"]
    assert poster_fetches and all(url.startswith("https://image.tmdb.org/") for url in poster_fetches)
    again = client.get(f"{path}/card.png", headers={"If-None-Match": card.headers["etag"]})
    assert again.status_code == 304


def test_the_pictures_cope_with_long_breaks_private_plans_and_ticks():
    long_break = {"by": None, "name": "Christmas to New Year's " * 4, "span": "Thu Dec 24 to Fri Jan 1",
                  "phase": "during", "day_number": 3, "day_count": 16, "titles": 30, "hours": "40 hours",
                  "finished": 2, "done": 5, "stretches": 40,
                  "days": [[0, 1, 2, 3, 4, 5]] * 16, "done_days": [6] * 16,
                  "day_labels": [["THU", "Dec 24"]] * 16,
                  "shown": [[f"Title {n}" * 6, "", "Dec 24 to 28", n % 2 == 0, n == 0, "books"] for n in range(6)]}
    assert Image.open(io.BytesIO(break_share.render_card(long_break, {}))).size == (1200, 630)
    assert Image.open(io.BytesIO(break_share.render_story(long_break, {}))).size == (1080, 1920)
    rows, more = break_share.story_days(long_break)
    assert rows == [2, 3, 4, 5] and more == 10  # from today on, mid-break
    empty = dict(long_break, shown=[], days=[[]] * 4, phase="upcoming")
    break_share.render_card(empty, {})
    break_share.render_story(empty, {})
    assert break_share.meta_line(dict(long_break, phase="after")) == "Got through 5 of 40 · finished 2 titles"


# ---------------------------------------------------------------- planning the same days

def test_the_planner_gets_the_days_and_titles_from_a_link(client, db_session, shared):
    owner, _rows, _plan, path = shared
    token = path.rsplit("/", 1)[-1]
    remy = make_user(db_session, "remy")
    db_session.add(models.Movie(user_id=remy.id, title="paddington 2", year=2017, watched=True))
    db_session.add(models.TVShow(user_id=remy.id, title="Severance", year=2022, watched=False))
    db_session.commit()
    sign_in(client, remy)
    data = client.get(f"/api/break/from/{token}?today=2026-11-24").json()
    assert data["own"] is False and data["by"] is None
    assert data["days"] == {"starts_on": "2026-11-26", "ends_on": "2026-11-29", "preset": "thanksgiving-2026",
                            "name": "Thanksgiving weekend", "light": ["2026-11-26"],
                            "span": "Thu Nov 26 to Sun Nov 29", "day_count": 4}
    mine = {entry["title"]: entry["mine"] for entry in data["titles"]}
    assert mine["Severance"] == "open" and mine["Paddington 2"] == "finished" and mine["Rumours"] is None
    assert all("item_id" not in entry and "id" not in entry for entry in data["titles"])
    sign_in(client, owner)
    assert client.get(f"/api/break/from/{token}?today=2026-11-24").json()["own"] is True
    sign_in(client, remy)
    assert client.get("/api/break/from/nottherealtoken12345?today=2026-11-24").status_code == 404


def test_once_the_break_is_under_way_the_same_days_start_today(shared, db_session):
    _owner, _rows, plan_json, _path = shared
    plan = db_session.get(models.BreakPlan, plan_json["id"])
    friday = break_plan.same_days(plan, date(2026, 11, 27))
    assert friday["starts_on"] == "2026-11-27" and friday["preset"] == "thanksgiving-2026" and friday["light"] == []
    assert break_plan.same_days(plan, date(2026, 11, 30)) is None


def test_a_plan_from_a_link_puts_the_ticked_titles_first_and_on_the_new_list(client, db_session, shared):
    owner, rows, plan, path = shared
    assert {"Rumours", "Paddington 2"} <= titles_on(plan) and "Piranesi" not in titles_on(plan)
    token = path.rsplit("/", 1)[-1]
    remy = make_user(db_session, "remy")
    sign_in(client, remy)
    body = {"starts_on": "2026-11-26", "ends_on": "2026-11-29", "minutes": THANKSGIVING, "today": "2026-11-24",
            "preset": "thanksgiving-2026", "from_token": token,
            "picks": [{"kind": "album", "slug": "rumours-1977"}, {"kind": "movie", "slug": "paddington-2-2017"},
                      # Not on nova's plan (it didn't fit), so the link never showed it.
                      {"kind": "book", "slug": "piranesi-2020"}]}
    response = client.post("/api/break", json=body)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["taken"] == {"picked": 2, "placed": 2}
    assert titles_on(result["plan"]) == {"Rumours", "Paddington 2"}  # remy's library was empty before
    assert db_session.query(models.Book).filter_by(user_id=remy.id).count() == 0
    album = db_session.query(models.Music).filter_by(user_id=remy.id).one()
    assert album.title == "Rumours" and album.rating is None and not album.review
    added = {entry["title"]: entry["added"] for day in result["plan"]["days"] for entry in day["items"]}
    assert added == {"Rumours": True, "Paddington 2": True}
    # "Try another mix" leaves them where they are.
    shuffled = client.post(f"/api/break/{result['plan']['id']}/shuffle", json={"today": "2026-11-24"}).json()["plan"]
    assert {"Rumours", "Paddington 2"} <= titles_on(shuffled)
    # nova's own library is untouched.
    assert db_session.query(models.Music).filter_by(user_id=owner.id).count() == 1


def test_picks_go_ahead_of_what_the_member_was_already_watching(client, db_session, shared):
    _owner, _rows, _plan, path = shared
    token = path.rsplit("/", 1)[-1]
    remy = make_user(db_session, "remy")
    mine = models.TVShow(user_id=remy.id, title="Slow Horses", year=2022, seasons=1, episodes=6, watched=False)
    db_session.add(mine)
    db_session.commit()
    save_progress(db_session, remy.id, "tv-shows", mine.id, ProgressWrite(unit="episode", position=1, expected_revision=0))
    sign_in(client, remy)
    body = {"starts_on": "2026-11-26", "ends_on": "2026-11-26", "minutes": {"2026-11-26": 120}, "today": "2026-11-24",
            "from_token": token, "picks": [{"kind": "movie", "slug": "paddington-2-2017"}]}
    plan = client.post("/api/break", json=body).json()["plan"]
    first = plan["days"][0]["items"][0]
    assert first["title"] == "Paddington 2"


def test_titles_from_a_link_that_stopped_working_are_refused_but_the_days_still_plan(client, db_session, shared):
    owner, _rows, plan, path = shared
    token = path.rsplit("/", 1)[-1]
    sign_in(client, owner)
    client.delete(f"/api/break/{plan['id']}/share?today=2026-11-24")
    remy = make_user(db_session, "remy")
    db_session.add(models.Movie(user_id=remy.id, title="Arrival", year=2016, watched=False))
    db_session.commit()
    sign_in(client, remy)
    body = {"starts_on": "2026-11-26", "ends_on": "2026-11-29", "minutes": THANKSGIVING, "today": "2026-11-24",
            "from_token": token, "picks": [{"kind": "album", "slug": "rumours-1977"}]}
    refused = client.post("/api/break", json=body)
    assert refused.status_code == 404 and "isn't shared anymore" in refused.json()["detail"]
    assert db_session.query(models.Music).filter_by(user_id=remy.id).count() == 0
    body["picks"] = []
    made = client.post("/api/break", json=body)
    assert made.status_code == 201 and "taken" not in made.json()


def test_hidden_and_private_shelves_stay_off_the_link_and_the_planner(client, db_session, shared):
    owner, _rows, _plan, path = shared
    owner.music_private = True
    db_session.commit()
    token = path.rsplit("/", 1)[-1]
    page = client.get(path, headers=CHROME).text
    assert "Rumours" not in page and "keeps private" in page
    remy = make_user(db_session, "remy")
    sign_in(client, remy)
    titles = {entry["title"] for entry in client.get(f"/api/break/from/{token}?today=2026-11-24").json()["titles"]}
    assert "Rumours" not in titles
    body = {"starts_on": "2026-11-26", "ends_on": "2026-11-29", "minutes": THANKSGIVING, "today": "2026-11-24",
            "from_token": token, "picks": [{"kind": "album", "slug": "rumours-1977"}]}
    result = client.post("/api/break", json=body).json()
    assert result["taken"] == {"picked": 0, "placed": 0}
    assert db_session.query(models.Music).filter_by(user_id=remy.id).count() == 0


def test_new_funnel_events_are_known():
    for event in ("break_from_link_started", "break_from_link_created"):
        assert event in funnel.SERVER_EVENTS
    for event in ("break_link_shared", "break_story_saved", "break_title_saved", "break_same_days_clicked"):
        assert event in funnel.CLIENT_EVENTS and event in funnel.SERVER_EVENTS
