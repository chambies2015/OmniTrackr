"""Sweep of the Nov 13 merges: episode scores and notes (#206), the friends feed, clubs and
discussions refresh (#207), after the Nov 13 sweep itself (#205)."""
import time

from sqlalchemy import event

from app import episode_notes, models
from app.routers import progress as progress_router
from tests.conftest import engine
from tests.test_episode_notes import note, show  # noqa: F401  (fixture)
from tests.test_episode_tracking import TVmazeClient, use_client
from tests.test_security_sweep_nov06 import _limited


def _statements(fn):
    seen = []

    def hook(conn, cursor, statement, *args):
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", hook)
    try:
        result = fn()
    finally:
        event.remove(engine, "before_cursor_execute", hook)
    return result, seen


# ---------------------------------------------------------------- rate limits

def test_every_episode_notes_route_is_rate_limited():
    for method in ("PUT", "DELETE"):
        assert _limited(progress_router.router, "/progress/{category}/{item_id}/episode-notes", method)


# ---------------------------------------------------------------- backup import

def test_counting_per_show_matches_a_full_scan():
    have = {("anime", 1, "e1"), ("anime", 1, "e2"), ("tv-shows", 1, "s1e1"), ("anime", 2, "e1")}
    assert episode_notes.count_per_show(have) == {("anime", 1): 2, ("tv-shows", 1): 1, ("anime", 2): 1}


def test_import_with_many_rows_for_one_show_stays_quick(authenticated_client, show, db_session):
    """Each row used to scan every saved entry, so 20,000 rows over 50,000 entries took over a minute."""
    have = {("anime", item % 500, f"e{item}") for item in range(50000)}
    counts = episode_notes.count_per_show(have)
    started = time.perf_counter()
    for _ in range(5000):
        episode_notes.stage_import(db_session, 1, 7, "anime", [], have, [0], counts)
    assert time.perf_counter() - started < 1.0


def test_import_looks_a_repeated_show_up_once_and_keeps_the_per_show_cap(authenticated_client, show, db_session,
                                                                          monkeypatch):
    monkeypatch.setattr(episode_notes, "MAX_PER_SHOW", 3)
    note(authenticated_client, show["id"], season=1, episode=1, rating=8)
    row = {"category": "tv-shows", "title": "Breaking Bad", "year": 2008}
    backup = {"episode_notes": [
        {**row, "episodes": [{"season": 1, "episode": 2, "rating": 7}]},
        {**row, "episodes": []},
        {**row, "episodes": [{"season": 1, "episode": 3, "rating": 6}, {"season": 1, "episode": 4, "rating": 5}]},
        {**row, "episodes": [{"season": 1, "episode": 5, "rating": 4}]},
    ]}
    response, seen = _statements(lambda: authenticated_client.post("/import/", json=backup))
    result = response.json()
    # One saved before plus two restored reaches the cap of three; the other two wait.
    assert result["episode_notes_created"] == 2
    assert result["episode_notes_skipped"] == 2
    assert sorted(entry.episode for entry in db_session.query(models.EpisodeNote)) == [1, 2, 3]
    show_lookups = [s for s in seen if s.lstrip().upper().startswith("SELECT") and "FROM tv_shows" in s
                    and "lower(trim(tv_shows.title))" in s.lower()]
    assert len(show_lookups) == 1


# ---------------------------------------------------------------- episode guide queries

def test_episode_guide_reads_the_show_and_checkpoint_once(authenticated_client, show, monkeypatch):
    client = authenticated_client
    use_client(monkeypatch, TVmazeClient())
    client.get(f"/progress/tv-shows/{show['id']}/episodes")

    saved, writes = _statements(lambda: note(client, show["id"], season=1, episode=3, rating=9, note="Good"))
    assert saved.status_code == 200
    assert len(writes) <= 11, len(writes)
    assert saved.json()["episode_notes"][0]["rating"] == 9

    changed, writes = _statements(lambda: note(client, show["id"], season=1, episode=3, rating=8))
    assert changed.status_code == 200 and len(writes) <= 9, len(writes)

    guide, reads = _statements(lambda: client.get(f"/progress/tv-shows/{show['id']}/episodes"))
    assert guide.status_code == 200
    assert len(reads) <= 5, len(reads)
    body = guide.json()
    assert body["category"] == "tv-shows" and body["item_id"] == show["id"]
    assert body["layout"]["seasons"][0] == {"number": 1, "episodes": 7}
    assert body["episode_note_summary"] == {"rated": 1, "noted": 0, "average": 8.0}


def test_episode_guide_still_answers_404_for_someone_elses_show(authenticated_client, show, db_session):
    other = models.User(email="other@example.com", username="someoneelse", hashed_password="x", is_verified=True)
    db_session.add(other)
    db_session.commit()
    theirs = models.TVShow(user_id=other.id, title="Not yours", year=2020, watched=False)
    db_session.add(theirs)
    db_session.commit()
    assert authenticated_client.get(f"/progress/tv-shows/{theirs.id}/episodes").status_code == 404
    assert note(authenticated_client, theirs.id, season=1, episode=1, rating=5).status_code == 404
