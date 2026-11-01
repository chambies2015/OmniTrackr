"""Discussion boards on public title pages: threads, replies, spoilers, reports, moderation and limits."""
from datetime import datetime, timedelta

import pytest

from app import models, title_discussions
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


def _setup(db):
    add_movie(db, member(db, "tracker"))
    alice, bob = _veteran(db, "alice"), _veteran(db, "bob")
    db.commit()
    return alice, bob


def _start(client, subject="That docking scene", body=OPENER, spoiler=False):
    response = client.post(API, json={"subject": subject, "body": body, "spoiler": spoiler})
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "private, no-store"
    return response.json()


def _reply(client, thread_id, body, spoiler=False):
    return client.post(f"/api/discussions/{thread_id}/replies", json={"body": body, "spoiler": spoiler})


def test_title_page_invites_the_first_discussion(client, db_session):
    _setup(db_session)
    html = client.get(TITLE).text
    assert 'id="discussions-title"' in html and "Nobody has started a discussion about Interstellar yet" in html
    assert f'href="{BOARD}#start">Start the first discussion</a>' in html
    assert '<a href="#discussions-title">Discussions</a>' in html


def test_start_reply_and_read(client, db_session):
    alice, bob = _setup(db_session)
    _as(client, alice)
    started = _start(client)
    assert started["url"] == f"{BOARD}/{started['id']}"
    thread = db_session.get(models.TitleDiscussion, started["id"])
    assert (thread.kind, thread.slug, thread.title, thread.user_id) == ("movie", "interstellar-2014", "Interstellar", alice.id)

    _as(client, bob)
    response = _reply(client, started["id"], "Agreed. Hans Zimmer's organ in that scene still gives me chills.")
    assert response.status_code == 201
    assert response.json()["url"] == f"{started['url']}#reply-{response.json()['id']}"
    note = db_session.query(models.Notification).filter_by(user_id=alice.id, type="discussion_reply").one()
    assert note.link == started["url"] and note.message == 'bob replied to your discussion "That docking scene" on Interstellar.'
    # A second reply while that note is unread doesn't pile on another.
    _reply(client, started["id"], "Also the 'no time for caution' line.")
    assert db_session.query(models.Notification).filter_by(user_id=alice.id, type="discussion_reply").count() == 1

    _as(client, None)
    page = client.get(started["url"])
    assert page.status_code == 200 and page.headers["cache-control"] == "public, max-age=60"
    assert "That docking scene" in page.text and "Hans Zimmer" in page.text and "2 replies" in page.text
    assert '"@type": "DiscussionForumPosting"' in page.text
    assert "Sign in to join the discussion" in page.text and "data-disc-reply" not in page.text
    # Short threads stay out of search until they carry real writing.
    assert 'content="noindex, follow"' in page.text

    title_page = client.get(TITLE).text
    assert "That docking scene" in title_page and "Start a discussion</a>" in title_page

    board = client.get(BOARD)
    assert board.status_code == 200 and "That docking scene" in board.text and "<strong>2</strong> replies" in board.text
    listed = client.get(API).json()
    assert listed["count"] == 1 and listed["threads"][0]["replies"] == 2 and listed["threads"][0]["author"] == "alice"


def test_long_threads_are_indexed_and_in_the_sitemap(client, db_session):
    alice, bob = _setup(db_session)
    _as(client, alice)
    started = _start(client, body="\n\n".join([LONG_REVIEW, LONG_REVIEW.replace("Interstellar", "It"), LONG_REVIEW.lower()]))
    _as(client, None)
    page = client.get(started["url"]).text
    assert 'content="index, follow"' in page
    assert title_discussions.sitemap_paths(db_session)[0][0] == started["url"]


