"""The start page (/start): where new members land after their first log-in, aiming for five titles."""
from datetime import datetime, timedelta

import pytest

from app import funnel, models, start_flow, title_search
from tests.test_title_pages import add_movie, member


def _me(db):
    return db.query(models.User).filter_by(username="testuser").one()


def _register(client, db, name="newbie", created=None):
    response = client.post("/auth/register", json={"email": f"{name}@example.com", "username": name, "password": "testpassword123"})
    assert response.status_code == 201
    user = db.query(models.User).filter_by(username=name).one()
    user.is_verified = True
    user.verification_token = None
    if created is not None:
        user.created_at = created
    db.commit()
    return user


def _login(client, name="newbie"):
    return client.post("/auth/login", data={"username": name, "password": "testpassword123"})


@pytest.fixture
def events(monkeypatch):
    seen = []
    monkeypatch.setattr(funnel, "record", lambda event, request=None: seen.append(event) or True)
    return seen


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


# ---------------------------------------------------------------- who lands there

def test_first_log_in_opens_the_start_page_once(client, db_session):
    _register(client, db_session)
    login = _login(client)
    assert login.status_code == 200
    assert start_flow.COOKIE in login.cookies

    first = client.get("/", follow_redirects=False)
    assert first.status_code == 303 and first.headers["location"] == "/start"
    page = client.get("/start")
    assert page.status_code == 200
    assert 'id="startFlow"' in page.text and page.headers["x-robots-tag"] == "noindex, follow"
    assert start_flow.COOKIE not in client.cookies
    assert client.get("/", follow_redirects=False).status_code == 200


def test_links_with_a_destination_are_not_redirected(client, db_session):
    _register(client, db_session)
    _login(client)
    assert client.get("/?start=import", follow_redirects=False).status_code == 200
    assert client.get("/?library_category=movies&library_item=1", follow_redirects=False).status_code == 200


def test_existing_members_and_later_log_ins_are_left_alone(client, db_session):
    _register(client, db_session, "oldtimer", created=start_flow.LAUNCH - timedelta(days=40))
    assert start_flow.COOKIE not in _login(client, "oldtimer").cookies
    client.cookies.clear()
    _register(client, db_session, "second")
    _login(client, "second")
    client.cookies.clear()
    assert start_flow.COOKIE not in _login(client, "second").cookies


