"""Ask a friend for their take: share links, the friend's view, the asker's note, the weekly email."""
from datetime import datetime, timedelta
from urllib.parse import urlsplit, parse_qs

from app import auth, digest, models
from tests.test_title_pages import LONG_REVIEW, add_movie, member

PAGE = "/titles/movie/interstellar-2014"
API = "/api/titles/movie/interstellar-2014"


def _me(db):
    return db.query(models.User).filter_by(username="testuser").one()


def _ask(client):
    response = client.post(f"{API}/ask")
    assert response.status_code == 200
    data = response.json()
    url = urlsplit(data["url"])
    assert url.path == PAGE and url.fragment == "write-review"
    return data, parse_qs(url.query)["take"][0]


def _as(client, user):
    client.cookies.clear()
    client.headers = {"Authorization": f"Bearer {auth.create_user_access_token(user)}"}
    client.cookies.set(auth.AUTH_COOKIE_NAME, auth.create_user_access_token(user))
    return client


def test_members_see_the_ask_button_and_visitors_do_not(client, authenticated_client, db_session):
    add_movie(db_session, member(db_session, "a"))
    db_session.commit()
    assert 'id="ask-friend" data-take-ask data-title-kind="movie" data-title-slug="interstellar-2014"' in authenticated_client.get(PAGE).text
    authenticated_client.headers = {}
    authenticated_client.cookies.clear()
    assert "data-take-ask" not in client.get(PAGE).text


def test_asking_returns_one_reusable_link(authenticated_client, db_session):
    add_movie(db_session, member(db_session, "a"))
    db_session.commit()
    data, token = _ask(authenticated_client)
    assert data["text"] == "What did you think of Interstellar? I'd love your take."
    assert _ask(authenticated_client)[1] == token
    take = db_session.query(models.TakeRequest).one()
    assert (take.asker_id, take.kind, take.slug, take.title) == (_me(db_session).id, "movie", "interstellar-2014", "Interstellar")
    assert authenticated_client.post("/api/titles/movie/missing-1999/ask").status_code == 404


def test_asking_requires_login(client):
    assert client.post(f"{API}/ask").status_code == 401


def test_friend_sees_who_asked_and_page_stays_out_of_search(client, authenticated_client, db_session):
    add_movie(db_session, member(db_session, "a"), review=LONG_REVIEW, review_public=True)
    db_session.commit()
    _, token = _ask(authenticated_client)
    authenticated_client.headers = {}
    authenticated_client.cookies.clear()
    page = client.get(f"{PAGE}?take={token}")
    assert "<strong>testuser</strong> asked what you thought of Interstellar" in page.text
    assert "Share your take on Interstellar" in page.text
    assert f"%3Ftake%3D{token}%23write-review" in page.text  # sign-in returns to the same link
    assert page.headers["x-robots-tag"] == "noindex, follow" and page.headers["cache-control"] == "private, no-store"
    for bad in ("nope", "x" * 20, token + "x"):
        other = client.get(f"{PAGE}?take={bad}")
        assert "asked what you thought" not in other.text


def test_expired_or_other_title_links_show_nothing(client, authenticated_client, db_session):
    add_movie(db_session, member(db_session, "a"))
    add_movie(db_session, member(db_session, "b"), title="Arrival", year=2016)
    add_movie(db_session, member(db_session, "c"), title="Arrival", year=2016)
    db_session.commit()
    _, token = _ask(authenticated_client)
    authenticated_client.headers = {}
    authenticated_client.cookies.clear()
    assert "asked what you thought" not in client.get(f"/titles/movie/arrival-2016?take={token}").text
    take = db_session.query(models.TakeRequest).one()
    take.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()
    assert "asked what you thought" not in client.get(f"{PAGE}?take={token}").text


