"""The November 2027 challenge and Discover edition: nine stories about telling stories, one per format, and the
"tell" step that counts a title the member recommended to someone in November, to a friend or by share link."""
from datetime import date, datetime, timedelta
from html import unescape

import pytest

from app import advent_calendar_data, challenges, models, pick, seasonal, title_pages
from app.discover_catalog import MONTHLY_EDITIONS, TRAILS, find_guest_pick, guest_fields, published_editions
from app.holiday_guides import GUIDES as COMPANIONS
from app.routers.collections import CATEGORIES
from app.seasonal_guides import SEASONS

NOVEMBER = MONTHLY_EDITIONS["november-2027"]
CHALLENGE = challenges.CHALLENGES["2027-11"]
EVENING = datetime(2027, 11, 12, 20, 0)
OCTOBER_NIGHT = datetime(2027, 10, 28, 21, 0)
DECEMBER_NIGHT = datetime(2027, 12, 2, 21, 0)
EXTRAS = {"other", "maker", "shadow", "classroom", "bargain", "teller", "machine"}


@pytest.fixture
def live(monkeypatch):
    """Publish the November edition now, whatever today's date is."""
    monkeypatch.setitem(NOVEMBER, "published_date", "2026-01-01")
    return NOVEMBER


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


def _finish(db_session, user, category, row, when=EVENING, rating=None):
    kind = title_pages.LIBRARY_TO_KIND[category]
    setattr(row, title_pages.COMPLETE_FIELD[kind], True)
    db_session.add(models.ActivityEntry(user_id=user.id, category=category, item_id=row.id, title=row.title,
                                        action="completed", occurred_at=when, rating=rating))
    db_session.commit()


def _told(db_session, user, title, category="movies", when=EVENING, recipient=None, token=None, source=None):
    rec = models.FriendRecommendation(sender_id=user.id, recipient_id=recipient.id if recipient else None,
                                      token=token, source_id=source.id if source else None, category=category,
                                      title=title, details="{}", created_at=when,
                                      expires_at=when + timedelta(days=60) if token else None)
    db_session.add(rec)
    db_session.commit()
    return rec


def _tell(db_session, user):
    return challenges.progress(db_session, user.id, "2027-11")[1]


def test_the_edition_and_challenge_go_live_on_november_first():
    assert "november-2027" not in published_editions(date(2027, 10, 31))
    assert "november-2027" in published_editions(date(2027, 11, 1))
    assert challenges.public_months(date(2027, 10, 31))[0] == "2027-10"
    assert challenges.public_months(date(2027, 11, 1))[0] == "2027-11"
    assert CHALLENGE["edition"] == "november-2027" and "revisits_count" not in CHALLENGE
    assert [step["kind"] for step in CHALLENGE["steps"]] == ["edition", "tell", "formats"]
    assert CHALLENGE["steps"][1]["count"] == 1 and CHALLENGE["steps"][2]["count"] == 2
    assert CHALLENGE["published"] == NOVEMBER["published_date"] == "2027-11-01"
    # Thanksgiving 2027, which the edition and its notes name, is Thursday, November 25.
    assert date(2027, 11, 25).strftime("%A") == "Thursday"
    assert "November 25" in " ".join(NOVEMBER["notes"]["paragraphs"])


def test_nine_picks_one_per_format_each_naming_its_teller():
    items = NOVEMBER["items"]
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
        teller = item["teller"]
        # "Movie, told by a grandfather" on the challenge page.
        assert teller["who"] and (teller["who"][0].islower() or teller["who"].startswith("Death")), item["title"]
        assert len(teller["note"].split()) >= 30, item["title"]
        # Only one kind of extra line per pick.
        assert not (EXTRAS - {"teller"}) & set(item)


def test_no_pick_repeats_another_edition_trail_hub_or_advent_door():
    mine = {(title_pages.LIBRARY_TO_KIND[item["category"]], title_pages.slugify(item["title"])) for item in NOVEMBER["items"]}
    taken = {(title_pages.LIBRARY_TO_KIND[item["category"]], title_pages.slugify(item["title"]))
             for slug, edition in MONTHLY_EDITIONS.items() if slug != "november-2027" for item in edition["items"]}
    taken |= {(title_pages.LIBRARY_TO_KIND[item["category"]], title_pages.slugify(item["title"]))
              for trail in TRAILS.values() for item in trail["items"]}
    taken |= {(door["kind"], title_pages.slugify(door["title"])) for edition in advent_calendar_data.EDITIONS.values()
              for door in edition["doors"]}
    # The Thanksgiving guide especially: this edition is about storytellers, not the holiday weekend.
    for entry in (*SEASONS.values(), *COMPANIONS.values()):
        taken |= {(item["kind"], title_pages.slugify(item["title"])) for item in seasonal.picks(entry)}
    assert not taken & mine
    # No maker repeats a pick from October, the month before.
    october = {item["meta"].get(field) for item in MONTHLY_EDITIONS["october-2027"]["items"]
               for field in ("director", "author", "artist", "host") if item["meta"].get(field)}
    assert not october & {item["meta"].get(field) for item in NOVEMBER["items"]
                          for field in ("director", "author", "artist", "host") if item["meta"].get(field)}


