"""The July 2027 challenge and Discover edition: nine stories that exist in two formats, one per format, and
the "pair" step that counts a finish whose other version, in another format, the member has finished too."""
from datetime import date, datetime, timedelta
from html import unescape

import pytest

from app import advent_calendar_data, challenges, models, pick, title_pages
from app.discover_catalog import MONTHLY_EDITIONS, TRAILS, find_guest_pick, guest_fields, published_editions
from app.routers.collections import CATEGORIES

JULY = MONTHLY_EDITIONS["july-2027"]
CHALLENGE = challenges.CHALLENGES["2027-07"]
START, END = challenges.month_bounds("2027-07")
EVENING = datetime(2027, 7, 10, 20, 0)


@pytest.fixture
def live(monkeypatch):
    """Publish the July edition now, whatever today's date is."""
    monkeypatch.setitem(JULY, "published_date", "2026-01-01")
    return JULY


def _user(db_session, username="testuser"):
    return db_session.query(models.User).filter(models.User.username == username).one()


def _member(db_session, name):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.flush()
    return user


def _row(db_session, user, model, title, finished=True, added_at=None):
    kind = next(kind for kind, spec in title_pages.KINDS.items() if spec[0] is model)
    row = model(user_id=user.id, title=title, **{title_pages.COMPLETE_FIELD[kind]: finished})
    if added_at is not None:
        row.added_at = added_at
    db_session.add(row)
    db_session.commit()
    return row


def _finish(db_session, user, category, row, when=EVENING, title=None, note=None):
    db_session.add(models.ActivityEntry(user_id=user.id, category=category, item_id=row.id if row else None,
                                        title=row.title if row else title, action="completed",
                                        occurred_at=when, note=note))
    db_session.commit()


def _pair(db_session, user):
    return challenges.progress(db_session, user.id, "2027-07")[1]


def test_the_edition_and_challenge_go_live_on_july_first():
    assert "july-2027" not in published_editions(date(2027, 6, 30))
    assert "july-2027" in published_editions(date(2027, 7, 1))
    assert challenges.public_months(date(2027, 6, 30))[0] == "2027-06"
    assert challenges.public_months(date(2027, 7, 1))[0] == "2027-07"
    assert CHALLENGE["edition"] == "july-2027" and "revisits_count" not in CHALLENGE
    assert [step["kind"] for step in CHALLENGE["steps"]] == ["edition", "pair", "reflect"]
    assert CHALLENGE["steps"][1]["count"] == 1
    assert CHALLENGE["published"] == JULY["published_date"] == "2027-07-01"


def test_nine_picks_one_per_format_each_with_another_version():
    items = JULY["items"]
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
        other = item["other"]
        assert other["category"] in CATEGORIES and challenges._pairs_with(item["category"], other["category"]), item["title"]
        assert other["title"] and len(other["note"].split()) >= 30, item["title"]
    # The other versions spread over formats too: no format is the other version of more than three picks.
    others = [item["other"]["category"] for item in items]
    assert max(others.count(category) for category in others) <= 3


def test_no_pick_repeats_another_edition_trail_or_advent_door():
    mine = {title_pages.slugify(item["title"]) for item in JULY["items"]}
    elsewhere = {title_pages.slugify(item["title"]) for slug, edition in MONTHLY_EDITIONS.items() if slug != "july-2027"
                 for item in edition["items"]}
    elsewhere |= {title_pages.slugify(item["title"]) for trail in TRAILS.values() for item in trail["items"]}
    elsewhere |= {title_pages.slugify(door["title"]) for edition in advent_calendar_data.EDITIONS.values()
                  for door in edition["doors"]}
    assert not elsewhere & mine


