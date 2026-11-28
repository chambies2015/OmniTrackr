"""The February 2027 challenge and Discover edition: nine love stories, and the "revisit" step
that counts a rewatch, reread or replay the way the diary does."""
from datetime import date, timedelta
from html import unescape

import pytest

from app import challenges, models, pick, title_pages
from app.discover_catalog import MONTHLY_EDITIONS, TRAILS, find_guest_pick, guest_fields, published_editions
from app.routers.collections import CATEGORIES

FEBRUARY = MONTHLY_EDITIONS["february-2027"]
CHALLENGE = challenges.CHALLENGES["2027-02"]


@pytest.fixture
def live(monkeypatch):
    """Publish the February edition now, whatever today's date is."""
    monkeypatch.setitem(FEBRUARY, "published_date", "2026-01-01")
    return FEBRUARY


def _user(db_session, username="testuser"):
    return db_session.query(models.User).filter(models.User.username == username).one()


def _member(db_session, name):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.flush()
    return user


def _log(db_session, user, category, item, action, when, note=None):
    db_session.add(models.ActivityEntry(user_id=user.id, category=category, item_id=item.id, title=item.title,
                                        action=action, occurred_at=when, note=note))
    db_session.commit()


def test_the_edition_and_challenge_go_live_on_february_first():
    assert "february-2027" not in published_editions(date(2027, 1, 31))
    assert "february-2027" in published_editions(date(2027, 2, 1))
    assert challenges.public_months(date(2027, 1, 31))[0] == "2027-01"
    assert challenges.public_months(date(2027, 2, 1))[0] == "2027-02"
    assert CHALLENGE["edition"] == "february-2027" and CHALLENGE["revisits_count"] is True
    assert [step["kind"] for step in CHALLENGE["steps"]] == ["edition", "revisit", "reflect"]
    assert CHALLENGE["steps"][0]["edition"] == "february-2027"


def test_nine_picks_one_per_format_none_repeated():
    items = FEBRUARY["items"]
    assert [item["category"] for item in items] == list(CATEGORIES)
    assert len({item["key"] for item in items}) == 9
    for item in items:
        assert item["source"].startswith("https://")
        assert len(item["why"].split()) >= 80, item["title"]
        assert item["caveat"]
        model = CATEGORIES[item["category"]][0]
        assert all(hasattr(model, field) for field in item["meta"]), item["title"]
        assert guest_fields(item) is not None
    elsewhere = {title_pages.slugify(item["title"]) for slug, edition in MONTHLY_EDITIONS.items() if slug != "february-2027"
                 for item in edition["items"]}
    elsewhere |= {title_pages.slugify(item["title"]) for trail in TRAILS.values() for item in trail["items"]}
    assert not elsewhere & {title_pages.slugify(item["title"]) for item in items}


