"""Watch together: plans, joining, places on the track, notes that wait, notices and the weekly email."""
import asyncio
import re
from datetime import date, datetime, timedelta

import pytest

from app import auth, models, together
from app.progress import ProgressWrite, save_progress


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


def show(db, user, title="Severance", episodes=10, seasons=2):
    row = models.TVShow(user_id=user.id, title=title, year=2022, seasons=seasons, episodes=episodes, watched=False,
                        poster_url="https://image.tmdb.org/t/p/w342/severance.jpg")
    db.add(row)
    db.commit()
    return row


def checkpoint(db, user, row, episode, season=None, category="tv-shows"):
    entry = db.query(models.ProgressCheckpoint).filter_by(user_id=user.id, category=category, item_id=row.id).first()
    unit = "episode" if category in ("tv-shows", "anime", "podcasts") else "chapter"
    payload = {"unit": unit, "position": episode, "expected_revision": entry.revision if entry else 0}
    if season is not None:
        payload["season"] = season
    save_progress(db, user.id, category, row.id, ProgressWrite(**payload))


@pytest.fixture
def pair(client, db_session):
    owner = make_user(db_session, "dana")
    friend = make_user(db_session, "sam")
    row = show(db_session, owner)
    sign_in(client, owner)
    today = date.today()
    response = client.post("/api/together", json={
        "category": "tv-shows", "item_id": row.id, "season": 2, "total": 10, "pace": 2,
        "starts_on": today.isoformat(), "remind_email": True,
    })
    assert response.status_code == 201, response.text
    plan = db_session.get(models.TogetherPlan, response.json()["id"])
    return owner, friend, row, plan


def join(client, plan, user, **body):
    sign_in(client, user)
    response = client.post(f"/api/together/join/{plan.token}", json=body)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------- the schedule

def test_weeks_split_the_title_and_the_last_week_takes_what_is_left():
    plan = models.TogetherPlan(total=11, pace=3, starts_on=date(2026, 11, 23), unit="episode", category="tv-shows")
    assert together.weeks_total(plan) == 4
    assert [together.week_span(plan, index) for index in range(4)] == [(1, 3), (4, 6), (7, 9), (10, 11)]
    assert together.target(plan, date(2026, 11, 22)) == 0
    assert together.target(plan, date(2026, 11, 23)) == 3
    assert together.target(plan, date(2026, 12, 7)) == 9
    assert together.target(plan, date(2027, 1, 30)) == 11
    assert together.ends_on(plan) == date(2026, 12, 20)
    assert together.span_label(plan, 4, 6) == "Episodes 4–6"
    assert together.span_label(plan, 10, 10) == "Episode 10"


def test_status_reads_a_place_against_this_weeks_stretch():
    plan = models.TogetherPlan(total=10, pace=2, starts_on=date(2026, 11, 16), unit="episode", category="tv-shows")
    today = date(2026, 11, 24)  # week 2: episodes 3-4
    assert together.status_of(plan, 1, today) == "behind"
    assert together.status_of(plan, 2, today) == "on"
    assert together.status_of(plan, 3, today) == "on"
    assert together.status_of(plan, 4, today) == "done"
    assert together.status_of(plan, 6, today) == "ahead"
    assert together.status_of(plan, 10, today) == "finished"
    assert together.status_of(plan, 0, date(2026, 11, 10)) == "waiting"


def test_checkpoints_are_placed_by_season():
    plan = models.TogetherPlan(total=10, pace=2, unit="episode", season=2, category="tv-shows")
    point = lambda season, position, unit="episode": models.ProgressCheckpoint(unit=unit, season=season, position=position)  # noqa: E731
    assert together.placed(plan, point(2, 4)) == 4
    assert together.placed(plan, point(3, 1)) == 10
    assert together.placed(plan, point(1, 9)) == 0
    assert together.placed(plan, point(None, 7)) == 7
    assert together.placed(plan, point(2, 40)) == 10
    assert together.placed(plan, point(None, 3, "chapter")) is None
    whole = models.TogetherPlan(total=24, pace=4, unit="episode", season=None, category="anime")
    assert together.placed(whole, point(None, 5)) == 5
    assert together.placed(whole, point(2, 5)) is None


