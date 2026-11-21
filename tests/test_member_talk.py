"""Nov 18 2026: getting members talking. Openers on empty boards, @mentions, a note to members who
track a title when a discussion starts, the /discussions hub, Reply under reviews, and the finish screen link."""
from datetime import datetime, timedelta

import pytest

from app import discussion_hub, models, title_discussions, web_push
from tests.test_shared_lists import _as
from tests.test_title_pages import LONG_REVIEW, add_movie, member

TITLE = "/titles/movie/interstellar-2014"
BOARD = TITLE + "/discussions"
API = "/api/titles/movie/interstellar-2014/discussions"
OPENER = "Did anyone else think the docking scene was the best part? The music there is something else."


@pytest.fixture(autouse=True)
def no_posting_gap(monkeypatch):
    monkeypatch.setattr(title_discussions, "POST_GAP_SECONDS", 0)


def _veteran(db, name):
    user = member(db, name)
    user.created_at = datetime.utcnow() - timedelta(days=30)
    db.flush()
    return user


def _start(client, subject="That docking scene", body=OPENER, **extra):
    response = client.post(API, json={"subject": subject, "body": body, "spoiler": False, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def _notes(db, user, kind):
    return db.query(models.Notification).filter_by(user_id=user.id, type=kind).all()


# ---------------------------------------------------------------- openers

@pytest.mark.parametrize("kind", sorted(discussion_hub.OPENERS))
def test_every_kind_has_openers_that_fit_the_form(kind):
    found = discussion_hub.openers(kind, "A Very Long Title " * 8)
    assert len(found) >= 4
    for item in found:
        assert title_discussions.SUBJECT_MIN <= len(item["subject"]) <= title_discussions.SUBJECT_MAX
        assert len(item["body"]) >= 12 and "{title}" not in item["body"]


def test_empty_title_page_and_board_offer_openers(client, db_session):
    add_movie(db_session, member(db_session, "tracker"))
    alice = _veteran(db_session, "alice")
    db_session.commit()
    page = client.get(TITLE).text
    assert f'href="{BOARD}?opener=0#start">That ending of Interstellar: did it work for you?</a>' in page
    _as(client, alice)
    board = client.get(BOARD + "?opener=2").text
    assert 'value="The scene from Interstellar I can&#x27;t stop thinking about"' in board
    assert ">There&#x27;s one scene in Interstellar I keep coming back to: </textarea>" in board
    assert "data-opener-used" in board and "data-disc-opener" in board and "Need an opener?" in board
    # Out of range openers are ignored, not an error.
    assert client.get(BOARD + "?opener=9").status_code == 200


def test_reply_to_a_review_prefills_the_mention_and_rejects_junk(client, db_session):
    add_movie(db_session, member(db_session, "tracker"))
    alice = _veteran(db_session, "alice")
    db_session.commit()
    _as(client, alice)
    board = client.get(BOARD + "?mention=Postal").text
    assert 'value="About Postal&#x27;s review of Interstellar"' in board and ">@Postal </textarea>" in board
    junk = client.get(BOARD + "?mention=%3Cscript%3E").text
    assert "&lt;script" not in junk and "<script>" not in junk.split("<main>", 1)[1]


def test_starting_from_an_opener_is_accepted(client, db_session):
    add_movie(db_session, member(db_session, "tracker"))
    alice = _veteran(db_session, "alice")
    db_session.commit()
    _as(client, alice)
    assert _start(client, opener=True)["url"].startswith(BOARD + "/")


# ---------------------------------------------------------------- mentions

def test_mentions_are_found_once_and_never_in_email_addresses():
    assert title_discussions.mentioned_names("@Postal. and @postal again, mail me at a@b.com, @bo") == ["Postal"]
    assert title_discussions.mentioned_names("@one @two @three @four") == ["one", "two", "three"]
    html = title_discussions.body_html("hey @Postal what did you think? a@b.com")
    assert '<span class="disc-mention">@Postal</span>' in html and "a@b.com" in html


def test_a_mention_tells_that_member_once(client, db_session):
    add_movie(db_session, member(db_session, "tracker"))
    alice, bob, carol = _veteran(db_session, "alice"), _veteran(db_session, "bob"), _veteran(db_session, "Carol")
    db_session.commit()
    _as(client, alice)
    thread = _start(client)
    _as(client, bob)
    body = "@carol you said the ending lost you. What about the docking scene? Also @alice @bob"
    assert client.post(f"/api/discussions/{thread['id']}/replies", json={"body": body}).status_code == 201
    [note] = _notes(db_session, carol, "discussion_mention")
    assert note.link == thread["url"] and note.message == 'bob mentioned you in "That docking scene" on Interstellar.'
    # Alice started it, so the reply note already reaches her; bob wrote it.
    assert not _notes(db_session, alice, "discussion_mention") and len(_notes(db_session, alice, "discussion_reply")) == 1
    assert not _notes(db_session, bob, "discussion_mention")
    client.post(f"/api/discussions/{thread['id']}/replies", json={"body": "@Carol one more thing"})
    assert len(_notes(db_session, carol, "discussion_mention")) == 1  # Still unread, so no pile-up.
    page = client.get(thread["url"]).text
    assert '<span class="disc-mention">@carol</span>' in page


def test_reply_to_buttons_show_on_other_peoples_posts(client, db_session):
    add_movie(db_session, member(db_session, "tracker"))
    alice, bob = _veteran(db_session, "alice"), _veteran(db_session, "bob")
    db_session.commit()
    _as(client, alice)
    thread = _start(client)
    assert 'data-disc-reply-to="alice"' not in client.get(thread["url"]).text
    _as(client, bob)
    assert 'data-disc-reply-to="alice">Reply to alice</button>' in client.get(thread["url"]).text


# ---------------------------------------------------------------- shelf notes

def test_members_who_track_the_title_hear_a_discussion_started(client, db_session):
    tracker = member(db_session, "tracker")
    add_movie(db_session, tracker, watched=True)
    hidden = member(db_session, "hidden")
    hidden.movies_private = True
    add_movie(db_session, hidden)
    gone = member(db_session, "gone", active=False)
    add_movie(db_session, gone)
    alice = _veteran(db_session, "alice")
    add_movie(db_session, alice)
    db_session.commit()
    _as(client, alice)
    thread = _start(client)
    [note] = _notes(db_session, tracker, "discussion_started")
    assert note.link == thread["url"]
    assert note.message == 'alice started a discussion about Interstellar, which is on your list: "That docking scene"'
    assert not _notes(db_session, alice, "discussion_started")
    assert not _notes(db_session, hidden, "discussion_started")  # A private shelf is never read.
    assert not _notes(db_session, gone, "discussion_started")
    # One a day at most.
    _start(client, subject="Best line in the film", body="No time for caution. Every single time it gets me.")
    assert len(_notes(db_session, tracker, "discussion_started")) == 1


def test_a_mentioned_tracker_gets_one_note_not_two(client, db_session):
    tracker = member(db_session, "tracker")
    add_movie(db_session, tracker)
    alice = _veteran(db_session, "alice")
    db_session.commit()
    _as(client, alice)
    _start(client, body="@tracker you added this last week, what did you make of the ending?")
    assert len(_notes(db_session, tracker, "discussion_mention")) == 1
    assert not _notes(db_session, tracker, "discussion_started")


def test_push_switches_for_the_new_notes():
    assert web_push.topic_of("discussion_mention") == "discussions" and web_push.wants(None, "discussion_mention")
    assert web_push.topic_of("discussion_started") == "shelf_talk" and not web_push.wants(None, "discussion_started")
    assert {"discussion_mention", "discussion_started"} <= set(web_push.TITLES)


# ---------------------------------------------------------------- the hub

def test_hub_for_guests_lists_latest_and_is_not_indexed(client, db_session):
    add_movie(db_session, member(db_session, "tracker"))
    alice = _veteran(db_session, "alice")
    db_session.commit()
    _as(client, alice)
    _start(client)
    _as(client, None)
    response = client.get("/discussions")
    assert response.status_code == 200 and response.headers["x-robots-tag"] == "noindex, follow"
    html = response.text
    assert "<h1>Discussions</h1>" in html and "Latest across OmniTrackr" in html
    assert f'class="disc-row__title" href="{BOARD}">Movie · Interstellar</a>' in html
    assert "Sign in to join in" in html and "Where you&#x27;re talking" not in html and "Where you're talking" not in html
    assert 'href="/discussions" aria-current="page"' in html


def test_hub_for_members_shows_their_threads_shelf_and_titles_waiting(client, db_session):
    tracker = member(db_session, "tracker")
    add_movie(db_session, tracker)
    add_movie(db_session, tracker, title="Arrival", year=2016)
    alice, bob = _veteran(db_session, "alice"), _veteran(db_session, "bob")
    add_movie(db_session, bob, watched=True)
    add_movie(db_session, bob, title="Arrival", year=2016, watched=True)
    db_session.commit()
    _as(client, alice)
    thread = _start(client)
    _as(client, bob)
    client.post(f"/api/discussions/{thread['id']}/replies", json={"body": "The docking scene, no contest."})
    _as(client, alice)
    html = client.get("/discussions").text
    yours = html.split('id="hub-yours"', 1)[1].split("</section>", 1)[0]
    assert "That docking scene" in yours and '<span class="disc-tag disc-tag--new">1 new</span>' in yours
    assert "1 new reply since you last posted." in yours

    _as(client, bob)
    html = client.get("/discussions").text
    assert "That docking scene" in html.split('id="hub-yours"', 1)[1].split("</section>", 1)[0]
    waiting = html.split('id="hub-waiting"', 1)[1].split("</section>", 1)[0]
    assert "Arrival" in waiting and "You finished it" in waiting and "/titles/movie/arrival-2016/discussions?opener=" in waiting
    assert "Interstellar" not in waiting  # It has a discussion already.


def test_hub_is_in_the_community_menu(client):
    html = client.get("/discussions").text
    nav = html[html.index('<header class="site-header'):html.index("</header>")]
    assert 'href="/discussions"' in nav


# ---------------------------------------------------------------- reviews and the finish screen

def test_review_page_offers_a_reply_on_the_board(client, db_session):
    writer = member(db_session, "Postal")
    movie = add_movie(db_session, writer, review=LONG_REVIEW, review_public=True, rating=9.0, watched=True)
    db_session.commit()
    html = client.get(f"/reviews/{movie.id}?category=movie").text
    assert "Agree with Postal?" in html
    assert f'href="{BOARD}?mention=Postal#start">Reply to Postal</a>' in html


def test_finish_screen_gets_the_board(client, db_session):
    alice = _veteran(db_session, "alice")
    movie = add_movie(db_session, alice, watched=True)
    db_session.commit()
    _as(client, alice)
    response = client.post("/completion-moments/", json={"category": "movies", "item_id": movie.id})
    assert response.status_code == 200, response.text
    assert response.json()["talk"] == {"url": BOARD, "count": 0}


def test_talk_summary_for_the_friends_feed_rail(client, db_session):
    tracker = member(db_session, "tracker")
    add_movie(db_session, tracker)
    alice, bob = _veteran(db_session, "alice"), _veteran(db_session, "bob")
    db_session.commit()
    _as(client, alice)
    thread = _start(client)
    _as(client, bob)
    client.post(f"/api/discussions/{thread['id']}/replies", json={"body": "The docking scene, no contest."})
    _as(client, alice)
    data = client.get("/api/discussions/summary").json()
    assert data["new_replies"] == 1
    assert data["threads"] == [{"subject": "That docking scene", "title": "Interstellar", "url": thread["url"], "new_replies": 1}]
    _as(client, tracker)
    shelf = client.get("/api/discussions/summary").json()
    assert shelf["new_replies"] == 0 and shelf["threads"][0]["url"] == thread["url"]
    _as(client, None)
    assert client.get("/api/discussions/summary").status_code == 401
