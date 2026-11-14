"""The December advent calendar: door dates, the page and door pages, opening doors, saving, reminders and the card."""
from datetime import date, datetime

import pytest

from app import advent_calendar as advent, badges, models, seasonal, title_pages, web_push
from app.advent_calendar_data import EDITIONS
from app.routers import advent_calendar as advent_router

NOVEMBER = datetime(2026, 11, 20, 12, 0)
DEC_5_NOON = datetime(2026, 12, 5, 12, 0)  # UTC; door 6 is already open in UTC+14


@pytest.fixture
def at(monkeypatch):
    monkeypatch.delenv("ADVENT_CALENDAR_OPENS", raising=False)

    def set_now(when):
        monkeypatch.setattr(advent, "_now", lambda: when)
        return when
    set_now(DEC_5_NOON)
    return set_now


def _user(db_session, username="testuser"):
    return db_session.query(models.User).filter(models.User.username == username).one()


# ---------------------------------------------------------------- the writing

def test_edition_has_24_doors_across_every_format():
    doors = EDITIONS[2026]["doors"]
    assert [door["day"] for door in doors] == list(range(1, 25))
    kinds = [door["kind"] for door in doors]
    assert set(kinds) == set(title_pages.KINDS)
    assert all(kinds.count(kind) >= 2 for kind in title_pages.KINDS)
    for door in doors:
        for field in ("hint", "time", "why", "note", "caveat", "title", "creator"):
            assert door[field], (door["day"], field)
        assert isinstance(door["year"], int)
        # The closed door and the reminder must never give the pick away.
        assert door["title"].lower() not in door["hint"].lower()
        assert len(door["why"].split()) >= 50, door["title"]


def test_no_door_repeats_another_holiday_guide():
    from app.discover_catalog import MONTHLY_EDITIONS
    taken = {(item["kind"], title_pages.slugify(item["title"]))
             for slug in ("holidays", "thanksgiving", "reading-and-listening") for item in seasonal.picks(seasonal.season(slug))}
    december = MONTHLY_EDITIONS["december-2026"]["items"]
    taken |= {(title_pages.LIBRARY_TO_KIND[item["category"]], title_pages.slugify(item["title"])) for item in december}
    for door in EDITIONS[2026]["doors"]:
        assert (door["kind"], title_pages.slugify(door["title"])) not in taken, door["title"]
    titles = [title_pages.slugify(door["title"]) for door in EDITIONS[2026]["doors"]]
    assert len(titles) == len(set(titles))


# ---------------------------------------------------------------- dates

def test_doors_open_one_a_day_from_december_first(at):
    assert advent.opens(2026) == date(2026, 12, 1)
    assert advent.door_date(2026, 24) == date(2026, 12, 24)
    at(NOVEMBER)
    assert not advent.is_public(2026) and advent.current_year() is None and advent.unlocked(2026) == []
    # Door 1 is open once December 1 has started anywhere (UTC+14), 14 hours before it starts in UTC.
    at(datetime(2026, 11, 30, 9, 59))
    assert advent.unlocked(2026) == []
    at(datetime(2026, 11, 30, 10, 0))
    assert advent.unlocked(2026) == [1] and advent.current_year() == 2026
    at(DEC_5_NOON)
    assert advent.unlocked(2026) == [1, 2, 3, 4, 5, 6]
    at(datetime(2027, 3, 1))
    assert len(advent.unlocked(2026)) == 24 and advent.is_public(2026)
    assert advent.unlocked(2026, preview=True) == list(range(1, 25))


def test_env_switch_moves_opening_day(at, monkeypatch):
    monkeypatch.setenv("ADVENT_CALENDAR_OPENS", "2026-11-14")
    assert advent.opens(2026) == date(2026, 11, 14) and advent.door_date(2026, 3) == date(2026, 11, 16)
    at(datetime(2026, 11, 15, 12, 0))
    assert advent.unlocked(2026) == [1, 2, 3]
    # A date outside the edition's year is ignored.
    monkeypatch.setenv("ADVENT_CALENDAR_OPENS", "2025-12-01")
    assert advent.opens(2026) == date(2026, 12, 1)
    monkeypatch.setenv("ADVENT_CALENDAR_OPENS", "soon")
    assert advent.opens(2026) == date(2026, 12, 1)


# ---------------------------------------------------------------- pages

def test_page_is_hidden_before_opening(client, at):
    at(NOVEMBER)
    assert client.get("/holidays/advent-calendar").status_code == 404
    assert client.get("/holidays/advent-calendar/2026/1").status_code == 404
    assert client.get("/holidays/advent-calendar/2026/1/card.png").status_code == 404


def test_admins_can_preview_before_opening(authenticated_client, at, monkeypatch):
    at(NOVEMBER)
    monkeypatch.setattr(advent_router, "is_site_admin", lambda user: user is not None and user.username == "testuser")
    page = authenticated_client.get("/holidays/advent-calendar")
    assert page.status_code == 200
    assert "noindex" in page.headers.get("X-Robots-Tag", "")
    assert "Preview for site admins" in page.text and "It&#x27;s a Wonderful Life" in page.text