# ---------------------------------------------------------------- making and joining

def test_a_plan_starts_from_a_library_title(client, db_session, pair):
    owner, _friend, row, plan = pair
    assert plan.title == "Severance" and plan.season == 2 and plan.unit == "episode" and plan.kind == "tv"
    assert plan.image.startswith("https://")
    data = client.get(f"/api/together/{plan.id}").json()
    assert data["week"] == 1 and data["weeks_total"] == 5
    assert data["this_week"]["label"] == "Episodes 1–2"
    assert data["you"]["owner"] and data["you"]["linked"]
    assert data["invite_url"].endswith(f"/together/join/{plan.token}")
    assert [person["username"] for person in data["people"]] == ["dana"]


def test_a_plan_can_start_from_a_searched_title(client, db_session):
    owner = make_user(db_session, "dana")
    sign_in(client, owner)
    response = client.post("/api/together", json={
        "kind": "book", "title": "Piranesi", "year": 2020, "total": 18, "pace": 3,
        "starts_on": date.today().isoformat(),
    })
    assert response.status_code == 201, response.text
    book = db_session.query(models.Book).filter_by(user_id=owner.id, title="Piranesi").one()
    plan = db_session.get(models.TogetherPlan, response.json()["id"])
    assert plan.unit == "chapter" and plan.category == "books"
    member = together.member_of(db_session, plan.id, owner.id)
    assert member.item_id == book.id


@pytest.mark.parametrize("body, message", [
    ({"kind": "movie", "title": "Dune", "total": 1, "pace": 1}, "TV shows, anime"),
    ({"kind": "tv", "title": "Severance", "total": 10, "pace": 11}, "no more than"),
    ({"kind": "book", "title": "Piranesi", "total": 10, "pace": 2, "season": 2}, "seasons"),
])
def test_bad_plans_are_refused(client, db_session, body, message):
    owner = make_user(db_session, "dana")
    sign_in(client, owner)
    response = client.post("/api/together", json={**body, "starts_on": date.today().isoformat()})
    assert response.status_code == 422
    assert message in response.text


def test_the_start_date_must_be_soon(client, db_session):
    owner = make_user(db_session, "dana")
    row = show(db_session, owner)
    sign_in(client, owner)
    far = (date.today() + timedelta(days=together.START_WITHIN_DAYS + 3)).isoformat()
    response = client.post("/api/together", json={"category": "tv-shows", "item_id": row.id, "total": 10, "pace": 2,
                                                  "starts_on": far})
    assert response.status_code == 422


def test_someone_else_cannot_start_a_plan_from_my_library(client, db_session):
    owner = make_user(db_session, "dana")
    other = make_user(db_session, "sam")
    row = show(db_session, owner)
    sign_in(client, other)
    response = client.post("/api/together", json={"category": "tv-shows", "item_id": row.id, "total": 10, "pace": 2,
                                                  "starts_on": date.today().isoformat()})
    assert response.status_code == 404


def test_joining_adds_the_title_and_tells_the_others(client, db_session, pair):
    owner, friend, _row, plan = pair
    result = join(client, plan, friend)
    assert result["joined"] and result["path"] == f"/together/{plan.id}"
    copy = db_session.query(models.TVShow).filter_by(user_id=friend.id, title="Severance").one()
    member = together.member_of(db_session, plan.id, friend.id)
    assert member.item_id == copy.id and member.position == 0
    note = db_session.query(models.Notification).filter_by(user_id=owner.id, type="together_joined").one()
    assert "sam joined Severance" in note.message and note.link == f"/together/{plan.id}"
    again = join(client, plan, friend)
    assert again["joined"] is False


