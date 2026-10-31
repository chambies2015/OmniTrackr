"""Year in Review story mode: new yearly stats, tap-through slides, the vertical story image,
and the December entry points (weekly email, public profile)."""
import io
from datetime import date, datetime, timedelta

from app import digest, models, year_in_review
from app.routers import year_in_review as recap_router


def _user(db_session):
    return db_session.query(models.User).filter(models.User.username == "testuser").one()


def _finish(client, path, payload, done_field):
    item = client.post(path, json=dict(payload, **{done_field: True})).json()
    response = client.post("/completion-moments/", json={"category": path.strip("/"), "item_id": item["id"]})
    assert response.status_code == 200, response.text
    return item


def _seed(client):
    _finish(client, "/movies/", {"title": "Arrival", "director": "Denis Villeneuve", "year": 2016, "rating": 9.5}, "watched")
    _finish(client, "/movies/", {"title": "Dune", "director": "Denis Villeneuve", "year": 2021, "rating": 8}, "watched")
    _finish(client, "/movies/", {"title": "Heat", "director": "Michael Mann", "year": 1995, "rating": 9}, "watched")
    _finish(client, "/books/", {"title": "Piranesi", "author": "S. Clarke", "year": 2020, "rating": 7}, "read")
    return datetime.utcnow().year


def _shared_path(client, year):
    url = client.put(f"/api/year-in-review/{year}/share", json={}).json()["url"]
    return "/" + url.split("://", 1)[1].split("/", 1)[1]


def test_longest_streak_counts_consecutive_days():
    day = date(2026, 11, 1)
    days = {day, day + timedelta(days=1), day + timedelta(days=2), day + timedelta(days=5)}
    assert year_in_review._longest_streak(days) == 3
    assert year_in_review._longest_streak(set()) == 0


def test_persona_rules():
    base = {"year": 2026, "finished_total": 10, "longest_streak": 0, "ratings": None}
    omnivore = dict(base, categories=[{"finished": 2}] * 4, top_category={"category": "movies", "finished": 3})
    assert year_in_review.persona(omnivore)["key"] == "omnivore"
    books = dict(base, categories=[{"finished": 8}, {"finished": 2}], top_category={"category": "books", "finished": 8})
    assert year_in_review.persona(books)["name"] == "The Bookworm"
    mixed = dict(base, categories=[{"finished": 5}, {"finished": 5}], top_category={"category": "movies", "finished": 5})
    assert year_in_review.persona(mixed)["key"] == "mixer"
    assert year_in_review.persona(dict(mixed, longest_streak=9))["key"] == "regular"
    assert year_in_review.persona(dict(base, finished_total=2, categories=[], top_category=None)) is None


def test_recap_has_streak_rating_style_and_top_creator(authenticated_client):
    year = _seed(authenticated_client)
    recap = authenticated_client.get(f"/api/year-in-review/{year}").json()["recap"]
    assert recap["active_days"] >= 1 and recap["longest_streak"] >= 1
    assert recap["ratings"]["count"] == 4 and recap["ratings"]["average"] == 8.4
    assert recap["top_creator"] == {"name": "Denis Villeneuve", "category": "movies", "label": "Movies",
                                    "role": "director", "count": 2}
    assert recap["persona"]["name"] == "The Movie Night Regular"


def test_owner_page_has_story_and_story_image(authenticated_client):
    year = _seed(authenticated_client)
    page = authenticated_client.get(f"/year-in-review/{year}")
    assert page.status_code == 200
    assert "data-recap-story" in page.text and "data-story-open" in page.text
    assert "year-in-review-story.js" in page.text
    assert "Your top director" in page.text and "The Movie Night Regular" in page.text
    image = authenticated_client.get(f"/api/year-in-review/{year}/story.png")
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    from PIL import Image
    assert Image.open(io.BytesIO(image.content)).size == (1080, 1920)


def test_empty_year_has_no_story(authenticated_client):
    page = authenticated_client.get(f"/year-in-review/{datetime.utcnow().year}")
    assert page.status_code == 200
    assert "data-recap-story" not in page.text


def test_shared_story_leaves_out_private_shelves(authenticated_client, db_session):
    year = _seed(authenticated_client)
    user = _user(db_session)
    user.movies_private = True
    db_session.commit()
    path = _shared_path(authenticated_client, year)
    authenticated_client.headers = {}
    authenticated_client.cookies.clear()
    page = authenticated_client.get(path)
    assert page.status_code == 200
    assert "data-recap-story" in page.text and "Start tracking free" in page.text
    assert "Villeneuve" not in page.text and "Arrival" not in page.text
    story = authenticated_client.get(path + "/story.png")
    assert story.status_code == 200 and story.headers["content-type"] == "image/png"


def test_signed_in_visitor_is_sent_to_their_own_recap(authenticated_client):
    year = _seed(authenticated_client)
    page = authenticated_client.get(_shared_path(authenticated_client, year))
    assert f'href="/year-in-review/{year}"' in page.text and "Open my recap" in page.text


def test_old_snapshot_without_new_stats_still_renders(authenticated_client, db_session):
    year = _seed(authenticated_client)
    path = _shared_path(authenticated_client, year)
    share = db_session.query(models.YearInReviewShare).one()
    share.snapshot = ('{"year": %d, "finished_total": 2, "categories": [], "months": [], "top_rated": [], '
                      '"favorites": [], "goals": []}' % year)
    db_session.commit()
    recap_router._CARDS.clear_user(share.user_id)
    assert authenticated_client.get(path).status_code == 200
    assert authenticated_client.get(path + "/story.png").status_code == 200


def test_render_story_handles_long_names_and_quiet_years():
    png = recap_router.render_story("x" * 80, {"year": 2026, "finished_total": 0})
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_weekly_email_mentions_recap_in_season(authenticated_client, db_session):
    year = _seed(authenticated_client)
    user = _user(db_session)
    assert digest.recap_line(db_session, user.id, date(year, 10, 19)) is None
    line = digest.recap_line(db_session, user.id, date(year, 12, 4))
    assert line == {"year": year, "finished": 4}
    report = {"matches": [], "popular": [{"title": "Some Film", "label": "Movie", "date": None, "url": "/release-radar"}]}
    subject, html, text = digest.build_digest("testuser", report, "https://x/unsub", recap=line)
    assert f"Your {year} in review" in html and f"/year-in-review/{year}#story" in text


def test_profile_links_shared_recap_in_season(authenticated_client, db_session, monkeypatch):
    year = _seed(authenticated_client)
    _shared_path(authenticated_client, year)
    share = db_session.query(models.YearInReviewShare).one()
    from app.routers import profiles
    monkeypatch.setattr(year_in_review, "season_year", lambda today=None: year)
    assert profiles._season_recap(db_session, share.user_id) == (year_in_review.share_path(share), year)
    monkeypatch.setattr(year_in_review, "season_year", lambda today=None: None)
    assert profiles._season_recap(db_session, share.user_id) == (None, None)
