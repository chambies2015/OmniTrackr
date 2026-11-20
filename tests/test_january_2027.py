"""The January 2027 challenge and Discover edition: the first edition in all nine formats,
and the "waiting" step that counts a finish from the member's backlog."""
from datetime import date, datetime, timedelta
from html import unescape

import pytest

from app import challenges, models, pick, title_pages
from app.discover_catalog import MONTHLY_EDITIONS, find_guest_pick, guest_fields, published_editions
from app.routers.collections import CATEGORIES

JANUARY = MONTHLY_EDITIONS["january-2027"]
CHALLENGE = challenges.CHALLENGES["2027-01"]


@pytest.fixture
def live(monkeypatch):
    """Publish the January edition now, whatever today's date is."""
    monkeypatch.setitem(JANUARY, "published_date", "2026-01-01")
    return JANUARY


def _user(db_session, username="testuser"):
    return db_session.query(models.User).filter(models.User.username == username).one()


def test_the_edition_and_challenge_go_live_on_new_years_day():
    assert "january-2027" not in published_editions(date(2026, 12, 31))
    assert "january-2027" in published_editions(date(2027, 1, 1))
    assert challenges.public_months(date(2026, 12, 31))[0] == "2026-12"
    assert challenges.public_months(date(2027, 1, 1))[0] == "2027-01"
    assert CHALLENGE["edition"] == "january-2027"
    assert [step["kind"] for step in CHALLENGE["steps"]] == ["edition", "waiting", "reflect"]
    assert CHALLENGE["steps"][0]["edition"] == "january-2027"


def test_nine_picks_one_per_format_none_repeated():
    items = JANUARY["items"]
    assert [item["category"] for item in items] == list(CATEGORIES)
    assert len({item["key"] for item in items}) == 9
    for item in items:
        assert item["source"].startswith("https://")
        assert len(item["why"].split()) >= 80, item["title"]
        assert item["caveat"]
        # Every meta key is a column on that format's library row, so saving can pass them straight through.
        model = CATEGORIES[item["category"]][0]
        assert all(hasattr(model, field) for field in item["meta"]), item["title"]
        assert guest_fields(item) is not None
    earlier = {title_pages.slugify(item["title"]) for slug, edition in MONTHLY_EDITIONS.items() if slug != "january-2027"
               for item in edition["items"]}
    assert not earlier & {title_pages.slugify(item["title"]) for item in items}