def test_joining_starts_from_the_library_place_but_old_checkpoints_never_move_it(client, db_session, pair):
    owner, friend, _row, plan = pair
    mine = show(db_session, friend)
    checkpoint(db_session, friend, mine, 3, season=2)
    sign_in(client, friend)
    preview = client.get(f"/api/together/join/{plan.token}").json()
    assert preview["in_library"] and preview["library_at"] == 3
    join(client, plan, friend, position=1)
    data = client.get(f"/api/together/{plan.id}").json()
    assert data["you"]["position"] == 1  # the older checkpoint at 3 doesn't count


def test_checkpoints_saved_after_joining_move_the_place(client, db_session, pair):
    owner, friend, _row, plan = pair
    join(client, plan, friend)
    copy = db_session.query(models.TVShow).filter_by(user_id=friend.id).one()
    member = together.member_of(db_session, plan.id, friend.id)
    member.moved_at = datetime.utcnow() - timedelta(minutes=5)
    db_session.commit()
    checkpoint(db_session, friend, copy, 2, season=2)
    sign_in(client, owner)
    data = client.get(f"/api/together/{plan.id}").json()
    sam = next(person for person in data["people"] if person["username"] == "sam")
    assert sam["position"] == 2
    # Done with week one before dana: dana hears about it.
    assert db_session.query(models.Notification).filter_by(user_id=owner.id, type="together_ahead").count() == 1


def test_following_the_library_can_be_switched_off(client, db_session, pair):
    owner, friend, _row, plan = pair
    join(client, plan, friend)
    sign_in(client, friend)
    client.patch(f"/api/together/{plan.id}/me", json={"follow_library": False})
    copy = db_session.query(models.TVShow).filter_by(user_id=friend.id).one()
    checkpoint(db_session, friend, copy, 5, season=2)
    data = client.get(f"/api/together/{plan.id}").json()
    assert data["you"]["position"] == 0 and data["you"]["follow_library"] is False


def test_a_full_plan_turns_people_away(client, db_session, pair):
    owner, friend, _row, plan = pair
    for index in range(together.MEMBERS_MAX - 1):
        join(client, plan, make_user(db_session, f"guest{index}"))
    late = make_user(db_session, "late")
    sign_in(client, late)
    response = client.post(f"/api/together/join/{plan.token}", json={})
    assert response.status_code == 409 and "full" in response.text


def test_a_member_can_be_in_only_so_many_plans(client, db_session, monkeypatch):
    monkeypatch.setattr(together, "ACTIVE_MAX", 2)
    owner = make_user(db_session, "dana")
    sign_in(client, owner)
    for index in range(2):
        row = show(db_session, owner, title=f"Show {index}")
        assert client.post("/api/together", json={"category": "tv-shows", "item_id": row.id, "total": 4, "pace": 1,
                                                  "starts_on": date.today().isoformat()}).status_code == 201
    row = show(db_session, owner, title="One more")
    response = client.post("/api/together", json={"category": "tv-shows", "item_id": row.id, "total": 4, "pace": 1,
                                                  "starts_on": date.today().isoformat()})
    assert response.status_code == 409


# ---------------------------------------------------------------- moving and notes

def test_moving_forward_moves_the_library_forward_but_never_back(client, db_session, pair):
    owner, _friend, row, plan = pair
    response = client.put(f"/api/together/{plan.id}/position", json={"position": 3})
    assert response.status_code == 200, response.text
    assert response.json()["library_saved"] is True
    entry = db_session.query(models.ProgressCheckpoint).filter_by(user_id=owner.id, item_id=row.id).one()
    assert (entry.season, entry.position) == (2, 3)
    client.put(f"/api/together/{plan.id}/position", json={"position": 1})
    db_session.refresh(entry)
    assert entry.position == 3
    data = client.get(f"/api/together/{plan.id}").json()
    assert data["you"]["position"] == 1  # the library didn't pull the place back up


def test_a_library_already_further_on_is_left_alone(client, db_session, pair):
    owner, _friend, row, plan = pair
    checkpoint(db_session, owner, row, 2, season=3)
    member = together.member_of(db_session, plan.id, owner.id)
    member.follow_library = False
    db_session.commit()
    client.patch(f"/api/together/{plan.id}/me", json={"follow_library": True})
    response = client.put(f"/api/together/{plan.id}/position", json={"position": 4})
    assert response.json()["library_saved"] is False
    entry = db_session.query(models.ProgressCheckpoint).filter_by(user_id=owner.id, item_id=row.id).one()
    assert (entry.season, entry.position) == (3, 2)


