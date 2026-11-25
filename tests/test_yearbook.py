"""Yearbook: making one, signing it with and without an account, letting notes in, the votes, the home
card, closing day and the emails."""
import asyncio
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app import auth, models, yearbook

ROOT = Path(__file__).resolve().parents[1]
OPEN = datetime(2026, 12, 5, 15, 0)


def make_user(db, name, **extra):
    user = models.User(username=name, email=f"{name}@example.test", hashed_password="unused", is_active=True,
                       is_verified=True, **extra)
    db.add(user)
    db.commit()
    return user


def sign_in(client, user):
    client.headers["Authorization"] = "Bearer " + auth.create_access_token({"sub": user.username, "uid": user.id})


def sign_out(client):
    client.headers.pop("Authorization", None)
    client.cookies.clear()


def befriend(db, one, two):
    low, high = sorted((one.id, two.id))
    db.add(models.Friendship(user1_id=low, user2_id=high))
    db.commit()


class Clock:
    def __init__(self, monkeypatch, at):
        self.at = at
        monkeypatch.setattr(yearbook, "_now", lambda: self.at)


@pytest.fixture
def clock(monkeypatch):
    return Clock(monkeypatch, OPEN)


def finished_movie(db, user, title, rating=None, poster=None, when=datetime(2026, 6, 1)):
    movie = models.Movie(user_id=user.id, title=title, year=2024, watched=True, rating=rating, poster_url=poster)
    db.add(movie)
    db.flush()
    db.add(models.ActivityEntry(user_id=user.id, category="movies", item_id=movie.id, title=title, action="completed",
                                rating=rating, occurred_at=when))
    db.commit()
    return movie


