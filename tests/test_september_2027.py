"""The September 2027 challenge and Discover edition: nine works that classrooms teach, one per format, and the
"report" step that counts fifty words or more written about one of the month's finishes."""
from datetime import date, datetime
from html import unescape

import pytest

from app import advent_calendar_data, challenges, models, pick, title_pages
from app.discover_catalog import MONTHLY_EDITIONS, TRAILS, find_guest_pick, guest_fields, published_editions
from app.routers.collections import CATEGORIES

SEPTEMBER = MONTHLY_EDITIONS["september-2027"]
CHALLENGE = challenges.CHALLENGES["2027-09"]
EVENING = datetime(2027, 9, 10, 20, 0)
LATER = datetime(2027, 9, 12, 21, 0)
LONG_AGO = datetime(2025, 3, 1, 12, 0)
FIFTY = " ".join(f"word{index}" for index in range(50))


@pytest.fixture
def live(monkeypatch):
    """Publish the September edition now, whatever today's date is."""
    monkeypatch.setitem(SEPTEMBER, "published_date", "2026-01-01")
    return SEPTEMBER


def _user(db_session, username="testuser"):
    return db_session.query(models.User).filter(models.User.username == username).one()


def _member(db_session, name):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.flush()
    return user


def _row(db_session, user, model, title, finished=True, added_at=None, **fields):
    kind = next(kind for kind, spec in title_pages.KINDS.items() if spec[0] is model)
    row = model(user_id=user.id, title=title, **{title_pages.COMPLETE_FIELD[kind]: finished}, **fields)
    if added_at is not None:
        row.added_at = added_at
    db_session.add(row)
    db_session.commit()
    return row


def _finish(db_session, user, category, row, when=EVENING, title=None, note=None, action="completed"):
    db_session.add(models.ActivityEntry(user_id=user.id, category=category, item_id=row.id if row else None,
                                        title=row.title if row else title, action=action,
                                        occurred_at=when, note=note))
    db_session.commit()


def _moment(db_session, user, category, row, takeaway, when=EVENING):
    db_session.add(models.CompletionMoment(user_id=user.id, category=category, item_id=row.id, title=row.title,
                                           takeaway=takeaway, completed_at=when))
    db_session.commit()


def _report(db_session, user):
    return challenges.progress(db_session, user.id, "2027-09")[2]


def test_the_edition_and_challenge_go_live_on_september_first():
    assert "september-2027" not in published_editions(date(2027, 8, 31))
    assert "september-2027" in published_editions(date(2027, 9, 1))
    assert challenges.public_months(date(2027, 8, 31))[0] == "2027-08"
    assert challenges.public_months(date(2027, 9, 1))[0] == "2027-09"
    assert CHALLENGE["edition"] == "september-2027" and "revisits_count" not in CHALLENGE
    assert [step["kind"] for step in CHALLENGE["steps"]] == ["edition", "waiting", "report"]
    assert (CHALLENGE["steps"][2]["count"], CHALLENGE["steps"][2]["words"]) == (1, 50)
    assert CHALLENGE["published"] == SEPTEMBER["published_date"] == "2027-09-01"


def test_nine_picks_one_per_format_each_saying_where_it_was_taught():
    items = SEPTEMBER["items"]
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
        classroom = item["classroom"]
        # "Movie, taught <where>" on the challenge page.
        assert classroom["where"] and classroom["where"][0].islower(), item["title"]
        assert len(classroom["note"].split()) >= 30, item["title"]
        # Only one kind of extra line per pick.
        assert "shadow" not in item and "other" not in item


def test_no_pick_repeats_another_edition_trail_or_advent_door():
    mine = {title_pages.slugify(item["title"]) for item in SEPTEMBER["items"]}
    elsewhere = {title_pages.slugify(item["title"]) for slug, edition in MONTHLY_EDITIONS.items()
                 if slug != "september-2027" for item in edition["items"]}
    elsewhere |= {title_pages.slugify(item["title"]) for trail in TRAILS.values() for item in trail["items"]}
    elsewhere |= {title_pages.slugify(door["title"]) for edition in advent_calendar_data.EDITIONS.values()
                  for door in edition["doors"]}
    assert not elsewhere & mine