def test_friends_public_review_notifies_the_asker_once(authenticated_client, db_session):
    add_movie(db_session, member(db_session, "a"))
    db_session.commit()
    asker = _me(db_session)
    _, token = _ask(authenticated_client)
    friend = member(db_session, "friend")
    db_session.commit()
    _as(authenticated_client, friend)
    form = authenticated_client.get(f"{PAGE}?take={token}").text
    assert f'data-take="{token}"' in form

    saved = authenticated_client.put(f"{API}/review", json={"review": LONG_REVIEW, "take": token})
    assert saved.status_code == 200 and saved.json()["asked_by"] == "testuser"
    notes = db_session.query(models.Notification).filter_by(user_id=asker.id, type="take_received").all()
    assert [(n.message, n.link) for n in notes] == [("friend shared their take on Interstellar.", f"{PAGE}#community-title")]
    _as(authenticated_client, asker)
    listed = authenticated_client.get("/notifications").json()
    assert listed[0]["type"] == "take_received" and listed[0]["link"] == f"{PAGE}#community-title"
    _as(authenticated_client, friend)

    # Editing again doesn't notify twice.
    again = authenticated_client.put(f"{API}/review", json={"review": LONG_REVIEW + " Still great.", "take": token,
                                                              "expected_review": LONG_REVIEW})
    assert again.json()["asked_by"] == "testuser"
    assert db_session.query(models.Notification).filter_by(user_id=asker.id, type="take_received").count() == 1


def test_private_short_or_self_answers_do_not_notify(authenticated_client, db_session):
    add_movie(db_session, member(db_session, "a"))
    db_session.commit()
    asker = _me(db_session)
    _, token = _ask(authenticated_client)
    own = authenticated_client.put(f"{API}/review", json={"review": LONG_REVIEW, "take": token})
    assert own.json()["asked_by"] is None
    for name, body in (("quiet", {"review": LONG_REVIEW, "public": False}), ("brief", {"review": "Good."})):
        _as(authenticated_client, member(db_session, name))
        db_session.commit()
        response = authenticated_client.put(f"{API}/review", json={**body, "take": token})
        assert response.status_code == 200 and response.json()["asked_by"] is None
    assert db_session.query(models.Notification).filter_by(user_id=asker.id, type="take_received").count() == 0


def test_weekly_email_suggests_asking_about_a_recent_finish(db_session):
    reader = member(db_session, "reader")
    add_movie(db_session, member(db_session, "a"))
    movie = add_movie(db_session, reader, watched=True)
    old = add_movie(db_session, reader, title="Heat", year=1995, watched=True)
    db_session.add(models.CompletionMoment(user_id=reader.id, category="movies", item_id=old.id, title="Heat",
                                           completed_at=datetime.utcnow() - timedelta(days=40)))
    db_session.add(models.CompletionMoment(user_id=reader.id, category="movies", item_id=movie.id, title="Interstellar",
                                           completed_at=datetime.utcnow() - timedelta(days=3)))
    db_session.commit()
    ask = digest.recent_finish(db_session, reader.id, datetime.utcnow())
    assert ask == {"title": "Interstellar", "path": PAGE}
    report = {"matches": [{"title": "Severance", "label": "TV", "date": "2026-10-02", "url": "/release-radar/tv", "reason": "x"}],
              "popular": []}
    subject, html, text = digest.build_digest("reader", report, "https://x/unsub", None, ask)
    assert "What did your friends think?" in html and f"{PAGE}#ask-friend" in html and f"{PAGE}#ask-friend" in text
    assert digest.build_digest("reader", {"matches": [], "popular": []}, "u", None, ask) is None  # never forces a send
    assert digest.recent_finish(db_session, member(db_session, "nobody").id, datetime.utcnow()) is None


def test_notification_link_migration_is_additive(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect, text
    from app import migrations
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE notifications (id INTEGER PRIMARY KEY, user_id INTEGER, type VARCHAR, message VARCHAR)"))
        conn.execute(text("INSERT INTO notifications (user_id, type, message) VALUES (1, 'x', 'kept')"))
        conn.commit()
    monkeypatch.setattr(migrations, "engine", engine)
    migrations.add_notification_link_column()
    migrations.add_notification_link_column()  # running twice is harmless
    assert "link" in {c["name"] for c in inspect(engine).get_columns("notifications")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT message, link FROM notifications")).fetchall() == [("kept", None)]
