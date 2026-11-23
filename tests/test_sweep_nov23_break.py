"""Nov 23 2026 sweep of the break planner (PR #325): ticks must never set a member's library back or finish a
title on a guessed length, unticking has to stick, big libraries still get their started titles planned and
can find any title to add, and share links stay private in Site stats."""
from datetime import date, datetime

import pytest

from app import break_plan, models, site_traffic
from app.progress import ProgressWrite, save_progress
from tests.test_break_plan import THANKSGIVING, make_user, sign_in, sign_out


def _items(plan):
    return [entry for day in plan["days"] for entry in day["items"]]


def _plan(client, today="2026-11-24", **extra):
    body = {"starts_on": "2026-11-26", "ends_on": "2026-11-29", "minutes": THANKSGIVING, "today": today,
            "preset": "thanksgiving-2026", "games": False, **extra}
    response = client.post("/api/break", json=body)
    assert response.status_code == 201, response.text
    return response.json()["plan"]


def _checkpoint(db, user, category, item_id):
    entry = db.query(models.ProgressCheckpoint).filter_by(user_id=user.id, category=category, item_id=item_id).first()
    if entry is not None:
        db.refresh(entry)
    return entry


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(break_plan, "_now", lambda: datetime(2026, 11, 24, 15, 0))


@pytest.fixture
def dana(client, db_session, clock):
    user = make_user(db_session, "dana")
    sign_in(client, user)
    return user


def test_a_season_the_plan_cant_place_is_never_overwritten(client, db_session, dana):
    # Season 3, episode 2 of a show with no episode list cached: the plan can't tell how far in that is.
    show = models.TVShow(user_id=dana.id, title="Slow Horses", year=2022, seasons=4, watched=False)
    db_session.add(show)
    db_session.commit()
    save_progress(db_session, dana.id, "tv-shows", show.id,
                  ProgressWrite(unit="episode", season=3, position=2, expected_revision=0))
    plan = _plan(client)
    for entry in _items(plan):
        if entry["item_id"] == show.id and entry["category"] == "tv-shows":
            client.post(f"/api/break/{plan['id']}/items/{entry['id']}/done", json={"today": "2026-11-26"})
    entry = _checkpoint(db_session, dana, "tv-shows", show.id)
    assert (entry.season, entry.position) == (3, 2)
    db_session.refresh(show)
    assert show.watched is False
    assert not any(entry["item_id"] == show.id for entry in _items(plan))
    added = client.post(f"/api/break/{plan['id']}/items", json={"category": "tv-shows", "item_id": show.id,
                                                                "day": "2026-11-27", "today": "2026-11-24"})
    assert added.status_code == 409
    assert "episode" in added.json()["detail"]


def test_a_specials_checkpoint_is_left_alone_too(client, db_session, dana):
    show = models.TVShow(user_id=dana.id, title="Doctor Who", year=2005, seasons=1, episodes=13, watched=False)
    db_session.add(show)
    db_session.commit()
    save_progress(db_session, dana.id, "tv-shows", show.id,
                  ProgressWrite(unit="episode", season=0, position=4, expected_revision=0))
    item = models.BreakPlanItem(plan_id=0, user_id=dana.id, day=date(2026, 11, 26), category="tv-shows",
                                item_id=show.id, title="Doctor Who", unit="episode", first=1, last=3, total=13)
    assert break_plan._move_checkpoint(db_session, dana, item) is False
    entry = _checkpoint(db_session, dana, "tv-shows", show.id)
    assert (entry.season, entry.position) == (0, 4)


def test_unticking_a_stretch_puts_the_library_back_and_stays_unticked(client, db_session, dana):
    show = models.TVShow(user_id=dana.id, title="Severance", year=2022, seasons=1, episodes=9, watched=False)
    db_session.add(show)
    db_session.commit()
    save_progress(db_session, dana.id, "tv-shows", show.id,
                  ProgressWrite(unit="episode", position=3, note="Rewatch the cold open", expected_revision=0))
    plan = _plan(client)
    first = next(entry for entry in _items(plan) if entry["item_id"] == show.id)
    assert first["last"] < 9
    client.post(f"/api/break/{plan['id']}/items/{first['id']}/done", json={"today": "2026-11-26"})
    assert _checkpoint(db_session, dana, "tv-shows", show.id).position == first["last"]
    undone = client.post(f"/api/break/{plan['id']}/items/{first['id']}/undo", json={"today": "2026-11-26"})
    assert undone.status_code == 200, undone.text
    assert next(entry for entry in _items(undone.json()["plan"]) if entry["id"] == first["id"])["done"] is False
    entry = _checkpoint(db_session, dana, "tv-shows", show.id)
    assert (entry.position, entry.note) == (3, "Rewatch the cold open")
    fresh = client.get("/api/break?today=2026-11-26").json()["plan"]
    assert next(entry for entry in _items(fresh) if entry["id"] == first["id"])["done"] is False