def make_book(client, user, **extra):
    sign_in(client, user)
    body = {"cover_name": user.username.title(), "quote": "I'll start it after this episode.", "picks": [],
            **extra}
    response = client.put("/api/yearbook", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def token_of(db, user):
    db.expire_all()
    return yearbook.get(db, user.id, 2026).token


def sign(client, token, user=None, **body):
    if user is None:
        sign_out(client)
    else:
        sign_in(client, user)
    payload = {"note": "You got me into Frieren. Thank you.", **body}
    return client.post(f"/api/yearbook/sign/{token}", json=payload)


# ---------------------------------------------------------------- the season

def test_the_season_opens_late_november_and_closes_after_new_years_day():
    assert yearbook.state_of(2026, datetime(2026, 11, 25, 23, 0)) == "soon"
    assert yearbook.state_of(2026, datetime(2026, 11, 26, 0, 0)) == "open"
    assert yearbook.state_of(2026, datetime(2027, 1, 2, 11, 59)) == "open"
    assert yearbook.state_of(2026, datetime(2027, 1, 2, 12, 0)) == "closed"
    assert yearbook.closes_label(2026) == "January 1"
    assert yearbook.season_year(datetime(2027, 1, 15)) == 2026
    assert yearbook.season_year(datetime(2027, 1, 17)) is None
    assert yearbook.state_of(2031) is None


def test_the_opening_day_can_be_moved_for_a_late_deploy(monkeypatch):
    monkeypatch.setenv("YEARBOOK_OPENS", "2026-12-01")
    assert yearbook.state_of(2026, datetime(2026, 11, 28)) == "soon"
    assert yearbook.state_of(2026, datetime(2026, 12, 1)) == "open"


# ---------------------------------------------------------------- pages

def test_the_guide_explains_it_to_visitors(client, clock):
    response = client.get("/yearbook")
    assert response.status_code == 200
    page = response.text
    assert "Get your friends to sign your year" in page
    assert 'href="/?next=%2Fyearbook#signup"' in page and "data-yearbook-signup" in page
    assert "Most likely to rewatch the same comfort show again" in page
    assert "noindex" not in response.headers.get("x-robots-tag", "")
    assert "/static/yearbook.css?v=" in page and "/static/yearbook.js?v=" in page


def test_members_get_the_app_page(client, db_session, clock):
    dana = make_user(db_session, "dana")
    sign_in(client, dana)
    page = client.get("/yearbook").text
    assert 'id="yearbookApp"' in page and 'data-view="mine"' in page and 'data-year="2026"' in page


def test_making_a_yearbook_tells_friends_once(client, db_session, clock):
    dana = make_user(db_session, "dana")
    sam = make_user(db_session, "sam")
    befriend(db_session, dana, sam)
    made = make_book(client, dana)
    assert made["made"] is True
    assert made["book"]["url"].endswith(made["book"]["path"])
    assert re.fullmatch(r"/yearbook/[A-Za-z0-9_-]{16,40}", made["book"]["path"])
    assert made["book"]["story"] == made["book"]["path"] + "/story.png"
    note = db_session.query(models.Notification).filter_by(user_id=sam.id, type="yearbook_friend").one()
    assert note.link == made["book"]["path"] and "dana opened their 2026 yearbook" in note.message
    again = make_book(client, dana, quote="Changed my mind")
    assert again["made"] is False and again["book"]["quote"] == "Changed my mind"
    assert db_session.query(models.Notification).filter_by(user_id=sam.id, type="yearbook_friend").count() == 1


def test_setup_checks_the_cover_name_and_quote(client, db_session, clock):
    dana = make_user(db_session, "dana")
    sign_in(client, dana)
    assert client.put("/api/yearbook", json={"cover_name": "   "}).status_code == 422
    bad = client.put("/api/yearbook", json={"cover_name": "Dana", "quote": "follow me at example.com"})
    assert bad.status_code == 422 and "link" in bad.json()["detail"]
    good = client.put("/api/yearbook", json={"cover_name": "  Dana <b>  ", "quote": "x" * 200})
    assert good.status_code == 200
    assert good.json()["book"]["cover_name"] == "Dana b" and len(good.json()["book"]["quote"]) == yearbook.QUOTE_MAX


def test_yearbooks_wait_for_opening_day_except_for_admins(client, db_session, monkeypatch):
    Clock(monkeypatch, datetime(2026, 11, 20, 12, 0))
    dana = make_user(db_session, "dana")
    sign_in(client, dana)
    early = client.put("/api/yearbook", json={"cover_name": "Dana"})
    assert early.status_code == 409 and "November 26" in early.json()["detail"]
    assert client.get("/api/yearbook").json()["state"] == "soon"
    monkeypatch.setenv("ADMIN_USERNAMES", "dana")
    assert client.put("/api/yearbook", json={"cover_name": "Dana"}).status_code == 200


def test_picks_only_come_from_shelves_the_owner_shares(client, db_session, clock):
    dana = make_user(db_session, "dana")
    dune = finished_movie(db_session, dana, "Dune: Part Two", rating=9,
                          poster="https://image.tmdb.org/t/p/w500/dune.jpg")
    game = models.VideoGame(user_id=dana.id, title="Hades II", played=True, rating=9)
    db_session.add(game)
    dana.video_games_private = True
    db_session.commit()
    sign_in(client, dana)
    options = client.get("/api/yearbook").json()["options"]
    assert [option["title"] for option in options] == ["Dune: Part Two"]
    assert options[0]["this_year"] is True
    made = make_book(client, dana, picks=[{"category": "movies", "id": dune.id},
                                          {"category": "video-games", "id": game.id},
                                          {"category": "movies", "id": 99999}])
    assert made["book"]["picks"] == [{"category": "movies", "id": dune.id}]
    token = token_of(db_session, dana)
    sign_out(client)
    page = client.get(f"/yearbook/{token}").text
    assert "Dune: Part Two" in page and "Hades II" not in page
    assert "https://image.tmdb.org/t/p/w500/dune.jpg" in page
    assert "1 title finished in 2026" in page
    # A shelf made private later drops its picks and its numbers.
    dana.movies_private = True
    db_session.commit()
    page = client.get(f"/yearbook/{token}").text
    assert "Dune: Part Two" not in page and "finished in 2026" not in page


def test_the_shared_page_is_private_and_has_a_card(client, db_session, clock):
    dana = make_user(db_session, "dana")
    make_book(client, dana)
    token = token_of(db_session, dana)
    sign_out(client)
    response = client.get(f"/yearbook/{token}", headers={"User-Agent": "Mozilla/5.0 Chrome/120"})
    assert response.status_code == 200
    assert "noindex" in response.headers["x-robots-tag"] and "no-store" in response.headers["cache-control"]
    page = response.text
    assert "Class of 2026" in page and ">Dana<" in page and "I&#x27;ll start it after this episode." in page
    assert f"/yearbook/{token}/card.png?v=" in page
    assert 'name="name"' in page and 'name="website"' in page and "Sign the yearbook" in page
    db_session.expire_all()
    assert yearbook.get(db_session, dana.id, 2026).opened == 1
    card = client.get(f"/yearbook/{token}/card.png")
    assert card.status_code == 200 and card.headers["content-type"] == "image/png" and card.content[:4] == b"\x89PNG"
    story = client.get(f"/yearbook/{token}/story.png")
    assert story.status_code == 200 and story.content[:4] == b"\x89PNG"
    from PIL import Image
    import io
    assert Image.open(io.BytesIO(story.content)).size == (1080, 1920)
    again = client.get(f"/yearbook/{token}/story.png", headers={"If-None-Match": story.headers["etag"]})
    assert again.status_code == 304
    assert client.get("/yearbook/not-a-real-token-at-all").status_code == 404


def test_the_owner_sees_their_own_page_without_a_form(client, db_session, clock):
    dana = make_user(db_session, "dana")
    make_book(client, dana)
    token = token_of(db_session, dana)
    page = client.get(f"/yearbook/{token}").text
    assert "This is your yearbook" in page and "data-yearbook-sign" not in page
    db_session.expire_all()
    assert yearbook.get(db_session, dana.id, 2026).opened == 0


# ---------------------------------------------------------------- signing

def test_friends_show_straight_away_and_everyone_else_waits(client, db_session, clock):
    dana = make_user(db_session, "dana")
    sam = make_user(db_session, "sam")
    lee = make_user(db_session, "lee")
    befriend(db_session, sam, dana)
    make_book(client, dana)
    token = token_of(db_session, dana)
    assert sign(client, token, sam, superlative="best_recs").json() == {"status": "shown", "new": True}
    assert sign(client, token, lee).json() == {"status": "waiting", "new": True}
    assert sign(client, token, name="Priya", note="Happy new year!").json() == {"status": "waiting", "new": True}
    sign_out(client)
    page = client.get(f"/yearbook/{token}").text
    assert "sam" in page and "You got me into Frieren" in page
    assert "Priya" not in page and ">lee<" not in page
    assert "1 vote</strong> Most likely to recommend something you end up loving" in page
    bells = {note.type for note in db_session.query(models.Notification).filter_by(user_id=dana.id)}
    assert {"yearbook_signed", "yearbook_waiting"} <= bells
    sign_in(client, dana)
    notes = client.get("/api/yearbook").json()["book"]["notes"]
    assert [note["name"] for note in notes["shown"]] == ["sam"]
    assert {note["name"] for note in notes["waiting"]} == {"lee", "Priya"}
    assert [note["guest"] for note in notes["waiting"] if note["name"] == "Priya"] == [True]


def test_signing_rules(client, db_session, clock):
    dana = make_user(db_session, "dana")
    make_book(client, dana)
    token = token_of(db_session, dana)
    own = sign(client, token, dana)
    assert own.status_code == 403
    assert sign(client, token, note="Hi").status_code == 422  # guests need a name
    for note in ("call me 555-123-4567", "see https://spam.example", "mail me a@b.co", "go to cheapdeals.com now"):
        refused = sign(client, token, name="Spam", note=note)
        assert refused.status_code == 422 and "can't go in" in refused.json()["detail"], note
    assert sign(client, token, name="x", note="ok", superlative="worst_person").status_code == 422
    assert sign(client, token, name="Jo", note=" ").status_code == 422
    # Form bots fill the hidden box: they get a normal answer and nothing is kept.
    trapped = sign(client, token, name="Bot", note="Nice page", website="http://x")
    assert trapped.status_code == 200
    assert db_session.query(models.YearbookSignature).count() == 0


def test_one_address_can_leave_three_guest_notes(client, db_session, clock):
    dana = make_user(db_session, "dana")
    make_book(client, dana)
    token = token_of(db_session, dana)
    for index in range(yearbook.GUEST_PER_ADDRESS):
        assert sign(client, token, name=f"Guest {index}", note="Hello there").status_code == 200
    blocked = sign(client, token, name="Guest again", note="Hello again")
    assert blocked.status_code == 429
    marks = {row.guest_mark for row in db_session.query(models.YearbookSignature)}
    assert len(marks) == 1 and all(len(mark) == 32 for mark in marks)
    assert "testclient" not in next(iter(marks))


def test_members_change_their_note_and_hidden_ones_stay_hidden(client, db_session, clock):
    dana = make_user(db_session, "dana")
    sam = make_user(db_session, "sam")
    befriend(db_session, dana, sam)
    make_book(client, dana)
    token = token_of(db_session, dana)
    sign(client, token, sam)
    changed = sign(client, token, sam, note="Second try", superlative="cries")
    assert changed.json() == {"status": "shown", "new": False}
    assert db_session.query(models.YearbookSignature).count() == 1
    page = client.get(f"/yearbook/{token}").text
    assert "Change your note" in page and "Second try" in page and "Your note is in the yearbook." in page
    note_id = db_session.query(models.YearbookSignature.id).scalar()
    sign_in(client, dana)
    assert client.patch(f"/api/yearbook/notes/{note_id}", json={"action": "hide"}).json() == {"status": "hidden"}
    sign(client, token, sam, note="Third try")
    db_session.expire_all()
    assert db_session.get(models.YearbookSignature, note_id).status == "hidden"
    sign_in(client, sam)
    assert "Only you and Dana can see your note." in client.get(f"/yearbook/{token}").text
    assert client.delete(f"/api/yearbook/sign/{token}").json() == {"removed": True}
    assert db_session.query(models.YearbookSignature).count() == 0


def test_the_owner_lets_notes_in_hides_and_deletes_them(client, db_session, clock):
    dana = make_user(db_session, "dana")
    lee = make_user(db_session, "lee")
    make_book(client, dana)
    make_book(client, lee)
    token = token_of(db_session, dana)
    sign(client, token, name="Priya", note="Happy new year!", superlative="twist")
    note_id = db_session.query(models.YearbookSignature.id).scalar()
    sign_in(client, lee)
    assert client.patch(f"/api/yearbook/notes/{note_id}", json={"action": "show"}).status_code == 404
    assert client.delete(f"/api/yearbook/notes/{note_id}").status_code == 404
    sign_in(client, dana)
    assert client.patch(f"/api/yearbook/notes/{note_id}", json={"action": "pin"}).status_code == 422
    assert client.patch(f"/api/yearbook/notes/{note_id}", json={"action": "show"}).json() == {"status": "shown"}
    sign_out(client)
    page = client.get(f"/yearbook/{token}").text
    assert "Priya" in page and "Most likely to guess the twist" in page
    sign_in(client, dana)
    assert client.delete(f"/api/yearbook/notes/{note_id}").json() == {"deleted": True}
    assert db_session.query(models.YearbookSignature).count() == 0


def test_votes_count_shown_notes_only_and_the_cover_shows_three(db_session, clock):
    dana = make_user(db_session, "dana")
    book, _ = yearbook.save(db_session, dana, 2026, cover_name="Dana", quote=None, picks=[], show_numbers=True,
                            listed=False)
    votes = ["cries", "cries", "twist", "backlog", "best_taste", "twist", "cries"]
    for index, vote in enumerate(votes):
        db_session.add(models.YearbookSignature(yearbook_id=book.id, guest_name=f"G{index}", note="hi", superlative=vote,
                                                status="shown", created_at=OPEN + timedelta(minutes=index)))
    db_session.add(models.YearbookSignature(yearbook_id=book.id, guest_name="W", note="hi", superlative="backlog",
                                            status="waiting"))
    db_session.commit()
    view = yearbook.view(db_session, book, None)
    assert [(entry["key"], entry["votes"]) for entry in view["tally"]] == [("cries", 3), ("twist", 2), ("backlog", 1)]
    assert view["count"] == 7


def test_turning_the_link_off_and_on(client, db_session, clock):
    dana = make_user(db_session, "dana")
    make_book(client, dana)
    token = token_of(db_session, dana)
    assert client.delete("/api/yearbook/link").json() == {"url": None}
    assert client.get(f"/yearbook/{token}").status_code == 404
    assert client.get(f"/yearbook/{token}/card.png").status_code == 404
    assert client.get(f"/yearbook/{token}/story.png").status_code == 404
    assert sign(client, token, name="Jo", note="Hello").status_code == 404
    sign_in(client, dana)
    fresh = client.post("/api/yearbook/link").json()
    assert fresh["path"] != f"/yearbook/{token}"
    assert client.get(fresh["path"]).status_code == 200


def test_deactivated_owners_and_signers_drop_out(client, db_session, clock):
    dana = make_user(db_session, "dana")
    sam = make_user(db_session, "sam")
    befriend(db_session, dana, sam)
    make_book(client, dana)
    token = token_of(db_session, dana)
    sign(client, token, sam, note="From sam")
    sam.is_active = False
    db_session.commit()
    sign_out(client)
    assert "From sam" not in client.get(f"/yearbook/{token}").text
    dana.is_active = False
    db_session.commit()
    assert client.get(f"/yearbook/{token}").status_code == 404


# ---------------------------------------------------------------- closing

def test_signing_and_changes_stop_after_new_years_day(client, db_session, clock):
    dana = make_user(db_session, "dana")
    make_book(client, dana)
    token = token_of(db_session, dana)
    sign(client, token, name="Jo", note="Before the end")
    clock.at = datetime(2027, 1, 2, 12, 30)
    late = sign(client, token, name="Late", note="After the end")
    assert late.status_code == 409 and "closed" in late.json()["detail"]
    sign_in(client, dana)
    assert client.put("/api/yearbook", json={"cover_name": "Dana 2"}).status_code == 409
    mine = client.get("/api/yearbook").json()
    assert mine["state"] == "closed" and mine["can_edit"] is False
    sign_out(client)
    page = client.get(f"/yearbook/{token}").text
    assert "Signing is closed" in page and "data-yearbook-sign data-token" not in page


# ---------------------------------------------------------------- the home card

def test_the_home_card_through_the_season(client, db_session, clock):
    dana = make_user(db_session, "dana")
    sam = make_user(db_session, "sam")
    befriend(db_session, dana, sam)
    sign_in(client, dana)
    start = client.get("/api/yearbook/home").json()
    assert start["show"] and start["stage"] == "start" and start["action"]["path"] == "/yearbook"
    make_book(client, sam)
    sign_in(client, dana)
    start = client.get("/api/yearbook/home").json()
    assert [friend["name"] for friend in start["friends"]] == ["sam"] and start["status"] == "new"
    make_book(client, dana)
    token = token_of(db_session, dana)
    quiet = client.get("/api/yearbook/home").json()
    assert quiet["stage"] == "open" and quiet["notes"] == 0 and "group chat" in quiet["line"]
    sign(client, token, name="Priya", note="Hi Dana")
    sign_in(client, dana)
    waiting = client.get("/api/yearbook/home").json()
    assert waiting["waiting"] == 1 and waiting["status"] == "new" and waiting["action"]["path"] == "/yearbook#waiting"
    client.get("/api/yearbook?seen=true")
    note_id = db_session.query(models.YearbookSignature.id).scalar()
    client.patch(f"/api/yearbook/notes/{note_id}", json={"action": "show"})
    clock.at = OPEN + timedelta(minutes=5)
    sign(client, token, sam, note="From sam")
    sign_in(client, dana)
    fresh = client.get("/api/yearbook/home").json()
    assert fresh["new"] == 1 and fresh["notes"] == 2
    clock.at = datetime(2027, 1, 5)
    closed = client.get("/api/yearbook/home").json()
    assert closed["stage"] == "closed" and "2 notes" in closed["line"] and closed["friends"] == []
    clock.at = datetime(2027, 1, 20)
    assert client.get("/api/yearbook/home").json() == {"show": False}


def test_the_home_card_is_in_the_dashboard(client):
    index = (ROOT / "app/templates/index.html").read_text()
    assert 'id="yearbookHome"' in index and "/static/yearbook-home.js?v=20261125-yearbook-1" in index
    assert "/static/yearbook-home.css?v=20261125-yearbook-1" in index
    layout = (ROOT / "app/static/home-layout.js").read_text()
    assert "'#yearbook': 'yearbookHome'" in layout and "id === 'yearbookHome'" in layout
    home = (ROOT / "app/static/dashboard/home.js").read_text()
    assert "OmniYearbookHome?.refresh()" in home and "OmniYearbookHome?.reset()" in home


# ---------------------------------------------------------------- the class page

def test_the_class_page_is_for_members_and_lists_only_opted_in_books(client, db_session, clock):
    dana = make_user(db_session, "dana")
    sam = make_user(db_session, "sam")
    make_book(client, dana, listed=True, quote="Listed")
    make_book(client, sam, quote="Not listed")
    sign_out(client)
    guest = client.get("/yearbook/class/2026")
    assert "class page is for members" in guest.text
    sign_in(client, sam)
    page = client.get("/yearbook/class/2026")
    assert "noindex" in page.headers["x-robots-tag"]
    assert "Listed" in page.text and "Not listed" not in page.text


# ---------------------------------------------------------------- email

def run(now, sender, monkeypatch, db_factory):
    monkeypatch.setattr(yearbook, "allowance", lambda db, at: 10)
    return asyncio.run(yearbook.run_once(db_factory, now=now, sender=sender))


def test_new_note_emails_wait_then_come_at_most_three_times(client, db_session, clock, monkeypatch):
    from tests.conftest import TestingSessionLocal
    dana = make_user(db_session, "dana")
    make_book(client, dana)
    token = token_of(db_session, dana)
    sent = []

    async def sender(to, subject, html, unsubscribe_url):
        sent.append((to, subject, html))

    sign(client, token, name="Priya", note="Hi Dana")
    assert run(OPEN + timedelta(hours=2), sender, monkeypatch, TestingSessionLocal)["sent"] == 0  # bell first
    assert run(OPEN + timedelta(hours=21), sender, monkeypatch, TestingSessionLocal)["sent"] == 1
    assert sent[0][0] == "dana@example.test" and "waiting in your 2026 yearbook" in sent[0][1]
    assert "utm_campaign=yearbook" in sent[0][2] and "Unsubscribe" in sent[0][2]
    # Nothing new: nothing sent. Something new inside four days: still nothing.
    assert run(OPEN + timedelta(days=2), sender, monkeypatch, TestingSessionLocal)["sent"] == 0
    for step in (1, 2, 3):
        clock.at = OPEN + timedelta(days=5 * step)
        sign(client, token, name=f"Friend {step}", note="Another note")
        run(clock.at + timedelta(hours=21), sender, monkeypatch, TestingSessionLocal)
    assert len(sent) == yearbook.NOTES_EMAILS_MAX
    keys = {key for key, in db_session.query(models.EmailCampaignSend.campaign_key)}
    assert {key.rsplit("-", 1)[-1] for key in keys} == {"1", "2", "3"}


def test_the_closing_email_and_bell(client, db_session, clock, monkeypatch):
    from tests.conftest import TestingSessionLocal
    dana = make_user(db_session, "dana")
    sam = make_user(db_session, "sam")
    lee = make_user(db_session, "lee")
    befriend(db_session, dana, sam)
    make_book(client, dana)
    make_book(client, lee)  # nobody signs lee's, so lee gets nothing
    token = token_of(db_session, dana)
    sign(client, token, sam, note="See you next year", superlative="soundtrack")
    sent = []

    async def sender(to, subject, html, unsubscribe_url):
        sent.append((to, subject, html))

    after = datetime(2027, 1, 2, 13, 0)
    clock.at = after
    result = run(after, sender, monkeypatch, TestingSessionLocal)
    closing = [entry for entry in sent if "closed" in entry[1]]
    assert len(closing) == 1 and closing[0][0] == "dana@example.test"
    assert "1 note to keep" in closing[0][1] and "know the whole soundtrack" in closing[0][2] and "sam" in closing[0][2]
    assert result["closed_notes"] == 1
    run(after + timedelta(hours=1), sender, monkeypatch, TestingSessionLocal)
    assert len([entry for entry in sent if "closed" in entry[1]]) == 1
    assert db_session.query(models.Notification).filter_by(user_id=dana.id, type="yearbook_closed").count() == 1
    assert not [entry for entry in sent if entry[0] == "lee@example.test"]


def test_opted_out_owners_and_the_off_switch_get_nothing(client, db_session, clock, monkeypatch):
    from tests.conftest import TestingSessionLocal
    dana = make_user(db_session, "dana")
    make_book(client, dana)
    token = token_of(db_session, dana)
    sign(client, token, name="Priya", note="Hi Dana")
    sent = []

    async def sender(to, subject, html, unsubscribe_url):
        sent.append(to)

    monkeypatch.setenv("YEARBOOK_EMAILS", "off")
    run(OPEN + timedelta(days=1), sender, monkeypatch, TestingSessionLocal)
    assert sent == []
    monkeypatch.delenv("YEARBOOK_EMAILS")
    db_session.add(models.EmailOptOut(user_id=dana.id))
    db_session.commit()
    run(OPEN + timedelta(days=1), sender, monkeypatch, TestingSessionLocal)
    assert sent == []


# ---------------------------------------------------------------- wiring

def test_wiring_push_funnel_nav_sitemap_and_returns(client):
    from app import funnel, site_chrome, site_traffic, web_push
    topics = {topic[0]: topic for topic in web_push.TOPICS}
    assert set(topics["yearbook"][4]) == set(yearbook.NOTE_TYPES)
    assert all(kind in web_push.TITLES for kind in yearbook.NOTE_TYPES)
    events = {name for name, _label in funnel.GUEST}
    assert {"yearbook_started", "yearbook_link_opened", "yearbook_signed", "yearbook_signed_guest",
            "yearbook_let_in", "yearbook_email_sent"} <= events
    assert {"yearbook_shared", "yearbook_signup_clicked"} <= funnel.CLIENT_EVENTS
    assert ("Yearbook", "/yearbook") in [entry for _group, entries in site_chrome.FOOTER_GROUPS for entry in entries]
    assert site_traffic.PRIVATE_LINK.match("/yearbook/abcdefghijklmnop")
    assert "/yearbook" in client.get("/sitemap.xml").text
    auth_js = (ROOT / "app/static/auth.js").read_text()
    assert "Yearbook: the member page" in auth_js


def test_year_in_review_points_at_the_yearbook_while_it_is_open(client, db_session, monkeypatch):
    from app.routers import year_in_review as recap_router
    dana = make_user(db_session, "dana")
    monkeypatch.setattr(yearbook, "_now", lambda: OPEN)
    box = recap_router._yearbook_box(db_session, dana, 2026)
    assert "Make my yearbook" in box and 'href="/yearbook"' in box
    yearbook.save(db_session, dana, 2026, cover_name="Dana", quote=None, picks=[], show_numbers=True, listed=False)
    assert "Open my yearbook" in recap_router._yearbook_box(db_session, dana, 2026)
    monkeypatch.setattr(yearbook, "_now", lambda: datetime(2027, 1, 3))
    assert recap_router._yearbook_box(db_session, dana, 2026) == ""
