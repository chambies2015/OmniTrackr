"""Public profile, Nov 14 2026: showcase notes and spotlight, the opt-in "Right now" shelf, rating spread, favorites filter."""
import re
from datetime import datetime, timedelta
from pathlib import Path

from app import models
from tests.test_public_profiles import enable, headers_for, library, member

ROOT = Path(__file__).resolve().parent.parent


def _movies(db, user):
    return {m.title: m.id for m in db.query(models.Movie).filter(models.Movie.user_id == user.id)}


def _pin(client, user, picks):
    return client.put("/api/profile/showcase", headers=headers_for(user), json={"items": picks})


# ---------------------------------------------------------------- showcase notes

def test_pins_take_a_note_that_shows_in_the_spotlight_and_cards(client, db_session):
    user = member(db_session, "noter")
    library(db_session, user)
    enable(db_session, user)
    movies = _movies(db_session, user)
    response = _pin(client, user, [{"category": "movies", "id": movies["Interstellar"], "note": "  The docking   scene. "},
                                   {"category": "movies", "id": movies["Arrival"], "note": "Made me call my mum."}])
    assert response.status_code == 200
    assert [item["note"] for item in response.json()["showcase"]] == ["The docking scene.", "Made me call my mum."]
    html = client.get("/u/noter").text
    spotlight = html[html.index('class="profile-spotlight"'):html.index("</article>")]
    assert '<blockquote class="profile-spotlight__note"><p>The docking scene.</p></blockquote>' in spotlight
    assert '<q class="profile-pick__note">Made me call my mum.</q>' in html


def test_a_pick_without_a_note_keeps_the_old_one_and_an_empty_note_clears_it(client, db_session):
    user = member(db_session, "keeper")
    library(db_session, user)
    enable(db_session, user)
    movies = _movies(db_session, user)
    first, second = movies["Interstellar"], movies["Arrival"]
    _pin(client, user, [{"category": "movies", "id": first, "note": "Top of the list"},
                        {"category": "movies", "id": second, "note": "Close second"}])
    # An older page that doesn't know about notes reorders the pins.
    reordered = _pin(client, user, [{"category": "movies", "id": second}, {"category": "movies", "id": first}]).json()
    assert [(i["title"], i["note"]) for i in reordered["showcase"]] == [("Arrival", "Close second"), ("Interstellar", "Top of the list")]
    cleared = _pin(client, user, [{"category": "movies", "id": second, "note": ""}, {"category": "movies", "id": first}]).json()
    assert [i["note"] for i in cleared["showcase"]] == [None, "Top of the list"]


def test_notes_follow_the_bio_rules(client, db_session):
    user = member(db_session, "rulebound")
    library(db_session, user)
    enable(db_session, user)
    film = _movies(db_session, user)["Arrival"]
    too_long = _pin(client, user, [{"category": "movies", "id": film, "note": "x" * 141}])
    assert too_long.status_code == 422 and "140" in too_long.json()["detail"]
    link = _pin(client, user, [{"category": "movies", "id": film, "note": "Watch it at https://spam.example"}])
    assert link.status_code == 422
    assert db_session.query(models.ProfileShowcaseItem).filter_by(user_id=user.id).count() == 0


def test_old_pins_without_notes_still_render(client, db_session):
    user = member(db_session, "oldpins")
    library(db_session, user)
    enable(db_session, user)
    db_session.add(models.ProfileShowcaseItem(user_id=user.id, category="movies", item_id=_movies(db_session, user)["Arrival"]))
    db_session.commit()
    html = client.get("/u/oldpins").text
    assert ">Arrival</a></h3>" in html and "profile-spotlight__note" not in html


def test_owner_is_told_about_notes_until_they_write_one(client, db_session):
    user = member(db_session, "hinted")
    library(db_session, user)
    enable(db_session, user)
    film = _movies(db_session, user)["Arrival"]
    _pin(client, user, [{"category": "movies", "id": film}])
    from app import auth
    from app.auth import AUTH_COOKIE_NAME
    client.cookies.set(AUTH_COOKIE_NAME, auth.create_user_access_token(user))
    try:
        assert "Add a line to each pin" in client.get("/u/hinted").text
        _pin(client, user, [{"category": "movies", "id": film, "note": "A quiet one."}])
        assert "Add a line to each pin" not in client.get("/u/hinted").text
    finally:
        client.cookies.clear()


# ---------------------------------------------------------------- right now