def test_edition_page_shows_all_nine_with_their_tellers_and_links(client, monkeypatch, live):
    page = client.get("/discover/monthly/november-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert NOVEMBER["essay_title"] in text and "Pull up a chair" in text
    assert text.count("Who's telling it:") == 9
    for item in NOVEMBER["items"]:
        assert item["title"] in text
        assert item["teller"]["note"] in text
    for kind in ("manga", "podcast", "audiobook"):
        assert f'data-guest-kind="{kind}"' in page.text
    # The notes point to the Thanksgiving guide instead of repeating it.
    assert '<ul class="edition-links">' in page.text
    assert '<a href="/holidays/thanksgiving">The Thanksgiving weekend guide</a>' in page.text
    assert NOVEMBER["name"] in unescape(client.get("/discover").text)
    # The October edition still names its bargains and nothing about tellers.
    monkeypatch.setitem(MONTHLY_EDITIONS["october-2027"], "published_date", "2026-01-01")
    october = unescape(client.get("/discover/monthly/october-2027").text)
    assert "The bargain:" in october and "Who's telling it:" not in october and "edition-links" not in october


def test_saving_the_whole_edition_fills_every_format(authenticated_client, db_session, live):
    keys = [item["key"] for item in NOVEMBER["items"]]
    saved = authenticated_client.post("/api/discover/monthly/november-2027/save", json={"keys": keys})
    assert saved.status_code == 200, saved.text
    assert saved.json()["created"] == 9
    assert authenticated_client.post("/api/discover/monthly/november-2027/save", json={"keys": keys}).json()["created"] == 0
    user = _user(db_session)
    game = db_session.query(models.VideoGame).filter_by(user_id=user.id).one()
    assert game.title == "Where the Water Tastes Like Wine" and game.release_date == datetime(2018, 1, 1)
    audiobook = db_session.query(models.Audiobook).filter_by(user_id=user.id).one()
    assert (audiobook.title, audiobook.author, audiobook.narrator, audiobook.year, audiobook.length_hours) == (
        "The Book Thief", "Markus Zusak", "Allan Corduner", 2006, 13.93)
    assert db_session.query(models.Podcast).filter_by(user_id=user.id).one().host == "The Moth"
    music = db_session.query(models.Music).filter_by(user_id=user.id).one()
    assert (music.title, music.artist, music.year) == ("Alice's Restaurant", "Arlo Guthrie", 1967)
    assert db_session.query(models.Manga).filter_by(user_id=user.id).one().author == "Shigeru Mizuki"
    film = db_session.query(models.Movie).filter_by(user_id=user.id).one()
    assert (film.title, film.director, film.year) == ("The Princess Bride", "Rob Reiner", 1987)
    assert db_session.query(models.Book).filter_by(user_id=user.id).one().author == "Diane Setterfield"
    assert db_session.query(models.TVShow).filter_by(user_id=user.id).one().year == 1987


def test_pick_for_me_keeps_its_six_formats(live):
    entries = {entry["title"]: entry for entry in pick.pool() if entry["source_url"] == "/discover/monthly/november-2027"}
    assert {"The Princess Bride", "The Storyteller", "Showa Genroku Rakugo Shinju", "The Thirteenth Tale",
            "Alice's Restaurant"} <= set(entries)
    assert entries["Where the Water Tastes Like Wine"]["year"] == 2018
    assert "NonNonBa" not in entries and "The Book Thief" not in entries


def test_a_guest_saved_audiobook_moves_in_with_its_author(authenticated_client, db_session, live):
    audiobook = next(item for item in NOVEMBER["items"] if item["category"] == "audiobooks")
    fields = guest_fields(audiobook)
    assert find_guest_pick(fields["kind"], fields["slug"])["creator"] == "Markus Zusak"
    response = authenticated_client.post("/api/guest-list/import", json={"items": [{"kind": fields["kind"], "slug": fields["slug"]}]})
    assert response.status_code == 200, response.text
    row = db_session.query(models.Audiobook).filter_by(user_id=_user(db_session).id).one()
    assert (row.title, row.year) == ("The Book Thief", 2006)


def test_a_pick_saved_under_another_name_still_counts(db_session):
    for name, model, category, title in (("henson", models.TVShow, "tv-shows", "Jim Henson's The Storyteller"),
                                         ("yotaro", models.Anime, "anime", "Descending Stories: Showa Genroku Rakugo Shinju"),
                                         ("mizuki", models.Manga, "manga", "NonNonBâ")):
        user = _member(db_session, name)
        _finish(db_session, user, category, _row(db_session, user, model, title))
        assert challenges.progress(db_session, user.id, "2027-11")[0]["done"] is True, title


def test_telling_a_friend_or_making_a_link_in_november_counts(db_session):
    user = _member(db_session, "teller")
    friend = _member(db_session, "listener")
    film = _row(db_session, user, models.Movie, "The Princess Bride")
    _finish(db_session, user, "movies", film, rating=9)
    step = _tell(db_session, user)
    assert step["kind"] == "tell" and step["done"] is False
    # The card offers this month's finish, from the member's own library, to recommend.
    assert step["suggest"] == {"title": "The Princess Bride", "category": "movies", "id": film.id}
    _told(db_session, user, "The Princess Bride", recipient=friend)
    step = _tell(db_session, user)
    assert step["done"] is True and (step["count"], step["target"]) == (1, 1)
    # Done: the card names nothing more.
    assert step["suggest"] is None
    # A share link for someone not on OmniTrackr counts the same way.
    linker = _member(db_session, "linker")
    _told(db_session, linker, "Alice's Restaurant", category="music", token="tok-linker-1")
    assert _tell(db_session, linker)["done"] is True


def test_only_the_members_own_november_recommendations_count(db_session):
    user = _member(db_session, "quiet")
    friend = _member(db_session, "loud")
    # Before November and after it don't count.
    _told(db_session, user, "Too Early", when=OCTOBER_NIGHT, recipient=friend)
    _told(db_session, user, "Too Late", when=DECEMBER_NIGHT, recipient=friend)
    assert _tell(db_session, user)["done"] is False
    # Something a friend sent the member is theirs, not the member's.
    _told(db_session, friend, "Sent To Me", recipient=user)
    assert _tell(db_session, user)["done"] is False
    # The copy a share link leaves in a reader's inbox when they open it is not the reader telling anyone.
    link = _told(db_session, friend, "Shared Widely", token="tok-shared-1")
    _told(db_session, friend, "Shared Widely", recipient=user, source=link)
    assert _tell(db_session, user)["done"] is False
    assert challenges.tell_count(db_session, friend.id, "2027-11") == 2


def test_one_title_sent_to_three_friends_is_one_title_told(db_session):
    user = _member(db_session, "generous")
    for name in ("a", "b", "c"):
        _told(db_session, user, "The Moth", category="podcasts", recipient=_member(db_session, f"friend_{name}"))
    _told(db_session, user, " the moth ", category="podcasts", token="tok-generous-1")
    assert challenges.tell_count(db_session, user.id, "2027-11") == 1
    _told(db_session, user, "The Moth", category="movies", recipient=_member(db_session, "friend_d"))
    assert challenges.tell_count(db_session, user.id, "2027-11") == 2


def test_the_suggestion_prefers_a_rated_finish_still_in_the_library(db_session):
    user = _member(db_session, "chooser")
    rated = _row(db_session, user, models.Book, "The Thirteenth Tale")
    _finish(db_session, user, "books", rated, when=datetime(2027, 11, 3, 20, 0), rating=8)
    later = _row(db_session, user, models.Movie, "Unrated Later")
    _finish(db_session, user, "movies", later, when=datetime(2027, 11, 9, 20, 0))
    assert _tell(db_session, user)["suggest"]["title"] == "The Thirteenth Tale"
    # A finish removed from the library has nothing for the dialog to send, so the next one is offered.
    db_session.delete(rated)
    db_session.commit()
    assert _tell(db_session, user)["suggest"] == {"title": "Unrated Later", "category": "movies", "id": later.id}
    # Nothing finished this month: no suggestion, and the card says how the step counts.
    assert _tell(db_session, _member(db_session, "idle"))["suggest"] is None


def test_recommending_through_the_api_counts_this_month(authenticated_client, db_session):
    me = _user(db_session)
    friend = _member(db_session, "apifriend")
    db_session.add(models.Friendship(user1_id=min(me.id, friend.id), user2_id=max(me.id, friend.id)))
    film = _row(db_session, me, models.Movie, "The Princess Bride", year=1987)
    month = challenges.month_key()
    assert challenges.tell_count(db_session, me.id, month) == 0
    sent = authenticated_client.post("/api/friend-recs", json={"category": "movies", "item_id": film.id, "friend_ids": [friend.id]})
    assert sent.status_code == 200, sent.text
    assert challenges.tell_count(db_session, me.id, month) == 1
    book = _row(db_session, me, models.Book, "The Thirteenth Tale")
    made = authenticated_client.post("/api/friend-recs/link", json={"category": "books", "item_id": book.id})
    assert made.status_code == 200, made.text
    assert challenges.tell_count(db_session, me.id, month) == 2


def test_a_link_from_an_earlier_month_is_made_again_so_this_month_counts(authenticated_client, db_session):
    me = _user(db_session)
    book = _row(db_session, me, models.Book, "The Thirteenth Tale")
    now = datetime.utcnow()
    start = datetime(now.year, now.month, 1)
    old = _told(db_session, me, "The Thirteenth Tale", category="books", when=start - timedelta(days=3), token="tok-old-month-1")
    old.expires_at = now + timedelta(days=50)
    db_session.commit()
    made = authenticated_client.post("/api/friend-recs/link", json={"category": "books", "item_id": book.id})
    assert made.status_code == 200, made.text
    assert not made.json()["url"].endswith("/tok-old-month-1")
    assert challenges.tell_count(db_session, me.id, challenges.month_key()) == 1
    # The old link keeps working until it expires, and a link made this month is reused as before.
    assert authenticated_client.get("/r/tok-old-month-1").status_code == 200
    again = authenticated_client.post("/api/friend-recs/link", json={"category": "books", "item_id": book.id})
    assert again.json()["url"] == made.json()["url"]


def test_stories_told_two_ways_means_two_formats(db_session):
    user = _member(db_session, "twoways")
    _finish(db_session, user, "movies", _row(db_session, user, models.Movie, "The Princess Bride"))
    steps = challenges.progress(db_session, user.id, "2027-11")
    assert steps[0]["done"] is True and steps[2]["count"] == 1 and steps[2]["done"] is False
    _finish(db_session, user, "movies", _row(db_session, user, models.Movie, "Another Film"))
    assert challenges.progress(db_session, user.id, "2027-11")[2]["done"] is False
    _finish(db_session, user, "podcasts", _row(db_session, user, models.Podcast, "The Moth"))
    assert challenges.progress(db_session, user.id, "2027-11")[2]["done"] is True


def test_the_card_payload_has_the_tell_step_only_in_november(db_session):
    user = _member(db_session, "carded")
    payload = challenges.payload(db_session, user, today=date(2027, 11, 10))
    assert payload["name"] == "Tell me a story" and payload["url"] == "/challenges/november-2027"
    assert [step["kind"] for step in payload["steps"]] == ["edition", "tell", "formats"]
    assert payload["steps"][1]["suggest"] is None
    assert payload["days_left"] == 21
    assert all(step["kind"] != "tell" for step in challenges.progress(db_session, user.id, "2027-10"))


def test_challenge_page_lists_the_nine_with_who_tells_them(client, monkeypatch, live):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-11")
    page = client.get("/challenges/november-2027")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "The nine picks that count for step one" in text
    assert "Tell someone about one" in text and "Hear it told two ways" in text
    assert 'href="/discover/monthly/november-2027"' in page.text
    for item in NOVEMBER["items"]:
        assert item["title"] in text
    assert "Movie, told by a grandfather" in text and "Audiobook, told by Death himself" in text
    assert "Elsewhere on OmniTrackr this month" in text and 'href="/holidays/thanksgiving"' in page.text
    assert '"datePublished": "2027-11-01"' in page.text
    assert "Loved" not in text


def test_a_shared_november_challenge_shows_steps_never_titles(client, db_session):
    user = _member(db_session, "sharer")
    book = _row(db_session, user, models.Book, "A Very Private Novel")
    _finish(db_session, user, "books", book)
    _told(db_session, user, "A Very Private Novel", category="books", token="tok-sharer-1")
    entry = models.MonthlyChallengeEntry(user_id=user.id, month="2027-11", completed_at=EVENING, share_token="novsharetoken123")
    db_session.add(entry)
    db_session.commit()
    page = client.get("/challenge/novsharetoken123")
    assert page.status_code == 200
    text = unescape(page.text)
    assert "Tell someone about one" in text
    assert "Private Novel" not in text


def test_before_november_first_the_challenge_is_hidden(client, monkeypatch):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-10")
    assert client.get("/challenges/november-2027").status_code == 404
    assert client.get("/discover/monthly/november-2027").status_code == 404


def test_every_linked_page_exists(client, monkeypatch, live):
    monkeypatch.setattr(challenges, "month_key", lambda today=None: "2027-11")
    for label, href in (*NOVEMBER["notes"]["links"], *CHALLENGE["links"]):
        assert href.startswith("/") and label
        assert client.get(href, follow_redirects=False).status_code == 200, href


def test_essay_title_does_not_repeat_a_fixed_heading(client, live):
    page = unescape(client.get("/discover/monthly/november-2027").text)
    assert page.count(">Where to start<") <= 2
    assert NOVEMBER["essay_title"] not in ("Where to start", "The picks", "Pull up a chair")
