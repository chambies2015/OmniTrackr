"""Sweep of the Nov 9 merges: the Nov 9 sweep itself (#191), Best of 2026 in nine
formats (#192), the library and home screen redesign (#193) and cover lookups that no
longer rename titles (#194)."""
import pathlib
from datetime import datetime

from app import models
from app.home_summary import build
from app.routers import best_of as best_of_router
from app.routers import statistics as statistics_router
from tests.test_security_sweep_nov06 import _limited

STATIC = pathlib.Path(__file__).resolve().parents[1] / "app" / "static"


def test_saving_a_best_of_pick_is_rate_limited():
    """/api/pick/add has 30 a minute; the manga, podcast and audiobook save had none."""
    assert _limited(best_of_router.router, "/api/best-of/add", "POST")


def test_the_welcome_strip_is_rate_limited():
    """About 20 queries a call, fetched after edits and when the tab comes back."""
    assert _limited(statistics_router.router, "/statistics/home/", "GET")


class TestBestOfCaching:
    def test_guests_get_a_cacheable_hub_again(self, client):
        # The hub was public for ten minutes until the member scorecard arrived; guests all see the same page.
        response = client.get("/best-of")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "public, max-age=600"
        assert "Cookie" in response.headers["vary"]

    def test_members_pages_are_not_stored(self, authenticated_client):
        for url in ("/best-of", "/best-of/2026/movies", "/best-of/2026/audiobooks"):
            response = authenticated_client.get(url)
            assert response.status_code == 200, url
            assert response.headers["cache-control"] == "private, no-store", url
            assert "Cookie" in response.headers["vary"], url

    def test_guest_list_pages_keep_their_headers(self, client):
        response = client.get("/best-of/2026/manga")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-cache"


def test_this_month_leaves_out_hidden_libraries(db_session, authenticated_client):
    user = db_session.query(models.User).filter(models.User.username == "testuser").one()
    now = datetime.utcnow()
    film = models.Movie(user_id=user.id, title="Arrival", year=2016, watched=True)
    book = models.Book(user_id=user.id, title="Piranesi", author="Susanna Clarke", year=2020, read=True)
    db_session.add_all([film, book])
    db_session.flush()
    for category, item in (("movies", film), ("books", book)):
        db_session.add(models.ActivityEntry(user_id=user.id, category=category, item_id=item.id, title=item.title,
                                            action="completed", source="automatic", occurred_at=now))
    db_session.commit()
    assert build(db_session, user, now=now)["finished_this_month"] == 2

    user.books_visible = False
    db_session.commit()
    summary = build(db_session, user, now=now)
    assert summary["finished"] == 1
    assert summary["finished_this_month"] == 1

    for key in ("movies", "tv_shows", "anime", "video_games", "music", "books", "manga", "podcasts", "audiobooks"):
        setattr(user, f"{key}_visible", False)
    db_session.commit()
    assert build(db_session, user, now=now)["finished_this_month"] == 0


def test_coming_back_to_the_tab_only_refetches_stale_numbers():
    script = (STATIC / "home-hero.js").read_text()
    assert "state.loadedAt = Date.now();" in script
    assert "Date.now() - state.loadedAt > STALE_MS) refreshSoon();" in script
