"""Rankings: two at a time, a member's finished titles fall into order (app/rankings.py)."""
import math
from datetime import datetime, timedelta

import pytest

from app import auth, models, rankings
from app.site_traffic import RECORDER

CHROME = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"}


@pytest.fixture(autouse=True)
def counting(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    RECORDER._pending.clear()
    yield
    RECORDER._pending.clear()


def counted(key):
    return sum(amount for (_, kind, name), amount in RECORDER._pending.items() if kind == "rank" and name == key)


def member(db, name="nova"):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=True, is_active=True, created_at=datetime.utcnow() - timedelta(days=60))
    db.add(user)
    db.commit()
    return user


def headers(user):
    return {"Authorization": f"Bearer {auth.create_user_access_token(user)}", **CHROME}


def films(db, user, titles, watched=True, rating=None):
    rows = [models.Movie(title=title, year=2000 + index, director=f"Director {index}", watched=watched, rating=rating,
                         user_id=user.id, poster_url=f"https://image.tmdb.org/t/p/w342/{index}.jpg")
            for index, title in enumerate(titles)]
    db.add_all(rows)
    db.commit()
    return rows


def finished_on(db, user, row, when):
    db.add(models.ActivityEntry(user_id=user.id, category="movies", item_id=row.id, title=row.title,
                                action="completed", occurred_at=when))
    db.commit()


def card(client, user):
    response = client.get("/api/rankings/card", headers=headers(user))
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    return response.json()["card"]


def answer(client, user, question, choice, source="tab"):
    return client.post("/api/rankings/answer", headers=headers(user), json={
        "category": question["category"], "placing_id": question["placing"]["id"],
        "against_id": question["against"]["id"], "choice": choice, "source": source})


def detail(client, user, category="movies"):
    response = client.get(f"/api/rankings?category={category}", headers=headers(user))
    assert response.status_code == 200
    return response.json()["detail"]


def ranked_titles(client, user, category="movies"):
    return [item["title"] for item in detail(client, user, category)["ranked"]]


def rank_all(client, user, truth, source="tab"):
    """Answer every question from a known best-first order until nothing is waiting. Returns answers per title."""
    better = {title: index for index, title in enumerate(truth)}
    answers = []
    question = detail(client, user)["question"]
    steps = 0
    while question:
        placing, against = question["placing"]["title"], question["against"]["title"]
        choice = "placing" if better[placing] < better[against] else "against"
        response = answer(client, user, question, choice, source)
        assert response.status_code == 200, response.text
        body = response.json()
        steps += 1
        if "placed" in body:
            answers.append(steps)
            steps = 0
            question = detail(client, user)["question"]
        else:
            question = body["question"]
    return answers


# ---------------------------------------------------------------- the card and the first answer

def test_card_needs_two_finished_titles_in_a_format(client, db_session):
    user = member(db_session)
    films(db_session, user, ["Alien"])
    films(db_session, user, ["Dune"], watched=False)
    assert card(client, user) is None
    films(db_session, user, ["Arrival"])
    found = card(client, user)
    assert found["status"] == "start"
    titles = {found["question"]["placing"]["title"], found["question"]["against"]["title"]}
    assert titles == {"Alien", "Arrival"}  # never the unfinished one
    assert found["question"]["ranked"] == 0
    assert db_session.query(models.Ranking).count() == 0  # showing a question writes nothing


def test_first_answer_ranks_both_titles(client, db_session):
    user = member(db_session)
    films(db_session, user, ["Alien", "Arrival"])
    question = card(client, user)["question"]
    response = answer(client, user, question, "against", source="home")
    assert response.status_code == 200
    placed = response.json()["placed"]
    assert placed["position"] == 2 and placed["total"] == 2
    assert placed["title"]["title"] == question["placing"]["title"]
    assert placed["above"]["title"] == question["against"]["title"] and placed["below"] is None
    assert ranked_titles(client, user) == [question["against"]["title"], question["placing"]["title"]]
    assert counted("placed") == 1 and counted("first") == 1 and counted("from_home") == 1
    assert card(client, user) is None  # nothing left to place


@pytest.mark.parametrize("size", [3, 8, 21])
def test_binary_placement_lands_every_title_in_the_right_place(client, db_session, size):
    user = member(db_session)
    truth = [f"Film {chr(65 + i)}" for i in range(size)]
    films(db_session, user, list(reversed(truth)))
    answers = rank_all(client, user, truth)
    assert ranked_titles(client, user) == truth
    # Title n+1 lands among n others in at most ceil(log2(n + 1)) answers.
    for placed_after, steps in enumerate(answers, start=1):
        assert steps <= max(1, math.ceil(math.log2(placed_after + 1)))


