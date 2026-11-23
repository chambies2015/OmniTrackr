"""Supporter numbers, the founding supporter deadline, December's founding note and the note at the end of guides."""
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from app import auth, digest, guide_layout, migrations, models, support_asks, supporters
from app.site_traffic import RECORDER

TOKEN = "kofi-test-token"
CHROME = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"}
DECEMBER = datetime(2026, 12, 10, 15, 0)


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setenv("KOFI_VERIFICATION_TOKEN", TOKEN)
    monkeypatch.delenv("KOFI_MONTHLY_GOAL", raising=False)
    monkeypatch.delenv("KOFI_MONTHLY_COSTS", raising=False)
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    RECORDER._pending.clear()
    yield
    RECORDER._pending.clear()


def member(db, name, days_old=200, visit_days=40, titles=0):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=True, is_active=True, created_at=datetime.utcnow() - timedelta(days=days_old),
                       visit_days=visit_days)
    db.add(user)
    db.flush()
    for i in range(titles):
        db.add(models.Movie(title=f"Film {i}", director="X", year=2001, watched=True, user_id=user.id))
    db.commit()
    return user


def headers(user):
    return {"Authorization": f"Bearer {auth.create_user_access_token(user)}", **CHROME}


def pay(client, message_id, email, **fields):
    data = {"verification_token": TOKEN, "message_id": message_id, "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "type": "Donation", "is_public": True, "from_name": "A fan", "message": "", "amount": "3.00",
            "url": "https://ko-fi.com/x", "email": email, "currency": "USD", "is_subscription_payment": False,
            "is_first_subscription_payment": False, "kofi_transaction_id": message_id, "tier_name": None}
    data.update(fields)
    response = client.post("/api/kofi/webhook", data={"data": json.dumps(data)})
    assert response.status_code == 200, response.text
    return response


def counted(key):
    return sum(amount for (_, kind, name), amount in RECORDER._pending.items() if kind == "support" and name == key)


# ---------------------------------------------------------------- supporter numbers

def test_supporters_are_numbered_in_order_and_keep_their_number(client, db_session):
    first, second = member(db_session, "ana"), member(db_session, "ben")
    assert supporters.next_number(db_session) == 1
    pay(client, "m-1", "ana@example.com")
    pay(client, "m-2", "ben@example.com")
    pay(client, "m-3", "ana@example.com")  # a second coffee doesn't renumber anyone
    db_session.expire_all()
    assert supporters.get_supporter(db_session, first.id).number == 1
    assert supporters.get_supporter(db_session, second.id).number == 2
    assert supporters.next_number(db_session) == 3
    status = client.get("/api/supporter", headers=headers(first)).json()
    assert status["number"] == 1
    assert status["level"] == "Founding supporter #1 · 2 months"


def test_level_label_reads_well_with_and_without_a_number():
    assert supporters.level_label(True, 1, 1) == "Founding supporter #1"
    assert supporters.level_label(False, 4, 12) == "Supporter #12 · 4 months"
    assert supporters.level_label(False, 1, None) == "Supporter"
    assert supporters.level_label(True, 1, 0) == "Founding supporter"


def test_the_number_shows_on_the_profile_badge_and_review_chip(client, db_session):
    user = member(db_session, "ana")
    pay(client, "m-1", "ana@example.com")
    db_session.add(models.PublicProfile(user_id=user.id, enabled=True))
    db_session.commit()
    page = client.get("/u/ana").text
    assert "Founding supporter #1</a>" in page
    assert 'title="Founding supporter #1 of OmniTrackr on Ko-fi since' in page
    badge = supporters.public_badges(db_session, [user.id])[user.id]
    assert badge["number"] == 1
    assert 'title="Founding supporter #1 of OmniTrackr on Ko-fi since' in supporters.chip_html(badge)


def test_the_startup_migration_numbers_older_supporters_oldest_first(db_session, monkeypatch):
    monkeypatch.setattr(migrations, "engine", db_session.get_bind())
    users = [member(db_session, name) for name in ("ana", "ben", "cy")]
    base = datetime(2026, 10, 1)
    for user, days in zip(users, (5, 1, 3)):
        db_session.add(models.Supporter(user_id=user.id, since=base + timedelta(days=days), active_until=base + timedelta(days=40)))
    db_session.commit()
    db_session.execute(text("UPDATE supporters SET number = 7 WHERE user_id = :id"), {"id": users[2].id})
    db_session.commit()
    migrations.add_supporter_number_column()
    db_session.expire_all()
    numbers = {user.username: supporters.get_supporter(db_session, user.id).number for user in users}
    assert numbers == {"ben": 8, "ana": 9, "cy": 7}
    migrations.add_supporter_number_column()  # running again changes nothing
    db_session.expire_all()
    assert {user.username: supporters.get_supporter(db_session, user.id).number for user in users} == numbers