def test_notes_stay_folded_until_you_get_there(client, db_session, pair):
    owner, friend, _row, plan = pair
    join(client, plan, friend)
    sign_in(client, owner)
    client.put(f"/api/together/{plan.id}/position", json={"position": 4, "library": False})
    assert client.post(f"/api/together/{plan.id}/notes", json={"part": 4, "body": "That ending!"}).status_code == 201
    assert client.post(f"/api/together/{plan.id}/notes", json={"part": 0, "body": "So ready for this"}).status_code == 201
    ahead = client.post(f"/api/together/{plan.id}/notes", json={"part": 6, "body": "Can't post ahead"})
    assert ahead.status_code == 422
    sign_in(client, friend)
    data = client.get(f"/api/together/{plan.id}").json()
    assert [note["body"] for note in data["notes"]] == ["So ready for this"]
    assert data["locked"] == [{"part": 4, "part_label": "Episode 4", "count": 1, "authors": ["dana"]}]
    assert "That ending!" not in str(data)
    moved = client.put(f"/api/together/{plan.id}/position", json={"position": 4, "library": False}).json()
    assert moved["opened"] == 1
    assert [note["body"] for note in moved["notes"]] == ["So ready for this", "That ending!"]
    assert moved["locked"] == []


def test_a_note_notice_only_goes_to_people_who_can_read_it(client, db_session, pair):
    owner, friend, _row, plan = pair
    join(client, plan, friend)
    sign_in(client, friend)
    client.put(f"/api/together/{plan.id}/position", json={"position": 2, "library": False})
    client.post(f"/api/together/{plan.id}/notes", json={"part": 2, "body": "Wait for it"})
    assert db_session.query(models.Notification).filter_by(user_id=owner.id, type="together_note").count() == 0
    client.post(f"/api/together/{plan.id}/notes", json={"part": 0, "body": "Hi"})
    client.post(f"/api/together/{plan.id}/notes", json={"part": 0, "body": "Hi again"})
    notes = db_session.query(models.Notification).filter_by(user_id=owner.id, type="together_note").all()
    assert len(notes) == 1  # one unread notice per plan, not one per note


def test_notes_can_be_deleted_by_their_author_or_the_owner_only(client, db_session, pair):
    owner, friend, _row, plan = pair
    join(client, plan, friend)
    third = make_user(db_session, "priya")
    join(client, plan, third)
    sign_in(client, friend)
    data = client.post(f"/api/together/{plan.id}/notes", json={"part": 0, "body": "Mine"}).json()
    note_id = data["notes"][0]["id"]
    sign_in(client, third)
    assert client.delete(f"/api/together/{plan.id}/notes/{note_id}").status_code == 403
    sign_in(client, owner)
    assert client.delete(f"/api/together/{plan.id}/notes/{note_id}").status_code == 200
    assert db_session.query(models.TogetherNote).count() == 0


def test_note_text_is_cleaned_and_limited(client, db_session, pair):
    owner, _friend, _row, plan = pair
    body = "  Line one  \r\n\n\n\n  line   two "
    data = client.post(f"/api/together/{plan.id}/notes", json={"part": 0, "body": body}).json()
    assert data["notes"][0]["body"] == "Line one\n\nline two"
    assert client.post(f"/api/together/{plan.id}/notes", json={"part": 0, "body": "   "}).status_code == 422
    assert client.post(f"/api/together/{plan.id}/notes", json={"part": 0, "body": "x" * 501}).status_code == 422


