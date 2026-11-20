"""Sweep of the Nov 20 night merges: the March 2027 challenge (#269) and the winter 2027
TV, games, movies and books release guides (#270, #271)."""
from datetime import datetime

from app import models, new_releases
from app.routers import challenges as challenges_router
from tests.test_security_sweep_nov06 import _limited


def _member(db_session, name):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.flush()
    return user


def test_every_challenge_api_route_is_rate_limited():
    """Joining, leaving and sharing had limits. The card itself, "seen" and unsharing had none,
    and in March the card adds up to 20 queries for the "format you hardly ever finish" step."""
    checked = 0
    for route in challenges_router.router.routes:
        if not route.path.startswith("/api/"):
            continue
        for method in route.methods:
            assert _limited(challenges_router.router, route.path, method), (method, route.path)
            checked += 1
    assert checked == 6


def test_the_card_still_loads_with_its_limit(authenticated_client):
    response = authenticated_client.get("/api/challenge")
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "private, no-store"
    assert authenticated_client.post("/api/challenge/seen").status_code == 404
    assert authenticated_client.delete("/api/challenge/share").status_code == 404


def test_a_shared_march_card_names_all_nine_formats_and_never_the_members_formats(client, db_session):
    """The share page said "movies, shows, anime, games, music and books", six formats, under a
    challenge about trying any of nine. It also must not show which formats count for the member."""
    user = _member(db_session, "marchsharer")
    db_session.add(models.MonthlyChallengeEntry(user_id=user.id, month="2027-03", completed_at=datetime(2027, 3, 12),
                                                share_token="marchSweepToken1"))
    db_session.commit()
    page = client.get("/challenge/marchSweepToken1")
    assert page.status_code == 200
    assert "Finish something in a format you hardly ever finish" in page.text
    assert "manga, podcasts and audiobooks" in page.text
    assert "music and books." not in page.text
    assert "Counts for you" not in page.text


def test_the_challenges_index_describes_nine_formats(client):
    page = client.get("/challenges")
    assert page.status_code == 200
    assert "music, books, manga, podcasts and audiobooks, with a written guide" in page.text


def test_llms_txt_points_at_the_release_guides(client):
    text = client.get("/llms.txt").text
    assert f"{new_releases.BASE_PATH} pick the new movies" in text
    newest = list(new_releases.published())[:2]
    assert newest and all(new_releases.path(slug) in text for slug in newest)
    assert "{release_line}" not in text and "\nRelease guides at" in text
