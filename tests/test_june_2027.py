"""The June 2027 challenge and Discover edition: nine stories that happen inside a single day, one per
format, and the "day" step that counts two finishes less than 24 hours apart."""
from datetime import date, datetime, timedelta
from html import unescape

import pytest

from app import advent_calendar_data, challenges, models, pick, title_pages
from app.discover_catalog import MONTHLY_EDITIONS, TRAILS, find_guest_pick, guest_fields, published_editions
from app.routers.collections import CATEGORIES

JUNE = MONTHLY_EDITIONS["june-2027"]
CHALLENGE = challenges.CHALLENGES["2027-06"]
START, END = challenges.month_bounds("2027-06")
EVENING = datetime(2027, 6, 12, 20, 0)


@pytest.fixture
def live(monkeypatch):
    """Publish the June edition now, whatever today's date is."""
    monkeypatch.setitem(JUNE, "published_date", "2026-01-01")
    return JUNE


def _user(db_session, username="testuser"):
    return db_session.query(models.User).filter(models.User.username == username).one()


def _member(db_session, name):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.flush()
    return user


def _row(db_session, user, model, title, finished=True):
    kind = next(kind for kind, spec in title_pages.KINDS.items() if spec[0] is model)
    row = model(user_id=user.id, title=title, **{title_pages.COMPLETE_FIELD[kind]: finished})
    db_session.add(row)
    db_session.commit()
    return row


def _finish(db_session, user, category, row, when, note=None, rating=None):
    db_session.add(models.ActivityEntry(user_id=user.id, category=category, item_id=row.id if row else None,
                                        title=row.title if row else "Gone Home", action="completed",
                                        occurred_at=when, note=note, rating=rating))
    db_session.commit()


def _day(db_session, user):
    return challenges.progress(db_session, user.id, "2027-06")[1]


def test_the_edition_and_challenge_go_live_on_june_first():
    assert "june-2027" not in published_editions(date(2027, 5, 31))
    assert "june-2027" in published_editions(date(2027, 6, 1))
    assert challenges.public_months(date(2027, 5, 31))[0] == "2027-05"
    assert challenges.public_months(date(2027, 6, 1))[0] == "2027-06"
    assert CHALLENGE["edition"] == "june-2027" and "revisits_count" not in CHALLENGE
    assert [step["kind"] for step in CHALLENGE["steps"]] == ["edition", "day", "reflect"]
    assert CHALLENGE["steps"][1]["count"] == 2 and CHALLENGE["steps"][1]["hours"] == 24
    assert CHALLENGE["published"] == JUNE["published_date"] == "2027-06-01"


def test_nine_picks_one_per_format():
    items = JUNE["items"]
    assert [item["category"] for item in items] == list(CATEGORIES)
    assert len({item["key"] for item in items}) == 9
    for item in items:
        assert item["source"].startswith("https://")
        assert len(item["why"].split()) >= 80, item["title"]
        assert item["caveat"]
        model = CATEGORIES[item["category"]][0]
        # A game's year is saved as its release date.
        assert all(hasattr(model, field) or (field == "year" and item["category"] == "video-games")
                   for field in item["meta"]), item["title"]
        assert guest_fields(item) is not None
        assert all(isinstance(alias, str) and alias for alias in item.get("aliases", []))
        assert isinstance(item["meta"]["year"], int)


def test_no_pick_repeats_another_edition_trail_or_advent_door():
    mine = {title_pages.slugify(item["title"]) for item in JUNE["items"]}
    elsewhere = {title_pages.slugify(item["title"]) for slug, edition in MONTHLY_EDITIONS.items() if slug != "june-2027"
                 for item in edition["items"]}
    elsewhere |= {title_pages.slugify(item["title"]) for trail in TRAILS.values() for item in trail["items"]}
    elsewhere |= {title_pages.slugify(door["title"]) for edition in advent_calendar_data.EDITIONS.values()
                  for door in edition["doors"]}
    assert not elsewhere & mine