def test_reaching_the_end_tells_the_others_and_everyone_finishing_ends_the_plan(client, db_session, pair):
    owner, friend, _row, plan = pair
    join(client, plan, friend)
    sign_in(client, friend)
    client.put(f"/api/together/{plan.id}/position", json={"position": 10, "library": False})
    assert db_session.query(models.Notification).filter_by(user_id=owner.id, type="together_done").count() == 1
    db_session.refresh(plan)
    assert plan.ended_at is None
    sign_in(client, owner)
    client.put(f"/api/together/{plan.id}/position", json={"position": 10, "library": False})
    db_session.refresh(plan)
    assert plan.ended_at is not None
    assert client.put(f"/api/together/{plan.id}/position", json={"position": 3}).status_code == 409
    mine = client.get("/api/together").json()
    assert mine["running"] == [] and mine["ended"][0]["title"] == "Severance"


def test_finishing_ticks_the_title_off_in_the_library(client, db_session, pair):
    owner, _friend, row, plan = pair
    assert client.post(f"/api/together/{plan.id}/finish", json={"rating": 9}).status_code == 409
    client.put(f"/api/together/{plan.id}/position", json={"position": 10, "library": False})
    data = client.post(f"/api/together/{plan.id}/finish", json={"rating": 9}).json()
    db_session.refresh(row)
    assert row.watched is True and row.rating == 9.0
    assert data["you"]["library_done"] is True


# ---------------------------------------------------------------- privacy and people

def test_people_outside_the_plan_see_nothing(client, db_session, pair):
    owner, friend, _row, plan = pair
    sign_in(client, friend)
    assert client.get(f"/api/together/{plan.id}").status_code == 404
    assert client.put(f"/api/together/{plan.id}/position", json={"position": 1}).status_code == 404
    assert client.post(f"/api/together/{plan.id}/notes", json={"part": 0, "body": "hi"}).status_code == 404
    page = client.get(f"/together/{plan.id}")
    assert page.status_code == 404 and "This plan isn" in page.text


def test_the_invite_page_shows_the_plan_but_no_places_or_notes(client, db_session, pair):
    owner, _friend, _row, plan = pair
    client.put(f"/api/together/{plan.id}/position", json={"position": 2, "library": False})
    client.post(f"/api/together/{plan.id}/notes", json={"part": 1, "body": "SECRET NOTE TEXT"})
    sign_out(client)
    page = client.get(f"/together/join/{plan.token}")
    assert page.status_code == 200
    assert "Watch Severance together" in page.text and "2 episodes a week" in page.text
    assert "SECRET NOTE TEXT" not in page.text
    assert page.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert 'data-together-signup' in page.text and "%2Ftogether%2Fjoin%2F" in page.text
    assert f"/together/join/{plan.token}/card.png" in page.text
    assert client.get("/together/join/not-a-real-token-at-all").status_code == 404


def test_the_invite_picture_is_a_png(client, db_session, pair):
    _owner, _friend, _row, plan = pair
    sign_out(client)
    response = client.get(f"/together/join/{plan.token}/card.png")
    assert response.status_code == 200 and response.headers["content-type"] == "image/png"
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"
    again = client.get(f"/together/join/{plan.token}/card.png", headers={"If-None-Match": response.headers["ETag"]})
    assert again.status_code == 304


def test_a_new_link_retires_the_old_one(client, db_session, pair):
    owner, friend, _row, plan = pair
    old = plan.token
    data = client.post(f"/api/together/{plan.id}/link").json()
    assert old not in data["invite_url"]
    sign_in(client, friend)
    assert client.post(f"/api/together/join/{old}", json={}).status_code == 404


def test_only_the_owner_runs_the_plan(client, db_session, pair):
    owner, friend, _row, plan = pair
    join(client, plan, friend)
    sign_in(client, friend)
    assert client.patch(f"/api/together/{plan.id}", json={"pace": 3}).status_code == 403
    assert client.post(f"/api/together/{plan.id}/end").status_code == 403
    assert client.post(f"/api/together/{plan.id}/link").status_code == 403
    me = together.member_of(db_session, plan.id, owner.id)
    assert client.delete(f"/api/together/{plan.id}/members/{me.id}").status_code == 403
    sign_in(client, owner)
    assert client.patch(f"/api/together/{plan.id}", json={"pace": 3}).json()["pace_label"] == "3 episodes a week"
    them = together.member_of(db_session, plan.id, friend.id)
    assert client.delete(f"/api/together/{plan.id}/members/{them.id}").status_code == 200
    assert together.member_of(db_session, plan.id, friend.id) is None


