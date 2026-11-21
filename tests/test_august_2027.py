"""The August 2027 challenge and Discover edition: nine works in the shadow of their maker's best-known one, one
per format, and the "maker" step that counts a finish by someone whose other work the member has finished too."""
from datetime import date, datetime
from html import unescape

import pytest

from app import advent_calendar_data, challenges, models, pick, title_metadata, title_pages
from app.discover_catalog import MONTHLY_EDITIONS, TRAILS, find_guest_pick, guest_fields, published_editions
from app.routers.collections import CATEGORIES

AUGUST = MONTHLY_EDITIONS["august-2027"]
CHALLENGE = challenges.CHALLENGES["2027-08"]
EVENING = datetime(2027, 8, 10, 20, 0)
LONG_AGO = datetime(2025, 3, 1, 12, 0)


@pytest.fixture
def live(monkeypatch):
    """Publish the August edition now, whatever today's date is."""
    monkeypatch.setitem(AUGUST, "published_date", "2026-01-01")
    return AUGUST


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


def _finish(db_session, user, category, row, when=EVENING, title=None, note=None):
    db_session.add(models.ActivityEntry(user_id=user.id, category=category, item_id=row.id if row else None,
                                        title=row.title if row else title, action="completed",
                                        occurred_at=when, note=note))
    db_session.commit()


def _credit(db_session, kind, title, role, name, year=None, entity="person"):
    key = title_metadata.cache_key(kind, title_pages.normalize(title), year)
    db_session.add(models.TitleCredit(metadata_key=key, kind=kind, entity=entity, role=role, name=name,
                                      slug=title_pages.slugify(name)))
    db_session.commit()


def _maker(db_session, user):
    return challenges.progress(db_session, user.id, "2027-08")[1]


def test_the_edition_and_challenge_go_live_on_august_first():
    assert "august-2027" not in published_editions(date(2027, 7, 31))
    assert "august-2027" in published_editions(date(2027, 8, 1))
    assert challenges.public_months(date(2027, 7, 31))[0] == "2027-07"
    assert challenges.public_months(date(2027, 8, 1))[0] == "2027-08"
    assert CHALLENGE["edition"] == "august-2027" and "revisits_count" not in CHALLENGE
    assert [step["kind"] for step in CHALLENGE["steps"]] == ["edition", "maker", "reflect"]
    assert CHALLENGE["steps"][1]["count"] == 1
    assert CHALLENGE["published"] == AUGUST["published_date"] == "2027-08-01"


def test_nine_picks_one_per_format_each_with_a_maker_and_a_shadow():
    items = AUGUST["items"]
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
        assert challenges.maker_key(item["maker"]), item["title"]
        # Where the format saves a creator, the pick's creator is its maker, so a saved pick matches on its own.
        creator = title_pages.KINDS[title_pages.LIBRARY_TO_KIND[item["category"]]][4]
        if creator:
            assert item["meta"][creator] == item["maker"], item["title"]
        shadow = item["shadow"]
        assert shadow["category"] in CATEGORIES and all(category in CATEGORIES for category in shadow.get("also", ()))
        assert challenges.story_key(shadow["title"]) != challenges.story_key(item["title"])
        assert shadow["title"] and len(shadow["note"].split()) >= 30, item["title"]


def test_no_pick_repeats_another_edition_trail_or_advent_door():
    mine = {title_pages.slugify(item["title"]) for item in AUGUST["items"]}
    elsewhere = {title_pages.slugify(item["title"]) for slug, edition in MONTHLY_EDITIONS.items() if slug != "august-2027"
                 for item in edition["items"]}
    elsewhere |= {title_pages.slugify(item["title"]) for trail in TRAILS.values() for item in trail["items"]}
    elsewhere |= {title_pages.slugify(door["title"]) for edition in advent_calendar_data.EDITIONS.values()
                  for door in edition["doors"]}
    assert not elsewhere & mine


