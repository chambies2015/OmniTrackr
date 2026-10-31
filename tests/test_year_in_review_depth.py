"""Year in Review additions (Oct 31 2026): hours, top genres, release mix, friends on the same page, counters."""
import json
from datetime import datetime

from app import crud, models, time_spent, title_metadata, title_pages, year_in_review
from app.site_traffic import RECORDER
from tests.test_title_pages import member
from tests.test_year_in_review import _finish, _user

YEAR = datetime.utcnow().year


def _cache(db, kind, title, year, **data):
    key = title_metadata.cache_key(kind, title_pages.normalize(title), year)
    db.add(models.TitleMetadata(key=key, status="ok", data=json.dumps(data)))
    db.commit()


def _seed(client, db):
    movie = _finish(client, "/movies/", {"title": "Arrival", "director": "D. Villeneuve", "year": 2016, "rating": 9}, "watched")
    _cache(db, "movie", "Arrival", 2016, genres=["Science fiction", "Drama"],
           facts=[{"label": "Running time", "value": "116 min"}])
    _finish(client, "/books/", {"title": "Piranesi", "author": "S. Clarke", "year": 2020, "genre": "Fantasy", "rating": 8}, "read")
    _finish(client, "/video-games/", {"title": "Chrono Trigger", "platform": "SNES", "genres": "RPG, Fantasy",
                                      "release_date": "1995-03-11", "rating": 10}, "played")
    return movie


def _counts(event):
    return sum(count for (_, kind, key), count in RECORDER._pending.items() if kind == "funnel" and key == event)


def test_recap_adds_hours_genres_and_release_mix(authenticated_client, db_session):
    _seed(authenticated_client, db_session)
    recap = authenticated_client.get(f"/api/year-in-review/{YEAR}").json()["recap"]

    assert [g["name"] for g in recap["genres"]][0] == "Fantasy"
    assert {g["name"]: g["count"] for g in recap["genres"]}["Fantasy"] == 2
    assert recap["genres"][0]["count"] == 2 and all(g["count"] >= 1 for g in recap["genres"])

    # 116 minutes of film, a typical book and a typical game: hours, not minutes.
    assert recap["time"]["hours"] >= 20
    assert recap["time"]["shelves"][0]["label"] == "Games"

    releases = recap["releases"]
    assert releases["dated"] == 3 and releases["new"] == 0 and releases["classics"] == 1
    assert releases["oldest"] == {"title": "Chrono Trigger", "year": 1995, "label": "Games", "age": YEAR - 1995}

    page = authenticated_client.get(f"/year-in-review/{YEAR}").text
    assert "hours, give or take" in page and "Genres you kept coming back to" in page
    assert "Oldest finish" in page and "Chrono Trigger" in page
    assert "New or catching up?" in page


def test_hours_and_genres_reach_the_shared_page_and_images(authenticated_client, db_session):
    _seed(authenticated_client, db_session)
    state = authenticated_client.put(f"/api/year-in-review/{YEAR}/share", json={}).json()
    path = "/" + state["url"].split("://", 1)[1].split("/", 1)[1]
    authenticated_client.headers = {}
    authenticated_client.cookies.clear()
    page = authenticated_client.get(path)
    assert page.status_code == 200
    assert "hours, give or take" in page.text and "Fantasy" in page.text
    assert "recap-slide--time" in page.text and "recap-slide--genres" in page.text and "recap-slide--releases" in page.text
    assert "Friends on the same page" not in page.text
    for suffix in ("/card.png", "/story.png"):
        image = authenticated_client.get(path + suffix)
        assert image.status_code == 200 and image.content[:4] == b"\x89PNG"


