"""Profile looks (Oct 2026): a pinned showcase for every member and supporter banners."""
from datetime import datetime, timedelta

from app import models, public_profiles, supporters
from app.auth import AUTH_COOKIE_NAME
from app.routers import profiles as profiles_router
from tests.test_public_profiles import enable, headers_for, library, member


def _supporter(db, user, *, days=20, accent=None, banner=None, show_badge=True):
    db.add(models.Supporter(user_id=user.id, since=datetime(2026, 10, 1), active_until=datetime.utcnow() + timedelta(days=days),
                            accent=accent, banner=banner, show_badge=show_badge))
    db.commit()


def _ids(db, user):
    movies = {m.title: m.id for m in db.query(models.Movie).filter(models.Movie.user_id == user.id)}
    books = {b.title: b.id for b in db.query(models.Book).filter(models.Book.user_id == user.id)}
    return movies, books


# ---------------------------------------------------------------- showcase

def test_profiles_look_the_same_until_a_member_pins_something(client, db_session):
    user = member(db_session, "plain")
    library(db_session, user)
    enable(db_session, user)
    page = client.get("/u/plain").text
    assert "profile-showcase__grid" not in page and "profile-banner--" not in page


def test_members_pin_titles_in_order_and_they_lead_the_profile(client, db_session):
    user = member(db_session, "pinner")
    library(db_session, user)
    enable(db_session, user)
    movies, books = _ids(db_session, user)
    picks = [{"category": "books", "id": books["Dune"]}, {"category": "movies", "id": movies["Meh Movie"]}]
    response = client.put("/api/profile/showcase", headers=headers_for(user), json={"items": picks})
    assert response.status_code == 200
    assert [item["title"] for item in response.json()["showcase"]] == ["Dune", "Meh Movie"]
    page = client.get("/u/pinner").text
    assert page.index('id="profile-showcase"') < page.index('id="profile-stats"')
    assert page.index(">Dune</strong>") < page.index(">Meh Movie</strong>")
    settings = client.get("/api/profile/settings", headers=headers_for(user)).json()
    assert settings["showcase_limit"] == 3 and [i["title"] for i in settings["showcase"]] == ["Dune", "Meh Movie"]


def test_free_members_get_three_spots_and_supporters_six(client, db_session):
    user = member(db_session, "many")
    db_session.add_all([models.Movie(user_id=user.id, title=f"Film {i}", director="x", year=2000 + i, rating=7)
                        for i in range(7)])
    db_session.commit()
    ids = sorted(m.id for m in db_session.query(models.Movie).filter(models.Movie.user_id == user.id))
    four = [{"category": "movies", "id": i} for i in ids[:4]]
    response = client.put("/api/profile/showcase", headers=headers_for(user), json={"items": four})
    assert response.status_code == 422 and "up to 3" in response.json()["detail"]

    _supporter(db_session, user)
    six = [{"category": "movies", "id": i} for i in ids[:6]]
    assert len(client.put("/api/profile/showcase", headers=headers_for(user), json={"items": six}).json()["showcase"]) == 6
    seven = [{"category": "movies", "id": i} for i in ids]
    assert client.put("/api/profile/showcase", headers=headers_for(user), json={"items": seven}).status_code == 422


def test_a_lapsed_supporter_shows_their_first_three_pins(client, db_session):
    user = member(db_session, "lapsed")
    db_session.add_all([models.Movie(user_id=user.id, title=f"Film {i}", director="x", year=2000 + i, rating=7)
                        for i in range(5)])
    db_session.add(models.Supporter(user_id=user.id, since=datetime(2026, 1, 1), active_until=datetime(2026, 2, 1)))
    db_session.commit()
    for position, movie in enumerate(db_session.query(models.Movie).filter(models.Movie.user_id == user.id).order_by(models.Movie.id)):
        db_session.add(models.ProfileShowcaseItem(user_id=user.id, category="movies", item_id=movie.id, position=position))
    enable(db_session, user)
    view = public_profiles.build(db_session, user, public_profiles.get_settings(db_session, user.id))
    assert [item["title"] for item in view.showcase] == ["Film 0", "Film 1", "Film 2"]


def test_only_your_own_titles_can_be_pinned(client, db_session):
    owner = member(db_session, "owner")
    other = member(db_session, "other")
    library(db_session, other)
    movies, _ = _ids(db_session, other)
    response = client.put("/api/profile/showcase", headers=headers_for(owner),
                          json={"items": [{"category": "movies", "id": movies["Arrival"]}]})
    assert response.status_code == 422
    bad_category = client.put("/api/profile/showcase", headers=headers_for(owner), json={"items": [{"category": "users", "id": 1}]})
    assert bad_category.status_code == 422
    assert db_session.query(models.ProfileShowcaseItem).count() == 0


def test_private_shelves_can_not_be_pinned_and_old_pins_stay_hidden(client, db_session):
    user = member(db_session, "secret")
    library(db_session, user)
    enable(db_session, user)
    _, books = _ids(db_session, user)
    assert client.put("/api/profile/showcase", headers=headers_for(user),
                      json={"items": [{"category": "books", "id": books["Dune"]}]}).status_code == 200
    user.books_private = True
    db_session.commit()
    assert ">Dune</strong>" not in client.get("/u/secret").text
    response = client.put("/api/profile/showcase", headers=headers_for(user),
                          json={"items": [{"category": "books", "id": books["Dune"]}]})
    assert response.status_code == 422 and "private" in response.json()["detail"]
    search = client.get("/api/profile/showcase/search?q=dune", headers=headers_for(user)).json()["results"]
    assert search == []


