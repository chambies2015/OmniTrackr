"""Sweep of the Nov 8 merges: the homepage poster wall (#185), the Nov 6 sweep (#183),
the Thanksgiving and December guides (#186) and collection share links (#184)."""
from contextlib import contextmanager

from sqlalchemy import event

from app import auth, models
from tests.conftest import engine


@contextmanager
def counted_queries():
    seen = []

    def count(*args, **kwargs):
        seen.append(1)

    event.listen(engine, "before_cursor_execute", count)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", count)


def _long_list(db_session, username, titles):
    owner = models.User(username=username, email=f"{username}@example.test", hashed_password="unused",
                        is_active=True, is_verified=True)
    db_session.add(owner)
    db_session.flush()
    collection = models.Collection(user_id=owner.id, name=f"{titles} films I keep recommending")
    db_session.add(collection)
    db_session.flush()
    for position in range(titles):
        movie = models.Movie(user_id=owner.id, title=f"{username} film {position}", year=1940 + position)
        db_session.add(movie)
        db_session.flush()
        db_session.add(models.CollectionItem(collection_id=collection.id, category="movies", item_id=movie.id,
                                             position=position, curator_note="Worth a second look."))
    db_session.commit()
    return owner, collection


def sign_in(client, user):
    client.headers["Authorization"] = "Bearer " + auth.create_access_token({"sub": user.username})


class TestListEditsDontQueryEveryTitle:
    """Share links added a second per-title check to every edit of a list. Each title was
    read with its own query, so a 40-title list ran about 80 more queries per save."""

    def test_turning_on_a_share_link_reads_the_titles_once(self, client, db_session):
        owner, collection = _long_list(db_session, "link_owner", 40)
        sign_in(client, owner)
        with counted_queries() as seen:
            response = client.post(f"/collections/{collection.id}/link")
        assert response.status_code == 200, response.text
        assert len(seen) < 15

    def test_renaming_a_long_list_does_not_query_per_title(self, client, db_session):
        owner, collection = _long_list(db_session, "short_owner", 40)
        sign_in(client, owner)
        with counted_queries() as small:
            client.patch(f"/collections/{collection.id}", json={"name": "Forty films, renamed"})
        other, bigger = _long_list(db_session, "long_owner", 80)
        sign_in(client, other)
        with counted_queries() as large:
            response = client.patch(f"/collections/{bigger.id}", json={"name": "Eighty films, renamed"})
        assert response.status_code == 200, response.text
        assert response.json()["readiness"]["link_ready"] is True
        # Twice the titles shouldn't mean twice the queries.
        assert len(large) - len(small) < 10

