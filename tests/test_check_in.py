"""Check-ins (Nov 17 2026): the emailed "did you finish it?" page, the check-in email and its rules."""
import asyncio
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import pytest

from app import auth, check_in, comeback, models, visits
from app.site_traffic import RECORDER, clean_path

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 20, 12, 0)


@pytest.fixture(autouse=True)
def counters(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    RECORDER._pending.clear()
    yield
    RECORDER._pending.clear()


def counted(key):
    return sum(amount for (_, kind, name), amount in RECORDER._pending.items() if kind == "checkin" and name == key)


def member(db, name, *, away_days=14, created_days=60, verified=True):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=verified,
                       is_active=True, created_at=NOW - timedelta(days=created_days),
                       last_login_at=NOW - timedelta(days=away_days))
    db.add(user)
    db.flush()
    return user


def save(db, user, model=models.Movie, title="Dune", days_ago=10, **fields):
    row = model(title=title, user_id=user.id, added_at=NOW - timedelta(days=days_ago), **fields)
    db.add(row)
    db.flush()
    return row


def headers_for(user):
    return {"Authorization": f"Bearer {auth.create_user_access_token(user)}"}


class _KeepOpen:
    def __init__(self, db):
        self._db = db

    def __getattr__(self, name):
        return getattr(self._db, name)

    def close(self):
        pass


def run_send(db, sent, now=NOW):
    async def sender(to, subject, html, unsubscribe_url):
        sent.append((to, subject, html, unsubscribe_url))
    return asyncio.run(check_in.send_due(lambda: _KeepOpen(db), now=now, sender=sender))


def page_path(link):
    parts = urlsplit(link)
    return parts.path + ("?" + parts.query if parts.query else "")


# ---------------------------------------------------------------- the link

def test_token_round_trip_and_tampering(db_session):
    user = member(db_session, "reader")
    movie = save(db_session, user)
    token = check_in.make_token(user.id, [{"category": "movies", "id": movie.id}], "checkin")
    assert check_in.read_token(token) == {"user_id": user.id, "items": [("movies", movie.id)], "source": "checkin"}
    assert check_in.read_token(token[:-2] + ("aa" if not token.endswith("aa") else "bb")) is None
    assert check_in.read_token("") is None and check_in.read_token("x" * 500) is None
    # Signed for another purpose (the weekly email's link) is not a check-in link.
    from app import digest
    assert check_in.read_token(digest.subscribe_link_token(user.id)) is None
    old = check_in._serializer()
    import itsdangerous
    signer = itsdangerous.URLSafeTimedSerializer(auth.SECRET_KEY, salt=check_in.TOKEN_SALT)
    stale = signer.dumps({"u": user.id, "i": [["movies", movie.id]], "s": "checkin"})
    assert old.loads(stale)  # same signer
    assert check_in.read_token(signer.dumps({"u": user.id, "i": [["nope", 1]], "s": "checkin"})) is None
    assert check_in.read_token(signer.dumps({"u": True, "i": [["movies", 1]], "s": "checkin"})) is None
    assert check_in.read_token(signer.dumps({"u": user.id, "i": [], "s": "checkin"})) is None


def test_candidates_ask_unfinished_first_and_skip_ongoing_podcasts(db_session):
    user = member(db_session, "mixed")
    save(db_session, user, title="Old film", days_ago=40)
    save(db_session, user, models.TVShow, title="Severance", days_ago=3)
    save(db_session, user, models.Podcast, title="Endless pod", days_ago=1)
    save(db_session, user, models.Book, title="Finished book", days_ago=2, read=True)
    save(db_session, user, models.Book, title="Rated book", days_ago=2, read=True, rating=8)
    save(db_session, user, models.Movie, title="   ", days_ago=1)
    found = check_in.candidates(db_session, user.id)
    assert [card["title"] for card in found] == ["Severance", "Old film", "Finished book"]
    assert found[0]["finished_label"] == "Finished it" and found[2]["finished"] is True


