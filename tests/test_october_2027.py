"""The October 2027 challenge and Discover edition: nine stories about a wish granted at a price, one per format,
and the "draw" step that counts a title the member kept from the backlog draw and finished in October."""
from datetime import date, datetime
from html import unescape

import pytest

from app import advent_calendar_data, backlog_draw, challenges, models, pick, seasonal, title_pages
from app.discover_catalog import MONTHLY_EDITIONS, TRAILS, find_guest_pick, guest_fields, published_editions
from app.holiday_guides import GUIDES as COMPANIONS
from app.routers.collections import CATEGORIES
from app.seasonal_guides import SEASONS

OCTOBER = MONTHLY_EDITIONS["october-2027"]
CHALLENGE = challenges.CHALLENGES["2027-10"]
EVENING = datetime(2027, 10, 15, 20, 0)
SEPTEMBER_NIGHT = datetime(2027, 9, 28, 21, 0)
NOVEMBER_NIGHT = datetime(2027, 11, 2, 21, 0)


@pytest.fixture
def live(monkeypatch):
    """Publish the October edition now, whatever today's date is."""
    monkeypatch.setitem(OCTOBER, "published_date", "2026-01-01")
    return OCTOBER


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


def _finish(db_session, user, category, row, when=EVENING):
    kind = title_pages.LIBRARY_TO_KIND[category]
    setattr(row, title_pages.COMPLETE_FIELD[kind], True)
    db_session.add(models.ActivityEntry(user_id=user.id, category=category, item_id=row.id, title=row.title,
                                        action="completed", occurred_at=when))
    db_session.commit()


def _keep(db_session, user, category, row, when=EVENING, status="picked", night=None):
    draw = models.BacklogDraw(user_id=user.id, category=category, item_id=row.id, status=status, night=night,
                              picked_at=when, created_at=when)
    db_session.add(draw)
    db_session.commit()
    return draw


def _deal(db_session, user):
    return challenges.progress(db_session, user.id, "2027-10")[1]


def test_the_edition_and_challenge_go_live_on_october_first():
    assert "october-2027" not in published_editions(date(2027, 9, 30))
    assert "october-2027" in published_editions(date(2027, 10, 1))
    assert challenges.public_months(date(2027, 9, 30))[0] == "2027-09"
    assert challenges.public_months(date(2027, 10, 1))[0] == "2027-10"
    assert CHALLENGE["edition"] == "october-2027" and "revisits_count" not in CHALLENGE
    assert [step["kind"] for step in CHALLENGE["steps"]] == ["edition", "draw", "total"]
    assert CHALLENGE["steps"][1]["count"] == 1 and CHALLENGE["steps"][2]["count"] == 3
    assert CHALLENGE["published"] == OCTOBER["published_date"] == "2027-10-01"
    # Halloween 2027 is a Sunday.
    assert date(2027, 10, 31).strftime("%A") == "Sunday"


def test_nine_picks_one_per_format_each_naming_its_bargain():
    items = OCTOBER["items"]
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
        bargain = item["bargain"]
        # "Movie, a deal with <with>" on the challenge page.
        assert bargain["with"] and bargain["with"][0].islower(), item["title"]
        assert len(bargain["note"].split()) >= 30, item["title"]
        # Only one kind of extra line per pick.
        assert not {"classroom", "shadow", "other", "maker"} & set(item)


def test_no_pick_repeats_another_edition_trail_hub_or_advent_door():
    mine = {(title_pages.LIBRARY_TO_KIND[item["category"]], title_pages.slugify(item["title"])) for item in OCTOBER["items"]}
    taken = {(title_pages.LIBRARY_TO_KIND[item["category"]], title_pages.slugify(item["title"]))
             for slug, edition in MONTHLY_EDITIONS.items() if slug != "october-2027" for item in edition["items"]}
    taken |= {(title_pages.LIBRARY_TO_KIND[item["category"]], title_pages.slugify(item["title"]))
              for trail in TRAILS.values() for item in trail["items"]}
    taken |= {(door["kind"], title_pages.slugify(door["title"])) for edition in advent_calendar_data.EDITIONS.values()
              for door in edition["doors"]}
    # The Halloween hub especially: this edition is about bargains, not fright levels.
    for entry in (*SEASONS.values(), *COMPANIONS.values()):
        taken |= {(item["kind"], title_pages.slugify(item["title"])) for item in seasonal.picks(entry)}
    assert not taken & mine