def test_edition_page_shows_all_nine_with_the_famous_one_beside_each(client, monkeypatch, live):
    page = client.get("/discover/monthly/august-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert AUGUST["essay_title"] in text and "Before or after the famous one" in text
    for item in AUGUST["items"]:
        assert item["title"] in text
        assert f"In the shadow of {item['shadow']['title']}:" in text
        assert item["shadow"]["note"] in text
    for kind in ("manga", "podcast", "audiobook"):
        assert f'data-guest-kind="{kind}"' in page.text
    assert AUGUST["name"] in unescape(client.get("/discover").text)
    # The July edition still names its other versions, and June names neither.
    monkeypatch.setitem(MONTHLY_EDITIONS["july-2027"], "published_date", "2026-01-01")
    monkeypatch.setitem(MONTHLY_EDITIONS["june-2027"], "published_date", "2026-01-01")
    july = unescape(client.get("/discover/monthly/july-2027").text)
    assert "Pair it with the book:" in july and "In the shadow of" not in july
    june = client.get("/discover/monthly/june-2027").text
    assert "Pair it with" not in june and "In the shadow of" not in june


def test_saving_the_whole_edition_fills_every_format(authenticated_client, db_session, live):
    keys = [item["key"] for item in AUGUST["items"]]
    saved = authenticated_client.post("/api/discover/monthly/august-2027/save", json={"keys": keys})
    assert saved.status_code == 200, saved.text
    assert saved.json()["created"] == 9
    assert authenticated_client.post("/api/discover/monthly/august-2027/save", json={"keys": keys}).json()["created"] == 0
    user = _user(db_session)
    game = db_session.query(models.VideoGame).filter_by(user_id=user.id).one()
    assert game.title == "Transistor" and game.release_date == datetime(2014, 1, 1)
    audiobook = db_session.query(models.Audiobook).filter_by(user_id=user.id).one()
    assert (audiobook.author, audiobook.narrator, audiobook.year, audiobook.length_hours) == (
        "Toni Morrison", "Toni Morrison", 1973, 5.77)
    assert db_session.query(models.Podcast).filter_by(user_id=user.id).one().host == "Jad Abumrad"
    assert db_session.query(models.Music).filter_by(user_id=user.id).one().artist == "Fleetwood Mac"
    assert db_session.query(models.Manga).filter_by(user_id=user.id).one().author == "Hiromu Arakawa"
    film = db_session.query(models.Movie).filter_by(user_id=user.id).one()
    assert (film.title, film.director, film.year) == ("The Conversation", "Francis Ford Coppola", 1974)
    assert db_session.query(models.Book).filter_by(user_id=user.id).one().author == "Daphne du Maurier"


def test_pick_for_me_keeps_its_six_formats(live):
    entries = {entry["title"]: entry for entry in pick.pool() if entry["source_url"] == "/discover/monthly/august-2027"}
    assert {"The Conversation", "The Leftovers", "Kids on the Slope", "My Cousin Rachel", "Tusk"} <= set(entries)
    assert entries["Transistor"]["year"] == 2014
    assert "Silver Spoon" not in entries and "Sula" not in entries


def test_a_guest_saved_audiobook_moves_in_with_its_reader(authenticated_client, db_session, live):
    audiobook = next(item for item in AUGUST["items"] if item["category"] == "audiobooks")
    fields = guest_fields(audiobook)
    assert find_guest_pick(fields["kind"], fields["slug"])["creator"] == "Toni Morrison"
    response = authenticated_client.post("/api/guest-list/import", json={"items": [{"kind": fields["kind"], "slug": fields["slug"]}]})
    assert response.status_code == 200, response.text
    row = db_session.query(models.Audiobook).filter_by(user_id=_user(db_session).id).one()
    assert (row.title, row.year) == ("Sula", 1973)


def test_a_pick_saved_under_another_name_still_counts(db_session):
    for name, model, category, title in (("caul", models.Movie, "movies", "The Conversation (1974)"),
                                         ("kaoru", models.Anime, "anime", "Sakamichi no Apollon"),
                                         ("hachiken", models.Manga, "manga", "Gin no Saji")):
        user = _member(db_session, name)
        _finish(db_session, user, category, _row(db_session, user, model, title))
        assert challenges.progress(db_session, user.id, "2027-08")[0]["done"] is True, title


def test_maker_keys_fold_articles_accents_and_skip_placeholders():
    key = challenges.maker_key
    assert key("The Velvet Underground") == key("Velvet Underground") == "velvet-underground"
    assert key("Shinichirō Watanabe") == key("Shinichiro  Watanabe") == "shinichiro-watanabe"
    assert key("Various Artists") == key("Unknown") == key("") == key("   ") == ""
    names = challenges.maker_names
    assert names("podcast", "Joseph Fink, Jeffrey Cranor") == ["Joseph Fink", "Jeffrey Cranor"]
    assert names("movie", "Phil Lord & Christopher Miller") == ["Phil Lord", "Christopher Miller"]
    assert names("book", "Neil Gaiman and Terry Pratchett") == ["Neil Gaiman", "Terry Pratchett"]
    # A band keeps its commas and its ampersand; formats without a creator field have none.
    assert names("album", "Earth, Wind & Fire") == ["Earth, Wind & Fire"]
    assert names("tv", "Anyone") == [] and names("movie", None) == []


def test_a_second_film_by_a_director_seen_years_ago_counts(db_session):
    user = _member(db_session, "cinephile")
    # Seen long ago: marked finished in the library, nothing in the journal.
    _row(db_session, user, models.Movie, "Parasite", director="Bong Joon-ho", added_at=LONG_AGO)
    step = _maker(db_session, user)
    assert step["kind"] == "maker" and step["done"] is False
    _finish(db_session, user, "movies", _row(db_session, user, models.Movie, "Memories of Murder", director="bong joon-ho"))
    step = _maker(db_session, user)
    assert step["done"] is True and (step["count"], step["target"]) == (1, 1) and step["waiting"] == []


def test_one_name_among_several_makers_is_enough(db_session):
    user = _member(db_session, "listener")
    _row(db_session, user, models.Podcast, "Welcome to Night Vale", host="Joseph Fink, Jeffrey Cranor")
    _finish(db_session, user, "podcasts", _row(db_session, user, models.Podcast, "Within the Wires", host="Jeffrey Cranor"))
    assert _maker(db_session, user)["done"] is True
    # Another person who happens to share one word of a band's name is not the band.
    band = _member(db_session, "funk")
    _row(db_session, band, models.Music, "That's the Way of the World", artist="Earth, Wind & Fire")
    _finish(db_session, band, "music", _row(db_session, band, models.Music, "Fire", artist="Fire"))
    assert _maker(db_session, band)["done"] is False
    _finish(db_session, band, "music", _row(db_session, band, models.Music, "I Am", artist="Earth, Wind & Fire"))
    assert _maker(db_session, band)["done"] is True


def test_the_same_work_again_or_a_placeholder_name_does_not_count(db_session):
    user = _member(db_session, "samework")
    # The audiobook of a book already read, another volume of a manga and a second copy of an album.
    _row(db_session, user, models.Book, "Piranesi", author="Susanna Clarke")
    _finish(db_session, user, "audiobooks", _row(db_session, user, models.Audiobook, "Piranesi", author="Susanna Clarke"))
    _row(db_session, user, models.Manga, "Monster, Vol. 1", author="Naoki Urasawa")
    _finish(db_session, user, "manga", _row(db_session, user, models.Manga, "Monster, Vol. 2", author="Naoki Urasawa"))
    _row(db_session, user, models.Music, "Kind of Blue", artist="Miles Davis")
    _finish(db_session, user, "music", _row(db_session, user, models.Music, "Kind of Blue (Legacy Edition)", artist="Miles Davis"))
    _row(db_session, user, models.Music, "Now That's What I Call Music! 1", artist="Various Artists")
    _finish(db_session, user, "music", _row(db_session, user, models.Music, "Pure Moods", artist="Various Artists"))
    assert _maker(db_session, user)["done"] is False
    # A different book by the same author does count.
    _row(db_session, user, models.Book, "Jonathan Strange & Mr Norrell", author="Susanna Clarke")
    assert _maker(db_session, user)["done"] is True


def test_an_edition_pick_counts_with_the_famous_one_and_no_creator_saved(db_session):
    user = _member(db_session, "redfan")
    # Games save no creator: the edition's maker links Transistor to Hades.
    _row(db_session, user, models.VideoGame, "Hades II", added_at=LONG_AGO)
    _finish(db_session, user, "video-games", _row(db_session, user, models.VideoGame, "Transistor"))
    steps = challenges.progress(db_session, user.id, "2027-08")
    assert steps[0]["done"] is True and steps[1]["done"] is True
    # It works the other way round, and across the formats a shadow counts in (Rebecca on audio).
    other = _member(db_session, "manderley")
    _row(db_session, other, models.Book, "My Cousin Rachel")
    _finish(db_session, other, "audiobooks", _row(db_session, other, models.Audiobook, "Rebecca"))
    assert _maker(db_session, other)["done"] is True
    # The famous one's name in a format it doesn't count in is not the famous one.
    third = _member(db_session, "notthatone")
    _row(db_session, third, models.Movie, "Rumours")
    _finish(db_session, third, "music", _row(db_session, third, models.Music, "Tusk"))
    assert _maker(db_session, third)["done"] is False


def test_credits_on_title_pages_count_for_tv_anime_and_games(db_session):
    user = _member(db_session, "souls")
    _credit(db_session, "game", "Dark Souls", "Developer", "FromSoftware", entity="studio")
    _credit(db_session, "game", "Elden Ring", "Developer", "FromSoftware", year=2022, entity="studio")
    _row(db_session, user, models.VideoGame, "Dark Souls", added_at=LONG_AGO)
    _finish(db_session, user, "video-games", _row(db_session, user, models.VideoGame, "Elden Ring",
                                                  release_date=datetime(2022, 2, 25)))
    assert _maker(db_session, user)["done"] is True
    # Only the maker's credit counts: two series with the same actor are not by the same person.
    viewer = _member(db_session, "viewer")
    _credit(db_session, "tv", "Severance", "Cast", "Adam Scott")
    _credit(db_session, "tv", "Parks and Recreation", "Cast", "Adam Scott")
    _credit(db_session, "tv", "Watchmen", "Creator", "Damon Lindelof")
    _row(db_session, viewer, models.TVShow, "Parks and Recreation", added_at=LONG_AGO)
    _finish(db_session, viewer, "tv-shows", _row(db_session, viewer, models.TVShow, "Severance"))
    assert _maker(db_session, viewer)["done"] is False
    # A TV creator's credit links a series to Lost, the famous one the edition names for The Leftovers.
    _finish(db_session, viewer, "tv-shows", _row(db_session, viewer, models.TVShow, "Watchmen"))
    assert _maker(db_session, viewer)["done"] is False
    _row(db_session, viewer, models.TVShow, "Lost", added_at=LONG_AGO)
    assert _maker(db_session, viewer)["done"] is True


def test_a_removed_copy_still_counts(db_session):
    user = _member(db_session, "tidier")
    _row(db_session, user, models.Music, "Rumours", artist="Fleetwood Mac")
    # Tusk was finished in August and later removed: its journal entry keeps the title, not the id.
    _finish(db_session, user, "music", None, title="Tusk")
    assert _maker(db_session, user)["done"] is True


def test_the_card_names_titles_waiting_in_the_library(db_session):
    user = _member(db_session, "waiter")
    _row(db_session, user, models.Movie, "The Godfather", director="Francis Ford Coppola", added_at=LONG_AGO)
    _row(db_session, user, models.Book, "Rebecca", author="Daphne du Maurier", added_at=LONG_AGO)
    _row(db_session, user, models.Movie, "Apocalypse Now", director="Francis Ford Coppola", finished=False,
         added_at=datetime(2027, 7, 1))
    _row(db_session, user, models.Book, "My Cousin Rachel", author="Daphne du Maurier", finished=False,
         added_at=datetime(2027, 7, 20))
    # Not waiting: the audiobook of a book already read, an unrelated title and a second copy.
    _row(db_session, user, models.Audiobook, "Rebecca", author="Daphne du Maurier", finished=False,
         added_at=datetime(2027, 7, 25))
    _row(db_session, user, models.TVShow, "Severance", finished=False, added_at=datetime(2027, 7, 26))
    _row(db_session, user, models.Book, "My Cousin Rachel", author="Daphne du Maurier", finished=False,
         added_at=datetime(2027, 7, 2))
    step = _maker(db_session, user)
    assert step["waiting"] == [{"title": "My Cousin Rachel", "maker": "Daphne du Maurier"},
                               {"title": "Apocalypse Now", "maker": "Francis Ford Coppola"}]
    # No more than three, newest saves first; an edition pick needs no creator saved to be named.
    for index, title in enumerate(("Tusk", "Transistor", "Sula")):
        model = {"Tusk": models.Music, "Transistor": models.VideoGame, "Sula": models.Audiobook}[title]
        _row(db_session, user, model, title, finished=False, added_at=datetime(2027, 7, 27 + index))
    _row(db_session, user, models.Music, "Rumours", added_at=LONG_AGO)
    _row(db_session, user, models.VideoGame, "Hades", added_at=LONG_AGO)
    _row(db_session, user, models.Book, "Beloved", added_at=LONG_AGO)
    assert _maker(db_session, user)["waiting"] == [{"title": "Sula", "maker": "Toni Morrison"},
                                                   {"title": "Transistor", "maker": "Supergiant Games"},
                                                   {"title": "Tusk", "maker": "Fleetwood Mac"}]
    # Once the step is done the card has nothing to suggest.
    _finish(db_session, user, "movies", db_session.query(models.Movie).filter_by(user_id=user.id, title="Apocalypse Now").one())
    step = _maker(db_session, user)
    assert step["done"] is True and step["waiting"] == []


def test_the_card_payload_has_the_maker_step_only_in_august(db_session):
    user = _member(db_session, "carded")
    payload = challenges.payload(db_session, user, today=date(2027, 8, 10))
    assert payload["name"] == "Eclipsed" and payload["url"] == "/challenges/august-2027"
    assert [step["kind"] for step in payload["steps"]] == ["edition", "maker", "reflect"]
    assert payload["steps"][1]["waiting"] == []
    assert payload["days_left"] == 22
    assert all(step["kind"] != "maker" for step in challenges.progress(db_session, user.id, "2027-07"))


def test_reflect_step_counts_a_note_on_an_august_finish(db_session):
    user = _member(db_session, "noter")
    _finish(db_session, user, "music", _row(db_session, user, models.Music, "Tusk"), note="Better than Rumours. Fight me.")
    assert challenges.progress(db_session, user.id, "2027-08")[2]["done"] is True


def test_challenge_page_lists_the_nine_with_their_shadows(client, monkeypatch, live):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-08")
    page = client.get("/challenges/august-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "The nine picks that count for step one" in text
    assert "Finish something else by a creator you already know" in text and "same work" in text
    assert 'href="/discover/monthly/august-2027"' in page.text
    for item in AUGUST["items"]:
        assert item["title"] in text
    assert "Movie, in the shadow of The Godfather" in text and "Album, in the shadow of Rumours" in text
    assert '"datePublished": "2027-08-01"' in page.text
    assert "In your library:" not in text


def test_a_shared_august_challenge_shows_steps_never_titles(client, db_session):
    user = _member(db_session, "sharer")
    _row(db_session, user, models.Book, "A Very Private Novel", author="Somebody Private")
    _finish(db_session, user, "books", _row(db_session, user, models.Book, "Another Private Novel", author="Somebody Private"))
    entry = models.MonthlyChallengeEntry(user_id=user.id, month="2027-08", completed_at=EVENING, share_token="augsharetoken123")
    db_session.add(entry)
    db_session.commit()
    page = client.get("/challenge/augsharetoken123")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "Finish something else by a creator you already know" in text
    assert "Private Novel" not in text and "Somebody Private" not in text


def test_before_august_first_the_challenge_is_hidden(client, monkeypatch):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-07")
    assert client.get("/challenges/august-2027").status_code == 404
    assert client.get("/discover/monthly/august-2027").status_code == 404


def test_essay_title_does_not_repeat_a_fixed_heading(client, live):
    page = unescape(client.get("/discover/monthly/august-2027").text)
    assert page.count(">Where to start<") <= 2
    assert AUGUST["essay_title"] not in ("Where to start", "The picks", "Before or after the famous one")
