"""Homepage "What members are saying" section and the visitor funnel step (Oct 2026)."""
import pytest

from app import funnel, landing_proof, models
from app.site_traffic import RECORDER
from tests.test_review_discovery import STANDALONE

LONG = STANDALONE


def member(db, name, **extra):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_active=True, is_verified=True, **extra)
    db.add(user)
    db.flush()
    return user


def review(db, user, model=models.Movie, title="Arrival", text=LONG, **extra):
    item = model(user_id=user.id, title=title, review=text, review_public=True, rating=9, **extra)
    db.add(item)
    db.flush()
    return item


@pytest.fixture
def live_section(monkeypatch, db_session):
    landing_proof.clear_cache()
    monkeypatch.setattr(landing_proof, "homepage_section", lambda: landing_proof.build(db_session))
    yield
    landing_proof.clear_cache()


@pytest.mark.parametrize("count,expected", [(0, "0"), (99, "99"), (206, "200+"), (1461, "1,000+"), (12345, "12,000+")])
def test_round_down_never_inflates(count, expected):
    assert landing_proof.round_down(count) == expected


def test_pick_reviews_one_per_member_and_mixed_media():
    rows = [
        {"id": 1, "user_id": 1, "category": "movie", "title": "A", "search_ready": True},
        {"id": 2, "user_id": 1, "category": "anime", "title": "B", "search_ready": True},
        {"id": 3, "user_id": 2, "category": "movie", "title": "C", "search_ready": True},
        {"id": 4, "user_id": 3, "category": "book", "title": "D", "search_ready": True},
        {"id": 5, "user_id": 4, "category": "game", "title": "E", "search_ready": False},
        {"id": 6, "user_id": 5, "category": "movie", "title": " ", "search_ready": True},
    ]
    chosen = landing_proof.pick_reviews(rows)
    assert [r["id"] for r in chosen] == [1, 4, 3]


def test_section_needs_at_least_two_reviews():
    one = [{"id": 1, "user_id": 1, "category": "movie", "title": "A", "review": "x", "search_ready": True}]
    assert landing_proof.section_html(one, {"members": 500, "titles": 5000}) == ""


def test_section_escapes_member_text_and_only_links_profiles():
    rows = [
        {"id": 1, "user_id": 1, "category": "movie", "title": "<b>X</b>", "review": "<script>alert(1)</script> " + "word " * 80,
         "rating": 8.5, "username": "<img>", "profile_url": "javascript:alert(1)"},
        {"id": 2, "user_id": 2, "category": "book", "title": "Y", "review": "Fine.", "rating": None, "username": "bo",
         "profile_url": "/u/bo"},
    ]
    html = landing_proof.section_html(rows, {"members": 206, "titles": 1461})
    assert "<script>" not in html and "&lt;script&gt;" in html and "&lt;b&gt;X&lt;/b&gt;" in html
    assert "javascript:" not in html and '<a href="/u/bo">bo</a>' in html
    assert "8.5/10" in html and "/reviews/1?category=movie" in html
    assert "<strong>200+</strong> members" in html and "<strong>1,000+</strong> titles tracked" in html
    assert "…" in html  # long reviews are excerpted


def test_small_counts_are_not_shown():
    rows = [{"id": i, "user_id": i, "category": "movie", "title": "T", "review": "ok"} for i in (1, 2)]
    html = landing_proof.section_html(rows, {"members": 12, "titles": 40})
    assert "members</p>" not in html and "lp-voices__facts" not in html


def test_homepage_shows_real_public_reviews_only(client, db_session, live_section):
    a, b, c = member(db_session, "ann"), member(db_session, "ben"), member(db_session, "cal")
    review(db_session, a, title="Arrival")
    review(db_session, b, model=models.Book, title="Piranesi")
    private = models.Movie(user_id=c.id, title="Private One", review=LONG, review_public=False, rating=7)
    db_session.add(private)
    db_session.commit()
    html = client.get("/").text
    assert "What members are saying" in html
    assert "Arrival" in html and "Piranesi" in html and "Private One" not in html


def test_homepage_hides_the_section_without_enough_reviews(client, db_session, live_section):
    review(db_session, member(db_session, "ann"))
    db_session.commit()
    assert "What members are saying" not in client.get("/").text


def test_section_failures_never_break_the_homepage(client, monkeypatch):
    def boom():
        raise RuntimeError("db down")
    monkeypatch.setattr(landing_proof, "homepage_section", boom)
    response = client.get("/")
    assert response.status_code == 200 and "What members are saying" not in response.text


# ---------------------------------------------------------------- visitor funnel step

@pytest.fixture
def recorder(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    RECORDER._pending.clear()
    yield RECORDER
    RECORDER._pending.clear()


def counted(recorder, event):
    return sum(n for (day, kind, key), n in recorder._pending.items() if kind == "funnel" and key == event)


def test_visitor_homepage_views_are_counted(client, recorder):
    client.get("/")
    assert counted(recorder, "landing_viewed") == 1
    assert funnel.STEPS[0][0] == "landing_viewed"


def test_members_heads_bots_and_link_clicks_are_not_counted(client, recorder):
    client.head("/")
    client.get("/", headers={"user-agent": "Googlebot/2.1"})
    client.get("/?token=abc&email_verified=true")
    client.cookies.set("omnitrackr_session", "x")
    client.get("/")
    assert counted(recorder, "landing_viewed") == 0