def test_friends_who_finished_the_same_titles_stay_private(authenticated_client, db_session):
    movie = _seed(authenticated_client, db_session)
    me = _user(db_session)
    pal = member(db_session, "pal")
    loner = member(db_session, "loner")
    crud.create_friendship(db_session, min(me.id, pal.id), max(me.id, pal.id))
    crud.create_friendship(db_session, min(me.id, loner.id), max(me.id, loner.id))
    theirs = models.Movie(user_id=pal.id, title="arrival", director="D. Villeneuve", year=2016, watched=True)
    db_session.add(theirs)
    db_session.flush()
    db_session.add(models.CompletionMoment(user_id=pal.id, category="movies", item_id=theirs.id, title="arrival",
                                           completed_at=datetime(YEAR, 3, 3)))
    db_session.commit()

    recap = authenticated_client.get(f"/api/year-in-review/{YEAR}").json()["recap"]
    assert recap["friends"]["checked"] == 2
    assert recap["friends"]["matches"] == [{"username": "pal", "count": 1, "titles": ["Arrival"]}]
    page = authenticated_client.get(f"/year-in-review/{YEAR}").text
    assert "Friends on the same page" in page and "pal" in page and "loner" not in page

    # The shared snapshot never carries friends.
    assert "friends" not in year_in_review.build(db_session, me, YEAR, public=True)
    state = authenticated_client.put(f"/api/year-in-review/{YEAR}/share", json={}).json()
    share = year_in_review.find_share(db_session, state["url"].rsplit("/", 1)[1])
    assert "friends" not in year_in_review.snapshot(share)
    assert "pal" not in json.dumps(year_in_review.snapshot(share))

    # A friend's private shelf is skipped. My own private shelf still counts on my own private page,
    # like the rest of the recap, since nothing about it reaches the friend.
    pal.movies_private = True
    db_session.commit()
    recap = authenticated_client.get(f"/api/year-in-review/{YEAR}").json()["recap"]
    assert recap["friends"]["matches"] == []
    pal.movies_private = False
    me.movies_private = True
    db_session.commit()
    recap = authenticated_client.get(f"/api/year-in-review/{YEAR}").json()["recap"]
    assert recap["friends"]["matches"][0]["username"] == "pal"
    assert movie["id"]


def test_member_without_friends_gets_no_friends_block(authenticated_client, db_session):
    _seed(authenticated_client, db_session)
    recap = authenticated_client.get(f"/api/year-in-review/{YEAR}").json()["recap"]
    assert recap["friends"] is None
    assert "Friends on the same page" not in authenticated_client.get(f"/year-in-review/{YEAR}").text


def test_recap_counters(authenticated_client, db_session, monkeypatch):
    _seed(authenticated_client, db_session)
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    RECORDER._pending.clear()
    # The test client's own user agent reads as a bot; counters only count browsers.
    authenticated_client.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64) Chrome/130.0 Safari/537.36"
    try:
        authenticated_client.get(f"/year-in-review/{YEAR}")
        assert _counts("recap_opened") == 1
        state = authenticated_client.put(f"/api/year-in-review/{YEAR}/share", json={}).json()
        authenticated_client.put(f"/api/year-in-review/{YEAR}/share", json={})
        assert _counts("recap_link_created") == 1, "a refresh is not a new link"
        path = "/" + state["url"].split("://", 1)[1].split("/", 1)[1]
        authenticated_client.get(path)
        assert _counts("recap_link_opened") == 0, "the owner opening their own link is not a visitor"
        authenticated_client.headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/130.0 Safari/537.36"}
        authenticated_client.cookies.clear()
        authenticated_client.get(path)
        assert _counts("recap_link_opened") == 1
    finally:
        RECORDER._pending.clear()


def test_time_spent_estimate_takes_a_year(authenticated_client, db_session):
    _seed(authenticated_client, db_session)
    me = _user(db_session)
    this_year = time_spent.estimate(db_session, me, year=YEAR)
    last_year = time_spent.estimate(db_session, me, year=YEAR - 1)
    assert this_year["year"] == YEAR and this_year["year_minutes"] > 0
    assert last_year["year"] == YEAR - 1 and last_year["year_minutes"] == 0
    assert last_year["minutes"] == this_year["minutes"], "all-time totals do not depend on the year asked for"


def test_time_traveler_persona():
    recap = {
        "finished_total": 4,
        "categories": [{"category": "movies", "finished": 2}, {"category": "books", "finished": 2}],
        "top_category": {"category": "movies", "finished": 2},
        "releases": {"dated": 4, "new": 0, "classics": 3},
        "longest_streak": 1,
    }
    assert year_in_review.persona(recap)["name"] == "The Time Traveler"
    recap["releases"]["classics"] = 1
    assert year_in_review.persona(recap)["name"] == "The Mixtape"


def test_genre_splitting_and_dedupe():
    assert year_in_review._split_genres("RPG, Fantasy / Adventure; rpg") == ["RPG", "Fantasy", "Adventure", "rpg"]
    assert year_in_review._split_genres(None) == []
    assert year_in_review._split_genres("x" * 60) == []