def test_page_shows_opened_doors_only(client, at):
    page = client.get("/holidays/advent-calendar")
    assert page.status_code == 200
    html = page.text
    assert "noindex" not in page.headers.get("X-Robots-Tag", "")
    for door in EDITIONS[2026]["doors"]:
        if door["day"] <= 6:
            assert f'id="door-{door["day"]}"' in html
        else:
            assert f'id="door-{door["day"]}"' not in html
            # Locked doors show their hint, never their pick.
            assert f'data-advent-locked="{door["day"]}"' in html
    assert "Moominland Midwinter" in html and "The Holdovers" not in html
    assert "/static/ad-loader.js" in html and "guest-list.js" in html
    assert "Sign up free" in html
    assert "/holidays/advent-calendar/2026/6/card.png" in html  # the newest door is the share image


def test_door_page_and_card(client, at):
    door = client.get("/holidays/advent-calendar/2026/4")
    assert door.status_code == 200
    assert "noindex" in door.headers.get("X-Robots-Tag", "")
    assert "Door 4: Klaus" in door.text and "/holidays/advent-calendar/2026/4/card.png" in door.text
    assert client.get("/holidays/advent-calendar/2026/7").status_code == 404
    assert client.get("/holidays/advent-calendar/2026/25").status_code == 404
    assert client.get("/holidays/advent-calendar/2025/1").status_code == 404
    card = client.get("/holidays/advent-calendar/2026/4/card.png")
    assert card.status_code == 200 and card.headers["content-type"] == "image/png"
    assert card.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_listed_beside_the_holiday_hub_once_open(client, at):
    from app import editorial_index
    from app.routers.seasonal import extra_links
    at(NOVEMBER)
    assert all(link["path"] != advent.BASE_PATH for link in extra_links("holidays"))
    assert all(piece["href"] != advent.BASE_PATH for piece in editorial_index.entries())
    assert advent.BASE_PATH not in client.get("/sitemap.xml").text
    at(DEC_5_NOON)
    assert extra_links("holidays")[0]["path"] == advent.BASE_PATH
    assert any(piece["href"] == advent.BASE_PATH for piece in editorial_index.entries())
    assert advent.BASE_PATH in client.get("/sitemap.xml").text
    assert "/holidays/advent-calendar/2026/" not in client.get("/sitemap.xml").text


# ---------------------------------------------------------------- members

def test_opening_doors_counts_toward_the_badge(authenticated_client, db_session, at):
    # Only unlocked doors count; repeats and doors from the future are ignored.
    opened = authenticated_client.post("/api/advent-calendar/2026/open", json={"days": [1, 2, 3, 3, 9, 30]})
    assert opened.status_code == 200
    data = opened.json()
    assert data["newly_opened"] == [1, 2, 3] and data["opened"] == [1, 2, 3]
    assert data["unlocked"] == [1, 2, 3, 4, 5, 6] and data["badge"]["count"] == 3 and data["badge"]["tier"] == 0
    again = authenticated_client.post("/api/advent-calendar/2026/open", json={"days": [3, 4, 5, 6]}).json()
    assert again["newly_opened"] == [4, 5, 6] and again["badge"]["tier"] == 1
    user = _user(db_session)
    stored = db_session.query(models.UserBadge).filter_by(user_id=user.id, badge="advent").one()
    assert stored.tier == 1
    assert db_session.query(models.Notification).filter_by(user_id=user.id, type="badge_earned").count() == 1
    state = authenticated_client.get("/api/advent-calendar/2026").json()
    assert state["opened"] == [1, 2, 3, 4, 5, 6] and state["reminder"] is False and state["has_device"] is False


