"""The May 2027 challenge and Discover edition: nine titles with a round birthday in 2027, one per
format and one per decade, and the "birthday" step that counts a finish released 10, 20, 30... years ago."""
from datetime import date, datetime, timedelta
from html import unescape

import pytest

from app import advent_calendar_data, challenges, models, pick, title_pages
from app.discover_catalog import MONTHLY_EDITIONS, TRAILS, find_guest_pick, guest_fields, published_editions
from app.routers.collections import CATEGORIES

MAY = MONTHLY_EDITIONS["may-2027"]
CHALLENGE = challenges.CHALLENGES["2027-05"]
START, END = challenges.month_bounds("2027-05")
DURING = START + timedelta(days=9)
BEFORE = START - timedelta(days=40)


@pytest.fixture
def live(monkeypatch):
    """Publish the May edition now, whatever today's date is."""
    monkeypatch.setitem(MAY, "published_date", "2026-01-01")
    return MAY


def _user(db_session, username="testuser"):
    return db_session.query(models.User).filter(models.User.username == username).one()


def _member(db_session, name):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.flush()
    return user


def _row(db_session, user, model, title, year=None, finished=True, added=None):
    kind = next(kind for kind, spec in title_pages.KINDS.items() if spec[0] is model)
    fields = {title_pages.COMPLETE_FIELD[kind]: finished}
    if year is not None:
        fields["release_date" if kind == "game" else "year"] = datetime(year, 6, 1) if kind == "game" else year
    if added is not None:
        fields["added_at"] = added
    row = model(user_id=user.id, title=title, **fields)
    db_session.add(row)
    db_session.commit()
    return row


def _finish(db_session, user, category, row, when=DURING, note=None, rating=None, action="completed"):
    db_session.add(models.ActivityEntry(user_id=user.id, category=category, item_id=row.id, title=row.title,
                                        action=action, occurred_at=when, note=note, rating=rating))
    db_session.commit()


def _birthday(db_session, user):
    return challenges.progress(db_session, user.id, "2027-05")[1]


def test_the_edition_and_challenge_go_live_on_may_first():
    assert "may-2027" not in published_editions(date(2027, 4, 30))
    assert "may-2027" in published_editions(date(2027, 5, 1))
    assert challenges.public_months(date(2027, 4, 30))[0] == "2027-04"
    assert challenges.public_months(date(2027, 5, 1))[0] == "2027-05"
    assert CHALLENGE["edition"] == "may-2027" and CHALLENGE["revisits_count"] is True
    assert [step["kind"] for step in CHALLENGE["steps"]] == ["edition", "birthday", "reflect"]
    assert CHALLENGE["published"] == MAY["published_date"] == "2027-05-01"


def test_nine_picks_one_per_format_and_one_per_decade():
    items = MAY["items"]
    assert [item["category"] for item in items] == list(CATEGORIES)
    assert len({item["key"] for item in items}) == 9
    assert sorted(2027 - item["meta"]["year"] for item in items) == [10, 20, 30, 40, 50, 60, 70, 80, 90]
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
        assert challenges._turns_round(item["meta"]["year"], "2027-05", 10)


def test_no_pick_repeats_another_edition_trail_or_advent_door():
    mine = {title_pages.slugify(item["title"]) for item in MAY["items"]}
    elsewhere = {title_pages.slugify(item["title"]) for slug, edition in MONTHLY_EDITIONS.items() if slug != "may-2027"
                 for item in edition["items"]}
    elsewhere |= {title_pages.slugify(item["title"]) for trail in TRAILS.values() for item in trail["items"]}
    elsewhere |= {title_pages.slugify(door["title"]) for edition in advent_calendar_data.EDITIONS.values()
                  for door in edition["doors"]}
    assert not elsewhere & mine


