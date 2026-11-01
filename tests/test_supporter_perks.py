"""Supporter perks added in Oct 2026: founding supporters, months supported, gold, the wall and the hosting goal."""
from datetime import datetime, timedelta

from app import models, supporters
from tests.test_supporters import headers_for, kofi_token, member, payment, post  # noqa: F401 (kofi_token is autouse)


def _supporter(db, user, *, since=datetime(2026, 10, 1), days=20, on_wall=False, accent=None, show_badge=True):
    row = models.Supporter(user_id=user.id, since=since, active_until=datetime.utcnow() + timedelta(days=days),
                           on_wall=on_wall, accent=accent, show_badge=show_badge)
    db.add(row)
    return row


def _payments(db, user, count, kind="subscription"):
    for i in range(count):
        db.add(models.KofiPayment(message_id=f"{user.id}-{kind}-{i}", kind=kind, monthly=kind == "subscription",
                                  user_id=user.id, amount="5.00", currency="USD", received_at=datetime.utcnow()))


def test_levels_are_counted_from_payments():
    assert supporters.level_label(True, 1) == "Founding supporter"
    assert supporters.level_label(False, 0) == "Supporter"
    assert supporters.level_label(False, 7) == "Supporter · 7 months"


def test_shop_orders_do_not_count_as_months(db_session):
    user = member(db_session, "jo")
    _payments(db_session, user, 2)
    _payments(db_session, user, 3, kind="shop order")
    db_session.commit()
    assert supporters.months_supported(db_session, user.id) == 2


def test_new_supporters_are_founding_until_2027(client, db_session):
    user = member(db_session, "jo")
    db_session.commit()
    post(client, payment())
    data = client.get("/api/supporter", headers=headers_for(user)).json()
    assert data["founding"] is True and data["months"] == 1 and data["level"] == "Founding supporter"
    assert "gold" in data["unlocked_accents"] and data["on_wall"] is False
    assert client.put("/api/supporter", headers=headers_for(user), json={"accent": "gold"}).status_code == 200


def test_gold_waits_for_six_months_after_the_founding_window(client, db_session):
    user = member(db_session, "late")
    _supporter(db_session, user, since=datetime(2027, 2, 1))
    _payments(db_session, user, 5)
    db_session.commit()
    data = client.get("/api/supporter", headers=headers_for(user)).json()
    assert data["founding"] is False and "gold" not in data["unlocked_accents"] and "emerald" in data["unlocked_accents"]
    assert client.put("/api/supporter", headers=headers_for(user), json={"accent": "gold"}).status_code == 403
    assert client.put("/api/supporter", headers=headers_for(user), json={"accent": "emerald"}).status_code == 200

    _payments(db_session, user, 1, kind="donation")
    db_session.commit()
    assert client.put("/api/supporter", headers=headers_for(user), json={"accent": "gold"}).status_code == 200


def test_profile_badge_shows_founding_and_months(client, db_session):
    user = member(db_session, "jo")
    db_session.add(models.PublicProfile(user_id=user.id, enabled=True))
    _supporter(db_session, user, accent="gold")
    _payments(db_session, user, 3)
    db_session.commit()
    page = client.get("/u/jo").text
    assert "★</span> Founding supporter · 3 months</a>" in page and "profile-hero--accent-gold" in page


def test_the_wall_is_opt_in(client, db_session):
    user = member(db_session, "shy")
    db_session.commit()
    post(client, payment(email="shy@example.com"))
    assert "support-wall__name" not in client.get("/supporters").text
    assert client.put("/api/supporter", headers=headers_for(user), json={"on_wall": True}).json()["on_wall"] is True
    assert supporters.get_supporter(db_session, user.id).on_wall is True
    assert ">shy</span>" in client.get("/supporters").text


def test_wall_lists_current_supporters_first_and_links_public_profiles(client, db_session):
    past = member(db_session, "past")
    now = member(db_session, "now")
    hidden = member(db_session, "hidden")
    db_session.add(models.PublicProfile(user_id=now.id, enabled=True))
    _supporter(db_session, past, since=datetime(2026, 1, 1), days=-5, on_wall=True, accent="rose")
    _supporter(db_session, now, since=datetime(2026, 6, 1), on_wall=True, accent="teal")
    _supporter(db_session, hidden, on_wall=False)
    db_session.commit()
    names = [entry["name"] for entry in supporters.wall(db_session)]
    assert names == ["now", "past"]
    html = client.get("/supporters").text
    assert '<a class="support-wall__name support-wall__name--teal" href="/u/now"' in html
    assert 'class="support-wall__name support-wall__name--past"' in html  # a lapsed supporter loses the accent
    assert "hidden" not in names


def test_wall_escapes_usernames(db_session, client):
    user = member(db_session, "x")
    user.username = '<b>x</b>'
    _supporter(db_session, user, on_wall=True)
    db_session.commit()
    html = client.get("/supporters").text
    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in html


def test_goal_meter_only_shows_when_configured(client, db_session, monkeypatch):
    user = member(db_session, "jo")
    _payments(db_session, user, 3)
    db_session.add(models.KofiPayment(message_id="eur", kind="donation", amount="50", currency="EUR", received_at=datetime.utcnow()))
    db_session.add(models.KofiPayment(message_id="old", kind="donation", amount="50", currency="USD",
                                      received_at=datetime.utcnow() - timedelta(days=40)))
    db_session.commit()
    monkeypatch.delenv("KOFI_MONTHLY_GOAL", raising=False)
    assert "support-goal" not in client.get("/supporters").text
    monkeypatch.setenv("KOFI_MONTHLY_GOAL", "$60")
    progress = supporters.goal_progress(db_session)
    assert progress["raised"] == 15 and progress["percent"] == 25
    html = client.get("/supporters").text
    assert "<strong>25%</strong> of $60 covered" in html and "support-goal__fill--25" in html
    monkeypatch.setenv("KOFI_MONTHLY_GOAL", "lots")
    assert supporters.goal_progress(db_session) is None


def test_supporter_count_hides_until_there_are_a_few(client, db_session):
    for name in ("a1", "a2"):
        _supporter(db_session, member(db_session, name))
    db_session.commit()
    assert "support-hero__count" not in client.get("/supporters").text
    _supporter(db_session, member(db_session, "a3"))
    db_session.commit()
    assert "<strong>3</strong> members support OmniTrackr right now." in client.get("/supporters").text


def test_wall_migration_keeps_existing_supporters_off_the_wall(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect, text
    from app import migrations

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE supporters (id INTEGER PRIMARY KEY, user_id INTEGER, accent VARCHAR(16))"))
        conn.execute(text("INSERT INTO supporters (id, user_id, accent) VALUES (1, 7, 'teal')"))
        conn.commit()
    monkeypatch.setattr(migrations, "engine", engine)

    migrations.add_supporter_wall_column()
    migrations.add_supporter_wall_column()  # Safe to run on every boot.

    assert "on_wall" in {c["name"] for c in inspect(engine).get_columns("supporters")}
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id, user_id, accent, on_wall FROM supporters")).one()
    assert tuple(row) == (1, 7, "teal", 0)