def test_the_owner_leaving_hands_the_plan_over_and_the_last_one_out_deletes_it(client, db_session, pair):
    owner, friend, _row, plan = pair
    join(client, plan, friend)
    sign_in(client, owner)
    client.post(f"/api/together/{plan.id}/notes", json={"part": 0, "body": "bye"})
    assert client.post(f"/api/together/{plan.id}/leave").json() == {"left": True, "plan_kept": True}
    db_session.refresh(plan)
    assert plan.owner_id == friend.id
    assert db_session.query(models.TogetherNote).count() == 0
    sign_in(client, friend)
    assert client.post(f"/api/together/{plan.id}/leave").json()["plan_kept"] is False
    assert db_session.query(models.TogetherPlan).count() == 0


def test_friends_can_be_asked_in(client, db_session, pair):
    from app.crud.friends import create_friendship
    owner, friend, _row, plan = pair
    stranger = make_user(db_session, "stranger")
    create_friendship(db_session, owner.id, friend.id)
    data = client.get(f"/api/together/{plan.id}/friends").json()
    assert [entry["username"] for entry in data["friends"]] == ["sam"]
    assert client.post(f"/api/together/{plan.id}/invite", json={"friend_ids": [friend.id, stranger.id]}).json() == {"asked": 1}
    note = db_session.query(models.Notification).filter_by(user_id=friend.id, type="together_invite").one()
    assert note.link == f"/together/join/{plan.token}" and "2 episodes a week" in note.message
    join(client, plan, friend)
    db_session.refresh(note)
    assert note.read_at is not None


def test_opening_the_plan_marks_its_notices_read(client, db_session, pair):
    owner, friend, _row, plan = pair
    join(client, plan, friend)
    note = db_session.query(models.Notification).filter_by(user_id=owner.id, type="together_joined").one()
    sign_in(client, owner)
    client.get(f"/api/together/{plan.id}")
    db_session.refresh(note)
    assert note.read_at is not None


def test_the_home_list_has_a_line_and_a_next_button(client, db_session, pair):
    owner, friend, _row, plan = pair
    join(client, plan, friend)
    sign_in(client, friend)
    client.put(f"/api/together/{plan.id}/position", json={"position": 2, "library": False})
    client.post(f"/api/together/{plan.id}/notes", json={"part": 2, "body": "Wow"})
    sign_in(client, owner)
    data = client.get("/api/together").json()
    card = data["running"][0]
    assert card["with"] == "with sam" and card["next_label"] == "Watched episode 1"
    assert card["waiting"] == 1 and card["this_week"] == "Episodes 1–2"
    assert card["headline"] == "sam is done with this week. You haven't started yet."


def test_the_home_card_moves_you_on_without_marking_notes_read(client, db_session, pair):
    owner, friend, _row, plan = pair
    join(client, plan, friend)
    sign_in(client, owner)
    client.put(f"/api/together/{plan.id}/position", json={"position": 1, "library": False})
    client.post(f"/api/together/{plan.id}/notes", json={"part": 1, "body": "Cold open!"})
    sign_in(client, friend)
    moved = client.put(f"/api/together/{plan.id}/position?card=1", json={"position": 1, "library": False})
    assert moved.status_code == 200
    data = moved.json()
    assert data["opened"] == 1 and "notes" not in data
    card = data["running"][0]
    assert card["position"] == 1 and card["unread"] == 1
    # A note written long before still counts as new once moving on opens it.
    note = db_session.query(models.TogetherNote).filter_by(plan_id=plan.id).one()
    note.created_at = datetime.utcnow() - timedelta(days=3)
    db_session.commit()
    assert client.get("/api/together").json()["running"][0]["unread"] == 1
    assert card["week_first"] == 1 and card["week_last"] == 2
    assert card["next_label"] == "Watched episode 2"
    # Opening the plan page is what marks the note as read.
    client.get(f"/api/together/{plan.id}")
    assert client.get("/api/together").json()["running"][0]["unread"] == 0


