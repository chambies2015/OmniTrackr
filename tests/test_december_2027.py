"""The December 2027 challenge and Discover edition: nine time-travel stories, one per format, each naming its
time machine, and the "decades" step that counts the different decades of the titles a member finished in
December. The month's notes point to the holiday guides, Year in Review and the best-of lists instead of
repeating them."""
from datetime import date, datetime
from html import unescape

import pytest

from app import advent_calendar_data, challenges, models, pick, seasonal, title_pages
from app.discover_catalog import MONTHLY_EDITIONS, TRAILS, find_guest_pick, guest_fields, published_editions
from app.holiday_guides import GUIDES as COMPANIONS
from app.routers.collections import CATEGORIES
from app.seasonal_guides import SEASONS

DECEMBER = MONTHLY_EDITIONS["december-2027"]
CHALLENGE = challenges.CHALLENGES["2027-12"]
EVENING = datetime(2027, 12, 12, 20, 0)
NOVEMBER_NIGHT = datetime(2027, 11, 28, 21, 0)
EXTRAS = {"other", "maker", "shadow", "classroom", "bargain", "teller", "machine"}


@pytest.fixture
def live(monkeypatch):
    """Publish the December edition now, whatever today's date is."""
    monkeypatch.setitem(DECEMBER, "published_date", "2026-01-01")
    return DECEMBER


def _user(db_session, username="testuser"):
    return db_session.query(models.User).filter(models.User.username == username).one()


def _member(db_session, name):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.flush()
    return user


def _row(db_session, user, model, title, finished=False, **fields):
    kind = next(kind for kind, spec in title_pages.KINDS.items() if spec[0] is model)
    row = model(user_id=user.id, title=title, **{title_pages.COMPLETE_FIELD[kind]: finished}, **fields)
    db_session.add(row)
    db_session.commit()
    return row


def _finish(db_session, user, category, row, when=EVENING, rating=None, note=None):
    kind = title_pages.LIBRARY_TO_KIND[category]
    setattr(row, title_pages.COMPLETE_FIELD[kind], True)
    db_session.add(models.ActivityEntry(user_id=user.id, category=category, item_id=row.id, title=row.title,
                                        action="completed", occurred_at=when, rating=rating))
    db_session.commit()


def _decades(db_session, user):
    return challenges.progress(db_session, user.id, "2027-12")[1]


def test_the_edition_and_challenge_go_live_on_december_first():
    assert "december-2027" not in published_editions(date(2027, 11, 30))
    assert "december-2027" in published_editions(date(2027, 12, 1))
    assert challenges.public_months(date(2027, 11, 30))[0] == "2027-11"
    assert challenges.public_months(date(2027, 12, 1))[0] == "2027-12"
    assert CHALLENGE["edition"] == "december-2027" and "revisits_count" not in CHALLENGE
    assert [step["kind"] for step in CHALLENGE["steps"]] == ["edition", "decades", "reflect"]
    assert CHALLENGE["steps"][1]["count"] == 3 and CHALLENGE["steps"][2]["count"] == 1
    assert CHALLENGE["published"] == DECEMBER["published_date"] == "2027-12-01"
    # The whole 2027 run is written: every month has a challenge and an edition.
    for month in range(1, 13):
        key = f"2027-{month:02d}"
        assert key in challenges.CHALLENGES, key
        assert challenges.CHALLENGES[key]["edition"] in MONTHLY_EDITIONS, key


def test_nine_picks_one_per_format_each_naming_its_time_machine():
    items = DECEMBER["items"]
    assert [item["category"] for item in items] == list(CATEGORIES)
    assert len({item["key"] for item in items}) == 9
    for item in items:
        assert item["source"].startswith("https://")
        assert len(item["why"].split()) >= 80, item["title"]
        assert item["caveat"]
        model = CATEGORIES[item["category"]][0]
        assert all(hasattr(model, field) or (field == "year" and item["category"] == "video-games")
                   for field in item["meta"]), item["title"]
        assert guest_fields(item) is not None
        assert all(isinstance(alias, str) and alias for alias in item.get("aliases", []))
        assert isinstance(item["meta"]["year"], int)
        machine = item["machine"]
        # "Movie, by way of a dark cupboard" on the challenge page.
        assert machine["what"].startswith("a "), item["title"]
        assert len(machine["note"].split()) >= 30, item["title"]
        assert not (EXTRAS - {"machine"}) & set(item)


def test_the_nine_span_the_four_decades_the_step_and_notes_promise():
    decades = {challenges.decade_of(item["meta"]["year"]) for item in DECEMBER["items"]}
    assert decades == {1970, 1980, 1990, 2010}
    years = [item["meta"]["year"] for item in DECEMBER["items"]]
    first = next(item["title"] for item in DECEMBER["items"] if item["meta"]["year"] == min(years))
    last = next(item["title"] for item in DECEMBER["items"] if item["meta"]["year"] == max(years))
    span = f"from {first} in {min(years)} to {last} in {max(years)}"
    assert span in CHALLENGE["steps"][1]["detail"]
    assert any(span in paragraph for paragraph in DECEMBER["notes"]["paragraphs"])


