"""Group polls (/tonight): a member asks what to watch, friends and visitors vote by link."""
from datetime import datetime, timedelta

import pytest

from app import models, title_search, tonight_polls
from app.visitor_identity import VISITOR_COOKIE
from tests.test_shared_lists import _as, _friends, _me
from tests.test_title_pages import add_movie, member


@pytest.fixture(autouse=True)
def fresh_search_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


def _make(client, options=None, **extra):
    options = options or [{"kind": "movie", "title": "Heat", "year": 1995},
                           {"kind": "movie", "title": "Arrival", "year": 2016},
                           {"kind": "movie", "title": "Paddington 2", "year": 2017}]
    response = client.post("/api/tonight", json=dict({"options": options}, **extra))
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "private, no-store"
    return response.json()


def _ids(client, token):
    return [option["id"] for option in client.get(f"/api/tonight/{token}").json()["options"]]


def test_make_a_poll_and_vote(authenticated_client, db_session):
    made = _make(authenticated_client)
    assert made["question"] == "What should we watch tonight?"
    assert made["url"].endswith(made["path"]) and made["path"].startswith("/tonight/")
    token = made["token"]

    state = authenticated_client.get(f"/api/tonight/{token}").json()
    assert [option["title"] for option in state["options"]] == ["Heat", "Arrival", "Paddington 2"]
    assert state["owner"]["you"] is True and state["closed"] is False and state["total"] == 0
    assert state["closes_label"] == "Closes in 3 hours"

    heat, arrival, _ = _ids(authenticated_client, token)
    voted = authenticated_client.put(f"/api/tonight/{token}/vote", json={"option_id": arrival}).json()
    assert voted["me"]["option_id"] == arrival and voted["total"] == 1 and voted["leading"] == [arrival]
    # Changing your mind moves the vote, it doesn't add one.
    voted = authenticated_client.put(f"/api/tonight/{token}/vote", json={"option_id": heat}).json()
    assert voted["total"] == 1 and voted["me"]["option_id"] == heat
    assert voted["options"][0]["voters"][0]["name"] == "testuser"
    # The owner isn't notified about their own vote.
    assert db_session.query(models.Notification).filter_by(type="tonight_poll_vote").count() == 0

    cleared = authenticated_client.delete(f"/api/tonight/{token}/vote").json()
    assert cleared["total"] == 0 and cleared["me"]["option_id"] is None

    [mine] = authenticated_client.get("/api/tonight").json()["polls"]
    assert mine["token"] == token and mine["options"] == 3 and mine["closed"] is False


def test_visitors_vote_without_an_account(authenticated_client, db_session):
    owner = _me(db_session)
    token = _make(authenticated_client, question="  Friday   film? ")["token"]
    heat, arrival, paddington = _ids(authenticated_client, token)
    _as(authenticated_client, None)

    page = authenticated_client.get(f"/tonight/{token}")
    assert page.status_code == 200 and "Friday film?" in page.text
    assert page.headers["x-robots-tag"] == "noindex, nofollow"
    assert "Run the next movie night yourself" in page.text
    invite = db_session.query(models.FriendInvite).filter_by(user_id=owner.id).one()
    assert f"/?invite={invite.token}&amp;next=%2Ftonight%2F{token}#signup" in page.text
    assert VISITOR_COOKIE in authenticated_client.cookies

    voted = authenticated_client.put(f"/api/tonight/{token}/vote", json={"option_id": paddington, "name": " Priya "})
    assert voted.status_code == 200, voted.text
    data = voted.json()
    assert data["me"] == {"option_id": paddington, "name": "Priya", "signed_in": False, "owner": False}
    assert data["options"][2]["voters"] == [{"name": "Priya", "initials": "P", "member": False, "you": True}]
    note = db_session.query(models.Notification).filter_by(user_id=owner.id, type="tonight_poll_vote").one()
    assert note.message == 'Priya voted in your poll "Friday film?".' and note.link == f"/tonight/{token}"

    # A second visitor (a fresh browser) adds a vote; the owner still has one unread note.
    authenticated_client.cookies.clear()
    authenticated_client.get(f"/tonight/{token}")
    authenticated_client.put(f"/api/tonight/{token}/vote", json={"option_id": heat})
    state = authenticated_client.get(f"/api/tonight/{token}").json()
    assert state["total"] == 2 and state["options"][0]["others"] == 0
    assert state["options"][0]["voters"] == [{"name": "You", "initials": "Y", "member": False, "you": True}]
    assert db_session.query(models.Notification).filter_by(user_id=owner.id, type="tonight_poll_vote").count() == 1

    # Visitors can't close or delete it.
    assert authenticated_client.post(f"/api/tonight/{token}/close").status_code == 401
    assert authenticated_client.delete(f"/api/tonight/{token}").status_code == 401


