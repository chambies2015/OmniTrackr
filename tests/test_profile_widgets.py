"""Embeddable profile widgets: privacy follows the public profile, images render, and the embed page."""
from datetime import datetime
from io import BytesIO

import pytest

from app import auth, models, profile_widgets
from app.middleware import PUBLIC_PROFILE_PATH
from tests.test_public_profiles import enable, library, member


@pytest.fixture(autouse=True)
def fresh_widget_cache():
    profile_widgets.CACHE._items.clear()
    yield
    profile_widgets.CACHE._items.clear()


def size_of(response):
    from PIL import Image
    return Image.open(BytesIO(response.content)).size


def log_finish(db, user, title, when):
    item = db.query(models.Movie).filter(models.Movie.user_id == user.id, models.Movie.title == title).one()
    db.add(models.ActivityEntry(user_id=user.id, category="movies", item_id=item.id, title=title,
                                action="completed", note="private thoughts", occurred_at=when))
    db.commit()


def test_widgets_404_until_profile_is_on(client, db_session):
    user = member(db_session, "shyfan")
    library(db_session, user)
    for kind in profile_widgets.KINDS:
        assert client.get(f"/u/shyfan/widget/{kind}.png").status_code == 404
    assert client.get("/u/shyfan/widgets").status_code == 404
    db_session.add(models.PublicProfile(user_id=user.id, enabled=False))
    db_session.commit()
    assert client.get("/u/shyfan/widget/stats.png").status_code == 404


def test_stats_and_favorites_widgets_render(client, db_session):
    user = member(db_session, "widgetfan")
    library(db_session, user)
    enable(db_session, user)
    stats = client.get("/u/widgetfan/widget/stats.png")
    assert stats.status_code == 200 and stats.headers["content-type"] == "image/png"
    assert size_of(stats) == (profile_widgets.WIDTH, profile_widgets.HEIGHTS["stats"])
    assert stats.headers["cache-control"] == "public, max-age=900"
    assert stats.headers["cross-origin-resource-policy"] == "cross-origin"
    sharp = client.get("/u/widgetfan/widget/favorites.png?theme=light&scale=2")
    assert sharp.status_code == 200
    assert size_of(sharp) == (profile_widgets.WIDTH * 2, profile_widgets.HEIGHTS["favorites"] * 2)
    # The diary is opt-in, so its widget is too.
    assert client.get("/u/widgetfan/widget/recent.png").status_code == 404
    assert client.get("/u/widgetfan/widget/nope.png").status_code == 404
    # Unknown options fall back instead of failing.
    assert client.get("/u/widgetfan/widget/stats.png?theme=neon&scale=9").status_code == 200


def test_widgets_follow_section_and_privacy_settings(client, db_session):
    user = member(db_session, "privatestats", statistics_private=True)
    library(db_session, user)
    enable(db_session, user, show_favorites=False)
    assert client.get("/u/privatestats/widget/stats.png").status_code == 404
    assert client.get("/u/privatestats/widget/favorites.png").status_code == 404
    page = client.get("/u/privatestats/widgets")
    assert page.status_code == 200
    assert "/widget/stats.png" not in page.text and "/widget/favorites.png" not in page.text


def test_private_categories_stay_off_widgets(db_session):
    user = member(db_session, "nobooks", books_private=True)
    library(db_session, user)
    profile = enable(db_session, user)
    stats = profile_widgets.gather(db_session, user, profile, "stats")
    assert [row["category"] for row in stats.stats] == ["movies"]
    favorites = profile_widgets.gather(db_session, user, profile, "favorites")
    titles = [row["title"] for row in favorites.rows]
    assert "Dune" not in titles and "Interstellar" in titles


