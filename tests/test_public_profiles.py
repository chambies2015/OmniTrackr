"""Opt-in public profiles (/u/<username>): privacy, content rules, settings API, share card."""
from datetime import datetime

import pytest

from app import auth, models, public_profiles
from app.middleware import PUBLIC_PROFILE_PATH
from app.routers import profiles as profiles_router

LONG_REVIEW = (
    "Interstellar works because the science never crowds out the family story at its center. The docking "
    "sequence is one of the most tense scenes I have seen, and the score keeps building pressure without "
    "feeling cheap. Some dialogue is clumsy, yet the time-dilation planet hit me hard on a rewatch and the final "
    "act ties the father and daughter threads together better than I remembered."
)


def member(db, name, active=True, **extra):
    user = models.User(username=name, email=f"{name.replace(' ', '_')}@example.com",
                       hashed_password=auth.get_password_hash("password123"),
                       is_verified=True, is_active=active, created_at=datetime(2025, 3, 4), **extra)
    db.add(user)
    db.flush()
    return user


def headers_for(user):
    return {"Authorization": f"Bearer {auth.create_user_access_token(user)}"}


def enable(db, user, **fields):
    profile = models.PublicProfile(user_id=user.id, enabled=True, **fields)
    db.add(profile)
    db.commit()
    return profile


def library(db, user):
    db.add_all([
        models.Movie(user_id=user.id, title="Interstellar", director="Christopher Nolan", year=2014, rating=10, watched=True,
                     review=LONG_REVIEW, review_public=True, poster_url="https://img.example/interstellar.jpg"),
        models.Movie(user_id=user.id, title="Arrival", director="Denis Villeneuve", year=2016, rating=9, watched=True),
        models.Movie(user_id=user.id, title="Meh Movie", director="Someone", year=2010, rating=5, watched=True),
        models.Book(user_id=user.id, title="Dune", author="Frank Herbert", year=1965, rating=9, read=True),
        models.Book(user_id=user.id, title="Secret Diary", author="Me", year=2020, rating=10, read=False,
                    review="My private thoughts about this diary are not for anyone else to read at all, ever, honestly.",
                    review_public=False),
    ])
    db.commit()


# ---------------------------------------------------------------- off by default

def test_profiles_are_off_by_default(client, db_session):
    user = member(db_session, "quietfan")
    library(db_session, user)
    assert client.get("/u/quietfan").status_code == 404
    assert client.get("/u/quietfan/card.png").status_code == 404
    assert client.get(f"/u/id/{user.id}").status_code == 404


def test_disabled_profile_row_stays_hidden(client, db_session):
    user = member(db_session, "paused")
    db_session.add(models.PublicProfile(user_id=user.id, enabled=False, bio="Hello there"))
    db_session.commit()
    assert client.get("/u/paused").status_code == 404


def test_deactivated_members_have_no_profile(client, db_session):
    user = member(db_session, "gonefan", active=False)
    enable(db_session, user)
    assert client.get("/u/gonefan").status_code == 404


# ---------------------------------------------------------------- page content

def test_profile_shows_chosen_sections(client, db_session):
    user = member(db_session, "cinephile")
    library(db_session, user)
    enable(db_session, user, bio="Sci-fi first, everything else second.")
    response = client.get("/u/cinephile")
    assert response.status_code == 200
    html = response.text
    assert "<h1>cinephile</h1>" in html
    assert "Member since March 2025" in html
    assert "Sci-fi first, everything else second." in html
    # Favorites: rated 8+ only, linked to title pages.
    assert 'href="/titles/movie/interstellar-2014"' in html
    assert 'href="/titles/movie/arrival-2016"' in html
    assert "Meh Movie" not in html
    # Only the public, community-ready review is shown.
    assert "/reviews/" in html and "Read the full review" in html
    assert "My private thoughts" not in html
    # Never the email.
    assert "cinephile@example.com" not in html
    assert response.headers["content-security-policy"]
    assert 'og:image" content="https://omnitrackr.xyz/u/cinephile/card.png"' in html


