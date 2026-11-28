"""Break planner (/break): presets, filling days from the library, ticking off, sharing and the two emails."""
import asyncio
import json
from datetime import date, datetime, timedelta

import pytest

from app import auth, break_plan, models
from app.progress import ProgressWrite, save_progress


def make_user(db, name, **extra):
    user = models.User(username=name, email=f"{name}@example.test", hashed_password="unused", is_active=True,
                       is_verified=True, **extra)
    db.add(user)
    db.commit()
    return user


def sign_in(client, user):
    client.headers["Authorization"] = "Bearer " + auth.create_access_token({"sub": user.username, "uid": user.id})


def sign_out(client):
    client.headers.pop("Authorization", None)
    client.cookies.clear()


def library(db, user):
    """A small library: a show part-way through, two films, an album, a book, a game and a finished film."""
    show = models.TVShow(user_id=user.id, title="Severance", year=2022, seasons=1, episodes=9, watched=False,
                         poster_url="https://image.tmdb.org/t/p/w342/severance.jpg")
    film = models.Movie(user_id=user.id, title="The Holdovers", year=2023, watched=False)
    film2 = models.Movie(user_id=user.id, title="Paddington 2", year=2017, watched=False)
    done = models.Movie(user_id=user.id, title="Knives Out", year=2019, watched=True)
    album = models.Music(user_id=user.id, title="Rumours", artist="Fleetwood Mac", year=1977, listened=False)
    book = models.Book(user_id=user.id, title="Piranesi", author="Susanna Clarke", year=2020, read=False)
    game = models.VideoGame(user_id=user.id, title="Hades", played=False)
    db.add_all([show, film, film2, done, album, book, game])
    db.commit()
    save_progress(db, user.id, "tv-shows", show.id, ProgressWrite(unit="episode", position=3, expected_revision=0))
    return {"show": show, "film": film, "film2": film2, "done": done, "album": album, "book": book, "game": game}


THANKSGIVING = {"2026-11-26": 60, "2026-11-27": 180, "2026-11-28": 180, "2026-11-29": 180}


def make_plan(client, today="2026-11-24", **extra):
    body = {"starts_on": "2026-11-26", "ends_on": "2026-11-29", "minutes": THANKSGIVING, "today": today,
            "preset": "thanksgiving-2026", **extra}
    response = client.post("/api/break", json=body)
    assert response.status_code == 201, response.text
    return response.json()["plan"]


@pytest.fixture
def member(client, db_session, monkeypatch):
    monkeypatch.setattr(break_plan, "_now", lambda: datetime(2026, 11, 24, 15, 0))
    user = make_user(db_session, "dana")
    rows = library(db_session, user)
    sign_in(client, user)
    return user, rows


# ---------------------------------------------------------------- presets

def test_thanksgiving_and_the_holidays_are_offered_with_their_light_days():
    found = {entry["key"]: entry for entry in break_plan.presets(date(2026, 11, 23))}
    assert found["thanksgiving-2026"]["starts_on"] == date(2026, 11, 26)
    assert found["thanksgiving-2026"]["ends_on"] == date(2026, 11, 29)
    assert found["thanksgiving-2026"]["light"] == [date(2026, 11, 26)]
    assert found["winter-2026"]["starts_on"] == date(2026, 12, 24)
    assert found["winter-2026"]["ends_on"] == date(2027, 1, 1)
    # The weekend overlaps Thanksgiving, so it isn't offered twice.
    assert not any(key.startswith("weekend-") for key in found)
    assert break_plan.thanksgiving(2027) == date(2027, 11, 25)


def test_a_holiday_under_way_starts_today_and_the_home_offer_follows_the_lead_up():
    friday = {entry["key"]: entry for entry in break_plan.presets(date(2026, 11, 27))}
    assert friday["thanksgiving-2026"]["starts_on"] == date(2026, 11, 27)
    assert friday["thanksgiving-2026"]["light"] == []
    assert break_plan.prompt_preset(date(2026, 11, 10)) is None
    assert break_plan.prompt_preset(date(2026, 11, 16))["key"] == "thanksgiving-2026"
    assert break_plan.prompt_preset(date(2026, 11, 29)) is None  # its last day: too late to plan
    assert break_plan.prompt_preset(date(2026, 12, 12))["key"] == "winter-2026"