# ---------------------------------------------------------------- the page

def test_page_shows_only_the_titles_in_the_link_without_signing_in(client, db_session):
    user = member(db_session, "visitor")
    dune = save(db_session, user, title="Dune")
    save(db_session, user, title="Not in the email")
    db_session.commit()
    token = check_in.make_token(user.id, [{"category": "movies", "id": dune.id}], "checkin")
    response = client.get(f"/check-in/{token}", headers={"user-agent": "Mozilla/5.0 Firefox/140.0"})
    assert response.status_code == 200
    assert "Dune" in response.text and "Not in the email" not in response.text
    assert "Did you watch it?" in response.text and "0 of 1 answered" in response.text
    assert response.headers["cache-control"] == "private, no-store"
    assert "noindex" in response.headers["x-robots-tag"]
    assert "Log in to my library" in response.text
    assert counted("opened_checkin") == 1
    # A mail app's link checker doesn't count as an open.
    client.get(f"/check-in/{token}", headers={"user-agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"})
    assert counted("opened_checkin") == 1


def test_expired_or_broken_links_get_a_friendly_page(client, db_session):
    response = client.get("/check-in/not-a-real-token")
    assert response.status_code == 404 and "run out" in response.text
    user = member(db_session, "gone")
    dune = save(db_session, user)
    db_session.commit()
    token = check_in.make_token(user.id, [{"category": "movies", "id": dune.id}], "checkin")
    db_session.delete(dune)
    db_session.commit()
    assert client.get(f"/check-in/{token}").status_code == 404
    assert client.post(f"/check-in/{token}", data={"item": "0", "choice": "finished"}).status_code == 404


def test_finishing_with_a_score_saves_it_and_counts_a_visit(client, db_session):
    user = member(db_session, "finisher")
    user.last_seen_on = (datetime.utcnow() - timedelta(days=14)).date()
    user.visit_days = 1
    show = save(db_session, user, models.TVShow, title="Severance")
    db_session.commit()
    token = check_in.make_token(user.id, [{"category": "tv-shows", "id": show.id}], "checkin")
    opened = client.post(f"/check-in/{token}", data={"item": "0", "choice": "open"}, follow_redirects=False)
    assert opened.status_code == 303 and opened.headers["location"].startswith("?pick=0&a=finished")
    assert token not in opened.headers["location"]  # redirects never repeat the link itself
    db_session.refresh(show)
    assert show.watched is False  # opening the score buttons saves nothing
    page = client.get(urljoin(f"/check-in/{token}", opened.headers["location"]))
    assert 'value="finished-8"' in page.text and "Save as finished, no score" in page.text

    saved = client.post(f"/check-in/{token}", data={"item": "0", "choice": "finished-8"}, follow_redirects=False)
    assert saved.status_code == 303 and "saved=0" in saved.headers["location"]
    db_session.refresh(show)
    db_session.refresh(user)
    assert show.watched is True and show.rating == 8.0
    entries = db_session.query(models.ActivityEntry).filter_by(user_id=user.id, item_id=show.id, action="completed").all()
    assert len(entries) == 1 and entries[0].rating == 8.0 and entries[0].category == "tv-shows"
    assert user.last_seen_on == visits.today_utc() and user.visit_days == 2
    done = client.get(urljoin(f"/check-in/{token}", saved.headers["location"]))
    assert "All caught up" in done.text and "your score 8/10" in done.text
    assert counted("finished_checkin") == 1 and counted("rated_checkin") == 1 and counted("all_done_checkin") == 1
    assert counted("opened_checkin") == 0  # our own redirects are not opens

    # Changing the score later doesn't add another journal entry or count "answered all" again.
    client.post(f"/check-in/{token}", data={"item": "0", "choice": "rate-9"}, follow_redirects=False)
    db_session.refresh(show)
    assert show.rating == 9.0
    assert db_session.query(models.ActivityEntry).filter_by(user_id=user.id, item_id=show.id).count() == 1
    assert counted("all_done_checkin") == 1