def test_signed_out_visitors_are_sent_to_log_in_and_back(client):
    response = client.get("/start", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/?next=/start#landing-auth"


def test_dashboard_offers_the_start_page(authenticated_client):
    assert 'href="/start"' in authenticated_client.get("/").text


# ---------------------------------------------------------------- the deck

def test_deck_puts_popular_titles_first_and_skips_what_the_member_has(authenticated_client, db_session):
    me = _me(db_session)
    for name in ("a", "b", "c"):
        add_movie(db_session, member(db_session, name), title="Arrival", year=2016, director="Denis Villeneuve")
    add_movie(db_session, member(db_session, "d"), title="Heat", year=1995)  # only one member: not popular
    add_movie(db_session, me, title="Interstellar", year=2014)
    db_session.commit()
    cards = authenticated_client.get("/api/start/deck?kinds=movie").json()["cards"]
    ids = [card["id"] for card in cards]
    assert ids[0] == "movie/arrival-2016" and cards[0]["members"] == 3
    assert "movie/interstellar-2014" not in ids and "movie/heat-1995" not in ids
    assert "movie/the-dark-knight-2008" in ids
    assert len(ids) == len(set(ids))


def test_deck_mixes_the_chosen_formats(authenticated_client):
    cards = authenticated_client.get("/api/start/deck?kinds=manga,podcast,nonsense").json()["cards"]
    assert {card["kind"] for card in cards} == {"manga", "podcast"}
    assert [card["kind"] for card in cards[:4]] == ["manga", "podcast", "manga", "podcast"]
    default = authenticated_client.get("/api/start/deck").json()["cards"]
    assert {card["kind"] for card in default} == set(start_flow.DEFAULT_KINDS)


def test_every_format_has_enough_well_known_titles():
    for kind in start_flow.FORMATS:
        rows = start_flow.WELL_KNOWN[kind]
        assert len(rows) >= 15, kind
        slugs = [start_flow._well_known_entry(kind, row)["slug"] for row in rows]
        assert len(slugs) == len(set(slugs)), kind


# ---------------------------------------------------------------- saving

def test_seen_it_saves_a_finished_title_and_counts_toward_five(authenticated_client, db_session, events):
    response = authenticated_client.post("/api/start/save", json={"id": "manga/berserk-1989", "answer": "seen"})
    assert response.status_code == 200
    data = response.json()
    assert (data["state"], data["category"], data["seen"], data["total"]) == ("created", "manga", True, 1)
    manga = db_session.query(models.Manga).one()
    assert (manga.title, manga.author, manga.year, manga.read) == ("Berserk", "Kentaro Miura", 1989, True)
    assert events == ["start_opened", "start_quick_add", "start_first_saved"]


def test_want_to_saves_a_member_tracked_title_as_not_started(authenticated_client, db_session):
    add_movie(db_session, member(db_session, "a"), title="Arrival", year=2016, director="Denis Villeneuve",
              rating=9.0, review="Private thoughts", watched=True)
    db_session.commit()
    data = authenticated_client.post("/api/start/save",
                                     json={"id": "movie/arrival-2016", "answer": "want", "via": "search"}).json()
    assert data["state"] == "created" and data["seen"] is False
    mine = db_session.query(models.Movie).filter_by(user_id=_me(db_session).id).one()
    assert (mine.title, mine.director, mine.rating, mine.review, mine.watched) == ("Arrival", "Denis Villeneuve", None, None, False)


def test_a_title_already_in_the_library_is_left_as_it_was(authenticated_client, db_session):
    add_movie(db_session, _me(db_session), title="The Dark Knight", year=2008, rating=6.0, watched=False)
    db_session.commit()
    data = authenticated_client.post("/api/start/save", json={"id": "movie/the-dark-knight-2008", "answer": "seen"}).json()
    assert data["state"] == "existing"
    movie = db_session.query(models.Movie).one()
    assert (movie.rating, movie.watched) == (6.0, False)


def test_only_known_titles_can_be_saved(authenticated_client):
    for item_id in ("movie/made-up-film-2030", "spaceship/whatever", "movie/../../etc"):
        assert authenticated_client.post("/api/start/save", json={"id": item_id, "answer": "seen"}).status_code == 404
    assert authenticated_client.post("/api/start/save", json={"id": "movie/the-matrix-1999", "answer": "loved"}).status_code == 422


def test_steps_count_each_member_once(authenticated_client, db_session, events):
    for slug in ("movie/the-matrix-1999", "movie/titanic-1997", "tv/friends-1994", "anime/naruto-2002"):
        authenticated_client.post("/api/start/save", json={"id": slug, "answer": "want"})
    assert events.count("start_quick_add") == 1 and events.count("start_first_saved") == 1
    assert "start_reached_five" not in events
    data = authenticated_client.post("/api/start/save", json={"id": "game/hades-2020", "answer": "seen"}).json()
    assert data["total"] == 5 and events.count("start_reached_five") == 1
    authenticated_client.post("/api/start/save", json={"id": "game/celeste-2018", "answer": "seen"})
    assert events.count("start_reached_five") == 1
    for step in ("import", "import", "quiz", "next_step", "skipped"):
        assert authenticated_client.post("/api/start/step", json={"step": step}).status_code == 204
    assert [events.count(name) for name in ("start_import", "start_quiz", "start_next_step", "start_skipped")] == [1, 1, 1, 1]
    assert events.count("start_opened") == 1
    assert authenticated_client.post("/api/start/step", json={"step": "reached_five"}).status_code == 422


def test_reaching_five_another_way_is_counted_on_the_next_check(authenticated_client, db_session, events):
    authenticated_client.get("/start")
    me = _me(db_session)
    for index in range(5):
        add_movie(db_session, me, title=f"Imported {index}", year=2000 + index)
    db_session.commit()
    state = authenticated_client.get("/api/start/state").json()
    assert state["total"] == 5 and len(state["shelf"]) == 5
    assert "start_reached_five" in events


# ---------------------------------------------------------------- undo

def test_undo_takes_back_a_title_saved_a_moment_ago(authenticated_client, db_session):
    saved = authenticated_client.post("/api/start/save", json={"id": "book/dune-1965", "answer": "seen"}).json()
    response = authenticated_client.post("/api/start/undo", json={"category": "books", "item_id": saved["item_id"]})
    assert response.status_code == 200 and response.json() == {"total": 0}
    assert db_session.query(models.Book).count() == 0


def test_undo_never_removes_older_titles_or_other_members_titles(authenticated_client, db_session):
    old = add_movie(db_session, _me(db_session), added_at=datetime.utcnow() - timedelta(days=2))
    theirs = add_movie(db_session, member(db_session, "other"))
    db_session.commit()
    assert authenticated_client.post("/api/start/undo", json={"category": "movies", "item_id": old.id}).status_code == 409
    assert authenticated_client.post("/api/start/undo", json={"category": "movies", "item_id": theirs.id}).status_code == 404
    assert db_session.query(models.Movie).count() == 2


# ---------------------------------------------------------------- site stats and emails

def test_site_stats_shows_the_start_page_counts():
    summary = funnel.summary({"start_opened": 4, "start_first_saved": 3, "start_reached_five": 2, "start_quick_add": 3})
    assert [step["count"] for step in summary["start"]] == [4, 3, 2, 0]
    assert {item["event"]: item["count"] for item in summary["start_paths"]}["start_quick_add"] == 3
    assert {"start_opened", "start_skipped"} <= funnel.SERVER_EVENTS
    assert not {"start_opened", "start_reached_five"} & funnel.CLIENT_EVENTS
    from pathlib import Path
    root = Path(__file__).parents[1] / "app"
    assert 'id="startFunnel"' in (root / "templates" / "site_stats.html").read_text(encoding="utf-8")
    assert "data.funnel.start" in (root / "static" / "site-stats.js").read_text(encoding="utf-8")


def test_day_one_welcome_email_points_an_empty_library_to_the_start_page():
    from app import welcome_emails
    _, _, _, sections = welcome_emails._day_one(0)
    links = [path for _, items in sections for _, _, path in items]
    assert links[0] == "/start" and "/taste-quiz" in links
    _, _, _, started = welcome_emails._day_one(3)
    assert "/start" not in [path for _, items in started for _, _, path in items]