def test_long_weekends_through_the_year():
    may = {entry["slug"]: entry for entry in break_plan.presets(date(2027, 5, 20))}
    assert (may["memorial"]["starts_on"], may["memorial"]["ends_on"]) == (date(2027, 5, 29), date(2027, 5, 31))
    july = {entry["slug"]: entry for entry in break_plan.presets(date(2027, 6, 30))}
    assert (july["july-4"]["starts_on"], july["july-4"]["ends_on"]) == (date(2027, 7, 3), date(2027, 7, 5))
    weekend = {entry["slug"]: entry for entry in break_plan.presets(date(2027, 3, 10))}["weekend"]
    assert (weekend["starts_on"], weekend["ends_on"]) == (date(2027, 3, 13), date(2027, 3, 14))


def test_lengths_read_like_a_person_wrote_them():
    assert break_plan.length_words(45) == "45 min"
    assert break_plan.length_words(133) == "2h 13m"
    assert break_plan.length_words(240) == "4h"
    assert break_plan.length_words(272) == "4h 32m"
    assert break_plan.length_words(150, guessed=True) == "About 2.5 hours"
    assert break_plan.clean_minutes(100) == 90
    assert break_plan.clean_minutes(-5) == 0


# ---------------------------------------------------------------- filling

def test_the_demo_finishes_the_show_first_and_keeps_films_whole():
    days = break_plan.days_of(date(2026, 11, 26), date(2026, 11, 29))
    board = break_plan.demo(date(2026, 11, 26), break_plan.default_minutes(days, 180, [date(2026, 11, 26)]))
    assert [day["budget"] for day in board] == [60, 180, 180, 180]
    labels = [entry["label"] for day in board for entry in day["items"] if entry["title"].startswith("Severance")]
    assert labels[0] == "Episode 5" and labels[-1].endswith("9")  # the sample member is halfway through
    for day in board:
        assert day["planned"] <= day["budget"] * 1.2


def test_a_new_title_only_goes_in_if_the_break_can_finish_it():
    long_show = break_plan.Candidate(category="tv-shows", item_id=1, title="Long", unit="episode", step=50,
                                     total=40, target=40)
    film = break_plan.Candidate(category="movies", item_id=2, title="Film", unit="whole", step=100)
    days = [break_plan.Day(date(2026, 11, 28), 180, 180), break_plan.Day(date(2026, 11, 29), 180, 180)]
    chunks = break_plan.fill_days(days, [long_show, film], max_titles=5)
    assert {chunk["title"] for chunk in chunks} == {"Film"}


def test_a_title_already_placed_never_loses_out_to_a_later_one():
    show = break_plan.Candidate(category="tv-shows", item_id=1, title="Show", group="started", unit="episode",
                                step=60, done=3, total=8, target=8)
    film = break_plan.Candidate(category="movies", item_id=2, title="Film", unit="whole", step=120)
    days = [break_plan.Day(date(2026, 11, 28), 180, 180), break_plan.Day(date(2026, 11, 29), 180, 180)]
    chunks = break_plan.fill_days(days, [show, film], max_titles=5)
    episodes = sum(chunk["last"] - chunk["first"] + 1 for chunk in chunks if chunk["title"] == "Show")
    assert episodes == 5
    assert "Film" not in {chunk["title"] for chunk in chunks}