def test_a_visitors_vote_follows_them_into_their_account(authenticated_client, db_session):
    owner = _me(db_session)
    token = _make(authenticated_client)["token"]
    _, arrival, _ = _ids(authenticated_client, token)
    sam = member(db_session, "sam")
    db_session.commit()
    _as(authenticated_client, None)
    authenticated_client.get(f"/tonight/{token}")
    visitor = authenticated_client.cookies.get(VISITOR_COOKIE)
    authenticated_client.put(f"/api/tonight/{token}/vote", json={"option_id": arrival, "name": "Sam"})

    _as(authenticated_client, sam)
    authenticated_client.cookies.set(VISITOR_COOKIE, visitor)
    state = authenticated_client.get(f"/api/tonight/{token}").json()
    assert state["total"] == 1 and state["me"]["option_id"] == arrival
    assert state["options"][1]["voters"] == [{"name": "sam", "initials": "S", "member": True, "you": True}]
    row = db_session.query(models.TonightPollVote).one()
    db_session.refresh(row)
    assert row.user_id == sam.id and row.name is None
    assert owner.id != sam.id


def test_closing_picks_a_winner_and_tells_voters(authenticated_client, db_session):
    owner = _me(db_session)
    token = _make(authenticated_client)["token"]
    heat, arrival, _ = _ids(authenticated_client, token)
    # Nobody voted yet, so there's nothing to call.
    assert authenticated_client.post(f"/api/tonight/{token}/close").status_code == 400

    sam, kai = member(db_session, "sam"), member(db_session, "kai")
    db_session.commit()
    for voter, choice in ((sam, arrival), (kai, arrival), (owner, heat)):
        _as(authenticated_client, voter)
        assert authenticated_client.put(f"/api/tonight/{token}/vote", json={"option_id": choice}).status_code == 200

    _as(authenticated_client, sam)
    assert authenticated_client.post(f"/api/tonight/{token}/close").status_code == 403
    _as(authenticated_client, owner)
    closed = authenticated_client.post(f"/api/tonight/{token}/close").json()
    assert closed["closed"] is True and closed["winner"] == arrival and closed["closes_label"] == "Voting closed"
    notes = db_session.query(models.Notification).filter_by(type="tonight_poll_result").all()
    assert sorted(note.user_id for note in notes) == sorted([sam.id, kai.id])
    assert notes[0].message == 'Arrival won testuser\'s poll "What should we watch tonight?".'

    _as(authenticated_client, kai)
    late = authenticated_client.put(f"/api/tonight/{token}/vote", json={"option_id": heat})
    assert late.status_code == 409


def test_polls_close_on_their_own_and_ties_are_drawn(authenticated_client, db_session):
    token = _make(authenticated_client, hours=1)["token"]
    heat, arrival, _ = _ids(authenticated_client, token)
    sam = member(db_session, "sam")
    db_session.commit()
    authenticated_client.put(f"/api/tonight/{token}/vote", json={"option_id": heat})
    _as(authenticated_client, sam)
    authenticated_client.put(f"/api/tonight/{token}/vote", json={"option_id": arrival})

    poll = db_session.query(models.TonightPoll).one()
    poll.closes_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()
    state = authenticated_client.get(f"/api/tonight/{token}").json()
    assert state["closed"] is True and state["winner"] in (heat, arrival)
    # Everyone sees the same winner from then on.
    for _ in range(3):
        assert authenticated_client.get(f"/api/tonight/{token}").json()["winner"] == state["winner"]


