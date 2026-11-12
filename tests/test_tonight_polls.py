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
    assert page.status_code == 200 and "Get the link" in page.text and "New poll" in page.text
    assert "index, follow" in page.text and "How to pick something everyone will actually enjoy" in page.text
    assert "/tonight" in authenticated_client.get("/sitemap.xml").text


def test_default_question_matches_the_titles():
    assert tonight_polls.default_question([{"kind": "game"}, {"kind": "game"}]) == "What should we play tonight?"
    assert tonight_polls.default_question([{"kind": "book"}]) == "What should we read tonight?"


# ---------------------------------------------------------------- Nov 2026: link previews, visitor shortlists, rounds

def _close_with_winner(client, db_session, token, winner_index=1):
    """Two members vote for one title, then the owner closes the poll."""
    owner = _me(db_session)
    ids = _ids(client, token)
    sam, kai = member(db_session, "sam"), member(db_session, "kai")
    db_session.commit()
    for voter in (sam, kai):
        _as(client, voter)
        assert client.put(f"/api/tonight/{token}/vote", json={"option_id": ids[winner_index]}).status_code == 200
    _as(client, owner)
    closed = client.post(f"/api/tonight/{token}/close").json()
    assert closed["winner"] == ids[winner_index]
    return owner, sam, kai, ids


def test_poll_link_has_its_own_preview_image(authenticated_client, db_session):
    token = _make(authenticated_client)["token"]
    _as(authenticated_client, None)
    page = authenticated_client.get(f"/tonight/{token}").text
    assert f'<meta property="og:image" content="https://omnitrackr.xyz/tonight/{token}/card.png?v=open">' in page
    assert '<meta name="twitter:card" content="summary_large_image">' in page
    assert "omnitrackr_vortex.png" not in page.split("</head>")[0]
    assert "testuser wants your vote: Heat, Arrival or Paddington 2. One tap, no account needed." in page

    card = authenticated_client.get(f"/tonight/{token}/card.png")
    assert card.status_code == 200 and card.headers["content-type"] == "image/png"
    assert card.content.startswith(b"\x89PNG") and card.headers["x-robots-tag"] == "noindex"
    assert card.headers["cache-control"] == "private, max-age=300"
    again = authenticated_client.get(f"/tonight/{token}/card.png", headers={"If-None-Match": card.headers["etag"]})
    assert again.status_code == 304
    # Votes don't change an open poll's card, so a chat app's copy stays right.
    heat = _ids(authenticated_client, token)[0]
    authenticated_client.put(f"/api/tonight/{token}/vote", json={"option_id": heat})
    assert authenticated_client.get(f"/tonight/{token}/card.png").headers["etag"] == card.headers["etag"]
    assert authenticated_client.get("/tonight/aaaaaaaaaaaaaaaaaaaa/card.png").status_code == 404


def test_the_preview_names_the_winner_once_voting_closes(authenticated_client, db_session):
    token = _make(authenticated_client)["token"]
    before = authenticated_client.get(f"/tonight/{token}/card.png")
    _, _, _, ids = _close_with_winner(authenticated_client, db_session, token)
    poll = db_session.query(models.TonightPoll).one()
    owner = _me(db_session)
    assert tonight_polls.preview_line(poll, owner) == "The group picked Arrival. See how the vote went."
    facts = tonight_polls.card_facts(db_session, poll, owner)
    assert facts["winner"] == ("Arrival", "Movie", 2016) and facts["winner_votes"] == 2 and facts["total"] == 2
    after = authenticated_client.get(f"/tonight/{token}/card.png")
    assert after.status_code == 200 and after.headers["etag"] != before.headers["etag"]
    page = authenticated_client.get(f"/tonight/{token}").text
    assert f"card.png?v=won{ids[1]}" in page


def test_card_draws_long_and_short_polls():
    from app import tonight_card
    many = [("Movie", f"A fairly long film title number {n} that keeps going", 2000 + n) for n in range(8)]
    for facts in (
        {"question": "Q?", "owner": "dan", "closed": False, "options": many[:2], "winner": None, "winner_votes": 0, "total": 0},
        {"question": "Which of these are we finally going to start this weekend, honestly now?" * 2, "owner": "a" * 50,
         "closed": False, "options": many, "winner": None, "winner_votes": 0, "total": 0},
        {"question": "Q?", "owner": "dan", "closed": True, "options": many[:3], "winner": None, "winner_votes": 0, "total": 0},
        {"question": "Q?", "owner": "dan", "closed": True, "options": many, "winner": many[0][1:2] + ("Movie", None),
         "winner_votes": 1, "total": 1},
    ):
        assert tonight_card.render(facts).startswith(b"\x89PNG")