def test_still_going_changes_nothing(client, db_session):
    user = member(db_session, "slow")
    book = save(db_session, user, models.Book, title="Middlemarch")
    film = save(db_session, user, title="Heat")
    db_session.commit()
    token = check_in.make_token(user.id, [{"category": "books", "id": book.id}, {"category": "movies", "id": film.id}], "comeback")
    response = client.post(f"/check-in/{token}", data={"item": "0", "choice": "still", "ok": ""}, follow_redirects=False)
    assert "ok=0" in response.headers["location"]
    db_session.refresh(book)
    assert book.read is False and book.rating is None
    page = client.get(urljoin(f"/check-in/{token}", response.headers["location"]))
    assert "Still going. It stays on your list." in page.text and "1 of 2 answered" in page.text
    assert counted("still_comeback") == 1
    # The email's own "Still going" button answers on opening, since nothing changes.
    direct = client.get(f"/check-in/{token}?pick=1&a=still", headers={"user-agent": "Mozilla/5.0 Firefox/140.0"})
    assert "Still going. It stays on your list." in direct.text
    db_session.refresh(film)
    assert film.watched is False
    assert counted("opened_comeback") == 1 and counted("still_comeback") == 2


def test_finished_without_score_and_bad_input(client, db_session):
    user = member(db_session, "quick")
    game = save(db_session, user, models.VideoGame, title="Hades")
    db_session.commit()
    token = check_in.make_token(user.id, [{"category": "video-games", "id": game.id}], "checkin")
    for data in ({"item": "5", "choice": "finished"}, {"item": "x", "choice": "finished"},
                 {"item": "0", "choice": "finished-11"}, {"item": "0", "choice": "rate-0"}, {"item": "0", "choice": "delete"}):
        assert client.post(f"/check-in/{token}", data=data, follow_redirects=False).status_code == 303
    db_session.refresh(game)
    assert game.played is False and game.rating is None
    client.post(f"/check-in/{token}", data={"item": "0", "choice": "finished"})
    db_session.refresh(game)
    assert game.played is True and game.rating is None
    page = client.get(f"/check-in/{token}?r=1")
    assert "You finished it. How was it, out of 10?" in page.text and "No score" in page.text


def test_a_link_never_touches_another_members_titles(client, db_session):
    owner = member(db_session, "owner1")
    other = member(db_session, "other1")
    theirs = save(db_session, other, title="Their film")
    db_session.commit()
    token = check_in.make_token(owner.id, [{"category": "movies", "id": theirs.id}], "checkin")
    assert client.get(f"/check-in/{token}").status_code == 404
    client.post(f"/check-in/{token}", data={"item": "0", "choice": "finished-10"})
    db_session.refresh(theirs)
    assert theirs.watched is False and theirs.rating is None


def test_cross_site_posts_are_refused(client, db_session):
    user = member(db_session, "csrf")
    film = save(db_session, user)
    db_session.commit()
    token = check_in.make_token(user.id, [{"category": "movies", "id": film.id}], "checkin")
    response = client.post(f"/check-in/{token}", data={"item": "0", "choice": "finished"},
                           headers={"origin": "https://evil.example"}, follow_redirects=False)
    assert response.status_code == 403
    db_session.refresh(film)
    assert film.watched is False


def test_the_link_is_masked_in_traffic_counts():
    assert clean_path("/check-in/abc.def.ghi") == "/check-in/(private link)"


# ---------------------------------------------------------------- who gets the email