def test_edition_page_shows_all_nine_with_guest_saves(client, live):
    page = client.get("/discover/monthly/june-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert JUNE["essay_title"] in text and "Clocks and calendars" in text
    for item in JUNE["items"]:
        assert item["title"] in text
    for kind in ("manga", "podcast", "audiobook"):
        assert f'data-guest-kind="{kind}"' in page.text
    hub = unescape(client.get("/discover").text)
    assert JUNE["name"] in hub and "Nine media types" in hub


def test_saving_the_whole_edition_fills_every_format(authenticated_client, db_session, live):
    keys = [item["key"] for item in JUNE["items"]]
    saved = authenticated_client.post("/api/discover/monthly/june-2027/save", json={"keys": keys})
    assert saved.status_code == 200, saved.text
    assert saved.json()["created"] == 9
    assert authenticated_client.post("/api/discover/monthly/june-2027/save", json={"keys": keys}).json()["created"] == 0
    user = _user(db_session)
    game = db_session.query(models.VideoGame).filter_by(user_id=user.id).one()
    assert game.title == "Gone Home" and game.release_date == datetime(2013, 1, 1)
    audiobook = db_session.query(models.Audiobook).filter_by(user_id=user.id).one()
    assert (audiobook.author, audiobook.year, audiobook.length_hours) == ("George Saunders", 2017, 7.4)
    assert audiobook.narrator.startswith("Nick Offerman, David Sedaris")
    assert db_session.query(models.Podcast).filter_by(user_id=user.id).one().host == "Kevin Fong"
    assert db_session.query(models.Music).filter_by(user_id=user.id).one().artist == "The Moody Blues"
    assert db_session.query(models.Manga).filter_by(user_id=user.id).one().author == "Ryōsuke Takeuchi, Takeshi Obata"
    film = db_session.query(models.Movie).filter_by(user_id=user.id).one()
    assert (film.title, film.director, film.year) == ("Cléo from 5 to 7", "Agnès Varda", 1962)
    assert db_session.query(models.TVShow).filter_by(user_id=user.id).one().title == "24"


def test_pick_for_me_keeps_its_six_formats(live):
    entries = {entry["title"]: entry for entry in pick.pool() if entry["source_url"] == "/discover/monthly/june-2027"}
    assert {"Cléo from 5 to 7", "24", "The Night Is Short, Walk On Girl", "Mrs Dalloway"} <= set(entries)
    assert entries["Gone Home"]["year"] == 2013
    assert "13 Minutes to the Moon" not in entries and "Lincoln in the Bardo" not in entries


def test_a_guest_saved_podcast_moves_in_with_its_host(authenticated_client, db_session, live):
    podcast = next(item for item in JUNE["items"] if item["category"] == "podcasts")
    fields = guest_fields(podcast)
    assert find_guest_pick(fields["kind"], fields["slug"])["creator"] == "Kevin Fong"
    response = authenticated_client.post("/api/guest-list/import", json={"items": [{"kind": fields["kind"], "slug": fields["slug"]}]})
    assert response.status_code == 200, response.text
    row = db_session.query(models.Podcast).filter_by(user_id=_user(db_session).id).one()
    assert (row.title, row.year) == ("13 Minutes to the Moon", 2019)


def test_a_pick_saved_under_another_name_still_counts(db_session):
    for name, model, category, title in (("cleo", models.Movie, "movies", "Cleo from 5 to 7"),
                                         ("dalloway", models.Book, "books", "Mrs. Dalloway"),
                                         ("bauer", models.TVShow, "tv-shows", "24: Season 1"),
                                         ("kyoto", models.Anime, "anime", "Night Is Short, Walk On Girl")):
        user = _member(db_session, name)
        _finish(db_session, user, category, _row(db_session, user, model, title), EVENING)
        assert challenges.progress(db_session, user.id, "2027-06")[0]["done"] is True, title


def test_two_finishes_less_than_a_day_apart_count(db_session):
    user = _member(db_session, "longday")
    film = _row(db_session, user, models.Movie, "An Afternoon Film")
    _finish(db_session, user, "movies", film, EVENING)
    step = _day(db_session, user)
    assert step["kind"] == "day" and step["done"] is False and (step["count"], step["target"]) == (1, 2)
    assert step["hours"] == 24
    # Finishing the same title again the next morning is still one title.
    _finish(db_session, user, "movies", film, EVENING + timedelta(hours=12))
    assert _day(db_session, user)["count"] == 1
    # Across midnight, 23 hours later, in another format.
    _finish(db_session, user, "music", _row(db_session, user, models.Music, "A Late Album"), EVENING + timedelta(hours=23))
    step = _day(db_session, user)
    assert step["done"] is True and step["count"] == 2 and step["open"] is None


def test_finishes_a_day_or_more_apart_do_not_count(db_session):
    user = _member(db_session, "spread")
    _finish(db_session, user, "books", _row(db_session, user, models.Book, "Monday Book"), EVENING)
    _finish(db_session, user, "video-games", _row(db_session, user, models.VideoGame, "Tuesday Game"), EVENING + timedelta(hours=24))
    _finish(db_session, user, "anime", _row(db_session, user, models.Anime, "Friday Anime"), EVENING + timedelta(days=4))
    assert _day(db_session, user)["done"] is False
    # A May finish the night before June 1 is not a June finish, so it can't pair with one.
    other = _member(db_session, "lastofmay")
    _finish(db_session, other, "movies", _row(db_session, other, models.Movie, "May Film"), START - timedelta(hours=2))
    _finish(db_session, other, "movies", _row(db_session, other, models.Movie, "June Film"), START + timedelta(hours=2))
    assert _day(db_session, other)["count"] == 1


def test_a_removed_copy_keeps_its_finish_time(db_session):
    user = _member(db_session, "tidier")
    # A copy of Gone Home was finished on the 12th and later removed: its entry keeps the title, not the id.
    _finish(db_session, user, "video-games", None, EVENING)
    live_copy = _row(db_session, user, models.VideoGame, "Gone Home")
    _finish(db_session, user, "video-games", live_copy, EVENING + timedelta(days=10))
    _finish(db_session, user, "music", _row(db_session, user, models.Music, "Paired Album"), EVENING + timedelta(hours=3))
    finishes = challenges._finishes(db_session, user.id, "2027-06")
    assert sorted(finish["title"] for finish in finishes) == ["Gone Home", "Paired Album"]
    assert _day(db_session, user)["done"] is True


def test_the_open_window_says_what_to_pair_with_and_by_when():
    finishes = [{"title": "Gone Home", "times": [EVENING]}, {"title": "Earlier", "times": [EVENING - timedelta(days=3)]}]
    found = challenges.day_progress(finishes, "2027-06", now=EVENING + timedelta(hours=14))
    assert found == {"best": 1, "open": {"titles": ["Gone Home"], "count": 1, "until": "2027-06-13T20:00:00Z"}}
    # Once the day has passed, nothing is waiting.
    assert challenges.day_progress(finishes, "2027-06", now=EVENING + timedelta(hours=25))["open"] is None
    # Outside June there is no window to offer, and the best day is still counted.
    assert challenges.day_progress(finishes, "2027-06", now=datetime(2027, 7, 2))["open"] is None
    # A window never runs past the end of the month.
    late = [{"title": "Last Night", "times": [datetime(2027, 6, 30, 12)]}]
    assert challenges.day_progress(late, "2027-06", now=datetime(2027, 6, 30, 20))["open"]["until"] == "2027-07-01T00:00:00Z"
    # Done means no hint.
    pair = [{"title": "A", "times": [EVENING]}, {"title": "B", "times": [EVENING + timedelta(hours=1)]}]
    assert challenges.day_progress(pair, "2027-06", now=EVENING + timedelta(hours=2)) == {"best": 2, "open": None}


def test_three_in_a_day_needs_them_inside_one_window():
    times = [EVENING, EVENING + timedelta(hours=20), EVENING + timedelta(hours=30)]
    finishes = [{"title": str(index), "times": [when]} for index, when in enumerate(times)]
    assert challenges.day_progress(finishes, "2027-06", target=3, now=datetime(2027, 7, 1))["best"] == 2
    times.append(EVENING + timedelta(hours=35))
    finishes.append({"title": "3", "times": [times[-1]]})
    assert challenges.day_progress(finishes, "2027-06", target=3, now=datetime(2027, 7, 1))["best"] == 3


def test_the_card_payload_has_the_day_step_only_in_june(db_session):
    user = _member(db_session, "carded")
    payload = challenges.payload(db_session, user, today=date(2027, 6, 10))
    assert payload["name"] == "All in a day" and payload["url"] == "/challenges/june-2027"
    assert [step["kind"] for step in payload["steps"]] == ["edition", "day", "reflect"]
    assert payload["steps"][1]["hours"] == 24 and payload["steps"][1]["open"] is None
    assert payload["days_left"] == 21
    assert all("open" not in step for step in challenges.progress(db_session, user.id, "2027-05"))


def test_reflect_step_counts_a_note_on_a_june_finish(db_session):
    user = _member(db_session, "noter")
    _finish(db_session, user, "books", _row(db_session, user, models.Book, "Train Book"), EVENING,
            note="Finished it on the 8:10 train.")
    assert challenges.progress(db_session, user.id, "2027-06")[2]["done"] is True


def test_challenge_page_lists_the_nine_and_explains_the_step(client, monkeypatch, live):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-06")
    page = client.get("/challenges/june-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "The nine picks that count for step one" in text
    assert "Finish two things within a day" in text and "less than 24 hours apart" in text
    assert 'href="/discover/monthly/june-2027"' in page.text
    for item in JUNE["items"]:
        assert item["title"] in text
    assert '"datePublished": "2027-06-01"' in page.text
    assert "to go with" not in text


def test_a_shared_june_challenge_shows_steps_never_titles(client, db_session):
    user = _member(db_session, "sharer")
    _finish(db_session, user, "movies", _row(db_session, user, models.Movie, "A Very Private Film"), EVENING)
    _finish(db_session, user, "music", _row(db_session, user, models.Music, "A Private Album"), EVENING + timedelta(hours=2))
    entry = models.MonthlyChallengeEntry(user_id=user.id, month="2027-06", completed_at=EVENING, share_token="junesharetoken12")
    db_session.add(entry)
    db_session.commit()
    page = client.get("/challenge/junesharetoken12")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "Finish two things within a day" in text
    assert "A Very Private Film" not in text and "A Private Album" not in text


def test_before_june_first_the_challenge_is_hidden(client, monkeypatch):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-05")
    assert client.get("/challenges/june-2027").status_code == 404
    assert client.get("/discover/monthly/june-2027").status_code == 404


def test_essay_title_does_not_repeat_a_fixed_heading(client, live):
    page = unescape(client.get("/discover/monthly/june-2027").text)
    assert page.count(">Where to start<") <= 2
    assert JUNE["essay_title"] not in ("Where to start", "The picks", "Clocks and calendars")