def test_visitors_build_a_shortlist_before_signing_up(authenticated_client, db_session):
    owner = _me(db_session)
    others = [member(db_session, name) for name in ("sam", "kai")]
    for user in [owner] + others:
        add_movie(db_session, user, title="Dune", year=2021, poster_url="https://img.example/dune.jpg")
        add_movie(db_session, user, title="No Art", year=2001)
    db_session.commit()
    _as(authenticated_client, None)

    page = authenticated_client.get("/tonight")
    assert page.status_code == 200 and 'data-guest="1"' in page.text and "Get the link" in page.text
    assert "You don't need an account to build the shortlist." in page.text
    assert "index, follow" in page.text and "How to pick something everyone will actually enjoy" in page.text
    assert "Run the losers back next week" in page.text

    starters = authenticated_client.get("/api/tonight/starters")
    assert starters.status_code == 200 and starters.headers["cache-control"] == "public, max-age=600"
    titles = starters.json()["titles"]
    # Only titles with a cover, and nothing about who tracks them.
    assert [entry["title"] for entry in titles] == ["Dune"]
    assert set(titles[0]) == {"kind", "label", "title", "year", "slug", "image"} and titles[0]["slug"] == "dune-2021"
    # Making the poll itself still needs the account.
    assert authenticated_client.post("/api/tonight", json={"options": [{"kind": "movie", "title": "Dune"},
                                                                       {"kind": "movie", "title": "Heat"}]}).status_code == 401


def test_another_round_drops_the_winner_and_the_old_link_points_at_it(authenticated_client, db_session):
    token = _make(authenticated_client, hours=1)["token"]
    # Still open: no next round yet.
    assert authenticated_client.post(f"/api/tonight/{token}/again", json={}).status_code == 409
    owner, sam, kai, ids = _close_with_winner(authenticated_client, db_session, token)

    _as(authenticated_client, sam)
    assert authenticated_client.post(f"/api/tonight/{token}/again", json={}).status_code == 403
    _as(authenticated_client, owner)
    made = authenticated_client.post(f"/api/tonight/{token}/again", json={})
    assert made.status_code == 201 and made.json()["made"] is True
    fresh = made.json()["token"]
    assert fresh != token

    state = authenticated_client.get(f"/api/tonight/{fresh}").json()
    assert [option["title"] for option in state["options"]] == ["Heat", "Paddington 2"]
    assert state["round"] == 2 and state["closed"] is False and state["total"] == 0
    assert state["previous"] == {"path": f"/tonight/{token}", "winner": "Arrival"}
    # Closed early, so the length picked last time is unknown and the round gets the usual three hours.
    assert state["question"] == "What should we watch tonight?" and state["closes_label"] == "Closes in 3 hours"
    old = authenticated_client.get(f"/api/tonight/{token}").json()
    assert old["round"] == 1 and old["previous"] is None
    assert old["next"] == {"path": f"/tonight/{fresh}", "closed": False, "closes_label": "Closes in 3 hours"}
    # The old round is untouched.
    assert old["winner"] == ids[1] and old["total"] == 2

    # Members who voted last time hear about it; pressing the button twice doesn't make two polls.
    notes = db_session.query(models.Notification).filter_by(type="tonight_poll", link=f"/tonight/{fresh}").all()
    assert sorted(note.user_id for note in notes) == sorted([sam.id, kai.id])
    assert notes[0].message == 'testuser started another round: "What should we watch tonight?"'
    twice = authenticated_client.post(f"/api/tonight/{token}/again", json={})
    assert twice.status_code == 200 and twice.json()["token"] == fresh and twice.json()["made"] is False
    assert db_session.query(models.TonightPoll).count() == 2

    # Deleting the new round frees the old poll to start another.
    assert authenticated_client.delete(f"/api/tonight/{fresh}").status_code == 204
    assert authenticated_client.get(f"/api/tonight/{token}").json()["next"] is None