# ---------------------------------------------------------------- the founding supporter deadline

def test_deadline_words_count_down_through_december():
    assert supporters.founding_deadline(datetime(2026, 11, 23)) == "Founding supporter is open until December 31, 2026."
    assert supporters.founding_deadline(datetime(2026, 12, 10, 23, 59)) == (
        "22 days left to become a founding supporter. It closes on December 31.")
    assert supporters.founding_deadline(datetime(2026, 12, 31, 8)) == (
        "December 31 is the last day to become a founding supporter.")
    assert supporters.founding_deadline(datetime(2027, 1, 1)) is None
    assert supporters.founding_days_left(datetime(2027, 3, 1)) == 0


def test_supporters_page_offers_number_one_while_nobody_has_supported(client, db_session, monkeypatch):
    monkeypatch.setattr(supporters, "_now", lambda: datetime(2026, 12, 20, 12))
    page = client.get("/supporters").text
    assert "Nobody has supported OmniTrackr yet. Whoever goes first is <strong>supporter #1</strong>" in page
    assert "12 days left to become a founding supporter. It closes on December 31." in page
    assert "★ Founding supporter #1</span>" in page
    assert "Nobody has it yet, so #1 is still open." in page


def test_supporters_page_names_the_next_number_and_the_wall_shows_numbers(client, db_session):
    user = member(db_session, "ana")
    pay(client, "m-1", "ana@example.com")
    supporters.get_supporter(db_session, user.id).on_wall = True
    db_session.commit()
    page = client.get("/supporters").text
    assert "The next supporter will be <strong>#2</strong>." in page
    assert "The next one is #2." in page
    assert '<small class="support-wall__number">#1</small>' in page
    assert "Nobody has supported" not in page


def test_supporters_page_drops_the_deadline_in_2027(client, db_session, monkeypatch):
    monkeypatch.setattr(supporters, "_now", lambda: datetime(2027, 1, 2))
    page = client.get("/supporters").text
    assert "support-hero__founding" not in page
    assert "♥ Supporter #1</span>" in page


# ---------------------------------------------------------------- December's founding note

def test_founding_note_shows_in_december_to_members_who_never_supported(db_session):
    user = member(db_session, "maya", visit_days=10, titles=3)
    assert support_asks.candidate(db_session, user, None, datetime(2026, 11, 30, 23)) is None
    found = support_asks.candidate(db_session, user, None, DECEMBER)
    assert found["moment"] == "founding" and found["key"] == "founding:2026"
    assert support_asks.candidate(db_session, user, None, datetime(2027, 1, 1)) is None


def test_founding_note_words(db_session, monkeypatch):
    user = member(db_session, "maya")
    monkeypatch.setattr(support_asks, "_now", lambda: DECEMBER)
    monkeypatch.setattr(supporters, "_now", lambda: DECEMBER)
    words = support_asks.copy_for(db_session, user, "founding", "founding:2026")
    assert words["eyebrow"] == "22 days left"
    assert words["title"] == "Founding supporter closes on December 31"
    assert "stays a founding supporter for good" in words["body"]
    assert "Nobody has supported yet, so the first one gets #1 on their badge." in words["body"]
    monkeypatch.setattr(support_asks, "_now", lambda: datetime(2026, 12, 31, 9))
    monkeypatch.setattr(supporters, "_now", lambda: datetime(2026, 12, 31, 9))
    assert support_asks.copy_for(db_session, user, "founding", "founding:2026")["eyebrow"] == "Last day"


def test_founding_note_follows_the_usual_rules(db_session):
    newcomer = member(db_session, "new", visit_days=10)
    newcomer.created_at = DECEMBER - timedelta(days=10)
    db_session.commit()
    assert support_asks.candidate(db_session, newcomer, None, DECEMBER) is None
    past = member(db_session, "past", visit_days=10)
    db_session.add(models.Supporter(user_id=past.id, since=datetime(2026, 10, 1), active_until=datetime(2026, 10, 31)))
    db_session.commit()
    found = support_asks.candidate(db_session, past, None, DECEMBER)
    assert found is None or found["moment"] != "founding"  # already a founding supporter
    stopped = member(db_session, "stopped")
    db_session.add(models.SupportAsk(user_id=stopped.id, stopped_at=datetime(2026, 11, 1)))
    db_session.commit()
    assert support_asks.candidate(db_session, stopped, support_asks.get_row(db_session, stopped.id), DECEMBER) is None
    recent = member(db_session, "recent")
    db_session.add(models.SupportAsk(user_id=recent.id, moment="titles", ask_key="titles:100", shown_at=datetime(2026, 11, 20)))
    db_session.commit()
    assert support_asks.candidate(db_session, recent, support_asks.get_row(db_session, recent.id), DECEMBER) is None


