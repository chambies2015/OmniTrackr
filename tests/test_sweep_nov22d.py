"""Sweep of #305-#307 (Nov 22 2026): Rankings placements stay right when titles leave the list mid-placement."""
from app import models, rankings

from tests.test_rankings import answer, counting, detail, films, headers, member, rank_all, ranked_titles  # noqa: F401


def _rank_all_but(client, db_session, user, rows, truth, waiting):
    """Rank every title except `waiting`, which are then finished again and wait to be placed."""
    by_title = {row.title: row for row in rows}
    for title in waiting:
        by_title[title].watched = False
    db_session.commit()
    rank_all(client, user, [title for title in truth if title not in waiting])
    for title in waiting:
        by_title[title].watched = True
    db_session.commit()
    return by_title


def _finish(client, user, question, truth):
    better = {title: index for index, title in enumerate(truth)}
    while question:
        choice = "placing" if better[question["placing"]["title"]] < better[question["against"]["title"]] else "against"
        response = answer(client, user, question, choice)
        assert response.status_code == 200, response.text
        question = response.json().get("question")


def test_a_title_deleted_above_the_stretch_does_not_shift_the_new_one_down(client, db_session):
    user = member(db_session)
    truth = [f"F{i:02d}" for i in range(8)]
    rows = films(db_session, user, truth)
    by_title = _rank_all_but(client, db_session, user, rows, truth, ["F04"])
    question = detail(client, user)["question"]
    assert question["placing"]["title"] == "F04" and question["against"]["title"] == "F03"
    answer(client, user, question, "against")  # F04 is somewhere below F03
    db_session.delete(by_title["F00"])  # deleted from the library, above where F04 can still go
    db_session.commit()
    _finish(client, user, detail(client, user)["question"], truth)
    assert ranked_titles(client, user) == truth[1:]  # was F01 F02 F03 F05 F04 ...


def test_a_title_deleted_at_the_end_of_the_stretch_does_not_freeze_the_question(client, db_session):
    user = member(db_session)
    truth = [f"F{i:02d}" for i in range(9)]
    rows = films(db_session, user, truth)
    by_title = _rank_all_but(client, db_session, user, rows, truth, ["F07", "F08"])
    # "Rank it" on F07 while F08, newer, would be offered first.
    question = client.post("/api/rankings/place", headers=headers(user),
                           json={"category": "movies", "item_id": by_title["F07"].id}).json()["question"]
    while True:
        question = answer(client, user, question, "against").json()["question"]
        row = db_session.query(models.Ranking).filter_by(user_id=user.id).one()
        db_session.refresh(row)
        if row.high - row.low == 1:
            break
    db_session.delete(by_title["F06"])  # the last title, the only one left in the stretch
    db_session.commit()
    question = detail(client, user)["question"]
    assert question["placing"]["title"] == "F07"  # still the title being placed, asked again from the middle
    first = answer(client, user, question, "against")
    assert first.status_code == 200, first.text  # was a 409 that handed back the same question, every time
    _finish(client, user, first.json().get("question"), truth)
    assert ranked_titles(client, user) == [title for title in truth if title not in ("F06", "F08")]
    assert detail(client, user)["question"]["placing"]["title"] == "F08"


def test_leaving_out_a_ranked_title_mid_placement_starts_the_question_again(client, db_session):
    user = member(db_session)
    truth = [f"F{i:02d}" for i in range(8)]
    rows = films(db_session, user, truth)
    by_title = _rank_all_but(client, db_session, user, rows, truth, ["F04"])
    question = detail(client, user)["question"]
    answer(client, user, question, "against")
    left = client.post("/api/rankings/skip", headers=headers(user),
                       json={"category": "movies", "item_id": by_title["F00"].id, "leave_out": True})
    assert left.status_code == 200
    _finish(client, user, detail(client, user)["question"], truth)
    assert ranked_titles(client, user) == truth[1:]


def test_window_counts_only_titles_still_in_the_library():
    row = models.Ranking(ranked=rankings._dump([1, 2, 3, 4, 5, 6]), low=3, high=6, placing_id=9)
    assert rankings._window(row, [1, 2, 3, 4, 5, 6]) == (3, 6)
    assert rankings._window(row, [2, 3, 4, 5, 6]) == (2, 5)   # one gone above: the stretch moves up
    assert rankings._window(row, [1, 2, 3, 4, 6]) == (3, 5)   # one gone inside: the stretch is shorter
    assert rankings._window(row, [1, 2, 3]) == (0, 3)         # all of it gone: ask from the whole list


def test_changelog_says_what_the_sweep_fixed(client):
    page = client.get("/changelog")
    assert page.status_code == 200
    assert 'id="security-nov22d-2026-heading"' in page.text
    assert page.text.index("security-nov22d-2026") < page.text.index("rankings-nov22-2026")