def test_spoilers_fold_and_inline_tags_hide(client, db_session):
    alice, bob = _setup(db_session)
    _as(client, alice)
    started = _start(client, subject="The ending explained", body="So the bookshelf was ||Cooper himself all along|| right? <b>wow</b>",
                     spoiler=False)
    folded = _start(client, subject="Big twist talk here", body="Everything about the tesseract and Murph's watch.", spoiler=True)
    _as(client, None)
    page = client.get(started["url"]).text
    assert '<span class="disc-spoiler" tabindex="0" role="button" aria-pressed="false" title="Spoiler: select to show">Cooper himself all along</span>' in page
    assert "&lt;b&gt;wow&lt;/b&gt;" in page and "<b>wow</b>" not in page
    # Listings and search snippets never show the hidden bit.
    board = client.get(BOARD).text
    assert "Cooper himself" not in board and "[spoiler]" in board
    assert "Murph's watch" not in board and "Murph&#x27;s watch" not in board
    folded_page = client.get(folded["url"]).text
    assert '<details class="disc-spoiler-post">' in folded_page and '"text"' not in folded_page.split("DiscussionForumPosting")[1].split("</script>")[0]


def test_validation_links_and_repeats(client, db_session):
    alice, _ = _setup(db_session)
    _as(client, alice)
    assert client.post(API, json={"subject": "Hi", "body": OPENER}).status_code == 422
    assert client.post(API, json={"subject": "Short body here", "body": "too short"}).status_code == 422
    spam = "Watch free: https://a.example https://b.example https://c.example right now"
    response = client.post(API, json={"subject": "Free streams", "body": spam})
    assert response.status_code == 422 and "up to 2 links" in response.json()["detail"]
    _start(client)
    again = client.post(API, json={"subject": "Docking scene again", "body": OPENER})
    assert again.status_code == 409
    assert client.post("/api/titles/movie/not-a-real-title-1999/discussions",
                       json={"subject": "Anything here", "body": OPENER}).status_code == 404


def test_signed_out_visitors_cannot_post(client, db_session):
    alice, _ = _setup(db_session)
    _as(client, None)
    assert client.post(API, json={"subject": "That docking scene", "body": OPENER}).status_code == 401
    assert "Sign in to start a discussion" in client.get(BOARD).text


def test_daily_limits_and_new_accounts(client, db_session, monkeypatch):
    alice, _ = _setup(db_session)
    newbie = member(db_session, "newbie")  # created just now
    db_session.commit()
    _as(client, newbie)
    for n in range(title_discussions.NEW_ACCOUNT_THREADS):
        _start(client, subject=f"Question number {n}", body=f"{OPENER} ({n})")
    blocked = client.post(API, json={"subject": "One more thought", "body": OPENER + " again"})
    assert blocked.status_code == 429 and "2 discussions a day" in blocked.json()["detail"]

    monkeypatch.setattr(title_discussions, "POST_GAP_SECONDS", 20)
    _as(client, alice)
    _start(client)
    quick = client.post(API, json={"subject": "Another quick one", "body": OPENER + " part two"})
    assert quick.status_code == 429 and "posting quickly" in quick.json()["detail"]


def test_authors_edit_and_delete(client, db_session):
    alice, bob = _setup(db_session)
    _as(client, alice)
    lonely = _start(client, subject="Nobody will answer", body="A thread that will get deleted before anyone replies.")
    assert client.delete(f"/api/discussions/{lonely['id']}").json()["state"] == "deleted"
    assert db_session.get(models.TitleDiscussion, lonely["id"]) is None

    started = _start(client)
    _as(client, bob)
    reply_id = _reply(client, started["id"], "The organ! Totally.").json()["id"]
    assert client.patch(f"/api/discussions/{started['id']}", json={"body": "hijack"}).status_code == 403
    assert client.delete(f"/api/discussions/{started['id']}?reply_id={reply_id}").status_code == 200
    reply_id = _reply(client, started["id"], "Second try at a reply.").json()["id"]
    edited = client.patch(f"/api/discussions/{started['id']}", json={"body": "Second try, now with ||a spoiler||.", "reply_id": reply_id})
    assert edited.status_code == 200 and "disc-spoiler" in edited.json()["body_html"]

    _as(client, alice)
    # With replies, deleting clears the opening post and keeps the conversation.
    assert client.delete(f"/api/discussions/{started['id']}").json()["state"] == "cleared"
    page = client.get(started["url"]).text
    assert "deleted their post" in page and "Second try" in page and OPENER not in page