def _queue(db, user):
    movies = _movies(db, user)
    db.add(models.Movie(user_id=user.id, title="Blade Runner 2049", year=2017, watched=False))
    db.add(models.TVShow(user_id=user.id, title="Dark", year=2017, watched=False))
    db.commit()
    runner = db.query(models.Movie).filter_by(user_id=user.id, title="Blade Runner 2049").one()
    dark = db.query(models.TVShow).filter_by(user_id=user.id, title="Dark").one()
    now = datetime.utcnow()
    db.add_all([
        models.NextUpItem(user_id=user.id, category="movies", item_id=runner.id, position=0, started_at=now - timedelta(days=2)),
        models.NextUpItem(user_id=user.id, category="tv-shows", item_id=dark.id, position=1),
        # Finished titles never show, even when they're still queued.
        models.NextUpItem(user_id=user.id, category="movies", item_id=movies["Arrival"], position=2, started_at=now),
    ])
    db.commit()


def test_right_now_is_off_by_default(client, db_session):
    user = member(db_session, "quietqueue")
    library(db_session, user)
    enable(db_session, user)
    _queue(db_session, user)
    html = client.get("/u/quietqueue").text
    assert 'id="profile-now"' not in html and "Blade Runner 2049" not in html
    assert client.get("/api/profile/settings", headers=headers_for(user)).json()["show_now"] is False


def test_right_now_shows_started_and_queued_titles_once_switched_on(client, db_session):
    user = member(db_session, "busy")
    library(db_session, user)
    enable(db_session, user)
    _queue(db_session, user)
    saved = client.put("/api/profile/settings", headers=headers_for(user), json={"show_now": True})
    assert saved.status_code == 200 and saved.json()["show_now"] is True
    html = client.get("/u/busy").text
    section = html[html.index('id="profile-now"'):html.index("</section>", html.index('id="profile-now"'))]
    assert "Watching" in section and "Blade Runner 2049" in section and "since " in section
    assert '<h3>Next in the queue</h3>' in section and ">Dark</span>" in section
    assert "Arrival" not in section
    assert '<a href="#profile-now">Right now</a>' in html


def test_right_now_skips_private_shelves(client, db_session):
    user = member(db_session, "privateq", movies_private=True)
    library(db_session, user)
    enable(db_session, user, show_now=True)
    _queue(db_session, user)
    html = client.get("/u/privateq").text
    assert "Blade Runner 2049" not in html
    assert ">Dark</span>" in html


# ---------------------------------------------------------------- rating spread and favorites filter

def test_rating_spread_sits_in_the_about_box(client, db_session):
    user = member(db_session, "spready")
    library(db_session, user)
    enable(db_session, user)
    html = client.get("/u/spready").text
    glance = html[html.index('class="title-glance profile-glance"'):]
    assert 'class="profile-spread__bars"' in glance
    assert len(re.findall(r'class="profile-spread__bar[ "]', html)) == 10
    assert "5 rated titles, most often a 9" in glance


def test_rating_spread_follows_the_stats_switches(client, db_session):
    user = member(db_session, "hidespread", statistics_private=True)
    library(db_session, user)
    enable(db_session, user)
    assert "profile-spread" not in client.get("/u/hidespread").text
    other = member(db_session, "nostats")
    library(db_session, other)
    enable(db_session, other, show_stats=False)
    assert "profile-spread" not in client.get("/u/nostats").text


def test_favorites_filter_only_with_enough_titles_in_two_formats(client, db_session):
    user = member(db_session, "filtery")
    library(db_session, user)
    enable(db_session, user)
    assert "data-profile-filter" not in client.get("/u/filtery").text
    db_session.add_all([models.Book(user_id=user.id, title=f"Book {i}", rating=9, read=True) for i in range(4)])
    db_session.commit()
    html = client.get("/u/filtery").text
    assert 'data-profile-filter hidden' in html
    assert '<button type="button" data-filter="books" aria-pressed="false">Books</button>' in html
    assert 'data-format="books"' in html


# ---------------------------------------------------------------- assets

def test_settings_and_assets_carry_the_new_parts():
    page = (ROOT / "app" / "templates" / "index.html").read_text()
    assert 'id="profileShowNow"' in page
    assert "show_now: 'profileShowNow'" in (ROOT / "app" / "static" / "public-profile.js").read_text()
    assert "showcase-row__note" in (ROOT / "app" / "static" / "profile-showcase.js").read_text()
    css = (ROOT / "app" / "static" / "member-profile.css").read_text()
    for name in (".profile-spotlight", ".profile-pick", ".profile-now__card", ".profile-spread__bar", ".profile-filter"):
        assert name in css
    assert "setupFilter" in (ROOT / "app" / "static" / "profile-page.js").read_text()