def test_private_categories_never_appear(client, db_session):
    user = member(db_session, "privatebooks", books_private=True)
    library(db_session, user)
    enable(db_session, user)
    html = client.get("/u/privatebooks").text
    assert "Dune" not in html and "Secret Diary" not in html
    assert "Interstellar" in html


def test_private_statistics_hide_library_counts(client, db_session):
    user = member(db_session, "nostats", statistics_private=True)
    library(db_session, user)
    enable(db_session, user)
    html = client.get("/u/nostats").text
    assert 'id="profile-stats"' not in html
    assert 'id="profile-favorites"' in html


def test_sections_can_be_switched_off(client, db_session):
    user = member(db_session, "minimal")
    library(db_session, user)
    enable(db_session, user, show_stats=False, show_favorites=False, show_reviews=False, show_collections=False)
    html = client.get("/u/minimal").text
    for marker in ('id="profile-stats"', 'id="profile-favorites"', 'id="profile-reviews"', 'id="profile-collections"'):
        assert marker not in html
    assert "hasn&#x27;t shared anything here yet" in html or "hasn't shared anything" in html


def test_suspended_and_unsafe_reviews_are_hidden(db_session):
    user = member(db_session, "reviewer")
    good = models.Movie(user_id=user.id, title="Interstellar", director="Nolan", year=2014, rating=9,
                        review=LONG_REVIEW, review_public=True)
    spam = models.Movie(user_id=user.id, title="Spam", director="x", year=2014, rating=9,
                        review=LONG_REVIEW + " Visit my site https://spam.example for more.", review_public=True)
    db_session.add_all([good, spam])
    db_session.commit()
    profile = enable(db_session, user)
    titles = [r["title"] for r in public_profiles.build(db_session, user, profile).reviews]
    assert titles == ["Interstellar"]
    from app.routers.reviews import _review_content_hash
    db_session.add(models.PublicReviewState(user_id=user.id, category="movie", item_id=good.id,
                                            content_hash=_review_content_hash("movie", good.id, good.review),
                                            report_count=3, suspended_at=datetime.utcnow()))
    db_session.commit()
    assert public_profiles.build(db_session, user, profile).reviews == []


def test_user_text_is_escaped(client, db_session):
    user = member(db_session, "escaper")
    db_session.add(models.Movie(user_id=user.id, title='<script>alert(1)</script>', director="x", year=2001, rating=9))
    db_session.commit()
    enable(db_session, user, bio="I like <b>bold</b> & \"quotes\"")
    html = client.get("/u/escaper").text
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<b>bold</b>" not in html


def test_thin_profiles_are_noindex(client, db_session):
    user = member(db_session, "thin")
    db_session.add(models.Movie(user_id=user.id, title="Arrival", director="x", year=2016, rating=9))
    db_session.commit()
    enable(db_session, user)
    response = client.get("/u/thin")
    assert response.headers.get("x-robots-tag") == "noindex, follow"
    assert '<meta name="robots" content="noindex, follow">' in response.text


def test_profiles_with_original_reviews_are_indexable_and_in_sitemap(client, db_session):
    user = member(db_session, "writer")
    library(db_session, user)
    enable(db_session, user)
    response = client.get("/u/writer")
    assert "x-robots-tag" not in response.headers
    assert '<meta name="robots" content="index, follow">' in response.text
    assert "/u/writer" in public_profiles.sitemap_paths(db_session)
    assert "/u/writer</loc>" in client.get("/sitemap.xml").text


def test_no_ads_on_profiles(client, db_session):
    user = member(db_session, "noads")
    library(db_session, user)
    enable(db_session, user)
    assert "ad-loader.js" not in client.get("/u/noads").text


# ---------------------------------------------------------------- addresses

def test_case_insensitive_lookup_redirects_to_canonical(client, db_session):
    user = member(db_session, "MixedCase")
    enable(db_session, user)
    response = client.get("/u/mixedcase", follow_redirects=False)
    assert response.status_code == 301 and response.headers["location"] == "/u/MixedCase"