def test_no_pick_repeats_another_edition_trail_hub_or_advent_door():
    mine = {(title_pages.LIBRARY_TO_KIND[item["category"]], title_pages.slugify(item["title"])) for item in DECEMBER["items"]}
    taken = {(title_pages.LIBRARY_TO_KIND[item["category"]], title_pages.slugify(item["title"]))
             for slug, edition in MONTHLY_EDITIONS.items() if slug != "december-2027" for item in edition["items"]}
    taken |= {(title_pages.LIBRARY_TO_KIND[item["category"]], title_pages.slugify(item["title"]))
              for trail in TRAILS.values() for item in trail["items"]}
    taken |= {(door["kind"], title_pages.slugify(door["title"])) for edition in advent_calendar_data.EDITIONS.values()
              for door in edition["doors"]}
    # The Christmas, winter and holiday guides especially: December's edition links them instead.
    for entry in (*SEASONS.values(), *COMPANIONS.values()):
        taken |= {(item["kind"], title_pages.slugify(item["title"])) for item in seasonal.picks(entry)}
    assert not taken & mine
    november = {item["meta"].get(field) for item in MONTHLY_EDITIONS["november-2027"]["items"]
                for field in ("director", "author", "artist", "host") if item["meta"].get(field)}
    assert not november & {item["meta"].get(field) for item in DECEMBER["items"]
                           for field in ("director", "author", "artist", "host") if item["meta"].get(field)}


