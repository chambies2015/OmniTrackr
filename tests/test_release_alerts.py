"""Release day alerts: a notification when something connected to a member's library comes out."""
from datetime import date, timedelta

from app import auth, models, release_alerts
from app import release_radar as radar

TODAY = date(2026, 10, 10)


def member(db, username, active=True):
    user = models.User(username=username, email=f"{username}@example.com", is_verified=True, is_active=active,
                       hashed_password=auth.get_password_hash("password123"))
    db.add(user)
    db.flush()
    return user


def item(category, key, title, day=TODAY, alt_title=""):
    return radar.make_item(category=category, key=key, title=title, release_date=day.isoformat(),
                           source_url=None, alt_title=alt_title, save={"title": title})


def notifications(db, user):
    return db.query(models.Notification).filter_by(user_id=user.id, type="release_day").all()


def test_member_is_told_on_release_day_about_a_title_they_track(db_session):
    sam = member(db_session, "sam")
    db_session.add(models.Movie(user_id=sam.id, title="The Long Walk", director="X"))
    db_session.commit()
    pool = [item("movies", "wd-Q1", "The Long Walk"), item("movies", "wd-Q2", "Something Else")]
    stats = release_alerts.send_alerts(db_session, pool, TODAY)
    assert stats == {"members": 1, "releases": 1}
    [note] = notifications(db_session, sam)
    assert note.message == "Out today: The Long Walk (Movie), from your library."
    assert note.link == "/release-radar/movies#item-wd-Q1"
    assert note.read_at is None


def test_new_seasons_and_sequels_name_the_title_they_continue(db_session):
    sam = member(db_session, "sam")
    db_session.add(models.TVShow(user_id=sam.id, title="Severance"))
    db_session.commit()
    release_alerts.send_alerts(db_session, [item("tv", "tvm-1-s3", "Severance Season 3")], TODAY)
    [note] = notifications(db_session, sam)
    assert note.message == "Out today: Severance Season 3 (TV), because you track Severance."


def test_alt_titles_match_too(db_session):
    sam = member(db_session, "sam")
    db_session.add(models.Anime(user_id=sam.id, title="Attack on Titan"))
    db_session.commit()
    release_alerts.send_alerts(db_session, [item("anime", "al-9", "Shingeki no Kyojin", alt_title="Attack on Titan")], TODAY)
    assert len(notifications(db_session, sam)) == 1


def test_several_releases_arrive_as_one_notification(db_session):
    sam = member(db_session, "sam")
    db_session.add_all([models.Movie(user_id=sam.id, title="Dune"), models.TVShow(user_id=sam.id, title="Andor"),
                        models.VideoGame(user_id=sam.id, title="Hollow Knight")])
    db_session.commit()
    pool = [item("movies", "wd-Q3", "Dune Part Three"), item("tv", "tvm-2-s2", "Andor Season 2"),
            item("games", "rawg-hollow-knight-silksong", "Hollow Knight Silksong")]
    stats = release_alerts.send_alerts(db_session, pool, TODAY)
    assert stats == {"members": 1, "releases": 3}
    [note] = notifications(db_session, sam)
    assert note.message == "Out today from your library: Dune Part Three, Andor Season 2 and 1 more."
    assert note.link == "/release-radar"
    assert db_session.query(models.ReleaseAlert).filter_by(user_id=sam.id).count() == 3


def test_each_release_is_announced_once_even_after_dismissal(db_session):
    sam = member(db_session, "sam")
    db_session.add(models.Movie(user_id=sam.id, title="Dune"))
    db_session.commit()
    pool = [item("movies", "wd-Q3", "Dune Part Three")]
    release_alerts.send_alerts(db_session, pool, TODAY)
    db_session.query(models.Notification).filter_by(user_id=sam.id).delete()
    db_session.commit()
    assert release_alerts.send_alerts(db_session, pool, TODAY) == {"members": 0, "releases": 0}
    assert notifications(db_session, sam) == []
    # A release whose date slipped is still not announced a second time.
    moved = [item("movies", "wd-Q3", "Dune Part Three", day=TODAY + timedelta(days=7))]
    assert release_alerts.send_alerts(db_session, moved, TODAY + timedelta(days=7))["members"] == 0