def test_recent_widget_reads_the_public_diary_without_notes(client, db_session):
    user = member(db_session, "diaryfan")
    library(db_session, user)
    profile = enable(db_session, user, show_diary=True)
    log_finish(db_session, user, "Arrival", datetime(2026, 10, 20, 12))
    log_finish(db_session, user, "Interstellar", datetime(2026, 10, 24, 12))
    data = profile_widgets.gather(db_session, user, profile, "recent")
    assert [row["title"] for row in data.rows] == ["Interstellar", "Arrival"]
    assert data.rows[0]["note"] == "Oct 24"
    assert "private thoughts" not in repr(data.rows)
    assert client.get("/u/diaryfan/widget/recent.png").status_code == 200


def test_switching_profile_off_beats_the_cache(client, db_session):
    user = member(db_session, "cachefan")
    library(db_session, user)
    profile = enable(db_session, user)
    assert client.get("/u/cachefan/widget/stats.png").status_code == 200
    profile.enabled = False
    db_session.commit()
    assert client.get("/u/cachefan/widget/stats.png").status_code == 404
    profile.enabled = True
    profile.show_stats = False
    db_session.commit()
    assert client.get("/u/cachefan/widget/stats.png").status_code == 404


def test_settings_change_clears_cached_widgets(client, db_session):
    user = member(db_session, "settingsfan")
    library(db_session, user)
    enable(db_session, user)
    assert client.get("/u/settingsfan/widget/stats.png").status_code == 200
    assert any(key[0] == user.id for key in profile_widgets.CACHE._items)
    headers = {"Authorization": f"Bearer {auth.create_user_access_token(user)}"}
    assert client.put("/api/profile/settings", json={"show_stats": False}, headers=headers).status_code == 200
    assert not any(key[0] == user.id for key in profile_widgets.CACHE._items)


def test_id_addresses_and_bot_filter(client, db_session):
    user = member(db_session, "Jane Widget")
    library(db_session, user)
    enable(db_session, user)
    assert client.get(f"/u/id/{user.id}/widget/stats.png").status_code == 200
    assert client.get(f"/u/id/{user.id}/widgets").status_code == 200
    for path in ("/u/admin_fan/widgets", "/u/admin_fan/widget/stats.png", "/u/id/4/widget/recent.png"):
        assert PUBLIC_PROFILE_PATH.match(path)
    assert not PUBLIC_PROFILE_PATH.match("/u/x/widget/../../.env")


def test_embed_page_has_snippets_that_link_back(client, db_session):
    user = member(db_session, "embedder")
    library(db_session, user)
    enable(db_session, user)
    response = client.get("/u/embedder/widgets")
    assert response.status_code == 200
    assert response.headers["x-robots-tag"] == "noindex, follow"
    html = response.text
    assert "https://omnitrackr.xyz/u/embedder?utm_source=profile-widget" in html
    assert "[img]https://omnitrackr.xyz/u/embedder/widget/stats.png[/img]" in html
    assert "Start tracking free" in html  # signed-out visitors get the sign-up nudge
    snippets = profile_widgets.snippets(user, "favorites", "light")
    assert snippets["markdown"] == ("[![embedder's favorites on OmniTrackr]"
                                    "(https://omnitrackr.xyz/u/embedder/widget/favorites.png?theme=light)]"
                                    "(https://omnitrackr.xyz/u/embedder?utm_source=profile-widget)")
    assert 'width="720"' in snippets["html"] and "scale=2" in snippets["html"]


def test_embed_page_escapes_usernames(client, db_session):
    user = member(db_session, "<b>x</b>")
    enable(db_session, user)
    html = client.get(f"/u/id/{user.id}/widgets").text
    assert "<b>x</b>" not in html


def test_owner_sees_widget_links(client, db_session):
    user = member(db_session, "ownerfan")
    library(db_session, user)
    enable(db_session, user)
    client.cookies.set(auth.AUTH_COOKIE_NAME, auth.create_user_access_token(user))
    try:
        profile_html = client.get("/u/ownerfan").text
        assert 'href="/u/ownerfan/widgets"' in profile_html
        page = client.get("/u/ownerfan/widgets").text
        assert "Your profile, anywhere" in page
        assert "Recently finished appears when you switch on the diary." in page
    finally:
        client.cookies.clear()