def test_options_from_the_library_and_next_up(authenticated_client, db_session):
    owner = _me(db_session)
    dune = add_movie(db_session, owner, title="Dune", year=2021, poster_url="https://img.example/dune.jpg")
    add_movie(db_session, owner, title="Heat", year=1995)
    add_movie(db_session, owner, title="Seen It", year=2001, watched=True)
    db_session.add(models.NextUpItem(user_id=owner.id, category="movies", item_id=dune.id, position=0))
    stranger = member(db_session, "stranger")
    theirs = add_movie(db_session, stranger, title="Theirs", year=2000)
    db_session.commit()

    data = authenticated_client.get("/api/tonight/suggestions").json()
    titles = [(entry["title"], entry["source"]) for entry in data["titles"]]
    assert titles[0] == ("Dune", "Next Up") and ("Heat", "Library") in titles
    assert all(title != "Seen It" for title, _ in titles)
    assert data["titles"][0]["image"] == "https://img.example/dune.jpg"

    made = _make(authenticated_client, options=[{"category": "movies", "item_id": dune.id},
                                                {"kind": "game", "title": "Outer Wilds"}])
    state = authenticated_client.get(f"/api/tonight/{made['token']}").json()
    assert made["question"] == "What should we start tonight?"
    assert state["options"][0]["image"] == "https://img.example/dune.jpg" and state["options"][1]["label"] == "Game"

    # Someone else's library item can't be used.
    other = authenticated_client.post("/api/tonight", json={"options": [{"category": "movies", "item_id": theirs.id},
                                                                        {"kind": "movie", "title": "Heat"}]})
    assert other.status_code == 404


def test_poll_rules(authenticated_client, db_session):
    one = authenticated_client.post("/api/tonight", json={"options": [{"kind": "movie", "title": "Heat"},
                                                                      {"kind": "movie", "title": " heat "}]})
    assert one.status_code == 400 and "at least 2" in one.json()["detail"]
    many = [{"kind": "movie", "title": f"Film {n}"} for n in range(9)]
    assert authenticated_client.post("/api/tonight", json={"options": many}).status_code == 400
    assert authenticated_client.post("/api/tonight", json={"options": many[:2], "hours": 5}).status_code == 400
    assert authenticated_client.post("/api/tonight", json={"options": [{"kind": "boat", "title": "A"},
                                                                       {"kind": "movie", "title": "B"}]}).status_code == 400
    token = _make(authenticated_client)["token"]
    other = _make(authenticated_client)["token"]
    wrong = _ids(authenticated_client, other)[0]
    assert authenticated_client.put(f"/api/tonight/{token}/vote", json={"option_id": wrong}).status_code == 404
    assert authenticated_client.get("/api/tonight/not-a-real-token").status_code == 404
    assert authenticated_client.get("/tonight/aaaaaaaaaaaaaaaaaaaa").status_code == 404


def test_friends_can_be_asked_and_deleting_cleans_up(authenticated_client, db_session):
    owner = _me(db_session)
    sam, stranger = member(db_session, "sam"), member(db_session, "stranger")
    _friends(db_session, owner, sam)
    db_session.commit()
    suggestions = authenticated_client.get("/api/tonight/suggestions").json()
    assert suggestions["friends"] == [{"id": sam.id, "username": "sam"}]
    made = _make(authenticated_client, friend_ids=[sam.id, stranger.id, owner.id])
    assert made["asked"] == 1
    note = db_session.query(models.Notification).filter_by(type="tonight_poll").one()
    assert note.user_id == sam.id and note.message == 'testuser wants your vote: "What should we watch tonight?"'

    _as(authenticated_client, sam)
    assert authenticated_client.get(made["path"]).status_code == 200
    db_session.refresh(note)
    assert note.read_at is not None  # Opening the poll clears its note.
    assert authenticated_client.delete(f"/api/tonight/{made['token']}").status_code == 403

    _as(authenticated_client, owner)
    assert authenticated_client.delete(f"/api/tonight/{made['token']}").status_code == 204
    assert db_session.query(models.TonightPoll).count() == 0
    assert db_session.query(models.TonightPollOption).count() == 0
    assert authenticated_client.get(made["path"]).status_code == 404


def test_a_deactivated_owners_poll_is_gone(authenticated_client, db_session):
    token = _make(authenticated_client)["token"]
    owner = _me(db_session)
    owner.is_active = False
    db_session.commit()
    _as(authenticated_client, None)
    assert authenticated_client.get(f"/tonight/{token}").status_code == 404


def test_tonight_page_for_visitors_and_members(authenticated_client, db_session):
    page = authenticated_client.get("/tonight")
    assert page.status_code == 200 and "New poll" in page.text and "tonight.js" in page.text
    _as(authenticated_client, None)
    page = authenticated_client.get("/tonight")
    assert page.status_code == 200 and "Make a poll, free" in page.text
    assert "index, follow" in page.text and "How to pick something everyone will actually enjoy" in page.text
    assert "/tonight" in authenticated_client.get("/sitemap.xml").text


def test_default_question_matches_the_titles():
    assert tonight_polls.default_question([{"kind": "game"}, {"kind": "game"}]) == "What should we play tonight?"
    assert tonight_polls.default_question([{"kind": "book"}]) == "What should we read tonight?"