def test_another_round_keeps_every_title_when_asked_or_when_nobody_voted(authenticated_client, db_session):
    two = [{"kind": "movie", "title": "Heat", "year": 1995}, {"kind": "movie", "title": "Arrival", "year": 2016}]
    token = _make(authenticated_client, options=two)["token"]
    _close_with_winner(authenticated_client, db_session, token)
    # Without the winner only one title would be left.
    short = authenticated_client.post(f"/api/tonight/{token}/again", json={})
    assert short.status_code == 400 and "only one title left" in short.json()["detail"]
    kept = authenticated_client.post(f"/api/tonight/{token}/again", json={"keep_winner": True}).json()
    assert len(_ids(authenticated_client, kept["token"])) == 2

    quiet = _make(authenticated_client)["token"]
    poll = db_session.query(models.TonightPoll).filter_by(token=quiet).one()
    poll.closes_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()
    assert authenticated_client.get(f"/api/tonight/{quiet}").json()["winner"] is None
    rerun = authenticated_client.post(f"/api/tonight/{quiet}/again", json={}).json()
    assert len(_ids(authenticated_client, rerun["token"])) == 3


def test_a_round_that_ran_its_full_time_gets_the_same_length_again(authenticated_client, db_session):
    token = _make(authenticated_client, hours=24)["token"]
    poll = db_session.query(models.TonightPoll).filter_by(token=token).one()
    poll.created_at -= timedelta(hours=25)
    poll.closes_at -= timedelta(hours=25)
    db_session.commit()
    fresh = authenticated_client.post(f"/api/tonight/{token}/again", json={}).json()["token"]
    again = db_session.query(models.TonightPoll).filter_by(token=fresh).one()
    assert round((again.closes_at - again.created_at).total_seconds() / 3600) == 24 and again.previous_id == poll.id


def test_a_round_copies_art_and_title_pages_from_the_round_before(authenticated_client, db_session):
    owner = _me(db_session)
    dune = add_movie(db_session, owner, title="Dune", year=2021, poster_url="https://img.example/dune.jpg")
    db_session.commit()
    token = _make(authenticated_client, options=[{"category": "movies", "item_id": dune.id},
                                                  {"kind": "movie", "title": "Heat", "year": 1995},
                                                  {"kind": "movie", "title": "Arrival", "year": 2016}])["token"]
    _close_with_winner(authenticated_client, db_session, token)
    fresh = authenticated_client.post(f"/api/tonight/{token}/again", json={}).json()["token"]
    state = authenticated_client.get(f"/api/tonight/{fresh}").json()
    assert state["options"][0]["title"] == "Dune" and state["options"][0]["image"] == "https://img.example/dune.jpg"


def test_keeping_the_winner_adds_it_to_the_library_and_next_up(authenticated_client, db_session):
    token = _make(authenticated_client)["token"]
    assert authenticated_client.post(f"/api/tonight/{token}/keep", json={"queue": True}).status_code == 409
    owner, sam, _, ids = _close_with_winner(authenticated_client, db_session, token)

    kept = authenticated_client.post(f"/api/tonight/{token}/keep", json={"queue": True})
    assert kept.status_code == 200, kept.text
    assert kept.json() == {"state": "created", "queued": True, "in_queue": True, "title": "Arrival", "category": "movies"}
    movie = db_session.query(models.Movie).filter_by(user_id=owner.id).one()
    assert movie.title == "Arrival" and movie.year == 2016 and not movie.watched and movie.rating is None
    queued = db_session.query(models.NextUpItem).filter_by(user_id=owner.id).one()
    assert queued.category == "movies" and queued.item_id == movie.id
    # A second press changes nothing.
    again = authenticated_client.post(f"/api/tonight/{token}/keep", json={"queue": True}).json()
    assert again["state"] == "existing" and again["queued"] is False
    assert db_session.query(models.Movie).filter_by(user_id=owner.id).count() == 1
    assert db_session.query(models.NextUpItem).filter_by(user_id=owner.id).count() == 1

    # Another voter who already has it rated keeps their row exactly as it was.
    theirs = add_movie(db_session, sam, title="arrival", year=2016, rating=9.0, watched=True, review="Loved it")
    db_session.commit()
    _as(authenticated_client, sam)
    result = authenticated_client.post(f"/api/tonight/{token}/keep", json={}).json()
    assert result == {"state": "existing", "queued": False, "in_queue": False, "title": "Arrival", "category": "movies"}
    db_session.refresh(theirs)
    assert theirs.rating == 9.0 and theirs.watched is True and theirs.review == "Loved it"
    assert db_session.query(models.NextUpItem).filter_by(user_id=sam.id).count() == 0
    # Any title on the poll can be kept, but not one from another poll.
    assert authenticated_client.post(f"/api/tonight/{token}/keep", json={"option_id": ids[0]}).json()["title"] == "Heat"
    assert authenticated_client.post(f"/api/tonight/{token}/keep", json={"option_id": 999999}).status_code == 404
    _as(authenticated_client, None)
    assert authenticated_client.post(f"/api/tonight/{token}/keep", json={}).status_code == 401


