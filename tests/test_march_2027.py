"""The March 2027 challenge and Discover edition: nine ways in, one per format, and the "stretch"
step that counts a finish in a format the member hardly ever finishes."""
from datetime import date, timedelta
from html import unescape

import pytest

from app import challenges, models, pick, title_pages
from app.discover_catalog import MONTHLY_EDITIONS, TRAILS, find_guest_pick, guest_fields, published_editions
from app.routers.collections import CATEGORIES

MARCH = MONTHLY_EDITIONS["march-2027"]
CHALLENGE = challenges.CHALLENGES["2027-03"]
START, END = challenges.month_bounds("2027-03")
DURING = START + timedelta(days=9)
BEFORE = START - timedelta(days=40)


@pytest.fixture
def live(monkeypatch):
    """Publish the March edition now, whatever today's date is."""
    monkeypatch.setitem(MARCH, "published_date", "2026-01-01")
    return MARCH


def _user(db_session, username="testuser"):
    return db_session.query(models.User).filter(models.User.username == username).one()


def _member(db_session, name):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.flush()
    return user


def _row(db_session, user, model, title, finished=False):
    field = title_pages.COMPLETE_FIELD[next(kind for kind, spec in title_pages.KINDS.items() if spec[0] is model)]
    row = model(user_id=user.id, title=title, **{field: finished})
    db_session.add(row)
    db_session.commit()
    return row


def _finish(db_session, user, category, row, when, note=None, rating=None):
    db_session.add(models.ActivityEntry(user_id=user.id, category=category, item_id=row.id, title=row.title,
                                        action="completed", occurred_at=when, note=note, rating=rating))
    db_session.commit()


def _stretch(db_session, user):
    return challenges.progress(db_session, user.id, "2027-03")[1]


def test_the_edition_and_challenge_go_live_on_march_first():
    assert "march-2027" not in published_editions(date(2027, 2, 28))
    assert "march-2027" in published_editions(date(2027, 3, 1))
    assert challenges.public_months(date(2027, 2, 28))[0] == "2027-02"
    assert challenges.public_months(date(2027, 3, 1))[0] == "2027-03"
    assert CHALLENGE["edition"] == "march-2027" and "revisits_count" not in CHALLENGE
    assert [step["kind"] for step in CHALLENGE["steps"]] == ["edition", "stretch", "reflect"]
    assert CHALLENGE["steps"][1]["under"] == 3


def test_nine_picks_one_per_format_none_repeated():
    items = MARCH["items"]
    assert [item["category"] for item in items] == list(CATEGORIES)
    assert len({item["key"] for item in items}) == 9
    for item in items:
        assert item["source"].startswith("https://")
        assert len(item["why"].split()) >= 80, item["title"]
        assert item["caveat"]
        model = CATEGORIES[item["category"]][0]
        assert all(hasattr(model, field) for field in item["meta"]), item["title"]
        assert guest_fields(item) is not None
        assert all(isinstance(alias, str) and alias for alias in item.get("aliases", []))
    elsewhere = {title_pages.slugify(item["title"]) for slug, edition in MONTHLY_EDITIONS.items() if slug != "march-2027"
                 for item in edition["items"]}
    elsewhere |= {title_pages.slugify(item["title"]) for trail in TRAILS.values() for item in trail["items"]}
    assert not elsewhere & {title_pages.slugify(item["title"]) for item in items}