def test_badge_counts_the_best_single_december(db_session, at):
    user = models.User(username="elf", email="elf@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.flush()
    for year, days in ((2025, range(1, 11)), (2026, range(1, 5))):
        for day in days:
            db_session.add(models.AdventDoor(user_id=user.id, year=year, day=day))
    db_session.commit()
    assert advent.most_doors(db_session, user.id) == 10
    assert badges.counts(db_session, user)["advent_doors"] == 10
    assert badges.tier_for(badges.BY_KEY["advent"], 24) == 3


def test_api_needs_an_open_calendar(authenticated_client, at):
    at(NOVEMBER)
    assert authenticated_client.get("/api/advent-calendar/2026").status_code == 404
    assert authenticated_client.post("/api/advent-calendar/2026/open", json={"days": [1]}).status_code == 404
    assert authenticated_client.get("/api/advent-calendar").json() == {"show": False}


def test_adding_a_pick_copies_title_year_and_creator(authenticated_client, db_session, at):
    added = authenticated_client.post("/api/advent-calendar/2026/doors/4/add")
    assert added.status_code == 200 and added.json()["state"] == "created"
    user = _user(db_session)
    movie = db_session.query(models.Movie).filter_by(user_id=user.id).one()
    assert (movie.title, movie.year, movie.director, movie.watched) == ("Klaus", 2019, "Sergio Pablos", False)
    assert added.json()["library"]["4"]["state"] == "tracked"
    assert authenticated_client.post("/api/advent-calendar/2026/doors/4/add").json()["state"] == "existing"
    assert db_session.query(models.Movie).filter_by(user_id=user.id).count() == 1
    # A manga door goes straight to the manga tracker.
    assert authenticated_client.post("/api/advent-calendar/2026/doors/1/add").json()["state"] == "created"
    manga = db_session.query(models.Manga).filter_by(user_id=user.id).one()
    assert manga.title == "Yotsuba&!"
    # A door that hasn't opened can't be added.
    assert authenticated_client.post("/api/advent-calendar/2026/doors/20/add").status_code == 404


def test_existing_library_titles_are_left_alone(authenticated_client, db_session, at):
    user = _user(db_session)
    db_session.add(models.Movie(user_id=user.id, title="klaus", year=2019, director="", watched=True, rating=9))
    db_session.commit()
    state = authenticated_client.get("/api/advent-calendar/2026").json()
    assert state["library"]["4"]["state"] == "done"
    assert authenticated_client.post("/api/advent-calendar/2026/doors/4/add").json()["state"] == "existing"
    movie = db_session.query(models.Movie).filter_by(user_id=user.id).one()
    assert (movie.title, movie.watched, movie.rating) == ("klaus", True, 9)


def test_guest_list_import_finds_opened_doors(at):
    found = advent.find("game", title_pages.title_slug("A Short Hike", 2019))
    assert found["title"] == "A Short Hike"
    assert advent.find("podcast", title_pages.title_slug("Song Exploder", 2014))["browse_kind"] == "podcasts"
    # Unopened doors are not importable yet.
    assert advent.find("movie", title_pages.title_slug("The Holdovers", 2023)) is None


def test_dashboard_card(authenticated_client, at):
    authenticated_client.post("/api/advent-calendar/2026/open", json={"days": [2]})
    card = authenticated_client.get("/api/advent-calendar").json()
    assert card["show"] and card["year"] == 2026 and card["opened_days"] == [2]
    assert [door["day"] for door in card["doors"]] == [1, 2, 3, 4, 5, 6]
    assert card["doors"][3] == {"day": 4, "date": "2026-12-04", "hint": EDITIONS[2026]["doors"][3]["hint"]}
    at(datetime(2027, 1, 2))
    assert authenticated_client.get("/api/advent-calendar").json() == {"show": False}


# ---------------------------------------------------------------- reminders

def _device(db_session, user, time_zone="America/New_York"):
    db_session.add(models.PushSubscription(user_id=user.id, endpoint="https://fcm.googleapis.com/fcm/send/abc",
                                           p256dh="x", auth="y"))
    db_session.add(models.PushPreference(user_id=user.id, time_zone=time_zone, quiet_hours=False))
    db_session.commit()


def test_reminder_switch(authenticated_client, db_session, at):
    on = authenticated_client.put("/api/advent-calendar/2026/reminder", json={"on": True}).json()
    assert on["reminder"] is True
    user = _user(db_session)
    row = db_session.query(models.AdventReminder).filter_by(user_id=user.id).one()
    # 7am Dec 5 in New York: door 5 is already out there, so it is never announced.
    assert row.last_day == 5
    off = authenticated_client.put("/api/advent-calendar/2026/reminder", json={"on": False}).json()
    assert off["reminder"] is False
    assert db_session.query(models.AdventReminder).count() == 0


def test_morning_reminder_goes_out_once_in_local_time(db_session, at, monkeypatch):
    user = models.User(username="rudolph", email="r@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.commit()
    _device(db_session, user)
    db_session.add(models.AdventReminder(user_id=user.id, year=2026, last_day=5))
    db_session.commit()
    sent = []
    monkeypatch.setattr(web_push, "deliver", lambda db, messages, http=None, now=None: sent.extend(messages) or {"sent": len(messages)})
    # 7am in New York on December 6: too early.
    at(datetime(2026, 12, 6, 12, 0))
    assert advent.send_reminders(db_session)["waiting"] == 1 and sent == []
    # 8am: door 6.
    at(datetime(2026, 12, 6, 13, 5))
    assert advent.send_reminders(db_session)["members"] == 1
    (user_id, kind, message, link), = sent
    assert (user_id, kind) == (user.id, "advent_door")
    assert message.startswith("Door 6 is open: A short book for a slow Sunday.")
    assert "Moomin" not in message and link.endswith("#door-6")
    # Not twice.
    assert advent.send_reminders(db_session)["members"] == 0 and len(sent) == 1
    # Away for a few days: missed doors are skipped, only today's is announced.
    at(datetime(2026, 12, 10, 14, 0))
    advent.send_reminders(db_session)
    assert len(sent) == 2 and sent[-1][2].startswith("Door 10 is open")
    assert db_session.query(models.AdventReminder).one().last_day == 10


def test_reminder_is_a_known_push_type():
    assert "advent_door" in web_push.TITLES
    assert web_push.topic_of("advent_door") is None  # only members who asked get it