def test_edition_page_shows_all_nine_with_their_bargains(client, monkeypatch, live):
    page = client.get("/discover/monthly/october-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert OCTOBER["essay_title"] in text and "Before you sign" in text
    assert text.count("The bargain:") == 9
    for item in OCTOBER["items"]:
        assert item["title"] in text
        assert item["bargain"]["note"] in text
    for kind in ("manga", "podcast", "audiobook"):
        assert f'data-guest-kind="{kind}"' in page.text
    assert OCTOBER["name"] in unescape(client.get("/discover").text)
    # The September edition still says where its picks were taught and nothing about bargains.
    monkeypatch.setitem(MONTHLY_EDITIONS["september-2027"], "published_date", "2026-01-01")
    september = unescape(client.get("/discover/monthly/september-2027").text)
    assert "In the classroom:" in september and "The bargain:" not in september


def test_saving_the_whole_edition_fills_every_format(authenticated_client, db_session, live):
    keys = [item["key"] for item in OCTOBER["items"]]
    saved = authenticated_client.post("/api/discover/monthly/october-2027/save", json={"keys": keys})
    assert saved.status_code == 200, saved.text
    assert saved.json()["created"] == 9
    assert authenticated_client.post("/api/discover/monthly/october-2027/save", json={"keys": keys}).json()["created"] == 0
    user = _user(db_session)
    game = db_session.query(models.VideoGame).filter_by(user_id=user.id).one()
    assert game.title == "Cult of the Lamb" and game.release_date == datetime(2022, 1, 1)
    audiobook = db_session.query(models.Audiobook).filter_by(user_id=user.id).one()
    assert (audiobook.title, audiobook.author, audiobook.narrator, audiobook.year) == (
        "The Screwtape Letters", "C. S. Lewis", "John Cleese", 1999)
    assert db_session.query(models.Podcast).filter_by(user_id=user.id).one().host == "Jonathan Sims"
    music = db_session.query(models.Music).filter_by(user_id=user.id).one()
    assert (music.title, music.artist, music.year) == ("King of the Delta Blues Singers", "Robert Johnson", 1961)
    assert db_session.query(models.Manga).filter_by(user_id=user.id).one().author == "CLAMP"
    film = db_session.query(models.Movie).filter_by(user_id=user.id).one()
    assert (film.title, film.director, film.year) == ("Death Becomes Her", "Robert Zemeckis", 1992)
    assert db_session.query(models.Book).filter_by(user_id=user.id).one().author == "Ray Bradbury"
    assert db_session.query(models.TVShow).filter_by(user_id=user.id).one().year == 1959


def test_pick_for_me_keeps_its_six_formats(live):
    entries = {entry["title"]: entry for entry in pick.pool() if entry["source_url"] == "/discover/monthly/october-2027"}
    assert {"Death Becomes Her", "The Twilight Zone", "Chainsaw Man", "Something Wicked This Way Comes",
            "King of the Delta Blues Singers"} <= set(entries)
    assert entries["Cult of the Lamb"]["year"] == 2022
    assert "xxxHolic" not in entries and "The Screwtape Letters" not in entries


def test_a_guest_saved_audiobook_moves_in_with_its_author(authenticated_client, db_session, live):
    audiobook = next(item for item in OCTOBER["items"] if item["category"] == "audiobooks")
    fields = guest_fields(audiobook)
    assert find_guest_pick(fields["kind"], fields["slug"])["creator"] == "C. S. Lewis"
    response = authenticated_client.post("/api/guest-list/import", json={"items": [{"kind": fields["kind"], "slug": fields["slug"]}]})
    assert response.status_code == 200, response.text
    row = db_session.query(models.Audiobook).filter_by(user_id=_user(db_session).id).one()
    assert (row.title, row.year) == ("The Screwtape Letters", 1999)


def test_a_pick_saved_under_another_name_still_counts(db_session):
    for name, model, category, title in (("archivist", models.Manga, "manga", "xxxHOLiC"),
                                         ("serling", models.TVShow, "tv-shows", "Twilight Zone"),
                                         ("denji", models.Anime, "anime", "Chensō Man")):
        user = _member(db_session, name)
        _finish(db_session, user, category, _row(db_session, user, model, title))
        assert challenges.progress(db_session, user.id, "2027-10")[0]["done"] is True, title


def test_a_kept_card_finished_in_october_takes_the_deal(db_session):
    user = _member(db_session, "dealt")
    film = _row(db_session, user, models.Movie, "Dune")
    other = _row(db_session, user, models.Book, "Never Dealt")
    _keep(db_session, user, "movies", film, when=datetime(2027, 10, 3, 19, 0))
    _finish(db_session, user, "books", other)
    step = _deal(db_session, user)
    assert step["kind"] == "draw" and step["done"] is False
    assert step["card"] == {"title": "Dune", "category": "movies", "night": None} and step["ready"] is False
    _finish(db_session, user, "movies", film)
    step = _deal(db_session, user)
    assert step["done"] is True and (step["count"], step["target"]) == (1, 1)
    # Done: the card names nothing more.
    assert step["card"] is None and step["ready"] is False


def test_a_card_counts_whatever_happened_to_it(db_session):
    for status in ("finished", "put_back", "replaced", "not_for_me"):
        user = _member(db_session, f"card_{status}")
        game = _row(db_session, user, models.VideoGame, f"Game {status}")
        # Kept in late September, finished in October: it still came from the draw.
        _keep(db_session, user, "video-games", game, when=SEPTEMBER_NIGHT, status=status)
        _finish(db_session, user, "video-games", game)
        assert _deal(db_session, user)["done"] is True, status


def test_a_card_only_counts_in_the_month_its_title_is_finished(db_session):
    user = _member(db_session, "early")
    book = _row(db_session, user, models.Book, "Finished in September")
    _keep(db_session, user, "books", book, when=datetime(2027, 9, 2, 19, 0), status="finished")
    _finish(db_session, user, "books", book, when=SEPTEMBER_NIGHT)
    assert _deal(db_session, user)["done"] is False
    # A card kept after October ended doesn't reach back into it.
    late = _member(db_session, "late")
    show = _row(db_session, late, models.TVShow, "Kept in November")
    _finish(db_session, late, "tv-shows", show)
    _keep(db_session, late, "tv-shows", show, when=NOVEMBER_NIGHT, status="finished")
    assert _deal(db_session, late)["done"] is False
    # Another member's card never counts.
    stranger = _member(db_session, "stranger")
    theirs = _row(db_session, stranger, models.TVShow, "Kept in November")
    _keep(db_session, user, "tv-shows", theirs, when=EVENING)
    _finish(db_session, stranger, "tv-shows", theirs)
    assert _deal(db_session, stranger)["done"] is False


def test_the_card_says_when_the_draw_can_deal(db_session):
    user = _member(db_session, "waiting")
    for title in ("One", "Two"):
        _row(db_session, user, models.Book, title)
    step = _deal(db_session, user)
    assert step["card"] is None and step["ready"] is False
    # Podcasts are never dealt, so they don't make up the three.
    _row(db_session, user, models.Podcast, "A Long Podcast")
    assert _deal(db_session, user)["ready"] is False
    _row(db_session, user, models.Movie, "Three")
    assert _deal(db_session, user)["ready"] is True


def test_a_card_with_a_night_says_which(db_session):
    user = _member(db_session, "planner")
    film = _row(db_session, user, models.Movie, "  Death Becomes Her ")
    _keep(db_session, user, "movies", film, night=date(2027, 10, 15))
    assert _deal(db_session, user)["card"] == {"title": "Death Becomes Her", "category": "movies", "night": "2027-10-15"}


def test_finishing_through_the_draw_card_counts(db_session, monkeypatch):
    user = _member(db_session, "through")
    rows = [_row(db_session, user, models.Movie, title) for title in ("A", "B", "C")]
    kept = backlog_draw.pick(db_session, user, "movies", rows[1].id, 0, date(2027, 10, 4), now=datetime(2027, 10, 4, 18, 0))
    assert kept.status == "picked"
    backlog_draw.answer(db_session, user, "finished", rating=8)
    # The draw's finish is written now; move it into October 2027 as if it had happened then.
    entry = db_session.query(models.ActivityEntry).filter_by(user_id=user.id, item_id=rows[1].id).one()
    entry.occurred_at = datetime(2027, 10, 9, 22, 0)
    db_session.query(models.CompletionMoment).filter_by(user_id=user.id, item_id=rows[1].id).update(
        {"completed_at": datetime(2027, 10, 9, 22, 0)})
    db_session.commit()
    steps = challenges.progress(db_session, user.id, "2027-10")
    assert steps[1]["done"] is True and steps[2]["count"] == 1


def test_three_wishes_means_three_finishes(db_session):
    user = _member(db_session, "wisher")
    for index, title in enumerate(("Death Becomes Her", "First", "Second")):
        _finish(db_session, user, "movies", _row(db_session, user, models.Movie, title), when=datetime(2027, 10, 5 + index, 20, 0))
    steps = challenges.progress(db_session, user.id, "2027-10")
    assert steps[0]["done"] is True and steps[2]["done"] is True and steps[2]["target"] == 3
    assert steps[1]["done"] is False


def test_the_card_payload_has_the_draw_step_only_in_october(db_session):
    user = _member(db_session, "carded")
    payload = challenges.payload(db_session, user, today=date(2027, 10, 10))
    assert payload["name"] == "At a price" and payload["url"] == "/challenges/october-2027"
    assert [step["kind"] for step in payload["steps"]] == ["edition", "draw", "total"]
    assert payload["steps"][1]["card"] is None and payload["steps"][1]["ready"] is False
    assert payload["days_left"] == 22
    assert all(step["kind"] != "draw" for step in challenges.progress(db_session, user.id, "2027-09"))


def test_challenge_page_lists_the_nine_with_who_the_deal_is_with(client, monkeypatch, live):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-10")
    page = client.get("/challenges/october-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "The nine picks that count for step one" in text
    assert "Take the deal" in text and "Make all three wishes" in text
    assert 'href="/discover/monthly/october-2027"' in page.text
    for item in OCTOBER["items"]:
        assert item["title"] in text
    assert "Game, a deal with a chained god" in text and "Movie, a deal with a woman who sells eternal youth" in text
    assert '"datePublished": "2027-10-01"' in page.text
    assert "Your card" not in text


def test_a_shared_october_challenge_shows_steps_never_titles(client, db_session):
    user = _member(db_session, "sharer")
    book = _row(db_session, user, models.Book, "A Very Private Novel")
    _keep(db_session, user, "books", book)
    _finish(db_session, user, "books", book)
    entry = models.MonthlyChallengeEntry(user_id=user.id, month="2027-10", completed_at=EVENING, share_token="octsharetoken123")
    db_session.add(entry)
    db_session.commit()
    page = client.get("/challenge/octsharetoken123")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "Take the deal" in text
    assert "Private Novel" not in text


def test_before_october_first_the_challenge_is_hidden(client, monkeypatch):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-09")
    assert client.get("/challenges/october-2027").status_code == 404
    assert client.get("/discover/monthly/october-2027").status_code == 404


def test_essay_title_does_not_repeat_a_fixed_heading(client, live):
    page = unescape(client.get("/discover/monthly/october-2027").text)
    assert page.count(">Where to start<") <= 2
    assert OCTOBER["essay_title"] not in ("Where to start", "The picks", "Before you sign")
