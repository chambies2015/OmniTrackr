"""Year in Review: private recap, opt-in shared snapshot, and share card."""
from datetime import date, datetime

from app import models, year_in_review


def _user(db_session):
    return db_session.query(models.User).filter(models.User.username == "testuser").one()


def _finish(client, path, payload, done_field):
    item = client.post(path, json=dict(payload, **{done_field: True})).json()
    category = path.strip("/")
    response = client.post("/completion-moments/", json={"category": category, "item_id": item["id"]})
    assert response.status_code == 200, response.text
    return item


def _seed(client, db_session):
    year = datetime.utcnow().year
    movie = _finish(client, "/movies/", {"title": "Arrival", "director": "D. Villeneuve", "year": 2016, "rating": 9.5}, "watched")
    _finish(client, "/books/", {"title": "Piranesi", "author": "S. Clarke", "year": 2020, "rating": 8}, "read")
    client.post("/activity/", json={"category": "movies", "item_id": movie["id"], "action": "noted",
                                    "note": "Private thought that must never be shared"})
    return year


def test_season_year():
    assert year_in_review.season_year(date(2026, 12, 3)) == 2026
    assert year_in_review.season_year(date(2027, 1, 20)) == 2026
    assert year_in_review.season_year(date(2026, 10, 8)) is None


def test_private_recap_counts_finishes_once(authenticated_client, db_session):
    year = _seed(authenticated_client, db_session)
    data = authenticated_client.get(f"/api/year-in-review/{year}").json()
    recap = data["recap"]
    assert recap["finished_total"] == 2
    assert recap["reflections_total"] == 1
    assert recap["top_rated"][0]["title"] == "Arrival"
    assert recap["added_total"] == 2
    assert data["share"]["shared"] is False


def test_recap_requires_sign_in(client):
    assert client.get("/api/year-in-review/2026").status_code == 401
    page = client.get("/year-in-review/2026", follow_redirects=False)
    assert page.status_code == 302 and page.headers["location"] == "/#login"


def test_future_year_is_not_found(authenticated_client):
    assert authenticated_client.get(f"/api/year-in-review/{datetime.utcnow().year + 1}").status_code == 404


def test_private_page_renders(authenticated_client, db_session):
    year = _seed(authenticated_client, db_session)
    response = authenticated_client.get(f"/year-in-review/{year}")
    assert response.status_code == 200
    assert "Arrival" in response.text and "noindex" in response.text
    assert "Create share link" in response.text


def test_share_snapshot_hides_private_shelves_and_notes(authenticated_client, db_session):
    year = _seed(authenticated_client, db_session)
    user = _user(db_session)
    user.books_private = True
    db_session.commit()

    state = authenticated_client.put(f"/api/year-in-review/{year}/share", json={}).json()
    assert state["shared"] is True
    path = state["url"].split("://", 1)[1].split("/", 1)[1]
    authenticated_client.headers = {}
    authenticated_client.cookies.clear()
    page = authenticated_client.get(f"/{path}")
    assert page.status_code == 200
    assert "Arrival" in page.text
    assert "Piranesi" not in page.text
    assert "Private thought" not in page.text
    assert "Start tracking free" in page.text
    assert page.headers["x-robots-tag"].startswith("noindex")

    card = authenticated_client.get(f"/{path}/card.png")
    assert card.status_code == 200 and card.headers["content-type"] == "image/png"
    assert card.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_refresh_keeps_link_and_unshare_ends_it(authenticated_client, db_session):
    year = _seed(authenticated_client, db_session)
    first = authenticated_client.put(f"/api/year-in-review/{year}/share", json={}).json()
    second = authenticated_client.put(f"/api/year-in-review/{year}/share", json={}).json()
    assert first["url"] == second["url"]
    path = "/" + first["url"].split("://", 1)[1].split("/", 1)[1]
    assert authenticated_client.delete(f"/api/year-in-review/{year}/share").json()["shared"] is False
    assert authenticated_client.get(path).status_code == 404
    assert authenticated_client.get(path + "/card.png").status_code == 404


def test_unknown_token_is_not_found(client):
    assert client.get("/recap/doesnotexist123").status_code == 404


def test_items_without_add_dates_are_not_counted_as_added(authenticated_client, db_session):
    year = datetime.utcnow().year
    authenticated_client.post("/movies/", json={"title": "Old", "director": "X", "year": 1990})
    db_session.query(models.Movie).update({models.Movie.added_at: None})
    db_session.commit()
    recap = authenticated_client.get(f"/api/year-in-review/{year}").json()["recap"]
    assert recap["added_total"] == 0
    assert recap["library_total"] == 1


def test_own_card_download(authenticated_client, db_session):
    year = _seed(authenticated_client, db_session)
    card = authenticated_client.get(f"/api/year-in-review/{year}/card.png")
    assert card.status_code == 200 and card.content[:4] == b"\x89PNG"
