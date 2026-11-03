"""Public profile redesign (Nov 2026): cover, poster scores, numbered showcase, shelf rows, accent and light theme."""
from datetime import datetime, timedelta
from pathlib import Path

from app import models
from app.routers import profiles as profiles_router
from tests.test_public_profiles import enable, headers_for, library, member

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


def test_profile_loads_its_own_stylesheet_and_leaves_the_shared_one_alone(client, db_session):
    user = member(db_session, "restyled")
    library(db_session, user)
    enable(db_session, user)
    html = client.get("/u/restyled").text
    assert f"/static/member-profile.css?v={profiles_router.CSS_VERSION}" in html
    # profile-page.css still styles the widgets, recap and compare pages; the profile itself no longer loads it.
    assert "/static/profile-page.css" not in html
    assert html.index("profile-banners.css") < html.index("member-profile.css")
    assert (STATIC / "member-profile.css").is_file() and (STATIC / "profile-page.css").is_file()


def test_every_profile_gets_a_cover_and_keeps_its_header_parts(client, db_session):
    user = member(db_session, "covered")
    enable(db_session, user, bio="Hello there")
    html = client.get("/u/covered").text
    assert 'class="profile-cover"' in html and 'class="profile-hero__avatar profile-hero__avatar--empty"' in html
    assert "<h1>covered</h1>" in html and "Member since March 2025" in html
    assert 'class="profile-hero__bio"' in html and 'class="profile-hero__actions"' in html


def test_favorites_show_scores_on_the_poster(client, db_session):
    user = member(db_session, "scored")
    library(db_session, user)
    enable(db_session, user)
    html = client.get("/u/scored").text
    assert 'class="profile-poster-grid"' in html
    assert '<span class="profile-poster__score"><span class="profile-sr">Rated </span>10<small>/10</small></span>' in html


def test_showcase_numbers_pins_in_order(client, db_session):
    user = member(db_session, "ranked")
    library(db_session, user)
    enable(db_session, user)
    movies = {m.title: m.id for m in db_session.query(models.Movie).filter(models.Movie.user_id == user.id)}
    picks = [{"category": "movies", "id": movies["Arrival"]}, {"category": "movies", "id": movies["Interstellar"]}]
    assert client.put("/api/profile/showcase", headers=headers_for(user), json={"items": picks}).status_code == 200
    html = client.get("/u/ranked").text
    assert "profile-showcase__grid--2" in html
    assert html.index('profile-poster__rank" aria-hidden="true">1<') < html.index(">Arrival</strong>")
    assert html.index(">Arrival</strong>") < html.index('profile-poster__rank" aria-hidden="true">2<') < html.index(">Interstellar</strong>")


def test_library_rows_put_the_biggest_shelf_first(client, db_session):
    user = member(db_session, "shelves")
    library(db_session, user)
    enable(db_session, user)
    html = client.get("/u/shelves").text
    stats = html[html.index('class="profile-stats"'):]
    assert stats.index("profile-stat--movies") < stats.index("profile-stat--books")
    assert 'class="profile-stat__label"' in stats and 'class="profile-stat__avg"' in stats


def test_supporter_accent_reaches_the_whole_page(client, db_session):
    user = member(db_session, "tinted")
    enable(db_session, user)
    db_session.add(models.Supporter(user_id=user.id, since=datetime(2026, 10, 1),
                                    active_until=datetime.utcnow() + timedelta(days=20), accent="teal", banner="stars"))
    db_session.commit()
    html = client.get("/u/tinted").text
    assert "profile-page--accent-teal" in html and "profile-hero--accent-teal" in html
    cover = html[html.index('class="profile-cover"'):]
    assert cover.index("profile-banner--stars") < cover.index('class="site-wrap profile-hero__inner"')


def test_free_members_get_no_accent_class(client, db_session):
    user = member(db_session, "untinted")
    enable(db_session, user)
    assert "profile-page--accent-" not in client.get("/u/untinted").text


def test_stylesheet_has_a_light_theme_and_every_accent():
    css = (STATIC / "member-profile.css").read_text()
    assert "@media (prefers-color-scheme: light)" in css
    from app import supporters
    for accent in supporters.ACCENTS:
        if accent != "violet":
            assert f".profile-page--accent-{accent} " in css