def test_a_new_game_takes_part_of_a_long_break_and_none_of_a_short_one():
    game = break_plan.Candidate(category="video-games", item_id=1, title="Game", unit="block", step=30,
                                total=40, target=40)
    long_days = [break_plan.Day(date(2026, 12, 24) + timedelta(days=n), 240, 240) for n in range(4)]
    chunks = break_plan.fill_days(long_days, [game], max_titles=5)
    assert sum(chunk["minutes"] for chunk in chunks) <= 960 * break_plan.GAME_SHARE
    assert all(chunk["minutes"] >= 60 for chunk in chunks)
    short = [break_plan.Day(date(2026, 11, 28), 120, 120), break_plan.Day(date(2026, 11, 29), 120, 120)]
    assert break_plan.fill_days(short, [game], max_titles=5) == []


def test_making_a_plan_fills_it_from_the_library_in_order(client, member):
    user, rows = member
    plan = make_plan(client)
    assert plan["name"] == "Thanksgiving weekend"
    assert plan["phase"] == "upcoming"
    items = [entry for day in plan["days"] for entry in day["items"]]
    titles = [entry["title"] for entry in items]
    assert titles[0] == "Severance"  # part-way through: first
    assert items[0]["label"] == "Episode 4"
    assert "Knives Out" not in titles  # finished already
    shows = [entry for entry in items if entry["title"] == "Severance"]
    assert shows[-1]["last"] == 9
    for entry in items:
        if entry["category"] == "movies":
            assert entry["unit"] == "whole"
    assert plan["days"][0]["budget"] == 60
    assert plan["totals"]["titles"] == len(set(titles))


def test_one_plan_at_a_time_and_dates_are_checked(client, member):
    make_plan(client)
    again = client.post("/api/break", json={"starts_on": "2026-12-24", "ends_on": "2027-01-01", "minutes": {},
                                            "today": "2026-11-24"})
    assert again.status_code == 409
    user, _ = member
    assert client.post("/api/break", json={"starts_on": "2026-11-20", "ends_on": "2026-11-22",
                                           "today": "2026-11-24"}).status_code in (409, 422)


def test_dates_are_checked(client, db_session, monkeypatch):
    monkeypatch.setattr(break_plan, "_now", lambda: datetime(2026, 11, 24, 15, 0))
    user = make_user(db_session, "lee")
    sign_in(client, user)
    past = client.post("/api/break", json={"starts_on": "2026-11-20", "ends_on": "2026-11-22", "today": "2026-11-24"})
    assert past.status_code == 422
    long = client.post("/api/break", json={"starts_on": "2026-12-01", "ends_on": "2026-12-31", "today": "2026-11-24"})
    assert long.status_code == 422
    busy = client.post("/api/break", json={"starts_on": "2026-11-28", "ends_on": "2026-11-29", "today": "2026-11-24",
                                           "minutes": {"2026-11-28": 0, "2026-11-29": 0}})
    assert busy.status_code == 422


# ---------------------------------------------------------------- ticking off

def _items(plan):
    return [entry for day in plan["days"] for entry in day["items"]]


def test_ticking_a_stretch_moves_the_library_forward_and_the_last_one_finishes_it(client, db_session, member):
    user, rows = member
    plan = make_plan(client)
    shows = [entry for entry in _items(plan) if entry["title"] == "Severance"]
    first = shows[0]
    response = client.post(f"/api/break/{plan['id']}/items/{first['id']}/done", json={"today": "2026-11-26"})
    assert response.status_code == 200, response.text
    entry = db_session.query(models.ProgressCheckpoint).filter_by(user_id=user.id, category="tv-shows",
                                                                  item_id=rows["show"].id).first()
    db_session.refresh(entry)
    assert entry.position == first["last"]
    last = shows[-1]
    response = client.post(f"/api/break/{plan['id']}/items/{last['id']}/done", json={"today": "2026-11-29"})
    assert response.json()["ticked"]["finished"] is True
    db_session.refresh(rows["show"])
    assert rows["show"].watched is True
    after = response.json()["plan"]
    assert all(entry["done"] for entry in _items(after) if entry["title"] == "Severance")
    assert db_session.query(models.ActivityEntry).filter_by(user_id=user.id, category="tv-shows",
                                                            action="completed").count() == 1


