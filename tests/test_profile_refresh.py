"""Public profile refresh (Oct 2026): headline numbers, tabs, About sidebar, visitor sign-up, share tags and card."""
import io
import json
import re

from PIL import Image

from app import auth, funnel, models, public_profiles
from app.routers import profiles as profiles_router
from tests.test_public_profiles import enable, library, member


def test_guest_page_has_numbers_tabs_sidebar_and_signup(client, db_session):
    user = member(db_session, "refreshed")
    library(db_session, user)
    enable(db_session, user, bio="Sci-fi first.")
    html = client.get("/u/refreshed").text
    assert 'class="profile-numbers"' in html and "titles tracked" in html
    assert 'class="title-tabs profile-tabs"' in html
    for anchor in ("#profile-stats", "#profile-favorites", "#profile-reviews"):
        assert f'href="{anchor}"' in html
    assert "About refreshed" in html and "Taste mix" in html
    assert "Make your own profile, free" in html and "data-profile-joinbar" in html
    assert 'href="/taste-quiz"' in html and "profile-page--guest" in html
    assert "Start tracking free" in html  # the closing card stays


def test_tabs_only_name_sections_on_the_page(client, db_session):
    user = member(db_session, "fewtabs")
    library(db_session, user)
    enable(db_session, user, show_reviews=False, show_collections=False)
    html = client.get("/u/fewtabs").text
    assert 'href="#profile-reviews"' not in html and 'href="#profile-collections"' not in html


def test_private_statistics_leave_out_numbers_and_mix(client, db_session):
    user = member(db_session, "hushnumbers", statistics_private=True)
    library(db_session, user)
    enable(db_session, user)
    html = client.get("/u/hushnumbers").text
    assert "titles tracked" not in html and "Taste mix" not in html and "Biggest shelf" not in html


def test_owner_and_members_get_no_signup_prompts(client, db_session):
    owner, other = member(db_session, "ownerview"), member(db_session, "otherview")
    library(db_session, owner)
    enable(db_session, owner)
    client.cookies.set(auth.AUTH_COOKIE_NAME, auth.create_user_access_token(owner))
    html = client.get("/u/ownerview").text
    assert 'href="/#public-profile">Edit profile' in html
    assert "data-profile-join" not in html and "data-profile-joinbar" not in html
    client.cookies.set(auth.AUTH_COOKIE_NAME, auth.create_user_access_token(other))
    html = client.get("/u/ownerview").text
    assert "Edit profile" not in html and "data-profile-join" not in html
    client.cookies.clear()


def test_share_tags_and_structured_data(client, db_session):
    user = member(db_session, "sharetags")
    library(db_session, user)
    enable(db_session, user, bio="</script><script>alert(1)</script>")
    html = client.get("/u/sharetags").text
    assert 'name="twitter:image" content="https://omnitrackr.xyz/u/sharetags/card.png"' in html
    assert 'property="og:image:alt"' in html and 'property="profile:username" content="sharetags"' in html
    raw = re.search(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S).group(1)
    assert "<" not in raw
    data = json.loads(raw)
    assert data["@type"] == "ProfilePage" and data["mainEntity"]["name"] == "sharetags"


def test_poster_wall_needs_three_posters_and_no_banner(db_session):
    user = member(db_session, "wallfan")
    profile = enable(db_session, user)
    view = public_profiles.build(db_session, user, profile)
    assert profiles_router._wall_html(view) == ""
    view.favorites = [{"image": f"https://img.example/{n}.jpg"} for n in range(4)]
    assert profiles_router._wall_html(view).count("<img") == 4
    view.supporter = {"banner": "aurora"}
    assert profiles_router._wall_html(view) == ""


def test_card_draws_the_profile_picture(db_session):
    user = member(db_session, "pictured")
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (255, 0, 0)).save(buffer, format="PNG")
    user.profile_picture_data = buffer.getvalue()
    profile = enable(db_session, user)
    card = Image.open(io.BytesIO(profiles_router.render_card(public_profiles.build(db_session, user, profile))))
    assert card.size == (1200, 630)
    assert card.getpixel((154, 210))[0] > 200  # inside the avatar circle
    user.profile_picture_data = b"not an image"
    assert profiles_router.render_card(public_profiles.build(db_session, user, profile))


def test_profile_funnel_events_are_known():
    assert "profile_link_opened" in funnel.SERVER_EVENTS and "profile_link_opened" not in funnel.CLIENT_EVENTS
    assert "profile_signup_clicked" in funnel.CLIENT_EVENTS