def test_edition_page_shows_all_nine_with_guest_saves(client, live):
    page = client.get("/discover/monthly/march-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert MARCH["essay_title"] in text and "How the nine fit together" in text
    for item in MARCH["items"]:
        assert item["title"] in text
    for kind in ("manga", "podcast", "audiobook"):
        assert f'data-guest-kind="{kind}"' in page.text
    hub = unescape(client.get("/discover").text)
    assert MARCH["name"] in hub and "Nine media types" in hub


def test_saving_the_whole_edition_fills_every_format(authenticated_client, db_session, live):
    keys = [item["key"] for item in MARCH["items"]]
    saved = authenticated_client.post("/api/discover/monthly/march-2027/save", json={"keys": keys})
    assert saved.status_code == 200, saved.text
    assert saved.json()["created"] == 9
    assert authenticated_client.post("/api/discover/monthly/march-2027/save", json={"keys": keys}).json()["created"] == 0
    user = _user(db_session)
    assert db_session.query(models.Podcast).filter_by(user_id=user.id).one().host == "Sarah Koenig"
    audiobook = db_session.query(models.Audiobook).filter_by(user_id=user.id).one()
    assert (audiobook.author, audiobook.narrator) == ("Trevor Noah", "Trevor Noah")
    assert db_session.query(models.Manga).filter_by(user_id=user.id).one().author == "Naoki Urasawa"
    assert db_session.query(models.Music).filter_by(user_id=user.id).one().artist == "Glenn Gould"


def test_pick_for_me_keeps_its_six_formats(live):
    sources = {entry["title"] for entry in pick.pool() if entry["source_url"] == "/discover/monthly/march-2027"}
    assert {"Sherlock Jr.", "Call My Agent!", "Monument Valley", "Sailing Alone Around the Room"} <= sources
    assert "Pluto" not in sources and "Serial" not in sources


def test_a_guest_saved_podcast_moves_in_with_its_host(authenticated_client, db_session, live):
    podcast = next(item for item in MARCH["items"] if item["category"] == "podcasts")
    fields = guest_fields(podcast)
    assert find_guest_pick(fields["kind"], fields["slug"])["creator"] == "Sarah Koenig"
    response = authenticated_client.post("/api/guest-list/import", json={"items": [{"kind": fields["kind"], "slug": fields["slug"]}]})
    assert response.status_code == 200, response.text
    row = db_session.query(models.Podcast).filter_by(user_id=_user(db_session).id).one()
    assert (row.title, row.host, row.year) == ("Serial", "Sarah Koenig", 2014)


def test_a_pick_saved_under_its_longer_name_still_counts(db_session):
    user = _member(db_session, "longname")
    book = _row(db_session, user, models.Audiobook, "Born a Crime: Stories from a South African Childhood", finished=True)
    _finish(db_session, user, "audiobooks", book, DURING)
    assert challenges.progress(db_session, user.id, "2027-03")[0]["done"] is True
    # Another month's edition step is unaffected by March's other names.
    assert ("audiobooks", "born a crime") in challenges._edition_titles("march-2027")
    assert ("audiobooks", "born a crime") not in challenges._edition_titles("february-2027")


def test_a_new_member_can_stretch_into_any_format(db_session):
    user = _member(db_session, "newcomer")
    step = _stretch(db_session, user)
    assert step["kind"] == "stretch" and step["done"] is False
    assert step["formats"] == ["movies", "TV", "anime", "games", "albums", "books", "manga", "podcasts", "audiobooks"]
    film = _row(db_session, user, models.Movie, "Any Film", finished=True)
    _finish(db_session, user, "movies", film, DURING)
    assert _stretch(db_session, user)["done"] is True


def test_three_earlier_finishes_take_a_format_off_the_list(db_session):
    user = _member(db_session, "filmgoer")
    for number in range(3):
        _row(db_session, user, models.Movie, f"Old Film {number}", finished=True)
    for number in range(2):
        _row(db_session, user, models.Book, f"Old Book {number}", finished=True)
    _row(db_session, user, models.Manga, "Saved, Never Read")
    step = _stretch(db_session, user)
    assert "movies" not in step["formats"] and "books" in step["formats"] and "manga" in step["formats"]

    # Another film in March doesn't do the step; a third book does.
    film = _row(db_session, user, models.Movie, "March Film", finished=True)
    _finish(db_session, user, "movies", film, DURING)
    assert _stretch(db_session, user)["done"] is False
    book = _row(db_session, user, models.Book, "March Book", finished=True)
    _finish(db_session, user, "books", book, DURING)
    step = _stretch(db_session, user)
    assert step["done"] is True and step["count"] == 1


def test_finishes_this_month_never_count_against_the_format(db_session):
    user = _member(db_session, "binger")
    for number in range(4):
        volume = _row(db_session, user, models.Manga, f"First Manga {number}", finished=True)
        _finish(db_session, user, "manga", volume, DURING + timedelta(hours=number))
    step = _stretch(db_session, user)
    assert "manga" in step["formats"] and step["done"] is True


def test_earlier_journal_finishes_count_even_for_removed_titles(db_session):
    user = _member(db_session, "listener")
    for number in range(3):
        db_session.add(models.ActivityEntry(user_id=user.id, category="podcasts", item_id=None,
                                            title=f"Removed Show {number}", action="completed", occurred_at=BEFORE))
    db_session.add(models.CompletionMoment(user_id=user.id, category="music", item_id=-4,
                                           title="Removed Album", completed_at=BEFORE))
    db_session.commit()
    step = _stretch(db_session, user)
    assert "podcasts" not in step["formats"] and "albums" in step["formats"]
    # A finish logged after March began is this month's, not an earlier one.
    album = _row(db_session, user, models.Music, "First Album In Years", finished=True)
    _finish(db_session, user, "music", album, DURING)
    step = _stretch(db_session, user)
    assert "albums" in step["formats"] and step["done"] is True


def test_a_member_with_every_format_gets_their_least_finished_one(db_session):
    user = _member(db_session, "omnivore")
    counts = {models.Movie: 6, models.TVShow: 5, models.Anime: 4, models.VideoGame: 4, models.Music: 7,
              models.Book: 5, models.Manga: 3, models.Podcast: 4, models.Audiobook: 3}
    for model, count in counts.items():
        for number in range(count):
            _row(db_session, user, model, f"{model.__name__} {number}", finished=True)
    assert _stretch(db_session, user)["formats"] == ["manga", "audiobooks"]


def test_a_new_format_pick_with_a_note_does_all_three_steps(db_session):
    user = _member(db_session, "firsttimer")
    for number in range(3):
        _row(db_session, user, models.Movie, f"Film {number}", finished=True)
    game = _row(db_session, user, models.VideoGame, "Monument Valley", finished=True)
    _finish(db_session, user, "video-games", game, DURING, note="Would play another this short.")
    assert [step["done"] for step in challenges.progress(db_session, user.id, "2027-03")] == [True, True, True]


def test_other_months_keep_their_steps_as_they_were(db_session):
    user = _member(db_session, "february")
    steps = challenges.progress(db_session, user.id, "2027-02")
    assert all("formats" not in step for step in steps)


def test_the_card_payload_lists_the_formats_that_count(db_session):
    user = _member(db_session, "carded")
    for number in range(3):
        _row(db_session, user, models.Movie, f"Film {number}", finished=True)
    payload = challenges.payload(db_session, user, today=date(2027, 3, 10))
    assert payload["name"] == "Nine ways in" and payload["url"] == "/challenges/march-2027"
    assert [step["kind"] for step in payload["steps"]] == ["edition", "stretch", "reflect"]
    assert payload["steps"][1]["formats"][0] == "TV"
    assert payload["days_left"] == 22


def test_challenge_page_lists_the_nine_and_explains_the_stretch(client, monkeypatch, live):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-03")
    page = client.get("/challenges/march-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "The nine picks that count for step one" in text
    assert "Finish something in a format you hardly ever finish" in text and "fewer than three" in text
    assert 'href="/discover/monthly/march-2027"' in page.text
    for item in MARCH["items"]:
        assert item["title"] in text
    assert '"datePublished": "2027-03-01"' in page.text
    assert "Counts for you" not in text


def test_before_march_first_the_challenge_is_hidden(client, monkeypatch):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-02")
    assert client.get("/challenges/march-2027").status_code == 404
    assert client.get("/discover/monthly/march-2027").status_code == 404


def test_essay_title_does_not_repeat_a_fixed_heading(client, live):
    page = unescape(client.get("/discover/monthly/march-2027").text)
    assert page.count(">Where to start<") <= 2  # the section heading and its contents link, once each
    assert MARCH["essay_title"] not in ("Where to start", "The picks", "How the nine fit together")