def test_ticking_a_film_finishes_it_and_it_can_be_scored(client, db_session, member):
    user, rows = member
    plan = make_plan(client)
    film = next(entry for entry in _items(plan) if entry["category"] == "movies")
    ticked = client.post(f"/api/break/{plan['id']}/items/{film['id']}/done", json={"today": "2026-11-27"}).json()
    assert ticked["ticked"]["finished"] is True
    rated = client.post(f"/api/break/{plan['id']}/items/{film['id']}/rate", json={"rating": 9})
    assert rated.status_code == 200
    model = db_session.get(models.Movie, film["item_id"])
    db_session.refresh(model)
    assert model.watched is True and model.rating == 9
    undo = client.post(f"/api/break/{plan['id']}/items/{film['id']}/undo", json={})
    assert undo.status_code == 409


def test_logging_in_the_library_ticks_the_plan(client, db_session, member):
    user, rows = member
    plan = make_plan(client)
    first = next(entry for entry in _items(plan) if entry["title"] == "Severance")
    entry = db_session.query(models.ProgressCheckpoint).filter_by(user_id=user.id, item_id=rows["show"].id).first()
    save_progress(db_session, user.id, "tv-shows", rows["show"].id,
                  ProgressWrite(unit="episode", position=first["last"], expected_revision=entry.revision))
    fresh = client.get("/api/break?today=2026-11-26").json()["plan"]
    assert next(item for item in _items(fresh) if item["id"] == first["id"])["done"] is True
    rows["album"].listened = True
    db_session.commit()
    fresh = client.get("/api/break?today=2026-11-26").json()["plan"]
    assert all(item["done"] for item in _items(fresh) if item["title"] == "Rumours")


def test_a_deleted_title_leaves_the_plan(client, db_session, member):
    user, rows = member
    plan = make_plan(client)
    assert any(entry["title"] == "Rumours" for entry in _items(plan))
    db_session.delete(rows["album"])
    db_session.commit()
    fresh = client.get("/api/break?today=2026-11-26").json()["plan"]
    assert not any(entry["title"] == "Rumours" for entry in _items(fresh))


# ---------------------------------------------------------------- changing it

def test_swap_move_remove_and_add(client, db_session, member):
    user, rows = member
    plan = make_plan(client)
    pid = plan["id"]
    film = next(entry for entry in _items(plan) if entry["category"] == "movies")
    moved = client.patch(f"/api/break/{pid}/items/{film['id']}", json={"day": "2026-11-29", "today": "2026-11-24"})
    assert moved.status_code == 200
    assert next(e for e in _items(moved.json()["plan"]) if e["id"] == film["id"]) and \
        any(e["id"] == film["id"] for e in moved.json()["plan"]["days"][3]["items"])
    assert client.patch(f"/api/break/{pid}/items/{film['id']}", json={"day": "2026-12-05"}).status_code == 422
    swapped = client.delete(f"/api/break/{pid}/items/{film['id']}?swap=true&today=2026-11-24").json()["plan"]
    assert film["title"] not in [entry["title"] for entry in _items(swapped)]
    titles = client.get(f"/api/break/{pid}/titles").json()["titles"]
    assert any(entry["title"] == film["title"] for entry in titles)
    added = client.post(f"/api/break/{pid}/items", json={"category": "movies", "item_id": film["item_id"],
                                                         "day": "2026-11-28", "today": "2026-11-24"})
    assert added.status_code == 200, added.text
    entries = [e for e in _items(added.json()["plan"]) if e["title"] == film["title"]]
    assert entries and entries[0]["added"] is True
    again = client.post(f"/api/break/{pid}/items", json={"category": "movies", "item_id": film["item_id"],
                                                         "day": "2026-11-28", "today": "2026-11-24"})
    assert again.status_code == 409
    finished = client.post(f"/api/break/{pid}/items", json={"category": "movies", "item_id": rows["done"].id,
                                                            "day": "2026-11-28", "today": "2026-11-24"})
    assert finished.status_code == 409