def test_edition_page_shows_all_nine_with_their_machines_and_links(client, monkeypatch, live):
    page = client.get("/discover/monthly/december-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert DECEMBER["essay_title"] in text and "Setting the dial" in text
    assert text.count("The time machine:") == 9
    for item in DECEMBER["items"]:
        assert item["title"] in text
        assert item["machine"]["note"] in text
    for kind in ("manga", "podcast", "audiobook"):
        assert f'data-guest-kind="{kind}"' in page.text
    assert '<ul class="edition-links">' in page.text
    for href in ("/holidays", "/holidays/christmas", "/year-in-review", "/best-of", "/challenges/december-2027"):
        assert f'<a href="{href}">' in page.text, href
    assert DECEMBER["name"] in unescape(client.get("/discover").text)
    # November keeps its tellers and no time machines.
    monkeypatch.setitem(MONTHLY_EDITIONS["november-2027"], "published_date", "2026-01-01")
    november = unescape(client.get("/discover/monthly/november-2027").text)
    assert "Who's telling it:" in november and "The time machine:" not in november


def test_saving_the_whole_edition_fills_every_format(authenticated_client, db_session, live):
    keys = [item["key"] for item in DECEMBER["items"]]
    saved = authenticated_client.post("/api/discover/monthly/december-2027/save", json={"keys": keys})
    assert saved.status_code == 200, saved.text
    assert saved.json()["created"] == 9
    assert authenticated_client.post("/api/discover/monthly/december-2027/save", json={"keys": keys}).json()["created"] == 0
    user = _user(db_session)
    game = db_session.query(models.VideoGame).filter_by(user_id=user.id).one()
    assert game.title == "Chrono Trigger" and game.release_date == datetime(1995, 1, 1)
    audiobook = db_session.query(models.Audiobook).filter_by(user_id=user.id).one()
    assert (audiobook.title, audiobook.author, audiobook.narrator, audiobook.year, audiobook.length_hours) == (
        "11/22/63", "Stephen King", "Craig Wasson", 2011, 30.67)
    assert db_session.query(models.Podcast).filter_by(user_id=user.id).one().host == "Greg Jenner"
    music = db_session.query(models.Music).filter_by(user_id=user.id).one()
    assert (music.title, music.artist, music.year) == ("Time", "Electric Light Orchestra", 1981)
    assert db_session.query(models.Manga).filter_by(user_id=user.id).one().author == "Kei Sanbe"
    film = db_session.query(models.Movie).filter_by(user_id=user.id).one()
    assert (film.title, film.director, film.year) == ("About Time", "Richard Curtis", 2013)
    assert db_session.query(models.Book).filter_by(user_id=user.id).one().author == "Octavia E. Butler"
    assert db_session.query(models.TVShow).filter_by(user_id=user.id).one().year == 2017


def test_saving_the_edition_then_finishing_three_of_it_visits_three_decades(authenticated_client, db_session, live):
    keys = [item["key"] for item in DECEMBER["items"]]
    authenticated_client.post("/api/discover/monthly/december-2027/save", json={"keys": keys})
    user = _user(db_session)
    _finish(db_session, user, "books", db_session.query(models.Book).filter_by(user_id=user.id).one())
    _finish(db_session, user, "music", db_session.query(models.Music).filter_by(user_id=user.id).one())
    _finish(db_session, user, "video-games", db_session.query(models.VideoGame).filter_by(user_id=user.id).one())
    step = _decades(db_session, user)
    assert step["done"] is True and step["decades"] == [1970, 1980, 1990]


def test_pick_for_me_keeps_its_six_formats(live):
    entries = {entry["title"]: entry for entry in pick.pool() if entry["source_url"] == "/discover/monthly/december-2027"}
    assert {"About Time", "Dark", "Steins;Gate", "Kindred", "Time"} <= set(entries)
    assert entries["Chrono Trigger"]["year"] == 1995
    assert "Erased" not in entries and "11/22/63" not in entries


def test_a_guest_saved_audiobook_moves_in_with_its_author(authenticated_client, db_session, live):
    audiobook = next(item for item in DECEMBER["items"] if item["category"] == "audiobooks")
    fields = guest_fields(audiobook)
    assert find_guest_pick(fields["kind"], fields["slug"])["creator"] == "Stephen King"
    response = authenticated_client.post("/api/guest-list/import", json={"items": [{"kind": fields["kind"], "slug": fields["slug"]}]})
    assert response.status_code == 200, response.text
    row = db_session.query(models.Audiobook).filter_by(user_id=_user(db_session).id).one()
    assert (row.title, row.year) == ("11/22/63", 2011)


def test_a_pick_saved_under_another_name_still_counts(db_session):
    for name, model, category, title in (("satoru", models.Manga, "manga", "Boku dake ga Inai Machi"),
                                         ("okabe", models.Anime, "anime", "Steins Gate"),
                                         ("jonas", models.TVShow, "tv-shows", "Dark (German series)"),
                                         ("epping", models.Audiobook, "audiobooks", "11/22/63: A Novel")):
        user = _member(db_session, name)
        _finish(db_session, user, category, _row(db_session, user, model, title))
        assert challenges.progress(db_session, user.id, "2027-12")[0]["done"] is True, title


def test_a_decade_is_ten_years_starting_at_zero():
    assert challenges.decade_of(1987) == challenges.decade_of(1989) == 1980
    assert challenges.decade_of(1990) == 1990 and challenges.decade_of(2000) == 2000
    for year in (None, 0, 999, 2101, 19870, "1987", 1987.0, True):
        assert challenges.decade_of(year) is None, year


def test_three_decades_counts_each_decade_once(db_session):
    user = _member(db_session, "traveller")
    _finish(db_session, user, "movies", _row(db_session, user, models.Movie, "Back Then", year=1987))
    _finish(db_session, user, "books", _row(db_session, user, models.Book, "Also Back Then", year=1989))
    step = _decades(db_session, user)
    # 1987 and 1989 are one decade.
    assert step["kind"] == "decades" and (step["count"], step["target"]) == (1, 3) and step["done"] is False
    assert step["decades"] == [1980]
    # 1989 and 1990 are two.
    _finish(db_session, user, "music", _row(db_session, user, models.Music, "Turn Of", year=1990))
    assert _decades(db_session, user)["decades"] == [1980, 1990]
    # A game counts by its release date.
    _finish(db_session, user, "video-games", _row(db_session, user, models.VideoGame, "Newer", release_date=datetime(2024, 3, 1)))
    step = _decades(db_session, user)
    assert step["done"] is True and step["decades"] == [1980, 1990, 2020]
    # Done: nothing more is suggested.
    assert step["waiting"] == []


def test_titles_without_a_year_or_finished_outside_december_do_not_count(db_session):
    user = _member(db_session, "undated")
    _finish(db_session, user, "movies", _row(db_session, user, models.Movie, "No Year"))
    _finish(db_session, user, "books", _row(db_session, user, models.Book, "Typo Year", year=19870))
    _finish(db_session, user, "anime", _row(db_session, user, models.Anime, "November Finish", year=1975), when=NOVEMBER_NIGHT)
    _finish(db_session, user, "tv-shows", _row(db_session, user, models.TVShow, "January Finish", year=1965),
            when=datetime(2028, 1, 2, 12, 0))
    step = _decades(db_session, user)
    assert step["count"] == 0 and step["decades"] == []


def test_the_card_suggests_unfinished_titles_from_decades_not_yet_visited(db_session):
    user = _member(db_session, "planner")
    _finish(db_session, user, "movies", _row(db_session, user, models.Movie, "Visited", year=1984))
    # Same decade as the finish: not suggested.
    _row(db_session, user, models.Book, "Same Decade", year=1988)
    # Finished already: not suggested, whatever its decade.
    _row(db_session, user, models.Music, "Heard Already", finished=True, year=1962)
    _row(db_session, user, models.Anime, "Older Save", year=1999, added_at=datetime(2027, 1, 1))
    _row(db_session, user, models.TVShow, "Newer Save", year=1993, added_at=datetime(2027, 6, 1))
    _row(db_session, user, models.VideoGame, "A Game", release_date=datetime(2008, 5, 1), added_at=datetime(2027, 3, 1))
    _row(db_session, user, models.Podcast, "A Podcast", year=2015, added_at=datetime(2027, 2, 1))
    _row(db_session, user, models.Manga, "No Year Saved")
    step = _decades(db_session, user)
    assert step["decades"] == [1980]
    # One per decade, newest saves first, three at most, each the member's own title.
    assert step["waiting"] == [
        {"title": "Newer Save", "category": "tv-shows", "decade": 1990},
        {"title": "A Game", "category": "video-games", "decade": 2000},
        {"title": "A Podcast", "category": "podcasts", "decade": 2010},
    ]
    # Another member's library is never suggested.
    other = _member(db_session, "stranger")
    _row(db_session, other, models.Movie, "Not Mine", year=1950)
    assert all(row["title"] != "Not Mine" for row in _decades(db_session, user)["waiting"])
    assert _decades(db_session, other)["waiting"] == [{"title": "Not Mine", "category": "movies", "decade": 1950}]


def test_leave_a_note_for_next_december_counts_a_rating(db_session):
    user = _member(db_session, "noter")
    _finish(db_session, user, "movies", _row(db_session, user, models.Movie, "About Time", year=2013))
    steps = challenges.progress(db_session, user.id, "2027-12")
    assert steps[0]["done"] is True and steps[2]["done"] is False
    _finish(db_session, user, "books", _row(db_session, user, models.Book, "Kindred", year=1979), rating=9)
    assert challenges.progress(db_session, user.id, "2027-12")[2]["done"] is True


def test_the_card_payload_has_the_decades_step_only_in_december(db_session):
    user = _member(db_session, "carded")
    payload = challenges.payload(db_session, user, today=date(2027, 12, 10))
    assert payload["name"] == "Between the years" and payload["url"] == "/challenges/december-2027"
    assert [step["kind"] for step in payload["steps"]] == ["edition", "decades", "reflect"]
    assert payload["steps"][1]["decades"] == [] and payload["steps"][1]["waiting"] == []
    assert payload["days_left"] == 22
    assert all(step["kind"] != "decades" for step in challenges.progress(db_session, user.id, "2027-11"))


def test_challenge_page_lists_the_nine_with_their_machines_and_where_else_to_go(client, monkeypatch, live):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-12")
    page = client.get("/challenges/december-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "The nine picks that count for step one" in text
    assert "Visit three decades" in text and "Leave a note for next December" in text
    assert 'href="/discover/monthly/december-2027"' in page.text
    for item in DECEMBER["items"]:
        assert item["title"] in text
    assert "Movie, by way of a dark cupboard" in text and "Audiobook, by way of a diner's pantry" in text
    assert "Elsewhere on OmniTrackr this month" in text
    for href in ("/holidays", "/holidays/christmas", "/year-in-review", "/best-of"):
        assert f'href="{href}"' in page.text, href
    assert '"datePublished": "2027-12-01"' in page.text
    # The member's own titles never reach the public page.
    assert "In your library" not in text


def test_a_shared_december_challenge_shows_steps_never_titles(client, db_session):
    user = _member(db_session, "sharer")
    _finish(db_session, user, "books", _row(db_session, user, models.Book, "A Very Private Novel", year=1984))
    _row(db_session, user, models.Movie, "A Secret Old Film", year=1955)
    entry = models.MonthlyChallengeEntry(user_id=user.id, month="2027-12", completed_at=EVENING, share_token="decsharetoken123")
    db_session.add(entry)
    db_session.commit()
    page = client.get("/challenge/decsharetoken123")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "Visit three decades" in text
    assert "Private Novel" not in text and "Secret Old Film" not in text


def test_before_december_first_the_challenge_is_hidden(client, monkeypatch):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-11")
    assert client.get("/challenges/december-2027").status_code == 404
    assert client.get("/discover/monthly/december-2027").status_code == 404


def test_every_linked_page_exists(client, monkeypatch, live):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-12")
    for label, href in (*DECEMBER["notes"]["links"], *CHALLENGE["links"]):
        assert href.startswith("/") and label
        assert client.get(href, follow_redirects=False).status_code in (200, 302, 303), href


def test_essay_title_does_not_repeat_a_fixed_heading(client, live):
    page = unescape(client.get("/discover/monthly/december-2027").text)
    assert page.count(">Where to start<") <= 2
    assert DECEMBER["essay_title"] not in ("Where to start", "The picks", "Setting the dial")