def test_unticking_after_the_library_moved_on_says_why_it_stays(client, db_session, dana):
    show = models.TVShow(user_id=dana.id, title="Severance", year=2022, seasons=1, episodes=9, watched=False)
    db_session.add(show)
    db_session.commit()
    save_progress(db_session, dana.id, "tv-shows", show.id, ProgressWrite(unit="episode", position=3, expected_revision=0))
    plan = _plan(client)
    first = next(entry for entry in _items(plan) if entry["item_id"] == show.id)
    client.post(f"/api/break/{plan['id']}/items/{first['id']}/done", json={"today": "2026-11-26"})
    entry = _checkpoint(db_session, dana, "tv-shows", show.id)
    # The member logs one more episode in the library after ticking: undoing must not wipe that.
    save_progress(db_session, dana.id, "tv-shows", show.id,
                  ProgressWrite(unit="episode", position=first["last"] + 1, expected_revision=entry.revision))
    undone = client.post(f"/api/break/{plan['id']}/items/{first['id']}/undo", json={"today": "2026-11-26"})
    assert undone.status_code == 409
    assert "library" in undone.json()["detail"]
    assert _checkpoint(db_session, dana, "tv-shows", show.id).position == first["last"] + 1


def test_a_guessed_length_asks_before_finishing_the_book(client, db_session, dana):
    # No page count known: the plan guesses 320 pages, so the last stretch can't know the book is done.
    book = models.Book(user_id=dana.id, title="An Unknown Book", author="Someone", read=False)
    db_session.add(book)
    db_session.commit()
    save_progress(db_session, dana.id, "books", book.id, ProgressWrite(unit="page", position=200, expected_revision=0))
    plan = _plan(client)
    stretches = [entry for entry in _items(plan) if entry["item_id"] == book.id and entry["category"] == "books"]
    assert stretches and stretches[-1]["last_part"]
    last = stretches[-1]
    ticked = client.post(f"/api/break/{plan['id']}/items/{last['id']}/done", json={"today": "2026-11-29"}).json()
    assert ticked["ticked"] == {"finished": False, "ask_finish": True}
    db_session.refresh(book)
    assert book.read is False
    shown = next(entry for entry in _items(ticked["plan"]) if entry["id"] == last["id"])
    assert shown["done"] is True and shown["confirm_finish"] is True
    finished = client.post(f"/api/break/{plan['id']}/items/{last['id']}/finish", json={"today": "2026-11-29"})
    assert finished.status_code == 200
    db_session.refresh(book)
    assert book.read is True


def test_a_show_that_grew_isnt_finished_by_its_old_last_episode(client, db_session, dana):
    show = models.TVShow(user_id=dana.id, title="Severance", year=2022, seasons=1, episodes=9, watched=False)
    db_session.add(show)
    db_session.commit()
    save_progress(db_session, dana.id, "tv-shows", show.id, ProgressWrite(unit="episode", position=3, expected_revision=0))
    plan = _plan(client)
    last = [entry for entry in _items(plan) if entry["item_id"] == show.id][-1]
    assert last["last"] == 9
    show.seasons, show.episodes = 2, 19  # a second season was added to the library since the plan was made
    db_session.commit()
    ticked = client.post(f"/api/break/{plan['id']}/items/{last['id']}/done", json={"today": "2026-11-29"}).json()
    assert ticked["ticked"]["finished"] is False
    db_session.refresh(show)
    assert show.watched is False
    assert _checkpoint(db_session, dana, "tv-shows", show.id).position == 9


def test_a_started_title_is_planned_however_big_the_library(client, db_session, dana):
    db_session.add_all([models.Book(user_id=dana.id, title=f"Saved book {n}", author="A", read=False)
                        for n in range(break_plan.POOL_PER_CATEGORY + 5)])
    reading = models.Book(user_id=dana.id, title="The One I'm Reading", author="B", read=False)
    queued = models.Movie(user_id=dana.id, title="Queued Film", year=2020, watched=False)
    db_session.add_all([reading, queued])
    db_session.commit()
    save_progress(db_session, dana.id, "books", reading.id, ProgressWrite(unit="page", position=40, expected_revision=0))
    db_session.add(models.NextUpItem(user_id=dana.id, category="movies", item_id=queued.id, position=0))
    db_session.commit()
    titles = [entry["title"] for entry in _items(_plan(client))]
    assert titles[0] == "The One I'm Reading"
    assert "Queued Film" in titles


def test_any_title_can_be_found_to_add(client, db_session, dana):
    db_session.add_all([models.Movie(user_id=dana.id, title=f"Film {n:03d}", year=2000, watched=False)
                        for n in range(230)])
    db_session.commit()
    plan = _plan(client)
    db_session.add(models.TVShow(user_id=dana.id, title="Zebra Show", year=2020, seasons=1, episodes=8, watched=False))
    db_session.commit()
    listed = client.get(f"/api/break/{plan['id']}/titles").json()["titles"]
    assert any(entry["category"] == "tv-shows" for entry in listed)
    found = client.get(f"/api/break/{plan['id']}/titles", params={"q": "film 22"}).json()["titles"]
    assert {entry["title"] for entry in found} >= {f"Film {n}" for n in range(220, 230)}
    assert all("22" in entry["title"] for entry in found)
    assert client.get(f"/api/break/{plan['id']}/titles", params={"q": "%"}).json()["titles"] == []