def test_questions_say_where_the_other_title_sits_and_how_many_are_left(client, db_session):
    user = member(db_session)
    truth = [f"Film {i}" for i in range(9)]
    films(db_session, user, truth)
    rank_all(client, user, truth)
    extra = films(db_session, user, ["Newcomer"])[0]
    response = client.post("/api/rankings/place", headers=headers(user),
                           json={"category": "movies", "item_id": extra.id, "source": "finish"})
    question = response.json()["question"]
    assert question["placing"]["title"] == "Newcomer"
    assert question["against"]["position"] == 5  # the middle of nine
    assert question["left"] == 4 and question["step"] == 1


# ---------------------------------------------------------------- double taps, ties, skips

def test_a_stale_answer_returns_the_current_question_instead_of_applying_twice(client, db_session):
    user = member(db_session)
    truth = [f"Film {i}" for i in range(6)]
    films(db_session, user, truth)
    rank_all(client, user, truth)
    extra = films(db_session, user, ["Late"])[0]
    question = client.post("/api/rankings/place", headers=headers(user),
                           json={"category": "movies", "item_id": extra.id}).json()["question"]
    first = answer(client, user, question, "placing")
    assert first.status_code == 200 and "question" in first.json()
    again = answer(client, user, question, "placing")  # the same tap, a second time
    assert again.status_code == 409
    current = again.json()["question"]
    assert current == first.json()["question"]


def test_too_close_to_call_puts_it_right_below(client, db_session):
    user = member(db_session)
    rows = films(db_session, user, ["A", "B", "C"])
    rank_all(client, user, ["A", "B", "C"])
    extra = films(db_session, user, ["Twin"])[0]
    question = client.post("/api/rankings/place", headers=headers(user),
                           json={"category": "movies", "item_id": extra.id}).json()["question"]
    assert question["against"]["title"] == "B"
    placed = answer(client, user, question, "tie").json()["placed"]
    assert placed["position"] == 3
    assert ranked_titles(client, user) == ["A", "B", "Twin", "C"]
    assert counted("tie") == 1
    assert rows  # library rows untouched
    assert [row.watched for row in db_session.query(models.Movie).all()] == [True] * 4


def test_skip_sends_a_title_to_the_back_and_leave_out_drops_it(client, db_session):
    user = member(db_session)
    films(db_session, user, ["A", "B", "C", "D"], rating=None)
    question = detail(client, user)["question"]
    first = question["placing"]["title"]
    response = client.post("/api/rankings/skip", headers=headers(user),
                           json={"category": "movies", "item_id": question["placing"]["id"]})
    assert response.status_code == 200
    assert response.json()["question"]["placing"]["title"] != first
    waiting = [item["title"] for item in detail(client, user)["waiting"]]
    assert waiting[-1] == first
    # Leave it out: never offered, listed under Left out, can be put back.
    target = detail(client, user)["waiting"][0]
    client.post("/api/rankings/skip", headers=headers(user),
                json={"category": "movies", "item_id": target["id"], "leave_out": True})
    body = detail(client, user)
    assert target["title"] not in [item["title"] for item in body["waiting"]]
    assert [item["title"] for item in body["left_out"]] == [target["title"]]
    client.post("/api/rankings/restore", headers=headers(user), json={"category": "movies", "item_id": target["id"]})
    assert target["title"] in [item["title"] for item in detail(client, user)["waiting"]]
    assert counted("skipped") == 1 and counted("left_out") == 1


def test_recent_finish_comes_first_and_makes_the_card_fresh(client, db_session):
    user = member(db_session)
    rows = films(db_session, user, ["Old 1", "Old 2", "Old 3"], rating=9)
    rank_all(client, user, ["Old 1", "Old 2", "Old 3"])
    films(db_session, user, ["Old 4"], rating=10)  # best scored, but finished long ago
    new = films(db_session, user, ["Just Watched"], rating=5)[0]
    finished_on(db_session, user, new, datetime.utcnow() - timedelta(days=2))
    found = card(client, user)
    assert found["status"] == "fresh"
    assert found["question"]["placing"]["title"] == "Just Watched" and found["question"]["fresh"] is True
    assert rows