def test_less_time_keeps_the_plan_and_more_time_fills_it(client, db_session, member):
    plan = make_plan(client)
    before = plan["totals"]["stretches"]
    response = client.patch(f"/api/break/{plan['id']}", json={"minutes": {"2026-11-26": 0}, "today": "2026-11-24"})
    assert response.json()["plan"]["totals"]["stretches"] == before
    assert response.json()["plan"]["days"][0]["over"] > 0
    longer = client.patch(f"/api/break/{plan['id']}", json={"ends_on": "2026-11-30", "today": "2026-11-24"}).json()["plan"]
    assert longer["day_count"] == 5


def test_another_mix_keeps_what_the_member_ticked_and_added(client, db_session, member):
    user, rows = member
    plan = make_plan(client)
    first = _items(plan)[0]
    client.post(f"/api/break/{plan['id']}/items/{first['id']}/done", json={"today": "2026-11-26"})
    mixed = client.post(f"/api/break/{plan['id']}/shuffle", json={"today": "2026-11-26"})
    assert mixed.status_code == 200
    assert any(entry["id"] == first["id"] and entry["done"] for entry in _items(mixed.json()["plan"]))


def test_other_members_cant_touch_a_plan(client, db_session, member):
    plan = make_plan(client)
    other = make_user(db_session, "sam")
    sign_in(client, other)
    item = _items(plan)[0]
    assert client.post(f"/api/break/{plan['id']}/items/{item['id']}/done", json={}).status_code == 404
    assert client.patch(f"/api/break/{plan['id']}", json={"name": "Mine"}).status_code == 404
    assert client.get("/api/break").json()["plan"] is None


# ---------------------------------------------------------------- home card

def test_home_card_offers_before_thanksgiving_then_shows_the_plan(client, db_session, member):
    card = client.get("/api/break/home?today=2026-11-24").json()["card"]
    assert card["state"] == "offer" and card["key"] == "thanksgiving-2026"
    make_plan(client)
    card = client.get("/api/break/home?today=2026-11-24").json()["card"]
    assert card["state"] == "upcoming" and card["first_day"]


def test_home_card_during_and_after(client, db_session, member, monkeypatch):
    plan = make_plan(client)
    monkeypatch.setattr(break_plan, "_now", lambda: datetime(2026, 11, 27, 15, 0))
    card = client.get("/api/break/home?today=2026-11-27").json()["card"]
    assert card["state"] == "during" and card["day_number"] == 2
    assert all(entry["id"] for entry in card["today_items"])
    seen = client.post("/api/break/seen", json={"today": "2026-11-27"}).json()
    assert seen["counted"] is True
    assert client.post("/api/break/seen", json={"today": "2026-11-27"}).json()["counted"] is False
    monkeypatch.setattr(break_plan, "_now", lambda: datetime(2026, 11, 30, 15, 0))
    after = client.get("/api/break/home?today=2026-11-30").json()["card"]
    assert after["state"] == "after"
    client.post(f"/api/break/{plan['id']}/hide-wrap", json={})
    assert client.get("/api/break/home?today=2026-11-30").json()["card"] is None


def test_no_offer_without_a_list(client, db_session, monkeypatch):
    user = make_user(db_session, "new")
    sign_in(client, user)
    assert client.get("/api/break/home?today=2026-11-24").json()["card"] is None


# ---------------------------------------------------------------- sharing

def test_a_shared_plan_shows_public_shelves_only(client, db_session, member):
    user, rows = member
    plan = make_plan(client)
    path = client.post(f"/api/break/{plan['id']}/share", json={"today": "2026-11-24"}).json()["path"]
    assert path.startswith("/break/s/")
    user.movies_private = True
    db_session.commit()
    sign_out(client)
    page = client.get(path)
    assert page.status_code == 200
    assert "Severance" in page.text
    assert "The Holdovers" not in page.text and "Paddington" not in page.text
    assert "keeps private" in page.text
    assert page.headers["x-robots-tag"].startswith("noindex")
    card = client.get(f"{path}/card.png")
    assert card.status_code == 200 and card.headers["content-type"] == "image/png"
    sign_in(client, user)
    client.delete(f"/api/break/{plan['id']}/share")
    sign_out(client)
    assert client.get(path).status_code == 404


