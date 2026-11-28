"""Supporter app themes, avatar frames, the /supporters try-on and running costs (Nov 2026)."""
from datetime import datetime, timedelta
from pathlib import Path

from app import models, supporters
from tests.test_supporters import headers_for, kofi_token, member  # noqa: F401 (kofi_token is autouse)

ROOT = Path(__file__).resolve().parents[1]


def _supporter(db, user, *, since=datetime(2027, 2, 1), days=20, member_days=None, tier=None, **fields):
    row = models.Supporter(user_id=user.id, since=since, active_until=datetime.utcnow() + timedelta(days=days), **fields)
    if member_days is not None:
        row.monthly = True
        row.tier = tier
        row.member_until = datetime.utcnow() + timedelta(days=member_days)
    db.add(row)
    return row


def test_non_supporters_cannot_save_a_theme_or_frame(client, db_session):
    user = member(db_session, "jo")
    db_session.commit()
    data = client.get("/api/supporter", headers=headers_for(user)).json()
    assert data["unlocked_themes"] == [] and data["unlocked_frames"] == [] and data["shown_theme"] is None
    assert "lagoon" in data["themes"] and "midnight" in data["member_themes"] and "orbit" in data["member_frames"]
    assert client.put("/api/supporter", headers=headers_for(user), json={"app_theme": "lagoon"}).status_code == 403


def test_supporter_picks_a_theme_and_frame(client, db_session):
    user = member(db_session, "sam")
    _supporter(db_session, user)
    db_session.commit()
    data = client.get("/api/supporter", headers=headers_for(user)).json()
    assert data["unlocked_themes"] == list(supporters.APP_THEMES)
    assert data["unlocked_frames"] == list(supporters.FRAMES)

    saved = client.put("/api/supporter", headers=headers_for(user), json={"app_theme": "sakura", "frame": "film"})
    assert saved.status_code == 200
    assert saved.json()["app_theme"] == "sakura" and saved.json()["shown_theme"] == "sakura" and saved.json()["frame"] == "film"

    assert client.put("/api/supporter", headers=headers_for(user), json={"app_theme": "midnight"}).status_code == 403
    assert client.put("/api/supporter", headers=headers_for(user), json={"frame": "neon"}).status_code == 403
    assert client.put("/api/supporter", headers=headers_for(user), json={"app_theme": "gilded"}).status_code == 403
    assert client.put("/api/supporter", headers=headers_for(user), json={"app_theme": "<b>"}).status_code == 422
    cleared = client.put("/api/supporter", headers=headers_for(user), json={"app_theme": None, "frame": None}).json()
    assert cleared["app_theme"] is None and cleared["frame"] is None


def test_members_and_gold_unlock_more_themes(client, db_session):
    user = member(db_session, "pop")
    _supporter(db_session, user, since=datetime(2026, 11, 1), member_days=20, tier="popcorn")
    db_session.commit()
    data = client.get("/api/supporter", headers=headers_for(user)).json()
    assert {"gilded", "midnight", "matinee"} <= set(data["unlocked_themes"])  # founding brings gold
    assert set(data["unlocked_frames"]) == set(supporters.ALL_FRAMES)
    assert client.put("/api/supporter", headers=headers_for(user), json={"app_theme": "matinee", "frame": "orbit"}).status_code == 200


def test_a_lapse_hides_the_theme_and_frame_but_keeps_the_picks(client, db_session):
    user = member(db_session, "gone")
    db_session.add(models.PublicProfile(user_id=user.id, enabled=True))
    row = _supporter(db_session, user, member_days=10, tier="season_pass", app_theme="midnight", avatar_frame="neon",
                     banner_motion=True)
    db_session.commit()
    assert supporters.public_badge(db_session, user.id)["frame_motion"] is True
    assert 'avatar-frame avatar-frame--neon avatar-frame--motion' in client.get("/u/gone").text

    row.member_until = datetime.utcnow() - timedelta(days=1)  # membership ended, a tip keeps basic perks on
    db_session.commit()
    data = client.get("/api/supporter", headers=headers_for(user)).json()
    assert data["app_theme"] == "midnight" and data["shown_theme"] is None and data["frame"] == "neon"
    assert supporters.public_badge(db_session, user.id)["frame"] is None
    assert "avatar-frame--neon" not in client.get("/u/gone").text


def test_profile_without_a_frame_keeps_the_old_markup(client, db_session):
    user = member(db_session, "plain")
    db_session.add(models.PublicProfile(user_id=user.id, enabled=True))
    _supporter(db_session, user)
    db_session.commit()
    page = client.get("/u/plain").text
    assert "profile-hero__frame" not in page and 'class="profile-hero__avatar' in page


def test_costs_parse_and_fill_in_the_goal(monkeypatch):
    monkeypatch.delenv("KOFI_MONTHLY_GOAL", raising=False)
    monkeypatch.setenv("KOFI_MONTHLY_COSTS", "Web server: $25; Database=20\nnonsense; Email: 15.5; Domain: lots")
    assert supporters.monthly_costs() == [{"label": "Web server", "amount": 25.0}, {"label": "Database", "amount": 20.0},
                                          {"label": "Email", "amount": 15.5}]
    assert supporters.monthly_goal() == 60.5
    monkeypatch.setenv("KOFI_MONTHLY_GOAL", "100")
    assert supporters.monthly_goal() == 100
    monkeypatch.delenv("KOFI_MONTHLY_COSTS")
    monkeypatch.delenv("KOFI_MONTHLY_GOAL")
    assert supporters.monthly_costs() == [] and supporters.monthly_goal() is None


def test_supporters_page_shows_costs_and_the_try_on(client, monkeypatch):
    monkeypatch.delenv("KOFI_MONTHLY_GOAL", raising=False)
    monkeypatch.delenv("KOFI_MONTHLY_COSTS", raising=False)
    html = client.get("/supporters").text
    assert "Where the money goes" in html and "support-costs--plain" in html and "support-goal" not in html
    assert 'data-try="theme" data-value="midnight"' in html and 'data-try="frame" data-value="orbit"' in html
    assert "<!--SUPPORTERS_" not in html

    monkeypatch.setenv("KOFI_MONTHLY_COSTS", "Web server: 30; <b>DB</b>: 10")
    html = client.get("/supporters").text
    assert "support-costs__fill--75" in html and "&lt;b&gt;DB&lt;/b&gt;" in html and "<b>DB</b>" not in html
    assert "About <strong>$40</strong> a month in all." in html and "support-goal" in html


def test_style_migration_adds_empty_columns(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect, text
    from app import migrations

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE supporters (id INTEGER PRIMARY KEY, user_id INTEGER, accent VARCHAR(16))"))
        conn.execute(text("INSERT INTO supporters (id, user_id, accent) VALUES (1, 7, 'teal')"))
        conn.commit()
    monkeypatch.setattr(migrations, "engine", engine)
    migrations.add_supporter_style_columns()
    migrations.add_supporter_style_columns()  # safe on every boot
    with engine.connect() as conn:
        row = conn.execute(text("SELECT accent, app_theme, avatar_frame FROM supporters")).one()
    assert tuple(row) == ("teal", None, None)
    assert {"app_theme", "avatar_frame"} <= {c["name"] for c in inspect(engine).get_columns("supporters")}


def test_theme_script_loads_before_the_page_paints():
    index = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
    body = index.index('<body class="dark-mode app-shell"')
    assert index.index('<script src="/static/app-themes.js', body) < index.index('<a class="skip-link"', body)
    script = (ROOT / "app" / "static" / "app-themes.js").read_text(encoding="utf-8")
    assert "innerHTML" not in script and "ot-color-mode" in script