def test_taking_a_title_off_keeps_it_off_when_the_day_is_filled_again(client, db_session, dana):
    film = models.Movie(user_id=dana.id, title="The Holdovers", year=2023, watched=False)
    other = models.Movie(user_id=dana.id, title="Paddington 2", year=2017, watched=False)
    db_session.add_all([film, other])
    db_session.commit()
    plan = _plan(client)
    entry = next(entry for entry in _items(plan) if entry["title"] == "The Holdovers")
    client.delete(f"/api/break/{plan['id']}/items/{entry['id']}", params={"today": "2026-11-24"})
    refilled = client.post(f"/api/break/{plan['id']}/fill", json={"today": "2026-11-24"}).json()["plan"]
    assert "The Holdovers" not in [item["title"] for item in _items(refilled)]
    back = client.post(f"/api/break/{plan['id']}/items", json={"category": "movies", "item_id": film.id,
                                                               "day": "2026-11-28", "today": "2026-11-24"})
    assert back.status_code == 200


def test_a_shorter_break_keeps_what_was_ticked_on_its_board(client, db_session, dana):
    db_session.add_all([models.Movie(user_id=dana.id, title=f"Film {n}", year=2000 + n, watched=False) for n in range(6)])
    db_session.commit()
    plan = _plan(client)
    sunday = next(entry for entry in plan["days"][3]["items"])
    client.post(f"/api/break/{plan['id']}/items/{sunday['id']}/done", json={"today": "2026-11-24"})
    shorter = client.patch(f"/api/break/{plan['id']}", json={"ends_on": "2026-11-28", "today": "2026-11-24"}).json()["plan"]
    on_board = [entry["id"] for entry in _items(shorter)]
    assert sunday["id"] in on_board
    assert shorter["totals"]["done"] == sum(1 for entry in _items(shorter) if entry["done"])


def test_a_shared_plan_drops_titles_taken_out_of_the_library(client, db_session, dana):
    film = models.Movie(user_id=dana.id, title="Embarrassing Film", year=2001, watched=False)
    db_session.add(film)
    db_session.commit()
    plan = _plan(client)
    assert any(entry["title"] == "Embarrassing Film" for entry in _items(plan))
    path = client.post(f"/api/break/{plan['id']}/share", json={"today": "2026-11-24"}).json()["path"]
    db_session.delete(film)
    db_session.commit()
    sign_out(client)
    page = client.get(path)
    assert page.status_code == 200
    assert "Embarrassing Film" not in page.text


def test_share_links_are_masked_in_site_stats():
    assert site_traffic.mask_private_link("/break/s/abcdefghijklmnopqrstuv") == "/break/s/(private link)"
    assert site_traffic.mask_private_link("/break") == "/break"


def test_unticking_part_of_a_title_finished_in_the_library_is_refused(client, db_session, dana):
    show = models.TVShow(user_id=dana.id, title="Severance", year=2022, seasons=1, episodes=9, watched=False)
    db_session.add(show)
    db_session.commit()
    plan = _plan(client)
    stretches = [entry for entry in _items(plan) if entry["item_id"] == show.id]
    first, last = stretches[0], stretches[-1]
    assert first["id"] != last["id"]
    client.post(f"/api/break/{plan['id']}/items/{last['id']}/done", json={"today": "2026-11-29"})
    db_session.refresh(show)
    assert show.watched is True
    # Finishing the show ticked the earlier stretch too; unticking it would only be ticked again.
    undone = client.post(f"/api/break/{plan['id']}/items/{first['id']}/undo", json={"today": "2026-11-29"})
    assert undone.status_code == 409


def test_the_undo_column_migration_is_additive(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect, text
    from app import migrations
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE break_plan_items (id INTEGER PRIMARY KEY, plan_id INTEGER, user_id INTEGER, "
                          "day DATE, category VARCHAR(16), item_id INTEGER, title VARCHAR(200), unit VARCHAR(8))"))
        conn.execute(text("INSERT INTO break_plan_items (id, plan_id, user_id, day, category, item_id, title, unit) "
                          "VALUES (1, 2, 3, '2026-11-26', 'movies', 4, 'Old row', 'whole')"))
    monkeypatch.setattr(migrations, "engine", engine)
    migrations.add_break_item_undo_column()
    migrations.add_break_item_undo_column()  # every start runs it; the second pass changes nothing
    assert "undo_progress" in {column["name"] for column in inspect(engine).get_columns("break_plan_items")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT title, undo_progress FROM break_plan_items")).fetchall() == [("Old row", None)]