# ---------------------------------------------------------------- pages and calendar

def test_guide_page_for_guests_and_members(client, db_session, member):
    user, _ = member
    sign_out(client)
    page = client.get("/break")
    assert page.status_code == 200
    assert "Plan your days off from your own list" in page.text
    assert "bp-board--demo" in page.text
    assert "FAQPage" in page.text
    assert "noindex" not in page.headers.get("x-robots-tag", "")
    sign_in(client, user)
    member_page = client.get("/break")
    assert 'id="breakApp"' in member_page.text


def test_demo_endpoint(client):
    response = client.post("/api/break/demo", json={"starts_on": "2026-11-28", "ends_on": "2026-11-29",
                                                    "minutes": {"2026-11-28": 120, "2026-11-29": 240}})
    assert response.status_code == 200
    days = response.json()["days"]
    assert [day["budget"] for day in days] == [120, 240]
    bad = client.post("/api/break/demo", json={"starts_on": "2026-11-28", "ends_on": "2027-01-29", "minutes": {}})
    assert bad.status_code == 422


def test_calendar_has_one_event_per_planned_day(client, member):
    plan = make_plan(client)
    response = client.get(f"/api/break/{plan['id']}/calendar.ics")
    assert response.status_code == 200
    assert response.text.count("BEGIN:VEVENT") == sum(1 for day in plan["days"] if day["items"])
    assert "DTSTART;VALUE=DATE:20261126" in response.text


# ---------------------------------------------------------------- emails

def test_start_and_wrap_emails_go_once_each_to_members_who_asked(client, db_session, member, monkeypatch):
    user, rows = member
    plan = make_plan(client, emails=True, tz=-300)
    sent = []

    async def sender(to, subject, html, unsubscribe_url):
        sent.append((to, subject, html))

    from tests.conftest import TestingSessionLocal
    monkeypatch.setattr(break_plan, "allowance", lambda db, now: 10)
    before = asyncio.run(break_plan.send_due(TestingSessionLocal, now=datetime(2026, 11, 26, 12, 0), sender=sender))
    assert before["sent"] == 0  # 8 am in UTC-5 is 13:00 UTC
    result = asyncio.run(break_plan.send_due(TestingSessionLocal, now=datetime(2026, 11, 26, 13, 5), sender=sender))
    assert result["sent"] == 1
    assert sent[-1][1] == "Thanksgiving weekend starts today"
    assert "Severance" in sent[-1][2]
    again = asyncio.run(break_plan.send_due(TestingSessionLocal, now=datetime(2026, 11, 26, 13, 20), sender=sender))
    assert again["sent"] == 0
    wrap = asyncio.run(break_plan.send_due(TestingSessionLocal, now=datetime(2026, 11, 30, 15, 10), sender=sender))
    assert wrap["sent"] == 1
    assert sent[-1][1] == "How did Thanksgiving weekend go?"
    assert "/check-in/" in sent[-1][2]


def test_no_email_without_asking_or_after_unsubscribing(client, db_session, member, monkeypatch):
    user, rows = member
    plan = make_plan(client)
    sent = []

    async def sender(to, subject, html, unsubscribe_url):
        sent.append(subject)

    from tests.conftest import TestingSessionLocal
    monkeypatch.setattr(break_plan, "allowance", lambda db, now: 10)
    asyncio.run(break_plan.send_due(TestingSessionLocal, now=datetime(2026, 11, 26, 13, 5), sender=sender))
    assert sent == []
    client.patch(f"/api/break/{plan['id']}", json={"emails": True, "today": "2026-11-24"})
    db_session.add(models.EmailOptOut(user_id=user.id))
    db_session.commit()
    result = asyncio.run(break_plan.send_due(TestingSessionLocal, now=datetime(2026, 11, 26, 8, 5), sender=sender))
    assert sent == [] and result["dropped"] >= 1
