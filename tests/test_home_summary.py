"""The dashboard welcome strip (/statistics/home/) and covers on Continue."""
from datetime import datetime, timedelta

from app import models
from app.home_summary import build


def _user(db_session, name="testuser"):
    return db_session.query(models.User).filter(models.User.username == name).one()


def test_home_summary_counts_each_format_and_the_latest_covers(authenticated_client, db_session):
    user = _user(db_session)
    now = datetime.utcnow()
    db_session.add_all([
        models.Movie(title="Arrival", director="Denis Villeneuve", year=2016, rating=9.5, watched=True,
                     poster_url="https://example.com/arrival.jpg", added_at=now - timedelta(days=3), user_id=user.id),
        models.Movie(title="Nope", director="Jordan Peele", year=2022, watched=False, added_at=now - timedelta(days=1), user_id=user.id),
        models.Book(title="Project Hail Mary", author="Andy Weir", year=2021, rating=8.0, read=True,
                    cover_art_url="https://example.com/phm.jpg", added_at=now, user_id=user.id),
        models.Book(title="Bad cover", author="Someone", year=2020, read=False,
                    cover_art_url="javascript:alert(1)", added_at=now, user_id=user.id),
    ])
    db_session.commit()

    response = authenticated_client.get("/statistics/home/")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    data = response.json()
    assert data["name"] == "testuser"
    assert (data["total"], data["finished"], data["unfinished"], data["rated"]) == (4, 2, 2, 2)
    libraries = {library["key"]: library for library in data["libraries"]}
    assert len(libraries) == 9
    assert libraries["movies"] == {
        "key": "movies", "one": "movie", "many": "movies", "verb": "watched", "total": 2,
        "finished": 1, "rated": 1, "average_rating": 9.5, "visible": True,
    }
    assert libraries["books"]["verb"] == "read" and libraries["books"]["finished"] == 1
    assert libraries["music"]["total"] == 0 and libraries["music"]["average_rating"] is None
    # Newest first, only real http(s) covers, never another member's titles.
    assert [item["title"] for item in data["recent"]] == ["Project Hail Mary", "Arrival"]
    assert data["recent"][0] == {"id": data["recent"][0]["id"], "category": "books", "title": "Project Hail Mary",
                                 "image": "https://example.com/phm.jpg"}


def test_home_summary_is_private_to_the_member(client):
    assert client.get("/statistics/home/").status_code == 401


def test_home_summary_leaves_out_hidden_tabs_and_counts_this_months_finishes(authenticated_client, db_session):
    user = _user(db_session)
    now = datetime(2026, 11, 9, 12, 0)
    db_session.add_all([
        models.Movie(title="Arrival", year=2016, watched=True, poster_url="https://example.com/a.jpg", user_id=user.id),
        models.Anime(title="Frieren", year=2023, watched=False, poster_url="https://example.com/f.jpg", user_id=user.id),
        models.ActivityEntry(user_id=user.id, category="movies", item_id=1, title="Arrival", action="completed",
                             source="automatic", occurred_at=datetime(2026, 11, 2)),
        # The same title finished twice counts once; October and other actions don't count.
        models.ActivityEntry(user_id=user.id, category="movies", item_id=1, title="Arrival", action="completed",
                             source="manual", occurred_at=datetime(2026, 11, 3)),
        models.ActivityEntry(user_id=user.id, category="movies", item_id=2, title="Old", action="completed",
                             source="automatic", occurred_at=datetime(2026, 10, 31, 23)),
        models.ActivityEntry(user_id=user.id, category="anime", item_id=3, title="Frieren", action="started",
                             source="manual", occurred_at=datetime(2026, 11, 4)),
    ])
    user.anime_visible = False
    db_session.commit()

    data = build(db_session, user, now=now)
    assert data["finished_this_month"] == 1
    assert data["total"] == 1
    assert [item["category"] for item in data["recent"]] == ["movies"]
    assert next(lib for lib in data["libraries"] if lib["key"] == "anime")["visible"] is False


def test_home_summary_with_an_empty_library(authenticated_client):
    data = authenticated_client.get("/statistics/home/").json()
    assert data["total"] == 0 and data["recent"] == [] and data["finished_this_month"] == 0


def test_continue_items_carry_the_members_cover(authenticated_client, db_session):
    user = _user(db_session)
    db_session.add_all([
        models.Movie(title="Nope", year=2022, watched=False, poster_url="https://example.com/nope.jpg", user_id=user.id),
        models.Book(title="No cover", year=2020, read=False, user_id=user.id),
    ])
    db_session.commit()
    items = {item["title"]: item for item in authenticated_client.get("/statistics/pulse/").json()["continue_items"]}
    assert items["Nope"]["image"] == "https://example.com/nope.jpg"
    assert items["No cover"]["image"] is None
