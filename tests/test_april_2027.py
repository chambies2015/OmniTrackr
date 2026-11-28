"""The April 2027 challenge and Discover edition: nine titles people kept passing on, and the
"recommended" step that counts a finish whose Why I added it names a person."""
from datetime import date, datetime, timedelta
from html import unescape

import pytest

from app import advent_calendar_data, challenges, models, pick, title_pages
from app.discover_catalog import MONTHLY_EDITIONS, TRAILS, find_guest_pick, guest_fields, published_editions
from app.routers.collections import CATEGORIES

APRIL = MONTHLY_EDITIONS["april-2027"]
CHALLENGE = challenges.CHALLENGES["2027-04"]
START, END = challenges.month_bounds("2027-04")
DURING = START + timedelta(days=9)
BEFORE = START - timedelta(days=40)


@pytest.fixture
def live(monkeypatch):
    """Publish the April edition now, whatever today's date is."""
    monkeypatch.setitem(APRIL, "published_date", "2026-01-01")
    return APRIL


def _user(db_session, username="testuser"):
    return db_session.query(models.User).filter(models.User.username == username).one()


def _member(db_session, name):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.flush()
    return user


def _row(db_session, user, model, title, finished=True):
    field = title_pages.COMPLETE_FIELD[next(kind for kind, spec in title_pages.KINDS.items() if spec[0] is model)]
    row = model(user_id=user.id, title=title, **{field: finished})
    db_session.add(row)
    db_session.commit()
    return row


def _finish(db_session, user, category, row, when=DURING, note=None, rating=None):
    db_session.add(models.ActivityEntry(user_id=user.id, category=category, item_id=row.id, title=row.title,
                                        action="completed", occurred_at=when, note=note, rating=rating))
    db_session.commit()


def _origin(db_session, user, category, row, source, who=None, friend=None, when=None):
    when = when or datetime.utcnow()
    db_session.add(models.TitleOrigin(user_id=user.id, category=category, item_id=row.id, source=source,
                                      friend_id=friend.id if friend else None, who=who,
                                      who_key=who.casefold() if who else None, created_at=when, updated_at=when))
    db_session.commit()


def _recommended(db_session, user):
    return challenges.progress(db_session, user.id, "2027-04")[1]


def test_the_edition_and_challenge_go_live_on_april_first():
    assert "april-2027" not in published_editions(date(2027, 3, 31))
    assert "april-2027" in published_editions(date(2027, 4, 1))
    assert challenges.public_months(date(2027, 3, 31))[0] == "2027-03"
    assert challenges.public_months(date(2027, 4, 1))[0] == "2027-04"
    assert CHALLENGE["edition"] == "april-2027" and "revisits_count" not in CHALLENGE
    assert [step["kind"] for step in CHALLENGE["steps"]] == ["edition", "recommended", "reflect"]
    assert CHALLENGE["published"] == APRIL["published_date"] == "2027-04-01"


def test_nine_picks_one_per_format_none_repeated():
    items = APRIL["items"]
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
    mine = {title_pages.slugify(item["title"]) for item in items}
    elsewhere = {title_pages.slugify(item["title"]) for slug, edition in MONTHLY_EDITIONS.items() if slug != "april-2027"
                 for item in edition["items"]}
    elsewhere |= {title_pages.slugify(item["title"]) for trail in TRAILS.values() for item in trail["items"]}
    elsewhere |= {title_pages.slugify(door["title"]) for edition in advent_calendar_data.EDITIONS.values()
                  for door in edition["doors"]}
    assert not elsewhere & mine


