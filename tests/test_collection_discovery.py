"""Curator credit, related collections and gallery sorting on public collection pages."""
from datetime import datetime, timedelta

from sqlalchemy import event

from app import models
from app.routers import collections as collections_router


INTRO = (
    "These are the titles I return to when I need a little room to think. Each one rewards attention in a "
    "different way, but together they remind me that a memorable experience can be quiet, curious, and kind. "
    "I keep them close because they make a strong case for taking art at its own pace instead of treating every "
    "watch, read, or play session as something to optimize. They are companions for a reflective weekend."
)


def _user(db, username, profile=None):
    user = models.User(username=username, email=f"{username}@example.com", hashed_password="x",
                       is_verified=True, is_active=True)
    db.add(user)
    db.flush()
    if profile is not None:
        db.add(models.PublicProfile(user_id=user.id, enabled=profile.get("enabled", True),
                                    show_collections=profile.get("show_collections", True)))
    return user


def _collection(db, user, name, titles, *, helpful=0, views=0, published=None):
    collection = models.Collection(user_id=user.id, name=name, description=INTRO, is_public=True,
                                   helpful_count=helpful, view_count=views,
                                   published_at=published or datetime.utcnow())
    db.add(collection)
    db.flush()
    for position, title in enumerate(titles):
        movie = models.Movie(user_id=user.id, title=title, director="Someone", year=2000 + position,
                             watched=True)
        db.add(movie)
        db.flush()
        db.add(models.CollectionItem(collection_id=collection.id, category="movies", item_id=movie.id,
                                     position=position))
    db.flush()
    db.refresh(collection)
    collections_router._apply_automated_readiness(collection, db)
    db.commit()
    return collection


class TestCuratorCredit:
    def test_curator_stays_anonymous_without_a_public_profile(self, client, db_session):
        owner = _user(db_session, "quietcurator")
        collection = _collection(db_session, owner, "Quiet evenings", ["Alpha", "Beta", "Gamma"])

        page = client.get(f"/collections/public/{collection.id}").text

        assert "Curated by an OmniTrackr member" in page
        assert "quietcurator" not in page
        assert '"author": {' not in page

    def test_hidden_collections_setting_keeps_the_curator_anonymous(self, client, db_session):
        owner = _user(db_session, "privatecurator", profile={"show_collections": False})
        collection = _collection(db_session, owner, "Quiet evenings", ["Alpha", "Beta", "Gamma"])

        page = client.get(f"/collections/public/{collection.id}").text

        assert "privatecurator" not in page

    def test_curator_with_public_profile_is_credited_and_linked(self, client, db_session):
        owner = _user(db_session, "loudcurator", profile={})
        collection = _collection(db_session, owner, "Loud mornings", ["Alpha", "Beta", "Gamma"])

        page = client.get(f"/collections/public/{collection.id}").text

        assert 'Curated by <a href="/u/loudcurator">loudcurator</a>' in page
        assert '<meta name="author" content="loudcurator">' in page
        assert '"author": {"@type": "Person", "name": "loudcurator"' in page
        assert '<time datetime="' in page


class TestRelatedCollections:
    def test_related_collections_prefer_shared_titles(self, client, db_session):
        owner = _user(db_session, "firstcurator")
        other = _user(db_session, "secondcurator", profile={})
        source = _collection(db_session, owner, "Source shelf", ["Alpha", "Beta", "Gamma"])
        _collection(db_session, other, "Popular but unrelated", ["Delta", "Epsilon", "Zeta"], helpful=50)
        _collection(db_session, other, "Shares two titles", ["Alpha", "Beta", "Omega"])

        page = client.get(f"/collections/public/{source.id}").text

        assert "More collections to explore" in page
        assert page.index("Shares two titles") < page.index("Popular but unrelated")
        assert 'By <a href="/u/secondcurator">secondcurator</a>' in page
        assert page.count('class="collection-tile"') == 2

    def test_no_related_section_when_nothing_else_is_public(self, client, db_session):
        owner = _user(db_session, "lonecurator")
        source = _collection(db_session, owner, "Only shelf", ["Alpha", "Beta", "Gamma"])
        hidden = models.Collection(user_id=owner.id, name="Private shelf", description=INTRO, is_public=False)
        db_session.add(hidden)
        db_session.commit()

        page = client.get(f"/collections/public/{source.id}").text

        assert "More collections to explore" not in page
        assert "Private shelf" not in page


class TestGallerySort:
    def _three(self, db):
        owner = _user(db, "sortcurator")
        now = datetime.utcnow()
        _collection(db, owner, "Old helpful", ["A1", "A2", "A3"], helpful=9, views=1, published=now - timedelta(days=9))
        _collection(db, owner, "Fresh", ["B1", "B2", "B3"], helpful=0, views=2, published=now)
        _collection(db, owner, "Widely read", ["C1", "C2", "C3"], helpful=1, views=99, published=now - timedelta(days=3))

    def test_default_sort_is_most_helpful_and_indexable(self, client, db_session):
        self._three(db_session)
        response = client.get("/collections/explore")
        page = response.text
        assert page.index("Old helpful") < page.index("Widely read") < page.index("Fresh")
        assert response.headers.get("x-robots-tag") is None
        assert "By an OmniTrackr member" in page

    def test_newest_and_most_read_sorts_are_not_indexed(self, client, db_session):
        self._three(db_session)
        newest = client.get("/collections/explore?sort=newest")
        assert newest.text.index("Fresh") < newest.text.index("Widely read") < newest.text.index("Old helpful")
        assert newest.headers["x-robots-tag"] == "noindex, follow"
        assert '<option value="newest" selected>' in newest.text
        popular = client.get("/collections/explore?sort=popular").text
        assert popular.index("Widely read") < popular.index("Fresh") < popular.index("Old helpful")

    def test_unknown_sort_falls_back_to_most_helpful(self, client, db_session):
        self._three(db_session)
        page = client.get("/collections/explore?sort=<script>").text
        assert "<script>" not in page.split("<main>")[1]
        assert '<option value="helpful" selected>' in page

    def test_public_page_query_count_stays_bounded(self, client, db_session):
        self._three(db_session)
        source = db_session.query(models.Collection).filter_by(name="Fresh").one()
        statements = []

        def count_statement(*args):
            statements.append(args[2])

        event.listen(db_session.bind, "before_cursor_execute", count_statement)
        try:
            response = client.get(f"/collections/public/{source.id}")
        finally:
            event.remove(db_session.bind, "before_cursor_execute", count_statement)
        assert response.status_code == 200
        assert response.text.count('class="collection-tile"') == 2
        assert len(statements) <= 24