def test_edition_page_shows_all_nine_with_guest_saves(client, live):
    page = client.get("/discover/monthly/february-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert FEBRUARY["essay_title"] in text and "How the nine fit together" in text
    for item in FEBRUARY["items"]:
        assert item["title"] in text
    for kind in ("manga", "podcast", "audiobook"):
        assert f'data-guest-kind="{kind}"' in page.text
    hub = unescape(client.get("/discover").text)
    assert FEBRUARY["name"] in hub and "Nine media types" in hub


def test_saving_the_whole_edition_fills_every_format(authenticated_client, db_session, live):
    keys = [item["key"] for item in FEBRUARY["items"]]
    saved = authenticated_client.post("/api/discover/monthly/february-2027/save", json={"keys": keys})
    assert saved.status_code == 200, saved.text
    assert saved.json()["created"] == 9
    assert authenticated_client.post("/api/discover/monthly/february-2027/save", json={"keys": keys}).json()["created"] == 0
    user = _user(db_session)
    assert db_session.query(models.Podcast).filter_by(user_id=user.id).one().host == "Esther Perel"
    audiobook = db_session.query(models.Audiobook).filter_by(user_id=user.id).one()
    assert (audiobook.author, audiobook.narrator) == ("Zora Neale Hurston", "Ruby Dee")
    assert db_session.query(models.Manga).filter_by(user_id=user.id).one().author == "Ai Yazawa"
    assert db_session.query(models.Music).filter_by(user_id=user.id).one().artist == "The Magnetic Fields"


def test_pick_for_me_keeps_its_six_formats(live):
    pool = pick.pool()
    sources = {entry["title"] for entry in pool if entry["source_url"] == "/discover/monthly/february-2027"}
    assert {"Past Lives", "Catastrophe", "To the Moon", "69 Love Songs", "Persuasion"} <= sources
    assert "Nana" not in sources and "Where Should We Begin?" not in sources


def test_a_guest_saved_podcast_moves_in_with_its_host(authenticated_client, db_session, live):
    podcast = next(item for item in FEBRUARY["items"] if item["category"] == "podcasts")
    fields = guest_fields(podcast)
    assert find_guest_pick(fields["kind"], fields["slug"])["creator"] == "Esther Perel"
    response = authenticated_client.post("/api/guest-list/import", json={"items": [{"kind": fields["kind"], "slug": fields["slug"]}]})
    assert response.status_code == 200, response.text
    row = db_session.query(models.Podcast).filter_by(user_id=_user(db_session).id).one()
    assert (row.title, row.host, row.year) == ("Where Should We Begin?", "Esther Perel", 2017)


def test_revisit_step_counts_what_the_diary_calls_a_rewatch(db_session):
    user = _member(db_session, "lover")
    other = _member(db_session, "someone")
    start, _ = challenges.month_bounds("2027-02")
    during = start + timedelta(days=9)

    # A first finish in February is a finish, not a revisit.
    first = models.Movie(user_id=user.id, title="First Time Seen")
    db_session.add(first)
    db_session.commit()
    _log(db_session, user, "movies", first, "completed", during)
    assert challenges.progress(db_session, user.id, "2027-02")[1] == {
        "key": "step-2", "kind": "revisit", "label": CHALLENGE["steps"][1]["label"], "count": 0, "target": 1, "done": False}

    # A revisit logged in January, or by somebody else, doesn't count for this member's February.
    album = models.Music(user_id=user.id, title="An Old Favourite")
    theirs = models.Book(user_id=other.id, title="Not Yours")
    db_session.add_all([album, theirs])
    db_session.commit()
    _log(db_session, user, "music", album, "revisited", start - timedelta(hours=2))
    _log(db_session, other, "books", theirs, "revisited", during)
    assert challenges._revisit_count(db_session, user.id, "2027-02") == 0

    # A second finish of a title finished before counts, as it does in the diary.
    film = models.Movie(user_id=user.id, title="Seen Before")
    db_session.add(film)
    db_session.commit()
    _log(db_session, user, "movies", film, "completed", start - timedelta(days=200))
    _log(db_session, user, "movies", film, "completed", during)
    assert challenges.progress(db_session, user.id, "2027-02")[1]["done"] is True

    # A journal "Revisited" entry counts, and one title revisited twice still counts once.
    _log(db_session, user, "music", album, "revisited", during)
    _log(db_session, user, "music", album, "revisited", during + timedelta(days=1))
    assert challenges._revisit_count(db_session, user.id, "2027-02") == 2


def test_a_revisited_pick_with_a_note_does_all_three_steps(db_session):
    user = _member(db_session, "rereader")
    start, _ = challenges.month_bounds("2027-02")
    book = models.Book(user_id=user.id, title="Persuasion", author="Jane Austen", year=1817)
    db_session.add(book)
    db_session.commit()
    _log(db_session, user, "books", book, "revisited", start + timedelta(days=14), note="The letter, again.")
    assert [step["done"] for step in challenges.progress(db_session, user.id, "2027-02")] == [True, True, True]


def test_only_february_counts_a_revisit_as_a_finish(db_session):
    user = _member(db_session, "january")
    start, _ = challenges.month_bounds("2027-01")
    book = models.Book(user_id=user.id, title="Neuromancer", author="William Gibson", year=1984)
    db_session.add(book)
    db_session.commit()
    _log(db_session, user, "books", book, "revisited", start + timedelta(days=3), note="Still dense.")
    assert [step["done"] for step in challenges.progress(db_session, user.id, "2027-01")] == [False, False, False]


def test_the_card_payload_names_the_revisit_step(db_session, monkeypatch):
    user = _member(db_session, "carded")
    payload = challenges.payload(db_session, user, today=date(2027, 2, 10))
    assert payload["name"] == "Love in every form" and payload["url"] == "/challenges/february-2027"
    assert [step["kind"] for step in payload["steps"]] == ["edition", "revisit", "reflect"]
    assert payload["days_left"] == 19


def test_challenge_page_lists_the_nine_and_explains_revisits(client, monkeypatch, live):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-02")
    page = client.get("/challenges/february-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "The nine picks that count for step one" in text
    assert "Go back to something you love" in text and "Revisited" in text
    assert 'href="/discover/monthly/february-2027"' in page.text
    for item in FEBRUARY["items"]:
        assert item["title"] in text
    assert '"datePublished": "2027-02-01"' in page.text


def test_before_february_first_the_challenge_is_hidden(client, monkeypatch):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-01")
    assert client.get("/challenges/february-2027").status_code == 404
    assert client.get("/discover/monthly/february-2027").status_code == 404