def test_ambiguous_case_insensitive_names_do_not_guess(client, db_session):
    a, b = member(db_session, "Twin"), member(db_session, "TWIN")
    enable(db_session, a)
    enable(db_session, b)
    assert client.get("/u/twin").status_code == 404
    assert client.get("/u/Twin").status_code == 200


@pytest.mark.parametrize("username", ["admin_fan", "media", "web", "test"])
def test_usernames_that_look_like_scanner_paths_still_work(client, db_session, username):
    user = member(db_session, username)
    library(db_session, user)
    enable(db_session, user)
    assert client.get(f"/u/{username}").status_code == 200
    assert client.get(f"/u/{username}/card.png").status_code == 200


def test_unusual_usernames_use_an_id_address(client, db_session):
    user = member(db_session, "Jane Doe")
    enable(db_session, user)
    assert public_profiles.profile_path(user) == f"/u/id/{user.id}"
    assert client.get(f"/u/id/{user.id}").status_code == 200
    assert client.get(f"/u/id/{user.id}/card.png").status_code == 200


def test_id_address_redirects_to_username_address(client, db_session):
    user = member(db_session, "plainname")
    enable(db_session, user)
    response = client.get(f"/u/id/{user.id}", follow_redirects=False)
    assert response.status_code == 301 and response.headers["location"] == "/u/plainname"


@pytest.mark.parametrize("path", ["/u/.env", "/u/a%2Fb", "/u/admin/../.env", "/u/id/abc"])
def test_bot_filter_still_blocks_scanner_paths(client, path):
    assert client.get(path).status_code == 404


def test_profile_path_pattern_matches_routes():
    assert PUBLIC_PROFILE_PATH.match("/u/admin_fan")
    assert PUBLIC_PROFILE_PATH.match("/u/web/card.png")
    assert PUBLIC_PROFILE_PATH.match("/u/id/42")
    assert not PUBLIC_PROFILE_PATH.match("/u/.env")
    assert not PUBLIC_PROFILE_PATH.match("/u/admin/.env")
    assert not PUBLIC_PROFILE_PATH.match("/u/web/config.js")


# ---------------------------------------------------------------- settings API

def test_settings_require_sign_in(client):
    assert client.get("/api/profile/settings").status_code == 401
    assert client.put("/api/profile/settings", json={"enabled": True}).status_code == 401


def test_settings_round_trip(client, db_session):
    user = member(db_session, "settler", movies_private=True)
    db_session.commit()
    data = client.get("/api/profile/settings", headers=headers_for(user)).json()
    assert data["enabled"] is False and data["url"] == "/u/settler"
    assert data["private_categories"] == ["Movies"]
    response = client.put("/api/profile/settings", headers=headers_for(user),
                          json={"enabled": True, "bio": "  Hello\r\n\r\n\r\nworld  ", "show_reviews": False})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["enabled"] is True and data["bio"] == "Hello\n\nworld" and data["show_reviews"] is False
    assert data["show_stats"] is True
    assert response.headers["cache-control"] == "private, no-store"
    # Partial update leaves other fields alone.
    data = client.put("/api/profile/settings", headers=headers_for(user), json={"enabled": False}).json()
    assert data["enabled"] is False and data["bio"] == "Hello\n\nworld"
    assert db_session.query(models.PublicProfile).filter_by(user_id=user.id).count() == 1


@pytest.mark.parametrize("bio", [
    "Find me at https://example.com",
    "email me: me@example.com",
    "call +1 555 123 4567 8",
    "Online casino bonus inside",
    "x" * 281,
])
def test_unsafe_or_long_bios_are_rejected(client, db_session, bio):
    user = member(db_session, "bioguy")
    db_session.commit()
    response = client.put("/api/profile/settings", headers=headers_for(user), json={"enabled": True, "bio": bio})
    assert response.status_code == 422
    assert db_session.query(models.PublicProfile).filter_by(user_id=user.id).first() is None


def test_bio_control_characters_are_removed():
    assert public_profiles.clean_bio("Hi‮there\u0000!") == "Hithere!"
    assert public_profiles.clean_bio("   ") is None
    assert public_profiles.clean_bio(None) is None