def test_the_home_screen_has_the_card_and_the_ways_in():
    index = open("app/templates/index.html", encoding="utf-8").read()
    assert 'id="togetherHome"' in index and "/static/together-home.js?v=" in index
    assert "/static/together-home.css?v=" in index
    assert 'href="/together">Watch with friends</a>' in index
    home = open("app/static/dashboard/home.js", encoding="utf-8").read()
    assert "window.OmniTogether?.refresh();" in home and "window.OmniTogether?.reset();" in home
    layout = open("app/static/home-layout.js", encoding="utf-8").read()
    assert "if (id === 'togetherHome') return true;" in layout


def test_shared_lists_point_to_watch_together(client, db_session):
    owner = make_user(db_session, "dana")
    sign_in(client, owner)
    assert 'href="/together"' in client.get("/lists").text


# ---------------------------------------------------------------- pages

def test_the_guest_page_explains_it_and_can_be_indexed(client):
    sign_out(client)
    page = client.get("/together")
    assert page.status_code == 200
    assert "index, follow" in page.text and "How to watch or read something together" in page.text
    assert "data-together-signup" in page.text


def test_members_get_the_hub(client, db_session):
    owner = make_user(db_session, "dana")
    sign_in(client, owner)
    page = client.get("/together")
    assert 'data-view="hub"' in page.text and "/static/together.js?v=" in page.text


def test_the_plan_page_asks_guests_to_log_in(client, db_session, pair):
    _owner, _friend, _row, plan = pair
    sign_out(client)
    page = client.get(f"/together/{plan.id}")
    assert "Log in to see this plan" in page.text
    assert "%2Ftogether%2F" in page.text


def test_member_plan_page(client, db_session, pair):
    _owner, _friend, _row, plan = pair
    page = client.get(f"/together/{plan.id}")
    assert page.status_code == 200 and f'data-plan-id="{plan.id}"' in page.text
    assert page.headers["X-Robots-Tag"] == "noindex, nofollow"


def test_titles_to_start_from(client, db_session):
    owner = make_user(db_session, "dana")
    sign_in(client, owner)
    row = show(db_session, owner)
    db_session.add(models.Movie(user_id=owner.id, title="Dune", year=2021, watched=False))
    db_session.add(models.Manga(user_id=owner.id, title="Vagabond", chapters=327, read=False))
    db_session.commit()
    checkpoint(db_session, owner, row, 3, season=1)
    data = client.get("/api/together/titles").json()
    titles = [entry["title"] for entry in data["titles"]]
    assert titles[0] == "Severance" and "Vagabond" in titles and "Dune" not in titles
    assert data["titles"][0]["at"] == {"position": 3, "season": 1, "unit": "episode"}
    assert next(entry for entry in data["titles"] if entry["title"] == "Vagabond")["total"] == 327


# ---------------------------------------------------------------- the weekly loop

def run(db_session, now, sender=None):
    sent = []

    async def fake(to, subject, html, unsubscribe):
        sent.append((to, subject, html))

    result = asyncio.run(together.run_once(lambda: db_session, now=now, sender=sender or fake))
    return result, sent


@pytest.fixture
def stale_session(db_session, monkeypatch):
    """run_once closes its session; the test keeps using the same one."""
    monkeypatch.setattr(db_session, "close", lambda: None)
    return db_session


def _plan_started(db, days_ago=2, total=10, pace=2):
    owner = make_user(db, "dana")
    friend = make_user(db, "sam", last_seen_on=date.today() - timedelta(days=10))
    row = show(db, owner)
    plan = together.create(db, owner, row, "tv-shows", total=total, pace=pace,
                           starts_on=date.today() - timedelta(days=days_ago),
                           today=date.today() - timedelta(days=days_ago), season=1)
    db.commit()
    copy = show(db, friend)
    db.add(models.TogetherMember(plan_id=plan.id, user_id=friend.id, item_id=copy.id, position=0,
                                 moved_at=datetime.utcnow(), remind_email=True))
    db.commit()
    return owner, friend, plan