def test_edition_page_shows_all_nine_with_guest_saves(client, live):
    page = client.get("/discover/monthly/may-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert MAY["essay_title"] in text and "A birthday in every decade" in text
    for item in MAY["items"]:
        assert item["title"] in text
    for kind in ("manga", "podcast", "audiobook"):
        assert f'data-guest-kind="{kind}"' in page.text
    hub = unescape(client.get("/discover").text)
    assert MAY["name"] in hub and "Nine media types" in hub


def test_saving_the_whole_edition_fills_every_format_with_its_year(authenticated_client, db_session, live):
    keys = [item["key"] for item in MAY["items"]]
    saved = authenticated_client.post("/api/discover/monthly/may-2027/save", json={"keys": keys})
    assert saved.status_code == 200, saved.text
    assert saved.json()["created"] == 9
    assert authenticated_client.post("/api/discover/monthly/may-2027/save", json={"keys": keys}).json()["created"] == 0
    user = _user(db_session)
    game = db_session.query(models.VideoGame).filter_by(user_id=user.id).one()
    assert game.title == "Castlevania: Symphony of the Night" and game.release_date == datetime(1997, 1, 1)
    audiobook = db_session.query(models.Audiobook).filter_by(user_id=user.id).one()
    assert (audiobook.author, audiobook.narrator, audiobook.year) == ("John Steinbeck", "Gary Sinise", 1937)
    assert db_session.query(models.Podcast).filter_by(user_id=user.id).one().host == "Earlonne Woods, Nigel Poor"
    assert db_session.query(models.Music).filter_by(user_id=user.id).one().artist == "The Crickets"
    assert db_session.query(models.Movie).filter_by(user_id=user.id).one().year == 1977
    # Every saved pick has the year the birthday step reads.
    years = challenges._release_years(db_session, [
        {"category": category, "item_id": row.id}
        for category in CATEGORIES
        for row in db_session.query(CATEGORIES[category][0]).filter_by(user_id=user.id)
    ])
    assert sorted(2027 - year for year in years.values()) == [10, 20, 30, 40, 50, 60, 70, 80, 90]


def test_an_older_edition_game_without_a_year_still_saves(authenticated_client, db_session, monkeypatch):
    april = MONTHLY_EDITIONS["april-2027"]
    monkeypatch.setitem(april, "published_date", "2026-01-01")
    saved = authenticated_client.post("/api/discover/monthly/april-2027/save", json={"keys": ["undertale"]})
    assert saved.status_code == 200, saved.text
    game = db_session.query(models.VideoGame).filter_by(user_id=_user(db_session).id).one()
    assert game.title == "Undertale" and game.release_date is None


def test_pick_for_me_keeps_its_six_formats(live):
    entries = {entry["title"]: entry for entry in pick.pool() if entry["source_url"] == "/discover/monthly/may-2027"}
    assert {"Star Wars", "The Prisoner", "Den-noh Coil", "The Plague"} <= set(entries)
    assert entries["Castlevania: Symphony of the Night"]["year"] == 1997
    assert "Ear Hustle" not in entries and "Of Mice and Men" not in entries


def test_a_guest_saved_audiobook_moves_in_with_its_author_and_year(authenticated_client, db_session, live):
    audiobook = next(item for item in MAY["items"] if item["category"] == "audiobooks")
    fields = guest_fields(audiobook)
    assert find_guest_pick(fields["kind"], fields["slug"])["creator"] == "John Steinbeck"
    response = authenticated_client.post("/api/guest-list/import", json={"items": [{"kind": fields["kind"], "slug": fields["slug"]}]})
    assert response.status_code == 200, response.text
    row = db_session.query(models.Audiobook).filter_by(user_id=_user(db_session).id).one()
    assert (row.title, row.year) == ("Of Mice and Men", 1937)


def test_a_pick_saved_under_another_name_still_counts(db_session):
    user = _member(db_session, "newhope")
    film = _row(db_session, user, models.Movie, "Star Wars: Episode IV – A New Hope", year=1977)
    _finish(db_session, user, "movies", film)
    assert challenges.progress(db_session, user.id, "2027-05")[0]["done"] is True
    other = _member(db_session, "requiem")
    game = _row(db_session, other, models.VideoGame, "Castlevania Requiem", year=2018)
    _finish(db_session, other, "video-games", game)
    steps = challenges.progress(db_session, other.id, "2027-05")
    # The edition pick counts by name; the collection's 2018 date doesn't make it a birthday.
    assert steps[0]["done"] is True and steps[1]["done"] is False
    assert ("music", 'the “chirping” crickets') in challenges._edition_titles("may-2027")


def test_a_finish_released_a_round_number_of_years_ago_counts(db_session):
    user = _member(db_session, "decades")
    for title, year in (("Last Year", 2026), ("Brand New", 2027), ("Nine Years", 2018), ("No Year", None)):
        _finish(db_session, user, "books", _row(db_session, user, models.Book, title, year=year))
    step = _birthday(db_session, user)
    assert step["kind"] == "birthday" and step["done"] is False and step["count"] == 0
    _finish(db_session, user, "music", _row(db_session, user, models.Music, "Thirty Years", year=1997))
    step = _birthday(db_session, user)
    assert step["done"] is True and step["count"] == 1 and step["turning"] == []


def test_a_game_counts_by_its_release_date(db_session):
    user = _member(db_session, "gamer")
    _finish(db_session, user, "video-games", _row(db_session, user, models.VideoGame, "Close Call", year=2006))
    assert _birthday(db_session, user)["done"] is False
    _finish(db_session, user, "video-games", _row(db_session, user, models.VideoGame, "Twenty", year=2007))
    assert _birthday(db_session, user)["done"] is True


def test_only_may_finishes_count_and_a_logged_revisit_counts(db_session):
    user = _member(db_session, "returner")
    film = _row(db_session, user, models.Movie, "Star Wars", year=1977)
    _finish(db_session, user, "movies", film, when=BEFORE)
    assert [step["done"] for step in challenges.progress(db_session, user.id, "2027-05")] == [False, False, False]
    _finish(db_session, user, "movies", film, action="revisited", note="Better than I remembered.")
    assert [step["done"] for step in challenges.progress(db_session, user.id, "2027-05")] == [True, True, True]
    # April doesn't count revisits, so the same entry there would do nothing.
    assert "revisits_count" not in challenges.CHALLENGES["2027-04"]


def test_the_card_names_unfinished_library_titles_turning_a_round_number(db_session):
    user = _member(db_session, "shelves")
    other = _member(db_session, "someoneelse")
    now = datetime(2026, 11, 1)
    _row(db_session, user, models.Movie, "Fifty", year=1977, finished=False, added=now - timedelta(days=5))
    _row(db_session, user, models.TVShow, "Sixty", year=1967, finished=False, added=now - timedelta(days=1))
    _row(db_session, user, models.VideoGame, "Thirty", year=1997, finished=False, added=now - timedelta(days=3))
    _row(db_session, user, models.Anime, "Twenty", year=2007, finished=False, added=now - timedelta(days=9))
    _row(db_session, user, models.Book, "Already Read", year=1947, finished=True, added=now)
    _row(db_session, user, models.Manga, "Not Round", year=1988, finished=False, added=now)
    _row(db_session, other, models.Podcast, "Not Mine", year=2017, finished=False, added=now)
    step = _birthday(db_session, user)
    assert step["years"] == [2017, 2007, 1997, 1987]
    assert [(title["title"], title["age"]) for title in step["turning"]] == [("Sixty", 60), ("Thirty", 30), ("Fifty", 50)]
    assert step["turning"][1]["category"] == "video-games"


def test_the_card_payload_has_the_birthday_list_only_in_may(db_session):
    user = _member(db_session, "carded")
    _row(db_session, user, models.Podcast, "Ear Hustle", year=2017, finished=False)
    payload = challenges.payload(db_session, user, today=date(2027, 5, 10))
    assert payload["name"] == "Many happy returns" and payload["url"] == "/challenges/may-2027"
    assert [step["kind"] for step in payload["steps"]] == ["edition", "birthday", "reflect"]
    assert payload["steps"][1]["turning"] == [{"category": "podcasts", "id": payload["steps"][1]["turning"][0]["id"],
                                               "title": "Ear Hustle", "age": 10}]
    assert payload["days_left"] == 22
    assert all("turning" not in step for step in challenges.progress(db_session, user.id, "2027-04"))


def test_challenge_page_lists_the_nine_and_explains_the_step(client, monkeypatch, live):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-05")
    page = client.get("/challenges/may-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "The nine picks that count for step one" in text
    assert "Finish something that turns 10, 20, 30 or more this year" in text and "year ending in seven" in text
    assert 'href="/discover/monthly/may-2027"' in page.text
    for item in MAY["items"]:
        assert item["title"] in text
    assert '"datePublished": "2027-05-01"' in page.text
    assert "In your library:" not in text


def test_a_shared_may_challenge_shows_steps_never_titles(client, db_session):
    user = _member(db_session, "sharer")
    _row(db_session, user, models.TVShow, "A Very Private Title", year=1987, finished=False)
    film = _row(db_session, user, models.Movie, "Another Private Film", year=1977)
    _finish(db_session, user, "movies", film)
    entry = models.MonthlyChallengeEntry(user_id=user.id, month="2027-05", completed_at=DURING, share_token="maysharetoken123")
    db_session.add(entry)
    db_session.commit()
    page = client.get("/challenge/maysharetoken123")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "Finish something that turns 10, 20, 30 or more this year" in text
    assert "A Very Private Title" not in text and "Another Private Film" not in text


def test_before_may_first_the_challenge_is_hidden(client, monkeypatch):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-04")
    assert client.get("/challenges/may-2027").status_code == 404
    assert client.get("/discover/monthly/may-2027").status_code == 404


def test_essay_title_does_not_repeat_a_fixed_heading(client, live):
    page = unescape(client.get("/discover/monthly/may-2027").text)
    assert page.count(">Where to start<") <= 2
    assert MAY["essay_title"] not in ("Where to start", "The picks", "A birthday in every decade")


def test_birthday_years_follow_the_month():
    assert challenges.birthday_years("2027-05")[:3] == [2017, 2007, 1997]
    assert challenges.birthday_years("2028-01")[:2] == [2018, 2008]
    assert challenges.birthday_years("2027-05")[-1] >= challenges.BIRTHDAY_OLDEST
    assert not challenges._turns_round(None, "2027-05", 10)
    assert not challenges._turns_round(2027, "2027-05", 10)
    assert challenges._turns_round(1937, "2027-05", 10)