def test_edition_page_shows_all_nine_with_their_classrooms(client, monkeypatch, live):
    page = client.get("/discover/monthly/september-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert SEPTEMBER["essay_title"] in text and "If you read it at school" in text
    assert text.count("In the classroom:") == 9
    for item in SEPTEMBER["items"]:
        assert item["title"] in text
        assert item["classroom"]["note"] in text
    for kind in ("manga", "podcast", "audiobook"):
        assert f'data-guest-kind="{kind}"' in page.text
    assert SEPTEMBER["name"] in unescape(client.get("/discover").text)
    # The August edition still names its famous works and nothing about classrooms.
    monkeypatch.setitem(MONTHLY_EDITIONS["august-2027"], "published_date", "2026-01-01")
    august = unescape(client.get("/discover/monthly/august-2027").text)
    assert "In the shadow of" in august and "In the classroom:" not in august


def test_saving_the_whole_edition_fills_every_format(authenticated_client, db_session, live):
    keys = [item["key"] for item in SEPTEMBER["items"]]
    saved = authenticated_client.post("/api/discover/monthly/september-2027/save", json={"keys": keys})
    assert saved.status_code == 200, saved.text
    assert saved.json()["created"] == 9
    assert authenticated_client.post("/api/discover/monthly/september-2027/save", json={"keys": keys}).json()["created"] == 0
    user = _user(db_session)
    game = db_session.query(models.VideoGame).filter_by(user_id=user.id).one()
    assert game.title == "The Oregon Trail" and game.release_date == datetime(1985, 1, 1)
    audiobook = db_session.query(models.Audiobook).filter_by(user_id=user.id).one()
    assert (audiobook.title, audiobook.author, audiobook.narrator, audiobook.year, audiobook.length_hours) == (
        "The Odyssey", "Homer", "Claire Danes", 2018, 13.53)
    assert db_session.query(models.Podcast).filter_by(user_id=user.id).one().host == "Robert Smith"
    assert db_session.query(models.Music).filter_by(user_id=user.id).one().artist == "Kendrick Lamar"
    assert db_session.query(models.Manga).filter_by(user_id=user.id).one().author == "Keiji Nakazawa"
    film = db_session.query(models.Movie).filter_by(user_id=user.id).one()
    assert (film.title, film.director, film.year) == ("12 Angry Men", "Sidney Lumet", 1957)
    assert db_session.query(models.Book).filter_by(user_id=user.id).one().author == "William Golding"


def test_pick_for_me_keeps_its_six_formats(live):
    entries = {entry["title"]: entry for entry in pick.pool() if entry["source_url"] == "/discover/monthly/september-2027"}
    assert {"12 Angry Men", "The Wire", "Cells at Work!", "Lord of the Flies", "To Pimp a Butterfly"} <= set(entries)
    assert entries["The Oregon Trail"]["year"] == 1985
    assert "Barefoot Gen" not in entries and "The Odyssey" not in entries


def test_a_guest_saved_audiobook_moves_in_with_its_reader(authenticated_client, db_session, live):
    audiobook = next(item for item in SEPTEMBER["items"] if item["category"] == "audiobooks")
    fields = guest_fields(audiobook)
    assert find_guest_pick(fields["kind"], fields["slug"])["creator"] == "Homer"
    response = authenticated_client.post("/api/guest-list/import", json={"items": [{"kind": fields["kind"], "slug": fields["slug"]}]})
    assert response.status_code == 200, response.text
    row = db_session.query(models.Audiobook).filter_by(user_id=_user(db_session).id).one()
    assert (row.title, row.year) == ("The Odyssey", 2018)


def test_a_pick_saved_under_another_name_still_counts(db_session):
    for name, model, category, title in (("juror", models.Movie, "movies", "Twelve Angry Men"),
                                         ("platelet", models.Anime, "anime", "Hataraku Saibō"),
                                         ("gen", models.Manga, "manga", "Hadashi no Gen")):
        user = _member(db_session, name)
        _finish(db_session, user, category, _row(db_session, user, model, title))
        assert challenges.progress(db_session, user.id, "2027-09")[0]["done"] is True, title


def test_report_words_count_words_not_punctuation():
    words = challenges.report_words
    assert words("Don't stop -- it's well-made, 1957!") == 5
    assert words("  ") == words(None) == words("") == words("— ... !!") == 0
    assert words("Ça va très bien, merci") == 5
    # Japanese and Chinese have no spaces, so two characters make a word.
    assert words("これは面白い本でした") == 5 and words("好") == 1
    assert words("Barefoot Gen はだしのゲン") == 2 + 3


def test_a_takeaway_and_a_review_add_up_to_a_report(db_session):
    user = _member(db_session, "student")
    book = _row(db_session, user, models.Book, "Lord of the Flies", author="William Golding",
                review=" ".join(["better"] * 25))
    _finish(db_session, user, "books", book)
    _moment(db_session, user, "books", book, " ".join(["piggy"] * 24))
    step = _report(db_session, user)
    assert step["kind"] == "report" and step["done"] is False and step["words"] == 50
    assert step["best"] == {"title": "Lord of the Flies", "category": "books", "id": book.id, "words": 49}
    # One more word anywhere hands it in, and the card stops suggesting.
    book.review = book.review + " still"
    db_session.commit()
    step = _report(db_session, user)
    assert step["done"] is True and (step["count"], step["target"]) == (1, 1) and step["best"] is None


def test_the_same_text_saved_twice_counts_once(db_session):
    user = _member(db_session, "copier")
    words = " ".join(["conch"] * 30)
    film = _row(db_session, user, models.Movie, "12 Angry Men")
    _finish(db_session, user, "movies", film, note=words)
    _moment(db_session, user, "movies", film, f"  {words.upper()} ")
    assert _report(db_session, user)["best"]["words"] == 30
    # A second journal finish with something new to say adds to it.
    _finish(db_session, user, "movies", film, when=LATER, note=" ".join(["jury"] * 20))
    assert _report(db_session, user)["done"] is True


def test_only_this_months_finishes_count(db_session):
    user = _member(db_session, "lastyear")
    # A long review on a title finished in August, and a long note on a title only noted in September.
    old = _row(db_session, user, models.Music, "To Pimp a Butterfly", review=FIFTY)
    _finish(db_session, user, "music", old, when=datetime(2027, 8, 20, 12, 0))
    noted = _row(db_session, user, models.Book, "Frankenstein", finished=False)
    _finish(db_session, user, "books", noted, note=FIFTY, action="noted")
    step = _report(db_session, user)
    assert step["done"] is False and step["best"] is None
    # A short September finish is named so the card can open it.
    game = _row(db_session, user, models.VideoGame, "The Oregon Trail")
    _finish(db_session, user, "video-games", game, note="Died of dysentery.")
    assert _report(db_session, user)["best"] == {"title": "The Oregon Trail", "category": "video-games",
                                                 "id": game.id, "words": 3}


def test_with_nothing_written_the_card_names_the_latest_finish(db_session):
    user = _member(db_session, "quiet")
    first = _row(db_session, user, models.TVShow, "The Wire")
    second = _row(db_session, user, models.Anime, "Cells at Work!")
    _finish(db_session, user, "tv-shows", first, when=EVENING)
    _finish(db_session, user, "anime", second, when=LATER)
    assert _report(db_session, user)["best"] == {"title": "Cells at Work!", "category": "anime",
                                                 "id": second.id, "words": 0}


def test_a_removed_copy_keeps_its_report(db_session):
    user = _member(db_session, "tidier")
    # Finished in September with a long journal note, then removed: the entry keeps the title, not the id.
    _finish(db_session, user, "podcasts", None, title="Planet Money Summer School", note=FIFTY)
    step = _report(db_session, user)
    assert step["done"] is True and step["best"] is None


def test_summer_reading_counts_titles_saved_before_september(db_session):
    user = _member(db_session, "summer")
    fresh = _row(db_session, user, models.Book, "A New Book", added_at=datetime(2027, 9, 3))
    _finish(db_session, user, "books", fresh)
    assert challenges.progress(db_session, user.id, "2027-09")[1]["done"] is False
    waiting = _row(db_session, user, models.Book, "Saved in June", added_at=datetime(2027, 6, 14))
    _finish(db_session, user, "books", waiting)
    assert challenges.progress(db_session, user.id, "2027-09")[1]["done"] is True


def test_the_card_payload_has_the_report_step_only_in_september(db_session):
    user = _member(db_session, "carded")
    payload = challenges.payload(db_session, user, today=date(2027, 9, 10))
    assert payload["name"] == "Required reading" and payload["url"] == "/challenges/september-2027"
    assert [step["kind"] for step in payload["steps"]] == ["edition", "waiting", "report"]
    assert payload["steps"][2]["words"] == 50 and payload["steps"][2]["best"] is None
    assert payload["days_left"] == 21
    assert all(step["kind"] != "report" for step in challenges.progress(db_session, user.id, "2027-08"))


def test_challenge_page_lists_the_nine_with_where_they_were_taught(client, monkeypatch, live):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-09")
    page = client.get("/challenges/september-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "The nine picks that count for step one" in text
    assert "Hand in a fifty-word report" in text and "Finish your summer reading" in text
    assert 'href="/discover/monthly/september-2027"' in page.text
    for item in SEPTEMBER["items"]:
        assert item["title"] in text
    assert "TV show, taught at Harvard" in text and "Movie, taught in British secondary schools" in text
    assert '"datePublished": "2027-09-01"' in page.text
    assert "so far" not in text


def test_a_shared_september_challenge_shows_steps_never_titles(client, db_session):
    user = _member(db_session, "sharer")
    book = _row(db_session, user, models.Book, "A Very Private Novel")
    _finish(db_session, user, "books", book, note="A private thought about a very private novel.")
    entry = models.MonthlyChallengeEntry(user_id=user.id, month="2027-09", completed_at=EVENING, share_token="sepsharetoken123")
    db_session.add(entry)
    db_session.commit()
    page = client.get("/challenge/sepsharetoken123")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "Hand in a fifty-word report" in text
    assert "Private Novel" not in text and "private thought" not in text


def test_before_september_first_the_challenge_is_hidden(client, monkeypatch):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-08")
    assert client.get("/challenges/september-2027").status_code == 404
    assert client.get("/discover/monthly/september-2027").status_code == 404


def test_essay_title_does_not_repeat_a_fixed_heading(client, live):
    page = unescape(client.get("/discover/monthly/september-2027").text)
    assert page.count(">Where to start<") <= 2
    assert SEPTEMBER["essay_title"] not in ("Where to start", "The picks", "If you read it at school")