def test_settings_only_change_your_own_profile(client, db_session):
    a, b = member(db_session, "alpha"), member(db_session, "bravo")
    db_session.commit()
    client.put("/api/profile/settings", headers=headers_for(a), json={"enabled": True, "user_id": b.id})
    assert db_session.query(models.PublicProfile).filter_by(user_id=b.id).first() is None
    assert db_session.query(models.PublicProfile).filter_by(user_id=a.id).one().enabled is True


def test_owner_sees_edit_hint_and_others_do_not(client, db_session):
    a, b = member(db_session, "owner1"), member(db_session, "viewer1")
    enable(db_session, a)
    token = auth.create_user_access_token(a)
    client.cookies.set(auth.AUTH_COOKIE_NAME, token)
    assert "This is your public profile" in client.get("/u/owner1").text
    client.cookies.set(auth.AUTH_COOKIE_NAME, auth.create_user_access_token(b))
    page = client.get("/u/owner1")
    assert "This is your public profile" not in page.text
    assert page.headers["cache-control"] == "private, no-store"
    client.cookies.clear()
    page = client.get("/u/owner1")
    assert page.headers["cache-control"].startswith("public") and "Start tracking free" in page.text


# ---------------------------------------------------------------- links from elsewhere

def test_title_and_review_pages_link_to_enabled_profiles(client, db_session):
    on, off = member(db_session, "sharer"), member(db_session, "hider")
    for user in (on, off):
        db_session.add(models.Movie(user_id=user.id, title="Interstellar", director="Christopher Nolan", year=2014,
                                    rating=9, review=LONG_REVIEW, review_public=True))
    db_session.commit()
    enable(db_session, on)
    page = client.get("/titles/movie/interstellar-2014").text
    assert 'href="/u/sharer"' in page and 'href="/u/hider"' not in page and "hider" in page
    review = db_session.query(models.Movie).filter_by(user_id=on.id).one()
    detail = client.get(f"/reviews/{review.id}?category=movie").text
    assert 'class="review-author-link" href="/u/sharer"' in detail
    index = client.get("/reviews").text
    assert 'href="/u/sharer"' in index and 'href="/u/hider"' not in index


def test_enabled_profile_paths_skip_disabled_and_inactive(db_session):
    a, b, c = member(db_session, "p1"), member(db_session, "p2"), member(db_session, "p3", active=False)
    enable(db_session, a)
    db_session.add(models.PublicProfile(user_id=b.id, enabled=False))
    enable(db_session, c)
    assert public_profiles.enabled_profile_paths(db_session, [a.id, b.id, c.id, None]) == {a.id: "/u/p1"}


# ---------------------------------------------------------------- share card

def test_share_card_is_a_png_and_cached(client, db_session):
    user = member(db_session, "carded")
    library(db_session, user)
    enable(db_session, user, bio="Hello")
    profiles_router._CARD_CACHE._items.clear()
    response = client.get("/u/carded/card.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert len(profiles_router._CARD_CACHE._items) == 1
    client.get("/u/carded/card.png")
    assert len(profiles_router._CARD_CACHE._items) == 1


def test_share_card_handles_long_names_and_no_data(db_session):
    user = member(db_session, "x" * 50)
    profile = enable(db_session, user)
    png = profiles_router.render_card(public_profiles.build(db_session, user, profile))
    from PIL import Image
    import io
    assert Image.open(io.BytesIO(png)).size == (1200, 630)


def test_card_cache_is_bounded():
    cache = profiles_router._CardCache(size=3)
    for index in range(5):
        cache.put((index, "f"), b"x")
    assert len(cache._items) == 3
    cache.clear_user(4)
    assert (4, "f") not in cache._items


def test_duplicate_library_entries_show_once(db_session):
    user = member(db_session, "doubler")
    for _ in range(3):
        db_session.add(models.Movie(user_id=user.id, title="Interstellar", director="Nolan", year=2014, rating=10,
                                    review=LONG_REVIEW, review_public=True))
    db_session.commit()
    view = public_profiles.build(db_session, user, enable(db_session, user))
    assert [f["title"] for f in view.favorites] == ["Interstellar"]
    assert len(view.reviews) == 1