def test_edition_page_shows_all_nine_with_their_other_versions(client, monkeypatch, live):
    page = client.get("/discover/monthly/july-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert JULY["essay_title"] in text and "Which one first" in text
    for item in JULY["items"]:
        assert item["title"] in text
        assert item["other"]["note"] in text
    assert "Pair it with the book:" in text and "Pair it with the TV show:" in text and "Pair it with the game:" in text
    for kind in ("manga", "podcast", "audiobook"):
        assert f'data-guest-kind="{kind}"' in page.text
    hub = unescape(client.get("/discover").text)
    assert JULY["name"] in hub
    # Editions without other versions render as before.
    monkeypatch.setitem(MONTHLY_EDITIONS["june-2027"], "published_date", "2026-01-01")
    june = client.get("/discover/monthly/june-2027")
    assert june.status_code == 200 and "Pair it with" not in june.text


def test_saving_the_whole_edition_fills_every_format(authenticated_client, db_session, live):
    keys = [item["key"] for item in JULY["items"]]
    saved = authenticated_client.post("/api/discover/monthly/july-2027/save", json={"keys": keys})
    assert saved.status_code == 200, saved.text
    assert saved.json()["created"] == 9
    assert authenticated_client.post("/api/discover/monthly/july-2027/save", json={"keys": keys}).json()["created"] == 0
    user = _user(db_session)
    game = db_session.query(models.VideoGame).filter_by(user_id=user.id).one()
    assert game.title == "80 Days" and game.release_date == datetime(2014, 1, 1)
    audiobook = db_session.query(models.Audiobook).filter_by(user_id=user.id).one()
    assert (audiobook.author, audiobook.year, audiobook.length_hours) == ("Taylor Jenkins Reid", 2019, 9.05)
    assert audiobook.narrator.startswith("Jennifer Beals, Pablo Schreiber")
    assert db_session.query(models.Podcast).filter_by(user_id=user.id).one().host == "Eli Horowitz, Micah Bloomberg"
    assert db_session.query(models.Music).filter_by(user_id=user.id).one().artist == "The Who"
    assert db_session.query(models.Manga).filter_by(user_id=user.id).one().author == "Katsuhiro Otomo"
    film = db_session.query(models.Movie).filter_by(user_id=user.id).one()
    assert (film.title, film.director, film.year) == ("Jaws", "Steven Spielberg", 1975)
    assert db_session.query(models.Book).filter_by(user_id=user.id).one().author == "Diana Wynne Jones"


def test_pick_for_me_keeps_its_six_formats(live):
    entries = {entry["title"]: entry for entry in pick.pool() if entry["source_url"] == "/discover/monthly/july-2027"}
    assert {"Jaws", "The Last of Us", "The Girl Who Leapt Through Time", "Howl's Moving Castle"} <= set(entries)
    assert entries["80 Days"]["year"] == 2014
    assert "Homecoming" not in entries and "Daisy Jones & The Six" not in entries


def test_a_guest_saved_podcast_moves_in_with_its_writers(authenticated_client, db_session, live):
    podcast = next(item for item in JULY["items"] if item["category"] == "podcasts")
    fields = guest_fields(podcast)
    assert find_guest_pick(fields["kind"], fields["slug"])["creator"] == "Eli Horowitz, Micah Bloomberg"
    response = authenticated_client.post("/api/guest-list/import", json={"items": [{"kind": fields["kind"], "slug": fields["slug"]}]})
    assert response.status_code == 200, response.text
    row = db_session.query(models.Podcast).filter_by(user_id=_user(db_session).id).one()
    assert (row.title, row.year) == ("Homecoming", 2016)


def test_a_pick_saved_under_another_name_still_counts(db_session):
    for name, model, category, title in (("bauer", models.TVShow, "tv-shows", "The Last of Us: Season 1"),
                                         ("makoto", models.Anime, "anime", "Toki o Kakeru Shoujo"),
                                         ("fogg", models.VideoGame, "video-games", "Eighty Days"),
                                         ("daisy", models.Audiobook, "audiobooks", "Daisy Jones and the Six")):
        user = _member(db_session, name)
        _finish(db_session, user, category, _row(db_session, user, model, title))
        assert challenges.progress(db_session, user.id, "2027-07")[0]["done"] is True, title


def test_story_keys_fold_seasons_parts_volumes_and_punctuation():
    key = challenges.story_key
    assert key("The Last of Us Part I") == key("The Last of Us: Season 1") == key("The Last of Us (season 1)") == "last of us"
    assert key("Dune: Part Two") == key("Dune (2021)") == "dune"
    assert key("Akira, Vol. 1") == key("AKIRA") == "akira"
    assert key("Attack on Titan: The Final Season") == "attack on titan"
    assert key("Howl's Moving Castle") == key("Howl’s Moving Castle") == key("Howls Moving Castle")
    assert key("Daisy Jones & The Six") == key("Daisy Jones and the Six")
    assert key("Cléo from 5 to 7") == "cleo from 5 to 7"
    # Words that are part of the name stay, and so does a title in another script.
    assert key("The Jungle Book") == "jungle book" and key("Rocky II") == "rocky ii"
    assert key("進撃の巨人") == "進撃の巨人"
    assert key("The") == "the" and key("") == ""


def test_the_film_of_a_book_read_years_ago_counts(db_session):
    user = _member(db_session, "reader")
    # Read long ago: marked finished in the library, nothing in the journal.
    _row(db_session, user, models.Book, "Dune")
    step = _pair(db_session, user)
    assert step["kind"] == "pair" and step["done"] is False and step["waiting"] == []
    _finish(db_session, user, "movies", _row(db_session, user, models.Movie, "Dune: Part One"))
    step = _pair(db_session, user)
    assert step["done"] is True and (step["count"], step["target"]) == (1, 1) and step["waiting"] == []


def test_both_versions_in_july_are_one_story(db_session):
    user = _member(db_session, "doubler")
    _finish(db_session, user, "manga", _row(db_session, user, models.Manga, "Frieren"), EVENING)
    _finish(db_session, user, "anime", _row(db_session, user, models.Anime, "Frieren: Beyond Journey's End"), EVENING)
    found = challenges.pair_progress(challenges._finishes(db_session, user.id, "2027-07"),
                                     challenges._library_rows(db_session, user.id))
    # The anime's longer title doesn't share the manga's name, so only an exact name or an edition pair counts.
    assert found["count"] == 0
    _finish(db_session, user, "anime", _row(db_session, user, models.Anime, "Frieren (2023)"), EVENING)
    found = challenges.pair_progress(challenges._finishes(db_session, user.id, "2027-07"),
                                     challenges._library_rows(db_session, user.id))
    assert found["count"] == 1


def test_a_book_and_its_audiobook_or_two_copies_in_one_format_do_not_pair(db_session):
    user = _member(db_session, "samewords")
    _row(db_session, user, models.Book, "Project Hail Mary")
    _finish(db_session, user, "audiobooks", _row(db_session, user, models.Audiobook, "Project Hail Mary"))
    _row(db_session, user, models.Movie, "Heat")
    _finish(db_session, user, "movies", _row(db_session, user, models.Movie, "Heat (1995)"))
    assert _pair(db_session, user)["done"] is False
    # The film of the same story does pair with the audiobook.
    _row(db_session, user, models.Movie, "Project Hail Mary")
    assert _pair(db_session, user)["done"] is True


def test_an_edition_pick_pairs_with_its_other_version_under_another_name(db_session):
    user = _member(db_session, "passepartout")
    _row(db_session, user, models.Book, "Around the World in Eighty Days")
    _finish(db_session, user, "video-games", _row(db_session, user, models.VideoGame, "80 Days"))
    steps = challenges.progress(db_session, user.id, "2027-07")
    assert steps[0]["done"] is True and steps[1]["done"] is True
    # Any version of the story counts, such as a film of it, and it works the other way round too.
    other = _member(db_session, "cinemagoer")
    _row(db_session, other, models.VideoGame, "Eighty Days")
    _finish(db_session, other, "movies", _row(db_session, other, models.Movie, "Around the World in 80 Days"))
    assert _pair(db_session, other)["done"] is True
    # The other version's name in the pick's own format is not a pair.
    third = _member(db_session, "gamer")
    _row(db_session, third, models.VideoGame, "Around the World in 80 Days")
    _finish(db_session, third, "video-games", _row(db_session, third, models.VideoGame, "80 Days"))
    assert _pair(db_session, third)["done"] is False


def test_a_removed_copy_still_pairs(db_session):
    user = _member(db_session, "tidier")
    _row(db_session, user, models.Anime, "Akira")
    # The manga was finished in July and later removed: its journal entry keeps the title, not the id.
    _finish(db_session, user, "manga", None, title="Akira")
    assert _pair(db_session, user)["done"] is True


def test_the_card_names_other_versions_waiting_in_the_library(db_session):
    user = _member(db_session, "waiter")
    _row(db_session, user, models.Book, "Dune")
    _row(db_session, user, models.Manga, "Akira")
    _row(db_session, user, models.Movie, "Dune", finished=False, added_at=datetime(2027, 6, 1))
    _row(db_session, user, models.Anime, "Akira", finished=False, added_at=datetime(2027, 6, 20))
    # Not a pair: the audiobook of a book already read, an unrelated title and a second unfinished copy.
    _row(db_session, user, models.Audiobook, "Dune", finished=False, added_at=datetime(2027, 6, 25))
    _row(db_session, user, models.TVShow, "Severance", finished=False, added_at=datetime(2027, 6, 26))
    _row(db_session, user, models.Anime, "Akira", finished=False, added_at=datetime(2027, 6, 2))
    step = _pair(db_session, user)
    assert step["waiting"] == [{"title": "Akira", "format": "anime", "with": "manga"},
                               {"title": "Dune", "format": "film", "with": "book"}]
    # No more than three, newest saves first.
    for index, title in enumerate(("Tommy", "Jaws", "Homecoming")):
        _row(db_session, user, models.Book, title)
        _row(db_session, user, models.Movie if title != "Homecoming" else models.TVShow, title, finished=False,
             added_at=datetime(2027, 6, 27 + index))
    assert [entry["title"] for entry in _pair(db_session, user)["waiting"]] == ["Homecoming", "Jaws", "Tommy"]
    # Once the step is done the card has nothing to suggest.
    _finish(db_session, user, "movies", db_session.query(models.Movie).filter_by(user_id=user.id, title="Dune").one())
    step = _pair(db_session, user)
    assert step["done"] is True and step["waiting"] == []


def test_the_card_payload_has_the_pair_step_only_in_july(db_session):
    user = _member(db_session, "carded")
    payload = challenges.payload(db_session, user, today=date(2027, 7, 10))
    assert payload["name"] == "Told twice" and payload["url"] == "/challenges/july-2027"
    assert [step["kind"] for step in payload["steps"]] == ["edition", "pair", "reflect"]
    assert payload["steps"][1]["waiting"] == []
    assert payload["days_left"] == 22
    assert all("waiting" not in step for step in challenges.progress(db_session, user.id, "2027-06"))


def test_reflect_step_counts_a_note_on_a_july_finish(db_session):
    user = _member(db_session, "noter")
    _finish(db_session, user, "books", _row(db_session, user, models.Book, "Jaws"), note="Hooper fares worse in print.")
    assert challenges.progress(db_session, user.id, "2027-07")[2]["done"] is True


def test_challenge_page_lists_the_nine_with_their_other_formats(client, monkeypatch, live):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-07")
    page = client.get("/challenges/july-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "The nine picks that count for step one" in text
    assert "Finish the other version of something" in text and "the same words" in text
    assert 'href="/discover/monthly/july-2027"' in page.text
    for item in JULY["items"]:
        assert item["title"] in text
    assert "Movie, with the book" in text and "Podcast, with the TV show" in text and "Album, with the movie" in text
    assert '"datePublished": "2027-07-01"' in page.text
    assert "In your library:" not in text


def test_a_shared_july_challenge_shows_steps_never_titles(client, db_session):
    user = _member(db_session, "sharer")
    _row(db_session, user, models.Book, "A Very Private Novel")
    _finish(db_session, user, "movies", _row(db_session, user, models.Movie, "A Very Private Novel"))
    entry = models.MonthlyChallengeEntry(user_id=user.id, month="2027-07", completed_at=EVENING, share_token="julysharetoken12")
    db_session.add(entry)
    db_session.commit()
    page = client.get("/challenge/julysharetoken12")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "Finish the other version of something" in text
    assert "A Very Private Novel" not in text


def test_before_july_first_the_challenge_is_hidden(client, monkeypatch):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-06")
    assert client.get("/challenges/july-2027").status_code == 404
    assert client.get("/discover/monthly/july-2027").status_code == 404


def test_essay_title_does_not_repeat_a_fixed_heading(client, live):
    page = unescape(client.get("/discover/monthly/july-2027").text)
    assert page.count(">Where to start<") <= 2
    assert JULY["essay_title"] not in ("Where to start", "The picks", "Which one first")