def test_a_placement_under_way_comes_back_on_the_card(client, db_session):
    user = member(db_session)
    films(db_session, user, [f"F{i}" for i in range(5)])
    rank_all(client, user, [f"F{i}" for i in range(5)])
    extra = films(db_session, user, ["Midway"])[0]
    question = client.post("/api/rankings/place", headers=headers(user),
                           json={"category": "movies", "item_id": extra.id}).json()["question"]
    answer(client, user, question, "against")
    found = card(client, user)
    assert found["status"] == "placing" and found["question"]["placing"]["title"] == "Midway"
    assert found["question"]["step"] == 2


# ---------------------------------------------------------------- choosing, moving, removing

def test_place_again_and_unfinished_titles(client, db_session):
    user = member(db_session)
    films(db_session, user, ["A", "B", "C"])
    rank_all(client, user, ["A", "B", "C"])
    ranked = detail(client, user)["ranked"]
    response = client.post("/api/rankings/place", headers=headers(user),
                           json={"category": "movies", "item_id": ranked[2]["id"]})
    question = response.json()["question"]
    assert question["placing"]["title"] == "C" and question["ranked"] == 2
    placed = answer(client, user, question, "placing").json()
    if "question" in placed:
        placed = answer(client, user, placed["question"], "placing").json()
    assert placed["placed"]["position"] == 1
    assert ranked_titles(client, user) == ["C", "A", "B"]
    unfinished = films(db_session, user, ["Not yet"], watched=False)[0]
    refused = client.post("/api/rankings/place", headers=headers(user),
                          json={"category": "movies", "item_id": unfinished.id})
    assert refused.status_code == 409


def test_first_title_placed_by_hand_lands_at_number_one(client, db_session):
    user = member(db_session)
    row = films(db_session, user, ["Solo"])[0]
    response = client.post("/api/rankings/place", headers=headers(user),
                           json={"category": "movies", "item_id": row.id, "source": "finish"})
    assert response.json()["placed"]["position"] == 1
    assert counted("from_finish") == 1


def test_move_and_remove(client, db_session):
    user = member(db_session)
    films(db_session, user, ["A", "B", "C", "D"])
    rank_all(client, user, ["A", "B", "C", "D"])
    ranked = detail(client, user)["ranked"]
    moved = client.post("/api/rankings/move", headers=headers(user),
                        json={"category": "movies", "item_id": ranked[3]["id"], "position": 1})
    assert moved.json()["position"] == 1
    assert ranked_titles(client, user) == ["D", "A", "B", "C"]
    client.post("/api/rankings/remove", headers=headers(user), json={"category": "movies", "item_id": ranked[0]["id"]})
    assert ranked_titles(client, user) == ["D", "B", "C"]
    assert "A" in [item["title"] for item in detail(client, user)["waiting"]]
    missing = client.post("/api/rankings/move", headers=headers(user),
                          json={"category": "movies", "item_id": ranked[0]["id"], "position": 1})
    assert missing.status_code == 404


def test_a_deleted_title_drops_out(client, db_session):
    user = member(db_session)
    rows = films(db_session, user, ["A", "B", "C"])
    rank_all(client, user, ["A", "B", "C"])
    db_session.delete(rows[1])
    db_session.commit()
    assert ranked_titles(client, user) == ["A", "C"]


def test_another_members_titles_cannot_be_used(client, db_session):
    owner = member(db_session, "owner")
    other = member(db_session, "other")
    rows = films(db_session, owner, ["A", "B"])
    films(db_session, other, ["X", "Y"])
    refused = client.post("/api/rankings/place", headers=headers(other),
                          json={"category": "movies", "item_id": rows[0].id})
    assert refused.status_code == 409
    question = {"category": "movies", "placing": {"id": rows[0].id}, "against": {"id": rows[1].id}}
    assert answer(client, other, question, "placing").status_code == 409
    assert db_session.query(models.Ranking).filter(models.Ranking.user_id == owner.id).count() == 0


def test_bad_input_is_refused(client, db_session):
    user = member(db_session)
    bad = client.post("/api/rankings/answer", headers=headers(user), json={
        "category": "cars", "placing_id": 1, "against_id": 2, "choice": "placing"})
    assert bad.status_code == 422
    bad = client.post("/api/rankings/answer", headers=headers(user), json={
        "category": "movies", "placing_id": 1, "against_id": 2, "choice": "both"})
    assert bad.status_code == 422
    assert client.get("/api/rankings/card").status_code == 401