def test_due_members_follow_every_rule(db_session):
    def due():
        return sorted(user.username for user in check_in.due_members(db_session, NOW))

    ok = member(db_session, "ok", away_days=14)
    save(db_session, ok)
    too_soon = member(db_session, "soon", away_days=5)
    save(db_session, too_soon)
    long_gone = member(db_session, "longgone", away_days=45)  # the come-back email's turn
    save(db_session, long_gone)
    brand_new = member(db_session, "brandnew", away_days=10, created_days=8)
    save(db_session, brand_new)
    empty = member(db_session, "empty", away_days=14)
    all_done = member(db_session, "alldone", away_days=14)
    save(db_session, all_done, watched=True, rating=7)
    opted = member(db_session, "optedout", away_days=14)
    save(db_session, opted)
    db_session.add(models.EmailOptOut(user_id=opted.id))
    weekly = member(db_session, "weekly", away_days=14)
    save(db_session, weekly)
    db_session.add(models.EmailDigestSubscription(user_id=weekly.id, token="tok-weekly"))
    unverified = member(db_session, "unverified", away_days=14, verified=False)
    save(db_session, unverified)
    recent_mail = member(db_session, "recentmail", away_days=14)
    save(db_session, recent_mail)
    db_session.add(models.EmailCampaignSend(campaign_key="welcome-3-never-miss", user_id=recent_mail.id,
                                            status="sent", sent_at=NOW - timedelta(hours=30)))
    db_session.commit()
    assert due() == ["ok"]
    assert empty and long_gone and brand_new


def test_one_email_per_stretch_away(db_session):
    user = member(db_session, "once", away_days=12)
    save(db_session, user, title="Arrival")
    db_session.commit()
    sent = []
    assert run_send(db_session, sent)["sent"] == 0  # not started
    check_in.set_status(db_session, "sending")
    assert run_send(db_session, sent)["sent"] == 1
    to, subject, html, unsubscribe_url = sent[0]
    assert to == "once@example.com" and subject == "Did you watch Arrival?"
    assert "/check-in/" in html and "&amp;a=finished" in html and "Still going" in html
    assert "/email/updates/unsubscribe?token=" in unsubscribe_url
    assert counted("sent_checkin") == 1
    # The next hourly run and the next week: still the same stretch away, so nothing more.
    assert run_send(db_session, sent, NOW + timedelta(hours=1))["sent"] == 0
    assert run_send(db_session, sent, NOW + timedelta(days=7))["sent"] == 0
    link = re.search(r'href="([^"]+/check-in/[^"]+)"', html).group(1).replace("&amp;", "&")
    token = urlsplit(link).path.rsplit("/", 1)[1]
    data = check_in.read_token(token)
    assert data["user_id"] == user.id and data["source"] == "checkin"
    assert parse_qs(urlsplit(link).query)["utm_campaign"] == ["check-in"]


def test_paused_while_whats_new_sends_and_inside_the_budget(db_session, monkeypatch):
    from app import announcements
    user = member(db_session, "budget", away_days=12)
    save(db_session, user)
    db_session.commit()
    check_in.set_status(db_session, "sending")
    db_session.add(models.EmailCampaign(key=announcements.CAMPAIGN_KEY, status="sending"))
    db_session.commit()
    assert run_send(db_session, [])["sent"] == 0
    db_session.query(models.EmailCampaign).filter_by(key=announcements.CAMPAIGN_KEY).update({"status": "done"})
    db_session.commit()
    monkeypatch.setenv("CHECKIN_DAILY_LIMIT", "0")
    assert run_send(db_session, [])["limited"] is True
    monkeypatch.setenv("CHECKIN_DAILY_LIMIT", "20")
    assert run_send(db_session, [])["sent"] == 1


def test_status_counts_returns_and_page_answers(db_session):
    user = member(db_session, "returner", away_days=12)
    save(db_session, user)
    db_session.commit()
    check_in.set_status(db_session, "sending")
    run_send(db_session, [])
    user.last_seen_on = (NOW + timedelta(days=2)).date()
    db_session.commit()
    info = check_in.status(db_session, NOW + timedelta(days=3))
    assert info["sent_30d"] == 1 and info["came_back"] == 1 and info["due_now"] == 0
    assert [row["source"] for row in info["page"]["by_source"]] == ["Check-in email", "Come-back email", "Backlog draw evening email",
                                                                    "Your week Sunday nudge", "Break plan wrap-up email"]