def test_edition_page_shows_all_nine_with_guest_saves(client, live):
    page = client.get("/discover/monthly/january-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert JANUARY["essay_title"] in text and "How the nine fit together" in text
    for item in JANUARY["items"]:
        assert item["title"] in text
    for kind in ("manga", "podcast", "audiobook"):
        assert f'data-guest-kind="{kind}"' in page.text
    hub = unescape(client.get("/discover").text)
    assert JANUARY["name"] in hub and "Nine media types" in hub


def test_saving_the_whole_edition_fills_every_format(authenticated_client, db_session, live):
    keys = [item["key"] for item in JANUARY["items"]]
    preview = authenticated_client.get("/api/discover/monthly/january-2027/preview").json()
    assert len(preview["items"]) == 9
    saved = authenticated_client.post("/api/discover/monthly/january-2027/save", json={"keys": keys})
    assert saved.status_code == 200, saved.text
    assert saved.json()["created"] == 9
    assert authenticated_client.post("/api/discover/monthly/january-2027/save", json={"keys": keys}).json()["created"] == 0
    user = _user(db_session)
    assert db_session.query(models.Podcast).filter_by(user_id=user.id).one().host == "Pacific Northwest Stories"
    audiobook = db_session.query(models.Audiobook).filter_by(user_id=user.id).one()
    assert (audiobook.author, audiobook.narrator) == ("Tomi Adeyemi", "Bahni Turpin")
    assert db_session.query(models.Manga).filter_by(user_id=user.id).one().author == "Kyousuke Motomi"
    collection = db_session.query(models.Collection).one()
    assert len(collection.items) == 9
    # Ten keys is still too many for any edition.
    assert authenticated_client.post("/api/discover/monthly/january-2027/save",
                                     json={"keys": keys + ["extra"]}).status_code == 422


def test_pick_for_me_keeps_its_six_formats(live):
    pool = pick.pool()
    assert {entry["kind"] for entry in pool} <= set(pick.KIND_ORDER)
    sources = {entry["title"]: entry["source_url"] for entry in pool if entry["source_url"] == "/discover/monthly/january-2027"}
    assert {"Neuromancer", "Metroid Dread", "Love & Basketball"} <= set(sources)
    assert "Dengeki Daisy" not in sources and "The Black Tapes" not in sources


def test_a_guest_saved_podcast_moves_in_with_its_host(authenticated_client, db_session, live):
    podcast = next(item for item in JANUARY["items"] if item["category"] == "podcasts")
    fields = guest_fields(podcast)
    assert find_guest_pick(fields["kind"], fields["slug"])["creator"] == "Pacific Northwest Stories"
    response = authenticated_client.post("/api/guest-list/import", json={"items": [{"kind": fields["kind"], "slug": fields["slug"]}]})
    assert response.status_code == 200, response.text
    row = db_session.query(models.Podcast).filter_by(user_id=_user(db_session).id).one()
    assert (row.title, row.host, row.year) == ("The Black Tapes", "Pacific Northwest Stories", 2015)


def _moment(db_session, user, category, item, when):
    db_session.add(models.CompletionMoment(user_id=user.id, category=category, item_id=item.id, title=item.title,
                                           completed_at=when))
    db_session.commit()


def test_waiting_step_counts_only_titles_saved_before_the_month(db_session):
    user = models.User(username="backlog", email="backlog@example.com", hashed_password="x", is_verified=True)
    other = models.User(username="other", email="other@example.com", hashed_password="x", is_verified=True)
    db_session.add_all([user, other])
    db_session.flush()
    start, _ = challenges.month_bounds("2027-01")
    fresh = models.Book(user_id=user.id, title="New This Month", added_at=start + timedelta(days=2))
    db_session.add(fresh)
    db_session.commit()
    during = start + timedelta(days=5)
    _moment(db_session, user, "books", fresh, during)
    assert challenges.progress(db_session, user.id, "2027-01")[1] == {
        "key": "step-2", "kind": "waiting", "label": CHALLENGE["steps"][1]["label"], "count": 0, "target": 1, "done": False}

    # Somebody else's old row with the same id never counts for this member.
    theirs = models.Anime(user_id=other.id, title="Not Yours", added_at=start - timedelta(days=400))
    db_session.add(theirs)
    db_session.commit()
    db_session.add(models.CompletionMoment(user_id=user.id, category="anime", item_id=theirs.id, title="Not Yours",
                                           completed_at=during))
    db_session.commit()
    assert challenges.progress(db_session, user.id, "2027-01")[1]["done"] is False

    # A row from before added_at was recorded has been waiting too.
    legacy = models.Movie(user_id=user.id, title="Saved Years Ago")
    db_session.add(legacy)
    db_session.commit()
    legacy.added_at = None
    db_session.commit()
    _moment(db_session, user, "movies", legacy, during)
    assert challenges.progress(db_session, user.id, "2027-01")[1]["done"] is True

    # A finish logged in December doesn't count toward January.
    old = models.Music(user_id=user.id, title="Older Album", added_at=start - timedelta(days=90))
    db_session.add(old)
    db_session.commit()
    _moment(db_session, user, "music", old, start - timedelta(hours=1))
    assert challenges.progress(db_session, user.id, "2027-01")[1]["count"] == 1


def test_a_pick_already_in_the_library_does_two_steps(db_session):
    user = models.User(username="reader", email="reader@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.flush()
    start, _ = challenges.month_bounds("2027-01")
    book = models.Book(user_id=user.id, title="Neuromancer", author="William Gibson", year=1984,
                       added_at=start - timedelta(days=30))
    db_session.add(book)
    db_session.commit()
    db_session.add(models.CompletionMoment(user_id=user.id, category="books", item_id=book.id, title="Neuromancer",
                                           completed_at=start + timedelta(days=3), takeaway="Molly steals every scene."))
    db_session.commit()
    steps = challenges.progress(db_session, user.id, "2027-01")
    assert [step["done"] for step in steps] == [True, True, True]


def test_challenge_page_lists_the_nine_and_mentions_the_pledge(client, monkeypatch, live):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-01")
    page = client.get("/challenges/january-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "The nine picks that count for step one" in text
    assert "2027 New Year challenge" in text
    assert 'href="/discover/monthly/january-2027"' in page.text
    for item in JANUARY["items"]:
        assert item["title"] in text
    assert '"datePublished": "2027-01-01"' in page.text


def test_before_new_years_day_the_challenge_is_hidden(client, monkeypatch):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2026-12")
    assert client.get("/challenges/january-2027").status_code == 404
    assert client.get("/discover/monthly/january-2027").status_code == 404