def test_deleted_titles_drop_out_of_the_showcase(client, db_session):
    user = member(db_session, "tidy")
    library(db_session, user)
    enable(db_session, user)
    movies, _ = _ids(db_session, user)
    client.put("/api/profile/showcase", headers=headers_for(user), json={"items": [{"category": "movies", "id": movies["Arrival"]}]})
    db_session.query(models.Movie).filter(models.Movie.id == movies["Arrival"]).delete()
    db_session.commit()
    assert "profile-showcase__grid" not in client.get("/u/tidy").text


def test_search_finds_your_titles_and_treats_wildcards_as_text(client, db_session):
    user = member(db_session, "finder")
    library(db_session, user)
    other = member(db_session, "nosy")
    db_session.add(models.Movie(user_id=other.id, title="Arrival Two", director="x", year=2020, rating=10))
    db_session.commit()
    found = client.get("/api/profile/showcase/search?q=arr", headers=headers_for(user)).json()["results"]
    assert [item["title"] for item in found] == ["Arrival"]
    assert client.get("/api/profile/showcase/search?q=%25", headers=headers_for(user)).json()["results"] == []
    top = client.get("/api/profile/showcase/search", headers=headers_for(user)).json()["results"]
    assert top[0]["title"] in {"Interstellar", "Secret Diary"} and top[0]["rating"] == 10
    assert client.get("/api/profile/showcase/search").status_code == 401


def test_showcase_titles_are_escaped(client, db_session):
    user = member(db_session, "escaper")
    db_session.add(models.Movie(user_id=user.id, title='<img src=x onerror=alert(1)>', director="x", year=2001, rating=6))
    db_session.commit()
    enable(db_session, user)
    movie = db_session.query(models.Movie).filter(models.Movie.user_id == user.id).one()
    client.put("/api/profile/showcase", headers=headers_for(user), json={"items": [{"category": "movies", "id": movie.id}]})
    page = client.get("/u/escaper").text
    assert "<img src=x" not in page and "&lt;img src=x onerror=alert(1)&gt;" in page


# ---------------------------------------------------------------- banners

def test_supporters_pick_a_banner_and_it_shows_on_their_profile(client, db_session):
    user = member(db_session, "bannered")
    enable(db_session, user)
    _supporter(db_session, user, accent="teal")
    response = client.put("/api/supporter", headers=headers_for(user), json={"banner": "vinyl"})
    assert response.status_code == 200 and response.json()["banner"] == "vinyl"
    assert "vinyl" in response.json()["banners"]
    page = client.get("/u/bannered").text
    assert 'class="profile-banner profile-banner--vinyl"' in page and "profile-hero--has-banner" in page
    assert "profile-hero--accent-teal" in page
    assert client.put("/api/supporter", headers=headers_for(user), json={"banner": None}).json()["banner"] is None
    assert "profile-banner--" not in client.get("/u/bannered").text


def test_unknown_banners_are_refused(client, db_session):
    user = member(db_session, "odd")
    _supporter(db_session, user)
    response = client.put("/api/supporter", headers=headers_for(user), json={"banner": "url(evil)"})
    assert response.status_code == 422


def test_banners_need_current_support_and_hide_when_it_lapses(client, db_session):
    user = member(db_session, "former")
    enable(db_session, user)
    db_session.add(models.Supporter(user_id=user.id, since=datetime(2026, 1, 1), active_until=datetime(2026, 2, 1),
                                    banner="stars"))
    db_session.commit()
    assert "profile-banner--stars" not in client.get("/u/former").text
    assert client.put("/api/supporter", headers=headers_for(user), json={"banner": "aurora"}).status_code == 403
    assert supporters.get_supporter(db_session, user.id).banner == "stars"  # kept for when they come back

    nobody = member(db_session, "nobody")
    db_session.commit()
    assert client.put("/api/supporter", headers=headers_for(nobody), json={"banner": "aurora"}).status_code == 403


def test_owner_hint_points_free_members_at_supporter_looks(client, db_session):
    free = member(db_session, "freebie")
    enable(db_session, free)
    client.cookies.set(AUTH_COOKIE_NAME, auth_cookie(free))
    page = client.get("/u/freebie").text
    assert "Supporters can also add a banner" in page

    backer = member(db_session, "backer")
    enable(db_session, backer)
    _supporter(db_session, backer, show_badge=False)
    client.cookies.set(AUTH_COOKIE_NAME, auth_cookie(backer))
    page = client.get("/u/backer").text
    client.cookies.clear()
    assert "pin titles to your showcase" in page
    assert "Supporters can also add a banner" not in page


def auth_cookie(user):
    from app import auth
    return auth.create_user_access_token(user)


def test_share_card_shows_the_supporter_badge(db_session):
    user = member(db_session, "carded")
    enable(db_session, user)
    _supporter(db_session, user, accent="rose", banner="aurora")
    view = public_profiles.build(db_session, user, public_profiles.get_settings(db_session, user.id))
    assert view.supporter["banner"] == "aurora"
    png = profiles_router.render_card(view)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_status_payload_lists_banners_for_the_picker(client, db_session):
    user = member(db_session, "picker")
    _supporter(db_session, user, banner="pixels")
    data = client.get("/api/supporter", headers=headers_for(user)).json()
    assert data["banner"] == "pixels" and data["banners"] == list(supporters.BANNERS)