def test_a_later_release_on_the_same_day_gets_its_own_notification(db_session):
    sam = member(db_session, "sam")
    db_session.add_all([models.Movie(user_id=sam.id, title="Dune"), models.TVShow(user_id=sam.id, title="Andor")])
    db_session.commit()
    release_alerts.send_alerts(db_session, [item("movies", "wd-Q3", "Dune Part Three")], TODAY)
    release_alerts.send_alerts(db_session, [item("movies", "wd-Q3", "Dune Part Three"),
                                            item("tv", "tvm-2-s2", "Andor Season 2")], TODAY)
    messages = sorted(note.message for note in notifications(db_session, sam))
    assert messages == ["Out today: Andor Season 2 (TV), because you track Andor.",
                        "Out today: Dune Part Three (Movie), because you track Dune."]


def test_only_todays_releases_count(db_session):
    sam = member(db_session, "sam")
    db_session.add(models.Movie(user_id=sam.id, title="Dune"))
    db_session.commit()
    pool = [item("movies", "wd-Q3", "Dune Part Three", day=TODAY + timedelta(days=1)),
            item("movies", "wd-Q4", "Dune Prequel", day=TODAY - timedelta(days=1))]
    assert release_alerts.send_alerts(db_session, pool, TODAY)["members"] == 0


def test_unrelated_and_inactive_members_are_left_alone(db_session):
    other = member(db_session, "other")
    gone = member(db_session, "gone", active=False)
    db_session.add_all([models.Movie(user_id=other.id, title="Heat"), models.Movie(user_id=gone.id, title="Dune"),
                        models.Book(user_id=other.id, title="Dune")])  # books aren't on Release Radar
    db_session.commit()
    pool = [item("movies", "wd-Q3", "Dune Part Three"), item("movies", "wd-Q5", "Heatwave")]
    assert release_alerts.send_alerts(db_session, pool, TODAY)["members"] == 0
    assert db_session.query(models.Notification).count() == 0


def test_library_is_not_changed(db_session):
    sam = member(db_session, "sam")
    db_session.add(models.Movie(user_id=sam.id, title="Dune", rating=8.0, watched=True))
    db_session.commit()
    release_alerts.send_alerts(db_session, [item("movies", "wd-Q3", "Dune Part Three")], TODAY)
    [movie] = db_session.query(models.Movie).filter_by(user_id=sam.id).all()
    assert (movie.title, movie.rating, movie.watched) == ("Dune", 8.0, True)


def test_like_wildcards_in_titles_are_literal(db_session):
    sam = member(db_session, "sam")
    db_session.add(models.Movie(user_id=sam.id, title="100 Percent"))
    db_session.commit()
    assert release_alerts.send_alerts(db_session, [item("movies", "wd-Q6", "100% Wolf")], TODAY)["members"] == 0


def test_unsafe_keys_link_to_the_category_page():
    assert release_alerts.item_link(item("games", "rawg-a b", "X")) == "/release-radar/games"
    assert release_alerts.item_link(item("games", "rawg-ab", "X")) == "/release-radar/games#item-rawg-ab"


def test_notification_reaches_the_bell(authenticated_client, db_session):
    me = db_session.query(models.User).filter_by(username="testuser").one()
    db_session.add(models.TVShow(user_id=me.id, title="Severance"))
    db_session.commit()
    release_alerts.send_alerts(db_session, [item("tv", "tvm-1-s3", "Severance Season 3")], TODAY)
    listed = authenticated_client.get("/notifications").json()
    assert any(n["type"] == "release_day" and n["link"] == "/release-radar/tv#item-tvm-1-s3" for n in listed)
    assert authenticated_client.get("/notifications/count").json()["count"] >= 1


def test_background_entry_point_uses_its_own_session(db_session):
    from tests.conftest import TestingSessionLocal
    sam = member(db_session, "sam")
    db_session.add(models.Movie(user_id=sam.id, title="Dune"))
    db_session.commit()
    stats = release_alerts.send_due_alerts(TestingSessionLocal, [item("movies", "wd-Q3", "Dune Part Three")], TODAY)
    assert stats == {"members": 1, "releases": 1}