def test_edition_page_shows_all_nine_with_guest_saves(client, live):
    page = client.get("/discover/monthly/april-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert APRIL["essay_title"] in text and "How the word got round" in text
    for item in APRIL["items"]:
        assert item["title"] in text
    for kind in ("manga", "podcast", "audiobook"):
        assert f'data-guest-kind="{kind}"' in page.text
    hub = unescape(client.get("/discover").text)
    assert APRIL["name"] in hub and "Nine media types" in hub


def test_saving_the_whole_edition_fills_every_format(authenticated_client, db_session, live):
    keys = [item["key"] for item in APRIL["items"]]
    saved = authenticated_client.post("/api/discover/monthly/april-2027/save", json={"keys": keys})
    assert saved.status_code == 200, saved.text
    assert saved.json()["created"] == 9
    assert authenticated_client.post("/api/discover/monthly/april-2027/save", json={"keys": keys}).json()["created"] == 0
    user = _user(db_session)
    assert db_session.query(models.Podcast).filter_by(user_id=user.id).one().host == "Joseph Fink, Jeffrey Cranor"
    audiobook = db_session.query(models.Audiobook).filter_by(user_id=user.id).one()
    assert (audiobook.author, audiobook.narrator) == ("Matt Dinniman", "Jeff Hays")
    assert db_session.query(models.Manga).filter_by(user_id=user.id).one().author == "Akiko Higashimura"
    assert db_session.query(models.Music).filter_by(user_id=user.id).one().artist == "The Velvet Underground"


def test_pick_for_me_keeps_its_six_formats(live):
    sources = {entry["title"] for entry in pick.pool() if entry["source_url"] == "/discover/monthly/april-2027"}
    assert {"Searching for Sugar Man", "Schitt's Creek", "Undertale", "The Song of Achilles"} <= sources
    assert "Blank Canvas" not in sources and "Dungeon Crawler Carl" not in sources


def test_a_guest_saved_audiobook_moves_in_with_its_author(authenticated_client, db_session, live):
    audiobook = next(item for item in APRIL["items"] if item["category"] == "audiobooks")
    fields = guest_fields(audiobook)
    assert find_guest_pick(fields["kind"], fields["slug"])["creator"] == "Matt Dinniman"
    response = authenticated_client.post("/api/guest-list/import", json={"items": [{"kind": fields["kind"], "slug": fields["slug"]}]})
    assert response.status_code == 200, response.text
    row = db_session.query(models.Audiobook).filter_by(user_id=_user(db_session).id).one()
    assert (row.title, row.year) == ("Dungeon Crawler Carl", 2020)


def test_a_pick_saved_under_another_name_still_counts(db_session):
    user = _member(db_session, "longname")
    manga = _row(db_session, user, models.Manga, "Blank Canvas: My So-Called Artist’s Journey")
    _finish(db_session, user, "manga", manga)
    assert challenges.progress(db_session, user.id, "2027-04")[0]["done"] is True
    other = _member(db_session, "curly")
    show = _row(db_session, other, models.TVShow, "Schitt’s Creek")
    _finish(db_session, other, "tv-shows", show)
    assert challenges.progress(db_session, other.id, "2027-04")[0]["done"] is True
    assert ("manga", "kakukaku shikajika") in challenges._edition_titles("april-2027")
    assert ("manga", "kakukaku shikajika") not in challenges._edition_titles("march-2027")


def test_a_finish_counts_once_it_names_who_recommended_it(db_session):
    user = _member(db_session, "listener")
    book = _row(db_session, user, models.Book, "A Book My Sister Lent Me")
    _finish(db_session, user, "books", book)
    step = _recommended(db_session, user)
    assert step["kind"] == "recommended" and step["done"] is False
    assert step["unsaid"] == [{"category": "books", "id": book.id, "title": "A Book My Sister Lent Me"}]
    _origin(db_session, user, "books", book, "person", who="Maya")
    step = _recommended(db_session, user)
    assert step["done"] is True and step["count"] == 1 and step["unsaid"] == []


def test_a_friend_counts_and_an_article_does_not(db_session):
    user = _member(db_session, "reader")
    friend = _member(db_session, "lender")
    film = _row(db_session, user, models.Movie, "A Film From a Review")
    _finish(db_session, user, "movies", film)
    _origin(db_session, user, "movies", film, "article", who="A newspaper")
    step = _recommended(db_session, user)
    assert step["done"] is False
    # It already says where it came from, so the card doesn't offer it again.
    assert step["unsaid"] == []
    game = _row(db_session, user, models.VideoGame, "A Game a Friend Sent")
    _finish(db_session, user, "video-games", game)
    _origin(db_session, user, "video-games", game, "friend", who="lender", friend=friend)
    assert _recommended(db_session, user)["done"] is True


def test_only_april_finishes_count_whenever_the_recommendation_was_saved(db_session):
    user = _member(db_session, "patient")
    old = _row(db_session, user, models.Anime, "Finished In February")
    _finish(db_session, user, "anime", old, when=BEFORE)
    _origin(db_session, user, "anime", old, "person", who="Sam")
    assert _recommended(db_session, user)["done"] is False
    # Recommended years ago, finished in April: counts.
    waiting = _row(db_session, user, models.Music, "An Album From Years Ago")
    _origin(db_session, user, "music", waiting, "person", who="Dad", when=BEFORE - timedelta(days=900))
    _finish(db_session, user, "music", waiting)
    assert _recommended(db_session, user)["done"] is True


def test_another_members_recommendations_never_count(db_session):
    user = _member(db_session, "mine")
    other = _member(db_session, "theirs")
    show = _row(db_session, user, models.TVShow, "Shared Taste")
    _finish(db_session, user, "tv-shows", show)
    db_session.add(models.TitleOrigin(user_id=other.id, category="tv-shows", item_id=show.id, source="person",
                                      who="Someone", who_key="someone"))
    db_session.commit()
    step = _recommended(db_session, user)
    assert step["done"] is False and [title["id"] for title in step["unsaid"]] == [show.id]


def test_the_card_offers_the_three_newest_live_finishes(db_session):
    user = _member(db_session, "busy")
    rows = []
    for number in range(5):
        row = _row(db_session, user, models.Podcast, f"Podcast {number}")
        _finish(db_session, user, "podcasts", row, when=DURING + timedelta(hours=number))
        rows.append(row)
    gone = _row(db_session, user, models.Movie, "Removed Since")
    _finish(db_session, user, "movies", gone, when=DURING + timedelta(days=2))
    db_session.delete(gone)
    db_session.commit()
    removed = models.ActivityEntry(user_id=user.id, category="books", item_id=None, title="Removed Book",
                                   action="completed", occurred_at=DURING + timedelta(days=3))
    db_session.add(removed)
    db_session.commit()
    step = _recommended(db_session, user)
    assert [title["title"] for title in step["unsaid"]] == ["Podcast 4", "Podcast 3", "Podcast 2"]


def test_a_recommended_pick_with_a_note_does_all_three_steps(db_session):
    user = _member(db_session, "everything")
    show = _row(db_session, user, models.TVShow, "Schitt's Creek")
    _origin(db_session, user, "tv-shows", show, "person", who="My cousin")
    _finish(db_session, user, "tv-shows", show, note="Keep going until season two.")
    assert [step["done"] for step in challenges.progress(db_session, user.id, "2027-04")] == [True, True, True]


def test_saying_who_from_the_library_finishes_the_step(authenticated_client, db_session):
    user = _user(db_session)
    book = _row(db_session, user, models.Book, "The Song of Achilles")
    _finish(db_session, user, "books", book)
    assert _recommended(db_session, user)["unsaid"][0]["id"] == book.id
    response = authenticated_client.put(f"/library/origins/books/{book.id}", json={"source": "person", "who": "Priya"})
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert _recommended(db_session, user)["done"] is True


def test_the_card_payload_lists_unsaid_finishes_only_for_april(db_session):
    user = _member(db_session, "carded")
    film = _row(db_session, user, models.Movie, "Searching for Sugar Man")
    _finish(db_session, user, "movies", film)
    payload = challenges.payload(db_session, user, today=date(2027, 4, 10))
    assert payload["name"] == "Pass it on" and payload["url"] == "/challenges/april-2027"
    assert [step["kind"] for step in payload["steps"]] == ["edition", "recommended", "reflect"]
    assert payload["steps"][0]["done"] is True
    assert payload["steps"][1]["unsaid"][0]["title"] == "Searching for Sugar Man"
    assert payload["days_left"] == 21
    assert all("unsaid" not in step for step in challenges.progress(db_session, user.id, "2027-03"))


def test_challenge_page_lists_the_nine_and_explains_the_step(client, monkeypatch, live):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-04")
    page = client.get("/challenges/april-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "The nine picks that count for step one" in text
    assert "Finish something someone recommended to you" in text and "Why I added it" in text
    assert 'href="/discover/monthly/april-2027"' in page.text
    for item in APRIL["items"]:
        assert item["title"] in text
    assert '"datePublished": "2027-04-01"' in page.text
    assert "Did someone recommend" not in text


def test_a_shared_april_challenge_shows_steps_never_titles(client, db_session, monkeypatch):
    user = _member(db_session, "sharer")
    show = _row(db_session, user, models.TVShow, "A Very Private Title")
    _finish(db_session, user, "tv-shows", show)
    entry = models.MonthlyChallengeEntry(user_id=user.id, month="2027-04", completed_at=DURING, share_token="aprilsharetoken1")
    db_session.add(entry)
    db_session.commit()
    page = client.get("/challenge/aprilsharetoken1")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "Finish something someone recommended to you" in text
    assert "A Very Private Title" not in text


def test_before_april_first_the_challenge_is_hidden(client, monkeypatch):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-03")
    assert client.get("/challenges/april-2027").status_code == 404
    assert client.get("/discover/monthly/april-2027").status_code == 404


def test_essay_title_does_not_repeat_a_fixed_heading(client, live):
    page = unescape(client.get("/discover/monthly/april-2027").text)
    assert page.count(">Where to start<") <= 2
    assert APRIL["essay_title"] not in ("Where to start", "The picks", "How the word got round")