def test_reports_hide_after_three_members(client, db_session, monkeypatch):
    alice, bob = _setup(db_session)
    carol, dave = _veteran(db_session, "carol"), _veteran(db_session, "dave")
    mod = _veteran(db_session, "danmod")
    db_session.commit()
    monkeypatch.setenv("ADMIN_USERNAMES", "danmod")
    _as(client, alice)
    started = _start(client)
    assert client.post(f"/api/discussions/{started['id']}/report", json={"reason": "spam"}).status_code == 409  # own post

    for reporter in (bob, carol):
        _as(client, reporter)
        assert client.post(f"/api/discussions/{started['id']}/report", json={"reason": "spam"}).json()["hidden"] is False
    _as(client, bob)
    assert client.post(f"/api/discussions/{started['id']}/report", json={"reason": "spam"}).json()["duplicate"] is True
    assert client.post(f"/api/discussions/{started['id']}/report", json={"reason": "nonsense"}).status_code == 422
    _as(client, dave)
    assert client.post(f"/api/discussions/{started['id']}/report", json={"reason": "harassment"}).json()["hidden"] is True
    assert db_session.query(models.Notification).filter_by(user_id=mod.id, type="discussion_report").count() == 2

    _as(client, None)
    assert client.get(started["url"]).status_code == 404
    assert "That docking scene" not in client.get(BOARD).text
    _as(client, alice)
    assert "Hidden from everyone else after reports" in client.get(started["url"]).text
    assert _reply(client, started["id"], "Hello?").status_code == 409

    _as(client, bob)
    assert client.post(f"/api/discussions/{started['id']}/moderate", json={"action": "restore"}).status_code == 403
    assert client.get("/discussions/moderation").status_code == 404
    _as(client, mod)
    queue = client.get("/discussions/moderation")
    assert queue.status_code == 200 and "That docking scene" in queue.text and "Spam or advertising" in queue.text
    assert client.post(f"/api/discussions/{started['id']}/moderate", json={"action": "restore"}).json()["hidden"] is False
    _as(client, None)
    assert client.get(started["url"]).status_code == 200


def test_spoiler_reports_fold_instead_of_hiding(client, db_session):
    alice, bob = _setup(db_session)
    carol = _veteran(db_session, "carol")
    db_session.commit()
    _as(client, alice)
    started = _start(client)
    _as(client, carol)
    reply_id = _reply(client, started["id"], "Cooper ends up inside the bookshelf, by the way.").json()["id"]
    for reporter in (alice, bob):
        _as(client, reporter)
        client.post(f"/api/discussions/{started['id']}/report", json={"reason": "spoilers", "reply_id": reply_id})
    post = db_session.get(models.TitleDiscussionReply, reply_id)
    db_session.refresh(post)
    assert post.spoiler is True and post.hidden_at is None


def test_moderators_lock_threads(client, db_session, monkeypatch):
    alice, bob = _setup(db_session)
    mod = _veteran(db_session, "danmod")
    db_session.commit()
    monkeypatch.setenv("ADMIN_USERNAMES", "danmod")
    _as(client, alice)
    started = _start(client)
    _as(client, mod)
    assert client.post(f"/api/discussions/{started['id']}/moderate", json={"action": "lock"}).json()["locked"] is True
    _as(client, bob)
    locked = _reply(client, started["id"], "Can I still reply?")
    assert locked.status_code == 409 and "locked" in locked.json()["detail"]
    assert "isn&#x27;t taking new replies" in client.get(started["url"]).text or "isn't taking new replies" in client.get(started["url"]).text


def test_inactive_members_posts_disappear(client, db_session):
    alice, bob = _setup(db_session)
    _as(client, alice)
    started = _start(client)
    alice.is_active = False
    db_session.commit()
    _as(client, None)
    assert client.get(started["url"]).status_code == 404
    assert client.get(API).json()["count"] == 0


def test_wrong_slug_redirects_and_unknown_pages_404(client, db_session):
    alice, _ = _setup(db_session)
    _as(client, alice)
    started = _start(client)
    _as(client, None)
    moved = client.get(f"/titles/movie/interstellar/discussions/{started['id']}", follow_redirects=False)
    assert moved.status_code in (301, 404)
    assert client.get(f"/titles/tv/interstellar-2014/discussions/{started['id']}").status_code == 404
    assert client.get("/titles/movie/no-such-title-2001/discussions").status_code == 404
    assert client.get(BOARD + "?page=9").status_code == 404