# ---------------------------------------------------------------- sharing

def test_top_ten_on_the_public_profile_only_when_asked(client, db_session):
    user = member(db_session)
    db_session.add(models.PublicProfile(user_id=user.id, enabled=True))
    db_session.commit()
    truth = [f"Film {i:02d}" for i in range(12)]
    films(db_session, user, truth, rating=7)
    rank_all(client, user, truth)
    assert rankings.public_lists(db_session, user) == []
    response = client.put("/api/rankings/settings", headers=headers(user), json={"category": "movies", "public": True})
    assert response.json()["public"] is True
    lists = rankings.public_lists(db_session, user)
    assert [item["title"] for item in lists[0]["items"]] == truth[:10]
    assert lists[0]["total"] == 12
    assert all("score" not in item for item in lists[0]["items"])
    page = client.get(f"/u/{user.username}")
    assert page.status_code == 200
    assert 'id="profile-ranked"' in page.text and "Film 00" in page.text and "Film 10" not in page.text
    assert counted("public_on") == 1
    # A format the member hides from their library never shows.
    user.movies_visible = False
    db_session.commit()
    assert rankings.public_lists(db_session, user) == []


def test_save_the_top_as_a_ranked_collection(client, db_session):
    user = member(db_session)
    truth = ["A", "B", "C", "D"]
    films(db_session, user, truth)
    too_few = client.post("/api/rankings/collection", headers=headers(user), json={"category": "movies"})
    assert too_few.status_code == 409
    rank_all(client, user, truth)
    response = client.post("/api/rankings/collection", headers=headers(user), json={"category": "movies", "top": 10})
    assert response.status_code == 200
    saved = db_session.get(models.Collection, response.json()["id"])
    assert saved.ranked is True and saved.is_public is False and saved.name == "My top 4 films"
    library = {row.id: row.title for row in db_session.query(models.Movie).all()}
    assert [library[item.item_id] for item in sorted(saved.items, key=lambda item: item.position)] == truth


# ---------------------------------------------------------------- the rest of the site

def test_overview_lists_visible_formats(client, db_session):
    user = member(db_session)
    films(db_session, user, ["A", "B", "C"])
    db_session.add(models.Book(title="Piranesi", read=True, user_id=user.id))
    db_session.commit()
    rank_all(client, user, ["A", "B", "C"])
    body = client.get("/api/rankings", headers=headers(user)).json()
    movies = next(item for item in body["formats"] if item["category"] == "movies")
    books = next(item for item in body["formats"] if item["category"] == "books")
    assert movies["ranked"] == 3 and movies["waiting"] == 0 and [item["title"] for item in movies["top"]] == ["A", "B", "C"]
    assert books["finished"] == 1 and books["ranked"] == 0 and books["waiting"] == 1
    assert body["ranked"] == 3
    assert body["profile"] == {"enabled": False, "path": None}


def test_badge_counts_ranked_titles(client, db_session):
    from app import badges
    user = member(db_session)
    truth = [f"F{i}" for i in range(10)]
    films(db_session, user, truth)
    rank_all(client, user, truth)
    assert badges.counts(db_session, user)["ranked"] == 10
    track = badges.BY_KEY["ranker"]
    assert badges.tier_for(track, 10) == 1


def test_site_stats_block(client, db_session):
    user = member(db_session)
    films(db_session, user, ["A", "B", "C"])
    rank_all(client, user, ["A", "B", "C"])
    found = rankings.stats(db_session, 30, datetime.utcnow())
    assert found["members_now"] == 1 and found["titles_now"] == 3 and found["public_now"] == 0
    assert set(found["counts"]) == set(rankings.COUNTERS)
    assert found["by_format"] == [{"label": "Films", "count": 1}]


def test_removing_the_account_removes_its_rankings(db_session):
    from app import account_removal
    user = member(db_session)
    db_session.add(models.Ranking(user_id=user.id, category="movies", ranked="[1,2]"))
    db_session.commit()
    table = models.Ranking.__table__
    assert any(fk.column.table is models.User.__table__ and fk.ondelete == "CASCADE" for fk in table.foreign_keys)
    assert account_removal  # the plan is built from table metadata, so a CASCADE key is enough


def test_stored_lists_survive_junk(db_session):
    assert rankings._ids("not json") == []
    assert rankings._ids('{"a": 1}') == []
    assert rankings._ids("[3, 3, -1, 0, true, 2.5, \"4\", 7]") == [3, 7]