@pytest.mark.parametrize("kind,model", [("tv", models.TVShow), ("anime", models.Anime), ("game", models.VideoGame),
                                        ("album", models.Music), ("book", models.Book), ("manga", models.Manga),
                                        ("podcast", models.Podcast), ("audiobook", models.Audiobook)])
def test_keeping_works_for_every_kind_of_title(authenticated_client, db_session, kind, model):
    token = _make(authenticated_client, options=[{"kind": kind, "title": "Typed By Hand", "year": 2020},
                                                  {"kind": kind, "title": "The Other One"}])["token"]
    owner, _, _, _ = _close_with_winner(authenticated_client, db_session, token, winner_index=0)
    kept = authenticated_client.post(f"/api/tonight/{token}/keep", json={"queue": True})
    assert kept.status_code == 200, kept.text
    row = db_session.query(model).filter_by(user_id=owner.id).one()
    assert row.title == "Typed By Hand"
    assert db_session.query(models.NextUpItem).filter_by(user_id=owner.id, item_id=row.id).count() == 1


def test_where_to_watch_the_winner(authenticated_client, db_session):
    from app import title_metadata
    from tests.test_where_to_watch import MOVIE_META, WHERE
    token = _make(authenticated_client)["token"]
    # Nothing to look up while voting is open.
    assert authenticated_client.get(f"/api/tonight/{token}/where").status_code == 404
    title_metadata.store(db_session, "movie:arrival:2016", MOVIE_META, "ok")
    title_metadata.store(db_session, "where:movie:arrival:2016", WHERE, "ok")
    _close_with_winner(authenticated_client, db_session, token)
    _as(authenticated_client, None)  # Visitors see it too.
    response = authenticated_client.get(f"/api/tonight/{token}/where")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "Arrival" and body["heading"] == "Where to watch"
    assert body["groups"][0]["providers"][0]["name"] == "Netflix" and body["tmdb_notice"] is True
    assert response.headers["cache-control"] == "private, no-store"


def test_poll_round_migration_is_additive(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect, text
    from app import migrations
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE tonight_polls (id INTEGER PRIMARY KEY, token VARCHAR(32), owner_id INTEGER, "
                          "question VARCHAR(120), created_at TIMESTAMP, closes_at TIMESTAMP, closed_at TIMESTAMP, winner_id INTEGER)"))
        conn.execute(text("INSERT INTO tonight_polls (id, token, owner_id, question) VALUES (1, 'abc', 7, 'Old poll?')"))
    monkeypatch.setattr(migrations, "engine", engine)
    migrations.add_poll_round_column()
    migrations.add_poll_round_column()  # Running it again is harmless.
    assert "previous_id" in {column["name"] for column in inspect(engine).get_columns("tonight_polls")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT token, owner_id, question, previous_id FROM tonight_polls")).fetchall() == [
            ("abc", 7, "Old poll?", None)]


def test_new_poll_counters_are_registered():
    from app import funnel
    for event in ("tonight_poll_draft_started", "tonight_poll_draft_signup", "tonight_poll_draft_sent", "tonight_poll_shared",
                  "tonight_poll_winner_saved", "tonight_poll_where_clicked"):
        assert event in funnel.CLIENT_EVENTS and event in funnel.SERVER_EVENTS
    for event in ("tonight_poll_next_round", "tonight_poll_winner_kept"):
        assert event in funnel.SERVER_EVENTS and event not in funnel.CLIENT_EVENTS