# ---------------------------------------------------------------- the come-back email

def test_come_back_email_gets_check_in_buttons(db_session):
    user = member(db_session, "away", away_days=45)
    save(db_session, user, title="Paddington 2")
    db_session.commit()
    subject, html, text, _ = comeback.email_for(db_session, user, None)
    assert "Still on your list" in html and "/check-in/" in html and "Watched it" in html
    assert "no need to sign in" in text
    token = re.search(r"/check-in/([^?\"]+)", html).group(1)
    assert check_in.read_token(token)["source"] == "comeback"


def test_come_back_email_without_anything_to_ask_keeps_its_old_shape(db_session):
    user = member(db_session, "settled", away_days=45)
    save(db_session, user, title="Seen it", watched=True, rating=9)
    db_session.commit()
    _subject, html, _text, _ = comeback.email_for(db_session, user, None)
    assert "/check-in/" not in html


# ---------------------------------------------------------------- Site stats

@pytest.fixture
def owner(db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "boss")
    user = member(db_session, "boss", away_days=0)
    db_session.commit()
    return user


def test_owner_controls_and_preview(client, db_session, owner):
    other = member(db_session, "notboss", away_days=0)
    db_session.commit()
    assert client.post("/api/site-stats/check-in", json={"action": "start"}, headers=headers_for(other)).status_code == 403
    assert client.get("/site-stats/check-in-preview", headers=headers_for(other)).status_code == 403
    empty = client.get("/site-stats/check-in-preview", headers=headers_for(owner))
    assert empty.status_code == 200 and "nothing to check in on" in empty.text
    save(db_session, owner, title="Blade Runner")
    db_session.commit()
    preview = client.get("/site-stats/check-in-preview", headers=headers_for(owner))
    assert "Preview only" in preview.text and "Blade Runner" in preview.text
    assert "default-src 'none'" in preview.headers["content-security-policy"]
    started = client.post("/api/site-stats/check-in", json={"action": "start"}, headers=headers_for(owner)).json()
    assert started["status"] == "sending"
    assert client.post("/api/site-stats/check-in", json={"action": "pause"}, headers=headers_for(owner)).json()["status"] == "paused"
    assert client.post("/api/site-stats/check-in", json={"action": "nuke"}, headers=headers_for(owner)).status_code == 422
    overview = client.get("/api/site-stats/overview", headers=headers_for(owner)).json()
    assert overview["check_in"]["status"] == "paused" and "page" in overview["check_in"]


def test_test_send_goes_only_to_the_owner(client, db_session, owner, monkeypatch):
    save(db_session, owner, title="Alien")
    bystander = member(db_session, "bystander", away_days=12)
    save(db_session, bystander)
    db_session.commit()
    sent = []

    async def fake_send(to, subject, html, unsubscribe_url):
        sent.append((to, subject))

    monkeypatch.setattr(check_in, "mail_configured", lambda: True)
    monkeypatch.setattr(check_in.send_test, "__defaults__", (fake_send,))
    response = client.post("/api/site-stats/check-in", json={"action": "test"}, headers=headers_for(owner))
    assert response.status_code == 200, response.text
    assert sent == [("boss@example.com", "[Test] Did you watch Alien?")]
    assert response.json()["sent_all_time"] == 0


def test_site_stats_page_has_the_card_and_report_line():
    page = (ROOT / "app/templates/site_stats.html").read_text(encoding="utf-8")
    script = (ROOT / "app/static/site-stats.js").read_text(encoding="utf-8")
    assert 'id="checkInCard"' in page and 'href="/site-stats/check-in-preview"' in page
    assert "Check-in email: ${data.check_in.status}" in script and "renderCheckIn(data)" in script