def test_each_new_week_is_announced_once(stale_session):
    db = stale_session
    owner, friend, plan = _plan_started(db, days_ago=0)
    result, _ = run(db, datetime.utcnow())
    assert result["weeks"] == 2
    week = db.query(models.Notification).filter_by(user_id=friend.id, type="together_week").one()
    assert week.message == "Severance with dana starts today: episodes 1–2 this week."
    result, _ = run(db, datetime.utcnow())
    assert result["weeks"] == 0


def test_the_reminder_goes_to_someone_away_and_behind_once_a_week(stale_session):
    db = stale_session
    owner, friend, plan = _plan_started(db, days_ago=3)
    member = together.member_of(db, plan.id, owner.id)
    member.position = 2
    db.add(models.TogetherNote(plan_id=plan.id, user_id=owner.id, part=2, body="hidden"))
    db.commit()
    result, sent = run(db, datetime.utcnow())
    assert result["sent"] == 1
    to, subject, html = sent[0]
    assert to == "sam@example.test"
    assert subject == "dana left you a note at episode 2 of Severance"
    assert "hidden" not in html and "utm_campaign=together" in html
    result, sent = run(db, datetime.utcnow())
    assert sent == []


def test_no_reminder_for_people_who_were_just_here_or_said_no(stale_session):
    db = stale_session
    owner, friend, plan = _plan_started(db, days_ago=3)
    together.member_of(db, plan.id, owner.id).position = 2
    friend.last_seen_on = date.today()
    db.commit()
    assert run(db, datetime.utcnow())[1] == []
    friend.last_seen_on = date.today() - timedelta(days=10)
    together.member_of(db, plan.id, friend.id).remind_email = False
    db.commit()
    assert run(db, datetime.utcnow())[1] == []
    together.member_of(db, plan.id, friend.id).remind_email = True
    db.add(models.EmailOptOut(user_id=friend.id))
    db.commit()
    assert run(db, datetime.utcnow())[1] == []


def test_no_reminder_early_in_the_week_or_when_nobody_is_ahead(stale_session):
    db = stale_session
    owner, friend, plan = _plan_started(db, days_ago=1)
    together.member_of(db, plan.id, owner.id).position = 2
    db.commit()
    assert run(db, datetime.utcnow())[1] == []
    plan.starts_on = date.today() - timedelta(days=3)
    together.member_of(db, plan.id, owner.id).position = 0
    db.commit()
    assert run(db, datetime.utcnow())[1] == []


def test_a_long_quiet_plan_ends_on_its_own(stale_session):
    db = stale_session
    _owner, _friend, plan = _plan_started(db, days_ago=7 * (5 + together.QUIET_END_WEEKS))
    result, _ = run(db, datetime.utcnow())
    assert result["ended"] == 1
    db.refresh(plan)
    assert plan.ended_at is not None


# ---------------------------------------------------------------- wiring

def test_every_together_api_route_is_rate_limited():
    from app import main
    from app.routers import together as together_router
    for route in together_router.router.routes:
        path = getattr(route, "path", "")
        for method in route.methods:
            if path in ("/together", "/together/{plan_id}"):
                continue
            assert (path, method) in main.TOGETHER_LIMITS, (path, method)
            assert hasattr(route.endpoint, "__wrapped__"), (path, method)


def test_together_notices_have_a_push_switch():
    from app import web_push
    for kind in together.NOTE_TYPES:
        assert web_push.TOPIC_FOR_TYPE[kind] == "together"
        assert kind in web_push.TITLES


def test_counters_are_known_events():
    from app import funnel
    for name in ("together_created", "together_joined", "together_note", "together_link_opened",
                 "together_email_sent", "together_back_from_email", "together_moved"):
        assert name in funnel.SERVER_EVENTS
    assert {"together_shared", "together_signup_clicked"} <= funnel.CLIENT_EVENTS
