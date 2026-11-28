"""Sweep of the Nov 4-5 merges: the "Share your reviews" card (#180), supporter app themes
and avatar frames (#181) and the guide cross-links and editorial ledger (#182)."""
from app import models, review_inbox, review_quality
from app.routers import review_inbox as review_inbox_router
from app.routers import supporters as supporters_router
from tests.test_supporter_styles import _supporter
from tests.test_supporters import headers_for, kofi_token, member  # noqa: F401 (kofi_token is autouse)
from tests.test_title_pages import ESSAY, add_movie


def _limited(router, path, method):
    for route in router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return hasattr(route.endpoint, "__wrapped__")
    raise AssertionError(f"no route {method} {path}")


def test_every_review_card_route_is_rate_limited():
    """The list reads up to 400 private reviews per format, so it has a limit like the writes."""
    for route in review_inbox_router.router.routes:
        for method in route.methods:
            assert _limited(review_inbox_router.router, route.path, method), (method, route.path)


def test_saving_supporter_settings_is_rate_limited():
    assert _limited(supporters_router.router, "/api/supporter", "PUT")


class TestSiteStatsLeavesTheReviewCacheAlone:
    """Site stats checks every member's private reviews. Those checks used to go into the
    cache the public feeds, homepage and sitemap share, so on a big enough site one visit
    could push every public review out of it."""

    def test_stats_does_not_add_private_reviews_to_the_shared_cache(self, db_session):
        add_movie(db_session, member(db_session, "writer"), review=ESSAY)
        db_session.commit()
        review_quality._evaluated.clear()

        assert review_inbox.stats(db_session, 30)["waiting"] == 1
        assert len(review_quality._evaluated) == 0

    def test_not_remembering_gives_the_same_answer(self):
        review_quality._evaluated.clear()
        quiet = review_quality.evaluate_public_review(ESSAY, 80, 240, remember=False)
        assert len(review_quality._evaluated) == 0
        assert quiet == review_quality.evaluate_public_review(ESSAY, 80, 240)
        assert len(review_quality._evaluated) == 1
        # A cached answer is still used, and still not moved or duplicated.
        assert review_quality.evaluate_public_review(ESSAY, 80, 240, remember=False) == quiet
        assert len(review_quality._evaluated) == 1


class TestProfileFrameStyles:
    """Every public profile loaded avatar-frames.css, though only supporters who pick a frame use it."""

    def test_profile_without_a_frame_skips_the_stylesheet(self, client, db_session):
        user = member(db_session, "plainprofile")
        db_session.add(models.PublicProfile(user_id=user.id, enabled=True))
        db_session.commit()
        html = client.get("/u/plainprofile").text
        assert "profile-hero" in html and "avatar-frames.css" not in html

    def test_profile_with_a_frame_loads_it(self, client, db_session):
        user = member(db_session, "framedprofile")
        db_session.add(models.PublicProfile(user_id=user.id, enabled=True))
        _supporter(db_session, user, avatar_frame="halo")
        db_session.commit()
        html = client.get("/u/framedprofile").text
        assert "avatar-frame--halo" in html and "/static/avatar-frames.css?v=" in html

    def test_a_lapsed_frame_skips_it_too(self, client, db_session):
        user = member(db_session, "lapsedframe")
        db_session.add(models.PublicProfile(user_id=user.id, enabled=True))
        _supporter(db_session, user, days=-1, avatar_frame="halo")
        db_session.commit()
        assert "avatar-frames.css" not in client.get("/u/lapsedframe").text


def test_review_card_script_skips_the_request_while_hidden():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "app/static/review-inbox.js").read_text()
    refresh = source[source.index("async function refresh()"):source.index("function init()")]
    assert refresh.index("hiddenForNow()") < refresh.index("fetch(")