def test_founding_note_shows_once_and_covers_reached_milestones(db_session):
    user = member(db_session, "maya", titles=101)
    assert support_asks.mark_shown(db_session, user, "founding:2026", now=DECEMBER)
    row = support_asks.get_row(db_session, user.id)
    assert row.moment == "founding" and row.titles_done == 100
    assert counted("ask_shown_founding") == 1
    later = DECEMBER + timedelta(days=8)
    assert support_asks.candidate(db_session, user, row, later) is None


def test_site_stats_list_the_founding_moment(db_session):
    data = support_asks.stats(db_session, 30, datetime.utcnow())
    assert any(row["moment"] == "Last month to be a founding supporter" for row in data["asks"])
    assert data["elsewhere_kofi"] == [{"place": "End of a written guide", "count": 0}]


# ---------------------------------------------------------------- weekly email

def test_weekly_email_line_mentions_founding_in_december_only():
    december = support_asks.email_note(DECEMBER)
    assert december["text"].endswith("Anyone who supports before 2027 stays a founding supporter for good.")
    january = support_asks.email_note(datetime(2027, 1, 12))
    assert "founding" not in january["text"] and "$3 coffee" in january["text"]
    report = {"matches": [], "popular": [{"title": "Dune", "label": "Movie", "date": "2026-12-01", "url": "/x"}]}
    _, html, plain = digest.build_digest("maya", report, "https://x/unsub", support=december)
    assert "founding supporter for good" in html and "founding supporter for good" in plain


# ---------------------------------------------------------------- the note at the end of written guides

PAGE = (
    '<html><head></head><body><main>'
    '<article class="trail-guide"><header class="hero hero--guide"><h1>A guide</h1>'
    '<p class="guide-byline">By OmniTrackr · Updated <time datetime="2026-11-01">November 1, 2026</time></p></header>'
    '<div class="guide-intro"><p>' + "word " * 400 + '</p></div><section id="faq"><h2>Questions</h2></section>'
    '</article></main></body></html>'
)


def test_guides_end_with_the_support_note(monkeypatch):
    monkeypatch.setattr(supporters, "_now", lambda: DECEMBER)
    html = guide_layout.add_reading_layout(PAGE)
    body = html.split('<div class="guide-body">', 1)[1].split('<aside class="guide-rail"', 1)[0]
    assert body.index('id="faq"') < body.index('<aside class="guide-support"')
    assert 'href="https://ko-fi.com/omnitrackr" data-guide-kofi target="_blank" rel="noopener noreferrer"' in body
    assert 'href="/supporters?from=guide"' in body
    assert "stays a founding supporter for good" in body
    assert "2 min read" in html  # the note doesn't count toward the reading time
    assert html.count("<div") == html.count("</div>")
    monkeypatch.setattr(supporters, "_now", lambda: datetime(2027, 2, 1))
    assert "guide-support__founding" not in guide_layout.add_reading_layout(PAGE)


def test_live_guides_carry_the_note_once(client):
    for path in ("/if-you-liked/interstellar", "/in-order/star-wars", "/holidays/gifts"):
        html = client.get(path).text
        assert html.count('<aside class="guide-support"') == 1, path
        assert html.index('<aside class="guide-support"') < html.index('<aside class="guide-rail"'), path


def test_guide_ko_fi_presses_are_counted_without_the_reader(client):
    response = client.post("/api/support/event", json={"event": "page_kofi", "place": "guide"}, headers=CHROME)
    assert response.status_code == 204
    assert counted("page_kofi_guide") == 1
    client.post("/api/support/event", json={"event": "page_seen", "place": "guide"}, headers=CHROME)
    assert counted("page_seen_guide") == 1
    client.post("/api/support/event", json={"event": "page_kofi", "place": "nowhere"}, headers=CHROME)
    assert counted("page_kofi_nowhere") == 0


def test_recap_ask_mentions_founding_before_2027(client, db_session):
    from app.routers import year_in_review
    user = member(db_session, "maya")
    box = year_in_review._support_box(db_session, user, 2026)
    assert "numbered badge" in box
    assert ("stays a founding supporter for good" in box) == supporters.founding_open()
